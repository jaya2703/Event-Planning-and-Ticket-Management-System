"""
Accounts Views
==============
Views handle what happens when a user visits a URL.
Think of views as "functions that respond to web requests".
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.db.models import Sum, Count, Q
import json
from .forms import RegisterForm, ProfileUpdateForm
from .models import CustomUser, Notification, Wishlist
from .services import (
    monthly_revenue_data, monthly_user_growth, category_distribution,
    log_activity, log_login, get_client_ip, notify,
)
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
                if user.role != selected_role:
                    role_labels = {'user': 'Attendee', 'organizer': 'Organizer', 'admin': 'Admin'}
                    role_error = (
                        f"This account is registered as {role_labels.get(user.role, user.role)}. "
                        f"Please select the correct role to sign in."
                    )
                else:
                    login(request, user)
                    log_login(user, get_client_ip(request), request.META.get('HTTP_USER_AGENT', ''))
                    log_activity(user, 'login', f'Role: {user.role}', get_client_ip(request))
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


def switch_account_view(request):
    """Log out and go to login so another user can sign in."""
    logout(request)
    messages.info(request, "Signed out. You can now log in with a different account.")
    return redirect('accounts:login')


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

    total_users = CustomUser.objects.count()
    total_organizers = CustomUser.objects.filter(role='organizer').count()
    total_events = Event.objects.count()
    total_bookings = Booking.objects.count()
    active_events = Event.objects.filter(status__in=['upcoming', 'ongoing']).count()
    cancelled_events = Event.objects.filter(status='cancelled').count()
    completed_events = Event.objects.filter(status='completed').count()
    tickets_sold = Booking.objects.filter(status__in=['confirmed', 'attended']).aggregate(
        t=Sum('quantity'))['t'] or 0

    total_revenue = Payment.objects.filter(status='success').aggregate(total=Sum('amount'))['total'] or 0
    pending_payments = Payment.objects.filter(status='pending').count()

    rev_labels, rev_values = monthly_revenue_data()
    user_labels, user_values = monthly_user_growth()
    cat_labels, cat_values = category_distribution()

    recent_users = CustomUser.objects.order_by('-date_joined')[:8]
    recent_bookings = Booking.objects.select_related('user', 'event').order_by('-booked_at')[:8]
    recent_events = Event.objects.select_related('organizer').order_by('-created_at')[:8]

    organizer_count = CustomUser.objects.filter(role='organizer').count()
    volunteer_count = CustomUser.objects.filter(role='volunteer').count()
    user_count = CustomUser.objects.filter(role='user').count()
    upcoming_events = Event.objects.filter(status='upcoming').count()
    ongoing_events = Event.objects.filter(status='ongoing').count()

    context = {
        'total_users': total_users,
        'total_organizers': total_organizers,
        'total_events': total_events,
        'total_bookings': total_bookings,
        'active_events': active_events,
        'cancelled_events': cancelled_events,
        'completed_events': completed_events,
        'tickets_sold': tickets_sold,
        'total_revenue': total_revenue,
        'pending_payments': pending_payments,
        'recent_users': recent_users,
        'recent_bookings': recent_bookings,
        'recent_events': recent_events,
        'organizer_count': organizer_count,
        'volunteer_count': volunteer_count,
        'user_count': user_count,
        'upcoming_events': upcoming_events,
        'ongoing_events': ongoing_events,
        'completed_events_count': completed_events,
        'chart_revenue_labels': json.dumps(rev_labels),
        'chart_revenue_values': json.dumps(rev_values),
        'chart_user_labels': json.dumps(user_labels),
        'chart_user_values': json.dumps(user_values),
        'chart_cat_labels': json.dumps(cat_labels),
        'chart_cat_values': json.dumps(cat_values),
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def organizer_dashboard_view(request):
    """Organizer dashboard"""
    if request.user.role not in ['organizer', 'admin']:
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
    
    from django.utils import timezone
    import json
    from bookings.models import Booking
    from payments.models import Payment
    my_events = Event.objects.filter(organizer=request.user).select_related('category')
    my_bookings = Booking.objects.filter(event__organizer=request.user).select_related('user', 'event')
    my_revenue = Payment.objects.filter(
        booking__event__organizer=request.user, status='success'
    ).aggregate(total=Sum('amount'))['total'] or 0

    from volunteers.models import VolunteerAssignment
    my_volunteers = VolunteerAssignment.objects.filter(
        event__organizer=request.user
    ).select_related('volunteer', 'event')

    event_analytics = []
    for ev in my_events[:6]:
        checked_in = Booking.objects.filter(event=ev, is_checked_in=True).count()
        capacity = ev.total_capacity or 1
        occupancy = int((checked_in / capacity) * 100)
        event_analytics.append({
            'event': ev,
            'checked_in': checked_in,
            'occupancy': occupancy,
            'density': ev.crowd_density,
            'revenue': Payment.objects.filter(
                booking__event=ev, status='success'
            ).aggregate(t=Sum('amount'))['t'] or 0,
        })

    booking_labels = []
    booking_values = []
    for i in range(5, -1, -1):
        from datetime import timedelta
        day = timezone.now().date() - timedelta(days=i * 7)
        booking_labels.append(day.strftime('%d %b'))
        booking_values.append(my_bookings.filter(booked_at__date__gte=day, booked_at__date__lt=day + timedelta(days=7)).count())

    context = {
        'my_events': my_events,
        'my_events_count': my_events.count(),
        'my_bookings_count': my_bookings.filter(status__in=['confirmed', 'attended']).aggregate(t=Sum('quantity'))['t'] or 0,
        'my_revenue': my_revenue,
        'recent_bookings': my_bookings.order_by('-booked_at')[:10],
        'my_volunteers': my_volunteers,
        'event_analytics': event_analytics,
        'chart_booking_labels': json.dumps(booking_labels),
        'chart_booking_values': json.dumps(booking_values),
    }
    return render(request, 'dashboard/organizer_dashboard.html', context)


@login_required
def user_dashboard_view(request):
    """User dashboard - shows bookings, recommended events etc."""
    from bookings.models import Booking
    from django.utils import timezone

    my_bookings = Booking.objects.filter(user=request.user).order_by('-booked_at')
    recommended_events = get_recommended_events(request.user)
    wishlist_ids = set(Wishlist.objects.filter(user=request.user).values_list('event_id', flat=True))

    context = {
        'my_bookings': my_bookings,
        'my_bookings_count': my_bookings.count(),
        'recommended_events': recommended_events,
        'upcoming_bookings': my_bookings.filter(status='confirmed', event__status='upcoming')[:3],
        'wishlist_count': len(wishlist_ids),
        'wishlist_ids': wishlist_ids,
    }
    return render(request, 'dashboard/user_dashboard.html', context)


@login_required
def toggle_wishlist(request, event_id):
    from events.models import Event
    event = get_object_or_404(Event, id=event_id)
    item, created = Wishlist.objects.get_or_create(user=request.user, event=event)
    if not created:
        item.delete()
        messages.info(request, f'Removed "{event.title}" from wishlist.')
    else:
        messages.success(request, f'Added "{event.title}" to wishlist.')
    return redirect(request.META.get('HTTP_REFERER', 'accounts:wishlist'))


@login_required
def wishlist_view(request):
    items = Wishlist.objects.filter(user=request.user).select_related('event', 'event__category')
    return render(request, 'accounts/wishlist.html', {'items': items})


def get_recommended_events(user):
    """AI Smart Recommendation — interests, booking history, trending."""
    from bookings.models import Booking
    from django.db.models import Q

    already_booked = list(Booking.objects.filter(user=user).values_list('event_id', flat=True))
    booked_categories = list(Booking.objects.filter(user=user).exclude(
        event__category__isnull=True
    ).values_list('event__category_id', flat=True).distinct())

    interest_q = Q()
    if user.interests:
        for interest in [i.strip() for i in user.interests.split(',') if i.strip()]:
            interest_q |= Q(category__name__icontains=interest) | Q(title__icontains=interest) | Q(description__icontains=interest)

    recommended = Event.objects.filter(status='upcoming').exclude(id__in=already_booked)
    if booked_categories or interest_q:
        recommended = recommended.filter(Q(category_id__in=booked_categories) | interest_q).distinct()
    recommended = list(recommended[:4])

    if len(recommended) < 4:
        trending = Event.objects.filter(status='upcoming').exclude(
            id__in=already_booked + [e.id for e in recommended]
        ).annotate(booking_count=Count('bookings')).order_by('-booking_count')[:4 - len(recommended)]
        recommended.extend(trending)

    return recommended[:4]


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
