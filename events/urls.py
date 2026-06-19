from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.event_list, name='list'),
    path('<int:event_id>/', views.event_detail, name='detail'),
    path('create/', views.create_event, name='create'),
    path('<int:event_id>/edit/', views.edit_event, name='edit'),
    path('<int:event_id>/delete/', views.delete_event, name='delete'),
    path('<int:event_id>/poll/add/', views.add_poll, name='add_poll'),
]
