import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFrame, QListWidget
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from tex_metadata import get_tex_metadata


def create_path_group(parent, settings, log_message, on_scan_mods_callback):
    path_group = QGroupBox("Penumbra Path Setup", parent)
    path_layout = QVBoxLayout()
    path_layout.setAlignment(Qt.AlignTop)

    label_path = QLabel("Select the folder containing your Penumbra mods:")
    path_entry = QLineEdit()
    path_entry.setPlaceholderText("Enter or select a path...")
    saved_path = settings.value("penumbra_mods_path", "")
    if saved_path:
        path_entry.setText(saved_path)

    select_path_btn = QPushButton("Select Path")

    def on_select_path():
        from PySide6.QtWidgets import QFileDialog

        path_to_check = path_entry.text()
        if not path_to_check:
            folder = QFileDialog.getExistingDirectory(parent, "Select Folder")
            if folder:
                path_to_check = folder
                path_entry.setText(folder)
        if path_to_check and os.path.isdir(path_to_check):
            settings.setValue("penumbra_mods_path", path_to_check)
            log_message(f"Saved path: {path_to_check}")
        else:
            log_message(f"Invalid path: {path_to_check}")

    select_path_btn.clicked.connect(on_select_path)

    path_layout.addWidget(label_path)
    path_layout.addWidget(path_entry)
    path_layout.addWidget(select_path_btn)

    line_spacer = QFrame()
    line_spacer.setFrameShape(QFrame.HLine)
    line_spacer.setFrameShadow(QFrame.Sunken)
    path_layout.addWidget(line_spacer)

    button_scan_mods = QPushButton("Scan Penumbra Mods")
    button_scan_mods.clicked.connect(on_scan_mods_callback)
    path_layout.addWidget(button_scan_mods)

    path_group.setLayout(path_layout)

    return path_group, path_entry

def create_mod_list_widgets(parent):
    search_box = QLineEdit(parent)
    search_box.setPlaceholderText("Search mods...")

    mod_list = QListWidget(parent)
    mod_list.setSelectionMode(QListWidget.SingleSelection)

    def filter_mod_list():
        search_text = search_box.text().lower()
        for i in range(mod_list.count()):
            item = mod_list.item(i)
            item.setHidden(search_text not in item.text().lower())

    search_box.textChanged.connect(filter_mod_list)

    return search_box, mod_list


def scan_mods(base_path, mod_list_widget, log_message):
    mod_list_widget.clear()
    if base_path and os.path.isdir(base_path):
        log_message(f"Scanning mods in: {base_path}")
        found_mod_names = []
        name_count = {}
        for mod_folder in os.listdir(base_path):
            mod_folder_full = os.path.join(base_path, mod_folder)
            meta_path = os.path.join(mod_folder_full, "meta.json")
            if not os.path.isdir(mod_folder_full):
                continue
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8-sig") as f:
                        meta = json.load(f)
                    mod_name = meta.get("Name", mod_folder)
                except Exception as e:
                    log_message(f"Error reading meta.json in '{mod_folder_full}': {e}")
                    mod_name = mod_folder
                if mod_name in name_count:
                    name_count[mod_name] += 1
                    mod_name_display = f"{mod_name} - {name_count[mod_name]}"
                else:
                    name_count[mod_name] = 1
                    mod_name_display = mod_name
                found_mod_names.append(mod_name_display)
            else:
                log_message(f"Skipping '{mod_folder_full}', invalid mod structure.")
        mod_list_widget.addItems(found_mod_names)
        log_message(f"Found {len(found_mod_names)} mods.")
    else:
        log_message("Please select a valid Penumbra mods path before scanning.")


def build_mod_folder_map(base_path):
    mod_folder_map = {}
    name_count = {}
    for mod_folder in os.listdir(base_path):
        mod_folder_full = os.path.join(base_path, mod_folder)
        meta_path = os.path.join(mod_folder_full, "meta.json")
        if not os.path.isdir(mod_folder_full) or not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8-sig") as f:
                meta = json.load(f)
            mod_name = meta.get("Name", mod_folder)
        except Exception:
            mod_name = mod_folder
        if mod_name in name_count:
            name_count[mod_name] += 1
            mod_name_display_actual = f"{mod_name} - {name_count[mod_name]}"
        else:
            name_count[mod_name] = 1
            mod_name_display_actual = mod_name
        mod_folder_map[mod_name_display_actual] = mod_folder_full
    return mod_folder_map


def categorize_tex(filename: str, mod_folder_full: str = None, mtrl_mapping: dict = None) -> str:
    """
    Categorize a texture file by type.
    
    Priority:
    1. If mtrl_mapping provided, use it (from material file analysis)
    2. Otherwise fall back to filename pattern matching
    
    Args:
        filename: The texture filename or path
        mod_folder_full: Optional mod folder path (for lazy loading mtrl mapping)
        mtrl_mapping: Optional pre-computed mtrl mapping dictionary
        
    Returns:
        Texture type: 'Normal', 'ID', 'Mask', 'Diffuse', 'Specular', or 'Unknown'
    """
    # Try mtrl mapping first if provided
    if mtrl_mapping:
        # Try exact match
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
    name = filename.lower()
    if name.endswith('.tex'):
        name = name[:-4]
    
    # Check longer, more specific patterns first to avoid false matches
    # (e.g., "_mask" before "_m", "_diff" before "_d", "_spec" before "_s")
    
    if any(s in name for s in ['_norm', '_normal']):
        return 'Normal'
    if any(s in name for s in ['_n.']):  # _n at end (before extension)
        return 'Normal'
    
    if any(s in name for s in ['_index', '_id']):
        return 'ID'
    
    if any(s in name for s in ['_mask']):
        return 'Mask'
    
    if any(s in name for s in ['_diff', '_diffuse', '_base', '_d.']):  # Check _diff before _d
        return 'Diffuse'
    
    if any(s in name for s in ['_spec', '_specular', '_s.']):  # Check _spec before _s
        return 'Specular'
    
    # Only check single-letter patterns if they appear at specific positions
    # to avoid matching in the middle of item codes like "dwn" or "sho"
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


def build_mtrl_mapping_for_mod(mod_folder_full: str) -> dict:
    """
    Build texture type mapping from .mtrl files in the mod folder.
    
    Returns:
        Dictionary mapping texture paths/basenames to their types
    """
    try:
        from processing import build_texture_type_mapping_from_mtrls
        return build_texture_type_mapping_from_mtrls(mod_folder_full)
    except Exception:
        return {}


def populate_tex_list(mod_folder_full, tex_list_widget, log_message=None):
    """Populate texture list with mtrl-based categorization when available."""
    tex_list_widget.clear()
    
    # Build mtrl mapping for accurate categorization
    if log_message:
        log_message("Building texture type mappings from material files...")
    mtrl_mapping = build_mtrl_mapping_for_mod(mod_folder_full)
    if log_message and mtrl_mapping:
        log_message(f"Found {len(mtrl_mapping)} texture type mappings from .mtrl files")
    
    tex_files = []
    for root, dirs, files in os.walk(mod_folder_full):
        for file in files:
            if file.lower().endswith(".tex"):
                rel_path = os.path.relpath(os.path.join(root, file), mod_folder_full)
                category = categorize_tex(file, mod_folder_full, mtrl_mapping)
                tex_files.append((category, rel_path))
    tex_files.sort(key=lambda x: (x[0], x[1].lower()))
    tex_list_widget.addItems([f"[{cat}] {path}" for cat, path in tex_files])


def populate_tex_list_with_info(mod_folder_full, tex_list_widget, show_info: bool = False, log_message=None):
    """Populate texture list with info, using mtrl-based categorization when available."""
    tex_list_widget.clear()
    
    # Build mtrl mapping for accurate categorization
    if log_message:
        log_message("Building texture type mappings from material files...")
    mtrl_mapping = build_mtrl_mapping_for_mod(mod_folder_full)
    if log_message and mtrl_mapping:
        log_message(f"Found {len(mtrl_mapping)} texture type mappings from .mtrl files")
    
    tex_entries = []
    for root, dirs, files in os.walk(mod_folder_full):
        for file in files:
            if not file.lower().endswith(".tex"):
                continue
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, mod_folder_full)
            category = categorize_tex(file, mod_folder_full, mtrl_mapping)
            size_bytes = os.path.getsize(full_path)

            info = ""
            if show_info:
                width, height, fmt_name = get_tex_metadata(full_path)
                size_kb = size_bytes / 1024.0
                if width is not None and height is not None and fmt_name is not None:
                    info = f"| {width}x{height} | {size_kb:.1f} KB | {fmt_name}"
                else:
                    info = f"| {size_kb:.1f} KB"

            # Show extra info at the beginning so it is immediately visible
            if show_info and info:
                display = f"{info} [{category}] {rel_path}"
            else:
                display = f"[{category}] {rel_path}"
            tex_entries.append((category, rel_path.lower(), display))

    tex_entries.sort(key=lambda x: (x[0], x[1]))
    for _, _, display in tex_entries:
        tex_list_widget.addItem(display)
    
def populate_tex_tree_with_info(mod_folder_full, tex_tree_widget, show_info, log_message, sort_order: str = "Type"):
    tex_tree_widget.clear()
    tex_files = []
    for root, _, files in os.walk(mod_folder_full):
        for f in files:
            if f.lower().endswith('.tex'):
                full_path = os.path.join(root, f)
                tex_files.append(full_path)
    tex_files.sort(key=lambda p: os.path.relpath(p, mod_folder_full).lower())

    rows = []
    for full_path in tex_files:
        rel_path = os.path.relpath(full_path, mod_folder_full)
        category = categorize_tex(os.path.basename(full_path))
        width = height = fmt = None
        size_kb = 0
        if show_info:
            try:
                from tex_metadata import get_tex_metadata
                width, height, fmt = get_tex_metadata(full_path)
            except Exception as e:
                log_message(f"Metadata read failed for {rel_path}: {e}")
            try:
                size_kb = int(os.path.getsize(full_path) / 1024.0)
            except Exception:
                size_kb = 0
        rows.append({
            'category': category,
            'rel_path': rel_path,
            'width': width,
            'height': height,
            'size_kb': size_kb,
            'fmt': fmt,
        })

    # Apply sorting
    order = (sort_order or "Type").lower()
    if order == "size":
        rows.sort(key=lambda r: r['size_kb'])
    elif order == "dimension":
        rows.sort(key=lambda r: (r['width'] or 0, r['height'] or 0))
    else:  # Type
        rows.sort(key=lambda r: r['category'])

    for r in rows:
        # Calculate full path for hidden column
        full_path = os.path.join(mod_folder_full, r['rel_path'])
        cols = [
            r['category'],
            r['rel_path'],
            str(r['width']) if r['width'] is not None else ("" if not show_info else "?"),
            str(r['height']) if r['height'] is not None else ("" if not show_info else "?"),
            str(r['size_kb']) if show_info else "",
            r['fmt'] if r['fmt'] is not None else ("" if not show_info else "?"),
            full_path,  # Hidden column with true path
        ]
        tex_tree_widget.addTopLevelItem(QTreeWidgetItem(cols))
