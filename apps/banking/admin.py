from django.contrib import admin

from .models import (
    BankAccount,
    BankPartner,
    BankTransaction,
    CategoryRule,
    OutgoingPayment,
    StandingOrder,
    TANChallenge,
)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "account_type", "provider", "masked_iban", "balance", "needs_tan", "last_sync_at")
    list_filter = ("account_type", "provider", "needs_tan", "is_active")
    search_fields = ("name", "iban", "holder", "bank_name")
    readonly_fields = ("balance_updated_at", "last_sync_at", "created_at")


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ("booking_date", "account", "amount", "counterparty_name", "status", "confidence_score")
    list_filter = ("status", "account", "currency")
    search_fields = ("purpose", "counterparty_name", "counterparty_iban", "external_id")
    date_hierarchy = "booking_date"


@admin.register(BankPartner)
class BankPartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "iban", "customer_ref", "email")
    search_fields = ("name", "iban", "customer_ref")


@admin.register(CategoryRule)
class CategoryRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "pattern", "category", "cost_center", "priority", "is_active")
    list_filter = ("is_active",)


@admin.register(TANChallenge)
class TANChallengeAdmin(admin.ModelAdmin):
    list_display = ("account", "operation", "tan_type", "status", "created_at", "expires_at")
    list_filter = ("status", "tan_type", "operation")
    readonly_fields = ("dialog_state", "challenge_image", "payload", "created_at", "completed_at")


@admin.register(OutgoingPayment)
class OutgoingPaymentAdmin(admin.ModelAdmin):
    list_display = ("created_at", "account", "recipient_name", "amount", "payment_type", "status")
    list_filter = ("status", "payment_type", "account")
    search_fields = ("recipient_name", "recipient_iban", "purpose", "reference")


@admin.register(StandingOrder)
class StandingOrderAdmin(admin.ModelAdmin):
    list_display = ("recipient_name", "account", "amount", "interval", "start_date", "is_active", "pending_action")
    list_filter = ("is_active", "interval", "pending_action")
