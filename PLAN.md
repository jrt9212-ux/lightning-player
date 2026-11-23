# Execution Plan: Lightning Player v2.0.0 Release & Updater Overhaul

## 1. Research & Analysis (Complete)
- `research_notes.md`: Documents Windows process file locking (`ERROR_SHARING_VIOLATION`), process tree termination (`taskkill /f /pid`), batch working directory preservation (`cd /d`), and semver comparison normalization.

## 2. Implementation & Fixes (Complete)
- **Windows Self-Updater Overhaul (`app.py`)**:
  - Implemented PID and process name taskkill in updater bootstrap script before file swap.
  - Active polling loop awaiting kernel process termination (`tasklist /fi "pid eq {pid}"`).
  - Robust 10-attempt move/copy replacement loop with retry delays.
  - Added `cd /d "{target_dir}"` before spawning target executable to ensure working directory context is retained.
  - Added automatic `.zip` archive extraction when release assets are bundled in zip packages.
  - Normalized version comparison to 3-part semver padding (`[2] == [2, 0, 0]`).
  - Bumped `APP_VERSION = "2.0.0"`.
- **Category Pill Bar Anti-Clipping (`client/style.css`)**:
  - Set `min-height: 56px; height: auto; padding: 10px 8px;` and removed `contain: layout` and fixed 58px bounding.
  - Verified with CDP rendering: pills have 10px breathing room on top and bottom; zero clipping on active border and box-shadow.
- **Library & Navigation Enhancements (`client/index.html`, `client/player.js`)**:
  - Added Recently Listened category to left sidebar with real-time badge count and Clear History action.
  - Added 10-track reverse traversal stack on Previous Track button.
  - Strict platform isolation on Discovery tab (100% YouTube on YouTube mode, 100% Spotify on Spotify mode; cross-platform allowed only in saved user playlists).
- **Binary & Version Artifacts (`version_info.txt`, `dist/Lightning Player.exe`, `Lightning Player.exe`)**:
  - Bumped Windows file and product version to `2.0.0.0`.
  - Built fresh standalone one-file executable `Lightning Player.exe` via PyInstaller.
  - Packaged standalone release zip `Lightning-Player-v2.0.0-Windows-x64.zip`.

## 3. Verification & Testing (Complete)
- Automated updater simulation verified clean PID kill, file swap, and target launch.
- Headless browser CDP screenshot analysis confirmed intact 36px pill rendering without clipping.
- Discovery API verified 100% pure platform isolation for YouTube and Spotify modes.
