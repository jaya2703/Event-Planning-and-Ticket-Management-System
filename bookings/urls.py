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
    path('export/<int:event_id>/', views.export_attendees_csv, name='export_csv'),
    path('import/<int:event_id>/', views.import_attendees_csv, name='import_csv'),
    path('register/<int:event_id>/', views.manual_registration, name='manual_registration'),
    path('<int:booking_id>/badge/', views.badge_generation, name='badge'),
    path('api/sync/', views.api_offline_sync, name='api_sync'),
]
