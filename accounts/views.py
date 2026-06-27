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
from .forms import RegisterForm, ProfileUpdateForm, AdminAccountForm
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
                if user.role == 'volunteer':
                    role_error = (
                        'Volunteer is no longer a platform login role. '
                        'Event staff are managed by organizers — use Attendee or Organizer to sign in.'
                    )
                elif user.role != selected_role:
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
    User -> user dashboard
    """
    user = request.user
    
    if user.role == 'admin':
        return redirect('accounts:admin_dashboard')
    elif user.role == 'organizer':
        return redirect('accounts:organizer_dashboard')
    elif user.role == 'volunteer':
        messages.error(request, 'Volunteer platform accounts are no longer supported. Contact your event organizer.')
        logout(request)
        return redirect('accounts:login')
    else:
        return redirect('accounts:user_dashboard')


@login_required
def admin_dashboard_view(request):
    """Admin dashboard with full system analytics"""
    if request.user.role != 'admin':
        messages.error(request, "Access denied. Admin only.")
        return redirect('accounts:dashboard')

    from .admin_analytics import build_admin_dashboard_context
    context = build_admin_dashboard_context()
    context['admin_user'] = request.user
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

    from volunteers.models import EventVolunteer
    vol_qs = EventVolunteer.objects.filter(event__organizer=request.user)
    volunteer_stats = {
        'total': vol_qs.count(),
        'assigned': vol_qs.filter(status='assigned').count(),
        'active_today': vol_qs.filter(is_present=True).count(),
        'pending': vol_qs.filter(status='pending').count(),
    }
    my_volunteers = vol_qs.select_related('event').order_by('-assigned_at')[:8]

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
        'volunteer_stats': volunteer_stats,
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
    from payments.models import Payment
    from accounts.models import AuditLog

    my_bookings = Booking.objects.filter(user=request.user).order_by('-booked_at')
    recommended_events = get_recommended_events(request.user)
    wishlist_ids = set(Wishlist.objects.filter(user=request.user).values_list('event_id', flat=True))

    # 1. Greeting
    hour = timezone.localtime().hour
    if hour < 12:
        greeting = 'Good Morning'
    elif hour < 17:
        greeting = 'Good Afternoon'
    else:
        greeting = 'Good Evening'

    # 2. Profile completion calculation
    profile_completion = 25
    u = request.user
    if u.first_name or u.last_name:
        profile_completion += 25
    if u.phone:
        profile_completion += 15
    if u.profile_picture:
        profile_completion += 15
    if u.bio:
        profile_completion += 10
    if u.interests:
        profile_completion += 10

    # 3. Gamification and Finance Metrics
    reward_points = my_bookings.filter(status='confirmed').count() * 100
    money_spent = Payment.objects.filter(booking__user=request.user, status='success').aggregate(t=Sum('amount'))['t'] or 0
    attended_count = my_bookings.filter(status='attended').count()
    
    # 4. Favorite Category
    fav_category_row = my_bookings.filter(
        status__in=['confirmed', 'attended'], event__category__isnull=False
    ).values('event__category__name').annotate(count=Count('id')).order_by('-count').first()
    fav_category = fav_category_row['event__category__name'] if fav_category_row else '—'

    # 5. Timeline Activities & Recent Notifications
    recent_activities = AuditLog.objects.filter(user=request.user).order_by('-created_at')[:4]
    recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:3]

    context = {
        'my_bookings': my_bookings,
        'my_bookings_count': my_bookings.count(),
        'recommended_events': recommended_events,
        'upcoming_bookings': my_bookings.filter(status='confirmed', event__date__gte=timezone.localtime().date()).order_by('event__date')[:3],
        'wishlist_count': len(wishlist_ids),
        'wishlist_ids': wishlist_ids,
        'greeting': greeting,
        'profile_completion': profile_completion,
        'reward_points': reward_points,
        'money_spent': money_spent,
        'attended_count': attended_count,
        'fav_category': fav_category,
        'recent_activities': recent_activities,
        'recent_notifications': recent_notifications,
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
    sort_option = request.GET.get('sort', 'date_nearest')
    items = Wishlist.objects.filter(user=request.user).select_related('event', 'event__category')
    
    from django.utils import timezone
    from django.db.models import Case, When, Value, BooleanField
    
    today = timezone.now().date()
    
    # Annotate past events so they can be positioned at the bottom
    items = items.annotate(
        is_past=Case(
            When(event__date__lt=today, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    )
    
    # Order by is_past first (upcoming/current first, past last), then the selected sort option
    if sort_option == 'date_nearest':
        items = items.order_by('is_past', 'event__date', 'event__time')
    elif sort_option == 'date_latest':
        items = items.order_by('is_past', '-event__date', '-event__time')
    elif sort_option == 'name_az':
        items = items.order_by('is_past', 'event__title')
    elif sort_option == 'name_za':
        items = items.order_by('is_past', '-event__title')
    elif sort_option == 'price_low':
        items = items.order_by('is_past', 'event__ticket_price')
    elif sort_option == 'price_high':
        items = items.order_by('is_past', '-event__ticket_price')
    else:
        items = items.order_by('is_past', 'event__date', 'event__time')
        sort_option = 'date_nearest'

    return render(request, 'accounts/wishlist.html', {
        'items': items,
        'sort_option': sort_option,
    })


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
    if request.user.role == 'admin':
        from .models import LoginHistory
        last_login = (
            LoginHistory.objects.filter(user=request.user)
            .order_by('-logged_in_at')
            .first()
        )
        if request.method == 'POST':
            form = AdminAccountForm(request.POST, instance=request.user)
            if form.is_valid():
                user = form.save()
                if form.cleaned_data.get('new_password'):
                    update_session_auth_hash(request, user)
                messages.success(request, 'Account settings updated successfully.')
                return redirect('accounts:profile')
        else:
            form = AdminAccountForm(instance=request.user)
        return render(request, 'accounts/profile_admin.html', {
            'form': form,
            'last_login': last_login,
        })

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
    if request.user.role == 'admin':
        return redirect('accounts:profile')

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
