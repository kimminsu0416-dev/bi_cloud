from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('users/', views.user_management_view, name='user_management'),
    path('api/users/create/', views.create_user_api, name='create_user_api'),
    path('api/users/<int:user_id>/delete/', views.delete_user_api, name='delete_user_api'),
    path('api/users/<int:user_id>/reset-password/', views.reset_user_password_api, name='reset_password_api'),
]
