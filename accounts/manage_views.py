"""Custom admin panel views — no Django admin UI."""
import csv
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone

from accounts.models import CustomUser, AuditLog, LoginHistory
from accounts.services import (
    monthly_revenue_data, monthly_user_growth, category_distribution, log_activity, get_client_ip,
)
from events.models import Event, Category
from bookings.models import Booking
from payments.models import Payment


def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'admin':
            messages.error(request, 'Admin access required.')
            return redirect('accounts:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@admin_required
def manage_users(request):
    users = CustomUser.platform_users().order_by('-date_joined')
    role_filter = request.GET.get('role', '')
    search = request.GET.get('q', '')
    if role_filter:
        users = users.filter(role=role_filter)
    if search:
        users = users.filter(
            Q(username__icontains=search) | Q(email__icontains=search) |
            Q(first_name__icontains=search) | Q(last_name__icontains=search)
        )
    return render(request, 'admin/manage_users.html', {
        'users': users,
        'role_filter': role_filter,
        'search': search,
    })


@login_required
@admin_required
def toggle_user_active(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if user == request.user:
        messages.error(request, 'Cannot deactivate your own account.')
    else:
        user.is_active = not user.is_active
        user.save()
        log_activity(request.user, 'toggle_user_active', f'{user.username} active={user.is_active}', get_client_ip(request))
        messages.success(request, f'User {user.username} updated.')
    return redirect('accounts:manage_users')


@login_required
@admin_required
def manage_events(request):
    from accounts.event_admin_analytics import build_events_admin_context
    return render(request, 'admin/manage_events.html', build_events_admin_context(request))


@login_required
@admin_required
def manage_bookings(request):
    from accounts.booking_admin_analytics import build_bookings_admin_context
    return render(request, 'admin/manage_bookings.html', build_bookings_admin_context(request))


@login_required
@admin_required
def manage_payments(request):
    payments = Payment.objects.select_related('booking__user', 'booking__event').order_by('-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        payments = payments.filter(status=status_filter)
    return render(request, 'admin/manage_payments.html', {
        'payments': payments,
        'status_filter': status_filter,
    })


@login_required
@admin_required
def manage_categories(request):
    categories = Category.objects.annotate(event_count=Count('event')).order_by('name')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        icon = request.POST.get('icon', 'bi-star').strip()
        if name:
            Category.objects.create(name=name, icon=icon)
            messages.success(request, f'Category "{name}" created.')
        return redirect('accounts:manage_categories')

    active_count = sum(1 for c in categories if c.event_count > 0)
    events_total = sum(c.event_count for c in categories)
    most_used = max(categories, key=lambda c: c.event_count, default=None) if categories else None
    if most_used is not None and most_used.event_count == 0:
        most_used = None

    return render(request, 'admin/manage_categories.html', {
        'categories': categories,
        'stats': {
            'total': categories.count(),
            'active': active_count,
            'events_total': events_total,
            'empty': categories.count() - active_count,
            'most_used': most_used,
        },
    })


@login_required
@admin_required
def admin_statistics(request):
    from accounts.admin_analytics import build_admin_statistics_context
    return render(request, 'admin/statistics.html', build_admin_statistics_context())


@login_required
@admin_required
def admin_reports(request):
    report_items = [
        {'title': 'Events Report', 'desc': 'All platform events with capacity, status, and organizer.', 'icon': 'bi-calendar-event', 'csv': 'events'},
        {'title': 'Bookings Report', 'desc': 'All bookings with status, amounts, and dates.', 'icon': 'bi-ticket-perforated', 'csv': 'bookings'},
        {'title': 'Payments Report', 'desc': 'Transaction history, methods, and payment status.', 'icon': 'bi-credit-card', 'csv': 'payments'},
        {'title': 'Users Report', 'desc': 'Registered users, roles, and account status.', 'icon': 'bi-people', 'csv': 'users'},
        {'title': 'Audit Trail', 'desc': 'System activity and admin actions log.', 'icon': 'bi-journal-text', 'csv': 'audit'},
        {'title': 'Login History', 'desc': 'Authentication sessions and IP addresses.', 'icon': 'bi-box-arrow-in-right', 'csv': 'logins'},
    ]
    return render(request, 'admin/reports.html', {'report_items': report_items})


@login_required
@admin_required
def audit_logs(request):
    from datetime import timedelta

    today = timezone.now().date()
    search = request.GET.get('q', '').strip()
    action_filter = request.GET.get('action', '').strip()
    active_tab = request.GET.get('tab', 'audit')

    logs = AuditLog.objects.select_related('user').order_by('-created_at')
    logins = LoginHistory.objects.select_related('user').order_by('-logged_in_at')

    if search:
        logs = logs.filter(
            Q(user__username__icontains=search)
            | Q(action__icontains=search)
            | Q(details__icontains=search)
            | Q(ip_address__icontains=search)
        )
        logins = logins.filter(
            Q(user__username__icontains=search) | Q(ip_address__icontains=search)
        )

    if action_filter:
        logs = logs.filter(action=action_filter)

    action_types = (
        AuditLog.objects.order_by('action')
        .values_list('action', flat=True)
        .distinct()
    )

    stats = {
        'total_audits': AuditLog.objects.count(),
        'total_logins': LoginHistory.objects.count(),
        'logins_today': LoginHistory.objects.filter(logged_in_at__date=today).count(),
        'active_users_week': LoginHistory.objects.filter(
            logged_in_at__gte=timezone.now() - timedelta(days=7)
        ).values('user').distinct().count(),
    }

    login_chart_labels = []
    login_chart_values = []
    audit_chart_values = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        login_chart_labels.append(day.strftime('%a'))
        login_chart_values.append(
            LoginHistory.objects.filter(logged_in_at__date=day).count()
        )
        audit_chart_values.append(
            AuditLog.objects.filter(created_at__date=day).count()
        )

    return render(request, 'admin/audit_logs.html', {
        'logs': logs[:200],
        'logins': logins[:100],
        'stats': stats,
        'search': search,
        'action_filter': action_filter,
        'action_types': action_types,
        'active_tab': active_tab,
        'login_chart_labels': json.dumps(login_chart_labels),
        'login_chart_values': json.dumps(login_chart_values),
        'audit_chart_values': json.dumps(audit_chart_values),
    })


@login_required
@admin_required
def export_report(request, report_type):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="eventpro_{report_type}_{timezone.now():%Y%m%d}.csv"'
    writer = csv.writer(response)
    if report_type == 'bookings':
        writer.writerow(['ID', 'User', 'Event', 'Qty', 'Amount', 'Status', 'Date'])
        for b in Booking.objects.select_related('user', 'event').order_by('-booked_at'):
            writer.writerow([b.booking_id, b.user.username, b.event.title, b.quantity, b.total_price, b.status, b.booked_at])
    elif report_type == 'payments':
        writer.writerow(['Payment ID', 'User', 'Event', 'Amount', 'Status', 'Method', 'Date'])
        for p in Payment.objects.select_related('booking__user', 'booking__event').order_by('-created_at'):
            writer.writerow([p.payment_id, p.booking.user.username, p.booking.event.title, p.amount, p.status, p.payment_method, p.created_at])
    elif report_type == 'users':
        writer.writerow(['Username', 'Email', 'Role', 'Active', 'Joined'])
        for u in CustomUser.platform_users().order_by('-date_joined'):
            writer.writerow([u.username, u.email, u.role, u.is_active, u.date_joined])
    elif report_type == 'audit':
        writer.writerow(['User', 'Action', 'Details', 'IP Address', 'Timestamp'])
        for log in AuditLog.objects.select_related('user').order_by('-created_at'):
            writer.writerow([
                log.user.username if log.user else 'System',
                log.action,
                log.details,
                log.ip_address or '',
                log.created_at,
            ])
    elif report_type == 'logins':
        writer.writerow(['User', 'IP Address', 'User Agent', 'Logged In At'])
        for entry in LoginHistory.objects.select_related('user').order_by('-logged_in_at'):
            writer.writerow([
                entry.user.username,
                entry.ip_address,
                entry.user_agent,
                entry.logged_in_at,
            ])
    elif report_type == 'events':
        writer.writerow(['Title', 'Organizer', 'Category', 'City', 'Date', 'Status', 'Capacity', 'Tickets Sold', 'Price'])
        for e in Event.objects.select_related('organizer', 'category').order_by('-created_at'):
            writer.writerow([
                e.title, e.organizer.username,
                e.category.name if e.category else '',
                e.city, e.date, e.status,
                e.total_capacity, e.tickets_booked, e.ticket_price,
            ])
    else:
        messages.error(request, 'Unknown report type.')
        return redirect('accounts:admin_dashboard')
    return response
