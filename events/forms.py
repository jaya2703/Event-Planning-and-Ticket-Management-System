from django import forms
from .models import Event, Poll, PollOption, EventFeedback


class EventForm(forms.ModelForm):
    """Form for creating/editing events"""
    class Meta:
        model = Event
        fields = ['title', 'description', 'category', 'banner', 'date', 'time', 
                  'venue', 'city', 'total_capacity', 'ticket_price', 'rules', 'status']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'rules': forms.Textarea(attrs={'rows': 3}),
        }


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = EventFeedback
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Share your experience...'}),
        }


class PollForm(forms.ModelForm):
    class Meta:
        model = Poll
        fields = ['question']
