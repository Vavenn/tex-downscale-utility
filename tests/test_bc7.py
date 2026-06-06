#!/usr/bin/env python3
"""Quick test of DirectXTex BC7 wrapper"""

from dxtex_wrapper import is_available, compress_bc7, dds_to_tex

print("Testing DirectXTex BC7 wrapper...")
print(f"DLL available: {is_available()}")

if is_available():
    # Create a small 64x64 red test texture (BGRA format)
    width, height = 64, 64
    rgba = bytearray()
    for _ in range(width * height):
        rgba.extend([0, 0, 255, 255])  # BGRA: Blue=0, Green=0, Red=255, Alpha=255
    
    print(f"\nCompressing {width}x{height} BGRA texture to BC7...")
    try:
        dds_bytes = compress_bc7(bytes(rgba), width, height, mipmaps=1)
        print(f"  DDS size: {len(dds_bytes)} bytes")
        
        print("Converting DDS to TEX format...")
        tex_bytes = dds_to_tex(dds_bytes)
        print(f"  TEX size: {len(tex_bytes)} bytes (80-byte header + compressed pixels)")
        
        output_path = "test_bc7_output.tex"
        with open(output_path, 'wb') as f:
            f.write(tex_bytes)
        print(f"  Wrote: {output_path}")
        print("\nSuccess! BC7 compression working.")
        
    except Exception as e:
        print(f"Error during compression: {e}")
else:
    print("\nDLL not found. Make sure DirectXTex.dll is in DirectXTex/bin/x64/Release/")
