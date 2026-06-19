from django.db import models
from django.conf import settings
from events.models import Event


class VolunteerAssignment(models.Model):
    """Assigns a volunteer to an event under an organizer"""
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
        limit_choices_to={'role': 'volunteer'}
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='volunteers')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='helpdesk')
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['volunteer', 'event']
    
    def __str__(self):
        return f"{self.volunteer.username} -> {self.event.title} ({self.role})"
