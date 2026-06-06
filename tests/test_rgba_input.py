import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src'))

import dxtex_wrapper
import numpy as np
import texture2ddecoder

# Test with RGBA input (what converter.py provides)
print("Test: Create RGBA input [R=128, G=128, B=255, A=255]")
print("This represents RGB=(128, 128, 255) which is purplish-blue normal map")

rgba_input = np.zeros((4, 4, 4), dtype=np.uint8)
rgba_input[:, :, 0] = 128  # R in RGBA
rgba_input[:, :, 1] = 128  # G
rgba_input[:, :, 2] = 255  # B
rgba_input[:, :, 3] = 255  # A

print(f"\nInput bytes (first pixel RGBA): {rgba_input[0, 0].tolist()}")

# Compress with DirectXTex (should swap to BGRA internally)
dds_bytes = dxtex_wrapper.compress_bc7(rgba_input.tobytes(), 4, 4, mipmaps=1)
tex_bytes = dxtex_wrapper.dds_to_tex(dds_bytes)

# Decode back (returns BGRA)
decoded = texture2ddecoder.decode_bc7(tex_bytes[80:], 4, 4)

# Check what we got back (BGRA format)
b, g, r, a = decoded[0], decoded[1], decoded[2], decoded[3]
print(f"\nDecoded bytes (first pixel BGRA): B={b}, G={g}, R={r}, A={a}")
print(f"As RGB this is: R={r}, G={g}, B={b}")

if b > 200 and r < 150:
    print("\n✓ PASS: Got blue as expected - RGBA→BGRA swap working correctly")
elif r > 200 and b < 150:
    print("\n❌ FAIL: Got red when we wanted blue - swap is wrong")
else:
    print(f"\n⚠ UNCLEAR: Got R={r}, B={b}")
