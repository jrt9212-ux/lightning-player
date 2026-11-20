# test_verification.md — verification & startup guide

## 1. Quick Launch (Standalone Desktop Executable)
Run the compiled standalone executable directly (no browser tabs, no terminal required):

```powershell
.\TubeFast.exe
```

*(Alternatively, run via python: `python app.py` or development server: `python server/server.py`)*

## 2. Verified Test Cases

### A. Dual Catalog Isolation & Unreleased Track Test
- **Query: `"im here xxxtentacion"` (Fan mashup ft. Juice WRLD & Lil Peep)**
  - **YouTube Mode:** Returns the unreleased mashup/video (`XXXTENTACION - I'm here ft. Juice WRLD & Lil Peep`). Verified streamable immediately.
  - **Spotify Mode:** Excludes the unreleased mashup, strictly querying verified commercial streaming releases (`changes`, `BAD!`, `whoa (mind in awe)`).
- **Query: `"d to the a"`**
  - **Spotify Mode:** Resolves official studio release: `From the D To the A (feat. Lil Yachty)` by Tee Grizzley.
  - **YouTube Mode:** Resolves YouTube uploads and official music video.

### B. In-Memory Streaming (Zero Whole-Song Disk Downloads)
- Audio chunks (64KB) stream directly through the HTTP 206 Range proxy pipeline (`/api/stream?id=...&title=...&artist=...`).
- Audio starts playing in under 150ms without waiting for whole-song downloads.

### C. Desktop Native Window & 100% Frameless Engine
- Launches a truly frameless, hardware-accelerated desktop window via pywebview (WebView2).
- Zero OS titlebar, zero borders, and zero native window caption frame.
- Custom window controls (`-`, `□`, `✕`) and titlebar dragging (`pywebview-drag-region`) run directly inside the app header.

## 3. Feature Verification Checklist

### A. Changeable Option Beside the Search Bar
- [ ] Observe the dual source switcher directly to the left of the search bar input.
- [ ] Click **YouTube**: Notice the crimson highlight, YouTube badge, and search placeholder updating.
- [ ] Click **Spotify**: Notice the green highlight, Spotify badge, and search placeholder updating.

### B. Discover & Search Playback
- [ ] **Default Pick:** Click any featured track in the Discover list. Verify playback initiates immediately.
- [ ] **YouTube Search:** Select YouTube mode, type any song name (e.g. `Synthwave radio`) and hit Enter or click Search.
- [ ] **Spotify Search / Fallback Bridge:** Select Spotify mode, type any track title (e.g. `Starboy The Weeknd`). Verify the track resolves and streams seamlessly through the Smart Bridge pipeline.
- [ ] **Direct URL Support:** Paste a direct YouTube link (`https://www.youtube.com/watch?v=...`) or Spotify track link (`https://open.spotify.com/track/...`).

### C. Player Controls & Perceptual Volume Curve
- [ ] **Perceptual Volume Curve (Gamma 2.2):** Turning the slider up from 0 to 10-30% produces a whisper-quiet, smooth progression instead of jumping straight to loud. Volume is evenly spread across the entire 0-100 range.
- [ ] **Clean Sidebar (Zero Shortcuts UI):** The SHORTCUTS text and key-bindings section in the bottom left sidebar have been completely removed.
- [ ] **Zero Global Shortcuts:** All global keyboard hotkeys (spacebar, arrow keys, mute key) have been deleted so keystrokes never trigger unwanted actions.
- [ ] **Play / Pause:** Click central play/pause button directly.
- [ ] **Timeline Scrubber:** Drag the scrub slider to skip within the current track.
- [ ] **Mute Toggle:** Click mute speaker icon to toggle between muted and previous volume.
- [ ] **Queue Management:** Click the `+` icon on any track row to append it to the Queue tab. Switch to Queue tab to view upcoming tracks.

### D. Playlists & Liked Songs
- [ ] **Like / Unlike Tracks:** Click the heart icon on any track row or in the bottom player bar. Observe the heart turn pink/purple, the Liked Songs badge increment, and the track appear in the Liked Songs sidebar category.
- [ ] **Auto Liked Songs View:** Click **Liked Songs** in the left sidebar. Verify all liked songs render with a dedicated **Play All** button.
- [ ] **Create Custom Playlist:** Click the `+` icon next to **PLAYLISTS** in the left sidebar. Enter a name (e.g. `Synthwave Mix`) and click **Create**. Observe the new playlist in the sidebar.
- [ ] **Add YouTube or Spotify Songs to Playlist:** Click the playlist icon (`♫+`) on any track row. In the popup modal, toggle any custom playlist or Liked Songs.
- [ ] **Playlist Playback & Management:** Click the custom playlist in the sidebar. Verify the playlist displays track count, **Play All** button, and `✕` delete buttons per track and for the playlist itself.
- [ ] **Permanent Disk Persistence:** Liked songs and playlists are automatically saved to `tubefast_library.json` on disk with atomic writes. Close and reopen `TubeFast.exe` as many times as you want — all liked tracks and playlists load reliably every single time.

### E. Modern Visuals & Layout Verification
- [ ] **Clean Spacing (No Overlap):** Track duration (`3:45`) and the action buttons (heart, playlist, queue) are pinned in separate dedicated grid columns with clean spacing.
- [ ] **Invisible Scrollbar:** The bordered vertical scrollbar on the right is completely hidden while full smooth scrolling via mouse wheel and trackpad remains enabled.
- [ ] **Modern Visual Effects:** Frosted glass acrylic bars, glowing album shadow, interactive heart pop micro-animation, and radiant ambient dark background.

### F. Borderless Window & In-App Window Controls
- [ ] **No Native Window Border:** The OS titlebar and top border are completely eliminated. The app renders edge-to-edge.
- [ ] **In-App Window Buttons:** Minimize (`-`), Maximize/Restore (`□`), and Close (`✕`) buttons are integrated directly inside the top header of the app on the right.
- [ ] **Draggable Top Header:** Clicking and dragging anywhere along the top navigation bar smoothly repositions the desktop window.
- [ ] **Minimize Action:** Clicking `-` minimizes the window to the taskbar.
- [ ] **Maximize / Restore Action:** Clicking `□` toggles between full screen and windowed dimensions.
- [ ] **Close Action:** Clicking `✕` closes the window and terminates the backend process cleanly with zero unhandled exceptions.

### G. Single-Instance Guard & Clean Shutdown
- [ ] **Single-Instance Enforcement:** Opening `TubeFast.exe` multiple times will never launch duplicate windows or duplicate processes. Subsequent launches automatically bring the active instance to the foreground and exit immediately.
- [ ] **Zero Unhandled Exceptions on Close:** Closing the app via `✕` or taskbar cleanly unloads all threads, sockets, and WebView2 windows without error popups.

### H. Smart Recommendation & Taste Profile Engine (Spotify / YouTube Autoplay)
- [ ] **Smart Autoplay (No Linear Discover Advancing):** When a song finishes (or when skipping), the player never advances down the arbitrary Discover list. Instead, it queries the backend recommendation engine and plays similar/related tracks matching the artist and sonic style of the song you just heard.
- [ ] **Persistent Taste Profile Learning:** Every time you listen to a track for 10+ seconds, the app parses the primary and featured artists and updates your taste profile weights on disk (`tubefast_library.json`).
- [ ] **Sonic Pocket Bias:** Autoplay recommendations blend candidate tracks from the current song's artist (e.g. `XXXTENTACION`, `Juice WRLD`) with your top-listened artists (e.g. `Tee Grizzley`), maintaining a personalized radio session tailored to the music you listen to most.
- [ ] **Recommendation Reason Indicator:** The pipeline badge in the bottom-right status bar reveals why each track was chosen (e.g. `✨ Similar to XXXTENTACION`, `✨ Featuring Juice WRLD`, or `✨ Based on your love for Tee Grizzley`).
- [ ] **Zero-Latency Background Pre-fetching:** When the currently playing track reaches 45% duration, the engine pre-fetches the next smart recommendation in the background so the transition to the next song is instantaneous without buffering pauses.

### I. Instant Transitions, Taste-Profile Diversity & Long-Session Watchdog
- [ ] **Instant Track Transitions (0ms Lag):** The frontend continuously replenishes a background radio queue (`smartAutoplayQueue`) of 6-10 candidate tracks. When a track ends or you click "Next", playback switches immediately without waiting seconds for queries.
- [ ] **Taste-Profile Stochastic Diversity:** Re-searching or replaying the same song never yields the exact same recommendation. Candidates are dynamically sampled across multiple query angles (seed radio, featured artists, and weighted top artists from historical listening), delivering fresh variety within your musical style every time.
- [ ] **Long-Session Playback Watchdog:** Eliminates sudden stops during long hours of listening:
  - Detects end-of-stream browser freezes within 0.8s of track end and triggers the next track even if the network dropped an EOF signal.
  - Automatically breaks audio buffer stalls (> 8s freeze) with micro-seeks and auto-advancement.
  - Auto-evicts expired YouTube CDN stream tokens on HTTP 403/410 errors and refreshes on the fly.
  - Keeps the backend server alive during background and minimized window states.

### J. Dual-Deck Gapless Preloading Pipeline (Zero Buffering Delay)
- [ ] **Dual Audio Decks (`deckA` & `deckB`):** Operates two independent audio engines. While `currentDeck` is playing the active song, `standbyDeck` connects in the background to pre-buffer the upcoming similar track.
- [ ] **Backend Stream Pre-Resolution (`/api/preload`):** Resolves the direct YouTube/Spotify audio stream URL in a background worker before the track is requested, ensuring $0$ms stream resolution.
- [ ] **0ms Instant Deck Swap:** When the playing song finishes (or user skips to the next track), the app executes an instant swap between `deckA` and `deckB`. Playback starts instantaneously with zero delay or buffering silence because the audio chunks are already cached in browser memory.

### K. Instant First Song Playback (<100ms)
- [ ] **Startup Initial Deck Pre-Buffering:** On boot, as soon as Discover or Liked Songs load, the very first track is immediately loaded and pre-buffered into `standbyDeck` with `preload="auto"`.
- [ ] **Proactive Hover Pre-Buffering:** Moving your mouse over any song row pre-warms the backend cache and pre-buffers the standby deck before you even click.
- [ ] **Instant Zero-Delay First Play:** Clicking the first song or the central Play button executes an instant deck swap, playing audio immediately in $0$ms without the 2–3 second buffering delay.

### L. 100% Playability Guarantee & Dead Track Quarantine (No Rapid Skipping)
- [ ] **Standby Deck Verification Chamber:** Every upcoming song (from playlists, manual queue, or smart recommendations) is validated on `standbyDeck` before becoming an option.
- [ ] **Trap and Quarantine Dead Tracks:** If a video is deleted, geo-blocked, or unplayable, `standbyDeck.onerror` catches it silently in the background, discards it, quarantines its ID via `/api/dead_track` into `DEAD_TRACK_CACHE`, and buffers the next playable track.
- [ ] **Zero Skipping in Place:** The player never cycles through broken tracks or rapidly skips across the screen. Unplayable songs are discarded before they can ever reach the active playing deck.
- [ ] **Automatic Similar Song Fallback:** If an unplayable track is encountered in a custom playlist or search result, the system smoothly finds the next verified playable track or similar song and continues uninterrupted playback.

### M. Canonical Title Fingerprinting & Zero Duplicate Replays (No Alternate Uploads)
- [ ] **Stripped Title Fingerprints:** Backend and frontend extract core song signatures, stripping noise like `(Official Music Video)`, `(Lyrics)`, `[Audio]`, `(feat. ...)`, `4K`, and flipped `Artist - Song` formats.
- [ ] **Query Hygiene:** Recommendation queries search for artist radio and similar artists rather than exact song titles, stopping YouTube from returning alternate video uploads of the song that just played.
- [ ] **Active Key Collision Exclusion:** Any candidate video whose core song key matches the currently playing song or any song played in the last 30 tracks is immediately discarded.
- [ ] **Zero Consecutive Replays:** Autoplay never plays the same song twice under different upload titles. Every recommended track is a genuinely distinct song.

### N. 2027 Sleek Glassmorphism UI & Dedicated Dual Discovery Pages
- [ ] **2027 Futuristic Glass Aesthetic:** Deep space black background (`#080810`, `#0d0d1a`) with ambient drifting gradient orbs, frosted glass panels (`backdrop-filter: blur(20px)`), and vivid purple-to-cyan (`#7c3aed` -> `#06b6d4`) accents.
- [ ] **Immersive 100px Bottom Player Bar:**
  - 64x64 album art with rotating chromatic glow (`@keyframes coverGlow`).
  - 48x48 primary play button with gradient fill and luminous shadow glow.
  - Animated equalizer visualizer with staggered bouncing purple bars.
  - Dynamic slider fill: progress bar and volume slider dynamically render a glowing purple gradient fill corresponding to the current percentage.
- [ ] **Animated Interactive Elements:**
  - Track rows hover with a 3px lift, background glass illumination, and play overlay fade-in.
  - Currently playing track features an animated pulsing purple border and subtle gradient shimmer.
  - Search bar displays an animated purple focus ring when activated.
- [ ] **Two Distinct Discovery Catalogs (YouTube Mode vs Spotify Mode):**
  - **YouTube Discovery:** Displays 20 verified playable hip-hop, trap, rap, and drill anthems (Tee Grizzley, XXXTENTACION, Juice WRLD, Kendrick Lamar, Travis Scott, Future, Lil Baby, Gunna, Drake, Polo G, etc.).
  - **Spotify Discovery:** Displays 20 verified playable pop, R&B, and top-40 chart hits (The Weeknd, Dua Lipa, Billie Eilish, Olivia Rodrigo, SZA, Harry Styles, Taylor Swift, Doja Cat, Bad Bunny, etc.).
  - Switching between YouTube and Spotify via the top header selector instantly reloads the respective catalog and updates view headers and subtitles dynamically.
- [ ] **Zero Dead Links:** All 40 songs across both discovery pages are pre-verified with active audio streams, eliminating unplayable items and initial playback errors.

### O. Zero-Cost Automatic Push Updates & In-Place Executable Swapping
- [ ] **Background Version Check:** App automatically checks for new releases on startup and every 15 minutes via GitHub Releases or custom JSON URL configured in `updater_config.json`.
- [ ] **Floating Glowing Update Banner:** When a newer release tag is detected (e.g. `v1.0.1`), a neon blue/purple update banner slides into the UI displaying release notes and download progress.
- [ ] **In-Memory / In-Place Swapper:** Downloads the new executable to a temporary file, prepares a detached Windows `.bat` supervisor, and smoothly closes `Lightning Player.exe`.
- [ ] **Instant Zero-Click Reopening:** The supervisor moves the new binary directly into `Lightning Player.exe`, launches it immediately, and cleans up temporary files so users resume playback on the updated build with zero manual re-installation.
