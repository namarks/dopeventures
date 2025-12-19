# Native App UI Options

This document outlines options for improving the user experience, particularly around permissions and making the app feel more native.

## Current Setup

- **Backend**: FastAPI (Python)
- **Frontend**: HTML/CSS/JavaScript served via FastAPI
- **Launch**: Opens in external browser (Safari/Chrome/etc)
- **Permissions**: User must manually grant Full Disk Access

## Option 1: Keep Web UI + Add Helper Features (✅ RECOMMENDED - Easiest)

**Pros:**
- ✅ Minimal changes to existing code
- ✅ Already works well
- ✅ Easy to maintain and update
- ✅ Cross-platform compatible (if you ever want to support other OS)

**Cons:**
- ❌ Still opens in external browser
- ❌ Less "native" feel

**What we've added:**
- ✅ Button to open System Settings directly to Full Disk Access
- ✅ Better error messages and instructions
- ✅ Help section that appears when validation fails

**Implementation Status:** ✅ DONE

---

## Option 2: Embed Web UI in Native Window (PyWebView)

**Pros:**
- ✅ Native window (not external browser)
- ✅ Keep existing web UI code
- ✅ Better integration with macOS
- ✅ Can add native menus, notifications, etc.

**Cons:**
- ❌ Additional dependency (pywebview)
- ❌ Slightly more complex build process
- ❌ Need to handle window management

**Implementation:**

1. Install pywebview:
   ```bash
   pip install pywebview
   ```

2. Modify `launch_bundled.py`:
   ```python
   import webview
   
   def launch_main_app():
       # ... existing setup code ...
       
       # Instead of opening browser, create native window
       webview.create_window(
           'Dopetracks',
           'http://127.0.0.1:8888',
           width=1200,
           height=800,
           min_size=(800, 600),
           resizable=True
       )
       webview.start(debug=False)
   ```

3. Update `build_app.spec` to include pywebview:
   ```python
   hiddenimports = [
       # ... existing imports ...
       'webview',
       'webview.platforms.cocoa',  # macOS-specific
   ]
   ```

**Estimated Effort:** 2-3 hours

---

## Option 3: Full Native UI (PyQt/PySide)

**Pros:**
- ✅ Fully native macOS look and feel
- ✅ Best integration with macOS features
- ✅ Can use native dialogs, menus, etc.
- ✅ No browser dependency

**Cons:**
- ❌ Need to rewrite entire frontend
- ❌ Much more complex
- ❌ Larger app bundle size
- ❌ Steeper learning curve

**Implementation:**

Would require rewriting the entire frontend in PyQt/PySide. This is a significant undertaking.

**Estimated Effort:** 2-3 weeks

---

## Option 4: Hybrid Approach (Current + Native Window)

**Best of both worlds:**

1. Keep the web-based UI (easy to maintain)
2. Use PyWebView to show it in a native window
3. Add native macOS features:
   - Native menus (File, Edit, Help)
   - System tray icon
   - Native notifications
   - Better permission handling

**Implementation:**

Similar to Option 2, but with additional native features.

**Estimated Effort:** 1 week

---

## Recommendation

**Start with Option 1** (what we've already done):
- ✅ Button to open System Settings
- ✅ Better error messages
- ✅ Clear instructions

**Then consider Option 2** (PyWebView) if users want:
- Native window instead of browser
- Better macOS integration
- More "app-like" experience

**Skip Option 3** unless you have a strong reason to rewrite everything.

---

## Testing the System Settings Button

The new `/open-full-disk-access` endpoint uses:
```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
```

This should work on macOS Ventura (13.0+) and later. For older macOS versions, you might need:
```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
```

Or fallback to:
```bash
open /System/Library/PreferencePanes/Security.prefPane
```

---

## Next Steps

1. ✅ **DONE**: Add System Settings button
2. **Test**: Verify the button works on different macOS versions
3. **Consider**: Add PyWebView for native window (if users request it)
4. **Future**: Consider native notifications, system tray icon, etc.

