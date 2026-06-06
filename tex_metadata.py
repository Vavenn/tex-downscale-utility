import io
import os

from kaitaistruct import KaitaiStream


def get_tex_metadata(tex_path: str):
    """Return (width, height, format_name) for a TEX file, or (None, None, None) on failure."""
    try:
        if not os.path.isfile(tex_path):
            return None, None, None

        import importlib.util
        import sys

        # Handle PyInstaller bundled mode
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            parser_path = os.path.join(sys._MEIPASS, "FFXIV Tex Converter", "src", "parsers", "tex.py")
        else:
            parser_path = os.path.join(
                os.path.dirname(__file__),
                "FFXIV Tex Converter",
                "src",
                "parsers",
                "tex.py",
            )
        if not os.path.isfile(parser_path):
            return None, None, None

        spec = importlib.util.spec_from_file_location("ffxiv_tex_meta", parser_path)
        tex_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tex_module)

        with open(tex_path, "rb") as f:
            tex_data = f.read()
        tex_obj = tex_module.Tex(KaitaiStream(io.BytesIO(tex_data)))

        width = tex_obj.hdr.width
        height = tex_obj.hdr.height
        fmt = tex_obj.hdr.format
        fmt_name = getattr(fmt, "name", str(fmt))
        return width, height, fmt_name
    except Exception:
        return None, None, None
