"""
Accounts Views
==============
Views handle what happens when a user visits a URL.
Think of views as "functions that respond to web requests".
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .forms import RegisterForm, ProfileUpdateForm
from .models import CustomUser, Notification
from events.models import Event
from bookings.models import Booking


def register_view(request):
    """
    Registration page.
    GET request = show empty form
    POST request = process the submitted form
    """
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Log the user in immediately after registration
            messages.success(request, f"Welcome {user.first_name}! Your account has been created.")
            return redirect('accounts:dashboard')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = RegisterForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """Login page with role selection"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    role_error = None
    selected_role = request.POST.get('role', 'user') if request.method == 'POST' else 'user'

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                if user.role != selected_role and user.role != 'admin':
                    role_labels = {'user': 'Attendee', 'organizer': 'Organizer', 'admin': 'Admin'}
                    role_error = (
                        f"This account is registered as {role_labels.get(user.role, user.role)}. "
                        f"Please select the correct role to sign in."
                    )
                else:
                    login(request, user)
                    messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                    return redirect('accounts:dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {
        'form': form,
        'selected_role': selected_role,
        'role_error': role_error,
    })


def logout_view(request):
    """Log the user out and redirect to home"""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('home')


@login_required  # This decorator means: "User must be logged in to access this"
def dashboard_view(request):
    """
    Main dashboard - redirects user to the right dashboard based on their role.
    Admin -> admin dashboard
    Organizer -> organizer dashboard
    User/Volunteer -> user dashboard
    """
    user = request.user
    
    if user.role == 'admin':
        return redirect('accounts:admin_dashboard')
    elif user.role == 'organizer':
        return redirect('accounts:organizer_dashboard')
    else:
        return redirect('accounts:user_dashboard')


@login_required
def admin_dashboard_view(request):
    """Admin dashboard with full system analytics"""
    if request.user.role != 'admin':
        messages.error(request, "Access denied. Admin only.")
        return redirect('accounts:dashboard')
    
    from bookings.models import Booking
    from payments.models import Payment
    
    # Gather all statistics for the admin
    total_users = CustomUser.objects.count()
    total_events = Event.objects.count()
    total_bookings = Booking.objects.count()
    
    # Revenue = sum of all successful payments
    from django.db.models import Sum
    total_revenue = Payment.objects.filter(status='success').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Recent activity
    recent_users = CustomUser.objects.order_by('-date_joined')[:5]
    recent_bookings = Booking.objects.order_by('-booked_at')[:5]
    recent_events = Event.objects.order_by('-created_at')[:5]
    
    # Users by role for a pie chart
    organizer_count = CustomUser.objects.filter(role='organizer').count()
    volunteer_count = CustomUser.objects.filter(role='volunteer').count()
    user_count = CustomUser.objects.filter(role='user').count()
    
    # Events by status
    upcoming_events = Event.objects.filter(status='upcoming').count()
    ongoing_events = Event.objects.filter(status='ongoing').count()
    completed_events = Event.objects.filter(status='completed').count()
    
    context = {
        'total_users': total_users,
        'total_events': total_events,
        'total_bookings': total_bookings,
        'total_revenue': total_revenue,
        'recent_users': recent_users,
        'recent_bookings': recent_bookings,
        'recent_events': recent_events,
        'organizer_count': organizer_count,
        'volunteer_count': volunteer_count,
        'user_count': user_count,
        'upcoming_events': upcoming_events,
        'ongoing_events': ongoing_events,
        'completed_events': completed_events,
        'all_organizers': CustomUser.objects.filter(role='organizer'),
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def organizer_dashboard_view(request):
    """Organizer dashboard"""
    if request.user.role not in ['organizer', 'admin']:
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
    
    from bookings.models import Booking
    from payments.models import Payment
    from django.db.models import Sum, Count
    
    # Get events created by this organizer only
    my_events = Event.objects.filter(organizer=request.user)
    
    # Get bookings for this organizer's events
    my_bookings = Booking.objects.filter(event__organizer=request.user)
    
    # Revenue for this organizer
    my_revenue = Payment.objects.filter(
        booking__event__organizer=request.user,
        status='success'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Volunteers assigned to organizer's events
    from volunteers.models import VolunteerAssignment
    my_volunteers = VolunteerAssignment.objects.filter(event__organizer=request.user)
    
    context = {
        'my_events': my_events,
        'my_events_count': my_events.count(),
        'my_bookings_count': my_bookings.count(),
        'my_revenue': my_revenue,
        'recent_bookings': my_bookings.order_by('-booked_at')[:10],
        'my_volunteers': my_volunteers,
    }
    return render(request, 'dashboard/organizer_dashboard.html', context)


@login_required
def user_dashboard_view(request):
    """User dashboard - shows bookings, recommended events etc."""
    from bookings.models import Booking
    
    # Get all bookings for this user
    my_bookings = Booking.objects.filter(user=request.user).order_by('-booked_at')
    
    # Notifications for this user
    my_notifications = Notification.objects.filter(
        user=request.user, is_read=False
    )[:5]
    
    # AI Recommendation - simple logic based on interests and past bookings
    recommended_events = get_recommended_events(request.user)
    
    context = {
        'my_bookings': my_bookings,
        'my_bookings_count': my_bookings.count(),
        'notifications': my_notifications,
        'recommended_events': recommended_events,
        'upcoming_bookings': my_bookings.filter(event__status='upcoming')[:3],
    }
    return render(request, 'dashboard/user_dashboard.html', context)


def get_recommended_events(user):
    """
    Simple AI Recommendation Logic:
    1. Look at user's interests (stored as comma-separated text)
    2. Look at what categories they booked before
    3. Return events matching those categories
    
    This is a beginner-friendly approach - no machine learning needed!
    """
    from bookings.models import Booking
    
    # Find categories the user has booked before
    booked_categories = Booking.objects.filter(
        user=user
    ).values_list('event__category', flat=True)
    
    # Get user interests from their profile
    user_interests = []
    if user.interests:
        user_interests = [i.strip().lower() for i in user.interests.split(',')]
    
    # Find upcoming events the user hasn't booked yet
    already_booked_events = Booking.objects.filter(user=user).values_list('event_id', flat=True)
    
    # Recommend events from same categories they like
    recommended = Event.objects.filter(
        status='upcoming',
        category__in=list(booked_categories)
    ).exclude(id__in=already_booked_events)[:4]
    
    # If no matches found, just show latest upcoming events
    if not recommended:
        recommended = Event.objects.filter(
            status='upcoming'
        ).exclude(id__in=already_booked_events)[:4]
    
    return recommended


@login_required
def profile_view(request):
    """User profile page"""
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def change_password_view(request):
    """Change password page"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in after password change
            messages.success(request, "Password changed successfully!")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
    except Notification.DoesNotExist:
        pass
    return redirect('accounts:dashboard')
