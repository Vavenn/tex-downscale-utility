#!/usr/bin/env python3
"""Debug script to compare TEX headers"""

import sys
import struct

def read_tex_header(path):
    """Read and parse the 80-byte TEX header"""
    with open(path, 'rb') as f:
        header = f.read(80)
    
    # Parse header fields
    tex_type = struct.unpack('<I', header[0:4])[0]
    tex_format = struct.unpack('<I', header[4:8])[0]
    width = struct.unpack('<H', header[8:10])[0]
    height = struct.unpack('<H', header[10:12])[0]
    depth = struct.unpack('<H', header[12:14])[0]
    mip_count = struct.unpack('<B', header[14:15])[0]
    array_size = struct.unpack('<B', header[15:16])[0]
    
    print(f"File: {path}")
    print(f"  Type: 0x{tex_type:08X} ({tex_type})")
    print(f"  Format: 0x{tex_format:08X} ({tex_format})")
    print(f"  Dimensions: {width}x{height}x{depth}")
    print(f"  Mip Count: {mip_count}")
    print(f"  Array Size: {array_size}")
    print(f"  Header (hex): {header[:20].hex()}")
    print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python debug_tex_header.py <path_to_tex_file> [path_to_tex_file2]")
        sys.exit(1)
    
    for path in sys.argv[1:]:
        try:
            read_tex_header(path)
        except Exception as e:
            print(f"Error reading {path}: {e}\n")
