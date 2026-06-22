from django.urls import path
from . import views, manage_views
from django.contrib.auth import views as auth_views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('switch-account/', views.switch_account_view, name='switch_account'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('dashboard/organizer/', views.organizer_dashboard_view, name='organizer_dashboard'),
    path('dashboard/user/', views.user_dashboard_view, name='user_dashboard'),
    path('wishlist/toggle/<int:event_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    # Custom admin panel (no Django admin UI)
    path('manage/users/', manage_views.manage_users, name='manage_users'),
    path('manage/users/<int:user_id>/toggle/', manage_views.toggle_user_active, name='toggle_user'),
    path('manage/events/', manage_views.manage_events, name='manage_events'),
    path('manage/payments/', manage_views.manage_payments, name='manage_payments'),
    path('manage/categories/', manage_views.manage_categories, name='manage_categories'),
    path('manage/audit/', manage_views.audit_logs, name='audit_logs'),
    path('manage/export/<str:report_type>/', manage_views.export_report, name='export_report'),
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('notification/<int:notification_id>/read/', views.mark_notification_read, name='mark_read'),
    
    # Django's built-in password reset (uses email)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html'
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),
]
