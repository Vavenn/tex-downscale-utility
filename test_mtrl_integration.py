"""Test script for mtrl-based texture categorization"""

from processing import build_texture_type_mapping_from_mtrls
from mod_browser import categorize_tex, build_mtrl_mapping_for_mod

test_path = r'e:\XIVMODS\[178] Octia'

print("=" * 70)
print("Testing MTRL-Based Texture Categorization Integration")
print("=" * 70)

# Build mapping
print("\n[1] Building texture type mapping from .mtrl files...")
mapping = build_mtrl_mapping_for_mod(test_path)
print(f"    Built mapping with {len(mapping)} entries")

if mapping:
    print("\n[2] Sample mappings:")
    for i, (k, v) in enumerate(list(mapping.items())[:5]):
        print(f"    {k}: {v}")

# Test categorization
print("\n[3] Testing categorize_tex with mapping...")
result1 = categorize_tex('c0201h0178_hir_norm.tex', test_path, mapping)
print(f"    c0201h0178_hir_norm.tex -> {result1}")

result2 = categorize_tex('c0201h0178_hir_mask.tex', test_path, mapping)
print(f"    c0201h0178_hir_mask.tex -> {result2}")

result3 = categorize_tex('scalpn.tex', test_path, mapping)
print(f"    scalpn.tex -> {result3}")

# Test fallback for unknown texture
print("\n[4] Testing fallback for unmapped texture...")
result4 = categorize_tex('random_normal.tex', test_path, mapping)
print(f"    random_normal.tex (fallback) -> {result4}")

result5 = categorize_tex('random_unknown.tex', test_path, mapping)
print(f"    random_unknown.tex (fallback) -> {result5}")

print("\n" + "=" * 70)
print("Integration test complete!")
print("=" * 70)
