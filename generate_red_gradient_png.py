"""
Generate a 1024x1024 PNG with 256 squares.
Each square shows its red value as text (0-255 in decimal).
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def generate_labeled_red_gradient_grid():
    """
    Create a 1024x1024 image divided into 256 squares (16x16 grid).
    Each square has a unique red value and displays the value as text.
    """
    size = 1024
    grid_size = 16  # 16x16 = 256 squares
    square_size = size // grid_size  # 64x64 pixels per square
    
    # Create RGBA image (1024x1024x4)
    img_array = np.zeros((size, size, 4), dtype=np.uint8)
    
    # Fill each square with incrementing red values
    red_value = 0
    for row in range(grid_size):
        for col in range(grid_size):
            y_start = row * square_size
            y_end = y_start + square_size
            x_start = col * square_size
            x_end = x_start + square_size
            
            # Set red channel to current value
            img_array[y_start:y_end, x_start:x_end, 0] = red_value
            # Green and blue = 0, alpha = 255
            img_array[y_start:y_end, x_start:x_end, 3] = 255
            
            red_value += 1
    
    # Convert to PIL Image for drawing text
    img = Image.fromarray(img_array, mode='RGBA')
    draw = ImageDraw.Draw(img)
    
    # Try to load a font, fall back to default if not available
    try:
        # Try to use a reasonable sized font (20pt = 25% bigger than 16pt)
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        try:
            font = ImageFont.truetype("segoeui.ttf", 20)
        except:
            # Use default font
            font = ImageFont.load_default()
    
    # Draw text on each square
    red_value = 0
    for row in range(grid_size):
        for col in range(grid_size):
            x_center = col * square_size + square_size // 2
            y_center = row * square_size + square_size // 2
            
            text = str(red_value)
            
            # Get text bounding box to center it
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            text_x = x_center - text_width // 2
            text_y = y_center - text_height // 2
            
            # Pure white text
            text_color = (255, 255, 255, 255)
            
            draw.text((text_x, text_y), text, fill=text_color, font=font)
            
            red_value += 1
    
    return img

if __name__ == '__main__':
    print("Generating 1024x1024 labeled red gradient grid...")
    
    img = generate_labeled_red_gradient_grid()
    
    output_path = 'red_gradient_grid_labeled.png'
    print(f"Saving PNG file: {output_path}")
    
    img.save(output_path)
    
    print(f"✓ Created {output_path}")
    print(f"  - Size: 1024x1024")
    print(f"  - Format: PNG (RGBA)")
    print(f"  - Content: 256 squares (16x16 grid) with red values 0-255")
    print(f"  - Each square displays its red value as text")
