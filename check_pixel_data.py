from PIL import Image

# Check what the decoded BC7 file actually contains
img = Image.open('test_uniform_normal_bc7.png')
pixels = img.load()

# Check first pixel
r, g, b, a = pixels[0, 0]
print(f"First pixel of test_uniform_normal_bc7.png: R={r}, G={g}, B={b}, A={a}")

# Check original
img_orig = Image.open('test_uniform_normal_original.png')
pixels_orig = img_orig.load()
r_orig, g_orig, b_orig, a_orig = pixels_orig[0, 0]
print(f"First pixel of test_uniform_normal_original.png: R={r_orig}, G={g_orig}, B={b_orig}, A={a_orig}")

print(f"\nExpected: R=128, G=128, B=255, A=255 (purplish-blue)")
print(f"If we got: R=255, G=128, B=128, A=255 (reddish) then R and B are still swapped")
