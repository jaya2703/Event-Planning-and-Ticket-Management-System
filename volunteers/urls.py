from django.urls import path
from . import views

app_name = 'volunteers'

urlpatterns = [
    path('', views.volunteer_overview, name='overview'),
    path('event/<int:event_id>/', views.manage_event_volunteers, name='manage'),
    path('assign/<int:event_id>/', views.manage_event_volunteers, name='assign'),
    path('<int:volunteer_id>/edit/', views.edit_volunteer, name='edit'),
]
