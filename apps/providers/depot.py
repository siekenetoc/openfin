from __future__ import annotations

import logging
from decimal import Decimal

from django.utils import timezone

from .models import DepotPosition

logger = logging.getLogger("openfin.depot")


def refresh_position_prices(account) -> dict:
    positions = list(account.depot_positions.all())
    if not positions:
        return {"status": "empty", "updated": 0}
    updated = 0
    try:
        import yfinance as yf

        for position in positions:
            symbol = position.yahoo_symbol or position.isin
            try:
                ticker = yf.Ticker(symbol)
                fast = getattr(ticker, "fast_info", None)
                price = None
                if fast:
                    price = fast.get("last_price") or fast.get("lastPrice")
                if price is None:
                    history = ticker.history(period="1d")
                    if not history.empty:
                        price = history["Close"].iloc[-1]
                if price:
                    position.price = Decimal(str(round(float(price), 4)))
                    position.price_source = f"yfinance:{symbol}"
                    position.updated_at = timezone.now()
                    position.save(update_fields=["price", "price_source", "updated_at"])
                    updated += 1
            except Exception:  # noqa: BLE001
                logger.warning("Kurs für %s konnte nicht aktualisiert werden", position.isin)
    except Exception:  # noqa: BLE001
        logger.exception("yfinance nicht verfügbar")
        return {"status": "error", "updated": 0}
    return {"status": "ok", "updated": updated, "total": len(positions)}


def depot_summary(account) -> dict:
    positions = list(account.depot_positions.all())
    total = sum((position.market_value for position in positions), Decimal("0.00"))
    return {
        "account": account,
        "positions": positions,
        "total_value": total,
        "position_count": len(positions),
    }
