from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout,QGridLayout, QSpinBox, QTextEdit, QLabel, QSplitter, QCheckBox, QGroupBox, QLineEdit, QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem, QProgressDialog, QMessageBox, QSizePolicy
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QSplashScreen
import os
import tempfile
import sys
import shutil
from typing import Optional, Tuple, Callable
from pathlib import Path

from converter import read_tex_to_rgba
from mod_browser import (
    create_path_group,
    create_mod_list_widgets,
    scan_mods,
    build_mod_folder_map,
    populate_tex_list,
    categorize_tex,
    build_mtrl_mapping_for_mod,
)
from settings import get_settings
from tex_preview import preview_selected_tex
from processing import process_textures, downscale_nearest, quantize_id_red_channel
from converter import rgba_to_bgra_tex
from dxtex_wrapper import compress_bcx, BC1_UNORM, BC3_UNORM, BC5_UNORM, BC7_UNORM
from mtrl_parser import scan_folder_for_shaders, determine_processing_mode, ShaderType
from backup_manager import create_backup_manager, MAX_BACKUP_MODS

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XIV Downscale Utility")
        
        # Set window icon
        # Handle PyInstaller bundled mode
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
        else:
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.settings = get_settings()


        # Central widget and splitter for vertical layout
        splitter = QSplitter(Qt.Vertical)


        # Console output area (needed early for log_message)
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setPlaceholderText("meep meep, I'm an annoying console")

            

        # Top controls area: three vertical columns
        column1 = QVBoxLayout()
        column2 = QVBoxLayout()
        column3 = QVBoxLayout()


        # Path selection and mod list
        def on_scan_mods():
            scan_mods(self.path_entry.text(), self.mod_list, self.log_message)

        path_group, self.path_entry = create_path_group(self, self.settings, self.log_message, on_scan_mods)
        column1.addWidget(path_group)

        self.search_box, self.mod_list = create_mod_list_widgets(self)
        column1.addWidget(self.search_box)
        column1.addWidget(self.mod_list)
        
        # Add "Open Folder" button
        self.btn_open_folder = QPushButton("Open Mod Folder")
        column1.addWidget(self.btn_open_folder)
        
        def open_mod_folder():
            base_path = self.path_entry.text()
            if not base_path or not os.path.isdir(base_path):
                self.log_message("Please select a valid Penumbra mods path first.")
                return
            
            selected_items = self.mod_list.selectedItems()
            if selected_items:
                # Open selected mod folder
                mod_name_display = selected_items[0].text()
                mod_folder_map = build_mod_folder_map(base_path)
                mod_folder_full = mod_folder_map.get(mod_name_display)
                if mod_folder_full and os.path.isdir(mod_folder_full):
                    os.startfile(mod_folder_full)
                    self.log_message(f"Opening folder: {mod_folder_full}")
                else:
                    self.log_message(f"Could not find folder for mod: {mod_name_display}")
            else:
                # Open general mods folder
                os.startfile(base_path)
                self.log_message(f"Opening folder: {base_path}")
        
        self.btn_open_folder.clicked.connect(open_mod_folder)
        
        # Add "Restore from Backup" button
        self.btn_restore_backup = QPushButton("Restore from Backup")
        column1.addWidget(self.btn_restore_backup)
        
        def restore_backup():
            base_path = self.path_entry.text()
            if not base_path or not os.path.isdir(base_path):
                self.log_message("Please select a valid Penumbra mods path first.")
                return
            
            backup_mgr = create_backup_manager(base_path)
            if not backup_mgr:
                QMessageBox.warning(self, "Backup Error", "Could not access backup system.")
                return
            
            backups = backup_mgr.list_backups()
            if not backups:
                QMessageBox.information(self, "No Backups", "No backups found.")
                return
            
            # Show dialog to select which backup to restore
            from PySide6.QtWidgets import QDialog, QListWidget, QDialogButtonBox
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Restore from Backup")
            dialog.setMinimumWidth(600)
            dialog.setMinimumHeight(400)
            
            layout = QVBoxLayout(dialog)
            
            info_label = QLabel(
                f"<b>Backup Location:</b> {base_path}\\.dwnscl_backup<br>"
                f"<b>Available Backups:</b> {len(backups)}/{MAX_BACKUP_MODS} (last 10 mods edited)"
            )
            layout.addWidget(info_label)
            
            label = QLabel("Select a mod to restore or delete:")
            layout.addWidget(label)
            
            list_widget = QListWidget()
            for backup in backups:
                import datetime
                last_backup_dt = datetime.datetime.fromisoformat(backup["last_backup"])
                last_backup_str = last_backup_dt.strftime("%Y-%m-%d %H:%M:%S")
                item_text = f"{backup['mod_name']} - {backup['file_count']} files - Last backup: {last_backup_str}"
                list_widget.addItem(item_text)
            layout.addWidget(list_widget)
            
            # Create custom button box with Restore, Delete, and Cancel
            button_box = QDialogButtonBox()
            restore_btn = button_box.addButton("Restore", QDialogButtonBox.AcceptRole)
            delete_btn = button_box.addButton("Delete Backup", QDialogButtonBox.DestructiveRole)
            cancel_btn = button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
            
            def on_restore():
                selected_items = list_widget.selectedItems()
                if not selected_items:
                    QMessageBox.warning(dialog, "No Selection", "Please select a backup to restore.")
                    return
                dialog.accept()
            
            def on_delete():
                selected_items = list_widget.selectedItems()
                if not selected_items:
                    QMessageBox.warning(dialog, "No Selection", "Please select a backup to delete.")
                    return
                
                selected_index = list_widget.row(selected_items[0])
                backup = backups[selected_index]
                mod_name = backup["mod_name"]
                
                reply = QMessageBox.question(
                    dialog,
                    'Confirm Delete',
                    f'Delete backup for "{mod_name}"?\n\n'
                    f'This action cannot be undone.\n'
                    f'Files: {backup["file_count"]}',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    if backup_mgr.delete_backup(mod_name):
                        QMessageBox.information(dialog, "Backup Deleted", f'Backup for "{mod_name}" has been deleted.')
                        self.log_message(f'Deleted backup for {mod_name}')
                        # Close and reopen dialog to refresh list
                        dialog.reject()
                        restore_backup()  # Reopen with updated list
                    else:
                        QMessageBox.warning(dialog, "Delete Failed", f'Failed to delete backup for "{mod_name}".')
            
            restore_btn.clicked.connect(on_restore)
            delete_btn.clicked.connect(on_delete)
            cancel_btn.clicked.connect(dialog.reject)
            
            layout.addWidget(button_box)
            
            if dialog.exec() == QDialog.Accepted:
                selected_items = list_widget.selectedItems()
                if selected_items:
                    selected_index = list_widget.row(selected_items[0])
                    backup = backups[selected_index]
                    mod_name = backup["mod_name"]
                    
                    import datetime
                    last_backup_dt = datetime.datetime.fromisoformat(backup["last_backup"])
                    last_backup_str = last_backup_dt.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Confirm restore
                    reply = QMessageBox.question(
                        self,
                        'Confirm Restore',
                        f'Restore backup for "{mod_name}"?\n\n'
                        f'This will overwrite current files with the backed-up versions.\n'
                        f'Files: {backup["file_count"]}\n'
                        f'Last backup: {last_backup_str}',
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        restored, failed = backup_mgr.restore_mod(mod_name)
                        if restored > 0:
                            QMessageBox.information(
                                self,
                                'Restore Complete',
                                f'Successfully restored {restored} file(s).\n'
                                f'Failed: {failed}'
                            )
                            self.log_message(f'Restored {restored} file(s) from backup for {mod_name}')
                        else:
                            QMessageBox.warning(
                                self,
                                'Restore Failed',
                                f'Failed to restore files.\n'
                                f'Please check the console for errors.'
                            )
                            self.log_message(f'Failed to restore backup for {mod_name}')
        
        self.btn_restore_backup.clicked.connect(restore_backup)

        # Tex files list
        self.tex_list = QTreeWidget()
        self.tex_list.setColumnCount(7)
        self.tex_list.setHeaderLabels(["Category", "Path", "Width", "Height", "Size (KB)", "Format", "True Path"])
        self.tex_list.setRootIsDecorated(False)
        self.tex_list.setUniformRowHeights(True)
        # Enable multi-selection
        self.tex_list.setSelectionMode(QTreeWidget.ExtendedSelection)
        # Set fixed column widths for readability
        header = self.tex_list.header()
        try:
            from PySide6.QtWidgets import QHeaderView
            # Lock all columns except Path; let Path stretch and be resizable
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.Fixed)
            header.setSectionResizeMode(1, QHeaderView.Stretch)
            header.setSectionResizeMode(2, QHeaderView.Fixed)
            header.setSectionResizeMode(3, QHeaderView.Fixed)
            header.setSectionResizeMode(4, QHeaderView.Fixed)
            header.setSectionResizeMode(5, QHeaderView.Fixed)
            header.setSectionResizeMode(6, QHeaderView.Fixed)
        except Exception:
            pass
        # Category, Path, Width, Height, Size (KB)
        self.tex_list.setColumnWidth(0, 62)
        self.tex_list.setColumnWidth(1, 531)
        self.tex_list.setColumnWidth(2, 46)
        self.tex_list.setColumnWidth(3, 46)
        self.tex_list.setColumnWidth(4, 55)
        # Hide the True Path column (column 6)
        self.tex_list.setColumnHidden(6, True)
        
        # Enable context menu for tex list
        self.tex_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tex_list.customContextMenuRequested.connect(self.show_tex_context_menu)

        header_layout = QHBoxLayout()
        header_label = QLabel("Texture Files")
        self.chk_show_tex_info = QCheckBox("Show details")
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["Type", "Size", "Dimension"]) 
        self.chk_show_tex_info.setChecked(False)
        header_layout.addWidget(header_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.chk_show_tex_info)
        header_layout.addWidget(QLabel("Sort:"))
        header_layout.addWidget(self.combo_sort)

        column2.addLayout(header_layout)
        column2.addWidget(self.tex_list)
        
        def show_tex_files():
            self.tex_list.clear()
            selected_items = self.mod_list.selectedItems()
            if not selected_items:
                return
            mod_name_display = selected_items[0].text()
            path_to_scan = self.path_entry.text()
            if not path_to_scan or not os.path.isdir(path_to_scan):
                return
            mod_folder_map = build_mod_folder_map(path_to_scan)
            mod_folder_full = mod_folder_map.get(mod_name_display)
            if not mod_folder_full:
                return
            from mod_browser import populate_tex_tree_with_info
            populate_tex_tree_with_info(
                mod_folder_full,
                self.tex_list,
                show_info=self.chk_show_tex_info.isChecked(),
                log_message=self.log_message,
                sort_order=self.combo_sort.currentText(),
            )

        self.mod_list.itemSelectionChanged.connect(show_tex_files)
        self.chk_show_tex_info.stateChanged.connect(lambda _state: show_tex_files())
        self.combo_sort.currentTextChanged.connect(lambda _text: show_tex_files())

        # 

        # Alpha control + image preview
        alpha_controls_layout = QHBoxLayout()
        self.alpha_checkbox = QCheckBox("Opaque Alpha")
        self.alpha_checkbox.setChecked(False)
        alpha_controls_layout.addWidget(self.alpha_checkbox)
        
        self.show_alpha_checkbox = QCheckBox("Show Alpha Channel")
        self.show_alpha_checkbox.setChecked(False)
        alpha_controls_layout.addWidget(self.show_alpha_checkbox)
        alpha_controls_layout.addStretch()
        
        # Replace texture button
        self.btn_replace_texture = QPushButton("Replace Texture")
        self.btn_replace_texture.setToolTip("Replace selected texture with an image file")
        alpha_controls_layout.addWidget(self.btn_replace_texture)
        
        column3.addLayout(alpha_controls_layout)

        # Image preview layout with two labels for side-by-side display
        self.image_container = QWidget()
        self.image_layout = QHBoxLayout(self.image_container)
        self.image_layout.setContentsMargins(0, 0, 0, 0)
        self.image_layout.setSpacing(5)
        
        self.image_label = QLabel("No image selected")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 400)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_layout.addWidget(self.image_label)
        
        self.alpha_label = QLabel()
        self.alpha_label.setAlignment(Qt.AlignCenter)
        self.alpha_label.setMinimumSize(400, 400)
        self.alpha_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.alpha_label.hide()  # Hidden by default
        self.image_layout.addWidget(self.alpha_label)
        
        # Set image container to expand vertically to take available space
        self.image_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        column3.addWidget(self.image_container, 1)  # Add stretch factor
        
        # Add stretch to push settings to bottom and maximize image preview space
        column3.addStretch()

        # Detailed per-type settings group box
        detail_group = QGroupBox("Conversion Settings")
        detail_layout = QVBoxLayout()
        detail_layout.setSpacing(5)  # Tighter spacing
        detail_layout.setContentsMargins(5, 5, 5, 5)  # Smaller margins
        
        # Save behaviour selection and uniform textures checkbox on same row
        behaviour_layout = QHBoxLayout()
        behaviour_label = QLabel("Saving:")
        self.combo_behaviour = QComboBox()
        self.combo_behaviour.addItems(["Modify in-place (!)", "Create copy"])
        self.combo_behaviour.setCurrentText("Create copy")
        behaviour_layout.addWidget(behaviour_label)
        behaviour_layout.addWidget(self.combo_behaviour)
        
        # Add uniform textures checkbox to same row
        self.chk_uniform_optimize = QCheckBox("Downscale uniform color textures to 8x8px")
        self.chk_uniform_optimize.setChecked(True)
        self.chk_uniform_optimize.setToolTip("Automatically reduce single-color textures to minimal size")
        behaviour_layout.addWidget(self.chk_uniform_optimize)
        behaviour_layout.addStretch()
        detail_layout.addLayout(behaviour_layout)
        
        # Create grid for per-type controls

        detail_grid = QGridLayout()
        
        # Define texture types (Global comes first)
        tex_types = ["Global", "Diffuse", "Normal", "Specular", "ID", "Mask", "Other"]
        
        # Row 0: Headers
        detail_grid.addWidget(QLabel("Type"), 0, 0)
        detail_grid.addWidget(QLabel("Downscale %"), 1, 0)
        detail_grid.addWidget(QLabel("Min Size (px)"), 2, 0)
        detail_grid.addWidget(QLabel("Format"), 3, 0)
        detail_grid.addWidget(QLabel("Options"), 4, 0)
        
        # Store controls for each type
        self.type_downscale_spinboxes = {}
        self.type_minsize_spinboxes = {}
        self.type_format_combos = {}
        self.type_align_checkboxes = {}
        
        # Global controls (will update all types)
        self.global_downscale = None
        self.global_minsize = None
        self.global_format = None
        
        # Custom spinbox class for power-of-2 values
        class PowerOf2SpinBox(QSpinBox):
            def __init__(self, parent=None):
                super().__init__(parent)
                self._powers = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096]
                
            def stepBy(self, steps):
                current = self.value()
                # Find current index in powers list
                try:
                    current_idx = self._powers.index(current)
                except ValueError:
                    # If not in list, find nearest
                    import math
                    power = round(math.log2(current))
                    snapped = 2 ** power
                    current_idx = self._powers.index(snapped) if snapped in self._powers else 5
                
                # Move by steps
                new_idx = max(0, min(len(self._powers) - 1, current_idx + steps))
                self.setValue(self._powers[new_idx])
        
        # Create controls for each type
        for col_idx, tex_type in enumerate(tex_types, start=1):
            # Type label
            type_label = QLabel(tex_type)
            if tex_type == "Global":
                type_label.setStyleSheet("font-weight: bold;")
            detail_grid.addWidget(type_label, 0, col_idx)
            
            # Downscale percentage spinbox
            downscale_spin = QSpinBox()
            downscale_spin.setRange(1, 100)
            downscale_spin.setValue(100)
            downscale_spin.setSingleStep(5)
            downscale_spin.setSuffix("%")
            downscale_spin.setMaximumWidth(70)
            detail_grid.addWidget(downscale_spin, 1, col_idx)
            
            if tex_type == "Global":
                self.global_downscale = downscale_spin
                # Connect global to update all types
                downscale_spin.valueChanged.connect(self.update_all_downscale)
            else:
                self.type_downscale_spinboxes[tex_type.lower()] = downscale_spin
            
            # Minimum size spinbox (powers of 2)
            minsize_spin = PowerOf2SpinBox()
            minsize_spin.setRange(16, 4096)
            minsize_spin.setValue(512)
            minsize_spin.setSuffix("px")
            minsize_spin.setMaximumWidth(80)
            detail_grid.addWidget(minsize_spin, 2, col_idx)
            
            if tex_type == "Global":
                self.global_minsize = minsize_spin
                # Connect global to update all types
                minsize_spin.valueChanged.connect(self.update_all_minsize)
            else:
                self.type_minsize_spinboxes[tex_type.lower()] = minsize_spin
            
            # Format combo box
            format_combo = QComboBox()
            format_combo.addItems(["Keep", "BC7 Smart", "BC7 Force"])
            format_combo.setCurrentText("Keep")
            format_combo.setMaximumWidth(100)
            detail_grid.addWidget(format_combo, 3, col_idx)
            
            if tex_type == "Global":
                self.global_format = format_combo
                # Connect global to update all types
                format_combo.currentTextChanged.connect(self.update_all_format)
            else:
                self.type_format_combos[tex_type.lower()] = format_combo
            
            # Options (Align ID checkbox for ID type only, empty for Global and others)
            if tex_type.lower() == "id":
                align_chk = QCheckBox("Align")
                align_chk.setChecked(False)
                align_chk.setToolTip("Quantize to exact target values")
                detail_grid.addWidget(align_chk, 4, col_idx)
                self.type_align_checkboxes[tex_type.lower()] = align_chk
            else:
                detail_grid.addWidget(QLabel(""), 4, col_idx)
        
        detail_layout.addLayout(detail_grid)
        
        # Convert buttons layout (main button + selected only button)
        buttons_layout = QHBoxLayout()
        
        # Main convert button (green, takes 2/3 of space)
        self.btn_convert_detailed = QPushButton("Convert!")
        self.btn_convert_detailed.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        buttons_layout.addWidget(self.btn_convert_detailed, 2)
        
        # Convert selected only button (takes 1/3 of space)
        self.btn_convert_selected = QPushButton("Selected Only")
        self.btn_convert_selected.setToolTip("Convert only the selected textures with per-type settings")
        buttons_layout.addWidget(self.btn_convert_selected, 1)
        
        detail_layout.addLayout(buttons_layout)
        
        detail_group.setLayout(detail_layout)
        # Set size policy to prefer minimum vertical space
        detail_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        column3.addWidget(detail_group)

        # Extra tools button
        self.btn_extra_tools = QPushButton("Extra Tools...")
        column3.addWidget(self.btn_extra_tools)

        # When a tex file is selected, show its image in column 3
        def show_tex_image():
            preview_selected_tex(
                self.tex_list,
                self.mod_list,
                self.path_entry,
                self.image_label,
                self.log_message,
                force_opaque_alpha=self.alpha_checkbox.isChecked(),
                show_alpha_separate=self.show_alpha_checkbox.isChecked(),
                alpha_label=self.alpha_label,
            )

        self.tex_list.itemSelectionChanged.connect(show_tex_image)
        self.alpha_checkbox.stateChanged.connect(lambda _state: show_tex_image())
        self.show_alpha_checkbox.stateChanged.connect(lambda _state: show_tex_image())

        # Replace texture functionality
        def replace_texture():
            """Replace selected texture with an image file."""
            from PySide6.QtWidgets import QFileDialog
            from PIL import Image
            from converter import rgba_to_bgra_tex
            
            # Check that exactly 1 texture is selected
            selected_items = self.tex_list.selectedItems()
            if len(selected_items) == 0:
                QMessageBox.warning(self, 'No Selection', 'Please select exactly one texture file to replace.')
                return
            elif len(selected_items) > 1:
                QMessageBox.warning(self, 'Multiple Selection', 'Please select only one texture file to replace.')
                return
            
            # Get the selected texture path
            selected_item = selected_items[0]
            tex_path = selected_item.text(6)  # Hidden column with true path
            
            if not tex_path or not os.path.isfile(tex_path):
                QMessageBox.warning(self, 'Invalid Selection', 'Selected texture file not found.')
                return
            
            # Open file dialog to select image
            image_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Image to Replace Texture",
                "",
                "Image Files (*.png *.jpg *.jpeg *.bmp *.dds);;All Files (*.*)"
            )
            
            if not image_path:
                return  # User cancelled
            
            try:
                # Load image and convert to RGBA
                img = Image.open(image_path)
                
                # Convert to RGBA if needed
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                width, height = img.size
                rgba_bytes = img.tobytes()
                
                # Show confirmation with size info
                reply = QMessageBox.question(
                    self,
                    'Confirm Replacement',
                    f'Replace texture with:\n'
                    f'Source: {os.path.basename(image_path)}\n'
                    f'Size: {width}x{height}\n'
                    f'Target: {os.path.basename(tex_path)}\n\n'
                    f'This will overwrite the texture file. Continue?',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    return
                
                # Create backup
                backup_path = tex_path + '.backup'
                if not os.path.exists(backup_path):
                    shutil.copy2(tex_path, backup_path)
                    self.log_message(f'Created backup: {os.path.basename(backup_path)}')
                
                # Convert to .tex format (BGRA8/ARGB8)
                rgba_to_bgra_tex(rgba_bytes, width, height, saving_path=tex_path)
                
                self.log_message(f'Replaced texture: {os.path.basename(tex_path)} with {os.path.basename(image_path)} ({width}x{height})')
                
                # Refresh preview
                show_tex_image()
                
                QMessageBox.information(
                    self,
                    'Success',
                    f'Texture replaced successfully!\n\n'
                    f'Original backed up to:\n{os.path.basename(backup_path)}'
                )
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    'Error',
                    f'Failed to replace texture:\n{str(e)}'
                )
                self.log_message(f'Error replacing texture: {e}')
        
        self.btn_replace_texture.clicked.connect(replace_texture)

        self.btn_convert_detailed.clicked.connect(self.processing_v2)
        self.btn_convert_selected.clicked.connect(self.processing_v2_selected)

        # Extra tools menu
        def show_extra_tools_menu():
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QTextEdit
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Extra Tools")
            dialog.setMinimumSize(600, 500)
            
            layout = QVBoxLayout()
            
            # Statistics button
            btn_stats = QPushButton("Scan All Mods - Texture Statistics")
            layout.addWidget(btn_stats)
            
            # Unknown textures button
            btn_unknown = QPushButton("List Unknown/Other Textures")
            layout.addWidget(btn_unknown)
            
            # Restore downscaled mod button
            btn_restore = QPushButton("Replace Original with Downscaled Mod")
            layout.addWidget(btn_restore)
            
            # Output text area
            output_text = QTextEdit()
            output_text.setReadOnly(True)
            layout.addWidget(output_text)
            
            # Close button
            btn_close = QPushButton("Close")
            btn_close.clicked.connect(dialog.close)
            layout.addWidget(btn_close)
            
            def scan_all_mods_statistics():
                output_text.clear()
                output_text.append("Scanning all mods for texture statistics...\n")
                
                base_path = self.path_entry.text()
                if not base_path or not os.path.isdir(base_path):
                    output_text.append("Error: Please select a valid Penumbra mods path first.")
                    return
                
                from collections import defaultdict
                from tex_metadata import get_tex_metadata
                
                # Statistics containers
                total_tex_files = 0
                type_stats = defaultdict(lambda: {
                    'count': 0,
                    'formats': defaultdict(int),
                    'resolutions': defaultdict(int)
                })
                
                # Scan all mods
                mod_folder_map = build_mod_folder_map(base_path)
                total_mods = len(mod_folder_map)
                output_text.append(f"Found {total_mods} mods to scan...\n")
                
                for mod_idx, (mod_name, mod_folder_full) in enumerate(mod_folder_map.items(), 1):
                    output_text.append(f"[{mod_idx}/{total_mods}] Scanning: {mod_name}")
                    QApplication.processEvents()  # Keep UI responsive
                    
                    # Build mtrl mapping for this mod for accurate categorization
                    mtrl_mapping = build_mtrl_mapping_for_mod(mod_folder_full)
                    
                    # Walk through mod folder
                    for root, _, files in os.walk(mod_folder_full):
                        for file in files:
                            if not file.lower().endswith('.tex'):
                                continue
                            
                            total_tex_files += 1
                            full_path = os.path.join(root, file)
                            
                            # Categorize texture (with mtrl mapping for accuracy)
                            category = categorize_tex(file, mod_folder_full, mtrl_mapping).lower()
                            if category == 'unknown':
                                category = 'other'
                            
                            # Get metadata
                            width, height, fmt_name = get_tex_metadata(full_path)
                            
                            # Update statistics
                            type_stats[category]['count'] += 1
                            
                            if fmt_name:
                                type_stats[category]['formats'][fmt_name] += 1
                            else:
                                type_stats[category]['formats']['unknown'] += 1
                            
                            if width and height:
                                # Round to nearest 32px
                                rounded_w = round(width / 32) * 32
                                rounded_h = round(height / 32) * 32
                                res_key = f"{rounded_w}x{rounded_h}"
                                type_stats[category]['resolutions'][res_key] += 1
                            else:
                                type_stats[category]['resolutions']['unknown'] += 1
                
                # Display results
                output_text.append("\n" + "="*60)
                output_text.append(f"TEXTURE STATISTICS SUMMARY")
                output_text.append("="*60 + "\n")
                output_text.append(f"Total .tex files found: {total_tex_files}\n")
                
                # Sort categories for consistent output
                categories = sorted(type_stats.keys())
                
                for category in categories:
                    stats = type_stats[category]
                    output_text.append(f"\n--- {category.upper()} ---")
                    output_text.append(f"Total files: {stats['count']}")
                    
                    # Format distribution
                    output_text.append("\nFormat Distribution:")
                    sorted_formats = sorted(stats['formats'].items(), key=lambda x: x[1], reverse=True)
                    for fmt, count in sorted_formats:
                        percentage = (count / stats['count']) * 100
                        output_text.append(f"  {fmt}: {count} ({percentage:.1f}%)")
                    
                    # Resolution distribution
                    output_text.append("\nResolution Distribution:")
                    sorted_resolutions = sorted(stats['resolutions'].items(), key=lambda x: x[1], reverse=True)
                    for res, count in sorted_resolutions:
                        percentage = (count / stats['count']) * 100
                        output_text.append(f"  {res}: {count} ({percentage:.1f}%)")
                
                output_text.append("\n" + "="*60)
                output_text.append("Scan complete!")
            
            btn_stats.clicked.connect(scan_all_mods_statistics)
            
            def list_unknown_textures():
                output_text.clear()
                output_text.append("Scanning all mods for Unknown/Other textures...\n")
                
                base_path = self.path_entry.text()
                if not base_path or not os.path.isdir(base_path):
                    output_text.append("Error: Please select a valid Penumbra mods path first.")
                    return
                
                # Collect unknown texture filenames
                unknown_textures = set()
                
                # Scan all mods
                mod_folder_map = build_mod_folder_map(base_path)
                total_mods = len(mod_folder_map)
                output_text.append(f"Found {total_mods} mods to scan...\n")
                
                for mod_idx, (mod_name, mod_folder_full) in enumerate(mod_folder_map.items(), 1):
                    output_text.append(f"[{mod_idx}/{total_mods}] Scanning: {mod_name}")
                    QApplication.processEvents()  # Keep UI responsive
                    
                    # Build mtrl mapping for this mod for accurate categorization
                    mtrl_mapping = build_mtrl_mapping_for_mod(mod_folder_full)
                    
                    # Walk through mod folder
                    for root, _, files in os.walk(mod_folder_full):
                        for file in files:
                            if not file.lower().endswith('.tex'):
                                continue
                            
                            # Categorize texture (with mtrl mapping for accuracy)
                            category = categorize_tex(file, mod_folder_full, mtrl_mapping)
                            if category.lower() in ['unknown', 'other']:
                                unknown_textures.add(file)
                
                # Display results
                output_text.append("\n" + "="*60)
                output_text.append(f"UNKNOWN/OTHER TEXTURES")
                output_text.append("="*60 + "\n")
                output_text.append(f"Total unknown/other textures found: {len(unknown_textures)}\n")
                
                if unknown_textures:
                    output_text.append("\nFilenames (sorted alphabetically):")
                    for filename in sorted(unknown_textures):
                        output_text.append(f"  {filename}")
                else:
                    output_text.append("\nNo unknown/other textures found!")
                
                output_text.append("\n" + "="*60)
                output_text.append("Scan complete!")
            
            btn_unknown.clicked.connect(list_unknown_textures)
            
            def restore_downscaled_mod():
                output_text.clear()
                output_text.append("Replacing original mod with downscaled version...\n")
                
                # Get the selected mod
                selected_items = self.mod_list.selectedItems()
                if not selected_items:
                    output_text.append("Error: Please select a mod from the mod list first.")
                    return
                
                mod_name_display = selected_items[0].text()
                base_path = self.path_entry.text()
                if not base_path or not os.path.isdir(base_path):
                    output_text.append("Error: Please select a valid Penumbra mods path first.")
                    return
                
                # Check if this is a downscaled mod
                if "[Downscaled]" not in mod_name_display:
                    output_text.append(f"Error: Selected mod '{mod_name_display}' is not a downscaled mod.")
                    output_text.append("Please select a mod with '[Downscaled]' in its name.")
                    return
                
                mod_folder_map = build_mod_folder_map(base_path)
                downscaled_folder = mod_folder_map.get(mod_name_display)
                
                if not downscaled_folder or not os.path.isdir(downscaled_folder):
                    output_text.append(f"Error: Could not find mod folder for '{mod_name_display}'")
                    return
                
                # Calculate original mod name (remove [Downscaled])
                original_mod_name = mod_name_display.replace(" [Downscaled]", "").replace("[Downscaled] ", "").replace("[Downscaled]", "").strip()
                original_folder = mod_folder_map.get(original_mod_name)
                
                output_text.append(f"Downscaled mod: {mod_name_display}")
                output_text.append(f"Original mod: {original_mod_name}")
                
                if not original_folder or not os.path.isdir(original_folder):
                    output_text.append(f"\nWarning: Original mod '{original_mod_name}' not found.")
                    output_text.append("Will only rename the downscaled mod.\n")
                    original_exists = False
                else:
                    output_text.append(f"\nOriginal mod folder exists at:")
                    output_text.append(f"  {original_folder}\n")
                    original_exists = True
                
                # Show confirmation dialog
                from PySide6.QtWidgets import QMessageBox
                
                if original_exists:
                    message = (
                        f'This will:\n'
                        f'1. DELETE the original mod: "{original_mod_name}"\n'
                        f'2. RENAME the downscaled mod to: "{original_mod_name}"\n\n'
                        f'WARNING: The original mod will be permanently deleted!\n\n'
                        f'Continue?'
                    )
                else:
                    message = (
                        f'This will rename the downscaled mod:\n'
                        f'From: "{mod_name_display}"\n'
                        f'To: "{original_mod_name}"\n\n'
                        f'Continue?'
                    )
                
                reply = QMessageBox.question(
                    dialog,
                    'Confirm Mod Replacement',
                    message,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    output_text.append("Operation cancelled by user.")
                    return
                
                try:
                    # Step 1: Delete original mod if it exists
                    if original_exists:
                        output_text.append(f"Deleting original mod folder...")
                        shutil.rmtree(original_folder)
                        output_text.append(f"✓ Deleted: {original_folder}\n")
                    
                    # Step 2: Rename downscaled mod
                    output_text.append(f"Renaming downscaled mod...")
                    
                    # Calculate new folder path (remove [Downscaled] from folder name)
                    downscaled_folder_name = os.path.basename(downscaled_folder)
                    new_folder_name = downscaled_folder_name.replace(" [Downscaled]", "").replace("[Downscaled] ", "").replace("[Downscaled]", "").strip()
                    new_folder_path = os.path.join(os.path.dirname(downscaled_folder), new_folder_name)
                    
                    os.rename(downscaled_folder, new_folder_path)
                    output_text.append(f"✓ Renamed to: {new_folder_path}\n")
                    
                    # Step 3: Update meta.json
                    output_text.append(f"Updating meta.json...")
                    meta_json_path = os.path.join(new_folder_path, "meta.json")
                    
                    if os.path.exists(meta_json_path):
                        try:
                            import json
                            
                            # Read meta.json
                            with open(meta_json_path, 'r', encoding='utf-8') as f:
                                meta_data = json.load(f)
                            
                            # Update the Name field
                            if 'Name' in meta_data:
                                old_name = meta_data['Name']
                                new_name = old_name.replace(" [Downscaled]", "").replace("[Downscaled] ", "").replace("[Downscaled]", "").strip()
                                meta_data['Name'] = new_name
                                
                                # Write back
                                with open(meta_json_path, 'w', encoding='utf-8') as f:
                                    json.dump(meta_data, f, indent=4, ensure_ascii=False)
                                
                                output_text.append(f"✓ Updated meta.json: '{old_name}' → '{new_name}'\n")
                            else:
                                output_text.append(f"⚠ meta.json has no 'Name' field\n")
                        except Exception as e:
                            output_text.append(f"⚠ Failed to update meta.json: {str(e)}\n")
                    else:
                        output_text.append(f"⚠ meta.json not found\n")
                    
                    # Summary
                    output_text.append("="*60)
                    output_text.append("REPLACEMENT COMPLETE")
                    output_text.append("="*60)
                    if original_exists:
                        output_text.append(f"Original mod deleted")
                    output_text.append(f"Downscaled mod is now: {original_mod_name}")
                    output_text.append("="*60)
                    
                    self.log_message(f"Replaced original mod with downscaled version: {original_mod_name}")
                    
                    # Refresh mod list
                    output_text.append("\nRefreshing mod list...")
                    from mod_browser import scan_mods
                    scan_mods(base_path, self.mod_list, self.log_message)
                    
                except Exception as e:
                    output_text.append(f"\n✗ Error: {str(e)}")
                    self.log_message(f"Error replacing mod: {str(e)}")
            
            btn_restore.clicked.connect(restore_downscaled_mod)
            
            dialog.setLayout(layout)
            dialog.exec()
        
        self.btn_extra_tools.clicked.connect(show_extra_tools_menu)

        # Use a QSplitter for the top controls area to make columns resizable
        top_splitter = QSplitter(Qt.Horizontal)
        col1_widget = QWidget()
        col1_widget.setLayout(column1)
        col2_widget = QWidget()
        col2_widget.setLayout(column2)
        col3_widget = QWidget()
        col3_widget.setLayout(column3)
        top_splitter.addWidget(col1_widget)
        top_splitter.addWidget(col2_widget)
        top_splitter.addWidget(col3_widget)
        # Proportional stretch: 15% / 50% / 35%
        top_splitter.setStretchFactor(0, 15)
        top_splitter.setStretchFactor(1, 50)
        top_splitter.setStretchFactor(2, 35)

        # Add top splitter and console to main splitter
        splitter.addWidget(top_splitter)
        splitter.addWidget(self.console_output)
        splitter.setSizes([80, 20])

        self.setCentralWidget(splitter)
    
    def update_all_downscale(self, value):
        """Update all texture type downscale percentages from global"""
        for spinbox in self.type_downscale_spinboxes.values():
            spinbox.setValue(value)
    
    def update_all_minsize(self, value):
        """Update all texture type minimum sizes from global"""
        for spinbox in self.type_minsize_spinboxes.values():
            spinbox.setValue(value)
    
    def update_all_format(self, text):
        """Update all texture type formats from global"""
        for combo in self.type_format_combos.values():
            combo.setCurrentText(text)
    
    def show_tex_context_menu(self, position):
        """Show context menu for texture list"""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        item = self.tex_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        
        # Copy file path action
        copy_path_action = QAction("Copy File Path", self)
        copy_path_action.triggered.connect(lambda: self.copy_tex_path(item))
        menu.addAction(copy_path_action)
        
        # Show menu at cursor position
        menu.exec(self.tex_list.viewport().mapToGlobal(position))
    
    def copy_tex_path(self, item):
        """Copy texture file path to clipboard"""
        true_path = item.text(6)  # Hidden column with true path
        if true_path:
            clipboard = QApplication.clipboard()
            clipboard.setText(true_path)
            self.log_message(f"Copied to clipboard: {true_path}")
    
    def log_message(self, message):
        self.console_output.append(message)

    def update_progress(self, message): #WILL NEED HOOKING UP
        self.console_output.append(message)
        # Update progress based on log messages
        if message.startswith('Downscaling') or message.startswith('BC7 compressed'):
            self.processed_count[0] += 1
            if self.total_count[0] > 0:
                self.progress.setValue(int((self.processed_count[0] / self.total_count[0]) * 100))
            self.progress.setLabelText(f"Processing... ({self.processed_count[0]}/{self.total_count[0]})")
        elif message.startswith('Done.'):
            self.progress.setValue(100)

    def processing_v2(self):
        """
        Like the thing above, but better.

        -Make temp
        -Process in temp
            -Downscaling
            -Processing for special file types
            -Compression
        -Apply changes back to original or new copy


        """
        destination = self.combo_behaviour.currentText()
        
        # Show confirmation dialog for "Modify in-place" mode
        if destination == 'Modify in-place (!)':
            reply = QMessageBox.question(
                self,
                'Confirm In-Place Modification',
                'This will modify your mod files directly. While changes are processed safely, '
                'it is recommended to have a backup.\n\nContinue?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # Create progress dialog
        progress = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Processing Textures")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        cancel_requested = [False]
        progress.canceled.connect(lambda: cancel_requested.__setitem__(0, True))
        
        #           Calculate initial file sizes - process all files in selected mod
        initial_size = 0
        source_folder = None
        
        selected_mod_items = self.mod_list.selectedItems()
        if selected_mod_items:
            mod_name_display = selected_mod_items[0].text()
            base_mods_path = self.path_entry.text()
            mod_folder_map = build_mod_folder_map(base_mods_path)
            source_folder = mod_folder_map.get(mod_name_display)
            if source_folder and os.path.isdir(source_folder):
                for root, _, files in os.walk(source_folder):
                    for f in files:
                        if f.lower().endswith('.tex'):
                            initial_size += os.path.getsize(os.path.join(root, f))
        
        self.log_message(f'Initial texture size: {initial_size / (1024*1024):.2f} MB')
        
        if cancel_requested[0]:
            progress.close()
            self.log_message('Processing cancelled by user')
            return
        #     selected_items = self.tex_list.selectedItems()
        #     if selected_items:
        #         for item in selected_items:
        #             true_path = item.text(6)  # Hidden column with true path
        #             original_files.append(true_path)
        # elif scope == 'All files':
        #     for line in range(self.tex_list.topLevelItemCount()):
        #         item = self.tex_list.topLevelItem(line)
        #         true_path = item.text(6)  # Hidden column with true path
        #         original_files.append(true_path)
        # elif scope == 'Other folder':
        #     # Scan other folder for .tex files
        #     other_folder = self.other_folder_edit.text()
        #     if os.path.isdir(other_folder):
        #         for root, _, files in os.walk(other_folder):
        #             for f in files:
        #                 if f.lower().endswith('.tex'):
        #                     full_path = os.path.join(root, f)
        #                     original_files.append(full_path)

        #           Create temp folder
        progress.setLabelText("Creating temporary workspace...")
        progress.setValue(5)
        temp_dir = tempfile.TemporaryDirectory()
        temp_path = temp_dir.name  

        #           Copy files to temp - copy whole mod folder
        progress.setLabelText("Copying files to temporary workspace...")
        progress.setValue(10)
        
        # Copy whole mod folder to temp
        selected_mod_items = self.mod_list.selectedItems()
        if selected_mod_items:
            mod_name_display = selected_mod_items[0].text()
            base_mods_path = self.path_entry.text()
            mod_folder_map = build_mod_folder_map(base_mods_path)
            mod_folder_full = mod_folder_map.get(mod_name_display)
            if mod_folder_full and os.path.isdir(mod_folder_full):
                temp_mod_path = os.path.join(temp_path, os.path.basename(mod_folder_full))
                shutil.copytree(mod_folder_full, temp_mod_path)
        
        if cancel_requested[0]:
            temp_dir.cleanup()
            progress.close()
            self.log_message('Processing cancelled by user')
            return

        #           Get all .tex files in temp
        progress.setLabelText("Scanning texture files...")
        progress.setValue(15)
        temp_tex_files = []
        for root, _, files in os.walk(temp_path):
            for f in files:
                if f.lower().endswith('.tex'):
                    full_path = os.path.join(root, f)
                    temp_tex_files.append(full_path)

        #           Scan for shader types to determine processing strategy
        self.log_message("Scanning material files for shader types...")
        shader_types = scan_folder_for_shaders(Path(temp_path))
        processing_mode = determine_processing_mode(shader_types)
        
        shader_type_names = [s.value for s in shader_types] if shader_types else ["none"]
        self.log_message(f"Found shader types: {', '.join(shader_type_names)}")
        self.log_message(f"Processing mode: {processing_mode}")
        
        # Determine compression strategy based on processing mode
        if processing_mode == "skin":
            self.log_message("Skin shader detected: Using RGBA quality for Normal, Mask, Diffuse")
            use_rgba_quality = True
            use_rgb_optimization = False
        elif processing_mode == "character":
            self.log_message("Character shader detected: Using RGB optimization (RG for ID)")
            use_rgba_quality = False
            use_rgb_optimization = True
        else:
            self.log_message("Other shader types: Using RGBA optimization")
            use_rgba_quality = True
            use_rgb_optimization = False

        tex_diffuse = []
        tex_normal = []
        tex_id = []
        tex_specular = []
        tex_mask = []
        tex_other = []

        # Build mtrl mapping for accurate categorization
        mtrl_mapping = build_mtrl_mapping_for_mod(temp_path)
        if mtrl_mapping:
            self.log_message(f"Using material file mappings for {len(mtrl_mapping)} textures")

        #           classify files
        for tex_file in temp_tex_files:
            file_type = categorize_tex(tex_file, temp_path, mtrl_mapping)
            if file_type == 'Diffuse':
                tex_diffuse.append(tex_file)
            elif file_type == 'Normal':
                tex_normal.append(tex_file)
            elif file_type == 'ID':
                tex_id.append(tex_file)
            elif file_type == 'Specular':
                tex_specular.append(tex_file)
            elif file_type == 'Mask':
                tex_mask.append(tex_file)
            else:
                tex_other.append(tex_file)
        
        # Calculate total operations for progress tracking
        total_textures = len(tex_diffuse) + len(tex_normal) + len(tex_id) + len(tex_specular) + len(tex_mask) + len(tex_other)
        if total_textures == 0:
            self.log_message('No textures to process')
            temp_dir.cleanup()
            progress.close()
            return
        
        self.log_message(f'Found {total_textures} textures to process:')
        self.log_message(f'  Diffuse: {len(tex_diffuse)}, Normal: {len(tex_normal)}, ID: {len(tex_id)}')
        self.log_message(f'  Specular: {len(tex_specular)}, Mask: {len(tex_mask)}, Other: {len(tex_other)}')
        
        processed_count = [0]
        
        def update_progress():
            if total_textures > 0:
                progress.setValue(15 + int((processed_count[0] / total_textures) * 70))
                progress.setLabelText(f"Processing textures... ({processed_count[0]}/{total_textures})")
            if cancel_requested[0]:
                raise Exception("Processing cancelled by user")
        
        def is_uniform_color(rgba_bytes: bytes, w: int, h: int) -> bool:
            """Check if texture is a single uniform color"""
            if len(rgba_bytes) < 4:
                return False
            # Get first pixel
            first_pixel = rgba_bytes[0:4]
            # Check if all pixels match
            for i in range(0, len(rgba_bytes), 4):
                if rgba_bytes[i:i+4] != first_pixel:
                    return False
            return True
            
        #       Downscaling
        progress.setLabelText("Processing textures...")
        progress.setValue(20)
        diffuse_fac = self.type_downscale_spinboxes['diffuse'].value() / 100.0
        normal_fac = self.type_downscale_spinboxes['normal'].value() / 100.
        id_fac = self.type_downscale_spinboxes['id'].value() / 100.0
        specular_fac = self.type_downscale_spinboxes['specular'].value() / 100.0
        mask_fac = self.type_downscale_spinboxes['mask'].value() / 100.
        other_fac = self.type_downscale_spinboxes['other'].value() / 100.0


                                                            #DIFFUSE
        for tex in tex_diffuse:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                target_w = max(1, int(w * diffuse_fac))
                target_h = max(1, int(h * diffuse_fac))
                
                # Enforce minimum size
                min_size = self.type_minsize_spinboxes['diffuse'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                # Check if uniform color optimization is enabled
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                # Apply compression if needed
                format_mode = self.type_format_combos['diffuse'].currentText()
                if format_mode != 'Keep':
                    # Shader-based processing:
                    # - Skin: RGBA quality (BC7)
                    # - Character: RGB optimization (BC7 or BC1)
                    # - Other: RGBA (BC7)
                    optimize = format_mode == 'BC7 Smart'
                    dds = compress_bcx(new_rgba, target_w, target_h, BC7_UNORM)
                    from dxtex_wrapper import dds_to_tex
                    new_tex = dds_to_tex(dds)
                    with open(tex, 'wb') as f:
                        f.write(new_tex)
                    self.log_message(f'Processed diffuse: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled diffuse: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing diffuse {os.path.basename(tex)}: {e}')
                processed_count[0] += 1
                                                            #NORMAL
        for tex in tex_normal:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                target_w = max(1, int(w * normal_fac))
                target_h = max(1, int(h * normal_fac))
                
                # Enforce minimum size
                min_size = self.type_minsize_spinboxes['normal'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                # Check if uniform color optimization is enabled
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                # Apply compression if needed
                format_mode = self.type_format_combos['normal'].currentText()
                if format_mode != 'Keep':
                    # Normal maps should use BC5 for best quality
                    # Shader-based: All modes benefit from BC5 for normals
                    from dxtex_wrapper import BC5_UNORM, dds_to_tex
                    dds = compress_bcx(new_rgba, target_w, target_h, BC5_UNORM)
                    new_tex = dds_to_tex(dds)
                    with open(tex, 'wb') as f:
                        f.write(new_tex)
                    self.log_message(f'Processed normal: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled normal: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing normal {os.path.basename(tex)}: {e}')
                processed_count[0] += 1
                                                            #ID
        for tex in tex_id:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                # Align ID ranges if checkbox is checked
                if self.type_align_checkboxes['id'] and self.type_align_checkboxes['id'].isChecked():
                    rgba, _ = quantize_id_red_channel(rgba, w, h, log=None)
                    self.log_message(f'Aligned ID ranges: {os.path.basename(tex)}')

                target_w = max(1, int(w * id_fac))
                target_h = max(1, int(h * id_fac))
                
                # Enforce minimum size
                min_size = self.type_minsize_spinboxes['id'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                # Check if uniform color optimization is enabled
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                # Apply compression if needed
                format_mode = self.type_format_combos['id'].currentText()
                if format_mode != 'Keep':
                    # ID textures: All shader modes use RG channel optimization
                    optimize = format_mode == 'BC7 Smart'
                    dds = self.id_bc7_compress(new_rgba, target_w, target_h, tex, optimize=optimize)
                    if dds:
                        from dxtex_wrapper import dds_to_tex
                        new_tex = dds_to_tex(dds)
                        with open(tex, 'wb') as f:
                            f.write(new_tex)
                        self.log_message(f'Processed ID: {os.path.basename(tex)}')
                    else:
                        rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                        self.log_message(f'Downscaled ID: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled ID: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing ID {os.path.basename(tex)}: {e}')
                processed_count[0] += 1

                                                            #SPECULAR
        for tex in tex_specular:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                target_w = max(1, int(w * specular_fac))
                target_h = max(1, int(h * specular_fac))
                
                # Enforce minimum size
                min_size = self.type_minsize_spinboxes['specular'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                # Check if uniform color optimization is enabled
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                # Apply compression if needed
                format_mode = self.type_format_combos['specular'].currentText()
                if format_mode != 'Keep':
                    optimize = format_mode == 'BC7 Smart'
                    dds = compress_bcx(new_rgba, target_w, target_h, BC7_UNORM)
                    from dxtex_wrapper import dds_to_tex
                    new_tex = dds_to_tex(dds)
                    with open(tex, 'wb') as f:
                        f.write(new_tex)
                    self.log_message(f'Processed specular: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled specular: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing specular {os.path.basename(tex)}: {e}')
                processed_count[0] += 1
                                                            #MASK
        for tex in tex_mask:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                target_w = max(1, int(w * mask_fac))
                target_h = max(1, int(h * mask_fac))
                
                # Enforce minimum size
                min_size = self.type_minsize_spinboxes['mask'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                # Check if uniform color optimization is enabled
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                # Apply compression if needed
                format_mode = self.type_format_combos['mask'].currentText()
                if format_mode != 'Keep':
                    # Check if mask is single-channel (grayscale) or multi-channel
                    # Single-channel masks benefit from BC4, but multi-channel need BC7
                    is_grayscale = True
                    for i in range(0, len(new_rgba), 4):
                        r, g, b = new_rgba[i], new_rgba[i+1], new_rgba[i+2]
                        if r != g or g != b:
                            is_grayscale = False
                            break
                    
                    if is_grayscale:
                        # Use BC4 for grayscale masks
                        from dxtex_wrapper import BC4_UNORM, dds_to_tex
                        dds = compress_bcx(new_rgba, target_w, target_h, BC4_UNORM)
                    else:
                        # Use BC7 for color masks
                        dds = compress_bcx(new_rgba, target_w, target_h, BC7_UNORM)
                    
                    new_tex = dds_to_tex(dds)
                    with open(tex, 'wb') as f:
                        f.write(new_tex)
                    self.log_message(f'Processed mask: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled mask: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing mask {os.path.basename(tex)}: {e}')
                processed_count[0] += 1
                                                            #OTHER
        for tex in tex_other:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                target_w = max(1, int(w * other_fac))
                target_h = max(1, int(h * other_fac))
                
                # Enforce minimum size
                min_size = self.type_minsize_spinboxes['other'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                # Check if uniform color optimization is enabled
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                # Apply compression if needed
                format_mode = self.type_format_combos['other'].currentText()
                if format_mode != 'Keep':
                    optimize = format_mode == 'BC7 Smart'
                    dds = compress_bcx(new_rgba, target_w, target_h, BC7_UNORM)
                    from dxtex_wrapper import dds_to_tex
                    new_tex = dds_to_tex(dds)
                    with open(tex, 'wb') as f:
                        f.write(new_tex)
                    self.log_message(f'Processed other: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled other: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing other {os.path.basename(tex)}: {e}')
                processed_count[0] += 1

        #           Apply changes back to original or new copy
        progress.setLabelText("Applying changes...")
        progress.setValue(85)
        if destination == 'Modify in-place (!)':
            # Backup files before copying processed files back to original location
            selected_mod_items = self.mod_list.selectedItems()
            if selected_mod_items:
                mod_name_display = selected_mod_items[0].text()
                base_mods_path = self.path_entry.text()
                mod_folder_map = build_mod_folder_map(base_mods_path)
                mod_folder_full = mod_folder_map.get(mod_name_display)
                if mod_folder_full and os.path.isdir(mod_folder_full):
                    # Create backup of files that will be modified
                    progress.setLabelText("Creating backups...")
                    backup_mgr = create_backup_manager(base_mods_path)
                    if backup_mgr:
                        # Collect all .tex files that were processed
                        files_to_backup = []
                        for root, _, files in os.walk(mod_folder_full):
                            for f in files:
                                if f.lower().endswith('.tex'):
                                    rel_path = os.path.relpath(os.path.join(root, f), mod_folder_full)
                                    files_to_backup.append(rel_path)
                        
                        if files_to_backup:
                            backup_success, backup_failed = backup_mgr.backup_files(mod_folder_full, files_to_backup)
                            self.log_message(f'Backed up {backup_success} files to .dwnscl_backup')
                            if backup_failed > 0:
                                self.log_message(f'Warning: {backup_failed} files failed to backup')
                    else:
                        self.log_message('Warning: Backup manager not available')
                    
                    # Copy processed files back to original location
                    progress.setLabelText("Applying changes...")
                    temp_mod_path = os.path.join(temp_path, os.path.basename(mod_folder_full))
                    # Copy back
                    for item in os.listdir(temp_mod_path):
                        s = os.path.join(temp_mod_path, item)
                        d = os.path.join(mod_folder_full, item)
                        if os.path.isdir(s):
                            if os.path.exists(d):
                                shutil.rmtree(d)
                            shutil.copytree(s, d)
                        else:
                            shutil.copy2(s, d)
        elif destination == 'Create copy':
            # Create a copy with suffix
            selected_mod_items = self.mod_list.selectedItems()
            if selected_mod_items:
                mod_name_display = selected_mod_items[0].text()
                base_mods_path = self.path_entry.text()
                mod_folder_map = build_mod_folder_map(base_mods_path)
                mod_folder_full = mod_folder_map.get(mod_name_display)
                if mod_folder_full and os.path.isdir(mod_folder_full):
                    temp_mod_path = os.path.join(temp_path, os.path.basename(mod_folder_full))
                    copy_folder = mod_folder_full + '_processed'
                    if os.path.exists(copy_folder):
                        shutil.rmtree(copy_folder)
                    shutil.copytree(temp_mod_path, copy_folder)
                    self.log_message(f'Created copy: {copy_folder}')
        
        #           Calculate final file sizes
        final_size = 0
        if destination == 'Modify in-place (!)':
            # Measure from original location after processing
            if source_folder and os.path.isdir(source_folder):
                for root, _, files in os.walk(source_folder):
                    for f in files:
                        if f.lower().endswith('.tex'):
                            final_size += os.path.getsize(os.path.join(root, f))
        elif destination == 'Create copy':
            # Measure from temp directory
            for root, _, files in os.walk(temp_path):
                for f in files:
                    if f.lower().endswith('.tex'):
                        final_size += os.path.getsize(os.path.join(root, f))
        
        # Calculate and report savings
        size_saved = initial_size - final_size
        if initial_size > 0:
            percent_saved = (size_saved / initial_size) * 100
            self.log_message(f'Final texture size: {final_size / (1024*1024):.2f} MB')
            self.log_message(f'Space saved: {size_saved / (1024*1024):.2f} MB ({percent_saved:.1f}%)')
        
        # Cleanup temp directory
        progress.setLabelText("Cleaning up...")
        progress.setValue(95)
        temp_dir.cleanup()
        
        progress.setValue(100)
        progress.close()
        self.log_message('Processing complete!')
        
        # Show completion message
        QMessageBox.information(
            self,
            'Processing Complete',
            f'Processing completed successfully!\n\n'
            f'Initial size: {initial_size / (1024*1024):.2f} MB\n'
            f'Final size: {final_size / (1024*1024):.2f} MB\n'
            f'Space saved: {size_saved / (1024*1024):.2f} MB ({percent_saved:.1f}%)'
        )

    def processing_v2_selected(self):
        """
        Process only the selected texture files with per-type settings.
        Similar to processing_v2 but handles multiple selected files instead of all files.
        """
        # Get selected items
        selected_items = self.tex_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, 'No Selection', 'Please select at least one texture file to process.')
            return
        
        destination = self.combo_behaviour.currentText()
        
        # Show confirmation dialog for "Modify in-place" mode
        if destination == 'Modify in-place (!)':
            reply = QMessageBox.question(
                self,
                'Confirm In-Place Modification',
                'This will modify your mod files directly. While changes are processed safely, '
                'it is recommended to have a backup.\n\nContinue?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # Get selected file paths
        selected_paths = [item.text(6) for item in selected_items]
        self.log_message(f"Processing {len(selected_paths)} selected texture(s)...")
        
        # Create progress dialog (single one for all files)
        progress = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Processing Selected Textures")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        cancel_requested = [False]
        progress.canceled.connect(lambda: cancel_requested.__setitem__(0, True))
        
        # Calculate initial file sizes
        initial_size = sum(os.path.getsize(path) for path in selected_paths if os.path.isfile(path))
        self.log_message(f'Initial texture size: {initial_size / (1024*1024):.2f} MB')
        
        if cancel_requested[0]:
            progress.close()
            self.log_message('Processing cancelled by user')
            return
        
        # Create temp folder
        progress.setLabelText("Creating temporary workspace...")
        progress.setValue(5)
        temp_dir = tempfile.TemporaryDirectory()
        temp_path = temp_dir.name
        
        # Copy selected files to temp (preserving directory structure for proper categorization)
        progress.setLabelText("Copying files to temporary workspace...")
        progress.setValue(10)
        
        # Create a mapping of temp paths to original paths
        temp_to_original = {}
        
        for file_path in selected_paths:
            # Copy file to temp with its relative structure preserved
            file_name = os.path.basename(file_path)
            temp_file_path = os.path.join(temp_path, file_name)
            
            # Handle duplicate filenames by adding parent directory
            if os.path.exists(temp_file_path):
                parent_dir = os.path.basename(os.path.dirname(file_path))
                temp_file_path = os.path.join(temp_path, f"{parent_dir}_{file_name}")
            
            shutil.copy2(file_path, temp_file_path)
            temp_to_original[temp_file_path] = file_path
        
        if cancel_requested[0]:
            temp_dir.cleanup()
            progress.close()
            self.log_message('Processing cancelled by user')
            return
        
        # Get all .tex files in temp
        progress.setLabelText("Scanning texture files...")
        progress.setValue(15)
        temp_tex_files = list(temp_to_original.keys())
        
        # Scan for shader types (use first file's directory as reference)
        self.log_message("Scanning material files for shader types...")
        first_original_dir = os.path.dirname(selected_paths[0]) if selected_paths else temp_path
        shader_types = scan_folder_for_shaders(Path(first_original_dir))
        processing_mode = determine_processing_mode(shader_types)
        
        shader_type_names = [s.value for s in shader_types] if shader_types else ["none"]
        self.log_message(f"Found shader types: {', '.join(shader_type_names)}")
        self.log_message(f"Processing mode: {processing_mode}")
        
        # Determine compression strategy
        if processing_mode == "skin":
            self.log_message("Skin shader detected: Using RGBA quality for Normal, Mask, Diffuse")
            use_rgba_quality = True
            use_rgb_optimization = False
        elif processing_mode == "character":
            self.log_message("Character shader detected: Using RGB optimization (RG for ID)")
            use_rgba_quality = False
            use_rgb_optimization = True
        else:
            self.log_message("Other shader types: Using RGBA optimization")
            use_rgba_quality = True
            use_rgb_optimization = False
        
        # Classify files
        tex_diffuse = []
        tex_normal = []
        tex_id = []
        tex_specular = []
        tex_mask = []
        tex_other = []
        
        # Build mtrl mapping for accurate categorization
        mtrl_mapping = build_mtrl_mapping_for_mod(temp_path)
        if mtrl_mapping:
            self.log_message(f"Using material file mappings for {len(mtrl_mapping)} textures")
        
        for tex_file in temp_tex_files:
            file_type = categorize_tex(tex_file, temp_path, mtrl_mapping)
            if file_type == 'Diffuse':
                tex_diffuse.append(tex_file)
            elif file_type == 'Normal':
                tex_normal.append(tex_file)
            elif file_type == 'ID':
                tex_id.append(tex_file)
            elif file_type == 'Specular':
                tex_specular.append(tex_file)
            elif file_type == 'Mask':
                tex_mask.append(tex_file)
            else:
                tex_other.append(tex_file)
        
        total_textures = len(temp_tex_files)
        
        if total_textures == 0:
            progress.close()
            temp_dir.cleanup()
            self.log_message('No texture files found to process')
            return
        
        self.log_message(f'Found {total_textures} textures to process:')
        self.log_message(f'  Diffuse: {len(tex_diffuse)}, Normal: {len(tex_normal)}, ID: {len(tex_id)}')
        self.log_message(f'  Specular: {len(tex_specular)}, Mask: {len(tex_mask)}, Other: {len(tex_other)}')
        
        processed_count = [0]
        
        def update_progress():
            if total_textures > 0:
                progress.setValue(15 + int((processed_count[0] / total_textures) * 70))
                progress.setLabelText(f"Processing textures... ({processed_count[0]}/{total_textures})")
            if cancel_requested[0]:
                raise Exception("Processing cancelled by user")
        
        def is_uniform_color(rgba_bytes: bytes, w: int, h: int) -> bool:
            """Check if texture is a single uniform color"""
            if len(rgba_bytes) < 4:
                return False
            first_pixel = rgba_bytes[0:4]
            for i in range(0, len(rgba_bytes), 4):
                if rgba_bytes[i:i+4] != first_pixel:
                    return False
            return True
        
        # Process textures (using the same logic as processing_v2)
        progress.setLabelText("Processing textures...")
        progress.setValue(20)
        
        # Get per-type settings
        diffuse_fac = self.type_downscale_spinboxes['diffuse'].value() / 100.0
        normal_fac = self.type_downscale_spinboxes['normal'].value() / 100.0
        id_fac = self.type_downscale_spinboxes['id'].value() / 100.0
        specular_fac = self.type_downscale_spinboxes['specular'].value() / 100.0
        mask_fac = self.type_downscale_spinboxes['mask'].value() / 100.0
        other_fac = self.type_downscale_spinboxes['other'].value() / 100.0
        
        # Process each type (code reused from processing_v2 - DIFFUSE)
        for tex in tex_diffuse:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                target_w = max(1, int(w * diffuse_fac))
                target_h = max(1, int(h * diffuse_fac))
                
                min_size = self.type_minsize_spinboxes['diffuse'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                format_mode = self.type_format_combos['diffuse'].currentText()
                if format_mode != 'Keep':
                    dds = compress_bcx(new_rgba, target_w, target_h, BC7_UNORM)
                    from dxtex_wrapper import dds_to_tex
                    new_tex = dds_to_tex(dds)
                    with open(tex, 'wb') as f:
                        f.write(new_tex)
                    self.log_message(f'Processed diffuse: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled diffuse: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing diffuse {os.path.basename(tex)}: {e}')
                processed_count[0] += 1
        
        # NORMAL
        for tex in tex_normal:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                target_w = max(1, int(w * normal_fac))
                target_h = max(1, int(h * normal_fac))
                
                min_size = self.type_minsize_spinboxes['normal'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                format_mode = self.type_format_combos['normal'].currentText()
                if format_mode != 'Keep':
                    from dxtex_wrapper import BC5_UNORM, dds_to_tex
                    dds = compress_bcx(new_rgba, target_w, target_h, BC5_UNORM)
                    new_tex = dds_to_tex(dds)
                    with open(tex, 'wb') as f:
                        f.write(new_tex)
                    self.log_message(f'Processed normal: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled normal: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing normal {os.path.basename(tex)}: {e}')
                processed_count[0] += 1
        
        # ID
        for tex in tex_id:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                
                if self.type_align_checkboxes.get('id') and self.type_align_checkboxes['id'].isChecked():
                    rgba, _ = quantize_id_red_channel(rgba, w, h, log=None)
                    self.log_message(f'Aligned ID ranges: {os.path.basename(tex)}')
                
                target_w = max(1, int(w * id_fac))
                target_h = max(1, int(h * id_fac))
                
                min_size = self.type_minsize_spinboxes['id'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                format_mode = self.type_format_combos['id'].currentText()
                if format_mode != 'Keep':
                    optimize = format_mode == 'BC7 Smart'
                    dds = self.id_bc7_compress(new_rgba, target_w, target_h, tex, optimize=optimize)
                    if dds:
                        from dxtex_wrapper import dds_to_tex
                        new_tex = dds_to_tex(dds)
                        with open(tex, 'wb') as f:
                            f.write(new_tex)
                        self.log_message(f'Processed ID: {os.path.basename(tex)}')
                    else:
                        rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                        self.log_message(f'Downscaled ID: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled ID: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing ID {os.path.basename(tex)}: {e}')
                processed_count[0] += 1
        
        # SPECULAR
        for tex in tex_specular:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                target_w = max(1, int(w * specular_fac))
                target_h = max(1, int(h * specular_fac))
                
                min_size = self.type_minsize_spinboxes['specular'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                format_mode = self.type_format_combos['specular'].currentText()
                if format_mode != 'Keep':
                    dds = compress_bcx(new_rgba, target_w, target_h, BC7_UNORM)
                    from dxtex_wrapper import dds_to_tex
                    new_tex = dds_to_tex(dds)
                    with open(tex, 'wb') as f:
                        f.write(new_tex)
                    self.log_message(f'Processed specular: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled specular: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing specular {os.path.basename(tex)}: {e}')
                processed_count[0] += 1
        
        # MASK
        for tex in tex_mask:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                target_w = max(1, int(w * mask_fac))
                target_h = max(1, int(h * mask_fac))
                
                min_size = self.type_minsize_spinboxes['mask'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                format_mode = self.type_format_combos['mask'].currentText()
                if format_mode != 'Keep':
                    # Check if mask is single-channel (grayscale) or multi-channel
                    is_grayscale = True
                    for i in range(0, len(new_rgba), 4):
                        r, g, b = new_rgba[i], new_rgba[i+1], new_rgba[i+2]
                        if r != g or g != b:
                            is_grayscale = False
                            break
                    
                    if is_grayscale:
                        from dxtex_wrapper import BC4_UNORM, dds_to_tex
                        dds = compress_bcx(new_rgba, target_w, target_h, BC4_UNORM)
                    else:
                        dds = compress_bcx(new_rgba, target_w, target_h, BC7_UNORM)
                    
                    from dxtex_wrapper import dds_to_tex
                    new_tex = dds_to_tex(dds)
                    with open(tex, 'wb') as f:
                        f.write(new_tex)
                    self.log_message(f'Processed mask: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled mask: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing mask {os.path.basename(tex)}: {e}')
                processed_count[0] += 1
        
        # OTHER
        for tex in tex_other:
            try:
                update_progress()
                decoded = read_tex_to_rgba(tex, self.log_message)
                if not decoded:
                    self.log_message(f'Failed to decode: {tex}')
                    processed_count[0] += 1
                    continue
                rgba, w, h = decoded
                target_w = max(1, int(w * other_fac))
                target_h = max(1, int(h * other_fac))
                
                min_size = self.type_minsize_spinboxes['other'].value()
                target_w = max(target_w, min_size)
                target_h = max(target_h, min_size)
                
                if self.chk_uniform_optimize.isChecked() and is_uniform_color(rgba, w, h):
                    target_w = min(target_w, 8)
                    target_h = min(target_h, 8)
                    self.log_message(f'Uniform color detected: {os.path.basename(tex)} -> 8x8px')
                
                new_rgba = downscale_nearest(rgba, w, h, target_w, target_h)
                format_mode = self.type_format_combos['other'].currentText()
                if format_mode != 'Keep':
                    dds = compress_bcx(new_rgba, target_w, target_h, BC7_UNORM)
                    from dxtex_wrapper import dds_to_tex
                    new_tex = dds_to_tex(dds)
                    with open(tex, 'wb') as f:
                        f.write(new_tex)
                    self.log_message(f'Processed other: {os.path.basename(tex)}')
                else:
                    rgba_to_bgra_tex(new_rgba, target_w, target_h, tex)
                    self.log_message(f'Downscaled other: {os.path.basename(tex)}')
                processed_count[0] += 1
            except Exception as e:
                if "cancelled" in str(e).lower():
                    raise
                self.log_message(f'Error processing other {os.path.basename(tex)}: {e}')
                processed_count[0] += 1
        
        # Copy back processed files
        progress.setLabelText("Applying changes...")
        progress.setValue(90)
        
        try:
            if destination == 'Modify in-place (!)':
                # Backup files before overwriting
                selected_mod_items = self.mod_list.selectedItems()
                if selected_mod_items:
                    base_mods_path = self.path_entry.text()
                    backup_mgr = create_backup_manager(base_mods_path)
                    if backup_mgr:
                        # Get mod folder for each file and backup
                        mod_folder_map = build_mod_folder_map(base_mods_path)
                        backed_up_count = 0
                        for temp_file, original_file in temp_to_original.items():
                            # Find which mod this file belongs to
                            for mod_name, mod_path in mod_folder_map.items():
                                if original_file.startswith(mod_path):
                                    rel_path = os.path.relpath(original_file, mod_path)
                                    if backup_mgr.backup_file(mod_path, rel_path):
                                        backed_up_count += 1
                                    break
                        self.log_message(f'Backed up {backed_up_count} file(s) to .dwnscl_backup')
                    else:
                        self.log_message('Warning: Backup manager not available')
                
                # Copy processed files back to original locations
                for temp_file, original_file in temp_to_original.items():
                    if os.path.isfile(temp_file):
                        shutil.copy2(temp_file, original_file)
                        self.log_message(f'Updated: {os.path.basename(original_file)}')
            elif destination == 'Create copy':
                # Create copies with _processed suffix
                for temp_file, original_file in temp_to_original.items():
                    if os.path.isfile(temp_file):
                        base, ext = os.path.splitext(original_file)
                        copy_path = base + '_processed' + ext
                        shutil.copy2(temp_file, copy_path)
                        self.log_message(f'Created copy: {copy_path}')
        except Exception as e:
            self.log_message(f'Error applying changes: {e}')
        
        # Calculate final sizes
        final_size = sum(os.path.getsize(temp_file) for temp_file in temp_to_original.keys() if os.path.isfile(temp_file))
        size_saved = initial_size - final_size
        percent_saved = (size_saved / initial_size * 100) if initial_size > 0 else 0
        
        self.log_message(f'Final texture size: {final_size / (1024*1024):.2f} MB')
        self.log_message(f'Space saved: {size_saved / (1024*1024):.2f} MB ({percent_saved:.1f}%)')
        
        # Cleanup
        progress.setLabelText("Cleaning up...")
        progress.setValue(95)
        temp_dir.cleanup()
        
        progress.setValue(100)
        progress.close()
        self.log_message('Processing complete!')
        
        # Show completion message
        QMessageBox.information(
            self,
            'Processing Complete',
            f'Processing completed successfully!\n\n'
            f'Files processed: {len(selected_paths)}\n'
            f'Initial size: {initial_size / (1024*1024):.2f} MB\n'
            f'Final size: {final_size / (1024*1024):.2f} MB\n'
            f'Space saved: {size_saved / (1024*1024):.2f} MB ({percent_saved:.1f}%)'
        )

    def bcx_compress(self, rgba: bytes, w: int, h: int, path: Optional[str], algo: int = BC7_UNORM) -> bytes:
        """
        Compress RGBA data using specified BCx algorithm.
        
        Args:
            rgba: Raw RGBA pixel data
            w: Width
            h: Height
            path: Optional file path for logging
            algo: BC format constant (BC1_UNORM, BC3_UNORM, BC4_UNORM, BC5_UNORM, BC7_UNORM)
        
        Returns:
            Compressed DDS bytes
        """
        data = compress_bcx(rgba, w, h, algo, 1)
        return data

    def id_bc7_compress(self, rgba: bytes, w: int, h: int, path: Optional[str], optimize: Optional[bool] = False) -> bytes:
        """
        Compress ID texture with optimal BCx format.
        
        Tries different compression algorithms and picks the smallest one
        that preserves ID values after quantization within error threshold.
        
        Args:
            rgba: Original RGBA bytes
            w: Width
            h: Height
            path: Optional path for logging
            optimize: If True, tries BC1/3/5/7. If False, only BC7.
        
        Returns:
            Compressed DDS bytes
        """
        # Quantize original RGBA to get reference values
        quantized_original, _ = quantize_id_red_channel(rgba, w, h, log=None)
        
        # Define algorithms to test
        if optimize:
            algos = [BC7_UNORM, BC1_UNORM, BC3_UNORM, BC5_UNORM]
        else:
            algos = [BC7_UNORM]
        
        # Compress with each algorithm
        algo_results = []
        for algo in algos:
            try:
                compressed_dds = self.bcx_compress(rgba, w, h, path, algo)
                algo_results.append((algo, compressed_dds, len(compressed_dds)))
            except Exception as e:
                self.log_message(f"Compression with format {algo} failed: {e}")
                continue
        
        if not algo_results:
            self.log_message(f"All compression algorithms failed for {path}")
            return None
        
        # Sort by size (smallest first)
        algo_results = sorted(algo_results, key=lambda x: x[2])
        
        # Error threshold: 0.1% of pixels can differ
        error_threshold = 0.001
        
        # Find best algorithm that meets error threshold
        best_result = None
        for algo, compressed_dds, size in algo_results:
            try:
                # Decompress to check quality - need to write to temp file first
                from dxtex_wrapper import dds_to_tex
                temp_tex = dds_to_tex(compressed_dds)
                temp_file = tempfile.NamedTemporaryFile(suffix='.tex', delete=False)
                temp_file.write(temp_tex)
                temp_file.close()
                
                decoded = read_tex_to_rgba(temp_file.name, self.log_message)
                os.unlink(temp_file.name)
                
                if not decoded:
                    continue
                    
                decoded_rgba, _, _ = decoded
                
                # Quantize the decompressed result
                quantized_decoded, _ = quantize_id_red_channel(decoded_rgba, w, h, log=None)
                
                # Compare red channels (ID values)
                total_pixels = w * h
                differing_pixels = 0
                for i in range(0, len(quantized_original), 4):
                    if quantized_original[i] != quantized_decoded[i]:
                        differing_pixels += 1
                
                error_rate = differing_pixels / total_pixels
                
                # Log results
                format_names = {BC1_UNORM: 'BC1', BC3_UNORM: 'BC3', 
                               BC5_UNORM: 'BC5', BC7_UNORM: 'BC7'}
                fmt_name = format_names.get(algo, f'{algo}')
                self.log_message(f"  {fmt_name}: {size} bytes, error rate: {error_rate*100:.2f}%")
                
                # If error rate is acceptable, use this compression
                if error_rate <= error_threshold:
                    best_result = compressed_dds
                    self.log_message(f"  → Selected {fmt_name} (smallest with acceptable error)")
                    break
            except Exception as e:
                self.log_message(f"Error testing format {algo}: {e}")
                continue
        
        # If no algorithm met threshold, use BC7 (highest quality)
        if best_result is None:
            self.log_message(f"  → All formats exceeded error threshold, using BC7")
            for algo, compressed_dds, size in algo_results:
                if algo == BC7_UNORM:
                    best_result = compressed_dds
                    break
            # Fallback to first result if BC7 not available
            if best_result is None:
                best_result = algo_results[0][1]
        
        return best_result

    def smart_bc7_compress(self, rgba: bytes, w: int, h: int, path: Optional[str]) -> bytes:
        """
        Intelligently compress texture by testing multiple BC formats.
        Selects the smallest format that maintains acceptable quality.
        
        Args:
            rgba: Raw RGBA pixel data
            w: Width
            h: Height
            path: Optional file path for logging
        
        Returns:
            Compressed DDS bytes
        """
        # Test BC1, BC3, BC5, BC7 and pick smallest with good quality
        from dxtex_wrapper import BC1_UNORM, BC3_UNORM, BC5_UNORM, BC7_UNORM
        
        candidates = []
        for algo in [BC1_UNORM, BC3_UNORM, BC5_UNORM, BC7_UNORM]:
            try:
                dds = self.bcx_compress(rgba, w, h, path, algo)
                candidates.append((algo, dds, len(dds)))
            except Exception as e:
                self.log_message(f"Compression with {algo} failed: {e}")
        
        if not candidates:
            # Fallback to BC7
            return self.bcx_compress(rgba, w, h, path, BC7_UNORM)
        
        # Sort by size and return smallest
        candidates.sort(key=lambda x: x[2])
        return candidates[0][1] 






















def main():
    app = QApplication(sys.argv)
    app.setApplicationName("XIV Downscale Utility")
    
    # Create and show splash screen
    # Handle PyInstaller bundled mode
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        splash_path = os.path.join(sys._MEIPASS, 'splash.png')
    else:
        splash_path = os.path.join(os.path.dirname(__file__), 'splash.png')
    
    splash = None
    if os.path.exists(splash_path):
        splash_pixmap = QPixmap(splash_path)
        splash = QSplashScreen(splash_pixmap, Qt.WindowStaysOnTopHint)
        
        # Set the splash screen to be transparent/frameless for modern look
        splash.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        # Enable transparency if the image has an alpha channel
        splash.setMask(splash_pixmap.mask())
        
        # Show the splash screen
        splash.show()
        app.processEvents()  # Process events to ensure splash is displayed
    
    # Create main window
    window = MainWindow()
    
    # Show splash for 1.5s before showing main window maximized
    if splash:
        def show_main_window():
            window.showMaximized()
            splash.close()
        
        # Wait 1.5 seconds, then show main window and close splash
        QTimer.singleShot(1500, show_main_window)
    else:
        window.showMaximized()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()


