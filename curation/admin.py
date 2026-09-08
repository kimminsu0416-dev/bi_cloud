from django.contrib import admin
from .models import Keyword, ApiUsage, SavedArticle


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "name", "is_active", "created_at")
    list_display_links = ("name",)
    list_editable = ("order", "is_active")
    search_fields = ("name",)


@admin.register(ApiUsage)
class ApiUsageAdmin(admin.ModelAdmin):
    list_display = ("date", "call_count", "created_at")
    ordering = ("-date",)


@admin.register(SavedArticle)
class SavedArticleAdmin(admin.ModelAdmin):
    list_display = ("keyword", "title", "press", "user", "created_at")
    list_filter = ("keyword", "press", "created_at")
    search_fields = ("title", "keyword", "business_implication", "memo")

