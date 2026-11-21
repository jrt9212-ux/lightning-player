# PLAN.md — custom online streaming player (youtube & spotify routing)

1. `research_notes.md` — findings from the search gate, with source URLs.
2. `client/style.css` — category pills layout & clipping fix (v1.1.9):
   - Eliminated top border slicing in `.category-pill-bar` by increasing top padding (`10px 4px 12px 4px`) and setting margin-top.
   - Set `.category-pill` with fixed `height: 38px`, `box-sizing: border-box`, `flex-shrink: 0`, and reset `line-height: 1`.
   - Tuned `.category-pill.active` border (`1.5px solid #38bdf8`) and glow for clean symmetrical rendering without clipping.
3. `client/player.js` — skip debounce, abort error handling & playback context separation (v1.1.9):
   - Caught `AbortError` / code 20 in audio play promises so skipping buffering tracks never triggers error cascades.
   - Guarded stall watchdog (`cur > 0.5`) to prevent aborting tracks during initial network handshake.
   - Removed `state.likedSongs` fallback from `triggerSmartAutoplay` and `findAndPlayNextPlayableTrack`, binding fallbacks to active category pools.
   - Introduced `state.playbackContext` ('discover' | 'playlist' | 'liked' | 'queue') so discover playback never falls back to sequential liked songs stepping.
   - Debounced next/previous buttons (350ms) to block rapid-click race conditions.
   - Corrected `handlePlayAll()` to enqueue `list.slice(1)` preventing duplicate playback.
4. `app.py` & `version_info.txt` — version bump to v1.1.9:
   - `APP_VERSION = "1.1.9"` in `app.py`.
   - Windows binary metadata version `1.1.9.0` in `version_info.txt`.
5. `compile and package` — compile with PyInstaller (`TubeFast.spec`), verify zero warnings, replace root `Lightning Player.exe`, and generate `Lightning-Player-v1.1.9-Windows-x64.zip`.
6. `test_verification.md` — test verification report.
