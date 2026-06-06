import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src'))

import dxtex_wrapper
import numpy as np

# Simple test without DLL - just verify input format
print("Testing input format...")
rgba = np.zeros((2, 2, 4), dtype=np.uint8)

# Pixel 0,0: Pure Red
rgba[0, 0, 0] = 0    # B
rgba[0, 0, 1] = 0    # G
rgba[0, 0, 2] = 255  # R
rgba[0, 0, 3] = 255  # A

# Pixel 0,1: Pure Green
rgba[0, 1, 0] = 0    # B
rgba[0, 1, 1] = 255  # G
rgba[0, 1, 2] = 0    # R
rgba[0, 1, 3] = 255  # A

# Pixel 1,0: Pure Blue
rgba[1, 0, 0] = 255  # B
rgba[1, 0, 1] = 0    # G
rgba[1, 0, 2] = 0    # R
rgba[1, 0, 3] = 255  # A

bytes_data = rgba.tobytes()
print(f"\nInput bytes (16 bytes total, 4 pixels × 4 channels):")
for i in range(0, len(bytes_data), 4):
    print(f"Pixel {i//4}: [{bytes_data[i]}, {bytes_data[i+1]}, {bytes_data[i+2]}, {bytes_data[i+3]}]")

print("\nExpected input format: BGRA")
print("After C++ swap should be: RGBA")
print("After BC7 decode should return: RGBA")

# Check DLL timestamp
dll_path = os.path.join(os.path.dirname(__file__), 'DirectXTex', 'bin', 'x64', 'Release', 'DirectXTex.dll')
if os.path.exists(dll_path):
    import datetime
    mtime = os.path.getmtime(dll_path)
    print(f"\nDLL last modified: {datetime.datetime.fromtimestamp(mtime)}")
else:
    print(f"\nDLL not found at: {dll_path}")
