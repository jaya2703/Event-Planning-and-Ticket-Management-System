from django.db import models
from django.conf import settings

class AttendeeProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendee_profile')
    company = models.CharField(max_length=150, blank=True, null=True)
    job_title = models.CharField(max_length=150, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    opt_in_networking = models.BooleanField(default=False)
    skills_interests = models.CharField(max_length=500, blank=True, null=True, help_text="Comma-separated interests/skills")

    def __str__(self):
        return f"Networking: {self.user.username}"


class MeetingRequest(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_meetings')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_meetings')
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='meetings')
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')],
        default='pending'
    )
    proposed_time = models.DateTimeField()
    table_number = models.CharField(max_length=50, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Meeting: {self.sender.username} -> {self.receiver.username} ({self.status})"
