import struct
from dataclasses import dataclass
from typing import List, BinaryIO, Optional

try:
    import texture2ddecoder
except Exception:
    texture2ddecoder = None

try:
    from PIL import Image
except Exception:
    Image = None

@dataclass
class TexHeader:
    magic: int
    version: int
    file_size: int
    header_size: int
    width: int
    height: int
    mip_count: int
    format: int

@dataclass
class Mipmap:
    level: int
    width: int
    height: int
    data: bytes  # RGBA bytes

@dataclass
class ParsedTexFile:
    header: TexHeader
    mipmaps: List[Mipmap]

class TexFileParser:
    MAGIC = 0x54455800  # 'TEX\0'
    FORMAT_ARGB8 = 0
    FORMAT_BC7 = 71

    def __init__(self, stream: BinaryIO):
        self.stream = stream

    def read_u32(self) -> int:
        return struct.unpack('<I', self.stream.read(4))[0]

    def read_header(self) -> TexHeader:
        magic = self.read_u32()
        version = self.read_u32()
        file_size = self.read_u32()
        header_size = self.read_u32()
        width = self.read_u32()
        height = self.read_u32()
        mip_count = self.read_u32()
        fmt = self.read_u32()
        return TexHeader(magic, version, file_size, header_size, width, height, mip_count, fmt)

    def parse(self) -> ParsedTexFile:
        header = self.read_header()
        if header.magic != self.MAGIC:
            raise ValueError(f"Invalid TEX magic: {hex(header.magic)}")

        self.stream.seek(header.header_size)
        w, h = header.width, header.height

        # Only decode highest-res mipmap
        if header.format == self.FORMAT_ARGB8:
            raw = self.stream.read(w*h*4)
            data = self.decode_argb8(raw)
        elif header.format == self.FORMAT_BC7:
            blocks_x = (w + 3)//4
            blocks_y = (h + 3)//4
            raw = self.stream.read(blocks_x*blocks_y*16)
            data = self.decode_bc7(raw, w, h)
        else:
            raise NotImplementedError(f"Format {header.format} not supported")

        mipmap = Mipmap(level=0, width=w, height=h, data=data)
        return ParsedTexFile(header=header, mipmaps=[mipmap])

    @staticmethod
    def decode_argb8(buf: bytes) -> bytes:
        out = bytearray(len(buf))
        for i in range(0, len(buf), 4):
            a,r,g,b = buf[i:i+4]
            out[i:i+4] = bytes([r,g,b,a])
        return bytes(out)

    @staticmethod
    def decode_bc7(buf: bytes, width: int, height: int) -> bytes:
        if texture2ddecoder is None:
            raise RuntimeError("texture2ddecoder required for BC7")
        bgra = texture2ddecoder.decode_bc7(buf, width, height)
        rgba = bytearray(len(bgra))
        for i in range(0, len(bgra), 4):
            b,g,r,a = bgra[i:i+4]
            rgba[i:i+4] = bytes([r,g,b,a])
        return bytes(rgba)

class TexFileWriter:
    MAGIC = 0x54455800
    FORMAT_ARGB8 = 0
    FORMAT_BC7 = 71

    @staticmethod
    def write(tex_path: str, width: int, height: int, data: bytes, fmt: int, mip_count: int =1):
        header_size = 32
        if fmt == TexFileWriter.FORMAT_ARGB8:
            file_size = header_size + len(data)
        elif fmt == TexFileWriter.FORMAT_BC7:
            blocks_x = (width+3)//4
            blocks_y = (height+3)//4
            file_size = header_size + blocks_x*blocks_y*16
        else:
            raise NotImplementedError(f"Format {fmt} not supported")

        with open(tex_path, 'wb') as f:
            f.write(struct.pack('<I', TexFileWriter.MAGIC))
            f.write(struct.pack('<I', 1))  # version
            f.write(struct.pack('<I', file_size))
            f.write(struct.pack('<I', header_size))
            f.write(struct.pack('<I', width))
            f.write(struct.pack('<I', height))
            f.write(struct.pack('<I', mip_count))
            f.write(struct.pack('<I', fmt))
            f.write(data)