"""
Accounts Forms
==============
Forms are used to collect data from users (like a registration form).
Django forms handle validation automatically.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser


class RegisterForm(UserCreationForm):
    """
    Registration form for new users.
    We extend Django's built-in UserCreationForm to add our extra fields.
    """
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    phone = forms.CharField(max_length=15, required=False)
    
    # Users can choose their role when registering
    role = forms.ChoiceField(choices=[
        ('user', 'Attendee'),
        ('organizer', 'Event Organizer'),
    ])
    
    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'role', 'password1', 'password2']
    
    def clean_email(self):
        """Make sure email is not already used"""
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email


class ProfileUpdateForm(forms.ModelForm):
    """Form for users to update their profile"""
    
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'bio', 'profile_picture', 'interests']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
            'interests': forms.TextInput(attrs={'placeholder': 'e.g. music, sports, technology'}),
        }
