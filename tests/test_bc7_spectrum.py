import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src'))

import dxtex_wrapper
import numpy as np
from parsers.tex import Tex
from io import BytesIO
from PIL import Image

def create_spectrum_texture(width, height):
    """Create a texture with full hue spectrum"""
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    
    for y in range(height):
        for x in range(width):
            # Full hue spectrum across width
            hue = (x / width) * 360
            
            # Convert HSV to RGB (saturation=1, value=1)
            h = hue / 60.0
            c = 1.0
            x_val = c * (1 - abs(h % 2 - 1))
            
            if h < 1:
                r, g, b = c, x_val, 0
            elif h < 2:
                r, g, b = x_val, c, 0
            elif h < 3:
                r, g, b = 0, c, x_val
            elif h < 4:
                r, g, b = 0, x_val, c
            elif h < 5:
                r, g, b = x_val, 0, c
            else:
                r, g, b = c, 0, x_val
            
            # Add brightness gradient across height
            brightness = y / height
            
            rgba[y, x, 0] = int(b * brightness * 255)  # BGRA order
            rgba[y, x, 1] = int(g * brightness * 255)
            rgba[y, x, 2] = int(r * brightness * 255)
            rgba[y, x, 3] = 255
    
    return rgba

def create_uniform_texture(width, height, r, g, b, a):
    """Create a uniform color texture"""
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[:, :, 0] = b  # BGRA order
    rgba[:, :, 1] = g
    rgba[:, :, 2] = r
    rgba[:, :, 3] = a
    return rgba

# Test 1: Full spectrum
print("Creating full spectrum texture (256x256)...")
spectrum = create_spectrum_texture(256, 256)

# Save original PNG
img = Image.frombytes('RGBA', (256, 256), spectrum.tobytes(), 'raw', 'BGRA')
img.save('test_spectrum_original.png')
print("Saved test_spectrum_original.png")

# Compress and save TEX
# Test 2: Normal map uniform color (128, 128, 255, 255)
print("\nCreating uniform normal map texture (128x128)...")
normal = create_uniform_texture(128, 128, 128, 128, 255, 255)

# Save original PNG
img = Image.frombytes('RGBA', (128, 128), normal.tobytes(), 'raw', 'BGRA')
img.save('test_uniform_normal_original.png')
print("Saved test_uniform_normal_original.png")

# Compress and save TEX
dds_bytes = dxtex_wrapper.compress_bc7(normal.tobytes(), 128, 128, mipmaps=1)
tex_bytes = dxtex_wrapper.dds_to_tex(dds_bytes)

with open('test_uniform_normal_bc7.tex', 'wb') as f:
    f.write(tex_bytes)
print(f"Wrote test_uniform_normal_bc7.tex ({len(tex_bytes)} bytes)")
normal = create_uniform_texture(128, 128, 128, 128, 255, 255)
# Test 3: Small uniform texture like the problematic one (16x16)
print("\nCreating small uniform normal map texture (16x16)...")
small_normal = create_uniform_texture(16, 16, 128, 128, 255, 255)

# Save original PNG
img = Image.frombytes('RGBA', (16, 16), small_normal.tobytes(), 'raw', 'BGRA')
img.save('test_small_uniform_original.png')
print("Saved test_small_uniform_original.png")

# Compress and save TEX
dds_bytes = dxtex_wrapper.compress_bc7(small_normal.tobytes(), 16, 16, mipmaps=1)
tex_bytes = dxtex_wrapper.dds_to_tex(dds_bytes)

with open('test_small_uniform_bc7.tex', 'wb') as f:
    f.write(tex_bytes)
print(f"Wrote test_small_uniform_bc7.tex ({len(tex_bytes)} bytes)")

print("\nTest files created! Check the PNG files in your browser.")
tex_bytes = dxtex_wrapper.dds_to_tex(dds_bytes)

with open('test_small_uniform_bc7.tex', 'wb') as f:
    f.write(tex_bytes)
print(f"Wrote test_small_uniform_bc7.tex ({len(tex_bytes)} bytes)")

print("\nTest files created! Load them in your viewer to check compression quality.")
