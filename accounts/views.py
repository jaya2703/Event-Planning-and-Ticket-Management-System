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
from django.http import JsonResponse

# ... in the imports ...
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
    """Organizer SaaS dashboard"""
    from bookings.views import cleanup_expired_reservations
    cleanup_expired_reservations()
    staff_roles = ['organizer', 'event_manager', 'finance', 'marketing', 'staff', 'volunteer', 'admin']
    if request.user.role not in staff_roles:
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
    
    from django.utils import timezone
    import json
    from bookings.models import Booking, Refund
    from payments.models import Payment
    from accounts.models import AuditLog
    
    org = request.user.organization
    is_admin = request.user.role == 'admin'
    if is_admin:
        my_events = Event.objects.all().select_related('category')
        my_bookings = Booking.objects.all().select_related('user', 'event')
        my_revenue = Payment.objects.filter(status='success').aggregate(total=Sum('amount'))['total'] or 0
        pending_refunds_count = Refund.objects.filter(status='pending').count()
        recent_activity = AuditLog.objects.all()[:5]
    else:
        my_events = Event.objects.filter(organizer=request.user).select_related('category')
        my_bookings = Booking.objects.filter(event__organizer=request.user).select_related('user', 'event')
        my_revenue = Payment.objects.filter(
            booking__event__organizer=request.user, status='success'
        ).aggregate(total=Sum('amount'))['total'] or 0
        pending_refunds_count = Refund.objects.filter(booking__event__organizer=request.user, status='pending').count()
        recent_activity = AuditLog.objects.filter(user=request.user)[:5]

    from volunteers.models import EventVolunteer
    if is_admin:
        vol_qs = EventVolunteer.objects.all()
    else:
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

    # SaaS stats
    registrations_today = my_bookings.filter(booked_at__date=timezone.now().date(), status__in=['confirmed', 'attended', 'pending_payment']).count()
    checkins_today = my_bookings.filter(is_checked_in=True, checked_in_at__date=timezone.now().date()).count()
    active_events_count = my_events.filter(status__in=['draft', 'published', 'upcoming', 'ongoing']).count()

    # Global Stats for Org
    total_capacity = sum(ev.total_capacity or 0 for ev in my_events)
    total_checked_in = 0
    for ev in my_events:
        total_checked_in += Booking.objects.filter(event=ev, is_checked_in=True).count()

    total_tickets_sold = my_bookings.filter(status__in=['confirmed', 'attended']).aggregate(t=Sum('quantity'))['t'] or 0
    remaining_capacity = total_capacity - total_tickets_sold
    attendance_rate = int((total_checked_in / total_capacity * 100)) if total_capacity > 0 else 0

    context = {
        'org': org,
        'my_events': my_events,
        'my_events_count': my_events.count(),
        'my_bookings_count': total_tickets_sold,
        'my_revenue': my_revenue,
        'recent_bookings': my_bookings.order_by('-booked_at')[:10],
        'my_volunteers': my_volunteers,
        'volunteer_stats': volunteer_stats,
        'event_analytics': event_analytics,
        'chart_booking_labels': json.dumps(booking_labels),
        'chart_booking_values': json.dumps(booking_values),
        'registrations_today': registrations_today,
        'checkins_today': checkins_today,
        'active_events_count': active_events_count,
        'pending_refunds_count': pending_refunds_count,
        'recent_activity': recent_activity,
        'total_capacity': total_capacity,
        'total_checked_in': total_checked_in,
        'remaining_capacity': remaining_capacity,
        'attendance_rate': attendance_rate,
    }
    return render(request, 'dashboard/organizer_dashboard.html', context)


@login_required
def user_dashboard_view(request):
    """User dashboard - shows bookings, recommended events etc."""
    from bookings.views import cleanup_expired_reservations
    cleanup_expired_reservations()
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
def organizer_stats_api(request):
    """API endpoint to return organizer dashboard statistics for auto-refresh."""
    from bookings.views import cleanup_expired_reservations
    cleanup_expired_reservations()
    staff_roles = ['organizer', 'event_manager', 'finance', 'marketing', 'staff', 'volunteer', 'admin']
    if request.user.role not in staff_roles:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    is_admin = request.user.role == 'admin'
    if is_admin:
        my_events = Event.objects.all()
        my_bookings = Booking.objects.all()
        my_revenue = Payment.objects.filter(status='success').aggregate(total=Sum('amount'))['total'] or 0
    else:
        my_events = Event.objects.filter(organizer=request.user)
        my_bookings = Booking.objects.filter(event__organizer=request.user)
        my_revenue = Payment.objects.filter(
            booking__event__organizer=request.user, status='success'
        ).aggregate(total=Sum('amount'))['total'] or 0

    total_capacity = sum(ev.total_capacity or 0 for ev in my_events)
    total_checked_in = 0
    for ev in my_events:
        total_checked_in += Booking.objects.filter(event=ev, is_checked_in=True).count()

    total_tickets_sold = my_bookings.filter(status__in=['confirmed', 'attended']).aggregate(t=Sum('quantity'))['t'] or 0
    remaining_capacity = total_capacity - total_tickets_sold
    attendance_rate = int((total_checked_in / total_capacity * 100)) if total_capacity > 0 else 0

    return JsonResponse({
        'my_events_count': my_events.count(),
        'my_bookings_count': total_tickets_sold,
        'my_revenue': float(my_revenue),
        'total_checked_in': total_checked_in,
        'remaining_capacity': remaining_capacity,
        'attendance_rate': attendance_rate,
        'registrations_today': my_bookings.filter(booked_at__date=timezone.now().date(), status__in=['confirmed', 'attended', 'pending_payment']).count(),
        'checkins_today': my_bookings.filter(is_checked_in=True, checked_in_at__date=timezone.now().date()).count(),
    })


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


from django.utils.text import slugify
from .models import Organization, ApiKey

@login_required
def workspace_settings(request):
    """Workspace branding settings (SaaS customization)."""
    if request.user.role not in ['organizer', 'admin']:
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
        
    org = request.user.organization
    if not org:
        org, _ = Organization.objects.get_or_create(
            owner=request.user,
            defaults={'name': f"{request.user.username}'s Workspace", 'slug': slugify(request.user.username)}
        )
        request.user.organization = org
        request.user.save()
        
    if request.method == 'POST':
        name = request.POST.get('name', org.name).strip()
        branding_color = request.POST.get('branding_color', org.branding_color).strip()
        custom_domain = request.POST.get('custom_domain', '').strip()
        logo = request.FILES.get('logo')
        
        from .services import check_subscription_limits
        if custom_domain and not check_subscription_limits(org, 'custom_domain'):
            messages.error(request, "Custom domains are only available on the Enterprise tier.")
            custom_domain = None
            
        if branding_color and not check_subscription_limits(org, 'custom_branding'):
            messages.error(request, "Custom branding colors are only available on the Pro/Enterprise tiers.")
            branding_color = '#6c5ce7'
            
        org.name = name
        org.branding_color = branding_color
        if custom_domain:
            org.custom_domain = custom_domain
        if logo:
            org.logo = logo
        org.save()
        messages.success(request, "Workspace settings updated!")
        return redirect('accounts:workspace_settings')
        
    return render(request, 'accounts/workspace_settings.html', {'org': org})


@login_required
def list_members(request):
    """List team members of the Organization workspace."""
    if request.user.role not in ['organizer', 'admin', 'event_manager']:
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
        
    org = request.user.organization
    members = CustomUser.objects.filter(organization=org) if org else []
    return render(request, 'accounts/members.html', {'members': members, 'org': org})


@login_required
def invite_member(request):
    """Invite a new team member with specific SaaS role."""
    if request.user.role not in ['organizer', 'admin']:
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
        
    org = request.user.organization
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', 'staff')
        
        if not username or not email:
            messages.error(request, "Username and Email are required.")
        else:
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    'username': username,
                    'role': role,
                    'organization': org
                }
            )
            if created:
                user.set_password('welcome123')
                user.save()
                messages.success(request, f"Invited {username} to workspace as {user.get_role_display()}!")
            else:
                user.organization = org
                user.role = role
                user.save()
                messages.success(request, f"Updated {username}'s role to {user.get_role_display()} in workspace.")
                
    return redirect('accounts:list_members')


@login_required
def generate_api_key(request):
    """Generate integration API keys."""
    if request.user.role not in ['organizer', 'admin']:
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
        
    org = request.user.organization
    if request.method == 'POST':
        import uuid
        key_name = request.POST.get('name', 'Default Key').strip()
        key_str = f"ep_live_{uuid.uuid4().hex}"
        ApiKey.objects.create(organization=org, name=key_name, key=key_str)
        messages.success(request, f"API key generated: {key_str}")
        
    keys = ApiKey.objects.filter(organization=org) if org else []
    return render(request, 'accounts/api_keys.html', {'keys': keys})


@login_required
def campaign_manager(request):
    """Send and track scheduled email and notification campaigns."""
    if request.user.role not in ['organizer', 'admin', 'marketing']:
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
        
    org = request.user.organization
    events = Event.objects.filter(organization=org) if org else []
    
    if request.method == 'POST':
        event_id = request.POST.get('event_id')
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        method = request.POST.get('method', 'email')
        
        event = get_object_or_404(Event, id=event_id)
        bookings = event.bookings.filter(status='confirmed').select_related('user')
        
        count = 0
        for b in bookings:
            if method == 'email':
                print(f"[CAMPAIGN EMAIL] Sent to {b.user.email} | Subject: {subject} | Body: {body[:50]}...")
            elif method == 'push':
                notify(b.user, f"📢 {subject}: {body[:80]}...", 'general')
            count += 1
            
        messages.success(request, f"Campaign '{subject}' sent successfully to {count} attendees via {method}!")
        
    return render(request, 'accounts/campaigns.html', {'events': events})


@login_required
def subscription_plans(request):
    """Manage SaaS Workspace subscription tiers."""
    if request.user.role not in ['organizer', 'admin']:
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')
        
    org = request.user.organization
    if request.method == 'POST':
        tier = request.POST.get('tier', 'free')
        if tier in ['free', 'pro', 'enterprise']:
            org.subscription_tier = tier
            org.subscription_status = 'active'
            org.save()
            messages.success(request, f"Workspace plan upgraded to {tier.upper()} successfully!")
            
    return render(request, 'accounts/subscriptions.html', {'org': org})

