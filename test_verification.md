# test_verification.md — Lightning Player v1.1.8 Verification Report

## Problem Addressed
- **User Issue**: Autoplay and "similar music" recommendations would play one similar track and then unexpectedly drift into completely unrelated genres (e.g. playing Bad Bunny / Latin or Taylor Swift / Pop while listening to Rap music like Tee Grizzley).
- **Previous Root Cause**:
  1. In `app.py`, when candidate pools fell below 6 tracks, the backend unconditionally appended `SPOTIFY_FEATURED`.
  2. `SPOTIFY_FEATURED` contained hardcoded tracks from disparate genres: Bad Bunny ("Dakiti" — Latin / Reggaeton), Taylor Swift ("Shake It Off" — Pop), Katy Perry ("Roar" — Pop), BTS ("Dynamite" — K-Pop).
  3. In `categories_catalog.json`, Bad Bunny's `"MÍA (feat. Drake)"` was placed under `spotify / hiphop_central` purely due to Drake's feature, polluting rap queries.
  4. Query generation only sampled the primary seed artist (`primary_seed`), rapidly exhausting candidates and forcing fallback to the generic featured pool.

## Implemented Fixes in v1.1.8
1. **Catalog Sanitization (`categories_catalog.json`)**:
   - Replaced Bad Bunny (`MÍA`) in `spotify / hiphop_central` with Travis Scott (`FE!N (feat. Playboi Carti)`).
   - Verified that all 10 platform categories strictly adhere to their respective genres.

2. **In-Memory Genre Taxonomy & Registry (`app.py`)**:
   - Added canonical genre mapping (`GENRE_FAMILIES`, `CATEGORY_TO_FAMILY`, `ARTIST_TO_FAMILY`, `FAMILY_TO_ARTISTS`, `FAMILY_TO_TRACKS`).
   - `init_genre_catalog()`: Indexes all 169 catalog artists and tracks into isolated genre pools on startup.
   - `detect_genre_family(seed_title, seed_artist)`: Resolves genre family via local catalog index, with real-time fallback to Apple iTunes Search API (`entity=musicArtist`). Token boundaries protect Latin tracks (`Urbano latino`) from false-matching the English word `urban`.

3. **Genre-Locked Query Expansion**:
   - Dynamically samples 2–3 sibling artists from `FAMILY_TO_ARTISTS[seed_family]` (e.g. for Tee Grizzley: 21 Savage, Lil Baby, King Von, Future).
   - Generates multi-artist search queries across both Spotify and YouTube catalogs within the exact same genre family.
   - Filters user taste profile so only historical artists sharing the active `seed_family` can be sampled.

4. **Candidate Validation & Category-Locked Backfill**:
   - `is_candidate_genre_compatible(c)`: Rejects candidates whose artists belong to conflicting genre families (hard-filtering Latin and Pop when playing Rap).
   - Replaced generic `SPOTIFY_FEATURED` backfills with `FAMILY_TO_TRACKS[seed_family]`, ensuring backfill tracks are 100% sourced from the matching category (e.g. `hiphop_central`, `rap_trap`, `drill_underground`).
   - Cleaned default `SPOTIFY_FEATURED` and `YOUTUBE_FEATURED` lists (replacing Bad Bunny with Travis Scott - "goosebumps", Taylor Swift with Kendrick Lamar - "HUMBLE.", and Halsey with Travis Scott ft. Drake - "SICKO MODE").

5. **Version Bump**:
   - Updated `APP_VERSION = "1.1.8"` in `app.py`.
   - Updated `version_info.txt` to `1.1.8.0`.
   - Built standalone executable `dist\Lightning Player.exe` (17.3 MB) and packaged `Lightning-Player-v1.1.8-Windows-x64.zip` (16.9 MB).

## Verification Results
- **Tee Grizzley Seed (`rap`)**:
  - Detected Family: `rap`
  - Sampled Similar Artists: `Future`, `King Von`, `21 Savage`
  - Recommendations: Roddy Ricch, Future, King Von, Tee Grizzley, Pop Smoke, Sleepy Hallow, Travis Scott, Playboi Carti.
  - Zero Spanish or Pop tracks.
- **Bad Bunny Seed (`latin`)**:
  - Detected Family: `latin`
  - Sampled Similar Artists: `Ozuna`, `Maluma`, `Shakira`
  - Recommendations: Bad Bunny, Bomba Estéreo, Ozuna, Shakira, Maluma, Chencho Corleone.
  - Zero Rap or Rock tracks.
- **Taylor Swift Seed (`pop`)**:
  - Detected Family: `pop`
  - Recommendations: Taylor Swift, Arizona Zervas, Lil Nas X.
  - Zero cross-genre contamination.
