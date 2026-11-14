from django.contrib import admin

from .models import DepotPosition, ScrapeRun


@admin.register(DepotPosition)
class DepotPositionAdmin(admin.ModelAdmin):
    list_display = ("name", "isin", "account", "quantity", "price", "market_value", "updated_at")
    search_fields = ("name", "isin", "yahoo_symbol")
    list_filter = ("account", "currency")


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = ("scraper", "account", "status", "items_found", "documents_saved", "created_at")
    list_filter = ("scraper", "status")
