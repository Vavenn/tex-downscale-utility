<img width="892" height="412" alt="github title" src="https://github.com/user-attachments/assets/8c407aef-f6e7-405e-a549-d80f12b159a6" />

# .Tex Downscale Utility

A texture downscaling and optimization tool for Final Fantasy XIV mods

## Features

### Core Functionality
- **Smart Texture Downscaling** - Reduce texture sizes while maintaining visual quality
- **Multiple Compression Formats** - Support for BC1, BC3, BC5, and BC7 compression
- **Material-Aware Processing** - Automatically categorizes textures based on .mtrl file references
- **Per-Type Settings** - Fine-grained control over downscale percentage, minimum size, and format for each texture type

### User Interface
- PySide6-based GUI
- Real-time texture preview
- Mod browser with search functionality
- Batch processing support

## Screenshots

 - Main interface
<img width="1919" height="1079" alt="main" src="https://github.com/user-attachments/assets/6d174e36-4cbd-40f5-bc34-f35c5461f329" />


 - Solid alpha & alpha preview (very useful for some normal textures that use Alpha weirdly)
<img width="1919" height="1079" alt="alpha-preview" src="https://github.com/user-attachments/assets/810c4d0d-653c-41d9-96cb-d71fb00b2fcf" />



### Installation
- This is a standalone build, no need to do anything else

## Usage Guide

### Basic Workflow

1. **Set Penumbra Mods Path**
   - Click "Browse" and select your Penumbra mods folder
   - Click "Scan Mods" to load your installed mods

2. **Configure Settings**
   - Set downscale percentage per texture type
   - Choose minimum texture sizes
  
3. **Apply Processing**
   - Choose your saving context and settings
   - Hit the big green button (or the selected only one)

### Backup System

#### Automatic Backups
When using "Modify in-place" mode, the utility automatically:
- Creates backups in `.dwnscl_backup` folder within your mods directory
- Saves the last 10 modified mods

#### Restoring from Backup
1. Click "Restore from Backup" button
2. Select a mod from the backup list
3. Click "Restore" to revert changes

## Other Features

### Uniform Color Optimization
Automatically detects single-color textures and reduces them to 8x8p

## Todo
- ARGB8 -> BCx Compression ID smart re-adjusting
- Improved downscaling algorithm that uses ID textures to have a smoother downscaling on most areas

