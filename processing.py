import os
import shutil
import json
import tempfile
from typing import List, Tuple, Optional, Callable, Dict, Set
from converter import read_tex_to_rgba, save_png_rgba, run_ispc_bc7, rgba_to_bgra_tex
from dxtex_wrapper import is_available as dxtex_is_available, compress_bcx as dxtex_compress_bc7, dds_to_tex as dxtex_dds_to_tex
from penumbrasettings import clone_config
from backup_manager import create_backup_manager
import numpy as np

LogFn = Callable[[str], None]


def build_texture_type_mapping_from_mtrls(mod_folder_path: str) -> Dict[str, str]:
    """
    Build a mapping of texture paths to their types by parsing all .mtrl files in the mod folder.
    
    This provides accurate texture type identification based on how materials actually use them,
    rather than relying on filename patterns.
    
    Args:
        mod_folder_path: Path to the mod folder
        
    Returns:
        Dictionary mapping texture paths (game paths and basenames) to texture types:
        {
            'chara/human/.../texture.tex': 'Normal',
            'texture.tex': 'Normal',
            ...
        }
    """
    try:
        from mod_file_mapper import parse_all_mtrl_files
        
        references = parse_all_mtrl_files(mod_folder_path)
        mapping = {}
        
        for ref in references:
            # Map both the full game path and just the basename
            # This allows matching against either full paths or just filenames
            mapping[ref.tex_path] = ref.texture_type
            basename = os.path.basename(ref.tex_path)
            if basename:
                # If multiple materials use same basename with different types,
                # prefer the more specific type (not 'Unknown')
                if basename not in mapping or mapping[basename] == 'Unknown':
                    mapping[basename] = ref.texture_type
        
        return mapping
    except Exception as e:
        # If mtrl parsing fails, return empty mapping (will fall back to name-based detection)
        return {}


def create_smart_categorize_function(mod_folder_path: str):
    """
    Create a categorization function that uses material file mappings as primary source,
    falling back to name-based detection for unmapped textures.
    
    Args:
        mod_folder_path: Path to the mod folder to scan for .mtrl files
        
    Returns:
        A categorization function that takes a filename and returns its type
    """
    # Build the mapping from .mtrl files
    mtrl_mapping = build_texture_type_mapping_from_mtrls(mod_folder_path)
    
    def categorize_with_mtrl_fallback(filename: str) -> str:
        """
        Categorize texture using mtrl mapping first, then fall back to name-based detection.
        """
        # Try exact match first (full path or basename)
        if filename in mtrl_mapping:
            tex_type = mtrl_mapping[filename]
            if tex_type != 'Unknown':
                return tex_type
        
        # Try basename match
        basename = os.path.basename(filename)
        if basename in mtrl_mapping:
            tex_type = mtrl_mapping[basename]
            if tex_type != 'Unknown':
                return tex_type
        
        # Fall back to name-based detection
        return _categorize_tex_from_name(filename)
    
    return categorize_with_mtrl_fallback


def _categorize_tex_from_name(filename: str) -> str:
    """
    Categorize texture based on filename patterns (fallback method).
    """
    name = filename.lower()
    if name.endswith('.tex'):
        name = name[:-4]
    
    # Check longer, more specific patterns first
    if any(s in name for s in ['_norm', '_normal']):
        return 'Normal'
    if any(s in name for s in ['_n.']):
        return 'Normal'
    
    if any(s in name for s in ['_index', '_id']):
        return 'ID'
    
    if any(s in name for s in ['_mask']):
        return 'Mask'
    
    if any(s in name for s in ['_diff', '_diffuse', '_base', '_d.']):
        return 'Diffuse'
    
    if any(s in name for s in ['_spec', '_specular', '_s.']):
        return 'Specular'
    
    # Check single-letter patterns at specific positions
    parts = name.split('_')
    for part in parts:
        if part == 'n':
            return 'Normal'
        if part == 'd':
            return 'Diffuse'
        if part == 's':
            return 'Specular'
        if part == 'm':
            return 'Mask'
    
    return 'Unknown'

# Target values for ID texture red channel
# These are the 16 quantization levels (in hex: 0x00, 0x10, 0x20, ..., 0xF0)
ID_TARGET_VALUES_HEX = [0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]
ID_TARGET_VALUES = [0, 17, 34, 51, 68, 85, 102, 119, 136, 153, 170, 187, 204, 221, 238, 255]
ID_TOLERANCE = 6


def quantize_id_red_channel(rgba: bytes, w: int, h: int, log: Optional[LogFn] = None) -> Tuple[bytes, bool]:
    """
    Quantize ID texture red channel values to perfect target values.
    
    Maps red channel values to the nearest exact target using defined ranges:
    0x00-0x08 -> 0x00 (0)
    0x09-0x19 -> 0x11 (17)
    0x1A-0x2A -> 0x22 (34)
    0x2B-0x3B -> 0x33 (51)
    0x3C-0x4C -> 0x44 (68)
    0x4D-0x5D -> 0x55 (85)
    0x5E-0x6E -> 0x66 (102)
    0x6F-0x7F -> 0x77 (119)
    0x80-0x90 -> 0x88 (136)
    0x91-0xA1 -> 0x99 (153)
    0xA2-0xB2 -> 0xAA (170)
    0xB3-0xC3 -> 0xBB (187)
    0xC4-0xD4 -> 0xCC (204)
    0xD5-0xE5 -> 0xDD (221)
    0xE6-0xF6 -> 0xEE (238)
    0xF7-0xFF -> 0xFF (255)
    
    Args:
        rgba: Original RGBA bytes
        w: Width of image
        h: Height of image
        log: Optional logging function
    
    Returns:
        Tuple of (new RGBA bytes with quantized red channel, has_edge_values_warning)
    """
    img = np.frombuffer(rgba, dtype=np.uint8).reshape((h, w, 4)).copy()
    red_channel = img[:, :, 0]
    
    
    ranges = [
        (0x00, 0x08, 0x00),   #   0-8   -> 0
        (0x09, 0x19, 0x11),   #   9-25  -> 17
        (0x1A, 0x2A, 0x22),   #  26-42  -> 34
        (0x2B, 0x3B, 0x33),   #  43-59  -> 51
        (0x3C, 0x4C, 0x44),   #  60-76  -> 68
        (0x4D, 0x5D, 0x55),   #  77-93  -> 85
        (0x5E, 0x6E, 0x66),   #  94-110 -> 102
        (0x6F, 0x7F, 0x77),   # 111-127 -> 119
        (0x80, 0x90, 0x88),   # 128-144 -> 136
        (0x91, 0xA1, 0x99),   # 145-161 -> 153
        (0xA2, 0xB2, 0xAA),   # 162-178 -> 170
        (0xB3, 0xC3, 0xBB),   # 179-195 -> 187
        (0xC4, 0xD4, 0xCC),   # 196-212 -> 204
        (0xD5, 0xE5, 0xDD),   # 213-229 -> 221
        (0xE6, 0xF6, 0xEE),   # 230-246 -> 238
        (0xF7, 0xFF, 0xFF),   # 247-255 -> 255
    ]
    
    # Check for problematic edge values where ranges overlap
    # Based on id_edgecases.txt - these are values that could map to wrong target
    bad_edge_values = [
        0x08,0x09,  # Could map to 0x00 or 0x11
        0x19,0x1A,  # Could map to 0x11 or 0x22
        0x2A,0x2B,  # Could map to 0x22 or 0x33
        0x3B,0x3C,  # Could map to 0x33 or 0x44
        0x4C,0x4D,  # Could map to 0x44 or 0x55
        0x5D,0x5E,  # Could map to 0x55 or 0x66
        0x6E,0x6F,  # Could map to 0x66 or 0x77
        0x7F,0x80,  # Could map to 0x77 or 0x88
        0x90,0x91,  # Could map to 0x88 or 0x99
        0xA1,0xA2,  # Could map to 0x99 or 0xAA
        0xB2,0xB3,  # Could map to 0xAA or 0xBB
        0xC3,0xC4,  # Could map to 0xBB or 0xCC
        0xD4,0xD5,  # Could map to 0xCC or 0xDD
        0xE5,0xE6,  # Could map to 0xDD or 0xEE
        0xF6,0xF7  # Could map to 0xEE or 0xFF
    ]
    
    edge_values_found = []
    for edge_val in bad_edge_values:
        if np.any(red_channel == edge_val):
            edge_values_found.append(f"0x{edge_val:02X}")
    
    has_warning = len(edge_values_found) > 0
    if has_warning and log:
        log(f"WARNING: ID texture has ambiguous edge values at range boundaries: {', '.join(edge_values_found)}")
    
    # Apply quantization
    quantized = np.zeros_like(red_channel)
    for min_val, max_val, target_val in ranges:
        mask = (red_channel >= min_val) & (red_channel <= max_val)
        quantized[mask] = target_val
    
    img[:, :, 0] = quantized
    return img.tobytes(), has_warning


def validate_id_red_channel(original_rgba: bytes, compressed_rgba: bytes, w: int, h: int) -> Tuple[bool, float]:
    """
    Validate that red channel values in ID texture remain within tolerance after BC7 compression.
    
    Compares compressed red channel directly against the quantized original.
    The original should already be quantized to target values before calling this function.
    
    Args:
        original_rgba: Quantized RGBA bytes before compression (already at target values)
        compressed_rgba: RGBA bytes after BC7 decompression
        w: Width of image
        h: Height of image
    
    Returns:
        Tuple of (is_valid, max_error) where is_valid is True if ALL pixels are within tolerance
    """
    orig = np.frombuffer(original_rgba, dtype=np.uint8).reshape((h, w, 4))
    comp = np.frombuffer(compressed_rgba, dtype=np.uint8).reshape((h, w, 4))
    
    # Extract red channels
    orig_red = orig[:, :, 0]
    comp_red = comp[:, :, 0]
    
    # Compare compressed against original (which is already quantized)
    # Calculate absolute differences
    errors = np.abs(comp_red.astype(np.int16) - orig_red.astype(np.int16))
    max_error = np.max(errors)
    
    # If ANY pixel exceeds tolerance, the texture fails validation
    is_valid = max_error <= ID_TOLERANCE
    return is_valid, float(max_error)


def downscale_nearest(rgba: bytes, w: int, h: int, target_w: int, target_h: int) -> bytes:
    """
    Downscale RGBA image using nearest-neighbor sampling (no interpolation).
    Preserves exact pixel values by sampling without averaging.
    """
    if w == target_w and h == target_h:
        return rgba
    
    # Convert to numpy array for easier indexing
    img = np.frombuffer(rgba, dtype=np.uint8).reshape((h, w, 4))
    
    # Create output array
    out = np.zeros((target_h, target_w, 4), dtype=np.uint8)
    
    # Calculate sampling ratios
    x_ratio = w / target_w
    y_ratio = h / target_h
    
    # Sample pixels without interpolation
    for y in range(target_h):
        for x in range(target_w):
            src_x = int(x * x_ratio)
            src_y = int(y * y_ratio)
            out[y, x] = img[src_y, src_x]
    
    return out.tobytes()


def calculate_target_size(w: int, h: int, mode: str, value: float) -> Tuple[int, int]:
    """
    Calculate target dimensions based on downscale mode.
    
    Args:
        w, h: Original dimensions
        mode: "Fixed size (px)", "Fixed ratio (%)", "Ceil (px)", "Relative ratio (%)"
        value: The numeric value from UI
    
    Returns:
        (target_width, target_height)
    """
    if mode == "Fixed size (px)":
        # Both dimensions become the fixed value
        target = max(1, int(value))
        return (target, target)
    
    elif mode == "Fixed ratio (%)":
        # Scale both dimensions by percentage
        ratio = max(0.01, value / 100.0)
        return (max(1, int(w * ratio)), max(1, int(h * ratio)))
    
    elif mode == "Ceil (px)":
        # Clamp larger dimension to ceiling value
        ceil_val = max(1, int(value))
        if w > h:
            if w > ceil_val:
                ratio = ceil_val / w
                return (ceil_val, max(1, int(h * ratio)))
        else:
            if h > ceil_val:
                ratio = ceil_val / h
                return (max(1, int(w * ratio)), ceil_val)
        return (w, h)  # No change if under ceiling
    
    elif mode == "Relative ratio (%)":
        # Scale based on original size tiers
        # TODO: Implement size-dependent scaling logic
        ratio = max(0.01, value / 100.0)
        return (max(1, int(w * ratio)), max(1, int(h * ratio)))
    
    return (w, h)  # No change by default


def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _collect_all_tex(root: str) -> List[str]:
    paths: List[str] = []
    for r, _d, files in os.walk(root):
        for f in files:
            if f.lower().endswith('.tex'):
                paths.append(os.path.normpath(os.path.join(r, f)))
    return paths


def _update_meta_name_atomic(meta_path: str, log: LogFn):
    try:
        if not os.path.isfile(meta_path):
            log('meta.json not found in copied mod; skipped update')
            return
        # Detect BOM to preserve original encoding
        with open(meta_path, 'rb') as fb:
            raw = fb.read()
        has_bom = raw.startswith(b'\xef\xbb\xbf')
        text = raw.decode('utf-8-sig' if has_bom else 'utf-8')
        data = json.loads(text)
        name = data.get('Name') or data.get('name')
        if not isinstance(name, str):
            log('meta.json Name not a string; skipped update')
            return
        if name.endswith('[Downscaled]') or name.endswith(' [Downscaled]'):
            # Already suffixed
            return
        new_name = name + ' [Downscaled]'
        if 'Name' in data:
            data['Name'] = new_name
        else:
            data['name'] = new_name
        # Write to a temp file first, then replace to avoid empty files on error
        temp_path = meta_path + '.tmp'
        dump_text = json.dumps(data, ensure_ascii=False, indent=2)
        with open(temp_path, 'w', encoding=('utf-8-sig' if has_bom else 'utf-8')) as fw:
            fw.write(dump_text)
        os.replace(temp_path, meta_path)
        log("Updated meta.json Name with [Downscaled]")
    except Exception as e:
        log(f"Failed to update meta.json: {e}")


def _copy_mod_with_suffix(src_mod: str, suffix: str, log: LogFn) -> Optional[str]:
    src_mod = os.path.normpath(src_mod)
    parent = os.path.dirname(src_mod.rstrip(os.sep))
    src_name = os.path.basename(src_mod.rstrip(os.sep))
    dest_name = src_name if src_name.endswith(suffix) else f"{src_name}{suffix}"
    dest_mod = os.path.normpath(os.path.join(parent, dest_name))
    try:
        shutil.copytree(src_mod, dest_mod, dirs_exist_ok=True)
        log(f"Copied mod folder -> {dest_mod}")
    except Exception as e:
        log(f"Failed to copy mod folder: {e}")
        return None

    # Update meta.json Name field if present
    meta_path = os.path.join(dest_mod, 'meta.json')
    _update_meta_name_atomic(meta_path, log)
    
    # Clone Penumbra collection settings from original to copy
    try:
        if clone_config(src_name, dest_name):
            log(f"Cloned Penumbra settings: {src_name} -> {dest_name}")
        else:
            log(f"No Penumbra settings found for '{src_name}' to clone")
    except Exception as e:
        log(f"Warning: Failed to clone Penumbra settings: {e}")
    
    return dest_mod


def _collect_from_tree_all(tex_tree) -> List[str]:
    # Reads all rows from QTreeWidget, using the Path column (index 1)
    result: List[str] = []
    for i in range(tex_tree.topLevelItemCount()):
        item = tex_tree.topLevelItem(i)
        rel_path = item.text(1)
        if rel_path:
            result.append(rel_path)
    return result


def _collect_from_tree_selected(tex_tree) -> Optional[str]:
    sel = tex_tree.selectedItems()
    if not sel:
        return None
    item = sel[0]
    rel_path = item.text(1)
    return rel_path or None


def _build_mod_folder(base_mods_path: str, selected_mod_display: str, build_mod_folder_map) -> Optional[str]:
    mod_map = build_mod_folder_map(base_mods_path)
    return mod_map.get(selected_mod_display)

def save_tex_file(tex_path: str, tex_bytes: bytes):
    _ensure_dir(tex_path)
    with open(tex_path, 'wb') as f:
        f.write(tex_bytes)

def process_textures(scope: str,
                     saving: str,
                     other_folder_path: str,
                     base_mods_path: str,
                     selected_mod_display: Optional[str],
                     tex_tree,
                     build_mod_folder_map,
                     log: LogFn,
                     enabled_types: Optional[set] = None,
                     categorize_fn: Optional[Callable[[str], str]] = None,
                     format_mode: Optional[str] = None,
                     downscale_mode: Optional[str] = None,
                     downscale_value: float = 100.0,
                     cancel_check: Optional[Callable[[], bool]] = None,
                     align_id_ranges: bool = False) -> Tuple[int, int]:
    """
    Process textures with a clean workflow:
    1. Create temp copy of mod folder
    2. Process all files in-place within temp
    3. Commit changes back to original (in-place mode) or to new location (copy mode)
    
    Returns (processed_count, copied_count)
    """
    scope = (scope or '').lower()
    saving = (saving or '').lower()
    inplace = saving.startswith('modify')
    
    # Step 1: Determine source mod and collect file list
    if scope == 'all files':
        if not selected_mod_display:
            log('No mod selected')
            return (0, 0)
        mod_folder = _build_mod_folder(base_mods_path, selected_mod_display, build_mod_folder_map)
        if not mod_folder or not os.path.isdir(mod_folder):
            log('Mod folder not found')
            return (0, 0)
        rel_paths = _collect_from_tree_all(tex_tree)
        
    elif scope == 'selected file':
        if not selected_mod_display:
            log('No mod selected')
            return (0, 0)
        mod_folder = _build_mod_folder(base_mods_path, selected_mod_display, build_mod_folder_map)
        if not mod_folder or not os.path.isdir(mod_folder):
            log('Mod folder not found')
            return (0, 0)
        rp = _collect_from_tree_selected(tex_tree)
        if not rp:
            log('No texture selected')
            return (0, 0)
        rel_paths = [rp]
        
    elif scope == 'other folder':
        log('Other folder scope not yet supported in refactored version')
        return (0, 0)
        
    else:
        log(f'Unknown scope: {scope}')
        return (0, 0)
    
    if not rel_paths:
        log('No textures to process')
        return (0, 0)
    
    # Step 2: Create temp working copy of entire mod folder
    temp_root = tempfile.mkdtemp(prefix='xiv_downscale_')
    temp_mod_folder = os.path.join(temp_root, os.path.basename(mod_folder))
    
    try:
        log(f'Creating temporary working copy...')
        shutil.copytree(mod_folder, temp_mod_folder)
        log(f'Working in temp: {temp_mod_folder}')
        
        # Step 3: Process all files in-place within temp copy
        processed = 0
        quantized_ids = set()  # Track quantized ID textures
        
        for rel in rel_paths:
            if cancel_check and cancel_check():
                log('Processing cancelled by user')
                return (0, 0)
            
            work_path = os.path.join(temp_mod_folder, rel)
            if not os.path.isfile(work_path):
                log(f'File not found: {rel}')
                continue
            
            # Filter by enabled types
            if enabled_types and categorize_fn:
                file_type = categorize_fn(os.path.basename(rel)).lower()
                if file_type not in enabled_types:
                    continue
            else:
                file_type = categorize_fn(os.path.basename(rel)).lower() if categorize_fn else ''
            
            # Apply ID alignment if enabled
            if align_id_ranges and file_type == 'id':
                decoded = read_tex_to_rgba(work_path, log)
                if decoded:
                    rgba, w, h = decoded
                    quantized_rgba, _ = quantize_id_red_channel(rgba, w, h, None)  # Suppress warnings
                    tex_bytes = rgba_to_bgra_tex(quantized_rgba, w, h)
                    with open(work_path, 'wb') as f:
                        f.write(tex_bytes)
                    quantized_ids.add(work_path)
                    log(f'Aligned ID ranges: {rel}')
                    
                    if cancel_check and cancel_check():
                        log('Processing cancelled by user')
                        return (0, 0)
            
            # Determine if we should process this file based on format_mode
            mode = (format_mode or '').strip().lower()
            convert_this = False
            
            if mode.startswith('same as'):
                convert_this = False
            elif mode.startswith('bc7 (artifact'):
                convert_this = file_type in ('diffuse', 'normal', 'specular')
            elif mode.startswith('bc7 (yolo'):
                convert_this = file_type in ('diffuse', 'normal', 'specular', 'id', 'mask')
            elif mode.startswith('smart (artifact'):
                convert_this = file_type in ('diffuse', 'normal', 'specular', 'id', 'mask')
            elif mode.startswith('smart (yolo'):
                convert_this = file_type in ('diffuse', 'normal', 'specular', 'id', 'mask')
            
            if not convert_this:
                continue
            
            # Decode texture
            decoded = read_tex_to_rgba(work_path, log)
            if not decoded:
                log(f'Failed to decode: {rel}')
                continue
            
            rgba, w, h = decoded
            
            if cancel_check and cancel_check():
                log('Processing cancelled by user')
                return (0, 0)
            
            # Apply downscaling if enabled
            if downscale_mode and downscale_mode != "None":
                skip_small = (w <= 32 or h <= 32) and scope != 'selected file'
                if not skip_small:
                    target_w, target_h = calculate_target_size(w, h, downscale_mode, downscale_value)
                    if target_w != w or target_h != h:
                        log(f'Downscaling {rel} from {w}x{h} to {target_w}x{target_h}')
                        rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                        w, h = target_w, target_h
                        
                        if cancel_check and cancel_check():
                            log('Processing cancelled by user')
                            return (0, 0)
            
            # Apply BC7 compression or special handling
            if file_type == 'id' and dxtex_is_available():
                # ID texture: compress to BC7, quantize, compare, decide format
                try:
                    dds_bytes = dxtex_compress_bc7(rgba, w, h, mipmaps=1)
                    tex_bytes_bc7 = dxtex_dds_to_tex(dds_bytes)
                    
                    # Quantize original (skip if already done)
                    if work_path in quantized_ids:
                        quantized_rgba = rgba
                    else:
                        quantized_rgba, _ = quantize_id_red_channel(rgba, w, h, log)
                        log(f'Quantized ID texture: {rel}')
                    
                    # Decompress BC7 and compare
                    import texture2ddecoder
                    comp_bgra = texture2ddecoder.decode_bc7(dds_bytes[128:], w, h)
                    comp_rgba = bytearray(comp_bgra)
                    for i in range(0, len(comp_rgba), 4):
                        comp_rgba[i], comp_rgba[i+2] = comp_rgba[i+2], comp_rgba[i]
                    
                    is_valid, max_error = validate_id_red_channel(quantized_rgba, bytes(comp_rgba), w, h)
                    
                    if is_valid:
                        # Use BC7
                        with open(work_path, 'wb') as f:
                            f.write(tex_bytes_bc7)
                        log(f'ID texture BC7 compressed (error: {max_error:.1f}): {rel}')
                    else:
                        # Use RGBA8
                        tex_bytes = rgba_to_bgra_tex(quantized_rgba, w, h)
                        with open(work_path, 'wb') as f:
                            f.write(tex_bytes)
                        log(f'ID texture kept as RGBA8 (error: {max_error:.1f}): {rel}')
                    
                    processed += 1
                    
                except Exception as e:
                    log(f'ID texture processing failed for {rel}: {e}')
                    # Fallback to quantized RGBA8
                    if work_path not in quantized_ids:
                        quantized_rgba, _ = quantize_id_red_channel(rgba, w, h, log)
                    tex_bytes = rgba_to_bgra_tex(quantized_rgba, w, h)
                    with open(work_path, 'wb') as f:
                        f.write(tex_bytes)
                    processed += 1
                    
            elif dxtex_is_available():
                # Standard BC7 compression
                try:
                    dds_bytes = dxtex_compress_bc7(rgba, w, h, mipmaps=1)
                    tex_bytes = dxtex_dds_to_tex(dds_bytes)
                    with open(work_path, 'wb') as f:
                        f.write(tex_bytes)
                    log(f'BC7 compressed: {rel}')
                    processed += 1
                except Exception as e:
                    log(f'BC7 compression failed for {rel}: {e}')
            else:
                log(f'DirectXTex not available, skipped: {rel}')
            
            if cancel_check and cancel_check():
                log('Processing cancelled by user')
                return (0, 0)
        
        # Step 4: Commit changes
        if inplace:
            # In-place: backup files before overwriting, then copy processed files back
            log(f'Creating backups before committing changes...')
            backup_mgr = create_backup_manager(base_mods_path)
            if backup_mgr:
                files_to_backup = [rel for rel in rel_paths if os.path.isfile(os.path.join(mod_folder, rel))]
                backup_success, backup_failed = backup_mgr.backup_files(mod_folder, files_to_backup)
                log(f'Backed up {backup_success} files ({backup_failed} failed)')
            else:
                log('Warning: Backup manager not available')
            
            log(f'Committing changes to original mod folder...')
            for rel in rel_paths:
                src_file = os.path.join(temp_mod_folder, rel)
                dst_file = os.path.join(mod_folder, rel)
                if os.path.isfile(src_file):
                    try:
                        shutil.copy2(src_file, dst_file)
                    except Exception as e:
                        log(f'Failed to copy back {rel}: {e}')
            log(f'Done. Processed: {processed}')
            return (processed, 0)
        else:
            # Copy mode: create new mod folder with suffix
            suffix = ' [Downscaled]'
            dest_mod = _copy_mod_with_suffix(mod_folder, suffix, log)
            if not dest_mod:
                return (0, 0)
            
            # Copy processed files from temp to new location
            log(f'Copying processed files to new mod folder...')
            for rel in rel_paths:
                src_file = os.path.join(temp_mod_folder, rel)
                dst_file = os.path.join(dest_mod, rel)
                if os.path.isfile(src_file):
                    try:
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        shutil.copy2(src_file, dst_file)
                    except Exception as e:
                        log(f'Failed to copy {rel}: {e}')
            log(f'Done. Processed: {processed}, Copied to new mod')
            return (processed, processed)
    
    finally:
        # Cleanup temp directory
        if os.path.exists(temp_root):
            try:
                shutil.rmtree(temp_root)
                log('Cleaned up temp directory')
            except Exception as e:
                log(f'Failed to cleanup temp: {e}')



