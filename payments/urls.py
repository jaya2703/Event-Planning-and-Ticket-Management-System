from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('process/<int:booking_id>/', views.process_payment, name='process'),
    path('success/<int:booking_id>/', views.payment_success, name='success'),
    path('failed/<int:booking_id>/', views.payment_failed, name='failed'),
    path('refund/<int:booking_id>/', views.request_refund, name='refund'),
    path('refund/<int:booking_id>/success/', views.refund_success, name='refund_success'),
]
