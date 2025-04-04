
from django.contrib.auth import get_user_model
from .utils.generator import QuestionGenerator
from .config.curriculum import GRADE_SUBJECT_CONFIG, DIFFICULTY_LEVELS
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from .models import CustomUser, UserSession, SessionProgress, UserProgress, QuestionRecord
from .serializers import UserRegistrationSerializer, UserProfileSerializer, RevisionQuestionRequestSerializer, SubmitAnswerSerializer, QuestionRequestSerializer
from django.utils import timezone
from django.db.utils import IntegrityError
import random
import uuid

User = get_user_model()


class RegisterAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            # Remove password confirmation before user creation
            validated_data = serializer.validated_data.copy()
            password = validated_data.pop('password')
            validated_data.pop('confirm_password', None)

            try:
                user = CustomUser.objects.create_user(
                    password=password,
                    **validated_data
                )
                token = Token.objects.create(user=user)
                return Response({
                    'token': token.key,
                    'account_id': user.account_id,
                    'user': UserProfileSerializer(user).data
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        user = authenticate(email=email, password=password)

        if user:
            # Close existing sessions
            UserSession.objects.filter(
                user=user, is_active=True).update(is_active=False)

            # Create new session
            new_session = UserSession.objects.create(user=user)

            # Initialize progress for each enrolled subject
            for subject in user.courses:
                # Get or create user progress
                user_progress, created = UserProgress.objects.get_or_create(
                    user=user,
                    grade=user.grade,
                    subject=subject,
                    defaults={
                        'current_topic': GRADE_SUBJECT_CONFIG[user.grade][subject]["topics"][0],
                        'completed_topics': [],  # Explicit empty list
                        'current_level': DIFFICULTY_LEVELS[0]
                    }
                )

                # Create session progress using user's existing progress
                SessionProgress.objects.create(
                    session=new_session,
                    subject=subject,
                    current_topic=user_progress.current_topic,
                    current_level=user_progress.current_level,
                    correct_answers=0,
                    incorrect_answers=0,
                    completed_topics=user_progress.completed_topics.copy()
                )

            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'account_id': user.account_id,
                'session_id': str(new_session.session_id),
                'user': UserProfileSerializer(user).data
            })
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get('session_id')
        try:
            session = UserSession.objects.get(
                session_id=session_id, user=request.user)
            session.is_active = False
            session.end_time = timezone.now()
            session.save()
            request.auth.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except UserSession.DoesNotExist:
            return Response({'error': 'Invalid session'}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


from django.contrib.auth import get_user_model
from .utils.generator import QuestionGenerator
from .config.curriculum import GRADE_SUBJECT_CONFIG, DIFFICULTY_LEVELS
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import SessionProgress, UserProgress, QuestionRecord, UserSession
from .serializers import QuestionRequestSerializer
import uuid

User = get_user_model()

class QuestionAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QuestionRequestSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        session_id = request.data.get('session_id')
        
        try:
            session = UserSession.objects.get(
                session_id=session_id,
                user=request.user,
                is_active=True
            )
            
            session_progress = SessionProgress.objects.get(
                session=session,
                subject=data['subject']
            )
            
            question_data = self._generate_question(data, session_progress)
            new_question_id = uuid.uuid4()
            
            QuestionRecord.objects.create(
                user=request.user,
                session=session,
                question_id=new_question_id,
                question_text=question_data['question_text'],
                options=question_data['options'],
                correct_answer=question_data['correct_answer'],
                subject=data['subject'],
                topic=session_progress.current_topic,
                level=session_progress.current_level
            )
            
            self._update_progress(session_progress)
            
            return Response({
                'question': question_data['question_text'],
                'options': question_data['options'],
                'hint': question_data['hint'],
                'explanation': question_data['explanation'],
                'question_id': str(new_question_id),
                'progress': self._progress_status(session_progress)
            })
            
        except UserSession.DoesNotExist:
            return Response({'error': 'Invalid session'}, status=status.HTTP_400_BAD_REQUEST)
        except SessionProgress.DoesNotExist:
            return Response({'error': 'Subject not started in this session'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _generate_question(self, data, progress):
        generator = QuestionGenerator()
        return generator.generate_question(
            grade=data['grade'],
            subject=data['subject'],
            topic=progress.current_topic,
            level=progress.current_level
        )

    def _update_progress(self, progress):
        # Only check progression if current streak reaches 5
        if progress.current_streak >= 5:
            current_level_index = DIFFICULTY_LEVELS.index(progress.current_level)
            
            if current_level_index < len(DIFFICULTY_LEVELS) - 1:
                # Move to next difficulty level
                progress.current_level = DIFFICULTY_LEVELS[current_level_index + 1]
                progress.current_streak = 0  # Reset streak for new level
            else:
                # Completed all levels - mark topic complete
                if progress.current_topic not in progress.completed_topics:
                    progress.completed_topics.append(progress.current_topic)
                
                # Get next topic from curriculum
                grade_config = GRADE_SUBJECT_CONFIG[progress.session.user.grade]
                subject_config = grade_config[progress.subject]
                current_topics = subject_config["topics"]
                
                try:
                    current_index = current_topics.index(progress.current_topic)
                    next_topic = current_topics[current_index + 1] if current_index + 1 < len(current_topics) else None
                except ValueError:
                    next_topic = current_topics[0] if current_topics else None
                
                if next_topic:
                    progress.current_topic = next_topic
                    progress.current_level = DIFFICULTY_LEVELS[0]  # Reset to first level
                    progress.current_streak = 0  # Reset streak for new topic
                else:
                    progress.current_topic = "All topics completed"

            progress.save()
            
            # Update user progress
            user_progress = UserProgress.objects.get(
                user=progress.session.user,
                grade=progress.session.user.grade,
                subject=progress.subject
            )
            user_progress.current_topic = progress.current_topic
            user_progress.current_level = progress.current_level
            user_progress.completed_topics = progress.completed_topics.copy()
            user_progress.save()

    def _progress_status(self, progress):
        return {
            'current_topic': progress.current_topic,
            'current_level': progress.current_level,
            'current_streak': progress.current_streak,
            'max_streak': progress.max_streak,
            'completed_topics': progress.completed_topics,
            'session_id': str(progress.session.session_id)
        }

class RevisionQuestionAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RevisionQuestionRequestSerializer(
            data=request.data,
            context={'request': request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        session_id = data['session_id']
        subject = data['subject']

        try:
            # Verify session
            session = UserSession.objects.get(
                session_id=session_id,
                user=request.user,
                is_active=True
            )

            # Get user progress
            user_progress = UserProgress.objects.get(
                user=request.user,
                grade=request.user.grade,
                subject=subject
            )

            # Select random completed topic
            topic = random.choice(user_progress.completed_topics)

            # Select random difficulty level
            level = random.choice(DIFFICULTY_LEVELS)

            # Generate question
            question = self._generate_revision_question(
                request.user.grade,
                subject,
                topic,
                level
            )

            return Response({
                'question': question['question_text'],
                'options': question['options'],
                'hint': question['hint'],
                'explanation': question['explanation'],
                'metadata': {
                    'type': 'revision',
                    'topic': topic,
                    'level': level
                }
            })

        except UserSession.DoesNotExist:
            return Response({'error': 'Invalid session'}, status=status.HTTP_400_BAD_REQUEST)
        except UserProgress.DoesNotExist:
            return Response({'error': 'Progress not found'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _generate_revision_question(self, grade, subject, topic, level):
        generator = QuestionGenerator()
        return generator.generate_question(
            grade=grade,
            subject=subject,
            topic=topic,
            level=level
        )


class SubmitAnswerAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubmitAnswerSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            question = QuestionRecord.objects.get(
                question_id=data['question_id'],
                user=request.user,
                user_answer__isnull=True
            )
        except QuestionRecord.DoesNotExist:
            return Response({'error': 'Invalid or already answered question'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        is_correct = (data['user_answer'] == question.correct_answer)
        question.user_answer = data['user_answer']
        question.is_correct = is_correct
        question.save()

        # Update session progress
        session_progress = SessionProgress.objects.get(
            session=question.session,
            subject=question.subject
        )
        
        if is_correct:
            session_progress.correct_answers += 1
            session_progress.current_streak += 1
            if session_progress.current_streak > session_progress.max_streak:
                session_progress.max_streak = session_progress.current_streak
        else:
            session_progress.incorrect_answers += 1
            session_progress.current_streak = 0  # Reset streak on wrong answer

        session_progress.save()

        # Update user progress
        user_progress = UserProgress.objects.get(
            user=request.user,
            grade=request.user.grade,
            subject=question.subject
        )
        
        if is_correct:
            user_progress.total_correct += 1
            user_progress.current_streak += 1
            if user_progress.current_streak > user_progress.max_streak:
                user_progress.max_streak = user_progress.current_streak
        else:
            user_progress.total_incorrect += 1
            user_progress.current_streak = 0  # Reset streak

        user_progress.save()

        return Response({
            'is_correct': is_correct,
            'correct_answer': question.correct_answer,
            'current_streak': session_progress.current_streak,
            'max_streak': session_progress.max_streak,
            'session_stats': {
                'correct': session_progress.correct_answers,
                'incorrect': session_progress.incorrect_answers
            },
            'total_stats': {
                'correct': user_progress.total_correct,
                'incorrect': user_progress.total_incorrect
            }
        })

    def _check_progression(self, progress):
        from quiz.config.curriculum import GRADE_SUBJECT_CONFIG

        total_answered = progress.correct_answers + progress.incorrect_answers

        if total_answered % 5 == 0:
            next_level = progress.get_next_level()
            if next_level:
                progress.current_level = next_level
            else:
                if progress.current_topic not in progress.completed_topics:
                    progress.completed_topics.append(progress.current_topic)
                topics = GRADE_SUBJECT_CONFIG[progress.session.user.grade][progress.subject]["topics"]
                try:
                    current_index = topics.index(progress.current_topic)
                    next_topic = topics[current_index +
                                        1] if current_index + 1 < len(topics) else None

                except ValueError:
                    next_topic = topics[0] if topics else None
                if next_topic:
                    progress.current_topic = next_topic
                    progress.current_level = DIFFICULTY_LEVELS[0]
                else:
                    progress.current_topic = "All topics completed"
                    progress.current_topic = topics[current_index + 1]
            progress.save()
            user_progress = UserProgress.objects.get(
                user=progress.session.user,
                grade=progress.session.user.grade,
                subject=progress.subject
            )
            user_progress.current_topic = progress.current_topic
            user_progress.current_level = progress.current_level
            user_progress.completed_topics = progress.completed_topics
            user_progress.save()
