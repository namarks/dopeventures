# Next Steps: Swift Native App Development

## ✅ What's Done

- ✅ XcodeGen installed and configured
- ✅ Xcode project generated with all Swift files
- ✅ All Models, Services, and Views included
- ✅ Project structure ready

## 🎯 Immediate Next Steps

### 1. Open and Verify Project

```bash
cd DopetracksApp
open DopetracksApp.xcodeproj
```

**In Xcode, verify:**
- All files appear in Project Navigator (Models, Services, Views folders)
- No red error indicators
- Project builds without errors

### 2. Fix App Entry Point

You have two app entry points. We need to use the custom one:

**Option A: Delete the default (Recommended)**
- In Xcode, delete `DopetracksAppApp.swift` (Xcode's default)
- Keep `DopetracksApp.swift` (has BackendManager integration)

**Option B: Update the default**
- Replace contents of `DopetracksAppApp.swift` with code from `DopetracksApp.swift`
- Delete `DopetracksApp.swift` (the duplicate at root level)

### 3. Fix ContentView

You have two ContentView files. Use the one with tab navigation:

- **Keep**: `DopetracksApp/DopetracksApp/ContentView.swift` (update it)
- **Replace its contents** with the code from `DopetracksApp/ContentView.swift` (the one with tabs)

Or delete the nested one and use the root level one.

### 4. Create Info.plist (if missing)

XcodeGen should create this, but verify:
- Check if `DopetracksApp/DopetracksApp/Info.plist` exists
- If not, create it with basic app metadata

### 5. Build and Test

1. **Select scheme**: "DopetracksApp" (top toolbar)
2. **Select destination**: "My Mac" 
3. **Build**: Cmd+B (or Product → Build)
4. **Fix any compilation errors**

### 6. Test Backend Connection

**Option A: Development Mode (Easier)**
1. Start Python backend manually:
   ```bash
   cd /Users/nmarks/root_code_repo/dopeventures
   python start.py
   # or
   uvicorn packages.dopetracks.app:app --host 127.0.0.1 --port 8888
   ```

2. Run Swift app in Xcode (Cmd+R)
3. App should connect to `localhost:8888`

**Option B: Production Mode**
- BackendManager will launch Python backend automatically
- Requires backend to be bundled (see SETUP.md)

## 🔧 Common Issues & Fixes

### Issue: "Cannot find 'BackendManager' in scope"
**Fix**: Make sure `BackendManager.swift` is in the project and added to target

### Issue: "Cannot find 'APIClient' in scope"  
**Fix**: Make sure `APIClient.swift` is in the project and added to target

### Issue: Multiple `@main` entry points
**Fix**: Delete `DopetracksAppApp.swift`, keep only `DopetracksApp.swift`

### Issue: Build errors about missing types
**Fix**: 
1. Clean build folder (Cmd+Shift+K)
2. Rebuild (Cmd+B)
3. Check all Swift files are added to target

### Issue: Backend won't start
**Fix**: 
- For development: Start backend manually first
- For production: Bundle backend executable (see SETUP.md)

## 📝 Development Workflow

### Daily Development:

1. **Create/edit Swift files** in Cursor or Xcode
2. **Regenerate project** (if you added new files):
   ```bash
   ./regenerate_project.sh
   ```
3. **Build and test** in Xcode

### Adding New Files:

1. Create Swift file in `DopetracksApp/DopetracksApp/` directory
2. Run: `./regenerate_project.sh`
3. File automatically included in Xcode project

### Testing:

1. Start Python backend: `python start.py`
2. Run Swift app in Xcode
3. Test features:
   - Chat search
   - Playlist creation
   - Settings/Spotify profile

## 🚀 Future Enhancements

- [ ] Add app icon
- [ ] Implement Server-Sent Events for progress updates
- [ ] Add native notifications
- [ ] System tray integration
- [ ] Code signing for distribution
- [ ] Bundle Python backend for standalone app

## 📚 Resources

- [SwiftUI Documentation](https://developer.apple.com/documentation/swiftui/)
- [XcodeGen Documentation](https://github.com/yonaskolb/XcodeGen)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

