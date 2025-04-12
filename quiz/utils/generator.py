import openai
import json
import logging
import re
import random
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
            return random.choice(cached)
            
        try:
            prompt = self._build_prompt(grade, subject, topic, level, revision)
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9 if revision else 0.7,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            question = json.loads(response.choices[0].message.content)
            question = self._validate_and_format(question, grade, subject, topic, level)
            
            QuestionCache.add(cache_key, question)
            return question
            
        except Exception as e:
            logger.error(f"Question generation failed: {str(e)}")
            return self._fallback_question(grade, subject, topic, level)

    def _build_prompt(self, grade, subject, topic, level, revision=False):
        subtopics = SUBJECT_TOPICS[subject][topic]
        return f"""
        Generate a {level} difficulty {subject} question for grade {grade} students.
        Topic: {topic}
        Subtopics: {', '.join(subtopics)}
        
        Requirements:
        - Generate completely unique scenario not used in previous questions
        - Provide 4 answer options labeled ONLY with A: , B: , C: , D:
        - Ensure correct answers are randomly distributed across positions
        - Avoid any patterns in correct answer placement
        - Include clear explanation of the solution
        - JSON format: questionText, options (array), correctAnswer, hint, explanation
        - Example format for options: ["5 apples", "10 apples", "3 apples", "15 apples"]
        """

    def _validate_and_format(self, question, grade, subject, topic, level):
        required_fields = ['questionText', 'options', 'correctAnswer', 'hint', 'explanation']
        if not all(field in question for field in required_fields):
            raise ValueError("Missing required fields in generated question")
        
        if len(question['options']) != 4:
            raise ValueError("Exactly 4 options required")

        # Clean existing labels from options
        cleaned_options = []
        for opt in question['options']:
            clean_opt = re.sub(r'^[A-D][):.]?\s*', '', str(opt)).strip()
            cleaned_options.append(clean_opt)

        # Validate correct answer exists
        try:
            correct_answer = re.sub(r'^[A-D][):.]?\s*', '', question['correctAnswer']).strip()
            correct_idx = cleaned_options.index(correct_answer)
        except ValueError:
            raise ValueError("Correct answer must match one of the cleaned options")

        # Shuffle options with correct answer tracking
        letters = ['A', 'B', 'C', 'D']
        indexed_options = list(enumerate(cleaned_options))
        random.shuffle(indexed_options)
        
        shuffled_options = [opt for _, opt in indexed_options]
        original_indices = [i for i, _ in indexed_options]
        new_correct_idx = original_indices.index(correct_idx)
        
        return {
            'question_text': question['questionText'],
            'options': [f"{letter}: {opt}" for letter, opt in zip(letters, shuffled_options)],
            'correct_answer': letters[new_correct_idx],
            'hint': question['hint'],
            'explanation': question['explanation'],
            'grade': grade,
            'subject': subject,
            'topic': topic,
            'level': level
        }

    def _fallback_question(self, grade, subject, topic, level):
        return {
            'question_text': "What is 2 + 2?",
            'options': ["A: 3", "B: 4", "C: 5", "D: 6"],
            'correct_answer': "B",
            'hint': "Basic addition",
            'explanation': "2 plus 2 equals 4",
            'grade': grade,
            'subject': subject,
            'topic': topic,
            'level': level
        }