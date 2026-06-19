from django.contrib import admin
from .models import Event, Category, Poll, PollOption, PollVote, EventFeedback

admin.site.register(Event)
admin.site.register(Category)
admin.site.register(Poll)
admin.site.register(PollOption)
admin.site.register(EventFeedback)
