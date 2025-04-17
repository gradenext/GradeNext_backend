# utils/generator.py
import openai
import json
import re
import random
import logging
from django.conf import settings
from quiz.config.curriculum import SUBJECT_TOPICS
from .cache import QuestionCache
from quiz.models import UserQuestionHistory
from django.utils import timezone
logger = logging.getLogger(__name__)

class QuestionGenerator:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.max_retries = 5
        self.required_fields = ['questionText', 'options', 'correctAnswer', 'hint', 'explanation']

    def generate_question(self, user, grade, subject, topic, level, revision=False):
        cache_key = QuestionCache.generate_key(grade, subject, topic, level, revision)
        seen_questions = set(UserQuestionHistory.objects.filter(user=user)
                           .values_list('question_signature', flat=True))

        for attempt in range(self.max_retries):
            try:
                # Try cache first with freshness check
                cached = [q for q in QuestionCache.get(cache_key)
                         if QuestionCache.generate_signature(q) not in seen_questions]
                
                if cached and random.random() < 0.7:  # 70% cache utilization
                    question = random.choice(cached)
                    QuestionCache.add(cache_key, question)  # Refresh cache position
                    self._record_question(user, question)
                    return question

                # Generate new question through GPT
                prompt = self._build_prompt(grade, subject, topic, level, revision, seen_questions)
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }],
                    temperature=0.8 if revision else 0.6,
                    max_tokens=1024,
                    response_format={"type": "json_object"}
                )

                raw_question = json.loads(response.choices[0].message.content)
                question = self._validate_and_format(raw_question, grade, subject, topic, level)
                
                if QuestionCache.generate_signature(question) in seen_questions:
                    raise ValueError("Duplicate question generated")

                QuestionCache.add(cache_key, question)
                self._record_question(user, question)
                return question

            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error on attempt {attempt+1}: {str(e)}")
                continue
            except KeyError as e:
                logger.warning(f"Missing key in response: {str(e)}")
                continue
            except ValueError as e:
                logger.warning(f"Validation error: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"GPT API error: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise RuntimeError("Failed to generate valid question after multiple attempts")
                continue

        raise RuntimeError("Exhausted all generation attempts")

    def _build_prompt(self, grade, subject, topic, level, revision, seen_hashes):
        subtopics = random.sample(SUBJECT_TOPICS[subject][topic], 3)
        return f"""Generate a unique {level} difficulty {subject} question for grade {grade} students in JSON format.
    Topic: {topic}
    Subtopics: {', '.join(subtopics)}

    Requirements (JSON FORMAT REQUIRED):
    - Return valid JSON with fields: questionText, options, correctAnswer, hint, explanation
    - Include 4 distinct options with values (not letters)
    - correctAnswer must be the exact text of the correct option
    - explanation should be a brief explanation of the correct answer
    - hint should be a short clue to help the student
    - Avoid using letter labels (A-D) in options or correctAnswer
    - Avoid the question relating to any containing any diagrams or images
    - Use a simple and clear language suitable for the grade level
    - Ensure the question is educational and relevant to the topic
    
    - Example JSON response:
    {{
        "questionText": "What is 15 - 7?",
        "options": ["8", "9", "7", "10"],
        "correctAnswer": "8",
        "hint": "Subtract carefully",
        "explanation": "15 - 7 = 8"
    }}

    Important: Do NOT use letter labels (A-D) in options or correctAnswer. Format as JSON."""
    
    
    def _validate_and_format(self, question, grade, subject, topic, level):
        # Structural validation
        if not all(key in question for key in self.required_fields):
            raise ValueError("Missing required fields in generated question")
        
        if len(question['options']) != 4:
            raise ValueError("Exactly 4 options required")

        # Validate option content
        clean_options = []
        for opt in question['options']:
            # Remove existing labels and whitespace
            clean_opt = re.sub(r'^[A-D][):.]?\s*', '', str(opt)).strip()
            
            # Check for meaningful content
            if len(clean_opt) < 1 or clean_opt in ['A', 'B', 'C', 'D']:
                raise ValueError(f"Invalid option content: {opt}")
                
            clean_options.append(clean_opt)

        # Validate correct answer format
        raw_correct = str(question['correctAnswer']).strip()
        
        # Extract value from letter-based answers
        if re.match(r'^[A-D]$', raw_correct, re.IGNORECASE):
            try:
                correct_index = ord(raw_correct.upper()) - 65
                correct_value = clean_options[correct_index]
            except IndexError:
                raise ValueError("Correct answer letter out of range")
        else:
            # Handle value-based answers
            clean_correct = re.sub(r'^[A-D][):.]?\s*', '', raw_correct).strip()
            if clean_correct not in clean_options:
                raise ValueError("Correct answer not found in options")
            correct_value = clean_correct

        # Shuffle options while tracking correct value
        random.shuffle(clean_options)

        return {
            'question_text': question['questionText'],
            'options': clean_options,  # Store raw values without labels
            'correct_answer': correct_value,  # Store actual correct value
            'hint': question['hint'],
            'explanation': question['explanation'],
            'grade': grade,
            'subject': subject,
            'topic': topic,
            'level': level
        }
    def _record_question(self, user, question):
        signature = QuestionCache.generate_signature(question)
        UserQuestionHistory.objects.update_or_create(
            user=user,
            question_signature=signature,
            defaults={'created_at': timezone.now()}
        )