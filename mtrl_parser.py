"""
MTRL File Parser
Extracts texture paths and shader package name from FFXIV .mtrl (Material) files.

Based on Penumbra's MtrlFile implementation:
https://github.com/xivdev/Penumbra/blob/main/Penumbra.GameData/Files/MtrlFile.cs
"""

import struct
from pathlib import Path
from typing import List, NamedTuple, Optional, Set
from dataclasses import dataclass
from enum import Enum


class ShaderType(Enum):
    """Categorized shader types"""
    SKIN = "skin"
    CHARACTER_LEGACY = "characterlegacy"
    CHARACTER = "character"
    OTHER = "other"
    
    @classmethod
    def from_shader_name(cls, shader_name: str) -> 'ShaderType':
        """Determine shader type from shader package name"""
        shader_lower = shader_name.lower().replace('.shpk', '')
        if 'skin' in shader_lower:
            return cls.SKIN
        elif shader_lower == 'characterlegacy':
            return cls.CHARACTER_LEGACY
        elif shader_lower in ('character', 'characterglass', 'charactertransparency'):
            return cls.CHARACTER
        else:
            return cls.OTHER


class Texture(NamedTuple):
    """Texture reference in material"""
    path: str
    flags: int
    dx11: bool  # True if using DX11 version
    
    @classmethod
    def from_flags(cls, path: str, flags: int):
        dx11 = (flags & 0x8000) != 0
        return cls(path, flags, dx11)


class Sampler(NamedTuple):
    """Sampler definition linking texture to shader parameter"""
    sampler_id: int  # uint32 - shader parameter ID
    flags: int       # uint32 - sampler flags
    texture_index: int  # byte - index into textures array


@dataclass
class MtrlFile:
    """FFXIV Material file"""
    version: int
    textures: List[Texture]
    shader_package_name: str
    samplers: List[Sampler]
    
    # Shader sampler IDs (from ShpkFile.cs constants)
    NORMAL_SAMPLER_ID = 0x0C5EC1F1    # g_SamplerNormal (suffix "_norm" or "_n")
    INDEX_SAMPLER_ID = 0x565F8FD8     # g_SamplerIndex (suffix "_id")
    SPECULAR_SAMPLER_ID = 0x2B99E025  # g_SamplerSpecular
    DIFFUSE_SAMPLER_ID = 0x115306BE   # g_SamplerDiffuse (suffix "_d" or "_base")
    MASK_SAMPLER_ID = 0x8A4E82B6      # g_SamplerMask (suffix "_m", "_mult" or "_mask")
    
    @property
    def shader_type(self) -> ShaderType:
        """Get categorized shader type"""
        return ShaderType.from_shader_name(self.shader_package_name)
    
    def get_texture_by_sampler_id(self, sampler_id: int) -> Optional[Texture]:
        """Get texture associated with a specific sampler ID"""
        for sampler in self.samplers:
            if sampler.sampler_id == sampler_id:
                if 0 <= sampler.texture_index < len(self.textures):
                    return self.textures[sampler.texture_index]
        return None
    
    def get_diffuse_texture(self) -> Optional[Texture]:
        """Get diffuse/albedo texture"""
        return self.get_texture_by_sampler_id(self.DIFFUSE_SAMPLER_ID)
    
    def get_normal_texture(self) -> Optional[Texture]:
        """Get normal map texture"""
        return self.get_texture_by_sampler_id(self.NORMAL_SAMPLER_ID)
    
    def get_mask_texture(self) -> Optional[Texture]:
        """Get mask texture"""
        return self.get_texture_by_sampler_id(self.MASK_SAMPLER_ID)
    
    def get_id_texture(self) -> Optional[Texture]:
        """Get ID texture (for color table indexing)"""
        return self.get_texture_by_sampler_id(self.INDEX_SAMPLER_ID)
    
    def get_specular_texture(self) -> Optional[Texture]:
        """Get specular texture"""
        return self.get_texture_by_sampler_id(self.SPECULAR_SAMPLER_ID)
    
    @classmethod
    def parse(cls, data: bytes) -> 'MtrlFile':
        """Parse MTRL file from binary data"""
        if len(data) < 16:
            raise ValueError("Data too short to be a valid MTRL file")
        
        pos = 0
        
        # Read material header (16 bytes)
        version = struct.unpack_from('<I', data, pos)[0]
        pos += 4
        
        file_size = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        
        data_set_size = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        
        string_table_size = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        
        shader_package_name_offset = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        
        texture_count = struct.unpack_from('<B', data, pos)[0]
        pos += 1
        
        uv_set_count = struct.unpack_from('<B', data, pos)[0]
        pos += 1
        
        color_set_count = struct.unpack_from('<B', data, pos)[0]
        pos += 1
        
        additional_data_size = struct.unpack_from('<B', data, pos)[0]
        pos += 1
        
        # Read texture offsets and flags
        texture_offsets = []
        texture_flags = []
        for i in range(texture_count):
            offset = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            flags = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            texture_offsets.append(offset)
            texture_flags.append(flags)
        
        # Skip UV set offsets
        pos += uv_set_count * 4  # offset (2 bytes) + index (2 bytes)
        
        # Skip color set offsets
        pos += color_set_count * 4  # offset (2 bytes) + index (2 bytes)
        
        # Read string table
        string_table_start = pos
        string_table_end = string_table_start + string_table_size
        string_table = data[string_table_start:string_table_end]
        
        # Helper to read null-terminated string from string table
        def read_string(offset: int) -> str:
            if offset >= len(string_table):
                return ""
            end = string_table.find(b'\x00', offset)
            if end == -1:
                end = len(string_table)
            return string_table[offset:end].decode('utf-8', errors='replace')
        
        # Parse texture paths
        textures = []
        for offset, flags in zip(texture_offsets, texture_flags):
            path = read_string(offset)
            textures.append(Texture.from_flags(path, flags))
        
        # Parse shader package name
        shader_package_name = read_string(shader_package_name_offset)
        
        # Skip to shader data
        pos = string_table_end
        pos += additional_data_size  # Skip additional data
        pos += data_set_size  # Skip color table data
        
        # Read shader package data header
        if pos + 8 > len(data):
            # File might be truncated, return what we have
            return cls(
                version=version,
                textures=textures,
                shader_package_name=shader_package_name,
                samplers=[]
            )
        
        shader_value_list_size = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        
        shader_key_count = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        
        constant_count = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        
        sampler_count = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        
        shader_flags = struct.unpack_from('<I', data, pos)[0]
        pos += 4
        
        # Skip shader keys (8 bytes each: key uint32 + value uint32)
        pos += shader_key_count * 8
        
        # Skip constants (8 bytes each: id uint32 + offset uint16 + size uint16)
        pos += constant_count * 8
        
        # Read samplers
        samplers = []
        for i in range(sampler_count):
            if pos + 13 > len(data):
                break  # Truncated file
            
            sampler_id = struct.unpack_from('<I', data, pos)[0]
            pos += 4
            
            flags = struct.unpack_from('<I', data, pos)[0]
            pos += 4
            
            texture_index = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            
            # Skip padding (2 bytes + 1 byte = 3 bytes)
            pos += 3
            
            samplers.append(Sampler(sampler_id, flags, texture_index))
        
        return cls(
            version=version,
            textures=textures,
            shader_package_name=shader_package_name,
            samplers=samplers
        )
    
    @classmethod
    def from_file(cls, filepath: Path) -> 'MtrlFile':
        """Load and parse MTRL file from disk"""
        with open(filepath, 'rb') as f:
            data = f.read()
        return cls.parse(data)
    
    def print_info(self):
        """Print material information"""
        print(f"Material File Info:")
        print(f"  Version: 0x{self.version:08X}")
        print(f"  Shader Package: {self.shader_package_name}")
        print(f"  Shader Type: {self.shader_type.value}")
        print(f"\nTextures ({len(self.textures)}):")
        for i, tex in enumerate(self.textures):
            dx11_str = " [DX11]" if tex.dx11 else ""
            print(f"  [{i}] {tex.path} (flags: 0x{tex.flags:04X}){dx11_str}")
        
        print(f"\nSamplers ({len(self.samplers)}):")
        sampler_names = {
            self.DIFFUSE_SAMPLER_ID: "Diffuse",
            self.NORMAL_SAMPLER_ID: "Normal",
            self.MASK_SAMPLER_ID: "Mask",
            self.INDEX_SAMPLER_ID: "Index/ID",
            self.SPECULAR_SAMPLER_ID: "Specular",
        }
        for sampler in self.samplers:
            name = sampler_names.get(sampler.sampler_id, f"0x{sampler.sampler_id:08X}")
            tex_path = "???"
            if 0 <= sampler.texture_index < len(self.textures):
                tex_path = self.textures[sampler.texture_index].path
            print(f"  {name}: texture[{sampler.texture_index}] = {tex_path}")


def scan_folder_for_shaders(folder_path: Path) -> Set[ShaderType]:
    """
    Scan a folder for all .mtrl files and return unique shader types found.
    
    Args:
        folder_path: Path to the mod folder to scan
        
    Returns:
        Set of ShaderType enums found in the folder
    """
    shader_types = set()
    
    if not folder_path.exists():
        return shader_types
    
    # Find all .mtrl files recursively
    for mtrl_file in folder_path.rglob('*.mtrl'):
        try:
            mtrl = MtrlFile.from_file(mtrl_file)
            shader_types.add(mtrl.shader_type)
        except Exception as e:
            # Skip files that can't be parsed
            print(f"Warning: Could not parse {mtrl_file}: {e}")
            continue
    
    return shader_types


def determine_processing_mode(shader_types: Set[ShaderType]) -> str:
    """
    Determine processing mode based on shader types found.
    
    Rules:
    - If ANY Skin shader: RGBA quality for Normal, Mask, Diffuse
    - If NO Skin but has Character/CharacterLegacy: RGB for all (RG for ID)
    - If ANY other shader type: RGBA for all (RG for ID)
    
    Args:
        shader_types: Set of ShaderType enums
        
    Returns:
        Processing mode: "skin", "character", or "other"
    """
    if ShaderType.SKIN in shader_types:
        return "skin"
    elif ShaderType.CHARACTER in shader_types or ShaderType.CHARACTER_LEGACY in shader_types:
        # Only if no Skin shaders
        return "character"
    else:
        return "other"


def main():
    """Example usage"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python mtrl_parser.py <path_to_mtrl_file>")
        print("\nExample:")
        print("  python mtrl_parser.py chara/equipment/e0001/material/v0001/mt_c0101e0001_a.mtrl")
        return
    
    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        return
    
    try:
        mtrl = MtrlFile.from_file(filepath)
        mtrl.print_info()
        
        # Show texture categorization
        print("\nTexture Categorization:")
        if diffuse := mtrl.get_diffuse_texture():
            print(f"  Diffuse: {diffuse.path}")
        if normal := mtrl.get_normal_texture():
            print(f"  Normal: {normal.path}")
        if mask := mtrl.get_mask_texture():
            print(f"  Mask: {mask.path}")
        if id_tex := mtrl.get_id_texture():
            print(f"  ID: {id_tex.path}")
        if spec := mtrl.get_specular_texture():
            print(f"  Specular: {spec.path}")
        
    except Exception as e:
        print(f"Error parsing file: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
