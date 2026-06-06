# Backup-Restore Feature Implementation

## Summary
Implemented a comprehensive backup-restore system for the XIV Downscale Utility that automatically backs up mod files before in-place modifications.

## Files Created

### 1. `backup_manager.py`
Core backup management module with the following features:
- `BackupManager` class for managing all backup operations
- Automatic backup of files before modification
- Index tracking with JSON metadata file
- Rolling backup history (keeps last 10 mods)
- Restore functionality
- Delete functionality
- Backup listing and info retrieval

Key functions:
- `backup_file()` - Backs up a single file
- `backup_files()` - Backs up multiple files at once
- `restore_mod()` - Restores all files for a mod
- `delete_backup()` - Removes a backup
- `list_backups()` - Lists all available backups
- `has_backup()` - Checks if a backup exists
- `get_backup_info()` - Retrieves backup metadata

### 2. `BACKUP_SYSTEM.md`
Comprehensive documentation covering:
- Feature overview
- How the system works
- Usage instructions
- Technical details
- Troubleshooting guide
- FAQ section

## Files Modified

### 1. `processing.py`
**Changes:**
- Added import for `backup_manager`
- Modified the in-place commit section (around line 663-673) to:
  - Create a backup manager instance
  - Collect list of files to be modified
  - Backup files before copying processed versions back
  - Log backup results

**Integration points:**
- Backups are created just before the "Committing changes to original mod folder..." step
- Logs show backup status (e.g., "Backed up 15 files (0 failed)")

### 2. `gui.py`
**Changes:**
- Added import for `backup_manager` and `MAX_BACKUP_MODS`
- Fixed existing bugs (undefined `temp_mod_folder` variable)
- Added "Restore from Backup" button in column1 (below "Open Mod Folder")
- Implemented restore dialog with:
  - List of all available backups
  - Backup information (file count, timestamp)
  - Restore button
  - Delete backup button
  - Proper error handling and user feedback
- Integrated backup into `processing_v2()` function:
  - Creates backups before applying changes in "Modify in-place" mode
  - Backs up all .tex files in the mod folder
  - Logs backup status
- Integrated backup into `processing_v2_selected()` function:
  - Creates backups for selected files before modification
  - Determines which mod each file belongs to
  - Logs backup status

## How It Works

### Backup Flow
1. User selects "Modify in-place" mode
2. User confirms the in-place modification warning
3. Processing begins (files are processed in temp folder)
4. **Before committing changes:**
   - Backup manager is created
   - List of files to be modified is collected
   - Each file is backed up to `.dwnscl_backup/<ModName>/`
   - Backup index is updated with metadata
   - Old backups are cleaned up if exceeding 10 mods
5. Processed files are copied back to original location
6. Console shows backup results

### Restore Flow
1. User clicks "Restore from Backup" button
2. Dialog shows all available backups with details
3. User selects a backup and clicks "Restore"
4. Confirmation dialog appears
5. User confirms
6. Files are copied from backup to original location
7. Success message shows restored file count

### Delete Flow
1. User opens restore dialog
2. User selects a backup and clicks "Delete Backup"
3. Confirmation dialog appears
4. User confirms
5. Backup folder and index entry are removed
6. Dialog refreshes to show updated list

## Backup Storage

### Location
```
<Penumbra Mods Path>/.dwnscl_backup/
```

### Structure
```
.dwnscl_backup/
├── backup_index.json          # Metadata tracking
├── ModName1/                   # First mod backup
│   ├── file1.tex
│   ├── subfolder/
│   │   └── file2.tex
│   └── ...
├── ModName2/                   # Second mod backup
│   └── ...
└── ...
```

### Index File (`backup_index.json`)
```json
{
  "ModName1": {
    "mod_folder": "C:\\Path\\To\\Penumbra\\mods\\ModName1",
    "last_backup": "2026-06-06T14:30:00.123456",
    "file_count": 15
  },
  "ModName2": {
    "mod_folder": "C:\\Path\\To\\Penumbra\\mods\\ModName2",
    "last_backup": "2026-06-06T15:45:00.123456",
    "file_count": 23
  }
}
```

## Features

### Automatic Backup
- ✅ Backs up files automatically before modification
- ✅ Works with both batch and selected file processing
- ✅ Only activates for "Modify in-place" mode
- ✅ Silent operation with console logging

### Rolling History
- ✅ Keeps last 10 mods backed up
- ✅ Automatically removes oldest backup when limit reached
- ✅ Uses OrderedDict to maintain chronological order

### User Interface
- ✅ "Restore from Backup" button in main window
- ✅ Intuitive restore dialog with backup details
- ✅ Delete backup functionality
- ✅ Confirmation dialogs for all destructive operations
- ✅ Detailed feedback messages

### Robustness
- ✅ Graceful error handling
- ✅ Preserves directory structure
- ✅ Maintains file timestamps and permissions
- ✅ Works with Unicode paths and filenames
- ✅ Handles missing or corrupted index files

## Testing Recommendations

### Test Scenarios
1. **Basic Backup & Restore:**
   - Process a mod with "Modify in-place"
   - Verify backup created in `.dwnscl_backup`
   - Restore the backup
   - Verify files are restored correctly

2. **Multiple Mods:**
   - Process 12 different mods in-place
   - Verify only last 10 are backed up
   - Check oldest 2 are automatically removed

3. **Selected Files:**
   - Select specific texture files
   - Process with "Modify in-place"
   - Verify only those files are backed up
   - Restore and verify

4. **Delete Backup:**
   - Create a backup
   - Use delete function
   - Verify backup folder and index entry removed

5. **Error Handling:**
   - Try to restore with invalid mod path
   - Try to backup with insufficient permissions
   - Verify appropriate error messages

6. **Edge Cases:**
   - Empty mod folder
   - Mod with single file
   - Very large mod (1000+ files)
   - Unicode characters in mod names

## Benefits
1. **Safety**: Users can safely use in-place modification knowing they can undo changes
2. **Convenience**: Automatic operation requires no user intervention
3. **Space Efficient**: Only keeps 10 most recent mods
4. **User Friendly**: Simple restore UI with clear information
5. **Transparent**: Console logs keep users informed of backup operations

## Potential Future Enhancements
- [ ] Configurable backup limit (currently hardcoded to 10)
- [ ] Backup compression to save disk space
- [ ] Incremental backups (only backup changed files)
- [ ] Backup before/after preview comparison
- [ ] Export/import backup sets
- [ ] Automatic cleanup of old backups by date
- [ ] Backup all mod files, not just .tex files
- [ ] Backup configuration settings
