import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src'))

from parsers.tex import Tex
from io import BytesIO
from PIL import Image
import texture2ddecoder
from kaitaistruct import KaitaiStream

def decode_tex_to_png(tex_path, png_path):
    """Decode a BC7 TEX file and save as PNG"""
    with open(tex_path, 'rb') as f:
        tex_data = f.read()
    
    tex = Tex(KaitaiStream(BytesIO(tex_data)))
    width = tex.hdr.width
    height = tex.hdr.height
    
    # Decode BC7
    pixels = tex_data[80:]  # Skip 80-byte header
    decoded = texture2ddecoder.decode_bc7(pixels, width, height)
    
    # texture2ddecoder returns BGRA, but PIL expects RGBA
    # Create PIL image with BGRA raw mode
    img = Image.frombytes('RGBA', (width, height), decoded, 'raw', 'BGRA')
    img.save(png_path)
    print(f"Decoded {tex_path} -> {png_path} ({width}x{height})")

# Decode all three BC7 test files
decode_tex_to_png('test_spectrum_bc7.tex', 'test_spectrum_bc7.png')
decode_tex_to_png('test_uniform_normal_bc7.tex', 'test_uniform_normal_bc7.png')
decode_tex_to_png('test_small_uniform_bc7.tex', 'test_small_uniform_bc7.png')

print("\nAll BC7 textures decoded to PNG!")
