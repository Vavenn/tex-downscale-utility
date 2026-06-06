import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src'))

# Test the calculate_target_size function
from processing import calculate_target_size

# Test with original size
w, h = 2048, 2048

print("Testing calculate_target_size:")
print(f"Original: {w}x{h}")
print()

modes = [
    ("Fixed size (px)", 256),
    ("Fixed ratio (%)", 50),
    ("Ceil (px)", 512),
    ("Relative ratio (%)", 50),
]

for mode, value in modes:
    target_w, target_h = calculate_target_size(w, h, mode, value)
    print(f"{mode} with value {value}: {target_w}x{target_h}")
