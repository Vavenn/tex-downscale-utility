# Backup System Documentation

## Overview
The XIV Downscale Utility now includes an automatic backup system that protects your mod files before any in-place modifications.

## Features

### Automatic Backups
- **Automatic Protection**: Whenever you use "Modify in-place" mode, the original files are automatically backed up before any changes are made.
- **Smart Storage**: Backups are stored in a hidden `.dwnscl_backup` folder inside your Penumbra mods directory.
- **Rolling History**: The system maintains backups for the last 10 modified mods to save space.

### Backup Location
```
<Your Penumbra Mods Path>/.dwnscl_backup/
├── backup_index.json          # Tracks backup metadata
├── ModName1/                   # Backup for ModName1
│   └── <original mod structure>
├── ModName2/                   # Backup for ModName2
│   └── <original mod structure>
...
```

### Backup Index
The `backup_index.json` file tracks:
- Mod name and folder path
- Last backup timestamp
- Number of backed-up files

## How It Works

### During In-Place Modification
1. **Before Processing**: The utility scans for files that will be modified
2. **Backup Creation**: Original files are copied to `.dwnscl_backup/<ModName>/`
3. **Processing**: Files are processed and modified in-place
4. **Completion**: Console logs show backup status (e.g., "Backed up 15 files to .dwnscl_backup")

### Backup Limits
- Maximum of **10 mods** are backed up at any time
- When the 11th mod is backed up, the oldest backup is automatically deleted
- This keeps your storage usage manageable

## Restoring Backups

### Using the Restore Button
1. Click **"Restore from Backup"** button in the main window (below "Open Mod Folder")
2. A dialog appears showing all available backups with:
   - Mod name
   - Number of backed-up files
   - Last backup timestamp
3. Select a mod and click **"Restore"**
4. Confirm the restoration
5. Original files are restored, overwriting the current versions

### Deleting Backups
If you want to manually remove a backup:
1. Open the "Restore from Backup" dialog
2. Select the backup you want to delete
3. Click **"Delete Backup"**
4. Confirm deletion

## Important Notes

### When Backups Are Created
✅ **Backups ARE created** for:
- "Modify in-place" mode in batch processing
- "Modify in-place" mode for selected files
- Any operation that overwrites existing mod files

❌ **Backups are NOT created** for:
- "Create copy" mode (original files remain untouched)
- Operations on folders outside your Penumbra mods directory

### Safety Considerations
- Backups are stored locally on your disk
- If you delete your mods folder, backups in `.dwnscl_backup` are also deleted
- Consider keeping separate manual backups for important mods
- Backups are automatic and silent - check console output for confirmation

### Backup Folder Management
- The `.dwnscl_backup` folder is hidden by default (starts with `.`)
- You can manually browse it if needed
- Safe to delete the entire `.dwnscl_backup` folder if you want to clear all backups
- The system will recreate it automatically on next backup

## Console Messages

### Backup Creation
```
Creating backups before committing changes...
Backed up 15 files (0 failed)
```

### Backup Restoration
```
Restored 15 file(s) from backup for MyAwesomeMod
```

### Backup Deletion
```
Deleted backup for MyAwesomeMod
```

### Warnings
```
Warning: Backup manager not available
Warning: 2 files failed to backup
```

## Technical Details

### File Structure Preservation
- Backups maintain the exact directory structure of your mod
- Relative paths are preserved for accurate restoration
- File timestamps and permissions are copied

### Thread Safety
- Backup operations are performed synchronously
- No race conditions during processing
- Progress dialog shows backup progress

### Error Handling
- Failed backups are logged but don't stop processing
- Partial backups are possible if some files fail
- Restoration failures are reported individually

## Troubleshooting

### "Backup manager not available"
- Ensure your Penumbra mods path is set correctly
- Check that you have write permissions to the mods folder
- Verify the path exists and is accessible

### Backups Not Working
1. Check console output for error messages
2. Verify sufficient disk space
3. Ensure the mod folder is not read-only
4. Try running the application as administrator (if needed)

### Can't Find Old Backups
- Only the last 10 mods are kept
- Older backups are automatically deleted
- Check the backup creation date in the restore dialog

## Best Practices

1. **Regular Manual Backups**: While automatic backups are convenient, keep separate backups of important mods
2. **Review Before Restoring**: Check the backup timestamp to ensure you're restoring the correct version
3. **Clean Up Unused Backups**: Use the delete function to remove backups you no longer need
4. **Monitor Disk Space**: 10 mod backups can use significant space depending on texture sizes
5. **Test Restorations**: Try restoring a backup on a test mod first to familiarize yourself with the process

## FAQ

**Q: Do backups include all mod files or just textures?**
A: Currently, backups include all `.tex` files that are modified. Other mod files (like `.mtrl`) are not backed up unless they're also modified.

**Q: Can I manually edit the backup_index.json?**
A: Not recommended. The utility manages this file automatically. Manual edits may cause issues.

**Q: What happens if I move my mods folder?**
A: Backup paths are absolute. If you move your mods folder, existing backups may not restore correctly. Delete old backups and create new ones after moving.

**Q: Can I backup more than 10 mods?**
A: The limit is hardcoded to 10 to save space. If you need more, consider manual backup solutions or modify the `MAX_BACKUP_MODS` constant in `backup_manager.py`.

**Q: Are backups compressed?**
A: No, backups are stored as-is for maximum reliability and speed. They use the same space as your original files.
