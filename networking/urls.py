from django.urls import path
from . import views

app_name = 'networking'

urlpatterns = [
    path('directory/', views.attendee_directory, name='directory'),
    path('profile/update/', views.update_networking_profile, name='update_profile'),
    path('meetings/', views.meeting_list, name='meetings'),
    path('meeting/request/<int:receiver_id>/', views.send_meeting_request, name='send_request'),
    path('meeting/respond/<int:meeting_id>/', views.respond_meeting_request, name='respond_request'),
]
