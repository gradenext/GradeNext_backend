# utils/image_utils.py (updated)
import io
import base64
from PIL import Image, ImageDraw, ImageFont
import cloudinary.uploader
import random

def create_pillow_image_with_text(text: str, size=(600, 300), bg_color="white", 
                                text_color="black", accent_color=None):
    """
    Generate an image with given text and optional decorative elements
    Returns the image object
    """
    img = Image.new("RGB", size, color=bg_color)
    draw = ImageDraw.Draw(img)

    # Add decorative elements if accent color provided
    if accent_color:
        # Header bar
        draw.rectangle([(0, 0), (size[0], 15)], fill=accent_color)
        # Side border
        draw.rectangle([(size[0]-20, 0), (size[0], size[1])], fill=accent_color)
        # Decorative circle
        draw.ellipse([(size[0]-50, size[1]-50), (size[0]-10, size[1]-10)], 
                    fill=accent_color)

    try:
        font = ImageFont.truetype("arial.ttf", 28) 
    except IOError:
        font = ImageFont.load_default()

    # Text positioning
    text_lines = text.split('\n')
    y_position = (size[1] - (font.size * len(text_lines))) // 2

    for line in text_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x_position = (size[0] - text_width) // 2
        draw.text((x_position, y_position), line, fill=text_color, font=font)
        y_position += font.size + 5

    return img

def upload_pillow_image_to_cloudinary(img: Image.Image, public_id=None):
    """
    Upload a Pillow Image object directly to Cloudinary
    Returns the secure URL of the uploaded image
    """
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    result = cloudinary.uploader.upload(
        img_buffer,
        resource_type="image",
        public_id=public_id,
        overwrite=True,
        folder="gradenext_question_images",
        quality=80,
        transformation=[
            {"width": 800, "height": 600, "crop": "limit"},
            {"quality": "auto:good"}
        ]
    )
    return result.get("secure_url")

def generate_quickchart_url(chart_config: dict):
    """
    Generate QuickChart URL with error handling
    """
    import urllib.parse
    import json
    
    try:
        base_url = "https://quickchart.io/chart"
        config_json = json.dumps(chart_config)
        params = urllib.parse.urlencode({"c": config_json, "w": 800, "h": 600})
        return f"{base_url}?{params}"
    except Exception as e:
        print(f"Failed to generate chart URL: {str(e)}")
        return None