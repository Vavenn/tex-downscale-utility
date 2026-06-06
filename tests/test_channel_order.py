import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src'))

import dxtex_wrapper
import numpy as np
from parsers.tex import Tex
from io import BytesIO
from kaitaistruct import KaitaiStream
import texture2ddecoder

# Create a simple test: pure red pixel
print("Creating 4x4 pure red BGRA texture...")
rgba = np.zeros((4, 4, 4), dtype=np.uint8)
rgba[:, :, 0] = 0    # B
rgba[:, :, 1] = 0    # G
rgba[:, :, 2] = 255  # R (pure red)
rgba[:, :, 3] = 255  # A

print("Input BGRA bytes (first pixel):", rgba[0, 0].tolist())

# Compress with DirectXTex
dds_bytes = dxtex_wrapper.compress_bc7(rgba.tobytes(), 4, 4, mipmaps=1)
tex_bytes = dxtex_wrapper.dds_to_tex(dds_bytes)

with open('test_red_pixel.tex', 'wb') as f:
    f.write(tex_bytes)

# Now decode and check
tex = Tex(KaitaiStream(BytesIO(tex_bytes)))
pixels = tex_bytes[80:]
decoded = texture2ddecoder.decode_bc7(pixels, 4, 4)

# Check first pixel (4 bytes)
first_pixel = [decoded[i] for i in range(4)]
print("Decoded bytes (first pixel):", first_pixel)
print("Expected: [255, 0, 0, 255] for RGBA red")
print("Got BGRA if: [0, 0, 255, 255]")
