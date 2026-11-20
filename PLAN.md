# PLAN.md — custom online streaming player (youtube & spotify routing)

1. `research_notes.md` — findings from the search gate, with source URLs.
2. `architecture_specification.md` — system design document detailing:
   - Dual-engine playback bridge (YouTube IFrame API + Spotify Web Playback SDK / metadata resolver).
   - "Spotify-to-YouTube" audio routing mechanism: allowing playback of Spotify playlist tracks via YouTube audio streams without requiring Spotify Premium.
   - Unified playback controller state machine (play/pause, queue, scrub, volume, source switching).
3. `app.py` — high-performance local streaming backend:
   - Native HTTP 206 Partial Content range audio proxy streaming direct YouTube m4a streams with 0-disk footprint.
   - Dual-deck stream pre-resolution (`/api/preload`) and persistent disk cache (`tubefast_cache.json`).
   - Dead track quarantine engine (`DEAD_TRACK_CACHE` and `/api/dead_track`) filtering unavailable, dead, or live videos permanently.
   - Smart recommendation engine blending seed artists, listening history, and sonic styles.
   - Canonical song fingerprinting & deduplication (`get_song_title_keys`, `is_duplicate_song`): strips noise/brackets/features and blocks alternate YouTube uploads of the currently playing song or recently played tracks.
4. `client/index.html` — single-page responsive web player interface:
   - Clean, lightweight UI inspired by Tubefast (dark mode, minimal memory footprint).
   - Dual independent `<audio id="deckA">` and `<audio id="deckB">` elements for gapless zero-latency switching.
5. `client/player.js` — unified player abstraction layer:
   - Instant zero-delay first song playback: pre-buffers first discover song or hovered track on standby deck immediately on boot.
   - Standby deck verification chamber: traps `oncanplay` and `onerror` before swapping. Dead tracks are quarantined in the background without causing playback stutter or skipping.
   - Continuous smart autoplay queue replenishment with taste-profile radio.
   - Client-side canonical title tracking (`recentPlayedTitleKeys`, `getSongTitleKey`, `isDuplicateSongTitle`) guaranteeing alternate video uploads of the same song are filtered before deck swap.
   - Smooth unplayable fallback: seamlessly finds next playable track or similar song if an unplayable track is encountered in playlists or queue.
6. `client/style.css` — 2027 sleek animated glassmorphism stylesheet:
   - Deep space blacks (`#080810`, `#0d0d1a`, `#111125`) with vivid purple-to-cyan (`#7c3aed` -> `#06b6d4`) gradient accents and `#e879f9` magenta highlights.
   - Glassmorphism panels with `backdrop-filter: blur(20px) saturate(180%)`, ambient drift background animation (`@keyframes ambientShift`), and animated focus rings.
   - Immersive 100px bottom player bar with cover glow rotation, 48px gradient play button, animated equalizer visualizer, and dynamic gradient-filled progress and volume sliders.
   - Split discovery catalogs: 20 verified playable hip-hop/trap/drill tracks for YouTube Discovery, and 20 verified playable pop/R&B/chart hits for Spotify Discovery.
   - Dynamic mode switching: toggling between YouTube and Spotify automatically refreshes the discovery feed with platform-appropriate tracks and headers.
7. `test_verification.md` — local deployment guide and verification checklist.
