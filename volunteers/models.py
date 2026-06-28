from django.db import models
from django.conf import settings
from events.models import Event


class DutyArea(models.Model):
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='duty_areas', null=True, blank=True)
    name = models.CharField(max_length=100)
    is_global = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['event', 'name']

    def __str__(self):
        return self.name


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
    duty = models.CharField(max_length=30, choices=DUTY_CHOICES, default='registration', null=True, blank=True)
    duty_area = models.ForeignKey(DutyArea, on_delete=models.SET_NULL, null=True, blank=True, related_name='volunteers')
    role = models.CharField(max_length=50, blank=True, default='Volunteer')
    shift_timing = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    notes = models.TextField(blank=True, default='')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_present = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        duty_name = self.duty_area.name if self.duty_area else self.get_duty_display()
        return f"{self.name} — {self.event.title} ({self.role} @ {duty_name})"


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


class Shift(models.Model):
    """Event staff/volunteer shift schedules"""
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='shifts')
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shifts')
    duty = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Shift: {self.staff.username} - {self.event.title}"


class Task(models.Model):
    """Staff/volunteer tasks checklist"""
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='tasks')
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assigned_tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('ongoing', 'Ongoing'), ('completed', 'Completed')],
        default='pending'
    )
    due_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Task: {self.title} -> {self.assignee.username}"

