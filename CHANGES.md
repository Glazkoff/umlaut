# Evolution UI - Recent Changes

## 2026-03-12 10:22 EDT

### Fixed: Long Process Commands in Debug Mode ✅

**Issue:** When Debug Mode was enabled, long process commands would overflow horizontally and create visual clutter.

**Solution:** Updated CSS for `.debug-process` class:
- Changed `white-space: nowrap` → `white-space: pre-wrap`
- Added `word-break: break-all` to break long commands
- Added `line-height: 1.4` for better readability

**Result:** Process commands now wrap properly and are much easier to read.

### Other Recent Improvements

1. **WebSocket Support** - Fixed nginx configuration to properly proxy WebSocket connections
2. **Local Storage** - Last selected project is now remembered across sessions
3. **Cron Management UI** - Added ability to create/remove cron jobs directly from the UI
4. **Debug Mode** - Toggle to see detailed process information and logs

### Testing the Fix

1. Open https://evo.ngl.bar/
2. Select a project (e.g., calendar-stats)
3. Enable Debug Mode by clicking the 🔧 button
4. Check the "Active Processes" section - commands should now wrap nicely

### Before & After

**Before:**
```
.root/.nvm/versions/node/v24.14.0/bin/openclaw agent --local --session-id evolution-calendar-stats-1773322374 --thinking high --timeout 600 --message "..."
```
(Horizontal scroll, hard to read)

**After:**
```
.root/.nvm/versions/node/v24.14.0/bin/openclaw
agent --local --session-id
evolution-calendar-stats-1773322374
--thinking high --timeout 600
--message "..."
```
(Wraps nicely, easy to read)

---

*Note: A browser hard refresh (Ctrl+Shift+R) may be needed to see the CSS changes.*
