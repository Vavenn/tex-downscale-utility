import texture2ddecoder
import numpy as np

# Test what format texture2ddecoder returns
# Create a simple BC7 block manually or check documentation

print("Testing texture2ddecoder.decode_bc7 output format...")
print("\nLet's check if it returns RGBA or BGRA by examining real game files...")

# The issue: BC7 stores data in a specific channel order
# texture2ddecoder might be decoding to BGRA format
# We need to determine what format it actually returns

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src'))

from parsers.tex import Tex
from io import BytesIO
from kaitaistruct import KaitaiStream

# Test with the working game file
working_file = r"E:\XIVMODS\Bibo+ (2)\Core Files_ Skin Multi Maps\Skin Multi Maps\chara\bibo_hroth_mask_v02.tex"
if os.path.exists(working_file):
    with open(working_file, 'rb') as f:
        tex_data = f.read()
    
    tex = Tex(KaitaiStream(BytesIO(tex_data)))
    pixels = tex_data[80:]
    decoded = texture2ddecoder.decode_bc7(pixels, tex.hdr.width, tex.hdr.height)
    
    # Sample a few pixels
    print(f"\nWorking BC7 file: {tex.hdr.width}x{tex.hdr.height}")
    print("First pixel (4 bytes):", [decoded[i] for i in range(4)])
    print("Second pixel (4 bytes):", [decoded[i] for i in range(4, 8)])
    
    print("\nIf texture2ddecoder returns BGRA, we need to swap when displaying")
    print("If it returns RGBA, our compression is wrong")
