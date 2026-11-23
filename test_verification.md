# Test Verification Report: v1.2.1

## Verification Objectives
1. **Pill Bar Anti-Clipping**:
   - Removed fixed height and `contain: layout`.
   - Hidden scrollbars across WebKit and Blink engines (`scrollbar-width: none !important; -ms-overflow-style: none !important; ::-webkit-scrollbar { display: none !important; }`).
   - Verified via CDP: `minHeight = 56px`, `height = 56px`, `boxSizing = border-box`, `scrollbarWidth = none`, `isTopClipped = False`.
2. **Recently Listened Category (Left Sidebar)**:
   - Added `Recently Listened` nav item with clock icon and `#historyBadge` count badge in `<aside class="sidebar">` under LIBRARY.
   - Added `#clearHistoryBtn` in view actions.
   - Verified via CDP: `hasHistoryNav = True`, `hasHistoryBadge = True`, `hasClearHistoryBtn = True`.
   - Clicking `#navHistoryBtn` switches active tab to `history`, sets header title to `Recently Listened`, and displays `state.history`.
   - Clicking `#clearHistoryBtn` wipes history, resets badge to 0, and updates view.
3. **10-Track Playback History (Previous Track Navigation)**:
   - Implemented `playbackHistoryStack = []` (capped at 10 items) and `isNavigatingHistory` flag.
   - When a track starts playing, pushes previous track to `playbackHistoryStack`.
   - When `playPrevTrack()` is called with `currentTime <= 3`, pops the previous song from the stack in true LIFO order, eliminating alternating/bouncing between two songs.
4. **Strict Platform Isolation on Discovery**:
   - In `app.py`: `get_smart_recommendations()` queries only YouTube when `source == 'youtube'` and only Spotify when `source == 'spotify'`.
   - Tested backend endpoints:
     - `/api/discover?source=youtube`: 15/15 for_you tracks are YouTube; all category tracks are YouTube (0% Spotify).
     - `/api/discover?source=spotify`: 15/15 for_you tracks are Spotify; all category tracks are Spotify (0% YouTube).
   - In `client/player.js`: `loadPopularTracks()` strictly filters candidates to `state.activeSource`.
   - Saved user playlists (`state.playbackContext === 'playlist'`) are the sole context where mixed cross-platform playback is permitted.

## Build Artifacts
- Binary: `dist\Lightning Player.exe` (v1.2.1.0)
- Root Binary: `.\Lightning Player.exe`
- Zip Archive: `.\Lightning-Player-v1.2.1-Windows-x64.zip`
- Verification Suite: `e2e_verify.py` (ALL TESTS PASSED CLEANLY)
