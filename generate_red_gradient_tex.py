"""
Generate a 1024x1024 RGBA8 TEX file with 256 squares.
Each square shows an incrementing red value (0-255).
"""
import numpy as np
from converter import rgba_to_bgra_tex

def generate_red_gradient_grid():
    """
    Create a 1024x1024 image divided into 256 squares (16x16 grid).
    Each square has a unique red value from 0 to 255.
    """
    size = 1024
    grid_size = 16  # 16x16 = 256 squares
    square_size = size // grid_size  # 64x64 pixels per square
    
    # Create RGBA image (1024x1024x4)
    img = np.zeros((size, size, 4), dtype=np.uint8)
    
    # Fill each square with incrementing red values
    red_value = 0
    for row in range(grid_size):
        for col in range(grid_size):
            y_start = row * square_size
            y_end = y_start + square_size
            x_start = col * square_size
            x_end = x_start + square_size
            
            # Set red channel to current value
            img[y_start:y_end, x_start:x_end, 0] = red_value
            # Green and blue = 0, alpha = 255
            img[y_start:y_end, x_start:x_end, 3] = 255
            
            red_value += 1
    
    return img.tobytes(), size, size

if __name__ == '__main__':
    print("Generating 1024x1024 red gradient grid...")
    rgba_bytes, width, height = generate_red_gradient_grid()
    
    output_path = 'red_gradient_grid.tex'
    print(f"Creating TEX file: {output_path}")
    
    # Generate TEX file bytes and write to disk
    tex_bytes = rgba_to_bgra_tex(rgba_bytes, width, height)
    with open(output_path, 'wb') as f:
        f.write(tex_bytes)
    
    print(f"✓ Created {output_path}")
    print(f"  - Size: {width}x{height}")
    print(f"  - Format: RGBA8/BGRA8")
    print(f"  - Content: 256 squares (16x16 grid) with red values 0-255")
