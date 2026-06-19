from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import VolunteerAssignment
from events.models import Event
from accounts.models import CustomUser


@login_required
def assign_volunteer(request, event_id):
    """Organizer assigns a volunteer to their event"""
    event = get_object_or_404(Event, id=event_id)
    
    if event.organizer != request.user and request.user.role != 'admin':
        messages.error(request, "Permission denied.")
        return redirect('events:detail', event_id=event.id)
    
    if request.method == 'POST':
        volunteer_id = request.POST.get('volunteer_id')
        role = request.POST.get('role', 'helpdesk')
        
        try:
            volunteer = CustomUser.objects.get(id=volunteer_id, role='volunteer')
            VolunteerAssignment.objects.get_or_create(
                volunteer=volunteer, event=event,
                defaults={'role': role}
            )
            messages.success(request, f"{volunteer.username} assigned as volunteer!")
        except CustomUser.DoesNotExist:
            messages.error(request, "Volunteer not found.")
    
    volunteers = CustomUser.objects.filter(role='volunteer')
    assigned = VolunteerAssignment.objects.filter(event=event)
    return render(request, 'volunteers/assign.html', {
        'event': event, 'volunteers': volunteers, 'assigned': assigned
    })
