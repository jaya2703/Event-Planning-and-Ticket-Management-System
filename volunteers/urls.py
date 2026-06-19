from django.urls import path
from . import views

app_name = 'volunteers'

urlpatterns = [
    path('assign/<int:event_id>/', views.assign_volunteer, name='assign'),
]
