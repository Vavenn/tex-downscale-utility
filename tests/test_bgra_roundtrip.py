import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src'))

import dxtex_wrapper
import numpy as np
import texture2ddecoder

# Test: Create uniform normal map color (128, 128, 255) in BGRA
print("Test: Create BGRA input [B=255, G=128, R=128, A=255]")
print("This represents RGB=(128, 128, 255) which is purplish-blue normal map")

rgba_bgra = np.zeros((4, 4, 4), dtype=np.uint8)
rgba_bgra[:, :, 0] = 255  # B in BGRA
rgba_bgra[:, :, 1] = 128  # G
rgba_bgra[:, :, 2] = 128  # R
rgba_bgra[:, :, 3] = 255  # A

print(f"\nInput bytes (first pixel BGRA): {rgba_bgra[0, 0].tolist()}")

# Compress with DirectXTex
dds_bytes = dxtex_wrapper.compress_bc7(rgba_bgra.tobytes(), 4, 4, mipmaps=1)
tex_bytes = dxtex_wrapper.dds_to_tex(dds_bytes)

# Decode back
decoded = texture2ddecoder.decode_bc7(tex_bytes[80:], 4, 4)

# Check what we got back (BGRA format)
b, g, r, a = decoded[0], decoded[1], decoded[2], decoded[3]
print(f"\nDecoded bytes (first pixel BGRA): B={b}, G={g}, R={r}, A={a}")
print(f"As RGB this is: R={r}, G={g}, B={b}")

if r > 200 and b < 150:
    print("\n❌ FAIL: Got red when we wanted blue - channels ARE swapped")
elif b > 200 and r < 150:
    print("\n✓ PASS: Got blue as expected - channels are correct")
else:
    print(f"\n⚠ UNCLEAR: Got R={r}, B={b} - might be compression artifact")
