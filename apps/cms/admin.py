from django.contrib import admin

from .models import ContentPage


@admin.register(ContentPage)
class ContentPageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "tenant", "is_published", "show_in_footer", "updated_at")
    list_filter = ("is_published", "show_in_footer", "tenant")
    search_fields = ("title", "slug", "content_html")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
