from django.urls import path
from . import views

app_name = "curation"

urlpatterns = [
    path("", views.index, name="index"),
    path("archive/", views.archive_view, name="archive"),
    path("api/curate/", views.api_curate, name="api_curate"),
    path("api/status/", views.api_settings_status, name="api_status"),
    path("api/usage/", views.api_usage_stats, name="api_usage_stats"),
    path("api/keywords/", views.api_keywords, name="api_keywords"),
    path("api/keywords/reorder/", views.api_keywords_reorder, name="api_keywords_reorder"),
    path("api/keywords/<int:keyword_id>/", views.api_keyword_detail, name="api_keyword_detail"),
    path("api/keywords/reset/", views.api_keywords_reset, name="api_keywords_reset"),
    path("api/articles/save/", views.api_save_article, name="api_save_article"),
    path("api/articles/<int:article_id>/delete/", views.api_delete_article, name="api_delete_article"),
    path("api/articles/<int:article_id>/memo/", views.api_update_article_memo, name="api_update_article_memo"),
    path("api/articles/list/", views.api_saved_articles_list, name="api_saved_articles_list"),
    path("api/articles/check-saved/", views.api_check_saved_urls, name="api_check_saved_urls"),
]
