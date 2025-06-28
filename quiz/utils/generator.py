import openai
import json
import re
import random
import logging
from django.conf import settings
from io import BytesIO
import uuid
import math
import os
from .cache import QuestionCache
from quiz.models import UserQuestionHistory
from django.utils import timezone
from quiz.config.curriculum import SUBJECT_TOPICS

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(CURRENT_DIR, "prompt.txt")

try:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
        logger.info("✅ System prompt loaded successfully.")
except Exception as e:
    logger.error(f"❌ Failed to load system prompt: {str(e)}")
    SYSTEM_PROMPT = ""

class QuestionGenerator:
    
    total_api_calls = 0
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.max_retries = 5
        self.required_fields = [
            'questionText', 'correctAnswer', 'hint', 'explanation', 'questionType']

    def generate_batch_questions(self, user, grade, subject, topic, level, revision=False, system_prompt=None):
        cache_key = QuestionCache.generate_key(grade, subject, topic, level, revision)
        seen_questions = set(UserQuestionHistory.objects.filter(user=user).values_list('question_signature', flat=True))

        all_subtopics = SUBJECT_TOPICS[subject][topic]
        subtopics = random.sample(all_subtopics, min(3, len(all_subtopics))) if all_subtopics else []

        system_prompt = system_prompt or SYSTEM_PROMPT
        prompt = self._build_prompt(grade, subject, topic, subtopics, level, revision, seen_questions, system_prompt, batch=True)

        QuestionGenerator.total_api_calls += 1
        logger.info(f"🔁 OpenAI Batch API Call #{QuestionGenerator.total_api_calls}")

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4000,
            # ❌ Don't use response_format here
            # response_format={"type": "json_object"},
        )

        raw_output = response.choices[0].message.content.strip()
        logger.debug(f"Raw OpenAI Response:\n{raw_output}")

        # ✅ Extract array using regex fallback if needed
        try:
            match = re.search(r'\[.*\]', raw_output, re.DOTALL)
            if not match:
                raise ValueError("No JSON array found in response.")
            questions_data = json.loads(match.group(0))
        except Exception as e:
            logger.error(f"❌ JSON parsing failed: {str(e)}")
            raise RuntimeError("Expected a list of question objects in JSON")

        valid_questions = []
        for qdata in questions_data:
            try:
                question_type = qdata.get('questionType')
                if question_type not in ['multiple', 'input']:
                    continue

                if question_type == 'multiple':
                    if 'options' not in qdata or len(qdata['options']) != 4 or qdata['correctAnswer'] not in qdata['options']:
                        continue
                elif question_type == 'input':
                    if 'options' not in qdata or len(qdata['options']) != 4 or not all(str(opt).isdigit() for opt in qdata['options']):
                        continue
                    if not str(qdata['correctAnswer']).isdigit():
                        continue

                if not self._validate_explanation_supports_answer(qdata['explanation'], qdata['correctAnswer']):
                    continue

                for field in ['questionText', 'hint', 'explanation']:
                    if field not in qdata:
                        raise ValueError(f"Missing required field: {field}")

                # Shuffle options and update correct_answer
                options = qdata.get('options', [])
                correct = qdata['correctAnswer']

                if correct in options:
                    random.shuffle(options)
                    correct_index = options.index(correct)
                else:
                    continue  # Skip if somehow the correct answer isn't in options

                question = {
                    "question_text": qdata['questionText'],
                    "options": options,
                    "correct_answer": options[correct_index],
                    "hint": qdata['hint'],
                    "explanation": qdata['explanation'],
                    "image_url": None,
                    "image_generated": False,
                    "question_type": question_type
                }


                if QuestionCache.generate_signature(question) in seen_questions:
                    continue

                QuestionCache.add(cache_key, question)
                self._record_question(user, question)
                valid_questions.append(question)

                if len(valid_questions) >= 10:
                    break

            except Exception as e:
                logger.warning(f"Skipping invalid question in batch: {str(e)}")
                continue

        if not valid_questions:
            raise RuntimeError("No valid questions generated")

        return valid_questions


    def _build_prompt(self, grade, subject, topic, subtopics, level, revision, seen_questions, system_prompt, batch=False):
        system_prompt = system_prompt or SYSTEM_PROMPT
        
        question_type = random.choice(['multiple', 'input'])

        if grade <= 3:
            text_visual_instruction = (
                "For grades 1 to 3:\n"
                "- Use simple number-based questions or equations.\n"
                "- Avoid using emojis or visual symbols.\n"
                "- Focus on numeric reasoning, basic operations (e.g., 2 + 3, 5 - 1, etc.), comparisons, or simple word problems using only text.\n"
                "- Do not focus on scenarios based questions.\n"
                "- Occasionally, include scenario-based questions.\n"
                "- Do not generate questions referring to images, diagrams, arrays, or figures unless they are clearly represented within the questionText.\n"
                "- Ensure the question is solvable by logic or calculation, not visuals.\n"
                "- Avoid phrases like 'look at the image', 'refer to the diagram', or 'see the array'.\n"
            )
        else:
            text_visual_instruction = "For grades 4 and above, use standard text format without emojis.\n"

        science_instruction = ""
        if subject == "science":
            science_instruction = (
                "For science questions:\n"
                "- Focus on key concepts from the topic and subtopics\n"
                "- Use age-appropriate scientific terminology\n"
                "- Include practical applications where possible\n"
                "- For experiments or observations, describe the scenario clearly\n"
                "- For grades 4+, you can include basic diagrams if helpful\n"
            )

        def generate_sample_question_json(question_type):
            return f"""
            {{
                "questionType": "{question_type}",
                "questionText": "The question text",
                "options": ["Option1", "Option2", "Option3", "Option4"],
                "correctAnswer": "CorrectOption",
                "hint": "A helpful clue or approach directly related to solving this specific question.",
                "explanation": "A detailed explanation that clearly and logically leads to the correct answer provided above. The explanation must only support the correctAnswer and must not describe or validate any incorrect options."
            }}
            """

        focus = f", specifically focusing on {', '.join(subtopics)}" if subtopics else ""

        if batch:
            # Create 10 random JSON examples with random question types
            sample_jsons = "\n\n".join([generate_sample_question_json(random.choice(['multiple', 'input'])) for _ in range(10)])

            user_prompt = (
                f"Generate 10 {level} difficulty {subject} questions for grade {grade} students about {topic}{focus}.\n"
                + text_visual_instruction + "\n" + science_instruction + "\n\n"
                "Return ONLY a valid JSON array of 10 question objects, each in the format shown below. Do not add any explanation or text outside the JSON array:\n\n"
                + sample_jsons
            )
        else:
            required_json = generate_sample_question_json(question_type)
            user_prompt = (
                f"Generate a {level} difficulty {subject} question for grade {grade} students about {topic}{focus}.\n\n"
                + text_visual_instruction + "\n" + science_instruction + "\n\n"
                "Required JSON Format:\n" + required_json
            )

        return system_prompt.strip() + "\n\n" + user_prompt.strip()


    def _validate_explanation_supports_answer(self, explanation, correct_answer):
        normalized_explanation = explanation.lower().replace(',', '').strip()
        normalized_answer = str(correct_answer).lower().replace(',', '').strip()
        return normalized_answer in normalized_explanation

    def _record_question(self, user, question):
        signature = QuestionCache.generate_signature(question)
        UserQuestionHistory.objects.update_or_create(
            user=user,
            question_signature=signature,
            defaults={'created_at': timezone.now()}
        )
