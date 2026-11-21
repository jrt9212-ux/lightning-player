# test_verification.md — Lightning Player v1.1.9 Verification Report

## Problem Addressed
1. **Category Pills Top Cut-Off**:
   - The category pill buttons in the discover header appeared sliced off flat at the top border (due to container `overflow-x: auto` clipping contents and default button line-height geometry).
2. **Skip Song Glitch & Liked Songs Trap**:
   - When skipping songs while audio was loading or buffering, the player would enter a runaway loop buffering through ~8 tracks in rapid succession.
   - The player would jump into Liked Songs unexpectedly and get stuck sequentially playing through the user's liked library instead of continuing discover autoplay.

## Root Causes Identified
1. **Category Pill Slicing**:
   - `.category-pill-bar` had asymmetric vertical padding (`8px 2px 14px 2px`) inside a container with `overflow-x: auto` (which forces `overflow-y: hidden`).
   - `.category-pill` elements did not enforce explicit `box-sizing: border-box`, `height: 38px`, or reset line-height, causing the top border and box-shadow to be clipped by the parent element's scroll boundary.
2. **8-Song Buffering Cascade**:
   - When skipping while a track is loading, updating `audio.src` rejects the pending `play()` promise with DOMException `AbortError` (code 20).
   - The `.catch()` handler treated this abort as a track failure, calling `handleDeckPlaybackError` -> `findAndPlayNextPlayableTrack`, which started loading the next track and triggered another abort, repeating across up to 8 tracks.
3. **Premature Watchdog Trigger**:
   - `playbackWatchdogTimer` checked for zero movement (`Math.abs(cur - lastAudioPosition) < 0.05`) even when `cur === 0`, causing tracks with slow DNS or initial audio buffering to be falsely flagged as stalled after 8 seconds and aborted.
4. **Liked Songs Hijack**:
   - Both `triggerSmartAutoplay()` and `findAndPlayNextPlayableTrack()` had fallbacks that iterated over `state.likedSongs` when candidate queues were small or replenishing.
   - `playNextTrack()` checked `state.activeTab !== 'discover'` rather than checking actual playback context, causing next button presses during discover view to step through `state.likedSongs`.

## Implemented Fixes in v1.1.9
1. **Category Pill Styling (`client/style.css`)**:
   - Added balanced padding to `.category-pill-bar`: `padding: 10px 4px 12px 4px; margin-top: 4px;`.
   - Set `.category-pill`: `height: 38px; padding: 0 16px; box-sizing: border-box; flex-shrink: 0; line-height: 1; outline: none; border: 1px solid rgba(255, 255, 255, 0.08);`.
   - Adjusted `.category-pill.active`: `border: 1.5px solid #38bdf8; box-shadow: 0 0 14px rgba(14, 165, 233, 0.3);`.
   - Verified in headless Edge layout test: top and bottom borders are completely visible with zero pixel clipping.
2. **Abort Error Handling (`client/player.js`)**:
   - In `playTrackImmediately` and `executeDeckSwapAndPlay`, added explicit checks:
     ```javascript
     if (err.name === 'AbortError' || err.code === 20) {
       console.log('Playback interrupted by new track selection (safe abort).');
       return;
     }
     ```
   - Eliminates cascading skip loops completely.
3. **Watchdog Guard (`client/player.js`)**:
   - Added guard condition `cur > 0.5` and extended timeout threshold to 12s so initial track loading is never killed prematurely.
4. **Context-Aware Playback & Liked Songs Isolation (`client/player.js`)**:
   - Added `state.playbackContext` track state ('discover' | 'playlist' | 'liked' | 'queue').
   - Replaced all `state.likedSongs` fallback loops in `triggerSmartAutoplay` and `findAndPlayNextPlayableTrack` with category pool fallbacks (`state.discoverData.categories[state.activeCategory]?.tracks` or `state.currentList`), keeping recommendations locked to the active genre.
   - Restricted sequential list stepping in `playNextTrack` strictly to `state.playbackContext === 'playlist' || state.playbackContext === 'liked'`.
   - Added 350ms button debounce `isSkippingTrack` on `elements.nextBtn` and `elements.prevBtn`.
   - Fixed `handlePlayAll()` to enqueue `list.slice(1)` so track 0 is not immediately queued behind itself.
5. **Version Bump & Packaging**:
   - `app.py`: `APP_VERSION = "1.1.9"`
   - `version_info.txt`: `1.1.9.0`
   - Compiled executable `Lightning Player.exe` (17.3 MB)
   - Created release package `Lightning-Player-v1.1.9-Windows-x64.zip` (16.9 MB)

## Verification Checklist
- [x] Category pill borders symmetrically rendered, top border not clipped.
- [x] Rapid skip clicking does not trigger AbortError cascades or multi-song skip loops.
- [x] Skipping during discover playback stays within discover/smart autoplay without jumping to Liked Songs.
- [x] Binary version properties report 1.1.9.0.
- [x] Release zip contains updated executable and assets.
