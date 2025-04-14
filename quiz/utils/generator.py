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
    - Include 4 distinct options with values (not just letters)
    - Include clear explanation of the solution
    - Example JSON response:
    {{
    "questionText": "What is 15 - 7?",
    "options": ["8", "9", "7", "10"],
    "correctAnswer": "A",
    "hint": "Subtract carefully",
    "explanation": "15 - 7 = 8"
    }}

    Important: You must format the response as JSON and include the word 'JSON' in your response."""
    
    
    def _validate_and_format(self, question, grade, subject, topic, level):
        # Structural validation
        if not all(key in question for key in self.required_fields):
            raise ValueError("Missing required fields in generated question")
        
        if len(question['options']) != 4:
            raise ValueError("Exactly 4 options required")

        # Validate option content
        clean_options = []
        for idx, opt in enumerate(question['options']):
            # Remove existing labels and whitespace
            clean_opt = re.sub(r'^[A-D][):.]?\s*', '', str(opt)).strip()
            
            # Check for meaningful content
            if len(clean_opt) < 1 or clean_opt in ['A', 'B', 'C', 'D']:
                raise ValueError(f"Invalid option content: {opt}")
                
            clean_options.append(clean_opt)

        # Check option type consistency - ADD THIS SECTION
        option_types = set()
        for opt in clean_options:
            if re.match(r'^-?\d+([.,]\d+)?$', opt):
                option_types.add('number')
            else:
                option_types.add('text')
                
        if len(option_types) > 1:
            raise ValueError("Mixed option types: " + ", ".join(option_types))
        # END OF NEW SECTION

        # Validate correct answer format
        raw_correct = str(question['correctAnswer']).strip().upper()
        
        # Handle letter-based answers
        if re.match(r'^[A-D]$', raw_correct):
            correct_index = ord(raw_correct) - 65
            if correct_index >= len(clean_options):
                raise ValueError("Correct answer letter out of range")
            correct_value = clean_options[correct_index]
        else:
            # Handle value-based answers
            clean_correct = re.sub(r'^[A-D][):.]?\s*', '', raw_correct).strip()
            if clean_correct not in clean_options:
                raise ValueError("Correct answer not found in options")
            correct_value = clean_correct

        # Shuffle options while tracking correct answer
        indexed_options = list(enumerate(clean_options))
        random.shuffle(indexed_options)
        
        # Build final options with new labels
        final_options = []
        correct_letter = None
        for i, (orig_idx, opt) in enumerate(indexed_options):
            letter = chr(65 + i)
            final_options.append(f"{letter}: {opt}")
            if clean_options[orig_idx] == correct_value:
                correct_letter = letter

        if not correct_letter:
            raise ValueError("Correct answer lost during shuffling")

        return {
            'question_text': question['questionText'],
            'options': final_options,
            'correct_answer': correct_letter,
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