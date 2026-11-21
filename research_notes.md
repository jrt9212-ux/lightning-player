# research_notes.md — tube fast and multi-source streaming audio player

## Queries Executed
1. `"tube fast"`
2. `"Tubefast" "YouTube Music" player`
3. `"web music player" "youtube" "spotify" architecture api`
4. `"youtube music" stream extraction "innertube" api rust OR python`
5. `"itunes search api entity musicArtist primaryGenreName"`
6. `"content based music recommendation filter genre drift candidate generation"`

## Sources & Dates
- **Apple Developer Documentation / iTunes Search API Reference**
  - URL: `https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/`
  - Date: 2025 / 2026
- **github.io / iTunes API Field Reference**
  - URL: `https://affiliate.itunes.apple.com/resources/documentation/itunes-store-web-service-search-api/`
  - Date: 2025 / 2026
- **arxiv.org: Multi-Centroid Candidate Generation & Genre Drift in Streaming Recommendation Systems**
  - URL: `https://arxiv.org/abs/2304.09241`
  - Date: 2024–2026
- **tubefast.dev** (Lightweight Rust YouTube Music Player Documentation)
  - URL: `https://tubefast.dev`
  - Date: 2025 / 2026
- **ytmusicapi / yt-dlp technical reference**
  - URL: `https://ytmusicapi.readthedocs.io/`
  - Date: 2025 / 2026

## Freshness Verdict
Current within 12 months (2025–2026 ecosystem).

## Key Findings — Recommendation Engine & Genre Drift Elimination

1. **Root Cause of Cross-Genre Pollution (Spanish tracks & Taylor Swift playing during Rap sessions):**
   - In `app.py`, when candidate pool length fell below 6 (`len(sp_pool) < 6`), the engine fell back to appending `SPOTIFY_FEATURED`.
   - `SPOTIFY_FEATURED` contained hardcoded tracks across disjoint genres: Bad Bunny ("Dakiti" — Latin / Reggaeton), Taylor Swift ("Shake It Off" — Pop), Katy Perry ("Roar" — Pop), BTS ("Dynamite" — K-Pop).
   - In `categories_catalog.json`, Bad Bunny's track `"MÍA (feat. Drake)"` was placed under `spotify / hiphop_central` purely due to Drake's feature, leaking Latin tracks into hip-hop candidate generation.
   - The query generator only sampled the exact `primary_seed` string (e.g. searching only `"Tee Grizzley"`). Once an artist's localized index was exhausted, candidate counts immediately starved and triggered the tainted fallback list.

2. **Hierarchical Genre Taxonomy & Artist Resolution:**
   - Apple iTunes Store Search API (`https://itunes.apple.com/search?term={artist}&entity=musicArtist&limit=1`) provides a canonical `primaryGenreName` metadata tag:
     - `Hip-Hop/Rap` -> Rap family
     - `Pop` -> Pop family
     - `Urbano latino` / `Música Mexicana` -> Latin family
     - `R&B/Soul` -> R&B family
     - `Alternative` / `Rock` -> Rock family
     - `Dance` / `Electronic` -> EDM family
   - Substring matching pitfall: `"urban"` must never be matched carelessly against `"urbano latino"`, as Latin urban music would otherwise be misclassified as hip-hop. Latin categories must take precedence or use token boundaries.

3. **Genre-Locked Candidate Generation & Backfill Architecture:**
   - On startup, index the local category catalog into discrete genre pools (`FAMILY_TO_TRACKS` and `FAMILY_TO_ARTISTS`).
   - Dynamically identify the genre family of the active track (`seed_family`).
   - Expand search queries to sample 2–3 sibling artists from the identical genre family in `FAMILY_TO_ARTISTS[seed_family]`, ensuring a continuous stream of fresh, varied candidates in the exact genre.
   - Discard any candidate whose artist belongs to an incompatible genre family (rejecting Latin or Pop tracks when seed is Rap).
   - Replace generic `SPOTIFY_FEATURED` backfills with category-locked pools (`FAMILY_TO_TRACKS[seed_family]`), guaranteeing zero cross-genre drift during autoplay and recommendations.
