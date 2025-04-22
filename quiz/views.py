
from django.contrib.auth import get_user_model
from .utils.generator import QuestionGenerator
from .config.curriculum import GRADE_SUBJECT_CONFIG, DIFFICULTY_LEVELS,SUBJECT_TOPICS
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from .models import CustomUser, UserSession, SessionProgress, UserProgress, QuestionRecord,UserTopicProgress
from .serializers import UserRegistrationSerializer, UserProfileSerializer, RevisionQuestionRequestSerializer, SubmitAnswerSerializer, QuestionRequestSerializer,TopicIntroductionSerializer,TopicQuestionRequestSerializer
from django.utils import timezone
from django.db.utils import IntegrityError
import random
import uuid
import json
import re


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

                SessionProgress.objects.create(
                    session=new_session,
                    subject=subject,
                    current_topic=user_progress.current_topic,
                    current_level=user_progress.current_level,
                    correct_answers=0,
                    incorrect_answers=0,
                    completed_topics=user_progress.completed_topics.copy()
                )

            # Calculate comprehensive user statistics
            user_stats = self._calculate_user_stats(user)
            
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'account_id': user.account_id,
                'session_id': str(new_session.session_id),
                'user': UserProfileSerializer(user).data,
                'user_stats': user_stats
            })
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    def _calculate_user_stats(self, user):
        from django.db.models import Count, Case, When, IntegerField

        # Get statistics from all answered questions
        topic_stats = QuestionRecord.objects.filter(user=user).values(
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
            
            question_data = self._generate_question(request.user,data, session_progress)
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

    def _generate_question(self, user, data, progress):
        generator = QuestionGenerator()
        return generator.generate_question(
            user=user,
            grade=data['grade'],
            subject=data['subject'],
            topic=progress.current_topic,
            level=progress.current_level
        )

    def _update_progress(self, progress):
        if progress.current_streak >= 5:
            current_level_index = DIFFICULTY_LEVELS.index(progress.current_level)
            
            if current_level_index < len(DIFFICULTY_LEVELS) - 1:
                # Progress to next level
                progress.current_level = DIFFICULTY_LEVELS[current_level_index + 1]
                progress.current_streak = 0
            else:
                if progress.is_custom_topic:
                    # Reset streak but stay on same level for custom topics
                    progress.current_streak = 0
                else:
                    # Original topic progression logic
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
            
            # Update user progress only for non-custom topics
            if not progress.is_custom_topic:
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

            generator = QuestionGenerator()
            question = generator.generate_question(
                user=request.user,
                grade=request.user.grade,
                subject=subject,
                topic=topic,
                level=level,
                revision=True
            )

            # Create question record for validation
            new_question_id = uuid.uuid4()
            QuestionRecord.objects.create(
                user=request.user,
                session=session,
                question_id=new_question_id,
                question_text=question['question_text'],
                options=question['options'],
                correct_answer=question['correct_answer'],
                subject=subject,
                topic=topic,
                level=level
            )

            return Response({
                'question': question['question_text'],
                'options': question['options'],
                'hint': question['hint'],
                'explanation': question['explanation'],
                'question_id': str(new_question_id),
                'metadata': {
                    'type': 'revision',
                    'topic': topic,
                    'level': level
                }
            })

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

        # Remove any residual labels from user answer
        user_answer = re.sub(r'^[A-D][).\s]*', '', user_answer).strip()
        
        is_correct = user_answer == correct_answer

        # Update question record
        question.user_answer = user_answer
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
        
        # New: Update topic progress
        topic_progress = UserTopicProgress.objects.get(
            user=request.user,
            subject=question.subject,
            topic=question.topic
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

        return Response({
            'is_correct': is_correct,
            'correct_answer': question.correct_answer,
            'user_answer': user_answer,
            'current_streak': session_progress.current_streak,
            'max_streak': session_progress.max_streak,
            'session_stats': {
                'correct': session_progress.correct_answers,
                'incorrect': session_progress.incorrect_answers
            },
            'total_stats': {
                'correct': user_progress.total_correct,
                'incorrect': user_progress.total_incorrect
            },
            'topic_stats': {
                'correct': topic_progress.correct,
                'incorrect': topic_progress.incorrect,
                'current_level': topic_progress.current_level
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
        if subject not in ["mathematics", "english"]:
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

        data = serializer.validated_data
        
        try:
            session = UserSession.objects.get(
                session_id=data['session_id'],
                user=request.user,
                is_active=True
            )
            
            # Get or create topic progress
            topic_progress, _ = UserTopicProgress.objects.get_or_create(
                user=request.user,
                subject=data['subject'],
                topic=data['topic'],
                defaults={'current_level': DIFFICULTY_LEVELS[0]}
            )

            # Generate question
            generator = QuestionGenerator()
            question = generator.generate_question(
                user=request.user,
                grade=request.user.grade,
                subject=data['subject'],
                topic=data['topic'],
                level=topic_progress.current_level
            )

            # Create question record
            new_question_id = uuid.uuid4()
            QuestionRecord.objects.create(
                user=request.user,
                session=session,
                question_id=new_question_id,
                question_text=question['question_text'],
                options=question['options'],
                correct_answer=question['correct_answer'],
                subject=data['subject'],
                topic=data['topic'],
                level=topic_progress.current_level
            )

            return Response({
                'question': question['question_text'],
                'options': question['options'],
                'hint': question['hint'],
                'explanation': question['explanation'],
                'question_id': str(new_question_id),
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