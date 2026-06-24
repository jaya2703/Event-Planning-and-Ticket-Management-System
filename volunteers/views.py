from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q

from events.models import Event
from .models import EventVolunteer
from .forms import EventVolunteerForm


def _can_manage_event(user, event):
    return user.role == 'admin' or event.organizer_id == user.id


@login_required
def volunteer_overview(request):
    """Organizer volunteer management across all events."""
    if request.user.role not in ('organizer', 'admin'):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')

    if request.user.role == 'admin':
        qs = EventVolunteer.objects.select_related('event')
    else:
        qs = EventVolunteer.objects.filter(event__organizer=request.user).select_related('event')

    today = timezone.now().date()
    stats = {
        'total': qs.count(),
        'assigned': qs.filter(status='assigned').count(),
        'active_today': qs.filter(is_present=True).count(),
        'pending': qs.filter(status='pending').count(),
    }
    volunteers = qs.order_by('-assigned_at')[:50]
    events = (
        Event.objects.filter(organizer=request.user)
        if request.user.role == 'organizer'
        else Event.objects.all()
    )

    return render(request, 'volunteers/overview.html', {
        'volunteers': volunteers,
        'stats': stats,
        'events': events,
    })


@login_required
def manage_event_volunteers(request, event_id):
    """Add, edit, and manage volunteers for a single event."""
    event = get_object_or_404(Event, id=event_id)
    if not _can_manage_event(request.user, event):
        messages.error(request, 'Permission denied.')
        return redirect('events:detail', event_id=event.id)

    volunteers = event.event_volunteers.all()
    form = EventVolunteerForm()

    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'add':
            form = EventVolunteerForm(request.POST)
            if form.is_valid():
                vol = form.save(commit=False)
                vol.event = event
                vol.save()
                messages.success(request, f'{vol.name} added as event staff.')
                return redirect('volunteers:manage', event_id=event.id)
        elif action == 'delete':
            vol = get_object_or_404(EventVolunteer, id=request.POST.get('volunteer_id'), event=event)
            name = vol.name
            vol.delete()
            messages.success(request, f'{name} removed from event staff.')
            return redirect('volunteers:manage', event_id=event.id)
        elif action == 'attendance':
            vol = get_object_or_404(EventVolunteer, id=request.POST.get('volunteer_id'), event=event)
            vol.is_present = not vol.is_present
            vol.checked_in_at = timezone.now() if vol.is_present else None
            vol.status = 'active' if vol.is_present else 'assigned'
            vol.save()
            return redirect('volunteers:manage', event_id=event.id)

    stats = {
        'total': volunteers.count(),
        'assigned': volunteers.filter(status='assigned').count(),
        'active': volunteers.filter(status='active').count(),
        'present': volunteers.filter(is_present=True).count(),
    }

    return render(request, 'volunteers/manage_event.html', {
        'event': event,
        'volunteers': volunteers,
        'form': form,
        'stats': stats,
    })


@login_required
def edit_volunteer(request, volunteer_id):
    vol = get_object_or_404(EventVolunteer, id=volunteer_id)
    if not _can_manage_event(request.user, vol.event):
        messages.error(request, 'Permission denied.')
        return redirect('events:detail', event_id=vol.event_id)

    if request.method == 'POST':
        form = EventVolunteerForm(request.POST, instance=vol)
        if form.is_valid():
            form.save()
            messages.success(request, f'{vol.name} updated.')
            return redirect('volunteers:manage', event_id=vol.event_id)
    else:
        form = EventVolunteerForm(instance=vol)

    return render(request, 'volunteers/edit.html', {'form': form, 'volunteer': vol, 'event': vol.event})


# Backward-compatible alias
assign_volunteer = manage_event_volunteers
