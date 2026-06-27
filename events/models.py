"""
Events Models
=============
This file defines what an "Event" looks like in our database.
"""
from django.db import models
from django.conf import settings


class Category(models.Model):
    """Event categories like Music, Sports, Tech, etc."""
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default='bi-star')  # Bootstrap icon class
    
    class Meta:
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name


class Venue(models.Model):
    """
    Venue metadata for hosting events
    """
    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='venues', null=True, blank=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField(default=100)
    map_link = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.city})"


class Speaker(models.Model):
    """
    Event speakers profile details
    """
    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='speakers', null=True, blank=True)
    name = models.CharField(max_length=150)
    title = models.CharField(max_length=150, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    avatar = models.ImageField(upload_to='speakers/', blank=True, null=True)
    twitter = models.CharField(max_length=200, blank=True, null=True)
    linkedin = models.CharField(max_length=200, blank=True, null=True)
    website = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Event(models.Model):
    """
    The main Event model.
    Stores all information about an event.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
    ]
    
    # Who created this event (must be an organizer or admin)
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organized_events'
    )
    
    # SaaS tenancy link
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events'
    )
    
    # Basic event info
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    
    # Event image/banner
    banner = models.ImageField(
        upload_to='event_banners/',
        blank=True, null=True
    )
    
    # When and where (multi-day ready)
    date = models.DateField()
    time = models.TimeField()
    end_date = models.DateField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=300)
    venue_ref = models.ForeignKey(
        Venue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events'
    )
    city = models.CharField(max_length=100, default='')
    
    # Ticketing & Visibility
    total_capacity = models.PositiveIntegerField(default=100)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    visibility = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('private', 'Private')],
        default='public'
    )
    password = models.CharField(max_length=50, blank=True, null=True)
    is_template = models.BooleanField(default=False)
    
    # Rules
    rules = models.TextField(blank=True, null=True)
    
    # Status of the event
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    
    # When this event was created in our system
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    @property
    def tickets_booked(self):
        """How many tickets have been booked for this event"""
        from bookings.models import Booking
        return Booking.objects.filter(
            event=self,
            status__in=['confirmed', 'attended', 'pending_payment']
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    @property
    def tickets_available(self):
        """How many tickets are still available"""
        return self.total_capacity - self.tickets_booked
    
    @property
    def is_full(self):
        """Returns True if no tickets are available"""
        return self.tickets_available <= 0
    
    @property
    def crowd_density(self):
        """
        Live Crowd Density feature:
        Calculate how crowded the event is based on check-ins.
        Formula: check-ins / total_capacity
        """
        from bookings.models import Booking
        checkins = Booking.objects.filter(event=self, is_checked_in=True).count()
        if self.total_capacity == 0:
            return 0
        ratio = checkins / self.total_capacity
        
        if ratio < 0.3:
            return 'low'
        elif ratio < 0.7:
            return 'medium'
        else:
            return 'high'
    
    @property
    def fill_percentage(self):
        """What percentage of capacity is booked"""
        if self.total_capacity == 0:
            return 0
        return min(100, int((self.tickets_booked / self.total_capacity) * 100))

    @property
    def banner_theme_class(self):
        """CSS class for category-themed placeholder banner."""
        themes = {
            'Music': 'ep-theme-music',
            'Sports': 'ep-theme-sports',
            'Technology': 'ep-theme-tech',
            'Food & Drink': 'ep-theme-food',
            'Arts': 'ep-theme-arts',
            'Business': 'ep-theme-business',
            'Health': 'ep-theme-health',
            'Education': 'ep-theme-education',
        }
        if self.category and self.category.name in themes:
            return themes[self.category.name]
        return 'ep-theme-default'

    @property
    def banner_icon(self):
        """Bootstrap icon for category placeholder banner."""
        if self.category and self.category.icon:
            return self.category.icon
        return 'bi-calendar-event'

    @property
    def card_fallback_image(self):
        """Static image for cards when no banner is uploaded."""
        images = {
            'Music': 'images/hero/hero-concert.jpg',
            'Sports': 'images/events/sports.jpg',
            'Technology': 'images/events/technology.jpg',
            'Food & Drink': 'images/events/food.jpg',
            'Arts': 'images/events/arts.jpg',
            'Business': 'images/events/business.jpg',
            'Health': 'images/events/health.jpg',
            'Education': 'images/events/education.jpg',
        }
        if self.category and self.category.name in images:
            return images[self.category.name]
        return 'images/events/default.jpg'


class Poll(models.Model):
    """Live poll for an event"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='polls')
    question = models.CharField(max_length=300)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Poll: {self.question[:50]} ({self.event.title})"


class PollOption(models.Model):
    """Options for a poll question"""
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=200)
    
    def __str__(self):
        return self.option_text
    
    @property
    def vote_count(self):
        return self.votes.count()


class PollVote(models.Model):
    """Stores who voted for what"""
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['poll', 'user']  # One vote per user per poll
    
    def __str__(self):
        return f"{self.user.username} voted on {self.poll}"


class EventFeedback(models.Model):
    """User feedback/reviews for events"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='feedbacks')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])  # 1-5 stars
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['event', 'user']
    
    def __str__(self):
        return f"{self.user.username} rated {self.event.title}: {self.rating}/5"


class TicketTier(models.Model):
    """Multiple ticket types per event."""
    TIER_CHOICES = [
        ('general', 'General'),
        ('vip', 'VIP'),
        ('student', 'Student'),
        ('early_bird', 'Early Bird'),
        ('group', 'Group'),
        ('complimentary', 'Complimentary'),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_tiers')
    tier_type = models.CharField(max_length=20, choices=TIER_CHOICES, default='general')
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    capacity = models.PositiveIntegerField(default=50)
    description = models.CharField(max_length=300, blank=True, default='')
    is_active = models.BooleanField(default=True)
    
    # SaaS features
    early_bird_deadline = models.DateTimeField(null=True, blank=True)
    ticket_limit_per_user = models.PositiveIntegerField(default=5)
    availability_timer = models.DateTimeField(null=True, blank=True)
    group_size = models.PositiveIntegerField(default=1, help_text="Min tickets for group tier")

    class Meta:
        unique_together = ['event', 'tier_type']
        ordering = ['price']

    def __str__(self):
        return f"{self.event.title} — {self.name}"

    @property
    def sold_count(self):
        from bookings.models import Booking
        return Booking.objects.filter(
            ticket_tier=self,
            status__in=['confirmed', 'attended', 'pending_payment']
        ).aggregate(total=models.Sum('quantity'))['total'] or 0

    @property
    def available(self):
        return max(0, self.capacity - self.sold_count)


class Session(models.Model):
    """Event sessions (agenda builder)"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='sessions')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    speaker = models.ForeignKey(Speaker, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')

    def __str__(self):
        return f"{self.title} ({self.event.title})"


class Sponsor(models.Model):
    """Event sponsors and deliverables checklist"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='sponsors')
    name = models.CharField(max_length=150)
    logo = models.ImageField(upload_to='sponsors/', blank=True, null=True)
    website = models.CharField(max_length=200, blank=True, null=True)
    tier = models.CharField(max_length=20, choices=[('gold', 'Gold'), ('silver', 'Silver'), ('bronze', 'Bronze')], default='silver')
    booth_number = models.CharField(max_length=50, blank=True, null=True)
    deliverables = models.TextField(blank=True, null=True, help_text="Deliverables checklist description")

    def __str__(self):
        return f"{self.name} ({self.event.title})"


class EventFAQ(models.Model):
    """Frequently asked questions for events"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(max_length=300)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"FAQ: {self.question[:50]}"

