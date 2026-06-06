import ctypes
import os
import sys
from typing import Optional, Tuple

# Windows-only DirectXTex wrapper (ctypes-based placeholder)
# Needs stoopid dll

_dll: Optional[ctypes.CDLL] = None


def _get_base_path():
    """Get the base path for resources, handling PyInstaller bundled mode."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in PyInstaller bundle
        return sys._MEIPASS
    else:
        # Running in normal Python
        return os.path.dirname(__file__)


def _load_dxtex_dll(custom_path: Optional[str] = None) -> Optional[ctypes.CDLL]:
    global _dll
    if _dll:
        return _dll
    
    base_path = _get_base_path()
    
    candidates = []
    if custom_path:
        candidates.append(custom_path)
    
    # Search paths for the DLL
    candidates.extend([
        # PyInstaller bundle path
        os.path.join(base_path, 'DirectXTex', 'bin', 'x64', 'release', 'DirectXTex.dll'),
        # Development paths
        os.path.join(os.path.dirname(__file__), 'DirectXTex', 'bin', 'x64', 'Release', 'DirectXTex.dll'),
        os.path.join(os.path.dirname(__file__), 'DirectXTex', 'bin', 'x64', 'release', 'DirectXTex.dll'),
        os.path.join(os.path.dirname(__file__), 'DirectXTex', 'DirectXTex.dll'),
    ])
    
    for path in candidates:
        if os.path.exists(path):
            try:
                _dll = ctypes.CDLL(path)
                return _dll
            except OSError as e:
                # Try to continue searching
                pass
    return None


def is_available() -> bool:
    return _load_dxtex_dll() is not None


class DXTexError(Exception):
    pass


# Placeholder signatures; the actual exported C interface must match.
# We will define a simple C ABI to avoid C++ name mangling.
# See README for the C shim that exposes:
#   int dxtex_compress_bc7(const uint8_t* rgba, int width, int height, int mipmaps, uint8_t** out_dds, size_t* out_size);
#   int dxtex_compress_bcx(const uint8_t* rgba, int width, int height, int mipmaps, int format, uint8_t** out_dds, size_t* out_size);
#   void dxtex_free(void* ptr);
#   int dxtex_dds_to_tex(const uint8_t* dds, size_t dds_size, uint8_t** out_tex, size_t* out_size);

# BCX format constants (matching DXGI_FORMAT enum values)
BC1_UNORM = 71      # DXGI_FORMAT_BC1_UNORM (DXT1)
BC2_UNORM = 74      # DXGI_FORMAT_BC2_UNORM (DXT3)
BC3_UNORM = 77      # DXGI_FORMAT_BC3_UNORM (DXT5)
BC4_UNORM = 80      # DXGI_FORMAT_BC4_UNORM
BC5_UNORM = 83      # DXGI_FORMAT_BC5_UNORM
BC7_UNORM = 98      # DXGI_FORMAT_BC7_UNORM
RGBA8_UNORM = 28    # DXGI_FORMAT_R8G8B8A8_UNORM


def compress_bcx(rgba: bytes, width: int, height: int, bc_format: int, mipmaps: int = 1) -> bytes:
    """
    Compress RGBA data to BCx format using DirectXTex.
    
    Args:
        rgba: Raw RGBA pixel data (width * height * 4 bytes)
        width: Image width
        height: Image height
        bc_format: BC format constant (BC1_UNORM, BC2_UNORM, BC3_UNORM, BC4_UNORM, BC5_UNORM, BC7_UNORM)
        mipmaps: Number of mipmap levels to generate (default 1)
    
    Returns:
        DDS file bytes
    """
    dll = _load_dxtex_dll()
    if not dll:
        raise DXTexError('DirectXTex.dll not found. Build and place it in DirectXTex/bin/x64/Release.')

    # Try generic bcx function first, fall back to bc7-specific if not available
    try:
        fn = dll.dxtex_compress_bcx
        fn.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
        fn.restype = ctypes.c_int
        use_generic = True
    except AttributeError:
        if bc_format != BC7_UNORM:
            raise DXTexError('dxtex_compress_bcx not exported from DirectXTex.dll. Only BC7 is available with legacy DLL.')
        # Fall back to BC7-only function
        fn = dll.dxtex_compress_bc7
        fn.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
        fn.restype = ctypes.c_int
        use_generic = False

    try:
        free_fn = dll.dxtex_free
        free_fn.argtypes = [ctypes.c_void_p]
        free_fn.restype = None
    except AttributeError:
        raise DXTexError('dxtex_free not exported from DirectXTex.dll. Build the C shim.')

    rgba_buf = ctypes.create_string_buffer(rgba)
    out_ptr = ctypes.c_void_p()
    out_size = ctypes.c_size_t()
    
    if use_generic:
        rc = fn(ctypes.cast(rgba_buf, ctypes.c_void_p), width, height, mipmaps, bc_format, 
                ctypes.byref(out_ptr), ctypes.byref(out_size))
    else:
        rc = fn(ctypes.cast(rgba_buf, ctypes.c_void_p), width, height, mipmaps,
                ctypes.byref(out_ptr), ctypes.byref(out_size))
    
    if rc != 0:
        format_names = {BC1_UNORM: 'BC1', BC2_UNORM: 'BC2', BC3_UNORM: 'BC3', 
                       BC4_UNORM: 'BC4', BC5_UNORM: 'BC5', BC7_UNORM: 'BC7'}
        fmt_name = format_names.get(bc_format, f'BCx({bc_format})')
        raise DXTexError(f'{fmt_name} compression failed with code {rc}.')

    # Copy output bytes
    size = out_size.value
    out_bytes = ctypes.string_at(out_ptr.value, size)
    free_fn(out_ptr)
    return out_bytes


def compress_bc7(rgba: bytes, width: int, height: int, mipmaps: int = 1) -> bytes:
    """Legacy BC7 compression function for backwards compatibility."""
    return compress_bcx(rgba, width, height, BC7_UNORM, mipmaps)


def dds_to_tex(dds_bytes: bytes) -> bytes:
    dll = _load_dxtex_dll()
    if not dll:
        raise DXTexError('DirectXTex.dll not found. Build and place it in DirectXTex/bin/x64/Release.')

    try:
        fn = dll.dxtex_dds_to_tex
        fn.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
        fn.restype = ctypes.c_int
        free_fn = dll.dxtex_free
    except AttributeError:
        raise DXTexError('dxtex_dds_to_tex or dxtex_free not exported from DirectXTex.dll. Build the C shim.')

    dds_buf = ctypes.create_string_buffer(dds_bytes)
    out_ptr = ctypes.c_void_p()
    out_size = ctypes.c_size_t()
    rc = fn(ctypes.cast(dds_buf, ctypes.c_void_p), ctypes.c_size_t(len(dds_bytes)), ctypes.byref(out_ptr), ctypes.byref(out_size))
    if rc != 0:
        raise DXTexError(f'DDS->TEX conversion failed with code {rc}.')

    size = out_size.value
    out_bytes = ctypes.string_at(out_ptr.value, size)
    free_fn(out_ptr)
    return out_bytes
