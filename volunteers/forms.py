from django import forms
from .models import EventVolunteer


class EventVolunteerForm(forms.ModelForm):
    class Meta:
        model = EventVolunteer
        fields = ['name', 'mobile', 'email', 'duty', 'shift_timing', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control ep-input', 'placeholder': 'Full name'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control ep-input', 'placeholder': '+91 98765 43210'}),
            'email': forms.EmailInput(attrs={'class': 'form-control ep-input', 'placeholder': 'email@example.com'}),
            'duty': forms.Select(attrs={'class': 'form-select ep-input'}),
            'shift_timing': forms.TextInput(attrs={'class': 'form-control ep-input', 'placeholder': 'e.g. 09:00 AM – 01:00 PM'}),
            'status': forms.Select(attrs={'class': 'form-select ep-input'}),
        }
