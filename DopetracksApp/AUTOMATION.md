# Automating Xcode Project Management

## Overview

Instead of manually adding files to Xcode, you can use **XcodeGen** to automatically generate the Xcode project from a YAML specification file. This means:

- ✅ **No manual file adding** - XcodeGen automatically includes all Swift files
- ✅ **Version control friendly** - Only the YAML file needs to be committed
- ✅ **Regenerates on demand** - Run one command to update the project
- ✅ **Works with Cursor** - Create files in Cursor, regenerate project

## Quick Start

### 1. Install XcodeGen

```bash
brew install xcodegen
```

Or run the setup script:
```bash
./setup_xcodegen.sh
```

### 2. Generate Xcode Project

```bash
cd DopetracksApp
xcodegen generate
```

This will create/update `DopetracksApp.xcodeproj` based on `project.yml`.

### 3. Open in Xcode

```bash
open DopetracksApp.xcodeproj
```

All Swift files will be automatically included!

## Workflow

### When You Add New Files in Cursor:

1. **Create your Swift files** in Cursor (e.g., `DopetracksApp/Models/NewModel.swift`)
2. **Regenerate the project**:
   ```bash
   cd DopetracksApp
   xcodegen generate
   ```
3. **Open in Xcode** - the new file will be there!

### When You Add New Files in Xcode:

If you add files through Xcode's GUI, you'll need to either:
- **Option A**: Manually update `project.yml` to include the new files
- **Option B**: Let XcodeGen regenerate (it will overwrite manual changes)

**Recommendation**: Use XcodeGen as the source of truth. Add files in Cursor, regenerate with XcodeGen.

## Project Structure

The `project.yml` file defines:
- **Sources**: All Swift files in `DopetracksApp/` directory
- **Resources**: Assets and other resources
- **Settings**: Build settings, bundle ID, deployment target
- **Info**: App metadata and permissions

## Advanced: Auto-Regeneration

You can set up a file watcher to automatically regenerate when files change:

### Using `fswatch` (macOS):

```bash
# Install fswatch
brew install fswatch

# Watch for Swift file changes and regenerate
fswatch -o DopetracksApp/**/*.swift | xargs -n1 -I{} xcodegen generate
```

### Using a Git Hook:

Create `.git/hooks/post-merge`:
```bash
#!/bin/bash
cd DopetracksApp && xcodegen generate
```

## Troubleshooting

### "xcodegen: command not found"
- Install XcodeGen: `brew install xcodegen`

### "Project file is out of sync"
- Regenerate: `xcodegen generate`

### Files not appearing in Xcode
- Check that files are in the `DopetracksApp/` directory
- Regenerate: `xcodegen generate`
- Clean build folder in Xcode (Cmd+Shift+K)

### Merge conflicts in project.pbxproj
- Delete `DopetracksApp.xcodeproj`
- Regenerate: `xcodegen generate`
- Commit the regenerated project

## Benefits Over Manual Management

| Manual Xcode | XcodeGen |
|-------------|----------|
| ❌ Manual file adding | ✅ Automatic |
| ❌ Merge conflicts | ✅ No conflicts (YAML is source) |
| ❌ Easy to miss files | ✅ Always in sync |
| ❌ Time consuming | ✅ One command |
| ❌ Error prone | ✅ Consistent |

## Next Steps

1. Install XcodeGen: `brew install xcodegen`
2. Generate project: `xcodegen generate`
3. Open in Xcode: `open DopetracksApp.xcodeproj`
4. Start developing! 🚀

