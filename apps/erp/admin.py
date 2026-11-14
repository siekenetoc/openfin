from django.contrib import admin

from .models import ERPConfig, ExpectedPayment, PurchaseInvoice, ReconciliationMatch


@admin.register(ERPConfig)
class ERPConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "erp_base_url", "company", "is_active")
    list_filter = ("is_active",)


@admin.register(ExpectedPayment)
class ExpectedPaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice_id", "customer_name", "amount", "due_date", "status")
    list_filter = ("status", "currency")
    search_fields = ("invoice_id", "customer_name", "erp_name")
    date_hierarchy = "due_date"


@admin.register(ReconciliationMatch)
class ReconciliationMatchAdmin(admin.ModelAdmin):
    list_display = ("transaction", "expected_payment", "score", "stage", "status", "created_at")
    list_filter = ("status", "stage")


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_id", "supplier", "amount", "due_date", "status")
    list_filter = ("status",)
    search_fields = ("invoice_id", "supplier", "erp_name")
