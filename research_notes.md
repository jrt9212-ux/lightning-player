# research_notes.md — Streaming Architecture & Platform Routing

## Queries Used
1. `yt-dlp extract audio stream url reliable`
2. `yt-dlp extractor_args youtube player_client web_creator mweb ios android`

## Source URLs & Publication Dates
- GitHub yt-dlp repository & issues (2025/2026): https://github.com/yt-dlp/yt-dlp
- ytdlp.org documentation (2025/2026): https://ytdlp.org
- StackOverflow programmatic extraction reference (2025): https://stackoverflow.com

## Key Findings
1. **Audio Extraction Reliability & Throttling**:
   - Direct googlevideo URLs extracted via `bestaudio` are tied to client IP, headers (User-Agent, Range), and expire quickly.
   - Using multiple fallback clients in `extractor_args` (`youtube:player_client=mweb,android,ios,web`) prevents 403 Forbidden throttling and signature failure when any single client interface is restricted or blocked by YouTube.
   - For audio streaming proxying, passing `m4a` / `aac` formats (`bestaudio[ext=m4a]/bestaudio`) ensures native Windows / Chromium `<audio>` compatibility without transcoding delays.

2. **Platform Routing & Shuffling Architecture**:
   - The user requested: "routes through each platform and shuffles and skips as the selected platform".
   - When YouTube is selected: all playback, recommendations, shuffles, and autoplay must remain strictly within YouTube's open catalog and YouTube tracks.
   - When Spotify is selected: tracks from Spotify catalog must cleanly resolve to high-quality audio streams without blocking or failing, and next/shuffle operations must stay strictly within the Spotify catalog context.
   - Instant deck pre-buffering must verify stream reachability with HEAD / probe before swapping decks, eliminating unplayable stalls and silent skip loops.

## Freshness Verdict
Current within 12 months (2025-2026 yt-dlp client mechanisms and Chromium audio guidelines).
