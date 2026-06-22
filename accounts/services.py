"""Enterprise services — notifications, audit, analytics helpers."""
from django.utils import timezone
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth


NOTIFICATION_TYPES = {
    'booking_success': {'icon': 'bi-ticket-perforated-fill', 'color': 'success'},
    'payment_success': {'icon': 'bi-credit-card-fill', 'color': 'success'},
    'payment_failed': {'icon': 'bi-x-circle-fill', 'color': 'danger'},
    'event_reminder': {'icon': 'bi-calendar-event-fill', 'color': 'info'},
    'event_cancelled': {'icon': 'bi-calendar-x-fill', 'color': 'danger'},
    'waitlist_upgraded': {'icon': 'bi-arrow-up-circle-fill', 'color': 'warning'},
    'poll_started': {'icon': 'bi-bar-chart-fill', 'color': 'primary'},
    'poll_ended': {'icon': 'bi-pie-chart-fill', 'color': 'secondary'},
    'refund': {'icon': 'bi-arrow-counterclockwise', 'color': 'warning'},
    'general': {'icon': 'bi-bell-fill', 'color': 'primary'},
}


def notify(user, message, notification_type='general', link=''):
    from accounts.models import Notification
    return Notification.objects.create(
        user=user,
        message=message,
        notification_type=notification_type,
        link=link,
    )


def log_activity(user, action, details='', ip_address=None):
    from accounts.models import AuditLog
    return AuditLog.objects.create(
        user=user,
        action=action,
        details=details,
        ip_address=ip_address,
    )


def log_login(user, ip_address='', user_agent=''):
    from accounts.models import LoginHistory
    return LoginHistory.objects.create(
        user=user,
        ip_address=ip_address or '0.0.0.0',
        user_agent=user_agent[:500] if user_agent else '',
    )


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def monthly_revenue_data(months=6):
    from payments.models import Payment
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now() - timedelta(days=months * 31)
    qs = (
        Payment.objects.filter(status='success', paid_at__gte=start)
        .annotate(month=TruncMonth('paid_at'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    labels, values = [], []
    for row in qs:
        if row['month']:
            labels.append(row['month'].strftime('%b %Y'))
            values.append(float(row['total'] or 0))
    return labels, values


def monthly_user_growth(months=6):
    from accounts.models import CustomUser
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now() - timedelta(days=months * 31)
    qs = (
        CustomUser.objects.filter(date_joined__gte=start)
        .annotate(month=TruncMonth('date_joined'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    labels, values = [], []
    for row in qs:
        if row['month']:
            labels.append(row['month'].strftime('%b %Y'))
            values.append(row['count'])
    return labels, values


def category_distribution():
    from events.models import Event
    qs = (
        Event.objects.filter(category__isnull=False)
        .values('category__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
    )
    return [r['category__name'] for r in qs], [r['count'] for r in qs]
