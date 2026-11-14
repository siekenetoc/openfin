from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from apps.banking.models import BankAccount, StandingOrder
from apps.erp.models import ExpectedPayment


def cashflow_forecast(days: int = 30, start: date | None = None) -> dict:
    """Einfache 30/60/90-Tage-Liquiditätsprognose aus Salden, offenen Posten und Daueraufträgen."""
    start = start or date.today()
    end = start + timedelta(days=days)

    balances = BankAccount.objects.filter(is_active=True).aggregate(total=Sum("balance"))["total"] or Decimal("0.00")
    incoming = (
        ExpectedPayment.objects.filter(
            status=ExpectedPayment.Status.OPEN,
            due_date__gte=start,
            due_date__lte=end,
            amount__gt=0,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    outgoing = Decimal("0.00")
    standing_items = []
    for order in StandingOrder.objects.filter(is_active=True):
        occurrences = _occurrences_between(order, start, end)
        if not occurrences:
            continue
        amount = order.amount * occurrences
        outgoing += amount
        standing_items.append(
            {
                "recipient": order.recipient_name,
                "amount": str(amount),
                "occurrences": occurrences,
                "interval": order.interval,
            }
        )

    delta = incoming - outgoing
    return {
        "days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "opening_balance": str(balances),
        "expected_incoming": str(incoming),
        "expected_outgoing": str(outgoing),
        "expected_delta": str(delta),
        "projected_balance": str(balances + delta),
        "standing_orders": standing_items,
    }


def _occurrences_between(order: StandingOrder, start: date, end: date) -> int:
    current = order.start_date
    if current > end:
        return 0
    if order.end_date and order.end_date < start:
        return 0
    step_days = {"weekly": 7, "monthly": 30, "quarterly": 91, "yearly": 365}.get(order.interval, 30)
    count = 0
    while current <= end:
        if current >= start:
            count += 1
        current += timedelta(days=step_days)
    return count
