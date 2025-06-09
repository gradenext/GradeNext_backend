from PIL import Image, ImageDraw, ImageFont
import random
import math
from quickchart import QuickChart
from .image_utils import upload_pillow_image_to_cloudinary  # Assuming image_utils.py is in the same package

def draw_ruler(length=10, units=1, unit_length=20):
    """
    Draws a ruler with the specified length and units.
    
    :param length: Total length of the ruler.
    :param units: Number of units per major tick.
    :param unit_length: Length of each unit in pixels.
    :return: URL of the uploaded image.
    """
    img_width = length * unit_length + 100  # Add padding
    img_height = 50
    img = Image.new("RGB", (img_width, img_height), "white")
    draw = ImageDraw.Draw(img)
    
    # Draw the ruler line
    draw.line([(50, 25), (50 + length * unit_length, 25)], fill="black", width=2)
    
    # Draw ticks and labels
    for i in range(length + 1):
        x = 50 + i * unit_length
        draw.line([(x, 20), (x, 30)], fill="black", width=1)
        if i % units == 0:
            draw.text((x - 10, 35), str(i), fill="black")
    
    return upload_pillow_image_to_cloudinary(img)

def draw_number_line(start=0, end=10, step=1, highlight=None):
    """
    Draws a number line with the specified range and optional highlight.
    
    :param start: Starting number of the number line.
    :param end: Ending number of the number line.
    :param step: Step size between numbers.
    :param highlight: Optional number to highlight.
    :return: URL of the uploaded image.
    """
    img_width = (end - start) * 20 + 100  # 20 pixels per unit
    img_height = 50
    img = Image.new("RGB", (img_width, img_height), "white")
    draw = ImageDraw.Draw(img)
    
    # Draw the line
    x_start = 50
    x_end = x_start + (end - start) * 20
    draw.line([(x_start, 25), (x_end, 25)], fill="black", width=2)
    
    # Draw ticks and labels
    current = start
    while current <= end:
        x = x_start + (current - start) * 20
        draw.line([(x, 20), (x, 30)], fill="black", width=1)
        draw.text((x - 10, 35), str(current), fill="black")
        if highlight and current == highlight:
            draw.line([(x, 15), (x, 35)], fill="red", width=3)
        current += step
    
    return upload_pillow_image_to_cloudinary(img)

def draw_fraction_bar(numerator, denominator):
    """
    Draws a fraction bar with the given numerator and denominator.
    
    :param numerator: Numerator of the fraction.
    :param denominator: Denominator of the fraction.
    :return: URL of the uploaded image.
    """
    img_width = 200
    img_height = 50
    img = Image.new("RGB", (img_width, img_height), "white")
    draw = ImageDraw.Draw(img)
    
    # Draw the bar
    bar_width = 180
    bar_height = 30
    draw.rectangle([(10, 10), (10 + bar_width, 10 + bar_height)], outline="black", width=2)
    
    # Divide into denominator parts
    part_width = bar_width / denominator
    for i in range(1, denominator):
        x = 10 + i * part_width
        draw.line([(x, 10), (x, 10 + bar_height)], fill="black", width=1)
    
    # Shade numerator parts
    shade_width = (numerator / denominator) * bar_width
    draw.rectangle([(10, 10), (10 + shade_width, 10 + bar_height)], fill="blue")
    
    return upload_pillow_image_to_cloudinary(img)

def draw_angle(degrees=90):
    """
    Draws an angle with the specified degrees.
    
    :param degrees: Angle in degrees.
    :return: URL of the uploaded image.
    """
    img_size = 200
    img = Image.new("RGB", (img_size, img_size), "white")
    draw = ImageDraw.Draw(img)
    
    # Draw two rays from origin
    center = (100, 100)
    # First ray along x-axis
    draw.line([center, (200, 100)], fill="black", width=2)
    # Second ray at given angle
    angle_rad = math.radians(degrees)
    end_x = 100 + 100 * math.cos(angle_rad)
    end_y = 100 - 100 * math.sin(angle_rad)  # y is inverted
    draw.line([center, (end_x, end_y)], fill="black", width=2)
    
    # Label the angle
    draw.text((120, 80), f"{degrees}°", fill="black")
    
    return upload_pillow_image_to_cloudinary(img)

def draw_cube():
    """
    Draws a simple 3D cube.
    
    :return: URL of the uploaded image.
    """
    img_size = 200
    img = Image.new("RGB", (img_size, img_size), "white")
    draw = ImageDraw.Draw(img)
    
    # Draw front face
    draw.polygon([(50, 50), (150, 50), (150, 150), (50, 150)], outline="black", width=2)
    # Draw top face
    draw.polygon([(50, 50), (150, 50), (120, 20), (20, 20)], outline="black", width=2)
    # Draw side face
    draw.polygon([(50, 150), (150, 150), (120, 170), (20, 170)], outline="black", width=2)
    
    return upload_pillow_image_to_cloudinary(img)

def draw_translation(shape="square", dx=50, dy=50):
    """
    Draws a shape and its translation.
    
    :param shape: Shape to translate (e.g., "square").
    :param dx: Translation distance along x-axis.
    :param dy: Translation distance along y-axis.
    :return: URL of the uploaded image.
    """
    img_size = 300
    img = Image.new("RGB", (img_size, img_size), "white")
    draw = ImageDraw.Draw(img)
    
    # Original shape
    if shape == "square":
        draw.rectangle([(50, 50), (100, 100)], outline="black", width=2)
    
    # Translated shape
    new_x1 = 50 + dx
    new_y1 = 50 + dy
    new_x2 = 100 + dx
    new_y2 = 100 + dy
    draw.rectangle([(new_x1, new_y1), (new_x2, new_y2)], outline="red", width=2)
    
    # Arrows to indicate translation
    draw.line([(100, 100), (100 + dx/2, 100 + dy/2)], fill="green", width=1)
    draw.line([(100, 100), (100 + dx/2, 100)], fill="green", width=1)
    draw.line([(100, 100), (100, 100 + dy/2)], fill="green", width=1)
    
    return upload_pillow_image_to_cloudinary(img)

def draw_scale_drawing(scale=2):
    """
    Draws a shape and its scaled version.
    
    :param scale: Scaling factor.
    :return: URL of the uploaded image.
    """
    img_size = 300
    img = Image.new("RGB", (img_size, img_size), "white")
    draw = ImageDraw.Draw(img)
    
    # Original square
    draw.rectangle([(50, 50), (100, 100)], outline="black", width=2)
    
    # Scaled square
    size = 50 * scale
    draw.rectangle([(150, 50), (150 + size, 50 + size)], outline="red", width=2)
    
    return upload_pillow_image_to_cloudinary(img)

def draw_graph(type='bar', labels=None, data=None, label="Data Series"):
    """
    Draws a graph using QuickChart.
    
    :param type: Type of graph (e.g., 'bar', 'line', 'pie').
    :param labels: Labels for the graph.
    :param data: Data points for the graph.
    :param label: Label for the dataset.
    :return: URL of the graph image.
    """
    if labels is None:
        labels = ["A", "B", "C", "D"]
    if data is None:
        data = [12, 19, 3, 5]
    
    chart_config = {
        "type": type,
        "data": {
            "labels": labels,
            "datasets": [{
                "label": label,
                "data": data,
                "backgroundColor": [
                    f"rgb({random.randint(0,255)}, {random.randint(0,255)}, {random.randint(0,255)})"
                    for _ in range(len(labels))
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

def draw_circle(radius=5):
    """
    Draws a circle with the given radius.
    
    :param radius: Radius of the circle.
    :return: URL of the uploaded image.
    """
    img_size = 200
    img = Image.new("RGB", (img_size, img_size), "white")
    draw = ImageDraw.Draw(img)
    
    center = (100, 100)
    draw.ellipse([(center[0] - radius*10, center[1] - radius*10), (center[0] + radius*10, center[1] + radius*10)], outline="black", width=2)
    
    return upload_pillow_image_to_cloudinary(img)

def draw_right_triangle(a=3, b=4, c=5):
    """
    Draws a right triangle with sides a, b (legs), and c (hypotenuse).
    
    :param a: Length of the first leg.
    :param b: Length of the second leg.
    :param c: Length of the hypotenuse.
    :return: URL of the uploaded image.
    """
    img_size = 200
    img = Image.new("RGB", (img_size, img_size), "white")
    draw = ImageDraw.Draw(img)
    
    p1 = (50, 150)  # Bottom left
    p2 = (50 + a*20, 150)  # Bottom right
    p3 = (50, 150 - b*20)  # Top left
    
    draw.line([p1, p2], fill="black", width=2)
    draw.line([p1, p3], fill="black", width=2)
    draw.line([p2, p3], fill="black", width=2)
    
    # Label sides
    draw.text((50 + a*20/2, 150 + 10), f"{c}", fill="black")  # Hypotenuse
    draw.text((50 - 10, 150 - b*20/2), f"{b}", fill="black")  # Vertical leg
    draw.text((50 + a*20/2, 150 - 10), f"{a}", fill="black")  # Horizontal leg
    
    return upload_pillow_image_to_cloudinary(img)