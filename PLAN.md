# PLAN.md — custom online streaming player (youtube & spotify routing)

1. `research_notes.md` — findings from the search gate, with source URLs.
2. `app.py` — discover endpoint stability & autoplay policy (v1.1.9):
   - Replaced unhandled `concurrent.futures.as_completed` timeout loop with `concurrent.futures.wait(..., timeout=3.5)` in `get_smart_recommendations`, preventing `TimeoutError` from crashing the server with `net::ERR_EMPTY_RESPONSE`.
   - Wrapped `/api/discover` in a robust try-except with instant fallback to catalog categories so the UI can never fail to receive categories.
   - Added `Cache-Control: no-cache, no-store, must-revalidate` headers in `DualStreamHandler.end_headers()` to prevent WebView2 from serving stale cached CSS/JS.
   - Added `--autoplay-policy=no-user-gesture-required` to WebView2 arguments and native window launcher.
3. `client/index.html` — asset cache busting (v1.1.9):
   - Appended `?v=1.1.9` query parameters to `style.css` and `player.js` references.
4. `client/style.css` — category pills layout & boundary clipping fix (v1.1.9):
   - `.category-pill-bar`: `min-height: 64px`, `overflow-x: auto`, `overflow-y: hidden`, `padding: 12px 6px 14px 6px`, `box-sizing: border-box`.
   - `.category-pill`: `height: 38px`, `line-height: 38px`, `padding: 0 18px`, `border: 1.5px solid rgba(255, 255, 255, 0.08)`, `border-radius: 9999px`.
   - `.category-pill.active`: `border: 1.5px solid #38bdf8`, `box-shadow: 0 0 14px rgba(14, 165, 233, 0.3)`.
5. `client/player.js` — autoplay & abort error handling (v1.1.9):
   - Caught `AbortError` / code 20 and `NotAllowedError` in audio play promises to eliminate auto-skip cascades.
   - Guarded stall watchdog (`cur > 0.5`) to prevent premature aborts on initial network connections.
   - Separated `playbackContext` ('discover' | 'playlist' | 'liked' | 'queue') so discover playback never falls back to sequential liked songs stepping.
6. `compile and package` — compiled with PyInstaller (`TubeFast.spec`), replaced root `Lightning Player.exe`, and generated `Lightning-Player-v1.1.9-Windows-x64.zip`.
7. `test_verification.md` — test verification report.
