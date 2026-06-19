"""
Main URL Configuration
======================
This file is the "traffic controller" of our website.
It decides which URL goes to which app.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from events import views as event_views

urlpatterns = [
    # Django admin panel (for superuser only)
    path('admin/', admin.site.urls),
    
    # Home page
    path('', event_views.home, name='home'),
    
    # All accounts URLs (login, register, dashboard, etc.)
    path('accounts/', include('accounts.urls')),
    
    # All event URLs (list, detail, create, etc.)
    path('events/', include('events.urls')),
    
    # All booking URLs
    path('bookings/', include('bookings.urls')),
    
    # All payment URLs
    path('payments/', include('payments.urls')),
    
    # All volunteer URLs
    path('volunteers/', include('volunteers.urls')),
    
    # Notifications
    path('notifications/', include('notifications.urls')),
]

# This tells Django to serve uploaded files (banners, QR codes) during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
