import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src'))

from parsers.tex import Tex
from io import BytesIO
from kaitaistruct import KaitaiStream
import texture2ddecoder
from PIL import Image

# Check the problematic file
tex_path = r"E:\XIVMODS\Ace Combat JPEG Dog [Downscaled]\chara\monster\m8058\obj\body\b0001\texture\unknown_b_n.tex"

with open(tex_path, 'rb') as f:
    tex_data = f.read()

tex = Tex(KaitaiStream(BytesIO(tex_data)))
print(f"Texture info:")
print(f"  Dimensions: {tex.hdr.width}x{tex.hdr.height}")
print(f"  Format: 0x{tex.hdr.format:04x} ({tex.hdr.format})")
print(f"  Type: 0x{tex.hdr.type:08x}")

# Decode
pixels = tex_data[80:]
decoded = texture2ddecoder.decode_bc7(pixels, tex.hdr.width, tex.hdr.height)

# Check first few pixels (decoded is BGRA)
print(f"\nFirst 4 pixels (BGRA format):")
for i in range(4):
    b = decoded[i*4 + 0]
    g = decoded[i*4 + 1]
    r = decoded[i*4 + 2]
    a = decoded[i*4 + 3]
    print(f"  Pixel {i}: B={b}, G={g}, R={r}, A={a}")

# Create image with BGRA interpretation
img = Image.frombytes('RGBA', (tex.hdr.width, tex.hdr.height), decoded, 'raw', 'BGRA')
img.save('problem_texture_decoded.png')
print(f"\nSaved as problem_texture_decoded.png")

# Check pixel data
pixels_check = img.load()
r, g, b, a = pixels_check[0, 0]
print(f"First pixel in PNG: R={r}, G={g}, B={b}, A={a}")
print(f"Expected for normal map: R=128, G=128, B=255 (purplish-blue)")
