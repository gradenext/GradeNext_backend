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
    # 'ruler': draw_ruler,
    # 'number_line': draw_number_line,
    # 'fraction': draw_fraction_bar,
    # 'angle': draw_angle,
    'cube': draw_cube,
    # 'translation': draw_translation,
    # 'scale_drawing': draw_scale_drawing,
    # 'graph': draw_graph,
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
            'questionText', 'correctAnswer', 'hint', 'explanation', 'questionType']
        self.valid_image_types = [
            'rectangle', 'number_line', 'fraction', 'clock', 'graph', 'geometric_shape',
            'ruler', 'angle', 'cube', 'translation', 'scale_drawing', 'circle', 'right_triangle'
        ]

    def _draw_rectangle(self, params: dict) -> str:
        """Generate rectangle diagram with given dimensions"""
        length = params.get('length', 5)
        width = params.get('width', 3)
        img = Image.new("RGB", (400, 250), "white")
        draw = ImageDraw.Draw(img)

        fill_color = (random.randint(0, 255), random.randint(
            0, 255), random.randint(0, 255))
        draw.rectangle([(50, 50), (50+length*20, 50+width*20)],
                       fill=fill_color, outline="black", width=2)

        font = ImageFont.truetype(
            "arial.ttf", 18) if settings.DEBUG else ImageFont.load_default()
        draw.text((60, 30), f"Length: {length}cm", fill="black", font=font)
        draw.text((200, 130), f"Width: {width}cm", fill="black", font=font)

        return upload_pillow_image_to_cloudinary(img)

    def _draw_clock(self, params: dict) -> str:
        """Generate clock face with specified time"""
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
        """Generate fixed-size geometric shapes centered in image"""
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
        shape_size = 200  # fixed size for all shapes
        half_size = shape_size // 2

        if shape == 'square':
            draw.rectangle(
                [(center_x - half_size, center_y - half_size),
                 (center_x + half_size, center_y + half_size)],
                fill=fill_color, outline="black", width=2
            )

        # elif shape == 'rectangle':
        #     rect_width = 200
        #     rect_height = 120
        #     draw.rectangle(
        #         [(center_x - rect_width // 2, center_y - rect_height // 2),
        #         (center_x + rect_width // 2, center_y + rect_height // 2)],
        #         fill=fill_color, outline="black", width=2
        #     )

        elif shape == 'circle':
            draw.ellipse(
                [(center_x - half_size, center_y - half_size),
                 (center_x + half_size, center_y + half_size)],
                fill=fill_color, outline="black", width=2
            )

        elif shape == 'triangle':
            base = shape_size
            height = int(shape_size * 0.866)  # height for equilateral triangle
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
                    center_x + radius *
                    math.cos(2 * math.pi * i / 5 - math.pi / 2),
                    center_y + radius *
                    math.sin(2 * math.pi * i / 5 - math.pi / 2)
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

    def _draw_graph(self, params: dict) -> str:
        """Generate a simple graph using QuickChart"""
        chart_config = {
            "type": params.get('type', 'bar'),
            "data": {
                "labels": params.get("labels", ["A", "B", "C", "D"]),
                "datasets": [{
                    "label": params.get("label", "Data Series"),
                    "data": params.get("data", [12, 19, 3, 5]),
                    "backgroundColor": [
                        f"rgb({random.randint(0, 255)}, {random.randint(0, 255)}, {random.randint(0, 255)})"
                        for _ in range(4)
                    ]
                }]
            },
            "options": {
                "plugins": {
                    "datalabels": {"display": True},
                    "legend": {"display": False}
                }
            }
        }
        qc = QuickChart()
        qc.width = 600
        qc.height = 400
        qc.config = chart_config
        return qc.get_short_url()
    
    def _process_question_text(self, text, grade):
        # """Process question text with emojis for grades 1-3"""
        # if grade <= 3:
        #     try:
        #         return emojize(text, language='alias')
        #     except Exception as e:
        #         logger.warning(f"Emoji processing failed: {str(e)}")
        #         return text
        return text

    def generate_question(self, user, grade, subject, topic, level, revision=False):
        cache_key = QuestionCache.generate_key(
            grade, subject, topic, level, revision)
        seen_questions = set(UserQuestionHistory.objects.filter(user=user)
                             .values_list('question_signature', flat=True))

        all_subtopics = SUBJECT_TOPICS[subject][topic]
        subtopics = random.sample(all_subtopics, min(
            3, len(all_subtopics))) if all_subtopics else []

        for attempt in range(self.max_retries):
            try:
                cached = [q for q in QuestionCache.get(cache_key)
                          if QuestionCache.generate_signature(q) not in seen_questions]

                if cached and random.random() < 0.3:  # 30% chance to use cached question
                    logger.info(f"Using cached question for {cache_key}")
                    question = random.choice(cached)
                    QuestionCache.add(cache_key, question)
                    self._record_question(user, question)
                    return question

                prompt = self._build_prompt(
                    grade, subject, topic, subtopics, level, revision, seen_questions)
                response = self.client.chat.completions.create(
                    model="gpt-4o",
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

                # ✅ NEW LOGIC: Ensure explanation supports correct answer
                if not self._validate_explanation_supports_answer(question_data['explanation'], question_data['correctAnswer']):
                    raise ValueError("Explanation does not logically support the correct answer")


                required_common_fields = [
                    'questionText', 'hint', 'explanation']
                for field in required_common_fields:
                    if field not in question_data:
                        raise ValueError(f"Missing required field: {field}")

                image_url = None
                image_generated = False
                try:
                    if grade >= 4 and 'imageType' in question_data and question_data['imageType']:
                        image_url, image_generated = self._generate_visual(
                            question_text=question_data.get(
                                "questionText", ""),
                            image_type=question_data['imageType'],
                            image_params=question_data.get("imageParams", {})
                        )
                    else:
                        image_url = None
                        image_generated = False
                except Exception as e:
                    logger.warning(
                        f"Image generation failed but continuing: {str(e)}")
                    image_url = None
                    image_generated = False

                question = {
                    "question_text": question_data['questionText'],
                    "options": question_data.get('options', []),
                    "correct_answer": question_data['correctAnswer'],
                    "hint": question_data['hint'],
                    "explanation": question_data['explanation'],
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
                logger.warning(
                    f"JSON decode error on attempt {attempt+1}: {str(e)}")
                continue
            except KeyError as e:
                logger.warning(f"Missing key in response: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Question generation error: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise RuntimeError(
                        "Failed to generate valid question after multiple attempts")
                continue

        raise RuntimeError("Exhausted all generation attempts")

    def _build_prompt(self, grade, subject, topic, subtopics, level, revision, seen_questions):
        text_visual_instruction = ""
        if grade <= 3:
            text_visual_instruction = (
            "For grades 1 to 3:\n"
            "- Use simple number-based questions or equations.\n"
            "- Avoid using emojis or visual symbols.\n"
            "- Focus on numeric reasoning, basic operations (e.g., 2 + 3, 5 - 1, etc.), comparisons, or simple word problems using only text.\n"
            "- Do not focus on scenarios based questions.\n "
            "- Ocasionally, include scenario-based questions.\n"
            "- Do not generate questions refering to images, diagrams, arrays, or figures unless they are clearly represented within the questionText.\n"
            "- Ensure the question is solvable by logic or calculation, not visuals.\n"
            "- Avoid phrases like 'look at the image', 'refer to the diagram', or 'see the array'.\n"
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
        - Math: For grades 1 to 3, focus on simple number equations or countable values. Use only numbers and euations in the content. No emojis, no references to diagrams unless included in the text.
        - English: For grades 1 to 3, Use only sentence-based or word-based questions. For grades 4+, use standard text.
        
        
        **Additional Instructions:**
        - For "multiple" type questions, provide 4 descriptive options (e.g., "80 degrees", "75 degrees" for math, or descriptive text for English).
        - For "input" type questions, provide 4 integer options (e.g., "80", "75", "90", "85") and ensure the correct answer is an integer.
        

        **Hint and Explanation Strict Rules:**
        - The "hint" must be directly relevant to the question asked. It should guide the student without giving away the full answer but must not be generic or unrelated.
        - Keep the explanation 3 to 5 lines max. Avoid over-explaining.
        - Under **no circumstance** should the explanation justify, validate, or mention incorrect options as being valid in any way.
        - The explanation must **only support the correctAnswer that is generated along with the question** and must not be vague, misleading, or conflict with the provided correct answer.
        - Any inconsistency between the correctAnswer and the explanation is considered invalid.
        - Ensure the explanation is clear, concise, and directly addresses the question asked.
        - Avoid using `pi`, `theta`, `lambda` in plain text. Always replace with `π`, `θ`, `λ`.
        - Do NOT use LaTeX or escape characters like \\( or \\), $...$, etc.
        - Format units cleanly: e.g., 4 cm × 5 cm = 20 cm².
        - Ensure all mathematical expressions are correctly formatted with symbols, not plain text (e.g., use '+' for addition, '×' for multiplication, '÷' for division, etc.).

        To help you understand the required format, here are some examples of correctly formatted explanations:

        1. For a question: 'What is the area of a rectangle with length 15 m and width 10 m?'

        Explanation: The area of a rectangle is calculated by multiplying its length by its width. So, area = 15 m × 10 m = 150 m².

        2. For a question: 'What is the area of a triangle with base 5 m and height 4 m?'

        Explanation: The area of a triangle is given by (1/2) × base × height. So, area = (1/2) × 5 m × 4 m = (1/2) × 20 m² = 10 m².

        3. For a question: 'Simplify 3 + 4 × 2'

        Explanation: First, perform the multiplication: 4 × 2 = 8. Then add 3: 3 + 8 = 11. So, 3 + 4 × 2 = 11.

        Make sure to use symbols like × for multiplication, + for addition, - for subtraction, ÷ for division, and ( ) for grouping. For fractions, use (numerator/denominator), like (1/2). For units, use m² for square meters, cm for centimeters, etc.
        

        **Correct Answer Calculation Rule:**
        - The correct answer must be **derived by performing logical or numerical calculations** based on the data or scenario provided in the question.
        - Do **not** choose the correct answer arbitrarily.
        - Ensure the explanation **clearly shows the steps or logic** used to arrive at the correct answer.
        - There must be **a direct connection** between:
        1. The values or context in the question,
        2. The steps described in the explanation,
        3. The final correct answer.
        - If a calculation or logical deduction cannot be shown clearly, **do not use such a question**.
        - You MUST verify that the correctAnswer matches the solution derived in the explanation. If it does not match, REJECT the question.

        
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
    

    def _validate_explanation_supports_answer(self, explanation, correct_answer):
        """
        Validates that the explanation supports the correct answer.
        Currently, this does a basic check to see if the correct answer
        is mentioned in the explanation.
        """
        normalized_explanation = explanation.lower().replace(',', '').strip()
        normalized_answer = str(correct_answer).lower().replace(',', '').strip()

        # Basic validation: answer must appear in explanation
        return normalized_answer in normalized_explanation

    def _generate_visual(self, question_text: str, image_type: str = None, image_params: dict = None) -> tuple[str, bool]:
        try:
            if image_type and image_type in DRAW_FUNCTIONS:
                draw_func = DRAW_FUNCTIONS[image_type]
                specific_params = image_params.get(image_type, {})
                validated_params = self._validate_image_params(
                    image_type, specific_params)
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
        print(f"Validated parameters for {image_type}: {validated}")
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

        raw_correct = str(question['correctAnswer']).strip()
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

        result = cloudinary.uploader.upload(
            buffer, folder='gradenext_questions')
        return result['secure_url']

    def _record_question(self, user, question):
        signature = QuestionCache.generate_signature(question)
        UserQuestionHistory.objects.update_or_create(
            user=user,
            question_signature=signature,
            defaults={'created_at': timezone.now()}
        )

    def _fallback_visual_generation(self, question_text: str) -> str:
        text = question_text.lower()

        shape_patterns = {
            'square': r'square|quadrilateral with equal sides',
            'triangle': r'triangle|three.?side',
            'circle': r'circle|radius|diameter'
        }

        for shape, pattern in shape_patterns.items():
            if re.search(pattern, text):
                return self._draw_geometric_shape({
                    'shape': shape,
                    'size': random.randint(3, 10)
                })

        measurement_patterns = [
            (r'length of (\d+).*width of (\d+)', 'rectangle'),
            (r'radius of (\d+)', 'circle'),
            (r'base of (\d+).*height of (\d+)', 'triangle')
        ]

        for pattern, image_type in measurement_patterns:
            match = re.search(pattern, text)
            if match:
                params = self._extract_measurement_params(match, image_type)
                return getattr(self, f'_draw_{image_type}')(params)

        concept_mapping = {
            'time': {'type': 'clock', 'params': {'hours': random.randint(1, 12)}},
            'fraction': {'type': 'fraction', 'params': {
                'numerator': random.randint(1, 5),
                'denominator': random.randint(2, 8)
            }},
            'graph': {'type': 'graph', 'params': {
                'type': 'bar',
                'labels': ['A', 'B', 'C', 'D'],
                'data': [random.randint(5, 20) for _ in range(4)]
            }}
        }

        for concept, config in concept_mapping.items():
            if concept in text:
                return getattr(self, f'_draw_{config["type"]}')(config["params"])

        return self._generate_text_based_fallback(question_text)

    def _extract_measurement_params(self, match, image_type):
        params = {}
        if image_type == 'rectangle':
            params = {
                'length': int(match.group(1)),
                'width': int(match.group(2))
            }
        elif image_type == 'circle':
            params = {'radius': int(match.group(1))}
        elif image_type == 'triangle':
            params = {
                'base': int(match.group(1)),
                'height': int(match.group(2))
            }
        return params

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