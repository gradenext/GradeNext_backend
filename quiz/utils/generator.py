import openai
import json
import uuid
import logging
from django.conf import settings
from quiz.config.curriculum import SUBJECT_TOPICS
from .cache import QuestionCache

logger = logging.getLogger(__name__)

class QuestionGenerator:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate_question(self, grade, subject, topic, level, revision=False):
        cache_key = QuestionCache.generate_key(grade, subject, topic, level, revision)
        cached = QuestionCache.get(cache_key)
        
        if cached and len(cached) >= 5:
            return cached.pop(0)
            
        try:
            prompt = self._build_prompt(grade, subject, topic, level, revision)
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            question = json.loads(response.choices[0].message.content)
            question = self._validate_and_format(question, grade, subject, topic, level)
            
            QuestionCache.add(cache_key, question)
            return question
            
        except openai.APIError as e:
            logger.error(f"OpenAI API Error: {e}")
            raise ValueError("Question generation service unavailable")
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {str(e)}")
            raise ValueError("Failed to parse question response")
        except Exception as e:
            logger.error(f"Question generation failed: {str(e)}")
            raise

    # Rest of the class remains the same...

    def _build_prompt(self, grade, subject, topic, level, revision=False):
        subtopics = SUBJECT_TOPICS[subject][topic]
        base = f"Generate a {level} difficulty {subject} question for grade {grade} students."
        revision_note = " Focus on revision of previously mastered concepts." if revision else  ""

        return f"""
        Generate a {level} difficulty {subject} question for grade {grade} students.
        Topic: {topic}
        Subtopics: {', '.join(subtopics)}
        
        Requirements:
        - Unique question not from textbooks
        - 4 multiple-choice options
        - Grade-appropriate language
        - Clear explanation
        - JSON format with: questionText, options, correctAnswer, hint, explanation
        """

    def _validate_and_format(self, question, grade, subject, topic, level):
        required_fields = ['questionText', 'options', 'correctAnswer', 'hint', 'explanation']
        if not all(field in question for field in required_fields):
            raise ValueError("Missing required fields in generated question")
            
        if len(question['options']) != 4:
            raise ValueError("Exactly 4 options required")
            
        if question['correctAnswer'] not in question['options']:
            raise ValueError("Correct answer must be one of the options")
            
        return {
            # 'id': str(uuid.uuid4()),
            'question_text': question['questionText'],
            'options': question['options'],
            'correct_answer': question['correctAnswer'],
            'hint': question['hint'],
            'explanation': question['explanation'],
            'grade': grade,
            'subject': subject,
            'topic': topic,
            'level': level
        }