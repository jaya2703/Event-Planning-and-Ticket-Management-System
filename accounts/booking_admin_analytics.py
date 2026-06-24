"""Analytics helpers for admin Booking Management page."""
import json
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, Avg
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from accounts.admin_analytics import pct_change
from accounts.models import CustomUser, AuditLog
from events.models import Event, Category
from bookings.models import Booking
from payments.models import Payment

SORT_MAP = {
    'date': '-booked_at',
    'date_asc': 'booked_at',
    'amount': '-total_price',
    'amount_asc': 'total_price',
    'qty': '-quantity',
    'qty_asc': 'quantity',
    'status': 'status',
}


def _month_bounds(offset=0):
    now = timezone.now()
    first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if offset == 0:
        return first, now
    end = first - timedelta(seconds=1)
    return end.replace(day=1, hour=0, minute=0, second=0, microsecond=0), end


def _payment_label(booking):
    if booking.is_refunded_booking:
        return 'refunded', 'Refunded'
    payment = getattr(booking, 'payment', None)
    if not payment:
        if booking.total_price <= 0 and booking.status in ('confirmed', 'attended'):
            return 'paid', 'Paid'
        return 'pending', 'Pending'
    if payment.status == 'success':
        return 'paid', 'Paid'
    if payment.status == 'failed':
        return 'failed', 'Failed'
    return 'pending', 'Pending'


def _ticket_status(booking):
    if booking.status == 'cancelled':
        return 'unavailable', 'Unavailable'
    if booking.status == 'confirmed' and booking.qr_code:
        return 'ready', 'Ready'
    if booking.status in ('pending_payment', 'waitlisted'):
        return 'pending', 'Pending'
    if booking.status == 'attended':
        return 'ready', 'Checked in'
    return 'unavailable', 'Unavailable'


def _build_activity_feed():
    items = []
    for b in Booking.objects.select_related('user', 'event').order_by('-booked_at')[:8]:
        items.append({
            'type': 'booking',
            'icon': 'bi-ticket-perforated',
            'tone': 'success',
            'text': f'{b.user.get_full_name() or b.user.username} booked {b.event.title}',
            'at': b.booked_at,
        })
    for b in Booking.objects.select_related('user', 'event').filter(
        status='cancelled'
    ).order_by('-booked_at')[:4]:
        items.append({
            'type': 'cancel',
            'icon': 'bi-x-circle',
            'tone': 'danger',
            'text': f'{b.user.get_full_name() or b.user.username} cancelled {b.event.title}',
            'at': b.booked_at,
        })
    for p in Payment.objects.filter(is_refunded=True).select_related(
        'booking__user', 'booking__event'
    ).order_by('-refunded_at')[:4]:
        if p.refunded_at:
            items.append({
                'type': 'refund',
                'icon': 'bi-arrow-counterclockwise',
                'tone': 'info',
                'text': f'Refund approved for {p.booking.event.title}',
                'at': p.refunded_at,
            })
    for log in AuditLog.objects.select_related('user').filter(
        Q(action__icontains='book') | Q(action__icontains='cancel') | Q(action__icontains='refund')
    ).order_by('-created_at')[:6]:
        items.append({
            'type': 'audit',
            'icon': 'bi-activity',
            'tone': 'muted',
            'text': log.details or log.action,
            'at': log.created_at,
        })
    items.sort(key=lambda x: x['at'], reverse=True)
    return items[:12]


def build_bookings_admin_context(request):
    search = request.GET.get('q', '').strip()
    event_filter = request.GET.get('event', '')
    status_filter = request.GET.get('status', '')
    payment_filter = request.GET.get('payment_status', '')
    organizer_filter = request.GET.get('organizer', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    sort = request.GET.get('sort', 'date')

    base_qs = Booking.objects.select_related(
        'user', 'event', 'event__organizer', 'event__category', 'payment'
    )
    filtered = base_qs

    if search:
        filtered = filtered.filter(
            Q(user__username__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__email__icontains=search)
            | Q(event__title__icontains=search)
            | Q(booking_id__icontains=search)
        )
    if event_filter:
        filtered = filtered.filter(event_id=event_filter)
    if status_filter:
        filtered = filtered.filter(status=status_filter)
    if organizer_filter:
        filtered = filtered.filter(event__organizer_id=organizer_filter)
    if date_from:
        filtered = filtered.filter(booked_at__date__gte=date_from)
    if date_to:
        filtered = filtered.filter(booked_at__date__lte=date_to)
    if payment_filter == 'paid':
        filtered = filtered.filter(payment__status='success', payment__is_refunded=False)
    elif payment_filter == 'pending':
        filtered = filtered.filter(
            Q(payment__status='pending') | Q(payment__isnull=True, status='pending_payment')
        )
    elif payment_filter == 'failed':
        filtered = filtered.filter(payment__status='failed')
    elif payment_filter == 'refunded':
        filtered = filtered.filter(payment__is_refunded=True)

    order = SORT_MAP.get(sort, '-booked_at')
    bookings_qs = filtered.order_by(order)

    paginator = Paginator(bookings_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    bookings_page = []
    for b in page_obj.object_list:
        pay_key, pay_label = _payment_label(b)
        tick_key, tick_label = _ticket_status(b)
        bookings_page.append({
            'obj': b,
            'payment_key': pay_key,
            'payment_label': pay_label,
            'ticket_key': tick_key,
            'ticket_label': tick_label,
            'display_id': f'BK-{b.booked_at.year}-{b.id:04d}',
        })

    total = Booking.objects.count()
    confirmed = Booking.objects.filter(status__in=['confirmed', 'attended']).count()
    cancelled = Booking.objects.filter(status='cancelled').count()
    revenue_total = Payment.objects.filter(
        status='success', is_refunded=False
    ).aggregate(t=Sum('amount'))['t'] or 0

    cur_start, cur_end = _month_bounds(0)
    prev_start, prev_end = _month_bounds(1)

    bookings_cur = Booking.objects.filter(booked_at__gte=cur_start, booked_at__lte=cur_end).count()
    bookings_prev = Booking.objects.filter(booked_at__gte=prev_start, booked_at__lte=prev_end).count()
    confirmed_cur = Booking.objects.filter(
        status__in=['confirmed', 'attended'], booked_at__gte=cur_start, booked_at__lte=cur_end
    ).count()
    confirmed_prev = Booking.objects.filter(
        status__in=['confirmed', 'attended'], booked_at__gte=prev_start, booked_at__lte=prev_end
    ).count()
    cancelled_cur = Booking.objects.filter(
        status='cancelled', booked_at__gte=cur_start, booked_at__lte=cur_end
    ).count()
    cancelled_prev = Booking.objects.filter(
        status='cancelled', booked_at__gte=prev_start, booked_at__lte=prev_end
    ).count()
    rev_cur = Payment.objects.filter(
        status='success', is_refunded=False, paid_at__gte=cur_start, paid_at__lte=cur_end
    ).aggregate(t=Sum('amount'))['t'] or 0
    rev_prev = Payment.objects.filter(
        status='success', is_refunded=False, paid_at__gte=prev_start, paid_at__lte=prev_end
    ).aggregate(t=Sum('amount'))['t'] or 0

    analytics = {
        'total': {
            'value': total,
            'growth': pct_change(bookings_cur, bookings_prev),
            'up': bookings_cur >= bookings_prev,
        },
        'confirmed': {
            'value': confirmed,
            'growth': pct_change(confirmed_cur, confirmed_prev),
            'up': confirmed_cur >= confirmed_prev,
        },
        'cancelled': {
            'value': cancelled,
            'growth': pct_change(cancelled_cur, cancelled_prev),
            'up': cancelled_cur >= cancelled_prev,
        },
        'revenue': {
            'value': revenue_total,
            'growth': pct_change(rev_cur, rev_prev),
            'up': rev_cur >= rev_prev,
        },
    }

    top_event = (
        Event.objects.annotate(bc=Count('bookings'))
        .order_by('-bc')
        .first()
    )
    top_revenue_event = (
        Event.objects.annotate(
            rev=Sum(
                'bookings__payment__amount',
                filter=Q(bookings__payment__status='success', bookings__payment__is_refunded=False),
            )
        )
        .order_by('-rev')
        .first()
    )
    top_user = (
        CustomUser.objects.annotate(bc=Count('bookings'))
        .filter(role='user')
        .order_by('-bc')
        .first()
    )
    cat_top = (
        Category.objects.annotate(bc=Count('event'))
        .order_by('-bc')
        .first()
    )
    avg_qty = Booking.objects.aggregate(a=Avg('quantity'))['a'] or 0

    insights = {
        'top_event': top_event,
        'top_revenue_event': top_revenue_event,
        'top_user': top_user,
        'top_category': cat_top.name if cat_top else '—',
        'avg_quantity': round(float(avg_qty), 1),
    }

    today = timezone.now().date()
    daily_start = today - timedelta(days=29)
    daily_qs = (
        Booking.objects.filter(booked_at__date__gte=daily_start)
        .annotate(day=TruncDate('booked_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    daily_labels = [r['day'].strftime('%d %b') for r in daily_qs if r['day']]
    daily_values = [r['count'] for r in daily_qs if r['day']]

    month_start = today - timedelta(days=180)
    rev_month_qs = (
        Payment.objects.filter(status='success', paid_at__date__gte=month_start)
        .annotate(month=TruncMonth('paid_at'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    rev_month_labels = [r['month'].strftime('%b') for r in rev_month_qs if r['month']]
    rev_month_values = [float(r['total'] or 0) for r in rev_month_qs if r['month']]

    status_dist = {
        'confirmed': Booking.objects.filter(status='confirmed').count(),
        'pending': Booking.objects.filter(status='pending_payment').count(),
        'cancelled': Booking.objects.filter(status='cancelled').count(),
        'attended': Booking.objects.filter(status='attended').count(),
        'waitlisted': Booking.objects.filter(status='waitlisted').count(),
    }

    event_rev = (
        Event.objects.annotate(
            rev=Sum(
                'bookings__payment__amount',
                filter=Q(bookings__payment__status='success', bookings__payment__is_refunded=False),
            )
        )
        .order_by('-rev')[:6]
    )
    event_rev_labels = [e.title[:20] for e in event_rev]
    event_rev_values = [float(e.rev or 0) for e in event_rev]

    events = Event.objects.order_by('title')
    organizers = CustomUser.objects.filter(role='organizer').order_by('username')

    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')

    return {
        'page_obj': page_obj,
        'bookings': bookings_page,
        'analytics': analytics,
        'insights': insights,
        'activity_feed': _build_activity_feed(),
        'search': search,
        'event_filter': event_filter,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'organizer_filter': organizer_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort,
        'events': events,
        'organizers': organizers,
        'query_string': query_params.urlencode(),
        'chart_daily_labels': json.dumps(daily_labels),
        'chart_daily_values': json.dumps(daily_values),
        'chart_rev_month_labels': json.dumps(rev_month_labels),
        'chart_rev_month_values': json.dumps(rev_month_values),
        'chart_status_labels': json.dumps(list(status_dist.keys())),
        'chart_status_values': json.dumps(list(status_dist.values())),
        'chart_event_rev_labels': json.dumps(event_rev_labels),
        'chart_event_rev_values': json.dumps(event_rev_values),
    }
