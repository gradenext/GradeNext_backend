import openai
import json
import re
import random
import logging
from django.conf import settings
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from quickchart import QuickChart
import cloudinary.uploader
import uuid
import math
from .cache import QuestionCache
from quiz.models import UserQuestionHistory
from django.utils import timezone
from .image_utils import (
    create_pillow_image_with_text,
    upload_pillow_image_to_cloudinary
)
from .visual_generator import (
    draw_ruler, draw_number_line, draw_fraction_bar, draw_angle, draw_cube,
    draw_translation, draw_scale_drawing, draw_graph, draw_circle, draw_right_triangle
)
from quiz.config.curriculum import SUBJECT_TOPICS
from emoji import emojize

logger = logging.getLogger(__name__)

DRAW_FUNCTIONS = {
    'cube': draw_cube,
    'circle': draw_circle,
    'right_triangle': draw_right_triangle,
    'rectangle': lambda **kwargs: QuestionGenerator()._draw_rectangle(kwargs),
    'clock': lambda **kwargs: QuestionGenerator()._draw_clock(kwargs),
    'geometric_shape': lambda **kwargs: QuestionGenerator()._draw_geometric_shape(kwargs),
}

class QuestionGenerator:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.max_retries = 5
        self.required_fields = [
            'questionText', 'correctAnswer', 'hint', 'questionType']
        self.valid_image_types = [
            'rectangle', 'number_line', 'fraction', 'clock', 'graph', 'geometric_shape',
            'ruler', 'angle', 'cube', 'translation', 'scale_drawing', 'circle', 'right_triangle'
        ]

    def _draw_rectangle(self, params: dict) -> str:
        length = params.get('length', 5)
        width = params.get('width', 3)
        img = Image.new("RGB", (400, 250), "white")
        draw = ImageDraw.Draw(img)
        fill_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        draw.rectangle([(50, 50), (50+length*20, 50+width*20)],
                       fill=fill_color, outline="black", width=2)
        font = ImageFont.truetype("arial.ttf", 18) if settings.DEBUG else ImageFont.load_default()
        draw.text((60, 30), f"Length: {length}cm", fill="black", font=font)
        draw.text((200, 130), f"Width: {width}cm", fill="black", font=font)
        return upload_pillow_image_to_cloudinary(img)

    def _draw_clock(self, params: dict) -> str:
        hours = params.get('hours', 12)
        minutes = params.get('minutes', 0)
        img = Image.new("RGB", (400, 400), "white")
        draw = ImageDraw.Draw(img)
        draw.ellipse((50, 50, 350, 350), outline="black", width=3)
        hour_angle = math.radians((hours % 12) * 30 - 90)
        hour_length = 80
        draw.line([(200, 200),
                   (200 + hour_length * math.cos(hour_angle),
                    200 + hour_length * math.sin(hour_angle))],
                  fill="blue", width=4)
        minute_angle = math.radians(minutes * 6 - 90)
        minute_length = 120
        draw.line([(200, 200),
                   (200 + minute_length * math.cos(minute_angle),
                    200 + minute_length * math.sin(minute_angle))],
                  fill="red", width=3)
        return upload_pillow_image_to_cloudinary(img)

    def _draw_geometric_shape(self, params: dict) -> str:
        shape = params.get('shape', 'square').lower()
        img_width, img_height = 400, 300
        img = Image.new("RGB", (img_width, img_height), "white")
        draw = ImageDraw.Draw(img)
        fill_color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        )
        center_x, center_y = img_width // 2, img_height // 2
        shape_size = 200
        half_size = shape_size // 2
        if shape == 'square':
            draw.rectangle(
                [(center_x - half_size, center_y - half_size),
                 (center_x + half_size, center_y + half_size)],
                fill=fill_color, outline="black", width=2
            )
        elif shape == 'circle':
            draw.ellipse(
                [(center_x - half_size, center_y - half_size),
                 (center_x + half_size, center_y + half_size)],
                fill=fill_color, outline="black", width=2
            )
        elif shape == 'triangle':
            base = shape_size
            height = int(shape_size * 0.866)
            points = [
                (center_x, center_y - height // 2),
                (center_x - base // 2, center_y + height // 2),
                (center_x + base // 2, center_y + height // 2)
            ]
            draw.polygon(points, fill=fill_color, outline="black", width=2)
        elif shape == 'pentagon':
            radius = shape_size // 2
            points = [
                (
                    center_x + radius * math.cos(2 * math.pi * i / 5 - math.pi / 2),
                    center_y + radius * math.sin(2 * math.pi * i / 5 - math.pi / 2)
                )
                for i in range(5)
            ]
            draw.polygon(points, fill=fill_color, outline="black", width=2)
        elif shape == 'hexagon':
            radius = shape_size // 2
            points = [
                (
                    center_x + radius * math.cos(2 * math.pi * i / 6),
                    center_y + radius * math.sin(2 * math.pi * i / 6)
                )
                for i in range(6)
            ]
            draw.polygon(points, fill=fill_color, outline="black", width=2)
        elif shape == 'oval':
            oval_width = 200
            oval_height = 120
            draw.ellipse(
                [(center_x - oval_width // 2, center_y - oval_height // 2),
                 (center_x + oval_width // 2, center_y + oval_height // 2)],
                fill=fill_color, outline="black", width=2
            )
        elif shape == 'parallelogram':
            base = 200
            height = 120
            slant = 40
            points = [
                (center_x - base // 2 + slant, center_y - height // 2),
                (center_x + base // 2 + slant, center_y - height // 2),
                (center_x + base // 2 - slant, center_y + height // 2),
                (center_x - base // 2 - slant, center_y + height // 2)
            ]
            draw.polygon(points, fill=fill_color, outline="black", width=2)
        else:
            raise ValueError(f"Unsupported shape: {shape}")
        return upload_pillow_image_to_cloudinary(img)

    def _process_question_text(self, text, grade):
        if grade <= 3:
            try:
                return emojize(text, language='alias')
            except Exception as e:
                logger.warning(f"Emoji processing failed: {str(e)}")
                return text
        return text

    def _build_prompt(self, grade, subject, topic, subtopics, level, revision, seen_questions):
        text_visual_instruction = ""
        if grade <= 3:
            text_visual_instruction = (
                "For grades 1-3:\n"
                "- Use EMOJIS instead of words for objects in the question.\n"
                "- Structure questions visually with 1 emoji = 1 object.\n"
                "- Example: '🍎 + 🍎 = ?' or 'If you have 🚗🚗🚗 and get 2 more, how many cars?'\n"
                "- ALWAYS use emojis for countable objects in the question text.\n"
                "- Options must be NUMBERS ONLY for math, TEXT ONLY for English, without emojis.\n"
                "- Strictly avoid generating questions referencing to any image or visual content.\n"
            )
        else:
            text_visual_instruction = "For grades 4 and above, use standard text format without emojis.\n"
        image_instruction = (
            "Additionally, include a visual diagram in the JSON to help illustrate the question better, for all grades. Use the following format:\n"
            "- 'imageType': A string indicating the type of image, choose from: 'rectangle', 'number_line', 'fraction', 'clock', 'graph', 'geometric_shape', 'ruler', 'angle', 'cube', 'translation', 'scale_drawing', 'circle', 'right_triangle'\n"
            "- 'imageParams': A dictionary with the imageType as the key, and another dictionary containing the parameters for that image type.\n"
            "Examples:\n"
            "  - Ruler: 'imageParams': {'ruler': {'length': 10, 'units': 1}}\n"
            "  - Number Line: 'imageParams': {'number_line': {'start': 0, 'end': 10, 'highlight': 5}}\n"
            "  - Fraction Bar: 'imageParams': {'fraction': {'numerator': 1, 'denominator': 2}}\n"
            "  - Angle: 'imageParams': {'angle': {'degrees': 90}}\n"
            "  - Cube: 'imageParams': {'cube': {}}\n"
            "  - Translation: 'imageParams': {'translation': {'shape': 'square', 'dx': 50, 'dy': 50}}\n"
            "  - Scale Drawing: 'imageParams': {'scale_drawing': {'scale': 2}}\n"
            "  - Circle: 'imageParams': {'circle': {'radius': 5}}\n"
            "  - Right Triangle: 'imageParams': {'right_triangle': {'a': 3, 'b': 4, 'c': 5}}\n"
            "Make sure to provide all required parameters for the chosen imageType.\n"
            "If no image is particularly helpful, you may omit 'imageType' and 'imageParams', but try to include one if possible.\n"
        )

        question_type = random.choice(['multiple', 'input'])
        required_json = """
        {
            "questionType": "%s",
            "questionText": "The question text",
            "options": ["Option1", "Option2", "Option3", "Option4"],
            "correctAnswer": "CorrectOption",
            "hint": "A helpful clue or approach directly related to solving this specific question.",
            "explanation": "A detailed explanation that clearly and logically leads to the correct answer provided above. The explanation must only support the correctAnswer and must not describe or validate any incorrect options."

        }
        """ % question_type

        if subtopics:
            focus = f", specifically focusing on {', '.join(subtopics)}"
        else:
            focus = ""

        prompt = f"""Generate a {level} difficulty {subject} question for grade {grade} students about {topic}{focus}. Include a visual diagram in the JSON if it can help illustrate the question better, for all grades.
        
        
        **Important Instructions:**
        - Do not include any formulas in the question text. The question should present a problem or scenario that requires the student to recall and apply the appropriate formula.
        - Use proper mathematical symbols and notation in the question text and options where mathematical expressions are involved. Avoid writing mathematical operations or concepts in plain text; use symbols such as +, -, ×, ÷, =, <, >, π, θ, etc., where appropriate.
        - If a mathematical symbol is not available, do not represent it with plain text (e.g., do not use "/pi/" for π). Instead, ensure that only symbols are used when necessary.
        - Always generate unique numerical values or scenarios each time a question is created.
        
        {text_visual_instruction}
        {image_instruction}
        
        **Required JSON Format:**
        {required_json}
        // Optionally:
        // "imageType": "type_of_image",
        // "imageParams": {{"type_of_image": {{"param1": value1, ...}}}}
        
        
        **Subject-Specific Rules:**
        - Math: For grades 1-3, use emoji equations or counting with emojis. For grades 4+, use standard math notation with symbols and strictly avoid giving formula in question.
        - English: For grades 1-3, use emoji sequences to represent actions or scenarios. For grades 4+, use standard text.
        
        
        **Additional Instructions:**
        - For "multiple" type questions, provide 4 descriptive options (e.g., "80 degrees", "75 degrees" for math, or descriptive text for English).
        - For "input" type questions, provide 4 integer options (e.g., "80", "75", "90", "85") and ensure the correct answer is an integer.
        
        
        **Table Inclusion:**
        -If the question includes structured information like comparisons, schedules, data analysis, classifications, frequency, etc.,   embed the information directly as a **visually formatted table** inside the `questionText` using **Markdown or clear ASCII formatting**.
        - If the question requires presenting data in a tabular format, include a markdown table in the 'questionText' field.
        - Use the markdown table format, for example:
        ```
        | Header1 | Header2 |
        |---------|---------|
        | Row1    | Row2    |
        ```
        - Ensure the table is clearly formatted with appropriate headers and is relevant to the question.
        - Ensure the **question references** the table clearly, e.g., "Refer to the table below to answer the question."
        - Do **not** place tables in a separate field like `"table"`. They must appear **inside the question text** itself.
        - Tables are most appropriate for:
        - Price comparisons
        - Train/bus schedules
        - Survey data
        - Frequency charts
        - Temperature/time measurements
        - Class attendance, etc.

        - If a table is needed but not useful to solving the question, skip it.
        
        **Math Formatting Rules (Grades 4+):**
        - Use proper mathematical notation and symbols.
        - Do not include any formulas or equations in the question text that provide the solution method.
        -Avoid using plain text for mathematical symbols.
        - Use Unicode math symbols where possible:
          - π → `π` (U+03C0)
          - θ → `θ` (U+03B8)
          - γ → `γ` (U+03B3)
          - λ → `λ` (U+03BB)
        
        - Avoid using `pi`, `theta`, `lambda` in plain text. Always replace with `π`, `θ`, `λ`.
        - Ensure all mathematical expressions are correctly formatted with symbols, not plain text (e.g., use '+' for addition, '×' for multiplication, '÷' for division, etc.).
        
        **Randomization & Variation Rules:**
        - Always generate unique numerical values or scenarios each time a question is created.
        - Avoid reusing the same numbers, figures, or object counts from previous questions.
        - Ensure variations are meaningful and affect the question outcome or difficulty.
        - Use random values within a reasonable range appropriate to the grade and topic. For example:
        - Circle radius: random between 4 cm and 15 cm
        - Rectangle sides: random between 5 and 25 units
        - Fractions: random numerators and denominators between 1 and 10
        - DO NOT repeat fixed examples like radius = 7, base = 5, or side = 10 in every run.
        
        
        **Clarity and Visual Accuracy Rules:**
        - If the question refers to a "highlighted", "underlined", or "bold" word in a sentence, make sure to actually format it in the `questionText` using clear **Markdown** or formatting indicators:
        - Use Markdown between `<u></u> underline html tag`, with `**bold**`, or `*italics*` to emphasize the referenced word.
        - Example: "Identify the part of speech of the underlined word in the sentence: 'She __quickly__ ran to the store.'"
        - Never mention formatting like "underlined" or "highlighted" without actually applying the formatting to the relevant word.
        - If you cannot apply the formatting, rephrase the question clearly, such as: "What part of speech is the word *quickly* in the sentence 'She quickly ran to the store'?"
        - If visual formatting like underlining is not possible, place the word in **quotes** or **capitalize it** for clarity:
        - Example: What part of speech is the word **"QUICKLY"** in the sentence: She quickly ran to the store?
        


        """
        return prompt

    def generate_question(self, user, grade, subject, topic, level, revision=False):
        cache_key = QuestionCache.generate_key(grade, subject, topic, level, revision)
        seen_questions = set(UserQuestionHistory.objects.filter(user=user).values_list('question_signature', flat=True))
        all_subtopics = SUBJECT_TOPICS[subject][topic]
        subtopics = random.sample(all_subtopics, min(3, len(all_subtopics))) if all_subtopics else []
        for attempt in range(self.max_retries):
            try:
                cached = [q for q in QuestionCache.get(cache_key) if QuestionCache.generate_signature(q) not in seen_questions]
                if cached and random.random() < 0.3:
                    logger.info(f"Using cached question for {cache_key}")
                    question = random.choice(cached)
                    QuestionCache.add(cache_key, question)
                    self._record_question(user, question)
                    return question
                prompt = self._build_prompt(grade, subject, topic, subtopics, level, revision, seen_questions)
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
                question_data = json.loads(response.choices[0].message.content)
                question_type = question_data.get('questionType')
                if question_type not in ['multiple', 'input']:
                    raise ValueError("Invalid questionType")
                if question_type == 'multiple':
                    if 'options' not in question_data or len(question_data['options']) != 4:
                        raise ValueError("Multiple-choice question must have exactly 4 options")
                    if 'correctAnswer' not in question_data or question_data['correctAnswer'] not in question_data['options']:
                        raise ValueError("Correct answer must be one of the options")
                elif question_type == 'input':
                    if 'options' not in question_data or len(question_data['options']) != 4:
                        raise ValueError("Input question must have exactly 4 integer options")
                    for opt in question_data['options']:
                        try:
                            int(opt)
                        except ValueError:
                            raise ValueError("All options for input type must be integers")
                    try:
                        int(question_data['correctAnswer'])
                    except ValueError:
                        raise ValueError("Correct answer for input type must be an integer")
                required_common_fields = ['questionText', 'hint']
                for field in required_common_fields:
                    if field not in question_data:
                        raise ValueError(f"Missing required field: {field}")
                image_url = None
                image_generated = False
                try:
                    if grade >= 4 and 'imageType' in question_data and question_data['imageType']:
                        image_url, image_generated = self._generate_visual(
                            question_text=question_data.get("questionText", ""),
                            image_type=question_data['imageType'],
                            image_params=question_data.get("imageParams", {})
                        )
                except Exception as e:
                    logger.warning(f"Image generation failed but continuing: {str(e)}")
                    image_url = None
                    image_generated = False
                # Moved explanation generation outside the nested try-except
                explanation = self._generate_explanation(
                    question_data['questionText'],
                    question_data['correctAnswer']
                )
                question = {
                    "question_text": self._process_question_text(question_data['questionText'], grade),
                    "options": question_data.get('options', []),
                    "correct_answer": question_data['correctAnswer'],
                    "hint": question_data['hint'],
                    "explanation": explanation,
                    "image_url": image_url,
                    "image_generated": image_generated,
                    "question_type": question_type
                }
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
            except Exception as e:
                logger.error(f"Question generation error: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise RuntimeError("Failed to generate valid question after multiple attempts")
                continue
        raise RuntimeError("Exhausted all generation attempts")

    def _generate_explanation(self, question_text, correct_answer):
        prompt = f"""
    Given the following 'correct answer: {correct_answer}' and 'question: {question_text}', generate a short, clear formatted explanation that only leads to the provided correct answer:{correct_answer}.

    Question: {question_text}
    Correct Answer: {correct_answer}

    Explanation Rules:
    - The explanation must support ONLY the correct answer ({correct_answer}).
    - Always strictly Use math formatting (×, =, √, etc.) where applicable to simplify understanding.
    - The explanation must be logically consistent with the correct answer — do the math if needed.
    - Never mention or calculate any other answer even if correct answer is wrong.
    - Keep the explanation 3–5 lines max. Avoid over-explaining.

    IMPORTANT:
    Double-check that the final calculation/result in the explanation equals the correct answer: {correct_answer}.
    If it does not, revise the steps so it does.
    
    **Math Formatting Rules (Grades 4+):**
    - Use proper mathematical notation and symbols.
    - Do not include any formulas or equations in the question text that provide the solution method.
    -Avoid using plain text for mathematical symbols.
    - Use Unicode math symbols where possible:
        - π → `π` (U+03C0)
        - θ → `θ` (U+03B8)
        - γ → `γ` (U+03B3)
        - λ → `λ` (U+03BB)
        
    - Avoid using `pi`, `theta`, `lambda` in plain text. Always replace with `π`, `θ`, `λ`.
    - Do NOT use LaTeX or escape characters like \\( or \\), $...$, etc.
    - Format units cleanly: e.g., 4 cm × 5 cm = 20 cm².
    - Ensure all mathematical expressions are correctly formatted with symbols, not plain text (e.g., use '+' for addition, '×' for multiplication, '÷' for division, etc.).

    Output only the explanation.
    """
        response = self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=250,
        )
        explanation = response.choices[0].message.content.strip()

        # Optional: Validate correctness in Python (last-resort fallback)
        if str(correct_answer) not in explanation:
            explanation += f"\n(Note: Ensure explanation result matches {correct_answer} exactly.)"

        return explanation



    def _generate_visual(self, question_text: str, image_type: str = None, image_params: dict = None) -> tuple[str, bool]:
        try:
            if image_type and image_type in DRAW_FUNCTIONS:
                draw_func = DRAW_FUNCTIONS[image_type]
                specific_params = image_params.get(image_type, {})
                validated_params = self._validate_image_params(image_type, specific_params)
                image_url = draw_func(**validated_params)
                return image_url, True
        except Exception as e:
            logger.warning(f"Image generation failed but continuing: {str(e)}")
            return self._generate_text_based_fallback(question_text), False
        return self._generate_text_based_fallback(question_text), False

    def _validate_image_params(self, image_type: str, params: dict) -> dict:
        validation_rules = {
            'rectangle': {'required': ['length', 'width']},
            'number_line': {'required': ['start', 'end'], 'optional': ['step', 'highlight'], 'defaults': {'step': 1, 'highlight': None}},
            'fraction': {'required': ['numerator', 'denominator'], 'defaults': {'numerator': 1, 'denominator': 2}},
            'clock': {'required': ['hours', 'minutes'], 'defaults': {'hours': 12, 'minutes': 0}},
            'graph': {'required': ['type', 'labels', 'data'], 'defaults': {'type': 'bar', 'labels': ['A', 'B', 'C', 'D'], 'data': [12, 19, 3, 5]}},
            'geometric_shape': {'required': ['shape'], 'defaults': {'shape': 'square'}},
            'ruler': {'required': ['length', 'units'], 'optional': ['unit_length'], 'defaults': {'unit_length': 20}},
            'angle': {'required': ['degrees'], 'defaults': {'degrees': 90}},
            'cube': {},
            'translation': {'required': ['shape', 'dx', 'dy'], 'defaults': {'shape': 'square', 'dx': 50, 'dy': 50}},
            'scale_drawing': {'required': ['scale'], 'defaults': {'scale': 2}},
            'circle': {'required': ['radius'], 'defaults': {'radius': 5}},
            'right_triangle': {'required': ['a', 'b', 'c'], 'defaults': {'a': 3, 'b': 4, 'c': 5}}
        }
        rule = validation_rules.get(image_type, {})
        validated = {}
        for key, value in params.items():
            if key in rule.get('required', []) or key in rule.get('optional', []):
                validated[key] = value
        for key, value in rule.get('defaults', {}).items():
            validated.setdefault(key, value)
        for param in rule.get('required', []):
            if param not in validated:
                raise ValueError(f"Missing required parameter: {param}")
        return validated

    def _validate_and_format(self, question, grade, subject, topic, level):
        if 'imageType' in question:
            if question['imageType'] not in self.valid_image_types:
                raise ValueError("Invalid imageType")
            if not isinstance(question.get('imageParams', {}), dict):
                raise ValueError("imageParams must be a dictionary")
        if not all(key in question for key in self.required_fields):
            raise ValueError("Missing required fields")
        if len(question['options']) != 4:
            raise ValueError("Exactly 4 options required")
        clean_options = []
        for opt in question['options']:
            clean_opt = re.sub(r'^[A-D][):.]?\s*', '', str(opt)).strip()
            if len(clean_opt) < 1:
                raise ValueError("Invalid option")
            clean_options.append(clean_opt)
        raw_correct = str(question['correct_answer']).strip()
        if raw_correct not in clean_options:
            raise ValueError("Correct answer not found in options")
        random.shuffle(clean_options)
        return {
            'question_text': question['questionText'],
            'options': clean_options,
            'correct_answer': raw_correct,
            'hint': question['hint'],
            'explanation': question['explanation'],
            'grade': grade,
            'subject': subject,
            'topic': topic,
            'level': level,
            'question_type': question['questionType']
        }

    def _generate_and_upload_image(self, question):
        text = question['question_text']
        img = Image.new('RGB', (800, 200), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        d.text((10, 80), text, fill=(0, 0, 0), font=font)
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        result = cloudinary.uploader.upload(buffer, folder='gradenext_questions')
        return result['secure_url']

    def _record_question(self, user, question):
        signature = QuestionCache.generate_signature(question)
        UserQuestionHistory.objects.update_or_create(
            user=user,
            question_signature=signature,
            defaults={'created_at': timezone.now()}
        )

    def _generate_text_based_fallback(self, text):
        accent_color = (
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200)
        )
        formatted_text = '\n'.join([
            text[:100],
            "Diagram:",
            "Generated by GradeNext"
        ])
        fallback_img = create_pillow_image_with_text(
            formatted_text,
            size=(600, 400),
            accent_color=accent_color
        )
        return upload_pillow_image_to_cloudinary(fallback_img)