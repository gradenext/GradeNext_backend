
from django.contrib.auth import get_user_model
from .utils.generator import QuestionGenerator
from .config.curriculum import GRADE_SUBJECT_CONFIG, DIFFICULTY_LEVELS,SUBJECT_TOPICS
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from quiz.permissions import HasActiveSubscription
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from .models import CustomUser, UserSession, SessionProgress, UserProgress, QuestionRecord,UserTopicProgress,OTPVerification
from .serializers import UserRegistrationSerializer, UserProfileSerializer, RevisionQuestionRequestSerializer, SubmitAnswerSerializer, QuestionRequestSerializer,TopicIntroductionSerializer,TopicQuestionRequestSerializer,VerifyOTPSerializer, ForgotPasswordSerializer, ResetPasswordSerializer,CloudinaryImageUploadSerializer
from django.utils import timezone
from django.db.utils import IntegrityError
import random
import uuid
import json
import re
import logging
from .utils.coupons import validate_coupon
from .utils.email import send_otp_email
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .utils.generator import QuestionGenerator, SYSTEM_PROMPT
import cloudinary.uploader


logger = logging.getLogger(__name__)

User = get_user_model()

SESSION_PROMPT_CACHE = {}

@method_decorator(csrf_exempt, name='dispatch')
class RegisterAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data.copy()
        email = data['email']
        password = data.pop('password')
        data.pop('confirm_password', None)

        # handle coupon logic here...
        # coupon = validate_coupon(data.get('coupon_code'))
        # if coupon:
        #     data['plan'] = coupon.plan_type
        #     data['applied_coupon'] = coupon
        #     coupon.times_used += 1
        #     coupon.save()

        # generate and store OTP
        otp = f"{random.randint(100000, 999999):06d}"
        OTPVerification.objects.filter(email=email, purpose='registration').delete()
        OTPVerification.objects.create(
            email=email,
            otp=otp,
            purpose='registration',
            registration_data={'user_data': data, 'password': password}
        )

        # send OTP
        try:
            send_otp_email(email, otp, 'registration')
            return Response({'status': 'OTP sent', 'email': email}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'error': 'Failed to send OTP, please try again later.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class VerifyOTPAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp = serializer.validated_data['otp']

            try:
                otp_record = OTPVerification.objects.get(
                    email=email,
                    otp=otp,
                    purpose='registration',
                    is_verified=False
                )

                # Check if OTP expired
                if otp_record.is_expired():
                    return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)

                if not otp_record.registration_data:
                    return Response({'error': 'Registration data corrupted'}, status=400)

                # Mark OTP as verified
                otp_record.is_verified = True
                otp_record.save()

                # Retrieve user data from OTP record
                user_data = otp_record.registration_data['user_data']
                password = otp_record.registration_data['password']

                # Create the user
                try:
                    user = CustomUser.objects.create_user(
                        password=password,
                        **user_data
                    )
                    user.is_verified = True
                    user.save()

                    # Create token for the user
                    token, _ = Token.objects.get_or_create(user=user)

                    return Response({
                        'status': 'Account verified and created',
                        'email': user.email,
                        'token': token.key,
                        'account_id': user.account_id,
                        'user': UserProfileSerializer(user).data
                    }, status=status.HTTP_201_CREATED)

                except Exception as e:
                    return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

            except OTPVerification.DoesNotExist:
                return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class ForgotPasswordAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            try:
                user = CustomUser.objects.get(email=email)
                otp = str(random.randint(100000, 999999))
                
                # Create or update OTP record
                OTPVerification.objects.filter(email=email, purpose='password_reset').delete()
                OTPVerification.objects.create(
                    email=email,
                    otp=otp,
                    purpose='password_reset'
                )
                
                try:
                    send_otp_email(email, otp, 'password reset')
                    return Response({'status': 'OTP sent', 'email': email})
                except Exception as e:
                    logger.error(f"Failed to send OTP to {email}: {str(e)}")
                    # Clean up OTP record if sending fails
                    # OTPVerification.objects.filter(email=email, purpose='password_reset').delete()
                    return Response({'error': 'Failed to send OTP'}, status=500)
                
            except CustomUser.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
        return Response(serializer.errors, status=400)
@method_decorator(csrf_exempt, name='dispatch')
class ResetPasswordAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp = serializer.validated_data['otp']
            new_password = serializer.validated_data['new_password']
            
            try:
                otp_record = OTPVerification.objects.get(
                    email=email, 
                    otp=otp,
                    purpose='password_reset',
                    is_verified=False
                )
                
                if otp_record.is_expired():
                    return Response({'error': 'OTP expired'}, status=400)
                
                user = CustomUser.objects.get(email=email)
                user.set_password(new_password)
                user.save()
                
                otp_record.is_verified = True
                otp_record.save()
                
                return Response({'status': 'Password reset successful'})
                
            except OTPVerification.DoesNotExist:
                return Response({'error': 'Invalid OTP'}, status=400)
            except CustomUser.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
        return Response(serializer.errors, status=400)
@method_decorator(csrf_exempt, name='dispatch')
class LoginAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        print("incomming login data:", request.data)
        email = request.data.get('email')
        password = request.data.get('password')
        user = authenticate(email=email, password=password)

        if user:
            if not user.is_verified:
                return Response({'error': 'Account not verified. Check your email for verification OTP'},
                              status=status.HTTP_401_UNAUTHORIZED)
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'account_id': user.account_id,
            }, status=status.HTTP_200_OK)
            
        return Response({'error': 'Invalid credentials'}, 
                      status=status.HTTP_401_UNAUTHORIZED)

    

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

class SessionAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Create a new learning session
        Returns: {
            "session_id": "uuid",
            "expires_at": "iso8601",
            "subjects": ["mathematics", "english","science","programming"]
        }
        """
        try:
            user = request.user
            
            # Close any existing active sessions
            UserSession.objects.filter(user=user, is_active=True).update(
                is_active=False, 
            )

            # Create new session
            new_session = UserSession.objects.create(user=user)

            # Initialize progress for each enrolled subject
            initialized_subjects = []
            for subject in user.courses:
                # Get or create user progress
                if subject not in GRADE_SUBJECT_CONFIG.get(user.grade, {}):
                    logger.warning(f"Subject '{subject}' is not available for grade {user.grade}")
                    continue 
                user_progress, created = UserProgress.objects.get_or_create(
                    user=user,
                    grade=user.grade,
                    subject=subject,
                    defaults={
                        'current_topic': GRADE_SUBJECT_CONFIG[user.grade][subject]["topics"][0],
                        'completed_topics': [],
                        'current_level': DIFFICULTY_LEVELS[0]
                    }
                )

                # Create session progress
                SessionProgress.objects.create(
                    session=new_session,
                    subject=subject,
                    current_topic=user_progress.current_topic,
                    current_level=user_progress.current_level,
                    correct_answers=0,
                    incorrect_answers=0,
                    completed_topics=user_progress.completed_topics.copy()
                )
                initialized_subjects.append(subject)
                
            SESSION_PROMPT_CACHE[str(new_session.session_id)] = SYSTEM_PROMPT
            if SYSTEM_PROMPT:
                logger.info(f"Storing system prompt in SESSION_PROMPT_CACHE for session {new_session.session_id}")
            else:
                logger.warning("SYSTEM_PROMPT is not set, using default prompt")

            return Response({
                'session_id': str(new_session.session_id),
                'subjects': initialized_subjects
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Session creation failed: {str(e)}")
            return Response({'error': 'Session creation failed'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ExpireSessionAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        """
        Expire a specific session
        """
        try:
            session_id_str = str(session_id)
            session = UserSession.objects.get(
                session_id=session_id,
                user=request.user,
                is_active=True
            )
            
            session.is_active = False
            session.end_time = timezone.now()
            session.save()
            
            # Update user progress from session progress
            for progress in session.progresses.all():
                UserProgress.objects.filter(
                    user=request.user,
                    grade=request.user.grade,
                    subject=progress.subject
                ).update(
                    current_topic=progress.current_topic,
                    current_level=progress.current_level,
                    completed_topics=progress.completed_topics
                )
                
            if session_id_str in SESSION_PROMPT_CACHE:
                del SESSION_PROMPT_CACHE[session_id_str]

            return Response({'status': 'session expired'}, 
                          status=status.HTTP_200_OK)
            
        except UserSession.DoesNotExist:
            return Response({'error': 'Session not found'}, 
                          status=status.HTTP_404_NOT_FOUND)

class UserProfileAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserProfileSerializer(user)
        user_stats = self._calculate_user_stats(user)
        return Response({
            'user': serializer.data,
            'user_stats': user_stats
        })

    def _calculate_user_stats(self, user):
        from django.db.models import Count, Case, When, IntegerField

        # Get statistics from all answered questions
        topic_stats = QuestionRecord.objects.filter(
            user=user,
            user_answer__isnull=False  # Only include answered questions
        ).values(

            'subject', 'topic'
        ).annotate(
            correct=Count(
                Case(
                    When(is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
            incorrect=Count(
                Case(
                    When(is_correct=False, then=1), 
                    output_field=IntegerField()
                )
            )
        )

        # Convert to nested dictionary {subject: {topic: stats}}
        stats_dict = {}
        for stat in topic_stats:
            subject = stat['subject']
            topic_key = stat['topic']
            stats_dict.setdefault(subject, {})[topic_key] = {
                'correct': stat['correct'],
                'incorrect': stat['incorrect'],
                'total': stat['correct'] + stat['incorrect']
            }

        # Get user's topic progression data
        user_topics = UserTopicProgress.objects.filter(user=user)
        user_topics_dict = {
            (ut.subject, ut.topic): ut for ut in user_topics
        }

        # Get user progresses for current grade
        user_progresses = UserProgress.objects.filter(user=user, grade=user.grade)
        
        # Build subject-wise statistics
        subjects = {}
        overall = {'correct': 0, 'incorrect': 0, 'total': 0}
        
        for progress in user_progresses:
            subject = progress.subject
            grade_config = GRADE_SUBJECT_CONFIG.get(user.grade, {})
            subject_config = grade_config.get(subject, {})
            display_names = subject_config.get("display_names", {})
            curriculum_topics = subject_config.get("topics", [])
            
            # Initialize subject entry
            subjects[subject] = {
                'total': 0,
                'correct': 0,
                'incorrect': 0,
                'topics': []
            }

            # Process all curriculum topics
            for topic_key in curriculum_topics:
                topic_name = display_names.get(topic_key, topic_key)
                stats = stats_dict.get(subject, {}).get(topic_key, {
                    'correct': 0,
                    'incorrect': 0,
                    'total': 0
                })
                
                # Get topic progress if exists
                ut_progress = user_topics_dict.get((subject, topic_key), None)
                current_level = ut_progress.current_level if ut_progress else None
                
                # Build topic entry
                topic_entry = {
                    'topic': topic_name,
                    'correct': stats['correct'],
                    'incorrect': stats['incorrect'],
                    'total': stats['total'],
                    'current_level': current_level
                }
                
                subjects[subject]['topics'].append(topic_entry)
                
                # Update subject totals
                subjects[subject]['correct'] += stats['correct']
                subjects[subject]['incorrect'] += stats['incorrect']
                subjects[subject]['total'] += stats['total']
            
            # Update overall totals
            overall['correct'] += subjects[subject]['correct']
            overall['incorrect'] += subjects[subject]['incorrect']
            overall['total'] += subjects[subject]['total']

        return {
            'overall': {
                'total': overall['total'],
                'correct': overall['correct'],
                'incorrect': overall['incorrect']
            },
            'subjects': subjects
        }

class QuestionAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QuestionRequestSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if request.user.plan not in ['trial','basic', 'pro', 'enterprise']:
            return Response({'error': 'No active plan'}, status=403)

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
            
            system_prompt = SESSION_PROMPT_CACHE.get(str(session_id))
            if system_prompt:
                logger.info(f"Using cached system prompt for session {session_id}")
            else:
                logger.info(f"No cached prompt found. Using default SYSTEM_PROMPT")
                system_prompt = SYSTEM_PROMPT
                SESSION_PROMPT_CACHE[str(session_id)] = system_prompt

            questions = self._generate_batch(request.user, data, session_progress, system_prompt)
            response_payload = []

            for question_data in questions:
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
                    level=session_progress.current_level,
                    question_type='regular',
                )

                response_payload.append({
                    'question': question_data['question_text'],
                    'options': question_data['options'],
                    'hint': question_data['hint'],
                    'explanation': question_data['explanation'],
                    'image_generated': question_data.get('image_generated', False),
                    'image_url': question_data.get('image_url'),
                    'question_id': str(new_question_id),
                    'question_type': question_data['question_type'],
                    'current_topic': session_progress.current_topic,
                    'current_level': session_progress.current_level,
                })

            self._update_progress(session_progress)
            
            print(f"Generated {len(response_payload)} questions for session {session_id}")
            print("response_payload:", response_payload)

            return Response({
                'questions': response_payload,
                'progress': self._progress_status(session_progress)
            })


        except UserSession.DoesNotExist:
            return Response({'error': 'Invalid session'}, status=status.HTTP_400_BAD_REQUEST)
        except SessionProgress.DoesNotExist:
            return Response({'error': 'Subject not started in this session'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # def _generate_question(self, user, data, progress,system_prompt):
    #     generator = QuestionGenerator()
    #     return generator.generate_question(
    #         user=user,
    #         grade=data['grade'],
    #         subject=data['subject'],
    #         topic=progress.current_topic,
    #         level=progress.current_level,
    #         system_prompt=system_prompt
    #     )
    
    def _generate_batch(self, user, data, progress, system_prompt):
        generator = QuestionGenerator()
        return generator.generate_batch_questions(
            user=user,
            grade=data['grade'],
            subject=data['subject'],
            topic=progress.current_topic,
            level=progress.current_level,
            system_prompt=system_prompt
        )


    def _update_progress(self, progress):
        if progress.current_streak >= 5:
            current_level_index = DIFFICULTY_LEVELS.index(progress.current_level)
            if current_level_index < len(DIFFICULTY_LEVELS) - 1:
                progress.current_level = DIFFICULTY_LEVELS[current_level_index + 1]
                progress.current_streak = 0
            else:
                if progress.current_topic not in progress.completed_topics:
                    progress.completed_topics.append(progress.current_topic)

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
                    progress.current_level = DIFFICULTY_LEVELS[0]
                    progress.current_streak = 0
                else:
                    progress.current_topic = "All topics completed"

            progress.save()

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

# class RevisionQuestionAPI(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         serializer = RevisionQuestionRequestSerializer(
#             data=request.data,
#             context={'request': request}
#         )
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         if request.user.plan not in ['pro', 'enterprise']:
#             return Response({'error': 'Pro plan required for revisions'}, status=403)

#         data = serializer.validated_data
#         session_id = data['session_id']
#         subject = data['subject']

#         try:
#             session = UserSession.objects.get(
#                 session_id=session_id,
#                 user=request.user,
#                 is_active=True
#             )

#             user_progress = UserProgress.objects.get(
#                 user=request.user,
#                 grade=request.user.grade,
#                 subject=subject
#             )

#             topic = random.choice(user_progress.completed_topics)
#             level = random.choice(DIFFICULTY_LEVELS)

#             generator = QuestionGenerator()
#             question = generator.generate_question(
#                 user=request.user,
#                 grade=request.user.grade,
#                 subject=subject,
#                 topic=topic,
#                 level=level,
#                 revision=True
#             )

#             # Create question record for validation
#             new_question_id = uuid.uuid4()
#             QuestionRecord.objects.create(
#                 user=request.user,
#                 session=session,
#                 question_id=new_question_id,
#                 question_text=question['question_text'],
#                 options=question['options'],
#                 correct_answer=question['correct_answer'],
#                 subject=subject,
#                 topic=topic,
#                 level=level
#             )

#             return Response({
#                 'question': question['question_text'],
#                 'options': question['options'],
#                 'hint': question['hint'],
#                 'explanation': question['explanation'],
#                 'question_id': str(new_question_id),
#                 'image_generated': question.get('image_generated', False),
#                 'image_url': question.get('image_url'),
#                 'question_type': question['question_type'],
#                 'metadata': {
#                     'type': 'revision',
#                     'topic': topic,
#                     'level': level
#                 }
#             })

#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RevisionQuestionAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RevisionQuestionRequestSerializer(
            data=request.data,
            context={'request': request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        if request.user.plan not in ['trial','pro', 'enterprise']:
            return Response({'error': 'Pro plan required for revisions'}, status=403)

        data = serializer.validated_data
        session_id = data['session_id']
        subject = data['subject']

        try:
            session = UserSession.objects.get(
                session_id=session_id,
                user=request.user,
                is_active=True
            )

            user_progress = UserProgress.objects.get(
                user=request.user,
                grade=request.user.grade,
                subject=subject
            )

            topic = random.choice(user_progress.completed_topics)
            level = random.choice(DIFFICULTY_LEVELS)

            # Get system prompt
            system_prompt = SESSION_PROMPT_CACHE.get(str(session_id))
            if system_prompt:
                logger.info(f"Using cached system prompt for session {session_id}")
            else:
                logger.info(f"No cached prompt found. Using default SYSTEM_PROMPT")
                system_prompt = SYSTEM_PROMPT
                SESSION_PROMPT_CACHE[str(session_id)] = system_prompt

            # Batch generate up to 10 revision questions
            generator = QuestionGenerator()
            questions = generator.generate_batch_questions(
                user=request.user,
                grade=request.user.grade,
                subject=subject,
                topic=topic,
                level=level,
                revision=True,
                system_prompt=system_prompt
            )

            if not questions:
                return Response({'error': 'Failed to generate questions'}, status=500)

            # Take the first question for response
            selected = questions[0]
            question_id = uuid.uuid4()

            # Save to DB
            QuestionRecord.objects.create(
                user=request.user,
                session=session,
                question_id=question_id,
                question_text=selected['question_text'],
                options=selected['options'],
                correct_answer=selected['correct_answer'],
                subject=subject,
                topic=topic,
                level=level,
                question_type='revision'
            )

            return Response({
                'question': selected['question_text'],
                'options': selected['options'],
                'hint': selected['hint'],
                'explanation': selected['explanation'],
                'question_id': str(question_id),
                'image_generated': selected.get('image_generated', False),
                'image_url': selected.get('image_url'),
                'question_type': selected['question_type'],
                'metadata': {
                    'type': 'revision',
                    'topic': topic,
                    'level': level
                }
            })

        except UserSession.DoesNotExist:
            return Response({'error': 'Invalid session'}, status=400)
        except UserProgress.DoesNotExist:
            return Response({'error': 'User progress not found'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# quiz/views.py (update SubmitAnswerAPI)
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

        # Normalize answers
        user_answer = str(data['user_answer']).strip()
        correct_answer = str(question.correct_answer).strip()
        is_correct = user_answer == correct_answer

        # Update question record
        question.user_answer = user_answer
        question.is_correct = is_correct
        question.save()

        # Handle different question types
        if question.question_type == 'topic_practice':
            return self._handle_topic_practice(question, is_correct)
        else:
            return self._handle_regular_progress(question, is_correct)

    def _handle_regular_progress(self, question, is_correct):
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
            session_progress.current_streak = 0

        session_progress.save()

        # Update user progress
        user_progress = UserProgress.objects.get(
            user=question.user,
            grade=question.user.grade,
            subject=question.subject
        )
        
        if is_correct:
            user_progress.total_correct += 1
            user_progress.current_streak += 1
            if user_progress.current_streak > user_progress.max_streak:
                user_progress.max_streak = user_progress.current_streak
        else:
            user_progress.total_incorrect += 1
            user_progress.current_streak = 0

        user_progress.save()

        return Response({
            'is_correct': is_correct,
            'correct_answer': question.correct_answer,
            'user_answer': question.user_answer,
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

    def _handle_topic_practice(self, question, is_correct):
        # Update topic progress
        topic_progress, _ = UserTopicProgress.objects.get_or_create(
            user=question.user,
            subject=question.subject,
            topic=question.topic,
            defaults={
                'correct': 0,
                'incorrect': 0,
                'current_level': DIFFICULTY_LEVELS[0]
            }
        )

        if is_correct:
            topic_progress.correct += 1
        else:
            topic_progress.incorrect += 1

        # Handle level progression for topic practice
        if is_correct and (topic_progress.correct + topic_progress.incorrect) % 5 == 0:
            current_idx = DIFFICULTY_LEVELS.index(topic_progress.current_level)
            if current_idx < len(DIFFICULTY_LEVELS) - 1:
                topic_progress.current_level = DIFFICULTY_LEVELS[current_idx + 1]
        
        topic_progress.save()

        # Get or create session progress for the subject
        session_progress, _ = SessionProgress.objects.get_or_create(
            session=question.session,
            subject=question.subject,
            defaults={
                'current_topic': question.topic,
                'current_level': DIFFICULTY_LEVELS[0],
                'correct_answers': 0,
                'incorrect_answers': 0,
                'completed_topics': []
            }
        )

        # Update session stats
        if is_correct:
            session_progress.correct_answers += 1
        else:
            session_progress.incorrect_answers += 1
        session_progress.save()

        return Response({
            'is_correct': is_correct,
            'correct_answer': question.correct_answer,
            'user_answer': question.user_answer,
            'topic_stats': {
                'correct': topic_progress.correct,
                'incorrect': topic_progress.incorrect,
                'current_level': topic_progress.current_level
            },
            'session_stats': {
                'correct': session_progress.correct_answers,
                'incorrect': session_progress.incorrect_answers
            }
        })


# Add to views.py
# Modified view in views.py
class TopicIntroductionAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TopicIntroductionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        subject = serializer.validated_data['subject']

        try:
            # Get user's current progress
            user_progress = UserProgress.objects.get(
                user=user,
                grade=user.grade,
                subject=subject
            )
            current_topic = user_progress.current_topic
            
            # Get curriculum data
            display_name = GRADE_SUBJECT_CONFIG[user.grade][subject]["display_names"][current_topic]

            # Generate content
            generator = QuestionGenerator()
            prompt = f"""Create a lesson summary for {display_name} (Grade {user.grade} {subject}) with:
            
            1. **Introduction**: Two distinct paragraphs (total 100 words) explaining:
               - First paragraph: Main concept and importance
               - Second paragraph: Practical applications
            2. **Key Concepts**: 5-7 fundamental principles as bullet points
            3. **Solved Examples**: 3 problems with step-by-step solutions

            Format requirements:
            - Use simple language suitable for students
            - Introduction must be 100 words 3 lines long mas
            - Return JSON with fields: introduction, key_concepts, examples
            - Example response format:
              {{
                "introduction": [
                    "First paragraph text...",
                    "Second paragraph text..."
                ],
                "key_concepts": [
                    "Concept 1...",
                    "Concept 2..."
                ],
                "examples": [
                    "Example 1...",
                    "Example 2..."
                ]
              }}
            """
            
            response = generator.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            
            content = json.loads(response.choices[0].message.content)
            
            # Validate response structure
            if not all(key in content for key in ['introduction', 'key_concepts', 'examples']):
                raise ValueError("Invalid response structure from OpenAI")

            # Ensure introduction is exactly 2 paragraphs
            if len(content['introduction']) != 2:
                content['introduction'] = self._split_paragraphs(content['introduction'])

            return Response(content)

        except UserProgress.DoesNotExist:
            return Response({'error': 'Progress not found - start a session first'}, 
                          status=status.HTTP_404_NOT_FOUND)
        except KeyError as e:
            return Response({'error': f'Missing key in response: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _split_paragraphs(self, text):
        """Fallback method to split text into two paragraphs"""
        sentences = text.split('. ')
        mid_point = len(sentences) // 2
        return [
            '. '.join(sentences[:mid_point]) + '.',
            '. '.join(sentences[mid_point:]) + '.'
        ]
        
class SubjectTopicsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, subject):
        if subject not in ["mathematics", "english", "science","programming"]:
            return Response({"error": "Invalid subject"}, status=400)

        try:
            grade_config = GRADE_SUBJECT_CONFIG[request.user.grade][subject]
            topics = grade_config["topics"]
            display_names = grade_config["display_names"]
            
            return Response([{
                "topic_key": topic,
                "topic_name": display_names.get(topic, topic)
            } for topic in topics])
            
        except KeyError:
            return Response({"error": "Subject not available for this grade"}, status=400)

# class SelectTopicAPI(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         serializer = TopicSelectionSerializer(data=request.data, context={'request': request})
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=400)

#         try:
#             session = UserSession.objects.get(user=request.user, is_active=True)
#             subject = serializer.validated_data['subject']
#             topic = serializer.validated_data['topic']
            
#             progress, _ = SessionProgress.objects.update_or_create(
#                 session=session,
#                 subject=subject,
#                 defaults={
#                     'current_topic': topic,
#                     'current_level': DIFFICULTY_LEVELS[0],
#                     'is_custom_topic': True,
#                     'current_streak': 0
#                 }
#             )
            
#             return Response({
#                 "status": f"Topic {topic} selected for {subject}",
#                 "current_level": progress.current_level,
#                 "current_streak": progress.current_streak
#             })
            
#         except UserSession.DoesNotExist:
#             return Response({"error": "No active session"}, status=400)
        
class TopicQuestionAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TopicQuestionRequestSerializer(
            data=request.data,
            context={'request': request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if request.user.plan not in ['enterprise', 'trial']:
            return Response({'error': 'Enterprise or Trial plan required for topic practice'}, status=403)


        data = serializer.validated_data

        try:
            session = UserSession.objects.get(
                session_id=data['session_id'],
                user=request.user,
                is_active=True
            )

            # Ensure session progress exists for this subject
            SessionProgress.objects.get_or_create(
                session=session,
                subject=data['subject'],
                defaults={
                    'current_topic': data['topic'],
                    'current_level': DIFFICULTY_LEVELS[0],
                    'correct_answers': 0,
                    'incorrect_answers': 0,
                    'completed_topics': []
                }
            )

            topic_progress, _ = UserTopicProgress.objects.get_or_create(
                user=request.user,
                subject=data['subject'],
                topic=data['topic'],
                defaults={'current_level': DIFFICULTY_LEVELS[0]}
            )

            # Get system prompt if cached
            session_id = str(data['session_id'])
            system_prompt = SESSION_PROMPT_CACHE.get(session_id)
            
            if system_prompt:
                logger.info(f"Using cached system prompt for session {session_id}")
            else:
                logger.info(f"No cached prompt found for session {session_id}, using default SYSTEM_PROMPT")
                system_prompt = SYSTEM_PROMPT
                SESSION_PROMPT_CACHE[session_id] = system_prompt

            # Generate batch of questions
            generator = QuestionGenerator()
            questions = generator.generate_batch_questions(
                user=request.user,
                grade=request.user.grade,
                subject=data['subject'],
                topic=data['topic'],
                level=topic_progress.current_level,
                system_prompt=system_prompt
            )

            response_questions = []

            for question in questions:
                new_question_id = uuid.uuid4()

                # Save each question to DB
                QuestionRecord.objects.create(
                    user=request.user,
                    session=session,
                    question_id=new_question_id,
                    question_text=question['question_text'],
                    options=question['options'],
                    correct_answer=question['correct_answer'],
                    subject=data['subject'],
                    topic=data['topic'],
                    level=topic_progress.current_level,
                    question_type='topic_practice',
                )

                response_questions.append({
                    'question': question['question_text'],
                    'options': question['options'],
                    'hint': question['hint'],
                    'explanation': question['explanation'],
                    'image_generated': question.get('image_generated', False),
                    'image_url': question.get('image_url'),
                    'question_id': str(new_question_id),
                    'question_type': question['question_type'],
                })

            return Response({
                'questions': response_questions,
                'metadata': {
                        'type': 'topic_practice',
                        'topic': data['topic'],
                        'current_level': topic_progress.current_level,
                        'current_streak': 0  # Not used in topic practice
                    }
            })

        except UserSession.DoesNotExist:
            return Response({'error': 'Invalid session'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


# Cognitory upload image API
class ImageUploadAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CloudinaryImageUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        images = serializer.validated_data['images']
        uploaded_urls = []
        upload_id = str(uuid.uuid4())

        try:
            for img in images:
                result = cloudinary.uploader.upload(img, folder=f"quiz_uploads/{upload_id}/")
                uploaded_urls.append(result["secure_url"])

            return Response({
                "image_id": upload_id,
                "image_urls": uploaded_urls
            }, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)