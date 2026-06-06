import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src'))

import numpy as np
from processing import downscale_nearest
from PIL import Image

# Create a test pattern: 8x8 pixels with distinct colors
print("Creating 8x8 test pattern...")
img = np.zeros((8, 8, 4), dtype=np.uint8)

# Make a checkerboard pattern (red and blue squares)
for y in range(8):
    for x in range(8):
        if (x // 2 + y // 2) % 2 == 0:
            img[y, x] = [255, 0, 0, 255]  # Red
        else:
            img[y, x] = [0, 0, 255, 255]  # Blue

# Save original
img_orig = Image.fromarray(img, 'RGBA')
img_orig.save('downscale_test_8x8.png')
print("Saved: downscale_test_8x8.png")

# Downscale to 4x4 (should keep every other pixel)
print("\nDownscaling 8x8 -> 4x4...")
downscaled_bytes = downscale_nearest(img.tobytes(), 8, 8, 4, 4)
downscaled = np.frombuffer(downscaled_bytes, dtype=np.uint8).reshape((4, 4, 4))

# Save downscaled
img_down = Image.fromarray(downscaled, 'RGBA')
img_down.save('downscale_test_4x4.png')
print("Saved: downscale_test_4x4.png")

# Verify it's nearest neighbor (no blending)
print("\nVerifying no color blending...")
unique_colors = set()
for y in range(4):
    for x in range(4):
        color = tuple(downscaled[y, x])
        unique_colors.add(color)
        print(f"  Pixel ({x},{y}): {color}")

print(f"\nUnique colors found: {len(unique_colors)}")
if len(unique_colors) == 2:
    print("✓ PASS: Only pure red and blue (no blending)")
else:
    print("❌ FAIL: Found intermediate colors (blending occurred)")
