from django import forms
from django.db import models
from .models import EventVolunteer, DutyArea


class EventVolunteerForm(forms.ModelForm):
    class Meta:
        model = EventVolunteer
        fields = ['name', 'mobile', 'email', 'role', 'duty_area', 'shift_timing', 'notes', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control ep-input', 'placeholder': 'Full name'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control ep-input', 'placeholder': '+91 98765 43210'}),
            'email': forms.EmailInput(attrs={'class': 'form-control ep-input', 'placeholder': 'email@example.com (optional)'}),
            'role': forms.TextInput(attrs={'class': 'form-control ep-input', 'placeholder': 'e.g. Security Guard, Volunteer'}),
            'shift_timing': forms.TextInput(attrs={'class': 'form-control ep-input', 'placeholder': 'e.g. 09:00 AM – 01:00 PM'}),
            'notes': forms.Textarea(attrs={'class': 'form-control ep-input', 'placeholder': 'Shift notes...', 'rows': 2}),
            'status': forms.Select(attrs={'class': 'form-select ep-input'}),
        }

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)
        if event:
            # Show global duty areas + event-specific duty areas
            self.fields['duty_area'].queryset = DutyArea.objects.filter(
                models.Q(event=event) | models.Q(is_global=True)
            )
            self.fields['duty_area'].empty_label = "-- Select Duty Area --"
            self.fields['duty_area'].widget.attrs.update({'class': 'form-select ep-input'})
