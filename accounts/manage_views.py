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
    
    # Pre-calculate counts for SaaS KPI row
    kpi_total = users.count()
    kpi_active = users.filter(is_active=True).count()
    kpi_organizers = users.filter(role='organizer').count()
    kpi_admins = users.filter(role='admin').count()

    role_filter = request.GET.get('role', '')
    search = request.GET.get('q', '')
    if role_filter:
        users = users.filter(role=role_filter)
    if search:
        users = users.filter(
            Q(username__icontains=search) | Q(email__icontains=search) |
            Q(first_name__icontains=search) | Q(last_name__icontains=search) |
            Q(phone__icontains=search) | Q(role__icontains=search)
        )
    return render(request, 'admin/manage_users.html', {
        'users': users,
        'role_filter': role_filter,
        'search': search,
        'kpis': {
            'total': kpi_total,
            'active': kpi_active,
            'organizers': kpi_organizers,
            'admins': kpi_admins,
        }
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
    
    # 1. Top KPI calculations
    total_rev = payments.filter(status='success', is_refunded=False).aggregate(t=Sum('amount'))['t'] or 0
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_rev = payments.filter(status='success', is_refunded=False, paid_at__gte=today_start).aggregate(t=Sum('amount'))['t'] or 0
    success_count = payments.filter(status='success').count()
    pending_count = payments.filter(status='pending').count()
    failed_count = payments.filter(status='failed').count()
    refund_amount = payments.filter(is_refunded=True).aggregate(t=Sum('amount'))['t'] or 0
    refund_count = payments.filter(is_refunded=True).count()
    
    pay_count = payments.filter(status='success', is_refunded=False).count()
    aov = float(total_rev) / pay_count if pay_count > 0 else 0
    total_transactions = payments.count()
    
    # 2. Chart data
    # Revenue Trend (Line Chart - Last 12 months)
    from accounts.services import monthly_revenue_data
    rev_trend_labels, rev_trend_values = monthly_revenue_data(12)
    
    # Payment Methods Distribution (Donut)
    method_data = list(payments.filter(status='success', is_refunded=False).values('payment_method').annotate(count=Count('id')).order_by('-count'))
    method_labels = [m['payment_method'].title() for m in method_data]
    method_values = [m['count'] for m in method_data]
    
    # Revenue by Category (Horizontal Bar)
    cat_data = Category.objects.annotate(
        rev=Sum(
            'event__bookings__payment__amount',
            filter=Q(event__bookings__payment__status='success', event__bookings__payment__is_refunded=False)
        )
    ).filter(rev__gt=0).order_by('-rev')
    cat_labels = [c.name for c in cat_data]
    cat_values = [float(c.rev or 0) for c in cat_data]
    
    # Revenue by Event (Horizontal Bar - Top 5 Events)
    event_data = Event.objects.annotate(
        rev=Sum(
            'bookings__payment__amount',
            filter=Q(bookings__payment__status='success', bookings__payment__is_refunded=False)
        )
    ).filter(rev__gt=0).order_by('-rev')[:5]
    event_labels = [e.title[:20] for e in event_data]
    event_values = [float(e.rev or 0) for e in event_data]
    
    # Payment Status Distribution (Donut/Bar)
    status_labels = ['Success', 'Pending', 'Failed', 'Refunded']
    status_values = [
        payments.filter(status='success', is_refunded=False).count(),
        payments.filter(status='pending').count(),
        payments.filter(status='failed').count(),
        payments.filter(is_refunded=True).count()
    ]
    
    # Top Revenue Events Table Data
    top_events = Event.objects.annotate(
        rev=Sum(
            'bookings__payment__amount',
            filter=Q(bookings__payment__status='success', bookings__payment__is_refunded=False),
        ),
        bookings_count=Count('bookings', filter=Q(bookings__status__in=['confirmed', 'attended']))
    ).filter(rev__gt=0).order_by('-rev')[:5]
    
    # Highest Revenue Event Card Data
    highest_revenue_event = Event.objects.annotate(
        rev=Sum(
            'bookings__payment__amount',
            filter=Q(bookings__payment__status='success', bookings__payment__is_refunded=False)
        )
    ).filter(rev__gt=0).order_by('-rev').first()
    
    # Recent Transactions Timeline (Latest 6)
    recent_transactions = payments[:6]
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        payments = payments.filter(status=status_filter)
        
    return render(request, 'admin/manage_payments.html', {
        'payments': payments,
        'status_filter': status_filter,
        'kpis': {
            'total_revenue': total_rev,
            'today_revenue': today_rev,
            'successful_payments': success_count,
            'pending_payments': pending_count,
            'failed_payments': failed_count,
            'refunds': refund_amount,
            'refund_count': refund_count,
            'aov': aov,
            'total_transactions': total_transactions,
        },
        'chart_trend_labels': json.dumps(rev_trend_labels),
        'chart_trend_values': json.dumps(rev_trend_values),
        'chart_method_labels': json.dumps(method_labels),
        'chart_method_values': json.dumps(method_values),
        'chart_cat_labels': json.dumps(cat_labels),
        'chart_cat_values': json.dumps(cat_values),
        'chart_event_labels': json.dumps(event_labels),
        'chart_event_values': json.dumps(event_values),
        'chart_status_labels': json.dumps(status_labels),
        'chart_status_values': json.dumps(status_values),
        'top_events': top_events,
        'highest_revenue_event': highest_revenue_event,
        'recent_transactions': recent_transactions,
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
        'logs_today': AuditLog.objects.filter(created_at__date=today).count(),
        'failed_actions': AuditLog.objects.filter(
            Q(action__icontains='fail') | Q(details__icontains='fail') | Q(action__icontains='deny') | Q(action__icontains='block')
        ).count(),
        'unique_users': AuditLog.objects.exclude(user=None).values('user').distinct().count(),
    }

    # Sidebar metrics
    most_active_user = CustomUser.objects.annotate(act_count=Count('auditlog')).order_by('-act_count').first()
    recent_errors = AuditLog.objects.filter(Q(action__icontains='fail') | Q(details__icontains='fail')).order_by('-created_at')[:3]
    top_ip_row = AuditLog.objects.values('ip_address').annotate(ip_count=Count('ip_address')).order_by('-ip_count').first()
    top_ip = top_ip_row['ip_address'] if (top_ip_row and top_ip_row['ip_address']) else '—'

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
        'most_active_user': most_active_user,
        'recent_errors': recent_errors,
        'top_ip': top_ip,
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
