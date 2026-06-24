from django.db import models
from django.conf import settings
from events.models import Event


class EventVolunteer(models.Model):
    """Event staff member — managed by organizer, not a platform login role."""

    DUTY_CHOICES = [
        ('registration', 'Registration Desk'),
        ('entry_gate', 'Entry Gate'),
        ('security', 'Security Support'),
        ('parking', 'Parking Assistance'),
        ('food', 'Food Counter'),
        ('technical', 'Technical Support'),
        ('stage', 'Stage Management'),
        ('helpdesk', 'Help Desk'),
        ('logistics', 'Logistics'),
    ]

    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('inactive', 'Inactive'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='event_volunteers')
    name = models.CharField(max_length=120)
    mobile = models.CharField(max_length=15, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    duty = models.CharField(max_length=30, choices=DUTY_CHOICES, default='registration')
    shift_timing = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_present = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} — {self.event.title} ({self.get_duty_display()})"


class VolunteerAssignment(models.Model):
    """Legacy: linked platform users to events. Superseded by EventVolunteer."""

    ROLE_CHOICES = [
        ('registration', 'Registration Desk'),
        ('security', 'Security'),
        ('helpdesk', 'Help Desk'),
        ('technical', 'Technical Support'),
        ('logistics', 'Logistics'),
    ]

    volunteer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='volunteer_assignments',
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='volunteers')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='helpdesk')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['volunteer', 'event']

    def __str__(self):
        return f"{self.volunteer.username} -> {self.event.title} ({self.role})"
