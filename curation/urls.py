from django.urls import path
from . import views

app_name = "curation"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/curate/", views.api_curate, name="api_curate"),
    path("api/status/", views.api_settings_status, name="api_status"),
    path("api/usage/", views.api_usage_stats, name="api_usage_stats"),
    path("api/keywords/", views.api_keywords, name="api_keywords"),
    path("api/keywords/reorder/", views.api_keywords_reorder, name="api_keywords_reorder"),
    path("api/keywords/<int:keyword_id>/", views.api_keyword_detail, name="api_keyword_detail"),
    path("api/keywords/reset/", views.api_keywords_reset, name="api_keywords_reset"),
]
