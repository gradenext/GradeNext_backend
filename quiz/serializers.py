# quiz/serializers.py
from rest_framework import serializers
from .models import CustomUser,UserSession,UserProgress
from quiz.config.curriculum import GRADE_SUBJECT_CONFIG,DIFFICULTY_LEVELS

# quiz/serializers.py
from rest_framework import serializers
from quiz.config.curriculum import GRADE_SUBJECT_CONFIG

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'email', 'password', 'confirm_password', 'student_name',
            'parent_name', 'gender', 'grade', 'courses', 'country',
            'state', 'zip_code'
        ]

    def validate(self, data):
        if data['password'] != data.pop('confirm_password'):
            raise serializers.ValidationError("Passwords do not match")
        return data

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)
    
    
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'account_id', 'email', 'student_name', 'parent_name',
            'gender', 'grade', 'courses',
            'country', 'state', 'zip_code'
        ]

    def get_active_session(self, obj):
        active_session = UserSession.objects.filter(user=obj, is_active=True).first()
        return str(active_session.session_id) if active_session else None



class QuestionRequestSerializer(serializers.Serializer):
    grade = serializers.IntegerField(min_value=1, max_value=5)
    subject = serializers.ChoiceField(choices=["mathematics", "english"])
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
    subject = serializers.ChoiceField(choices=["mathematics", "english"])
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