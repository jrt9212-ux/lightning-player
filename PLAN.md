# PLAN.md — Reliable Multi-Platform Routing, Audio Streaming Engine & UI Precision

1. `research_notes.md` — findings from the search gate, with source URLs.
2. `client/index.html` & `client/style.css` — precision UI overhaul:
   - Progress Bar Inconsistency Fix: Replace dirty-rect custom property linear-gradient on `<input type="range">` with a dual-layer hardware-accelerated progress bar: dedicated `.slider-progress-fill` element (`#progressFill`) inside `.slider-track-wrap` with transparent input on top. Zero repaint glitches, zero gaps, 100% synchronized with playback and scrubbing.
   - Volume Slider Sizing: Expand volume slider box to 180px and input width to 140px with a dedicated volume fill layer, giving feasible, high-precision audio control.
   - Category Pill Bar Fix: Lock `.category-pill-bar` vertical scroll (`scrollTop = 0`), redirect mouse wheel events to horizontal `scrollLeft`, and set clean headroom padding (`padding: 10px 12px; height: 58px`) so pills are never clipped or cut off at the top.
3. `app.py` — thread-local extraction, multi-client streaming engine & disk resolve cache:
   - Replace singleton `YDL_LOCK` with `threading.local()` multi-client extractor (`mweb,android,ios,web` and `ba[ext=m4a]/140/ba[ext=webm]/ba/best`) eliminating lock contention between simultaneous `/api/stream`, `/api/preload`, and `/api/recommendations`.
   - Persist Spotify-to-YouTube video ID resolution cache to `tubefast_resolve_cache.json` on disk across app restarts, enabling 0ms instant playback for repeated or pre-cached tracks.
   - Stream chunk flush (`self.wfile.flush()`) on first byte chunk for immediate audio playback start without waiting for TCP buffer fill.
   - Bump `APP_VERSION = "1.2.0"`.
4. `client/player.js` — strict platform routing, smart shuffle & skip consistency:
   - Platform Context Isolation: When YouTube mode is active, all search, autoplay, smart queue, and recommendations route exclusively through YouTube tracks (`source === 'youtube'`). When Spotify mode is active, all recommendations and queueing route exclusively through Spotify tracks (`source === 'spotify'`).
   - Overhaul Shuffle & Skip: Implement unplayed candidate pool per platform so shuffle next/skip draws random unplayed tracks without repetition within 50 tracks. When shuffle is off, step sequentially through active category list.
   - Preloader Synchronization: Sync preloaded track with intended next track (random for shuffle, next sequential for linear).
   - Dynamic Progress Fill Sync: Direct DOM update of `#progressFill` width on `timeupdate`, `input`, and `change`.
5. `compile and package` — compile standalone `Lightning Player.exe` via PyInstaller, update `version_info.txt` to 1.2.0.0, package `Lightning-Player-v1.2.0-Windows-x64.zip`.
6. `test_verification.md` — end-to-end Edge CDP verification confirming category pills rendered cleanly without clipping, progress fill and volume slider pixel accuracy, and uninterrupted multi-platform playback.
