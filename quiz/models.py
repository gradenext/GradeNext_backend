import uuid
from django.db import models
from django.conf import settings
from quiz.config.curriculum import DIFFICULTY_LEVELS
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin ,BaseUserManager
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email must be set')
        email = self.normalize_email(email)
        
        if extra_fields.get('plan', 'trial') == 'trial':
            extra_fields['trial_start_date'] = timezone.now()
            
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

PLAN_CHOICES = [
    ('trial', 'Trial'),
    ('basic', 'Basic'),
    ('pro', 'Pro'),
    ('enterprise', 'Enterprise'),
]
class Coupon(models.Model):
    code = models.CharField(max_length=20, unique=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_CHOICES)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    max_uses = models.PositiveIntegerField(default=1)
    times_used = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and
            self.valid_from <= now <= self.valid_to and
            self.times_used < self.max_uses
        )
        
class OTPVerification(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    purpose = models.CharField(max_length=20, default='registration')
    registration_data = models.JSONField(null=True, blank=True)

    def is_expired(self):
        from django.utils import timezone
        return (timezone.now() - self.created_at).total_seconds() > 900
class CustomUser(AbstractBaseUser, PermissionsMixin):

    account_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(unique=True)
    student_name = models.CharField(max_length=255)
    parent_name = models.CharField(max_length=255)
    gender = models.CharField(max_length=10)
    grade = models.PositiveSmallIntegerField()
    courses = models.JSONField(default=list)
    country = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False) 
    trial_start_date = models.DateTimeField(null=True, blank=True) 
    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default='trial'
    )
    applied_coupon = models.ForeignKey(
        Coupon, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL
    )
    
    def is_trial_expired(self):
        if self.plan != 'trial' or not self.trial_start_date:
            return False
        return timezone.now() > self.trial_start_date + timedelta(days=14)

    def trial_days_remaining(self):
        if self.plan != 'trial' or not self.trial_start_date:
            return 0
        days_passed = (timezone.now() - self.trial_start_date).days
        remaining = 14 - days_passed
        return max(0, remaining)

    
    
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['student_name', 'parent_name', 'gender', 'grade']
    
    objects = CustomUserManager()

    def __str__(self):
        return self.email
    

    
class UserSession(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-start_time']

class SessionProgress(models.Model):
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE, related_name='progresses')
    subject = models.CharField(max_length=20)
    current_topic = models.CharField(max_length=100)
    current_level = models.CharField(max_length=20, choices=[(l, l) for l in DIFFICULTY_LEVELS])
    correct_answers = models.PositiveIntegerField(default=0)
    incorrect_answers = models.PositiveIntegerField(default=0)
    completed_topics = models.JSONField(default=list)
    current_streak = models.PositiveIntegerField(default=0)  # Add this
    max_streak = models.PositiveIntegerField(default=0)
    # is_custom_topic = models.BooleanField(default=False)  

    def get_next_level(self):
        current_index = DIFFICULTY_LEVELS.index(self.current_level)
        if current_index < len(DIFFICULTY_LEVELS) - 1:
            return DIFFICULTY_LEVELS[current_index + 1]
        return None

    def get_next_topic(self):
        from quiz.config.curriculum import GRADE_SUBJECT_CONFIG
        topics = GRADE_SUBJECT_CONFIG[self.session.user.grade][self.session.user.subject]["topics"]
        try:
            current_index = topics.index(self.current_topic)
            if current_index < len(topics) - 1:
                return topics[current_index + 1]
            return None
        except ValueError:
            return topics[0] if topics else None
    def clean(self):
        if self.current_topic in self.completed_topics:
            raise ValidationError("Current topic cannot be in completed topics")

class UserProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    grade = models.PositiveSmallIntegerField()
    subject = models.CharField(max_length=20)
    current_topic = models.CharField(max_length=100)
    current_level = models.CharField(max_length=20, choices=[(l, l) for l in DIFFICULTY_LEVELS])
    total_correct = models.PositiveIntegerField(default=0)
    total_incorrect = models.PositiveIntegerField(default=0)
    completed_topics = models.JSONField(default=list)
    current_streak = models.PositiveIntegerField(default=0)  # Add this
    max_streak = models.PositiveIntegerField(default=0) 
    class Meta:
        unique_together = ('user', 'grade', 'subject')
        verbose_name_plural = "User Progress Records"

    def get_next_level(self):
        current_index = DIFFICULTY_LEVELS.index(self.current_level)
        if current_index < len(DIFFICULTY_LEVELS) - 1:
            return DIFFICULTY_LEVELS[current_index + 1]
        return None

    def get_next_topic(self):
        from quiz.config.curriculum import GRADE_SUBJECT_CONFIG
        topics = GRADE_SUBJECT_CONFIG[self.grade][self.subject]["topics"]
        try:
            current_index = topics.index(self.current_topic)
            if current_index < len(topics) - 1:
                return topics[current_index + 1]
            return None  # No more topics
        except ValueError:
            return topics[0] if topics else None

    def __str__(self):
        return f"{self.user.email} - Grade {self.grade} {self.subject}"
    
class QuestionRecord(models.Model):
    QUESTION_TYPES = [
        ('regular', 'Regular Curriculum'),
        ('revision', 'Revision'),
        ('topic_practice', 'Topic Practice')
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE)
    question_id = models.UUIDField(default=uuid.uuid4, unique=True)
    question_text = models.TextField()
    options = models.JSONField()
    correct_answer = models.CharField(max_length=255)
    user_answer = models.CharField(max_length=255, null=True)
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    subject = models.CharField(max_length=20)
    topic = models.CharField(max_length=100)
    level = models.CharField(max_length=20)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='regular')
    

class UserQuestionHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question_signature = models.CharField(max_length=64)  # SHA-256 hash
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # unique_together = ('user', 'question_signature')
        indexes = [
            models.Index(fields=['user', 'question_signature'])
        ]
        
class UserTopicProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.CharField(max_length=20)
    topic = models.CharField(max_length=100)
    correct = models.PositiveIntegerField(default=0)
    incorrect = models.PositiveIntegerField(default=0)
    current_level = models.CharField(max_length=20, choices=[(l, l) for l in DIFFICULTY_LEVELS], default=DIFFICULTY_LEVELS[0])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'subject', 'topic')
        
        
class StripeSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    user_name = models.CharField(max_length=255)
    user_email = models.EmailField()
    
    stripe_customer_id = models.CharField(max_length=255)
    stripe_subscription_id = models.CharField(max_length=255)
    
    plan = models.CharField(max_length=50)
    duration = models.IntegerField()
    platform_fee_applied = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, default="active")  # e.g., active, cancelled
    cancel_at_period_end = models.BooleanField(default=False)
    
    current_price_id = models.CharField(max_length=100, null=True, blank=True)
    coupon_applied = models.CharField(max_length=50, null=True, blank=True)
    
    start_date = models.DateTimeField(default=timezone.now)  # to track when the subscription started
    end_date = models.DateTimeField(null=True, blank=True)   # to track when the subscription ends


    def __str__(self):
        return f"{self.user_email} - {self.plan} ({self.duration} month(s))"

        
