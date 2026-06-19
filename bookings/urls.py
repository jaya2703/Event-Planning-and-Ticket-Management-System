from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('book/<int:event_id>/', views.book_ticket, name='book'),
    path('<int:booking_id>/', views.booking_detail, name='detail'),
    path('history/', views.booking_history, name='history'),
    path('<int:booking_id>/cancel/', views.cancel_booking, name='cancel'),
    path('<int:booking_id>/download/', views.download_ticket_pdf, name='download_pdf'),
    path('checkin/<uuid:booking_uuid>/', views.verify_checkin, name='verify_checkin'),
    path('scan/', views.scan_qr, name='scan_qr'),
]
