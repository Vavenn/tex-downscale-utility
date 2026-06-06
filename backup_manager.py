"""
Backup and restore functionality for XIV Downscale Utility.

This module manages automatic backups of mod files before in-place modifications.
- Creates .dwnscl_backup folder inside the mods directory
- Maintains backups of the last 10 modified mods
- Tracks backup metadata across program sessions
- Provides restore functionality
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import OrderedDict

BACKUP_FOLDER_NAME = ".dwnscl_backup"
BACKUP_INDEX_FILE = "backup_index.json"
MAX_BACKUP_MODS = 10


class BackupManager:
    """Manages backups of mod files before in-place modifications."""
    
    def __init__(self, mods_base_path: str):
        """
        Initialize backup manager.
        
        Args:
            mods_base_path: Path to the Penumbra mods folder
        """
        self.mods_base_path = Path(mods_base_path)
        self.backup_root = self.mods_base_path / BACKUP_FOLDER_NAME
        self.index_file = self.backup_root / BACKUP_INDEX_FILE
        self.index = self._load_index()
    
    def _load_index(self) -> OrderedDict:
        """
        Load backup index from file.
        
        Returns:
            OrderedDict with mod names as keys and metadata as values
        """
        if not self.index_file.exists():
            return OrderedDict()
        
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Convert to OrderedDict to maintain order
                return OrderedDict(data)
        except Exception as e:
            print(f"Warning: Failed to load backup index: {e}")
            return OrderedDict()
    
    def _save_index(self):
        """Save backup index to file."""
        self.backup_root.mkdir(exist_ok=True)
        
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save backup index: {e}")
    
    def _cleanup_old_backups(self):
        """Remove oldest backups when exceeding MAX_BACKUP_MODS."""
        while len(self.index) > MAX_BACKUP_MODS:
            # Remove oldest (first item in OrderedDict)
            oldest_mod = next(iter(self.index))
            backup_path = self.backup_root / oldest_mod
            
            try:
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                del self.index[oldest_mod]
                print(f"Cleaned up old backup: {oldest_mod}")
            except Exception as e:
                print(f"Warning: Failed to clean up backup {oldest_mod}: {e}")
                # Try to remove from index anyway
                del self.index[oldest_mod]
        
        self._save_index()
    
    def backup_file(self, mod_folder_path: str, file_rel_path: str) -> bool:
        """
        Back up a single file before modification.
        
        Args:
            mod_folder_path: Absolute path to the mod folder
            file_rel_path: Relative path to the file within the mod folder
            
        Returns:
            True if backup succeeded, False otherwise
        """
        mod_folder = Path(mod_folder_path)
        mod_name = mod_folder.name
        source_file = mod_folder / file_rel_path
        
        if not source_file.exists():
            print(f"Warning: Source file not found for backup: {source_file}")
            return False
        
        # Create backup directory structure
        backup_mod_dir = self.backup_root / mod_name
        backup_file = backup_mod_dir / file_rel_path
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Copy file to backup
            shutil.copy2(source_file, backup_file)
            
            # Update index - move to end (most recent)
            if mod_name in self.index:
                # Remove and re-add to move to end
                del self.index[mod_name]
            
            self.index[mod_name] = {
                "mod_folder": str(mod_folder),
                "last_backup": datetime.now().isoformat(),
                "file_count": len(list(backup_mod_dir.rglob("*.tex")))
            }
            
            self._save_index()
            self._cleanup_old_backups()
            
            return True
            
        except Exception as e:
            print(f"Warning: Failed to backup file {file_rel_path}: {e}")
            return False
    
    def backup_files(self, mod_folder_path: str, file_rel_paths: List[str]) -> Tuple[int, int]:
        """
        Back up multiple files from a mod before modification.
        
        Args:
            mod_folder_path: Absolute path to the mod folder
            file_rel_paths: List of relative paths to files within the mod folder
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        success = 0
        failed = 0
        
        for rel_path in file_rel_paths:
            if self.backup_file(mod_folder_path, rel_path):
                success += 1
            else:
                failed += 1
        
        return success, failed
    
    def restore_mod(self, mod_name: str) -> Tuple[int, int]:
        """
        Restore all backed-up files for a specific mod.
        
        Args:
            mod_name: Name of the mod to restore
            
        Returns:
            Tuple of (restored_count, failed_count)
        """
        if mod_name not in self.index:
            print(f"No backup found for mod: {mod_name}")
            return 0, 0
        
        backup_mod_dir = self.backup_root / mod_name
        if not backup_mod_dir.exists():
            print(f"Backup directory not found: {backup_mod_dir}")
            return 0, 0
        
        mod_info = self.index[mod_name]
        target_mod_folder = Path(mod_info["mod_folder"])
        
        if not target_mod_folder.exists():
            print(f"Target mod folder not found: {target_mod_folder}")
            return 0, 0
        
        restored = 0
        failed = 0
        
        # Find all backed-up files
        for backup_file in backup_mod_dir.rglob("*"):
            if backup_file.is_file():
                # Calculate relative path and target location
                rel_path = backup_file.relative_to(backup_mod_dir)
                target_file = target_mod_folder / rel_path
                
                try:
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, target_file)
                    restored += 1
                except Exception as e:
                    print(f"Failed to restore {rel_path}: {e}")
                    failed += 1
        
        return restored, failed
    
    def delete_backup(self, mod_name: str) -> bool:
        """
        Delete backup for a specific mod.
        
        Args:
            mod_name: Name of the mod whose backup should be deleted
            
        Returns:
            True if deletion succeeded, False otherwise
        """
        if mod_name not in self.index:
            return False
        
        backup_mod_dir = self.backup_root / mod_name
        
        try:
            if backup_mod_dir.exists():
                shutil.rmtree(backup_mod_dir)
            del self.index[mod_name]
            self._save_index()
            return True
        except Exception as e:
            print(f"Failed to delete backup for {mod_name}: {e}")
            return False
    
    def list_backups(self) -> List[Dict]:
        """
        Get list of all available backups.
        
        Returns:
            List of backup info dictionaries
        """
        backups = []
        for mod_name, info in self.index.items():
            backups.append({
                "mod_name": mod_name,
                "mod_folder": info["mod_folder"],
                "last_backup": info["last_backup"],
                "file_count": info["file_count"]
            })
        return backups
    
    def has_backup(self, mod_name: str) -> bool:
        """
        Check if a backup exists for a specific mod.
        
        Args:
            mod_name: Name of the mod to check
            
        Returns:
            True if backup exists, False otherwise
        """
        return mod_name in self.index
    
    def get_backup_info(self, mod_name: str) -> Optional[Dict]:
        """
        Get backup information for a specific mod.
        
        Args:
            mod_name: Name of the mod
            
        Returns:
            Dictionary with backup info, or None if no backup exists
        """
        if mod_name not in self.index:
            return None
        
        return {
            "mod_name": mod_name,
            **self.index[mod_name]
        }


def create_backup_manager(mods_base_path: str) -> Optional[BackupManager]:
    """
    Create a backup manager instance.
    
    Args:
        mods_base_path: Path to the Penumbra mods folder
        
    Returns:
        BackupManager instance, or None if path is invalid
    """
    if not mods_base_path or not os.path.isdir(mods_base_path):
        return None
    
    return BackupManager(mods_base_path)
