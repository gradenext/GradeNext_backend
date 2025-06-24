# quiz/serializers.py
from rest_framework import serializers
from .models import CustomUser,UserSession,UserProgress,PLAN_CHOICES
from quiz.config.curriculum import GRADE_SUBJECT_CONFIG,DIFFICULTY_LEVELS

# quiz/serializers.py
from rest_framework import serializers
from quiz.config.curriculum import GRADE_SUBJECT_CONFIG

class UserRegistrationSerializer(serializers.ModelSerializer):
    plan = serializers.ChoiceField(choices=PLAN_CHOICES, write_only=True)
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)
    coupon_code = serializers.CharField(write_only=True, required=False,allow_blank=True)

    class Meta:
        model = CustomUser
        fields = [
            'email', 'password', 'confirm_password', 'student_name',
            'parent_name', 'gender', 'grade', 'courses', 'country',
            'state', 'zip_code','plan','coupon_code'
        ]

    def validate(self, data):
        if data['password'] != data.pop('confirm_password'):
            raise serializers.ValidationError("Passwords do not match")
        
        if data['plan'] not in [choice[0] for choice in PLAN_CHOICES]:
            raise serializers.ValidationError("Invalid plan selected")
        coupon_code = data.pop('coupon_code', None)
        if coupon_code:
            if coupon_code != "NG100":  # Hardcoded special coupon
                raise serializers.ValidationError("Invalid coupon code")
            data['plan'] = 'enterprise'  # Override plan to enterprise
        
        return data

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)
    
# Add these new serializers
class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(min_length=6, write_only=True)
class UserProfileSerializer(serializers.ModelSerializer):
    plan = serializers.CharField(source='get_plan_display')
    
    class Meta:
        model = CustomUser
        fields = [
            'account_id', 'email', 'student_name', 'parent_name',
            'gender', 'grade', 'courses', 'country', 'state', 
            'zip_code', 'plan'
        ]
        read_only_fields = ['account_id', 'email']

    def get_active_session(self, obj):
        active_session = UserSession.objects.filter(user=obj, is_active=True).first()
        return str(active_session.session_id) if active_session else None



class QuestionRequestSerializer(serializers.Serializer):
    grade = serializers.IntegerField(min_value=1, max_value=8)
    subject = serializers.ChoiceField(choices=["mathematics", "english", "science"])
    session_id = serializers.UUIDField()

    def validate(self, data):
        user = self.context['request'].user
        if data['subject'] not in user.courses:
            raise serializers.ValidationError("User not enrolled in this subject")
        
        if data['grade'] not in GRADE_SUBJECT_CONFIG:
            raise serializers.ValidationError("Invalid grade")
            
        if data['subject'] not in GRADE_SUBJECT_CONFIG[data['grade']]:
            raise serializers.ValidationError("Subject not available for this grade")
            
        return data
    
    
class RevisionQuestionRequestSerializer(serializers.Serializer):
    subject = serializers.ChoiceField(choices=["mathematics", "english", "science"])
    session_id = serializers.UUIDField()

    def validate(self, data):
        user = self.context['request'].user
        try:
            user_progress = UserProgress.objects.get(
                user=user,
                grade=user.grade,
                subject=data['subject']
            )
            if not user_progress.completed_topics:
                raise serializers.ValidationError("No completed topics available for revision")
            return data
        except UserProgress.DoesNotExist:
            raise serializers.ValidationError("Progress record not found")
        
class SubmitAnswerSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    user_answer = serializers.CharField(max_length=255)
    
# Add to serializers.py
class TopicIntroductionSerializer(serializers.Serializer):
    subject = serializers.ChoiceField(choices=["mathematics", "english", "science"])
    
    
# class TopicSelectionSerializer(serializers.Serializer):
#     subject = serializers.ChoiceField(choices=["mathematics", "english"])
#     topic = serializers.CharField()

#     def validate(self, data):
#         user = self.context['request'].user
#         subject = data['subject']
#         topic = data['topic']
        
#         try:
#             topics = GRADE_SUBJECT_CONFIG[user.grade][subject]["topics"]
#             if topic not in topics:
#                 raise serializers.ValidationError("Invalid topic for selected subject and grade")
#         except KeyError:
#             raise serializers.ValidationError("Invalid subject or grade configuration")
            
#         return data

# class SubjectTopicsSerializer(serializers.Serializer):
#     subject = serializers.ChoiceField(choices=["mathematics", "english"])
    
class TopicQuestionRequestSerializer(serializers.Serializer):
    subject = serializers.ChoiceField(choices=["mathematics", "english", "science"])
    topic = serializers.CharField()
    session_id = serializers.UUIDField()

    def validate(self, data):
        user = self.context['request'].user
        try:
            topics = GRADE_SUBJECT_CONFIG[user.grade][data['subject']]["topics"]
            if data['topic'] not in topics:
                raise serializers.ValidationError("Invalid topic for subject and grade")
        except KeyError:
            raise serializers.ValidationError("Invalid subject configuration")
        return data
    
class SessionSerializer(serializers.Serializer):
    subject = serializers.ChoiceField(choices=["mathematics", "english", "science"], required=False)
    topic = serializers.CharField(required=False)
