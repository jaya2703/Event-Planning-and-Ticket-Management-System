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
    """
    Stores notifications for users
    e.g. "Your ticket has been booked!", "Event cancelled"
    """
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,  # If user deleted, delete their notifications
        related_name='user_notifications'
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']  # Show newest first
    
    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:50]}"


class WindowSession(models.Model):
    """Maps a browser window/tab id (wsid) to an isolated Django session."""
    wsid = models.CharField(max_length=64, unique=True, db_index=True)
    session_key = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Window {self.wsid[:8]}…"
