"""Playwright-basierte Scraper für Amazon-Bestellungen und Nicht-FinTS-Kreditkarten."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger("openfin.scrapers")


@dataclass
class ScrapedOrder:
    order_id: str
    order_date: str
    total: str
    items: list[str] = field(default_factory=list)
    invoice_url: str = ""
    invoice_path: str = ""


def parse_amazon_orders_html(html: str) -> list[ScrapedOrder]:
    soup = BeautifulSoup(html, "html.parser")
    orders: list[ScrapedOrder] = []
    containers = soup.select("[data-order-id], .order-card, .js-order-card")
    seen = set()
    for container in containers:
        order_id = container.get("data-order-id") or ""
        if not order_id:
            match = re.search(r"\b(\d{3}-\d{7}-\d{7})\b", container.get_text(" ", strip=True))
            order_id = match.group(1) if match else f"amazon-{uuid.uuid4().hex[:10]}"
        if order_id in seen:
            continue
        seen.add(order_id)
        text = container.get_text(" ", strip=True)
        date_match = re.search(r"(\d{1,2}\.\s*\w+\s*\d{4})", text)
        total_match = re.search(r"(\d+[.,]\d{2})\s*€", text)
        items = [
            item.get_text(" ", strip=True)
            for item in container.select(".product-title, .a-link-normal")
            if item.get_text(" ", strip=True)
        ][:10]
        invoice_link = container.select_one(
            'a[href*="invoice"], a[href*="rechnung"], a[href*="print.html"], a[href*="orderID"]'
        )
        orders.append(
            ScrapedOrder(
                order_id=order_id,
                order_date=date_match.group(1) if date_match else "",
                total=(total_match.group(1).replace(".", "").replace(",", ".") if total_match else "0.00"),
                items=items,
                invoice_url=invoice_link.get("href", "") if invoice_link else "",
            )
        )
    return orders


class AmazonScraper:
    """Persistenter Chromium-Kontext (Bind-Mount), Login optional per Credentials."""

    name = "amazon"

    def __init__(self, account, credentials: dict | None = None):
        self.account = account
        self.credentials = credentials or (account.credentials or {})
        self.profile_dir = Path(
            getattr(settings, "PLAYWRIGHT_PROFILES_DIR", settings.BASE_DIR / "docker-data" / "playwright_profiles")
        ) / f"amazon_{account.pk}"
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    def scrape(self, max_orders: int = 25) -> list[ScrapedOrder]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright ist nicht installiert.") from exc

        orders: list[ScrapedOrder] = []
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(self.profile_dir),
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
                locale="de-DE",
            )
            page = context.new_page()
            try:
                page.goto("https://www.amazon.de/gp/css/order-history?ref_=nav_orders_first", wait_until="domcontentloaded")
                if "signin" in page.url or "ap/signin" in page.url:
                    page.goto("https://www.amazon.de/ap/signin", wait_until="domcontentloaded")
                    if self.credentials.get("email"):
                        page.fill("#ap_email", self.credentials["email"])
                        page.click("#continue")
                        page.wait_for_load_state("domcontentloaded")
                    if self.credentials.get("password"):
                        page.fill("#ap_password", self.credentials["password"])
                        page.click("#signInSubmit")
                        page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(1500)
                orders = parse_amazon_orders_html(page.content())[:max_orders]
                for order in orders:
                    if order.invoice_url:
                        order.invoice_path = self._download_invoice(context, page, order)
            finally:
                context.close()
        return orders

    def _download_invoice(self, context, page, order: ScrapedOrder) -> str:
        try:
            url = order.invoice_url
            if url.startswith("/"):
                url = f"https://www.amazon.de{url}"
            response = context.request.get(url)
            if not response.ok:
                return ""
            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                return ""
            filename = f"invoices/amazon/{self.account.pk}/{order.order_id}-{uuid.uuid4().hex[:6]}.pdf"
            from django.core.files.base import ContentFile

            return default_storage.save(filename, ContentFile(response.body()))
        except Exception:  # noqa: BLE001
            logger.exception("Amazon-Rechnung konnte nicht geladen werden")
            return ""


class CreditCardScraper:
    """Generischer Playwright-Login-Scraper für Kreditkartenportale ohne FinTS."""

    name = "creditcard"

    def __init__(self, account, credentials: dict | None = None):
        self.account = account
        self.credentials = credentials or (account.credentials or {})
        self.profile_dir = Path(
            getattr(settings, "PLAYWRIGHT_PROFILES_DIR", settings.BASE_DIR / "docker-data" / "playwright_profiles")
        ) / f"creditcard_{account.pk}"
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    def scrape(self, max_transactions: int = 100) -> list[dict]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright ist nicht installiert.") from exc

        login_url = self.credentials.get("login_url")
        if not login_url:
            raise RuntimeError("credentials.login_url fehlt.")
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(self.profile_dir), headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = context.new_page()
            try:
                page.goto(login_url, wait_until="domcontentloaded")
                if self.credentials.get("username_selector") and self.credentials.get("username"):
                    page.fill(self.credentials["username_selector"], self.credentials["username"])
                if self.credentials.get("password_selector") and self.credentials.get("password"):
                    page.fill(self.credentials["password_selector"], self.credentials["password"])
                if self.credentials.get("submit_selector"):
                    page.click(self.credentials["submit_selector"])
                    page.wait_for_load_state("domcontentloaded")
                if self.credentials.get("transactions_url"):
                    page.goto(self.credentials["transactions_url"], wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
                html = page.content()
            finally:
                context.close()
        return self._parse_transactions(html, max_transactions)

    @staticmethod
    def _parse_transactions(html: str, limit: int) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for row in soup.select("table tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
            if len(cells) >= 3:
                rows.append(
                    {
                        "date": cells[0],
                        "description": cells[1],
                        "amount": cells[-1],
                    }
                )
            if len(rows) >= limit:
                break
        return rows
