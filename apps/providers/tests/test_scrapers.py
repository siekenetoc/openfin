from apps.providers.scrapers import parse_amazon_orders_html


AMAZON_HTML = """
<html><body>
<div class="order-card" data-order-id="302-1234567-1234567">
  <span>Bestellt am 12. März 2026</span>
  <div class="product-title">USB-C Kabel 2m</div>
  <div class="product-title">Maus</div>
  <span>Gesamt: 29,99 €</span>
  <a href="/gp/css/summary/print.html?orderID=302-1234567-1234567">Rechnung</a>
</div>
<div data-order-id="305-7654321-7654321">
  <span>Bestellt am 1. April 2026</span>
  <div class="product-title">Tastatur</div>
  <span>Gesamt: 1.049,00 €</span>
</div>
</body></html>
"""


def test_parse_amazon_orders():
    orders = parse_amazon_orders_html(AMAZON_HTML)
    assert len(orders) == 2
    assert orders[0].order_id == "302-1234567-1234567"
    assert orders[0].total == "29.99"
    assert "USB-C Kabel 2m" in orders[0].items
    assert orders[0].invoice_url.startswith("/gp/")
    assert orders[1].total == "1049.00"


def test_parse_amazon_orders_deduplicates():
    orders = parse_amazon_orders_html(AMAZON_HTML + AMAZON_HTML)
    assert len(orders) == 2
