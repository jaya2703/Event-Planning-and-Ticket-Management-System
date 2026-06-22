"""Custom admin panel views — no Django admin UI."""
import csv
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
    users = CustomUser.objects.all().order_by('-date_joined')
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
    events = Event.objects.select_related('organizer', 'category').order_by('-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        events = events.filter(status=status_filter)
    return render(request, 'admin/manage_events.html', {
        'events': events,
        'status_filter': status_filter,
    })


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
    return render(request, 'admin/manage_categories.html', {'categories': categories})


@login_required
@admin_required
def audit_logs(request):
    logs = AuditLog.objects.select_related('user').order_by('-created_at')[:200]
    logins = LoginHistory.objects.select_related('user').order_by('-logged_in_at')[:50]
    return render(request, 'admin/audit_logs.html', {'logs': logs, 'logins': logins})


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
        for u in CustomUser.objects.order_by('-date_joined'):
            writer.writerow([u.username, u.email, u.role, u.is_active, u.date_joined])
    else:
        messages.error(request, 'Unknown report type.')
        return redirect('accounts:admin_dashboard')
    return response
