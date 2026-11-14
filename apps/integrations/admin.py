from django.contrib import admin

from .models import AICategorization, AIQuery, DATEVConfig, PaperlessDocumentLink


@admin.register(DATEVConfig)
class DATEVConfigAdmin(admin.ModelAdmin):
    list_display = ("advisor_number", "client_number", "fiscal_year", "skr", "is_active")
    list_filter = ("is_active", "skr")


@admin.register(PaperlessDocumentLink)
class PaperlessDocumentLinkAdmin(admin.ModelAdmin):
    list_display = ("transaction", "document_id", "title", "match_score", "created_at")
    search_fields = ("document_id", "title")


@admin.register(AICategorization)
class AICategorizationAdmin(admin.ModelAdmin):
    list_display = ("transaction", "model", "category", "confidence", "accepted", "created_at")
    list_filter = ("model", "accepted")


@admin.register(AIQuery)
class AIQueryAdmin(admin.ModelAdmin):
    list_display = ("question", "row_count", "created_at", "error")
    readonly_fields = ("question", "generated_sql", "row_count", "error", "created_at")
