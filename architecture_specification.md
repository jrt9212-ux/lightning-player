# architecture_specification.md — dual-source streaming audio player

## 1. System Overview
The goal is to recreate the snappy, minimal experience of lightweight desktop audio clients like Tubefast inside an accessible web application. The player routes audio from both **YouTube** and **Spotify** under a single unified user interface.

## 2. Core Components

### A. Frontend UI (`client/index.html`, `client/style.css`)
- **Search Header & Source Selector:**
  - Search bar accompanied by a selector toggle: `[YouTube | Spotify]`.
  - When YouTube is selected: Searches YouTube Data / queries videos, directly streams audio via embedded IFrame audio-mode playback.
  - When Spotify is selected: Searches Spotify catalog via metadata endpoint. If user has Spotify Premium connected, plays via Spotify Web Playback SDK. If not connected or unauthenticated, routes playback seamlessly to the matching YouTube audio stream.
- **Track Queue & History:**
  - Unified queue tracking title, artist, duration, thumbnail, and stream source (`youtube` or `spotify`).
- **Player Controls & Scrub Bar:**
  - Standard playback controls: Play/Pause, Previous, Next, Loop, Shuffle.
  - Interactive scrub bar with real-time playback timestamp updates.
  - Volume slider and mute toggle.

### B. Unified Player Engine (`client/player.js`)
- **Strategy Pattern Engine:**
  - An abstraction controller that delegates commands (`loadTrack`, `play`, `pause`, `seekTo`, `setVolume`) to the active provider without breaking queue continuity.
- **YouTube Driver:**
  - Uses the official YouTube IFrame Player API.
  - Embeds a hidden/minimized video player container so that YouTube policies regarding player visibility and event firing are fulfilled without cluttering the UI.
- **Spotify Driver:**
  - Uses the Spotify Web Playback SDK for full authenticated playback.
  - Embeds fallback bridge: resolves `artist + track name` to YouTube audio if Spotify SDK cannot initialize on free/guest accounts.

### C. Server Backend (`server/server.js`)
- Standard Node.js HTTP server (zero external dependencies or lightweight express).
- Static file server for the web player assets (`/client`).
- API proxy endpoints:
  - `/api/search?q={query}&source={youtube|spotify}`
  - `/api/spotify/token` (handles client credentials or local session tokens)
