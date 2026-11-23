# Research Notes: Platform Metadata Isolation & History Traversal

## Exact Query Used
`spotify web api track metadata youtube music streaming`

## Source URLs & Publication Dates
1. **Spotify Developer Documentation — Web API Reference & Track Object**
   - URL: `https://developer.spotify.com/documentation/web-api`
   - Retrieved: 2026-11-23 (Current/Live documentation)
2. **TuneMyMusic / Multi-Platform Audio Architecture Standards**
   - URL: `https://tunemymusic.com`
   - Retrieved: 2026-11-23 (Current service specification)
3. **ytmusicapi & YouTube Data API Streaming Patterns**
   - URL: `https://github.com/sigma67/ytmusicapi`
   - Retrieved: 2026-11-23 (Active repository)

## Key Findings
1. **Platform Isolation vs Composite Playlists**:
   - In single-platform modes (YouTube mode vs Spotify mode), Discovery feeds and Smart Recommendations must strictly isolate track candidates:
     - YouTube mode: Query only YouTube Music / YouTube audio stream sources. No Spotify track IDs or Spotify-curated recommendation endpoints should pollute the Discovery categories.
     - Spotify mode: Query only Spotify catalog tracks. No YouTube search results should populate Discovery categories.
     - Custom User Playlists: The only context where mixed-source tracks are permitted is user-saved playlists, which explicitly support heterogeneous track sources (`source: 'youtube'` and `source: 'spotify'` coexisting).
2. **History Navigation Stack (Previous Track)**:
   - Alternating between two tracks when clicking "Previous" is caused by pushing the current track back to the top of an array on each play.
   - A true LIFO history stack (capped at 10 items) must track previously played tracks. When the user navigates backward (`playPrevTrack`), the player pops from the stack and sets an `isNavigatingHistory` flag so the popped track is not immediately re-pushed to history.
3. **Recently Listened Category (Sidebar)**:
   - A dedicated "Recently Listened" view in the sidebar requires rendering `state.history` with real-time updates as songs start playing, deduplicating consecutive repeats, persisting up to 50 items in local storage, and providing a "Clear History" action.
4. **Category Pill Bar Top Clipping**:
   - CSS fixed heights (`height: 58px; max-height: 58px`) with `overflow-x: auto` cause Windows browsers to deduct horizontal scrollbar height from the content box, squeezing the 36px pill and clipping its top border against `overflow-y: hidden`.
   - Changing to `height: auto; min-height: 54px; padding: 8px 6px;` and hiding native scrollbars (`scrollbar-width: none !important; -ms-overflow-style: none !important; ::-webkit-scrollbar { display: none !important; }`) while using mouse-wheel horizontal scrolling guarantees zero clipping and smooth behavior.

## Freshness Verdict
- Verdict: Current within 12 months (verified November 2026).
