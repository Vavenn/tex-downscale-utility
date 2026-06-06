import os
import subprocess
from PIL import Image
import numpy as np
from typing import Optional, Tuple, Callable
from dxtex_wrapper import compress_bcx, BC1_UNORM, BC3_UNORM, BC5_UNORM, BC7_UNORM, RGBA8_UNORM
LogFn = Callable[[str], None]


def find_ispc_texcomp() -> Optional[str]:
    # Try common names/locations; otherwise rely on PATH
    candidates = [
        os.path.join(os.getcwd(), 'ispc_texcomp.exe'),
        os.path.join(os.getcwd(), 'tools', 'ispc_texcomp.exe'),
        'ispc_texcomp.exe',
    ]
    for c in candidates:
        try:
            # If just a name, let subprocess resolve via PATH
            if os.path.isabs(c) and not os.path.isfile(c):
                continue
            return c
        except Exception:
            continue
    return None


def run_ispc_bc7(input_path: str, output_path: str, yolo: bool, log: LogFn) -> bool:
    exe = find_ispc_texcomp()
    if not exe:
        log('ispc_texcomp.exe not found (add to PATH or place in project root/tools)')
        return False
    # Flags: -d for output DDS, -f BC7; quality presets vary by build.
    # Using -mips to generate full mip chain might be desirable later.
    args = [exe, '-d', output_path, '-f', 'BC7', input_path]
    if yolo:
        # Placeholder: yolo mode could imply faster preset or fewer safety checks
        args.append('--fast')
    try:
        subprocess.run(args, check=True)
        log(f'BC7 encode: {os.path.basename(input_path)} -> {os.path.basename(output_path)}')
        return True
    except subprocess.CalledProcessError as e:
        log(f'BC7 encoder failed: {e}')
        return False


def save_png_rgba(temp_png: str, rgba_bytes: bytes, w: int, h: int) -> None:

    arr = np.frombuffer(rgba_bytes, dtype='uint8').reshape((h, w, 4))
    im = Image.fromarray(arr, mode='RGBA')
    im.save(temp_png)

def decode_rgba_from_raw(raw_data: bytes, w: int, h: int, fmt: int, log: LogFn) -> Optional[Tuple[bytes, int, int]]:
    """
    Decode raw texture data to RGBA bytes given format.
    
    Args:
        raw_data: Raw compressed/uncompressed texture bytes
        w: Width
        h: Height
        fmt: Texture format enum value
        log: Logging function
    
    Returns:
        Tuple of (rgba_bytes, width, height) or None if unsupported
    """
    import importlib.util
    import sys
    
    # Handle PyInstaller bundled mode
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        tex_parser_path = os.path.join(sys._MEIPASS, 'FFXIV Tex Converter', 'src', 'parsers', 'tex.py')
    else:
        tex_parser_path = os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src', 'parsers', 'tex.py')
    spec = importlib.util.spec_from_file_location('ffxiv_tex', tex_parser_path)
    tex_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tex_module)
    
    from texture2ddecoder import (
        decode_bc1, decode_bc3, decode_bc4, decode_bc5, decode_bc7
    )

    if fmt in (tex_module.Tex.Header.TextureFormat.b8g8r8a8,
                tex_module.Tex.Header.TextureFormat.b8g8r8x8):
        expected = w * h * 4
        raw = raw_data[:expected]
        bgra = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 4))
        rgba = np.ascontiguousarray(bgra[..., [2, 1, 0, 3]])
        return rgba.tobytes(), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.l8:
        expected = w * h
        raw = raw_data[:expected]
        gray = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 1))
        rgb = np.repeat(gray, 3, axis=2)
        a = np.full_like(gray, 255)
        rgba = np.concatenate([rgb, a], axis=2)
        return rgba.tobytes(), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.a8:
        expected = w * h
        raw = raw_data[:expected]
        a = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 1))
        rgb = np.full_like(a, 255)
        rgba = np.concatenate([rgb, rgb, rgb, a], axis=2)
        return rgba.tobytes(), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.dxt1:
        bgra = decode_bc1(raw_data, w, h)
        return _bgra_to_rgba_bytes(bgra), w, h
    elif fmt in (tex_module.Tex.Header.TextureFormat.dxt3,
                    tex_module.Tex.Header.TextureFormat.dxt5):
        bgra = decode_bc3(raw_data, w, h)
        return _bgra_to_rgba_bytes(bgra), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.ati1:
        bgra = decode_bc4(raw_data, w, h)
        return _bgra_to_rgba_bytes(bgra), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.ati2:
        bgra = decode_bc5(raw_data, w, h)
        return _bgra_to_rgba_bytes(bgra), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.bc7:
        bgra = decode_bc7(raw_data, w, h)
        return _bgra_to_rgba_bytes(bgra), w, h
    else:
        log(f'Unsupported TEX format for decode: {fmt}')
        return None

def read_tex_to_rgba(tex_path: str, log: LogFn) -> Optional[Tuple[bytes, int, int]]:
    # Decode TEX to RGBA using the existing Kaitai + texture2ddecoder path from preview
    # Minimal duplication to avoid GUI dependencies
    import io
    import importlib.util
    import numpy as np
    from kaitaistruct import KaitaiStream
    import sys

    # Handle PyInstaller bundled mode
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        tex_parser_path = os.path.join(sys._MEIPASS, 'FFXIV Tex Converter', 'src', 'parsers', 'tex.py')
    else:
        tex_parser_path = os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src', 'parsers', 'tex.py')
    spec = importlib.util.spec_from_file_location('ffxiv_tex', tex_parser_path)
    tex_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tex_module)

    with open(tex_path, 'rb') as f:
        tex_data = f.read()
    tex_obj = tex_module.Tex(KaitaiStream(io.BytesIO(tex_data)))
    w = tex_obj.hdr.width
    h = tex_obj.hdr.height
    fmt = tex_obj.hdr.format

    from texture2ddecoder import (
        decode_bc1, decode_bc3, decode_bc4, decode_bc5, decode_bc7
    )

    if fmt in (tex_module.Tex.Header.TextureFormat.b8g8r8a8,
               tex_module.Tex.Header.TextureFormat.b8g8r8x8):
        expected = w * h * 4
        raw = tex_obj.bdy.data[:expected]
        bgra = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 4))
        rgba = np.ascontiguousarray(bgra[..., [2, 1, 0, 3]])
        return rgba.tobytes(), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.l8:
        expected = w * h
        raw = tex_obj.bdy.data[:expected]
        gray = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 1))
        rgb = np.repeat(gray, 3, axis=2)
        a = np.full_like(gray, 255)
        rgba = np.concatenate([rgb, a], axis=2)
        return rgba.tobytes(), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.a8:
        expected = w * h
        raw = tex_obj.bdy.data[:expected]
        a = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 1))
        rgb = np.full_like(a, 255)
        rgba = np.concatenate([rgb, rgb, rgb, a], axis=2)
        return rgba.tobytes(), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.dxt1:
        bgra = decode_bc1(tex_obj.bdy.data, w, h)
        return _bgra_to_rgba_bytes(bgra), w, h
    elif fmt in (tex_module.Tex.Header.TextureFormat.dxt3,
                 tex_module.Tex.Header.TextureFormat.dxt5):
        bgra = decode_bc3(tex_obj.bdy.data, w, h)
        return _bgra_to_rgba_bytes(bgra), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.ati1:
        bgra = decode_bc4(tex_obj.bdy.data, w, h)
        return _bgra_to_rgba_bytes(bgra), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.ati2:
        bgra = decode_bc5(tex_obj.bdy.data, w, h)
        return _bgra_to_rgba_bytes(bgra), w, h
    elif fmt == tex_module.Tex.Header.TextureFormat.bc7:
        bgra = decode_bc7(tex_obj.bdy.data, w, h)
        return _bgra_to_rgba_bytes(bgra), w, h
    else:
        log(f'Unsupported TEX format for decode: {fmt}')
        return None


def _bgra_to_rgba_bytes(bgra: bytes) -> bytes:
    if not bgra:
        return b''
    b = bytearray(bgra)
    for i in range(0, len(b), 4):
        bb, gg, rr, aa = b[i:i+4]
        b[i:i+4] = bytes([rr, gg, bb, aa])
    return bytes(b)

def rgba_to_bgra_tex(rgba: bytes, w: int, h: int, saving_path: Optional[str] = None) -> bytes:
    """
    Convert RGBA bytes to TEX format with BGRA8 pixel format.
    Creates an 80-byte header followed by BGRA pixel data.
    
    Args:
        rgba: RGBA pixel data
        w: Width
        h: Height
    
    Returns:
        Complete TEX file bytes
    """
    import struct
    import numpy as np

    
    # Convert RGBA to BGRA
    img = np.frombuffer(rgba, dtype=np.uint8).reshape((h, w, 4))
    bgra = np.ascontiguousarray(img[..., [2, 1, 0, 3]])
    bgra_bytes = bgra.tobytes()
    
    # Create TEX header (80 bytes total)
    # Based on TEX format structure from tex.ksy
    header = bytearray(80)
    struct.pack_into('<I', header, 0, 0x00800000)  # Attribute (aligned_size flag)
    struct.pack_into('<I', header, 4, 0x00001450)  # Format (0x1450 = BGRA8, type = 0x0000)
    struct.pack_into('<H', header, 8, w)           # Width
    struct.pack_into('<H', header, 10, h)          # Height
    struct.pack_into('<H', header, 12, 1)          # Depth
    struct.pack_into('<H', header, 14, 1)          # Mip levels
    # lod_offset3: always 0, 1, 2
    struct.pack_into('<I', header, 16, 0)
    struct.pack_into('<I', header, 20, 1)
    struct.pack_into('<I', header, 24, 2)
    # offset_to_surface13: first mip offset is 80 (header size), rest are 0
    struct.pack_into('<I', header, 28, 80)         # First mip offset
    for i in range(1, 13):
        struct.pack_into('<I', header, 28 + i * 4, 0)  # Remaining offsets = 0
    
    if saving_path:
        with open(saving_path, 'wb') as f:
            f.write(header)
            f.write(bgra_bytes)

    return bytes(header) + bgra_bytes
