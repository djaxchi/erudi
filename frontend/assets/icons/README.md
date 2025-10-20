# Application Icons

This directory contains the application icons for Erudi.

## Required Files

For a complete build, you need:

### macOS
- `icon.icns` - macOS icon file (can be generated from PNG)

### Windows  
- `icon.ico` - Windows icon file

### Linux
- `icon.png` - PNG icon (preferably 512x512 or larger)

## Creating Icons from PNG

If you have a PNG logo (like the ones in `src/img/`), you can create the icons:

### For macOS (.icns)
```bash
# Create an iconset directory
mkdir icon.iconset

# Generate different sizes (use your source PNG)
sips -z 16 16     logo.png --out icon.iconset/icon_16x16.png
sips -z 32 32     logo.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     logo.png --out icon.iconset/icon_32x32.png
sips -z 64 64     logo.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   logo.png --out icon.iconset/icon_128x128.png
sips -z 256 256   logo.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   logo.png --out icon.iconset/icon_256x256.png
sips -z 512 512   logo.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   logo.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 logo.png --out icon.iconset/icon_512x512@2x.png

# Convert to icns
iconutil -c icns icon.iconset

# Clean up
rm -rf icon.iconset
```

### For Windows (.ico)
You can use online tools or ImageMagick:
```bash
# Using ImageMagick (if installed)
convert logo.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```

### Quick Setup
If you just want to get started quickly:
1. Copy one of the PNG logos from `src/img/` to this directory as `icon.png`
2. The build will use what's available for each platform
3. macOS: Will look for `icon.icns`, fallback to `icon.png`
4. Windows: Will look for `icon.ico`, fallback to `icon.png`
5. Linux: Will use `icon.png`

## Current Status
- [ ] icon.icns (macOS)
- [ ] icon.ico (Windows)
- [ ] icon.png (Linux/Fallback)
