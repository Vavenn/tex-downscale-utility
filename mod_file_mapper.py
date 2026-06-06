"""
Module for parsing Penumbra mod JSON files and mapping texture file replacements.

This module extracts mappings between in-game paths and actual file paths
from Penumbra mod group JSON files, specifically tracking .tex files.
It also parses .mtrl (material) files to extract texture references.
"""

import json
import os
from typing import Dict, List, Tuple, Optional, Set
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TextureReference:
    """Texture reference extracted from a material file"""
    tex_path: str  # Path to the .tex file
    mtrl_path: str  # Path to the .mtrl file that references it
    texture_type: str  # Type: 'Diffuse', 'Normal', 'Mask', 'ID', 'Specular', 'Unknown'
    sampler_id: Optional[int] = None  # Sampler ID if known
    
    
def get_texture_type_from_sampler_id(sampler_id: int) -> str:
    """
    Determine texture type from sampler ID.
    Based on Penumbra's ShpkFile.cs constants.
    """
    SAMPLER_ID_MAP = {
        0x115306BE: 'Diffuse',    # g_SamplerDiffuse
        0x0C5EC1F1: 'Normal',     # g_SamplerNormal
        0x8A4E82B6: 'Mask',       # g_SamplerMask
        0x565F8FD8: 'ID',         # g_SamplerIndex
        0x2B99E025: 'Specular',   # g_SamplerSpecular
    }
    return SAMPLER_ID_MAP.get(sampler_id, 'Unknown')


def categorize_tex_from_name(filename: str) -> str:
    """Categorize texture from filename patterns"""
    name = filename.lower()
    if name.endswith('.tex'):
        name = name[:-4]
    
    if any(s in name for s in ['_norm', '_normal', '_n.']):
        return 'Normal'
    if any(s in name for s in ['_index', '_id']):
        return 'ID'
    if any(s in name for s in ['_mask', '_m.', '_mult']):
        return 'Mask'
    if any(s in name for s in ['_diff', '_diffuse', '_base', '_d.']):
        return 'Diffuse'
    if any(s in name for s in ['_spec', '_specular', '_s.']):
        return 'Specular'
    return 'Unknown'


def parse_mtrl_file(mtrl_path: str) -> List[TextureReference]:
    """
    Parse a .mtrl file and extract texture references with their types.
    
    Args:
        mtrl_path: Path to the .mtrl file
        
    Returns:
        List of TextureReference objects
    """
    try:
        from mtrl_parser import MtrlFile
        
        with open(mtrl_path, 'rb') as f:
            data = f.read()
        
        mtrl = MtrlFile.parse(data)
        references = []
        
        # Try to get textures by sampler ID (most accurate)
        for sampler in mtrl.samplers:
            if 0 <= sampler.texture_index < len(mtrl.textures):
                texture = mtrl.textures[sampler.texture_index]
                tex_type = get_texture_type_from_sampler_id(sampler.sampler_id)
                
                references.append(TextureReference(
                    tex_path=texture.path,
                    mtrl_path=mtrl_path,
                    texture_type=tex_type,
                    sampler_id=sampler.sampler_id
                ))
        
        # Also add any textures that weren't associated with known samplers
        sampled_indices = {s.texture_index for s in mtrl.samplers}
        for idx, texture in enumerate(mtrl.textures):
            if idx not in sampled_indices:
                tex_type = categorize_tex_from_name(texture.path)
                references.append(TextureReference(
                    tex_path=texture.path,
                    mtrl_path=mtrl_path,
                    texture_type=tex_type,
                    sampler_id=None
                ))
        
        return references
    
    except Exception as e:
        print(f"Warning: Could not parse {mtrl_path}: {e}")
        return []


def find_all_mtrl_files(mod_folder_path: str) -> List[str]:
    """
    Find all .mtrl files in the mod folder.
    
    Args:
        mod_folder_path: Path to the mod folder
        
    Returns:
        List of absolute paths to .mtrl files
    """
    mtrl_files = []
    
    if not os.path.isdir(mod_folder_path):
        return mtrl_files
    
    for root, dirs, files in os.walk(mod_folder_path):
        for file in files:
            if file.lower().endswith('.mtrl'):
                mtrl_files.append(os.path.join(root, file))
    
    return mtrl_files


def parse_all_mtrl_files(mod_folder_path: str) -> List[TextureReference]:
    """
    Parse all .mtrl files in the mod folder and extract texture references.
    
    Args:
        mod_folder_path: Path to the mod folder
        
    Returns:
        List of all TextureReference objects from all materials
    """
    all_references = []
    mtrl_files = find_all_mtrl_files(mod_folder_path)
    
    print(f"Found {len(mtrl_files)} .mtrl files to parse")
    
    for mtrl_path in mtrl_files:
        references = parse_mtrl_file(mtrl_path)
        all_references.extend(references)
    
    return all_references


def get_mtrl_texture_summary(mod_folder_path: str) -> Dict[str, List[TextureReference]]:
    """
    Get all texture references from .mtrl files, organized by texture type.
    
    Args:
        mod_folder_path: Path to the mod folder
        
    Returns:
        Dictionary mapping texture types to lists of references:
        {
            'Diffuse': [TextureReference, ...],
            'Normal': [TextureReference, ...],
            ...
        }
    """
    all_references = parse_all_mtrl_files(mod_folder_path)
    by_type = {}
    
    for ref in all_references:
        if ref.texture_type not in by_type:
            by_type[ref.texture_type] = []
        by_type[ref.texture_type].append(ref)
    
    return by_type


def get_unique_textures_from_mtrls(mod_folder_path: str) -> Dict[str, Set[str]]:
    """
    Get unique texture paths referenced in .mtrl files, organized by type.
    
    Args:
        mod_folder_path: Path to the mod folder
        
    Returns:
        Dictionary mapping texture types to sets of unique texture paths:
        {
            'Diffuse': {'path1.tex', 'path2.tex', ...},
            'Normal': {'path3.tex', ...},
            ...
        }
    """
    all_references = parse_all_mtrl_files(mod_folder_path)
    unique_by_type = {}
    
    for ref in all_references:
        if ref.texture_type not in unique_by_type:
            unique_by_type[ref.texture_type] = set()
        unique_by_type[ref.texture_type].add(ref.tex_path)
    
    return unique_by_type


def parse_mod_file_mappings(mod_folder_path: str) -> Dict[str, List[str]]:
    """
    Parse all JSON files in a mod folder to extract .tex file mappings.
    
    Args:
        mod_folder_path: Path to the mod folder containing JSON group files
        
    Returns:
        Dictionary mapping in-game paths to list of real file paths.
        Multiple real files can map to the same game path.
        
        Example:
        {
            "chara/human/c0201/obj/hair/h0178/texture/normal.tex": [
                "common\\1\\normal.tex",
                "other\\path\\normal.tex"
            ]
        }
    """
    game_path_to_real_paths = {}
    
    if not os.path.isdir(mod_folder_path):
        return game_path_to_real_paths
    
    # Find all JSON files in the mod folder
    json_files = []
    for root, dirs, files in os.walk(mod_folder_path):
        for file in files:
            if file.lower().endswith('.json') and file.lower() != 'meta.json':
                json_files.append(os.path.join(root, file))
    
    # Parse each JSON file
    for json_path in json_files:
        try:
            with open(json_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            
            # Extract file mappings from Options
            if 'Options' in data and isinstance(data['Options'], list):
                for option in data['Options']:
                    if 'Files' in option and isinstance(option['Files'], dict):
                        for game_path, real_path in option['Files'].items():
                            # Filter for .tex files only
                            if game_path.lower().endswith('.tex'):
                                if game_path not in game_path_to_real_paths:
                                    game_path_to_real_paths[game_path] = []
                                
                                # Only add if not already in the list
                                if real_path not in game_path_to_real_paths[game_path]:
                                    game_path_to_real_paths[game_path].append(real_path)
        
        except (json.JSONDecodeError, IOError) as e:
            # Skip files that can't be parsed
            print(f"Warning: Could not parse {json_path}: {e}")
            continue
    
    return game_path_to_real_paths


def get_real_file_full_path(mod_folder_path: str, real_path: str) -> str:
    """
    Convert a relative real path from JSON to an absolute file path.
    
    Args:
        mod_folder_path: Path to the mod folder
        real_path: Relative path from JSON (e.g., "common\\1\\normal.tex")
        
    Returns:
        Absolute path to the actual file
    """
    # Normalize path separators
    normalized_path = real_path.replace('\\', os.sep).replace('/', os.sep)
    return os.path.join(mod_folder_path, normalized_path)


def get_tex_mappings_with_categories(mod_folder_path: str) -> List[Dict]:
    """
    Get all .tex file mappings with categorization and full paths.
    
    Args:
        mod_folder_path: Path to the mod folder
        
    Returns:
        List of dictionaries with mapping information:
        [
            {
                'game_path': 'chara/human/.../normal.tex',
                'real_path': 'common\\1\\normal.tex',
                'full_path': 'C:\\...\\mod_folder\\common\\1\\normal.tex',
                'category': 'Normal',
                'exists': True,
                'has_multiple_mappings': False
            },
            ...
        ]
    """
    try:
        from mod_browser import categorize_tex
    except ImportError:
        # Fallback if mod_browser can't be imported (e.g., standalone usage)
        def categorize_tex(filename: str) -> str:
            name = filename.lower()
            if name.endswith('.tex'):
                name = name[:-4]
            if any(s in name for s in ['_norm', '_normal', '_n.']):
                return 'Normal'
            if any(s in name for s in ['_index', '_id']):
                return 'ID'
            if any(s in name for s in ['_mask']):
                return 'Mask'
            if any(s in name for s in ['_diff', '_diffuse', '_base', '_d.']):
                return 'Diffuse'
            if any(s in name for s in ['_spec', '_specular', '_s.']):
                return 'Specular'
            return 'Unknown'
    
    mappings = parse_mod_file_mappings(mod_folder_path)
    results = []
    
    for game_path, real_paths in mappings.items():
        has_multiple = len(real_paths) > 1
        
        for real_path in real_paths:
            full_path = get_real_file_full_path(mod_folder_path, real_path)
            category = categorize_tex(os.path.basename(game_path))
            
            results.append({
                'game_path': game_path,
                'real_path': real_path,
                'full_path': full_path,
                'category': category,
                'exists': os.path.isfile(full_path),
                'has_multiple_mappings': has_multiple
            })
    
    return results


def get_mappings_by_category(mod_folder_path: str) -> Dict[str, List[Dict]]:
    """
    Get .tex file mappings organized by category.
    
    Args:
        mod_folder_path: Path to the mod folder
        
    Returns:
        Dictionary mapping categories to lists of mapping info:
        {
            'Normal': [{mapping info}, ...],
            'Diffuse': [{mapping info}, ...],
            ...
        }
    """
    all_mappings = get_tex_mappings_with_categories(mod_folder_path)
    categorized = {}
    
    for mapping in all_mappings:
        category = mapping['category']
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(mapping)
    
    return categorized


def find_conflicts(mod_folder_path: str) -> List[Dict]:
    """
    Find cases where multiple real files map to the same game path.
    
    Args:
        mod_folder_path: Path to the mod folder
        
    Returns:
        List of conflict information:
        [
            {
                'game_path': 'chara/human/.../texture.tex',
                'real_paths': ['path1\\texture.tex', 'path2\\texture.tex'],
                'count': 2
            },
            ...
        ]
    """
    mappings = parse_mod_file_mappings(mod_folder_path)
    conflicts = []
    
    for game_path, real_paths in mappings.items():
        if len(real_paths) > 1:
            conflicts.append({
                'game_path': game_path,
                'real_paths': real_paths,
                'count': len(real_paths)
            })
    
    return conflicts


if __name__ == "__main__":
    # Example usage/testing
    test_mod_path = r"e:\XIVMODS\[178] Octia"
    
    print("=" * 70)
    print("=== Parsing Material (.mtrl) Files ===")
    print("=" * 70)
    
    # Parse all .mtrl files and get texture references
    print("\n[1] Finding .mtrl files...")
    mtrl_files = find_all_mtrl_files(test_mod_path)
    print(f"    Found {len(mtrl_files)} .mtrl files")
    
    if mtrl_files:
        print("\n[2] Parsing .mtrl files for texture references...")
        texture_summary = get_mtrl_texture_summary(test_mod_path)
        
        print(f"\n[3] Texture references by type:")
        for tex_type in sorted(texture_summary.keys()):
            refs = texture_summary[tex_type]
            print(f"    {tex_type}: {len(refs)} references")
        
        print(f"\n[4] Unique texture paths by type:")
        unique_textures = get_unique_textures_from_mtrls(test_mod_path)
        for tex_type in sorted(unique_textures.keys()):
            paths = unique_textures[tex_type]
            print(f"    {tex_type}: {len(paths)} unique textures")
        
        # Show sample references
        print(f"\n[5] Sample texture references (first 5):")
        all_refs = parse_all_mtrl_files(test_mod_path)
        for i, ref in enumerate(all_refs[:5]):
            print(f"\n    Reference {i+1}:")
            print(f"      Type: {ref.texture_type}")
            print(f"      Texture: {ref.tex_path}")
            print(f"      Material: {os.path.basename(ref.mtrl_path)}")
            if ref.sampler_id:
                print(f"      Sampler ID: 0x{ref.sampler_id:08X}")
    
    print("\n" + "=" * 70)
    print("=== Parsing mod file mappings (JSON) ===")
    print("=" * 70)
    
    mappings = parse_mod_file_mappings(test_mod_path)
    print(f"\nFound {len(mappings)} unique game paths with .tex mappings")
    
    print("\n=== Sample mappings (first 5) ===")
    for i, (game_path, real_paths) in enumerate(list(mappings.items())[:5]):
        print(f"\nGame path: {game_path}")
        for real_path in real_paths:
            print(f"  -> {real_path}")
        if i >= 4:
            break
    
    print("\n=== Checking for conflicts ===")
    conflicts = find_conflicts(test_mod_path)
    print(f"Found {len(conflicts)} conflicts (multiple real files -> same game path)")
    for conflict in conflicts[:3]:
        print(f"\n{conflict['game_path']} has {conflict['count']} mappings:")
        for path in conflict['real_paths']:
            print(f"  - {path}")
    
    print("\n=== Mappings by category ===")
    by_category = get_mappings_by_category(test_mod_path)
    for category, mappings_list in sorted(by_category.items()):
        print(f"{category}: {len(mappings_list)} mappings")
