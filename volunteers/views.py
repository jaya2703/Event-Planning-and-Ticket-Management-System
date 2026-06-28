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
        qs = EventVolunteer.objects.select_related('event', 'duty_area')
    else:
        qs = EventVolunteer.objects.filter(event__organizer=request.user).select_related('event', 'duty_area')

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

    volunteers = event.event_volunteers.all().select_related('duty_area')
    form = EventVolunteerForm(event=event)

    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'add':
            form = EventVolunteerForm(request.POST, event=event)
            if form.is_valid():
                vol = form.save(commit=False)
                vol.event = event
                vol.save()
                
                # Staff assignment notification trigger
                from accounts.models import CustomUser
                from accounts.services import notify
                staff_user = None
                if vol.email:
                    staff_user = CustomUser.objects.filter(email=vol.email).first()
                if not staff_user and vol.mobile:
                    staff_user = CustomUser.objects.filter(phone=vol.mobile).first()
                if staff_user:
                    notify(
                        staff_user,
                        f"You have been assigned to staff duty for '{event.title}' as '{vol.role}' in duty area '{vol.duty_area.name if vol.duty_area else 'General'}'.",
                        'general',
                        link=f'/events/{event.id}/'
                    )

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
    
    # Get dynamic duty areas configured for this event
    from .models import DutyArea
    duty_areas = DutyArea.objects.filter(event=event)

    return render(request, 'volunteers/manage_event.html', {
        'event': event,
        'volunteers': volunteers,
        'form': form,
        'stats': stats,
        'duty_areas': duty_areas
    })


@login_required
def edit_volunteer(request, volunteer_id):
    vol = get_object_or_404(EventVolunteer, id=volunteer_id)
    if not _can_manage_event(request.user, vol.event):
        messages.error(request, 'Permission denied.')
        return redirect('events:detail', event_id=vol.event_id)

    if request.method == 'POST':
        form = EventVolunteerForm(request.POST, instance=vol, event=vol.event)
        if form.is_valid():
            form.save()
            
            # Staff change notification trigger
            from accounts.models import CustomUser
            from accounts.services import notify
            staff_user = None
            if vol.email:
                staff_user = CustomUser.objects.filter(email=vol.email).first()
            if not staff_user and vol.mobile:
                staff_user = CustomUser.objects.filter(phone=vol.mobile).first()
            if staff_user:
                notify(
                    staff_user,
                    f"Your staff assignment for '{vol.event.title}' has been updated to '{vol.role}' in duty area '{vol.duty_area.name if vol.duty_area else 'General'}'.",
                    'general',
                    link=f'/events/{vol.event.id}/'
                )

            messages.success(request, f'{vol.name} updated.')
            return redirect('volunteers:manage', event_id=vol.event_id)
    else:
        form = EventVolunteerForm(instance=vol, event=vol.event)

    return render(request, 'volunteers/edit.html', {'form': form, 'volunteer': vol, 'event': vol.event})


@login_required
def manage_duty_areas(request, event_id):
    """View to list, add and delete duty areas for an event"""
    event = get_object_or_404(Event, id=event_id)
    if not _can_manage_event(request.user, event):
        messages.error(request, 'Permission denied.')
        return redirect('events:detail', event_id=event.id)

    from .models import DutyArea
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name', '').strip()
            if name:
                if not DutyArea.objects.filter(event=event, name__iexact=name).exists():
                    DutyArea.objects.create(event=event, name=name)
                    messages.success(request, f"Duty area '{name}' added successfully.")
                else:
                    messages.error(request, f"Duty area '{name}' already exists.")
            else:
                messages.error(request, "Duty area name cannot be empty.")
        elif action == 'delete':
            area_id = request.POST.get('area_id')
            area = get_object_or_404(DutyArea, id=area_id, event=event)
            name = area.name
            area.delete()
            messages.success(request, f"Duty area '{name}' deleted.")
            
    return redirect('volunteers:manage', event_id=event.id)


# Backward-compatible alias
assign_volunteer = manage_event_volunteers
