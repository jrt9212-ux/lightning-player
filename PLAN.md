# PLAN.md — custom online streaming player (youtube & spotify routing)

1. `research_notes.md` — findings from the search gate, with source URLs.
2. `categories_catalog.json` — catalog sanitization:
   - Purged Bad Bunny from `hiphop_central` (replaced with Travis Scott - "FE!N (feat. Playboi Carti)").
   - Verified clean genre clustering across all 10 platform categories.
3. `app.py` — recommendation engine & smart autoplay overhaul (bump to v1.1.8):
   - In-memory genre taxonomy registry (`GENRE_FAMILIES`, `CATEGORY_TO_FAMILY`, `ARTIST_TO_FAMILY`, `FAMILY_TO_ARTISTS`, `FAMILY_TO_TRACKS`).
   - `init_genre_catalog()`: indexes all catalog tracks and artists into genre-locked pools on initialization.
   - `detect_genre_family(seed_title, seed_artist)`: detects genre family via local catalog, followed by live Apple iTunes Search API query (`entity=musicArtist`), with token-safe Latin/Rap distinction and fallback heuristics.
   - `get_smart_recommendations(...)`:
     - Detects `seed_family`.
     - Samples 2–3 sibling artists from `FAMILY_TO_ARTISTS[seed_family]` to generate rich, varied search queries within the same genre.
     - Filters taste history so only artists matching `seed_family` can be sampled.
     - Candidate genre validator (`is_candidate_genre_compatible`): rejects cross-genre contamination (blocks Spanish/Latin or Pop songs when playing Rap).
     - Category-locked backfill: pulls backfills exclusively from `FAMILY_TO_TRACKS[seed_family]`, eliminating generic `SPOTIFY_FEATURED` cross-genre leaks.
   - Sanitized `SPOTIFY_FEATURED` and `YOUTUBE_FEATURED` default lists to remove mismatched tracks.
   - Bumps `APP_VERSION` to `1.1.8`.
4. `version_info.txt` — bump Windows binary resource version to `1.1.8.0`.
5. `compile and package` — compile with PyInstaller (`TubeFast.spec`), verify zero warnings, replace root `Lightning Player.exe`, and generate `Lightning-Player-v1.1.8-Windows-x64.zip`.
6. `test_verification.md` — test verification report.
