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


class AdminAccountForm(forms.ModelForm):
    """Minimal account settings for administrators."""

    current_password = forms.CharField(
        required=False,
        label='Current password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Required only when changing password', 'autocomplete': 'current-password'}),
    )
    new_password = forms.CharField(
        required=False,
        label='New password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Leave blank to keep current password', 'autocomplete': 'new-password'}),
    )
    confirm_password = forms.CharField(
        required=False,
        label='Confirm new password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Re-enter new password', 'autocomplete': 'new-password'}),
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'phone']
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Administrator username'}),
            'email': forms.EmailInput(attrs={'placeholder': 'admin@example.com'}),
            'phone': forms.TextInput(attrs={'placeholder': '+91 98765 43210'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if CustomUser.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This email is already in use.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        current = cleaned_data.get('current_password', '')
        new = cleaned_data.get('new_password', '')
        confirm = cleaned_data.get('confirm_password', '')

        if any([current, new, confirm]):
            if not all([current, new, confirm]):
                raise forms.ValidationError('To change your password, fill in all three password fields.')
            if not self.instance.check_password(current):
                self.add_error('current_password', 'Current password is incorrect.')
            if new != confirm:
                self.add_error('confirm_password', 'New passwords do not match.')
            else:
                from django.contrib.auth.password_validation import validate_password
                validate_password(new, self.instance)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        new_password = self.cleaned_data.get('new_password')
        if new_password:
            user.set_password(new_password)
        if commit:
            user.save()
        return user
