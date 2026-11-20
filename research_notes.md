# research_notes.md — tube fast and multi-source streaming audio player

## Queries Executed
1. `"tube fast"`
2. `"Tubefast" "YouTube Music" player`
3. `"web music player" "youtube" "spotify" architecture api`
4. `"youtube music" stream extraction "innertube" api rust OR python`

## Sources & Dates
- **tubefast.dev** (Lightweight Rust YouTube Music Player Documentation)
  - URL: `https://tubefast.dev`
  - Date: 2025 / 2026
- **docs.rs: innertube-rs** (Rust client for YouTube / YouTube Music stream resolution)
  - URL: `https://docs.rs/innertube-rs`
  - Date: 2025 / 2026
- **developer.spotify.com** (Spotify Web Playback SDK & Web API Guides)
  - URL: `https://developer.spotify.com/documentation/web-playback-sdk`
  - Date: 2025 / 2026
- **ytmusicapi / yt-dlp technical reference**
  - URL: `https://ytmusicapi.readthedocs.io/`
  - Date: 2025 / 2026

## Freshness Verdict
Current within 12 months (2025–2026 ecosystem).

## Catalog Separation & Unreleased Audio Findings
1. **Catalog Boundary (Spotify vs YouTube):**
   - Community-created tribute mashups and unreleased leaks (e.g. `"I'm Here"` by XXXTENTACION ft. Juice WRLD & Lil Peep) circulate exclusively on YouTube, SoundCloud, and Audiomack. They do not exist within official commercial catalogs (Spotify / Apple Music).
   - Spotify Mode queries official commercial releases (ISRC-registered studio masters), cleanly filtering out unofficial fan uploads and leaks.
   - YouTube Mode searches the open video index via yt-dlp flat extraction, preserving access to unreleased tracks, live sets, remixes, and fan mashups.
2. **Audio Streaming Engine (Zero-Download In-Memory Pipeline):**
   - Rather than saving files to disk (which causes buffering delays and Pygame SDL_mixer codec faults), the backend acts as an HTTP 206 Partial Content proxy.
   - Chunks (64KB) stream directly from YouTube's progressive format 140 (AAC/M4A) straight into the HTML5 `<audio>` element with zero disk footprint.
3. **Application Mode Lifecycle Management:**
   - Standalone execution uses Microsoft Edge in dedicated app mode (`--app=http://127.0.0.1:8420 --user-data-dir=...`).
   - A heartbeat watchdog with a 60-second window and an unload beacon prevents premature server shutdown while providing clean teardown when the window is closed.

## Key Findings
1. **What is Tube Fast / Tubefast:**
   - Tubefast is an ultra-lightweight desktop streaming player for YouTube Music written in Rust (not Chromium/Electron), using direct InnerTube backend extraction and native audio decoding (typically rodio / symphonia / cpal) with a tiny memory footprint (~100MB RAM vs 600MB+ for browser wrappers).
2. **Feasibility of a Custom Online / Web Music Player Routing Through YouTube / Spotify:**
   - **YouTube Audio Playback:**
     - *Client-side Web Approach:* YouTube IFrame Player API. Embeds an invisible or minimized YouTube player inside the web app. Fully ToS-friendly, requires zero hosting or proxy servers for streams, no API quotas for media bytes.
     - *Backend Stream Extraction Approach:* InnerTube scraping / yt-dlp. Resolves direct audio streams (m4a/opus) and pipes to HTML5 `<audio>` elements or native decoders. Can suffer from YouTube IP blocks / cipher rotations (`n`-token / signature cipher) if run from cloud IPs.
   - **Spotify Audio Playback:**
     - *Constraint:* Raw Spotify audio files cannot be streamed directly due to Widevine / FairPlay DRM.
     - *SDK Requirement:* Spotify Web Playback SDK connects to Spotify Connect directly in the browser. Requires the logged-in user to have **Spotify Premium**.
     - *Metadata:* Spotify Web API provides track search, playlist tracks, album art, and metadata with standard OAuth 2.0.
   - **Hybrid Routing Architecture:**
     - Best pattern for a custom web player: Unified frontend player interface (Strategy pattern) where user can paste/search tracks.
     - Spotify tracks trigger Spotify Web Playback SDK (or fallback to searching and resolving the identical track name/artist on YouTube to stream without requiring Premium).
     - YouTube tracks play through YouTube IFrame API or audio stream resolver.
