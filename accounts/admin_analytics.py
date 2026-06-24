"""Admin dashboard & statistics analytics helpers."""
import json
from datetime import timedelta
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.models import CustomUser, LoginHistory, PLATFORM_ROLES
from accounts.services import monthly_revenue_data, monthly_user_growth, category_distribution
from events.models import Event, Category
from bookings.models import Booking, Waitlist
from payments.models import Payment


def get_greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return 'Good Morning'
    if hour < 17:
        return 'Good Afternoon'
    return 'Good Evening'


def pct_change(current, previous):
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def _month_bounds(offset=0):
    """offset 0 = current month, 1 = previous month."""
    now = timezone.now()
    first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if offset == 0:
        start = first_this
        end = now
    else:
        end = first_this - timedelta(seconds=1)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, end


def _sum_revenue(start, end):
    return Payment.objects.filter(
        status='success', paid_at__gte=start, paid_at__lte=end
    ).aggregate(t=Sum('amount'))['t'] or 0


def _count_bookings(start, end):
    return Booking.objects.filter(booked_at__gte=start, booked_at__lte=end).count()


def _count_users_joined(start, end):
    return CustomUser.objects.filter(date_joined__gte=start, date_joined__lte=end).count()


def _active_events_at(end):
    return Event.objects.filter(
        status__in=['upcoming', 'ongoing'], created_at__lte=end
    ).count()


def get_kpi_metrics():
    cur_start, cur_end = _month_bounds(0)
    prev_start, prev_end = _month_bounds(1)

    revenue_cur = _sum_revenue(cur_start, cur_end)
    revenue_prev = _sum_revenue(prev_start, prev_end)
    bookings_cur = _count_bookings(cur_start, cur_end)
    bookings_prev = _count_bookings(prev_start, prev_end)
    users_cur = CustomUser.objects.filter(role__in=PLATFORM_ROLES).count()
    users_prev = CustomUser.objects.filter(role__in=PLATFORM_ROLES, date_joined__lte=prev_end).count()
    events_cur = Event.objects.filter(status__in=['upcoming', 'ongoing']).count()
    events_prev = Event.objects.filter(
        status__in=['upcoming', 'ongoing'], created_at__lte=prev_end
    ).count()

    total_revenue = Payment.objects.filter(status='success').aggregate(t=Sum('amount'))['t'] or 0

    return {
        'revenue': {
            'value': total_revenue,
            'period': revenue_cur,
            'growth': pct_change(revenue_cur, revenue_prev),
            'up': revenue_cur >= revenue_prev,
        },
        'bookings': {
            'value': Booking.objects.count(),
            'period': bookings_cur,
            'growth': pct_change(bookings_cur, bookings_prev),
            'up': bookings_cur >= bookings_prev,
        },
        'events': {
            'value': events_cur,
            'period': events_cur,
            'growth': pct_change(events_cur, events_prev),
            'up': events_cur >= events_prev,
        },
        'users': {
            'value': users_cur,
            'period': _count_users_joined(cur_start, cur_end),
            'growth': pct_change(users_cur, users_prev),
            'up': users_cur >= users_prev,
        },
    }


def get_today_activity():
    today = timezone.now().date()
    return {
        'bookings': Booking.objects.filter(booked_at__date=today).count(),
        'revenue': Payment.objects.filter(status='success', paid_at__date=today).aggregate(
            t=Sum('amount')
        )['t'] or 0,
        'new_users': CustomUser.objects.filter(date_joined__date=today).count(),
        'logins': LoginHistory.objects.filter(logged_in_at__date=today).count(),
    }


def get_platform_health():
    pending_refunds = Booking.objects.filter(status='cancelled').filter(
        payment__status='success', payment__is_refunded=False
    ).count()
    return {
        'running_events': Event.objects.filter(status='ongoing').count(),
        'upcoming_events': Event.objects.filter(status='upcoming').count(),
        'pending_refunds': pending_refunds,
        'waitlist_requests': Waitlist.objects.count(),
        'failed_payments': Payment.objects.filter(status='failed').count(),
        'pending_payments': Payment.objects.filter(status='pending').count(),
        'unread_alerts': _recent_security_alerts(),
    }


def _recent_security_alerts():
    from accounts.models import AuditLog
    since = timezone.now() - timedelta(hours=24)
    return AuditLog.objects.filter(created_at__gte=since, action__icontains='fail').count()


def get_ai_insights():
    cat_labels, cat_values = category_distribution()
    top_category = cat_labels[0] if cat_labels else 'N/A'

    top_event = (
        Event.objects.annotate(bc=Count('bookings'))
        .order_by('-bc')
        .first()
    )
    top_event_name = top_event.title if top_event else 'No events yet'
    top_event_bookings = top_event.bc if top_event else 0

    rev_labels, rev_values = monthly_revenue_data(3)
    if len(rev_values) >= 2 and rev_values[-2] > 0:
        trend = 'up' if rev_values[-1] >= rev_values[-2] else 'down'
        rev_tip = (
            'Revenue is trending upward — consider promoting high-demand categories.'
            if trend == 'up' else
            'Revenue dipped this month — run targeted campaigns for top categories.'
        )
    else:
        rev_tip = 'Add more paid events to diversify revenue streams.'

    week_ago = timezone.now() - timedelta(days=7)
    logins_week = LoginHistory.objects.filter(logged_in_at__gte=week_ago).count()
    engagement = (
        f'{logins_week} logins this week — strong engagement.'
        if logins_week >= 5 else
        'User engagement is low — consider email campaigns or featured events.'
    )

    booking_labels, booking_values = _monthly_booking_data(3)
    if len(booking_values) >= 2:
        pred = 'stable'
        if booking_values[-1] > booking_values[-2]:
            pred = 'increasing'
        elif booking_values[-1] < booking_values[-2]:
            pred = 'decreasing'
        booking_pred = f'Booking volume is {pred} — plan capacity accordingly.'
    else:
        booking_pred = 'Insufficient data for booking predictions yet.'

    return {
        'top_category': top_category,
        'top_event_name': top_event_name,
        'top_event_bookings': top_event_bookings,
        'revenue_tip': rev_tip,
        'engagement_tip': engagement,
        'booking_prediction': booking_pred,
    }


def _monthly_booking_data(months=6):
    start = timezone.now() - timedelta(days=months * 31)
    qs = (
        Booking.objects.filter(booked_at__gte=start)
        .annotate(month=TruncMonth('booked_at'))
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


def get_top_events(limit=5):
    return (
        Event.objects.annotate(
            booking_count=Count('bookings'),
            revenue=Sum(
            'bookings__payment__amount',
            filter=Q(bookings__payment__status='success'),
        ),
        )
        .order_by('-booking_count')[:limit]
    )


def get_organizer_performance(limit=5):
    return (
        CustomUser.objects.filter(role='organizer')
        .annotate(
            event_count=Count('organized_events'),
            booking_count=Count('organized_events__bookings'),
        )
        .order_by('-booking_count')[:limit]
    )


def build_admin_dashboard_context():
    from volunteers.models import EventVolunteer

    kpis = get_kpi_metrics()
    today = get_today_activity()
    health = get_platform_health()
    insights = get_ai_insights()
    rev_labels, rev_values = monthly_revenue_data()
    book_labels, book_values = _monthly_booking_data()
    user_labels, user_values = monthly_user_growth()
    cat_labels, cat_values = category_distribution()

    recent_bookings = Booking.objects.select_related('user', 'event').order_by('-booked_at')[:8]
    recent_users = CustomUser.platform_users().order_by('-date_joined')[:8]

    return {
        'greeting': get_greeting(),
        'kpis': kpis,
        'today': today,
        'health': health,
        'insights': insights,
        'recent_bookings': recent_bookings,
        'recent_users': recent_users,
        'total_event_volunteers': EventVolunteer.objects.count(),
        'chart_revenue_labels': json.dumps(rev_labels),
        'chart_revenue_values': json.dumps(rev_values),
        'chart_booking_labels': json.dumps(book_labels),
        'chart_booking_values': json.dumps(book_values),
        'chart_user_labels': json.dumps(user_labels),
        'chart_user_values': json.dumps(user_values),
        'chart_cat_labels': json.dumps(cat_labels),
        'chart_cat_values': json.dumps(cat_values),
    }


def build_admin_statistics_context():
    rev_labels, rev_values = monthly_revenue_data(12)
    user_labels, user_values = monthly_user_growth(12)
    book_labels, book_values = _monthly_booking_data(12)
    cat_labels, cat_values = category_distribution()
    kpis = get_kpi_metrics()
    top_events = get_top_events(10)
    organizers = get_organizer_performance(10)
    tickets_sold = Booking.objects.filter(status__in=['confirmed', 'attended']).aggregate(
        t=Sum('quantity')
    )['t'] or 0

    return {
        'kpis': kpis,
        'top_events': top_events,
        'organizers': organizers,
        'tickets_sold': tickets_sold,
        'chart_revenue_labels': json.dumps(rev_labels),
        'chart_revenue_values': json.dumps(rev_values),
        'chart_user_labels': json.dumps(user_labels),
        'chart_user_values': json.dumps(user_values),
        'chart_booking_labels': json.dumps(book_labels),
        'chart_booking_values': json.dumps(book_values),
        'chart_cat_labels': json.dumps(cat_labels),
        'chart_cat_values': json.dumps(cat_values),
    }
