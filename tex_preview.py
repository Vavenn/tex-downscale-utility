import io
import os
import re
import sys

import numpy as np
from kaitaistruct import KaitaiStream
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage


# Global variable to track the current preview worker
_current_preview_worker = None


class PreviewWorker(QThread):
    """Worker thread for loading and decoding texture files without blocking the UI."""
    
    # Signals for communication back to main thread
    preview_ready = Signal(bytes, int, int, bool, bool, bytes)  # rgba_bytes, width, height, force_opaque, show_alpha, original_rgba
    preview_failed = Signal(str)  # error_message
    
    def __init__(self, tex_path, force_opaque_alpha, show_alpha_separate):
        super().__init__()
        self.tex_path = tex_path
        self.force_opaque_alpha = force_opaque_alpha
        self.show_alpha_separate = show_alpha_separate
        self._cancelled = False
    
    def cancel(self):
        """Request cancellation of this worker."""
        self._cancelled = True
    
    def run(self):
        """Load and decode the texture in a background thread."""
        try:
            if self._cancelled:
                return
            
            # Load the texture parser
            import importlib.util
            
            # Handle PyInstaller bundled mode
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                tex_parser_path = os.path.join(sys._MEIPASS, 'FFXIV Tex Converter', 'src', 'parsers', 'tex.py')
            else:
                tex_parser_path = os.path.join(os.path.dirname(__file__), 'FFXIV Tex Converter', 'src', 'parsers', 'tex.py')
            
            spec = importlib.util.spec_from_file_location('ffxiv_tex', tex_parser_path)
            tex_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tex_module)
            
            if self._cancelled:
                return
            
            # Read the texture file
            with open(self.tex_path, 'rb') as f:
                tex_data = f.read()
            
            tex_obj = tex_module.Tex(KaitaiStream(io.BytesIO(tex_data)))
            width = tex_obj.hdr.width
            height = tex_obj.hdr.height
            tex_format = tex_obj.hdr.format
            
            if self._cancelled:
                return
            
            # Decode based on format
            from texture2ddecoder import (
                decode_bc1, decode_bc3, decode_bc4, decode_bc5, decode_bc7
            )
            
            rgba_bytes = None
            
            if tex_format in (tex_module.Tex.Header.TextureFormat.b8g8r8a8,
                               tex_module.Tex.Header.TextureFormat.b8g8r8x8):
                expected_size = width * height * 4
                raw = tex_obj.bdy.data[:expected_size]
                if len(raw) < expected_size:
                    self.preview_failed.emit(f"Data too small ({len(raw)} < {expected_size})")
                    return
                bgra = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 4))
                rgba = np.ascontiguousarray(bgra[..., [2, 1, 0, 3]])
                rgba_bytes = rgba.tobytes()
            
            elif tex_format == tex_module.Tex.Header.TextureFormat.l8:
                expected_size = width * height
                raw = tex_obj.bdy.data[:expected_size]
                if len(raw) < expected_size:
                    self.preview_failed.emit(f"L8 data too small ({len(raw)} < {expected_size})")
                    return
                gray = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 1))
                rgba = np.repeat(gray, 3, axis=2)
                alpha = np.full_like(gray, 255)
                rgba = np.concatenate([rgba, alpha], axis=2)
                rgba_bytes = rgba.tobytes()
            
            elif tex_format == tex_module.Tex.Header.TextureFormat.a8:
                expected_size = width * height
                raw = tex_obj.bdy.data[:expected_size]
                if len(raw) < expected_size:
                    self.preview_failed.emit(f"A8 data too small ({len(raw)} < {expected_size})")
                    return
                alpha = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 1))
                rgb = np.full_like(alpha, 255)
                rgba = np.concatenate([rgb, rgb, rgb, alpha], axis=2)
                rgba_bytes = rgba.tobytes()
            
            elif tex_format == tex_module.Tex.Header.TextureFormat.dxt1:
                if self._cancelled:
                    return
                bc_data = tex_obj.bdy.data
                bgra = decode_bc1(bc_data, width, height)
                rgba_bytes = _bgra_to_rgba_bytes(bgra)
            
            elif tex_format in (tex_module.Tex.Header.TextureFormat.dxt3,
                                 tex_module.Tex.Header.TextureFormat.dxt5):
                if self._cancelled:
                    return
                bc_data = tex_obj.bdy.data
                bgra = decode_bc3(bc_data, width, height)
                rgba_bytes = _bgra_to_rgba_bytes(bgra)
            
            elif tex_format == tex_module.Tex.Header.TextureFormat.ati1:
                if self._cancelled:
                    return
                bc_data = tex_obj.bdy.data
                bgra = decode_bc4(bc_data, width, height)
                rgba_bytes = _bgra_to_rgba_bytes(bgra)
            
            elif tex_format == tex_module.Tex.Header.TextureFormat.ati2:
                if self._cancelled:
                    return
                bc_data = tex_obj.bdy.data
                bgra = decode_bc5(bc_data, width, height)
                rgba_bytes = _bgra_to_rgba_bytes(bgra)
            
            elif tex_format == tex_module.Tex.Header.TextureFormat.bc7:
                if self._cancelled:
                    return
                bc_data = tex_obj.bdy.data
                bgra = decode_bc7(bc_data, width, height)
                rgba_bytes = _bgra_to_rgba_bytes(bgra)
            
            else:
                self.preview_failed.emit(f"Format not supported for preview: {tex_format}")
                return
            
            if self._cancelled:
                return
            
            if rgba_bytes:
                # Keep original for alpha channel display
                original_rgba = rgba_bytes
                self.preview_ready.emit(rgba_bytes, width, height, self.force_opaque_alpha, 
                                       self.show_alpha_separate, original_rgba)
        
        except Exception as e:
            if not self._cancelled:
                self.preview_failed.emit(f"Failed to preview .tex: {e}")


def preview_selected_tex(tex_list, mod_list, path_entry, image_label, log_message, force_opaque_alpha=False, show_alpha_separate=False, alpha_label=None):
    global _current_preview_worker
    
    # Cancel any existing preview worker
    if _current_preview_worker and _current_preview_worker.isRunning():
        _current_preview_worker.cancel()
        _current_preview_worker.wait()
    
    image_label.clear()
    if alpha_label:
        alpha_label.clear()
        alpha_label.hide()
    selected_items = tex_list.selectedItems()
    if not selected_items:
        image_label.setText("No image selected")
        return

    # Derive rel_path from QTreeWidgetItem column (Path) with a robust fallback
    selected_item = selected_items[0]
    rel_path = None
    try:
        rel_path = selected_item.text(1)
    except Exception:
        rel_path = None
    if not rel_path:
        # Fallback: attempt to parse from first column formatted as "[Type] path"
        try:
            display_text = selected_item.text(0)
        except Exception:
            display_text = ""
        idx = display_text.rfind("] ")
        if idx != -1:
            rel_path = display_text[idx + 2:]
        else:
            # Last resort: use regex on the whole string if accessible
            whole = display_text
            m = re.match(r"\[.*\] (.*)", whole)
            if m:
                rel_path = m.group(1)
    if not rel_path:
        msg = "Invalid file selection"
        image_label.setText(msg)
        log_message(msg)
        return

    mod_selected = mod_list.selectedItems()
    if not mod_selected:
        msg = "No mod selected"
        image_label.setText(msg)
        log_message(msg)
        return
    mod_name_display = mod_selected[0].text()

    path_to_scan = path_entry.text()
    if not path_to_scan or not os.path.isdir(path_to_scan):
        msg = "Invalid mod path"
        image_label.setText(msg)
        log_message(msg)
        return

    from mod_browser import build_mod_folder_map

    mod_folder_map = build_mod_folder_map(path_to_scan)
    mod_folder_full = mod_folder_map.get(mod_name_display)
    if not mod_folder_full:
        msg = "Mod folder not found"
        image_label.setText(msg)
        log_message(msg)
        return

    rel_path = rel_path.strip().lstrip("./\\")
    tex_path = os.path.normpath(os.path.join(mod_folder_full, rel_path))
    if not os.path.isfile(tex_path):
        log_message(f"Preview path not found, attempted: {tex_path}")
        # Fallback: try to locate by filename within the mod folder
        target_name = os.path.basename(rel_path)
        candidate = None
        for root, _, files in os.walk(mod_folder_full):
            for f in files:
                if f.lower() == target_name.lower():
                    candidate = os.path.join(root, f)
                    break
            if candidate:
                break
        if candidate and os.path.isfile(candidate):
            tex_path = os.path.normpath(candidate)
            log_message(f"Resolved by filename to: {tex_path}")
        else:
            image_label.setText("File not found")
            log_message(f"Mod: {mod_name_display}; Base: {mod_folder_full}; Rel: {rel_path}")
            return

    # Handle non-.tex image files directly (no threading needed for these)
    if tex_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
        pixmap = QPixmap(tex_path)
        image_label.setPixmap(pixmap.scaled(image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return

    if not tex_path.lower().endswith('.tex'):
        msg = "Preview not supported for this file type"
        image_label.setText(msg)
        log_message(msg)
        return

    # Show loading message
    image_label.setText("Loading preview...")
    
    # Create signal handlers for the worker
    def on_preview_ready(rgba_bytes, width, height, force_opaque, show_alpha, original_rgba):
        """Called when preview is ready - runs on main thread."""
        # Optionally force opaque alpha
        if force_opaque:
            ba = bytearray(rgba_bytes)
            for i in range(3, len(ba), 4):
                ba[i] = 255
            rgba_bytes = bytes(ba)
        
        arr = np.frombuffer(rgba_bytes, dtype=np.uint8)
        if arr.size != width * height * 4:
            msg = f"Decoded size mismatch ({arr.size} != {width*height*4})"
            image_label.setText(msg)
            log_message(msg)
            return
        
        arr = arr.reshape((height, width, 4))
        arr = np.ascontiguousarray(arr)
        image = QImage(arr.data, width, height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(image)
        image_label.setPixmap(
            pixmap.scaled(
                image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        
        # Show alpha channel separately if requested
        if show_alpha and alpha_label:
            alpha_label.show()
            # Extract alpha channel and display as grayscale
            alpha_arr = np.frombuffer(original_rgba, dtype=np.uint8)
            alpha_arr = alpha_arr.reshape((height, width, 4))
            alpha_channel = alpha_arr[:, :, 3]  # Extract alpha channel
            # Create grayscale image from alpha
            gray_rgba = np.zeros((height, width, 4), dtype=np.uint8)
            gray_rgba[:, :, 0] = alpha_channel  # R
            gray_rgba[:, :, 1] = alpha_channel  # G
            gray_rgba[:, :, 2] = alpha_channel  # B
            gray_rgba[:, :, 3] = 255  # Full opacity
            gray_rgba = np.ascontiguousarray(gray_rgba)
            alpha_image = QImage(gray_rgba.data, width, height, QImage.Format_RGBA8888)
            alpha_pixmap = QPixmap.fromImage(alpha_image)
            alpha_label.setPixmap(
                alpha_pixmap.scaled(
                    alpha_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        elif alpha_label:
            alpha_label.hide()
    
    def on_preview_failed(error_msg):
        """Called when preview fails - runs on main thread."""
        image_label.setText(error_msg)
        log_message(error_msg)
    
    # Create and start the worker thread
    _current_preview_worker = PreviewWorker(tex_path, force_opaque_alpha, show_alpha_separate)
    _current_preview_worker.preview_ready.connect(on_preview_ready)
    _current_preview_worker.preview_failed.connect(on_preview_failed)
    _current_preview_worker.start()


def _bgra_to_rgba_bytes(bgra: bytes) -> bytes:
    if not bgra:
        return b""
    if isinstance(bgra, bytearray):
        bgra_bytes = bgra
    else:
        bgra_bytes = bytearray(bgra)
    for i in range(0, len(bgra_bytes), 4):
        b, g, r, a = bgra_bytes[i:i+4]
        bgra_bytes[i:i+4] = bytes([r, g, b, a])
    return bytes(bgra_bytes)
