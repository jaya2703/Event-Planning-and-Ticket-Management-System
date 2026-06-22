"""
Accounts Models
===============
This file defines our custom User with roles.
Roles: admin, organizer, user, volunteer
"""
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """
    Our custom user model.
    We extend Django's built-in User to add a 'role' field.
    AbstractUser already gives us: username, email, password, first_name, last_name
    """
    
    # Define the possible roles a user can have
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('organizer', 'Organizer'),
        ('user', 'User'),
        ('volunteer', 'Volunteer'),
    ]
    
    # Role field - every user must have one role
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user',  # By default, new users are regular "user"
    )
    
    # Profile picture - optional
    profile_picture = models.ImageField(
        upload_to='profile_pics/',  # Saved in media/profile_pics/
        blank=True,
        null=True
    )
    
    # Phone number - optional
    phone = models.CharField(max_length=15, blank=True, null=True)
    
    # Bio for organizers
    bio = models.TextField(blank=True, null=True)
    
    # User's interests for AI recommendation feature
    interests = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Comma separated interests e.g. music,sports,tech"
    )
    
    # When the user was created
    created_at = models.DateTimeField(auto_now_add=True)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=64, blank=True, default='')
    
    def __str__(self):
        # This is what shows in Django admin for this user
        return f"{self.username} ({self.role})"
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_organizer(self):
        return self.role == 'organizer'
    
    def is_volunteer(self):
        return self.role == 'volunteer'
    
    def is_regular_user(self):
        return self.role == 'user'


class Notification(models.Model):
    """In-app notification center with typed icons."""
    TYPE_CHOICES = [
        ('booking_success', 'Booking Success'),
        ('payment_success', 'Payment Success'),
        ('payment_failed', 'Payment Failed'),
        ('event_reminder', 'Event Reminder'),
        ('event_cancelled', 'Event Cancelled'),
        ('waitlist_upgraded', 'Waitlist Upgraded'),
        ('poll_started', 'Poll Started'),
        ('poll_ended', 'Poll Ended'),
        ('refund', 'Refund'),
        ('general', 'General'),
    ]
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='user_notifications'
    )
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='general')
    link = models.CharField(max_length=300, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def icon_class(self):
        icons = {
            'booking_success': 'bi-ticket-perforated-fill',
            'payment_success': 'bi-credit-card-fill',
            'payment_failed': 'bi-x-circle-fill',
            'event_reminder': 'bi-calendar-event-fill',
            'event_cancelled': 'bi-calendar-x-fill',
            'waitlist_upgraded': 'bi-arrow-up-circle-fill',
            'poll_started': 'bi-bar-chart-fill',
            'poll_ended': 'bi-pie-chart-fill',
            'refund': 'bi-arrow-counterclockwise',
        }
        return icons.get(self.notification_type, 'bi-bell-fill')

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:50]}"


class Wishlist(models.Model):
    """User saved / wishlist events."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='wishlist_items')
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'event']
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} ♥ {self.event.title}"


class AuditLog(models.Model):
    """System audit trail for admin monitoring."""
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=120)
    details = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} @ {self.created_at}"


class LoginHistory(models.Model):
    """Track user login sessions."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500, blank=True, default='')
    logged_in_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_in_at']
        verbose_name_plural = 'Login histories'


class WindowSession(models.Model):
    """Maps a browser window/tab id (wsid) to an isolated Django session."""
    wsid = models.CharField(max_length=64, unique=True, db_index=True)
    session_key = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Window {self.wsid[:8]}…"
