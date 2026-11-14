from django.contrib import admin

from .models import (
    PaymentEvent,
    PaymentLink,
    PaymentProviderConfig,
    SEPAMandate,
    SepaBatch,
    SepaBatchItem,
)


class SepaBatchItemInline(admin.TabularInline):
    model = SepaBatchItem
    extra = 0
    readonly_fields = ("end_to_end_id", "created_at")


@admin.register(SEPAMandate)
class SEPAMandateAdmin(admin.ModelAdmin):
    list_display = ("debtor_name", "mandate_reference", "debtor_iban", "mandate_type", "sequence_type", "is_active")
    list_filter = ("mandate_type", "sequence_type", "is_active")
    search_fields = ("debtor_name", "mandate_reference", "debtor_iban")


@admin.register(SepaBatch)
class SepaBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_id", "account", "collection_date", "total_amount", "status", "created_at")
    list_filter = ("status", "collection_date")
    inlines = [SepaBatchItemInline]
    readonly_fields = ("batch_id", "message_id", "total_amount", "xml_file", "created_at")


@admin.register(SepaBatchItem)
class SepaBatchItemAdmin(admin.ModelAdmin):
    list_display = ("batch", "mandate", "amount", "status", "prenotified_at")
    list_filter = ("status",)


@admin.register(PaymentLink)
class PaymentLinkAdmin(admin.ModelAdmin):
    list_display = ("provider", "expected_payment", "amount", "status", "created_at")
    list_filter = ("provider", "status")


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "event_type", "processed", "signature_valid", "created_at")
    list_filter = ("provider", "processed", "signature_valid")
    readonly_fields = ("payload",)


@admin.register(PaymentProviderConfig)
class PaymentProviderConfigAdmin(admin.ModelAdmin):
    list_display = ("provider", "mode", "is_active", "merchant_id")
    list_filter = ("provider", "is_active")
