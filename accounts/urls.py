from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('admin-panel/', views.admin_dashboard_view, name='admin_dashboard'),
    path('users/', views.user_management_view, name='user_management'),
    path('api/users/create/', views.create_user_api, name='create_user_api'),
    path('api/users/<int:user_id>/toggle-role/', views.toggle_user_role_api, name='toggle_role_api'),
    path('api/users/<int:user_id>/toggle-active/', views.toggle_user_active_api, name='toggle_active_api'),
    path('api/users/<int:user_id>/delete/', views.delete_user_api, name='delete_user_api'),
    path('api/users/<int:user_id>/reset-password/', views.reset_user_password_api, name='reset_password_api'),
]
