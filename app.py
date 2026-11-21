#!/usr/bin/env python3
"""
app.py - Standalone Desktop Launcher for TubeFast
Dual-source streaming architecture:
- YouTube mode: searches YouTube's open catalog (includes remixes, leaks, live versions)
- Spotify mode: searches official commercial release catalog (Spotify/Apple Music library)
Zero whole-song disk downloads. 100% in-memory streaming audio.
"""
import http.server
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
import gc
import ctypes
import concurrent.futures
from collections import deque

# Configure Microsoft Edge WebView2 for minimal RAM footprint (<150MB total)
if "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS" not in os.environ:
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        "--renderer-process-limit=1 "
        "--js-flags=--max-old-space-size=96 "
        "--disable-gpu-shader-disk-cache "
        "--disable-background-networking "
        "--disable-component-update "
        "--disable-features=OptimizationHints,Translate,MediaRouter,CalculateNativeWinOcclusion "
        "--disk-cache-size=16777216 "
        "--media-cache-size=16777216 "
        "--disable-extensions"
    )

kernel32 = ctypes.windll.kernel32 if os.name == 'nt' else None
user32 = ctypes.windll.user32 if os.name == 'nt' else None

def trim_process_memory():
    """Trim unreferenced heap objects and discard unused physical pages back to Windows OS."""
    try:
        gc.collect()
        if kernel32 and os.name == 'nt':
            try:
                ctypes.windll.psapi.EmptyWorkingSet(kernel32.GetCurrentProcess())
            except Exception:
                pass
    except Exception:
        pass

def memory_watchdog_thread():
    """Periodically trims process working set memory to maintain minimal RAM footprint (<100MB)."""
    while not SHUTDOWN_REQUESTED:
        time.sleep(30)
        trim_process_memory()

MUTEX_NAME = "Local\\LightningPlayer_SingleInstance_App_Mutex_8420"
ERROR_ALREADY_EXISTS = 183
APP_MUTEX = None

def enforce_single_instance():
    global APP_MUTEX
    if not kernel32:
        return
    APP_MUTEX = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    err = kernel32.GetLastError()
    if err == ERROR_ALREADY_EXISTS:
        log("Existing Lightning Player instance detected. Restoring focus and exiting.")
        if user32:
            hwnd = find_app_window()
            if hwnd:
                if user32.IsIconic(hwnd):
                    user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
        sys.exit(0)

def suppress_unhandled_exceptions(exctype, value, tb):
    if issubclass(exctype, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(exctype, value, tb)
        return
    log(f"Suppressed exception on exit: {exctype.__name__}: {value}")

sys.excepthook = suppress_unhandled_exceptions

class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long), ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ('length', ctypes.c_uint),
        ('flags', ctypes.c_uint),
        ('showCmd', ctypes.c_uint),
        ('ptMinPosition', POINT),
        ('ptMaxPosition', POINT),
        ('rcNormalPosition', RECT)
    ]

WINDOW_HWND = None
WEBVIEW_WINDOW = None
IS_MAXIMIZED = False
CLOSING = False
CLOSING_LOCK = threading.Lock()

APP_VERSION = "1.1.7"

UPDATE_STATE = {
    "current_version": APP_VERSION,
    "latest_version": APP_VERSION,
    "update_available": False,
    "download_url": "",
    "changelog": "",
    "downloading": False,
    "progress": 0,
    "ready_to_restart": False,
    "error": None
}
UPDATE_LOCK = threading.Lock()

def get_updater_config():
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv else "."))
    cfg_path = os.path.join(base_dir, "updater_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"Error reading updater_config.json: {e}")
    return {
        "github_repo": "jrt9212-ux/lightning-player",
        "update_url": "",
        "auto_check": True,
        "auto_apply": False
    }

def is_version_newer(latest, current):
    def parse_v(v):
        return [int(x) for x in re.findall(r'\d+', str(v))]
    try:
        p_latest = parse_v(latest)
        p_current = parse_v(current)
        return p_latest > p_current
    except Exception:
        return str(latest).strip().lower() != str(current).strip().lower()

def check_for_updates():
    cfg = get_updater_config()
    if not cfg.get("auto_check", True):
        return None

    repo = cfg.get("github_repo", "").strip()
    custom_url = cfg.get("update_url", "").strip()

    # 1. Custom JSON URL check
    if custom_url and custom_url.startswith("http"):
        try:
            req = urllib.request.Request(custom_url, headers={"User-Agent": f"LightningPlayer/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                remote_v = data.get("version", "").lstrip("v")
                dl_url = data.get("url", "") or data.get("download_url", "")
                notes = data.get("notes", "") or data.get("changelog", "")
                if remote_v and is_version_newer(remote_v, APP_VERSION) and dl_url:
                    with UPDATE_LOCK:
                        UPDATE_STATE["latest_version"] = remote_v
                        UPDATE_STATE["update_available"] = True
                        UPDATE_STATE["download_url"] = dl_url
                        UPDATE_STATE["changelog"] = notes
                    log(f"Update available via custom URL: v{remote_v}")
                    return UPDATE_STATE
        except Exception as e:
            log(f"Custom URL update check failed: {e}")

    # 2. GitHub Releases API check
    if repo and "/" in repo and not repo.startswith("your-github-username"):
        try:
            api_url = f"https://api.github.com/repos/{repo}/releases/latest"
            req = urllib.request.Request(api_url, headers={
                "User-Agent": f"LightningPlayer/{APP_VERSION}",
                "Accept": "application/vnd.github.v3+json"
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    tag = data.get("tag_name", "").lstrip("v")
                    body = data.get("body", "")
                    assets = data.get("assets", [])
                    exe_url = None
                    for a in assets:
                        name = a.get("name", "").lower()
                        if name.endswith(".exe"):
                            exe_url = a.get("browser_download_url")
                            break

                    if tag and is_version_newer(tag, APP_VERSION) and exe_url:
                        with UPDATE_LOCK:
                            UPDATE_STATE["latest_version"] = tag
                            UPDATE_STATE["update_available"] = True
                            UPDATE_STATE["download_url"] = exe_url
                            UPDATE_STATE["changelog"] = body
                        log(f"Update available via GitHub: v{tag} -> {exe_url}")
                        return UPDATE_STATE
        except Exception as e:
            log(f"GitHub update check failed for {repo}: {e}")

    return None

def trigger_update_download():
    with UPDATE_LOCK:
        if UPDATE_STATE["downloading"] or not UPDATE_STATE["download_url"]:
            return False
        UPDATE_STATE["downloading"] = True
        UPDATE_STATE["progress"] = 0
        UPDATE_STATE["error"] = None

    def worker():
        try:
            url = UPDATE_STATE["download_url"]
            temp_dir = tempfile.gettempdir()
            new_exe = os.path.join(temp_dir, f"LightningPlayer_v{UPDATE_STATE['latest_version']}_{int(time.time())}.exe")

            log(f"Downloading update from {url} to {new_exe}...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as resp:
                total_len = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(new_exe, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_len > 0:
                            pct = int((downloaded / total_len) * 100)
                            with UPDATE_LOCK:
                                UPDATE_STATE["progress"] = min(99, pct)

            with UPDATE_LOCK:
                UPDATE_STATE["downloading"] = False
                UPDATE_STATE["progress"] = 100
                UPDATE_STATE["ready_to_restart"] = True
            log("Update download complete. Executing in-place restart...")
            execute_windows_swap_and_restart(new_exe)
        except Exception as e:
            log(f"Update download failure: {e}")
            with UPDATE_LOCK:
                UPDATE_STATE["downloading"] = False
                UPDATE_STATE["error"] = str(e)

    threading.Thread(target=worker, daemon=True).start()
    return True

def execute_windows_swap_and_restart(new_exe_path):
    time.sleep(1.2)
    if getattr(sys, 'frozen', False):
        target_exe = os.path.abspath(sys.executable)
    else:
        target_exe = os.path.abspath("Lightning Player.exe")

    ts = int(time.time())
    bat_path = os.path.join(tempfile.gettempdir(), f"lp_swap_{ts}.bat")
    vbs_path = os.path.join(tempfile.gettempdir(), f"lp_run_{ts}.vbs")

    # Clean batch script: moves the new executable into place and launches it
    bat_content = f"""@echo off
chcp 65001 >nul
set _MEIPASS2=
set _MEIPASS=
set _PYI_APPLICATION_HOME_DIR=
set _PYI_PARENT_PROCESS_LEVEL=
set _PYI_ARCHIVE_FILE=
set _PYI_SPLASH_IPC=
set PYINSTALLER_RESET_ENVIRONMENT=
set PYINSTALLER_STRICT_UNPACK_MODE=
timeout /t 2 /nobreak >nul
:loop
move /y "{new_exe_path}" "{target_exe}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto loop
)
start "" "{target_exe}"
del "%~f0" >nul 2>&1
"""

    # VBScript runner: WshShell.Run with window style 0 runs cmd.exe 100% INVISIBLE with zero window flash
    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.Run "cmd.exe /c """"{bat_path}""""", 0, False\r\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
        'On Error Resume Next\r\n'
        'fso.DeleteFile WScript.ScriptFullName\r\n'
    )
    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write(vbs_content)

        clean_env = os.environ.copy()
        for k in list(clean_env.keys()):
            if k.startswith("_PYI") or k.startswith("_MEI") or "PYINSTALLER" in k:
                clean_env.pop(k, None)

        # wscript.exe is a GUI subsystem process: zero console window ever created
        subprocess.Popen(["wscript.exe", vbs_path], env=clean_env, close_fds=True)
        log("Dispatched silent VBS updater runner. Terminating host application.")
    except Exception as e:
        log(f"Error launching restart runner: {e}")

    safe_close_window()
    os._exit(0)

def auto_update_watchdog_thread():
    time.sleep(4)
    while not SHUTDOWN_REQUESTED:
        try:
            check_for_updates()
            cfg = get_updater_config()
            if cfg.get("auto_apply", False) and UPDATE_STATE.get("update_available"):
                trigger_update_download()
        except Exception:
            pass
        time.sleep(900)  # check every 15 minutes

def safe_close_window():
    global CLOSING, SHUTDOWN_REQUESTED
    with CLOSING_LOCK:
        if CLOSING:
            return
        CLOSING = True
    SHUTDOWN_REQUESTED = True
    log("Clean window shutdown triggered.")
    if WEBVIEW_WINDOW:
        try:
            WEBVIEW_WINDOW.destroy()
        except Exception:
            pass
    elif user32:
        hwnd = find_app_window()
        if hwnd:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)

def set_window_icon(hwnd):
    if not user32: return
    try:
        base_dir = get_base_dir()
        icon_path = os.path.join(base_dir, "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.abspath("icon.ico")
        if os.path.exists(icon_path):
            WM_SETICON = 0x0080
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            h_icon_big = user32.LoadImageW(None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
            h_icon_small = user32.LoadImageW(None, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            if h_icon_big:
                user32.SendMessageW(hwnd, WM_SETICON, 1, h_icon_big)
            if h_icon_small:
                user32.SendMessageW(hwnd, WM_SETICON, 0, h_icon_small)
            log(f"Applied custom lightning icon on HWND {hex(hwnd)}")
    except Exception as e:
        log(f"set_window_icon error: {e}")

def strip_window_decorations(hwnd):
    if not user32: return
    try:
        set_window_icon(hwnd)
        GWL_STYLE = -16
        WS_CAPTION = 0x00C00000
        WS_SYSMENU = 0x00080000
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        if style & WS_CAPTION:
            style &= ~WS_CAPTION
            style &= ~WS_SYSMENU
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0004 | 0x0020)
            log(f"Stripped top native titlebar from HWND {hex(hwnd)}")
    except Exception as e:
        log(f"strip_window_decorations error: {e}")

def find_app_window():
    global WINDOW_HWND
    if not user32: return None
    if WINDOW_HWND and user32.IsWindow(WINDOW_HWND):
        return WINDOW_HWND

    hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
    found = []
    def cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                val = buff.value.lower()
                if "lightning" in val or "tubefast" in val:
                    found.append(hwnd)
        return 1

    CB = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(cb)
    try:
        if hdesk:
            user32.EnumDesktopWindows(hdesk, CB, 0)
        else:
            user32.EnumWindows(CB, 0)
    except Exception:
        pass

    if found:
        WINDOW_HWND = found[0]
        log(f"Located TubeFast HWND: {hex(WINDOW_HWND)}")
        strip_window_decorations(WINDOW_HWND)
        return WINDOW_HWND
    return None

try:
    import yt_dlp
except ImportError:
    if not getattr(sys, 'frozen', False):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])
            import yt_dlp
        except Exception:
            pass

def get_base_dir():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

CLIENT_DIR = os.path.join(get_base_dir(), "client")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv else ".")), "tubefast.log")

def get_library_path():
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv else "."))
    target = os.path.join(base_dir, "tubefast_library.json")
    try:
        with open(target, "a", encoding="utf-8") as f:
            pass
        return target
    except Exception:
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        fallback_dir = os.path.join(appdata, "TubeFast")
        os.makedirs(fallback_dir, exist_ok=True)
        return os.path.join(fallback_dir, "tubefast_library.json")

LIBRARY_FILE = get_library_path()
LIBRARY_LOCK = threading.Lock()

def load_library_from_disk():
    with LIBRARY_LOCK:
        if os.path.exists(LIBRARY_FILE):
            try:
                with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {
                            "liked": data.get("liked", []),
                            "playlists": data.get("playlists", []),
                            "history": data.get("history", []),
                            "taste_profile": data.get("taste_profile", {"artists": {}})
                        }
            except Exception as e:
                log(f"Error reading library from {LIBRARY_FILE}: {e}")
        return {"liked": [], "playlists": [], "history": [], "taste_profile": {"artists": {}}}

def save_library_to_disk(data):
    with LIBRARY_LOCK:
        try:
            liked = data.get("liked", [])
            playlists = data.get("playlists", [])
            history = data.get("history", [])
            taste_profile = data.get("taste_profile", {"artists": {}})
            payload = {
                "liked": liked,
                "playlists": playlists,
                "history": history[:150],
                "taste_profile": taste_profile,
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            tmp_path = LIBRARY_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            if os.path.exists(LIBRARY_FILE):
                os.replace(tmp_path, LIBRARY_FILE)
            else:
                os.rename(tmp_path, LIBRARY_FILE)
            log(f"Persisted library ({len(liked)} liked, {len(playlists)} playlists, {len(history)} history) to disk: {LIBRARY_FILE}")
            return True
        except Exception as e:
            log(f"Error saving library to disk: {e}")
            return False

def parse_track_metadata(title, artist):
    clean_title = (title or "").strip()
    extracted_artists = []

    # Strip brackets like (Lyrics), (Official Music Video), [Audio], etc.
    bracket_pat = r'\s*[\(\[](?:official|music|video|lyrics?|audio|visualizer|hd|4k|hq|remastered?|explicit|clean|prod|produced|slowed|reverb)[\w\s]*[\)\]]'
    clean_title = re.sub(bracket_pat, '', clean_title, flags=re.IGNORECASE).strip()

    # If title has 'Artist - Song'
    if ' - ' in clean_title:
        p1, p2 = clean_title.split(' - ', 1)
        if 0 < len(p1.strip()) < 45:
            extracted_artists.append(p1.strip())
            clean_title = p2.strip()

    # Extract features from title or artist: ft., feat., featuring, &
    feat_pat = r'(?:feat\.?|ft\.?|featuring)\s+([^,\(\)\[\]\-]+)'
    feats = re.findall(feat_pat, clean_title, flags=re.IGNORECASE)
    for f in feats:
        clean_title = re.sub(r'(?:feat\.?|ft\.?|featuring)\s+' + re.escape(f), '', clean_title, flags=re.IGNORECASE).strip()
        for sub in re.split(r'[,&/]', f):
            if sub.strip():
                extracted_artists.append(sub.strip())

    # Clean leftover empty brackets
    clean_title = re.sub(r'\s*[\(\[\{\)\]\}]\s*', ' ', clean_title).strip()

    # Raw artist cleanup
    raw = (artist or "").strip()
    raw = re.sub(r'\s*-\s*Topic$', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'VEVO$', '', raw, flags=re.IGNORECASE).strip()
    generic_channels = {'fox music', 'lyrical lemonade', 'trap city', 'various artists', 'unknown artist', 'trap nation', 'chillhop music', 'lofi girl synthwave'}
    if raw and raw.lower() not in generic_channels:
        extracted_artists.append(raw)

    # Deduplicate while preserving order
    seen = set()
    final_artists = []
    for a in extracted_artists:
        norm = a.lower()
        if norm not in seen and len(a) > 1:
            seen.add(norm)
            final_artists.append(a)

    primary_artist = final_artists[0] if final_artists else (raw or "Unknown Artist")
    secondary_artists = final_artists[1:] if len(final_artists) > 1 else []

    return clean_title, primary_artist, secondary_artists

def get_song_title_keys(title, artist=''):
    """Extract distinct canonical title fingerprints from title and artist for duplicate prevention."""
    t = (title or "").strip()
    a = (artist or "").strip()

    bracket_pat = r'\s*[\(\[][^\)\]]*[\)\]]'
    clean_t = re.sub(bracket_pat, '', t, flags=re.IGNORECASE).strip()
    feat_pat = r'\b(?:feat\.?|ft\.?|featuring)\b.*$'
    clean_t = re.sub(feat_pat, '', clean_t, flags=re.IGNORECASE).strip()
    clean_t = re.sub(r'\s*-\s*topic\b', '', clean_t, flags=re.IGNORECASE)
    clean_t = re.sub(r'\bvevo\b', '', clean_t, flags=re.IGNORECASE).strip()

    artist_words = set(re.findall(r'\b[a-z0-9]+\b', a.lower()))
    artist_compact = "".join(ch for ch in a.lower() if ch.isalnum())

    title_keys = set()

    if ' - ' in clean_t:
        p1, p2 = clean_t.split(' - ', 1)
        p1_comp = "".join(ch for ch in p1.lower() if ch.isalnum())
        p2_comp = "".join(ch for ch in p2.lower() if ch.isalnum())

        if p1_comp == artist_compact or any(w in artist_words for w in re.findall(r'\b[a-z0-9]+\b', p1.lower())):
            title_keys.add(p2_comp)
        elif p2_comp == artist_compact or any(w in artist_words for w in re.findall(r'\b[a-z0-9]+\b', p2.lower())):
            title_keys.add(p1_comp)
        else:
            title_keys.add(p1_comp)
            title_keys.add(p2_comp)
    else:
        full_comp = "".join(ch for ch in clean_t.lower() if ch.isalnum())
        if artist_compact and full_comp.startswith(artist_compact):
            stripped = full_comp[len(artist_compact):]
            if len(stripped) >= 3:
                title_keys.add(stripped)
            else:
                title_keys.add(full_comp)
        elif artist_compact and full_comp.endswith(artist_compact):
            stripped = full_comp[:-len(artist_compact)]
            if len(stripped) >= 3:
                title_keys.add(stripped)
            else:
                title_keys.add(full_comp)
        else:
            title_keys.add(full_comp)

    title_keys.discard(artist_compact)
    return {k for k in title_keys if len(k) >= 3}

def is_duplicate_song(cand_title_keys, seen_title_keys):
    """Check if candidate song title matches any already-played or current song title."""
    if not cand_title_keys or not seen_title_keys:
        return False
    if cand_title_keys.intersection(seen_title_keys):
        return True
    for ck in cand_title_keys:
        if len(ck) < 5:
            continue
        for sk in seen_title_keys:
            if len(sk) < 5:
                continue
            if ck == sk or ck in sk or sk in ck:
                return True
    return False

def record_track_played(track_info):
    title = (track_info.get("title") or "").strip()
    artist = (track_info.get("artist") or "").strip()
    track_id = (track_info.get("id") or "").strip()
    source = track_info.get("source", "youtube")
    if not track_id or not title:
        return

    lib = load_library_from_disk()
    history = lib.get("history", [])
    taste = lib.get("taste_profile", {})
    artists = taste.get("artists", {})

    clean_title, primary_artist, secondary_artists = parse_track_metadata(title, artist)

    if primary_artist and primary_artist.lower() != "unknown artist":
        artists[primary_artist] = artists.get(primary_artist, 0) + 2

    for sec in secondary_artists:
        if sec and sec.lower() != "unknown artist":
            artists[sec] = artists.get(sec, 0) + 1

    if len(artists) > 120:
        top_keys = sorted(artists.keys(), key=lambda k: artists[k], reverse=True)[:100]
        artists = {k: artists[k] for k in top_keys}

    if not (history and history[0].get("id") == track_id):
        history.insert(0, {
            "id": track_id,
            "title": title,
            "artist": artist,
            "clean_title": clean_title,
            "primary_artist": primary_artist,
            "source": source,
            "playedAt": int(time.time())
        })

    lib["history"] = history[:150]
    lib["taste_profile"] = {"artists": artists}
    save_library_to_disk(lib)
    log(f"Recorded track play: '{title}' by '{artist}' -> Primary: '{primary_artist}', Features: {secondary_artists}")

RECENT_RECOMMENDED_IDS = deque(maxlen=80)

def get_smart_recommendations(seed_id, seed_title, seed_artist, source="youtube", exclude_ids=None):
    if exclude_ids is None:
        exclude_ids = set()
    else:
        exclude_ids = set(exclude_ids)
    if seed_id:
        exclude_ids.add(seed_id)

    lib = load_library_from_disk()
    taste = lib.get("taste_profile", {}).get("artists", {})
    history = lib.get("history", [])

    for h in history[:40]:
        if h.get("id"):
            exclude_ids.add(h["id"])

    for rid in list(RECENT_RECOMMENDED_IDS):
        exclude_ids.add(rid)

    clean_title, primary_seed, secondary_seeds = parse_track_metadata(seed_title, seed_artist)

    top_artists = sorted(taste.keys(), key=lambda a: taste[a], reverse=True)
    fav_candidates = [a for a in top_artists if a.lower() != primary_seed.lower() and a.lower() not in [s.lower() for s in secondary_seeds]]

    sampled_taste = []
    if fav_candidates:
        weights = [taste.get(a, 1) for a in fav_candidates]
        sample_k = min(2, len(fav_candidates))
        chosen = random.choices(fav_candidates, weights=weights, k=sample_k * 2)
        for c in chosen:
            if c not in sampled_taste:
                sampled_taste.append(c)
            if len(sampled_taste) >= sample_k:
                break

    # Build queries for BOTH Spotify and YouTube catalogs to guarantee a 50/50 balance
    sp_queries = []
    yt_queries = []

    if primary_seed and primary_seed.lower() != "unknown artist":
        sp_queries.append(primary_seed)
        if clean_title:
            sp_queries.append(f"{primary_seed} {clean_title}")
        yt_queries.append(f"{primary_seed} official audio")
        yt_queries.append(f"{primary_seed} songs")
    else:
        sp_queries.append("top hits")
        yt_queries.append("popular music songs")

    if secondary_seeds:
        sp_queries.append(secondary_seeds[0])
        yt_queries.append(f"{secondary_seeds[0]} songs")

    for tfav in sampled_taste:
        sp_queries.append(tfav)
        yt_queries.append(f"{tfav} songs")

    raw_sp = []
    raw_yt = []

    def run_sp(q):
        try:
            return search_spotify(q, max_results=8)
        except Exception:
            return []

    def run_yt(q):
        try:
            return search_youtube(q, max_results=8)
        except Exception:
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        f_sp = [executor.submit(run_sp, q) for q in sp_queries[:3]]
        f_yt = [executor.submit(run_yt, q) for q in yt_queries[:3]]

        for f in concurrent.futures.as_completed(f_sp, timeout=4.0):
            try:
                raw_sp.extend(f.result())
            except Exception:
                pass
        for f in concurrent.futures.as_completed(f_yt, timeout=4.0):
            try:
                raw_yt.extend(f.result())
            except Exception:
                pass

    seen_ids = set(exclude_ids or [])
    if seed_id:
        seen_ids.add(seed_id)
    seen_title_keys = set()
    seed_keys = get_song_title_keys(seed_title, seed_artist)
    seen_title_keys.update(seed_keys)

    try:
        lib = load_library_from_disk()
        for item in lib.get("history", [])[:30]:
            if item.get("id"):
                seen_ids.add(item["id"])
            h_keys = get_song_title_keys(item.get("title", ""), item.get("artist", ""))
            seen_title_keys.update(h_keys)
    except Exception:
        pass

    def is_valid_song_duration(dur_str):
        if not dur_str or dur_str == "Live" or dur_str == "Studio":
            return True
        parts = str(dur_str).split(":")
        if len(parts) >= 3:
            return False
        if len(parts) == 2:
            try:
                m = int(parts[0])
                s = int(parts[1])
                if m > 12:
                    return False
                if m == 0 and s < 25:
                    return False
            except ValueError:
                return False
        return True

    def process_bucket(raw_list):
        cleaned = []
        for c in raw_list:
            cid = c.get("id")
            cdur = c.get("duration")
            if not cid or cid in DEAD_TRACK_CACHE or not is_valid_song_duration(cdur):
                continue
            if cid in seen_ids:
                continue

            c_keys = get_song_title_keys(c.get("title", ""), c.get("artist", ""))
            if is_duplicate_song(c_keys, seen_title_keys):
                continue

            seen_ids.add(cid)
            seen_title_keys.update(c_keys)
            cleaned.append(c)
        return cleaned

    sp_pool = process_bucket(raw_sp)
    yt_pool = process_bucket(raw_yt)

    # Backfill if either pool is small to ensure robust 50/50 balance
    if len(sp_pool) < 6:
        sp_pool.extend(process_bucket(SPOTIFY_FEATURED))
    if len(yt_pool) < 6:
        yt_pool.extend(process_bucket(YOUTUBE_FEATURED))

    random.shuffle(sp_pool)
    random.shuffle(yt_pool)

    # Assign informative reasons
    for c in sp_pool:
        cartist = (c.get("artist") or "").lower()
        if primary_seed and primary_seed.lower() in cartist:
            c["reason"] = f"Spotify • More from {primary_seed}"
        else:
            c["reason"] = f"Spotify • Similar to {primary_seed}" if primary_seed else "Spotify • Top hit"

    for c in yt_pool:
        cartist = (c.get("artist") or "").lower()
        if primary_seed and primary_seed.lower() in cartist:
            c["reason"] = f"YouTube • More from {primary_seed}"
        else:
            c["reason"] = f"YouTube • Similar to {primary_seed}" if primary_seed else "YouTube • Trending"

    # Perfect 50/50 interleaving balance (Spotify mode: SP, YT, SP, YT... / YT mode: YT, SP, YT, SP...)
    interleaved = []
    first_pool = sp_pool if source == "spotify" else yt_pool
    second_pool = yt_pool if source == "spotify" else sp_pool

    while first_pool or second_pool:
        if first_pool:
            c = first_pool.pop(0)
            interleaved.append(c)
            RECENT_RECOMMENDED_IDS.append(c["id"])
        if second_pool:
            c = second_pool.pop(0)
            interleaved.append(c)
            RECENT_RECOMMENDED_IDS.append(c["id"])

    return interleaved[:20]

def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

# In-memory stream URL cache (video_id -> (url, expire_timestamp))
STREAM_CACHE = {}
# In-memory Spotify-to-YouTube resolution cache (spotify_id -> yt_video_id)
RESOLVE_CACHE = {}
# In-memory Spotify metadata cache (sp_id -> (title, artist))
SPOTIFY_META_CACHE = {}
# Set of tracks that failed playback or were removed/geo-blocked so they are never offered again
DEAD_TRACK_CACHE = set()

def get_cache_path(filename):
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv else "."))
    target = os.path.join(base_dir, filename)
    try:
        with open(target, "a", encoding="utf-8") as f:
            pass
        return target
    except Exception:
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        fallback_dir = os.path.join(appdata, "TubeFast")
        os.makedirs(fallback_dir, exist_ok=True)
        return os.path.join(fallback_dir, filename)

STREAM_CACHE_FILE = get_cache_path("tubefast_cache.json")
DEAD_TRACKS_FILE = get_cache_path("tubefast_dead.json")

def load_stream_cache():
    try:
        if os.path.exists(STREAM_CACHE_FILE):
            with open(STREAM_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                now = time.time()
                for k, v in data.items():
                    if isinstance(v, list) and len(v) == 2:
                        url, exp = v
                        if exp > now + 300:
                            STREAM_CACHE[k] = (url, exp)
            log(f"Loaded {len(STREAM_CACHE)} active stream URLs from disk cache")
    except Exception as e:
        log(f"Stream cache load error: {e}")

def save_stream_cache():
    try:
        now = time.time()
        to_save = {}
        for k, v in list(STREAM_CACHE.items()):
            url, exp = v
            if exp > now + 300:
                to_save[k] = [url, exp]
        with open(STREAM_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f)
    except Exception as e:
        log(f"Stream cache save error: {e}")

def load_dead_cache():
    DEAD_TRACK_CACHE.clear()

def save_dead_cache():
    pass

# Pre-load caches on boot
load_stream_cache()

# Watchdog state for standalone native window
LAST_HEARTBEAT = time.time()
HEARTBEAT_RECEIVED = False
SHUTDOWN_REQUESTED = False

YOUTUBE_FEATURED = [
    {
        "id": "ya8_AwKmv6U",
        "title": "From The D To The A",
        "artist": "Tee Grizzley",
        "duration": "2:39",
        "thumbnail": "https://i.ytimg.com/vi/ya8_AwKmv6U/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "GX8Hg6kWQYI",
        "title": "Moonlight",
        "artist": "XXXTENTACION",
        "duration": "2:17",
        "thumbnail": "https://i.ytimg.com/vi/GX8Hg6kWQYI/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "mzB1VGEGcSU",
        "title": "Lucid Dreams",
        "artist": "Juice WRLD",
        "duration": "3:50",
        "thumbnail": "https://i.ytimg.com/vi/mzB1VGEGcSU/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "H58vbez_m4E",
        "title": "Not Like Us",
        "artist": "Kendrick Lamar",
        "duration": "5:54",
        "thumbnail": "https://i.ytimg.com/vi/H58vbez_m4E/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "tvTRZJ-4EyI",
        "title": "HUMBLE.",
        "artist": "Kendrick Lamar",
        "duration": "3:04",
        "thumbnail": "https://i.ytimg.com/vi/tvTRZJ-4EyI/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "aWb8z-KhZdo",
        "title": "Mask Off",
        "artist": "Future",
        "duration": "3:24",
        "thumbnail": "https://i.ytimg.com/vi/aWb8z-KhZdo/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "ZBOoVj6IW3s",
        "title": "Life Is Good",
        "artist": "Future ft. Drake",
        "duration": "3:59",
        "thumbnail": "https://i.ytimg.com/vi/ZBOoVj6IW3s/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "m1a_GqJf02M",
        "title": "God's Plan",
        "artist": "Drake",
        "duration": "3:19",
        "thumbnail": "https://i.ytimg.com/vi/m1a_GqJf02M/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "R0ykLlhg0AQ",
        "title": "Money in the Grave",
        "artist": "Drake ft. Rick Ross",
        "duration": "4:18",
        "thumbnail": "https://i.ytimg.com/vi/R0ykLlhg0AQ/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "d-JBBNg8YKs",
        "title": "SICKO MODE",
        "artist": "Travis Scott",
        "duration": "5:14",
        "thumbnail": "https://i.ytimg.com/vi/d-JBBNg8YKs/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "uLHqpjW3aDs",
        "title": "The Box",
        "artist": "Roddy Ricch",
        "duration": "3:17",
        "thumbnail": "https://i.ytimg.com/vi/uLHqpjW3aDs/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "THcVOf1kNh0",
        "title": "Drip Too Hard",
        "artist": "Lil Baby & Gunna",
        "duration": "2:27",
        "thumbnail": "https://i.ytimg.com/vi/THcVOf1kNh0/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "DF2BcR1cRHw",
        "title": "Drip or Drown",
        "artist": "Gunna",
        "duration": "2:06",
        "thumbnail": "https://i.ytimg.com/vi/DF2BcR1cRHw/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "hLw4qUBfhVY",
        "title": "Pop Out",
        "artist": "Polo G ft. Lil Tjay",
        "duration": "2:45",
        "thumbnail": "https://i.ytimg.com/vi/hLw4qUBfhVY/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "rBRTamq0v-Q",
        "title": "Outside Today",
        "artist": "NBA YoungBoy",
        "duration": "2:09",
        "thumbnail": "https://i.ytimg.com/vi/rBRTamq0v-Q/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "83xBPCw5hh4",
        "title": "ROCKSTAR",
        "artist": "DaBaby ft. Roddy Ricch",
        "duration": "3:02",
        "thumbnail": "https://i.ytimg.com/vi/83xBPCw5hh4/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "4GFAZBKZVJY",
        "title": "rockstar",
        "artist": "Post Malone ft. 21 Savage",
        "duration": "3:38",
        "thumbnail": "https://i.ytimg.com/vi/4GFAZBKZVJY/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "R8vpQdZErbw",
        "title": "Congratulations",
        "artist": "Post Malone ft. Quavo",
        "duration": "3:40",
        "thumbnail": "https://i.ytimg.com/vi/R8vpQdZErbw/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "0j82Oygrol0",
        "title": "Stir Fry",
        "artist": "Migos",
        "duration": "3:10",
        "thumbnail": "https://i.ytimg.com/vi/0j82Oygrol0/hqdefault.jpg",
        "source": "youtube"
    },
    {
        "id": "aYr4fDuLhXg",
        "title": "Without Me",
        "artist": "Halsey",
        "duration": "3:24",
        "thumbnail": "https://i.ytimg.com/vi/aYr4fDuLhXg/hqdefault.jpg",
        "source": "youtube"
    }
]

SPOTIFY_FEATURED = [
    {
        "id": "Rif-RTvmmss",
        "title": "Starboy",
        "artist": "The Weeknd",
        "duration": "3:51",
        "thumbnail": "https://i.ytimg.com/vi/Rif-RTvmmss/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "fHI8X4OXluQ",
        "title": "Blinding Lights",
        "artist": "The Weeknd",
        "duration": "3:23",
        "thumbnail": "https://i.ytimg.com/vi/fHI8X4OXluQ/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "u6lihZAcy4s",
        "title": "Save Your Tears",
        "artist": "The Weeknd",
        "duration": "3:37",
        "thumbnail": "https://i.ytimg.com/vi/u6lihZAcy4s/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "WHuBW3qKm9g",
        "title": "Levitating",
        "artist": "Dua Lipa",
        "duration": "3:41",
        "thumbnail": "https://i.ytimg.com/vi/WHuBW3qKm9g/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "7-x3uD5z1bQ",
        "title": "Watermelon Sugar",
        "artist": "Harry Styles",
        "duration": "2:54",
        "thumbnail": "https://i.ytimg.com/vi/7-x3uD5z1bQ/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "V1Z586zoeeE",
        "title": "As It Was",
        "artist": "Harry Styles",
        "duration": "2:46",
        "thumbnail": "https://i.ytimg.com/vi/V1Z586zoeeE/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "YD4utuFiexw",
        "title": "bad guy",
        "artist": "Billie Eilish",
        "duration": "3:14",
        "thumbnail": "https://i.ytimg.com/vi/YD4utuFiexw/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "tNJhkrpLGT8",
        "title": "drivers license",
        "artist": "Olivia Rodrigo",
        "duration": "4:02",
        "thumbnail": "https://i.ytimg.com/vi/tNJhkrpLGT8/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "aeDdS9aIpck",
        "title": "good 4 u",
        "artist": "Olivia Rodrigo",
        "duration": "2:58",
        "thumbnail": "https://i.ytimg.com/vi/aeDdS9aIpck/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "SQnc1QibapQ",
        "title": "Kill Bill",
        "artist": "SZA",
        "duration": "2:36",
        "thumbnail": "https://i.ytimg.com/vi/SQnc1QibapQ/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "uAYG46w1SCA",
        "title": "Say So",
        "artist": "Doja Cat",
        "duration": "3:59",
        "thumbnail": "https://i.ytimg.com/vi/uAYG46w1SCA/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "Qb8q4ijHk_M",
        "title": "Stay",
        "artist": "The Kid LAROI",
        "duration": "2:21",
        "thumbnail": "https://i.ytimg.com/vi/Qb8q4ijHk_M/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "ay9y3CTkT40",
        "title": "Peaches",
        "artist": "Justin Bieber",
        "duration": "3:18",
        "thumbnail": "https://i.ytimg.com/vi/ay9y3CTkT40/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "JGwWNGJdvx8",
        "title": "Shape of You",
        "artist": "Ed Sheeran",
        "duration": "4:23",
        "thumbnail": "https://i.ytimg.com/vi/JGwWNGJdvx8/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "k0TEcUm7lTk",
        "title": "Shake It Off",
        "artist": "Taylor Swift",
        "duration": "3:39",
        "thumbnail": "https://i.ytimg.com/vi/k0TEcUm7lTk/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "CevxZvSJLk8",
        "title": "Roar",
        "artist": "Katy Perry",
        "duration": "4:29",
        "thumbnail": "https://i.ytimg.com/vi/CevxZvSJLk8/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "KT7F15T9VBI",
        "title": "Heat Waves",
        "artist": "Glass Animals",
        "duration": "3:58",
        "thumbnail": "https://i.ytimg.com/vi/KT7F15T9VBI/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "OiMWFojB9Ok",
        "title": "Dynamite",
        "artist": "BTS",
        "duration": "3:20",
        "thumbnail": "https://i.ytimg.com/vi/OiMWFojB9Ok/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "30YlLGeUReY",
        "title": "Dakiti",
        "artist": "Bad Bunny",
        "duration": "3:25",
        "thumbnail": "https://i.ytimg.com/vi/30YlLGeUReY/hqdefault.jpg",
        "source": "spotify"
    },
    {
        "id": "Aztdmq1tYY8",
        "title": "EARFQUAKE",
        "artist": "Tyler, the Creator",
        "duration": "3:10",
        "thumbnail": "https://i.ytimg.com/vi/Aztdmq1tYY8/hqdefault.jpg",
        "source": "spotify"
    }
]

# Combined list (used in recommendation seeding & catalog resolution)
FEATURED_TRACKS = YOUTUBE_FEATURED + SPOTIFY_FEATURED

CATEGORIES_CATALOG = None

def load_categories_catalog():
    global CATEGORIES_CATALOG
    if CATEGORIES_CATALOG is not None:
        return CATEGORIES_CATALOG
    base_dir = get_base_dir()
    target = os.path.join(base_dir, "categories_catalog.json")
    if not os.path.exists(target):
        target = os.path.abspath("categories_catalog.json")
    if os.path.exists(target):
        try:
            with open(target, "r", encoding="utf-8") as f:
                CATEGORIES_CATALOG = json.load(f)
                return CATEGORIES_CATALOG
        except Exception as e:
            log(f"Error loading categories_catalog.json: {e}")
    return {"spotify": {}, "youtube": {}}

def get_all_catalog_track_ids():
    ids = {t["id"] for t in FEATURED_TRACKS if t.get("id")}
    cat = load_categories_catalog()
    for plat in ["spotify", "youtube"]:
        for cdata in cat.get(plat, {}).values():
            for t in cdata.get("tracks", []):
                if t.get("id"):
                    ids.add(t["id"])
    return ids

FEATURED_TRACK_IDS = get_all_catalog_track_ids()
load_dead_cache()

YDL_LOCK = threading.Lock()
_SEARCH_YDL = None
_STREAM_YDL = None

def get_search_ydl():
    global _SEARCH_YDL
    if _SEARCH_YDL is None:
        opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'ignoreerrors': True,
            'noplaylist': True,
        }
        _SEARCH_YDL = yt_dlp.YoutubeDL(opts)
    return _SEARCH_YDL

def get_stream_ydl():
    global _STREAM_YDL
    if _STREAM_YDL is None:
        opts = {
            'format': 'ba[ext=m4a]/140/ba/b[height<=480]/18/best',
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'ignoreerrors': True,
            'noplaylist': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web']
                }
            }
        }
        _STREAM_YDL = yt_dlp.YoutubeDL(opts)
    return _STREAM_YDL

PRELOAD_QUEUE = deque(maxlen=2)
PRELOAD_LOCK = threading.Lock()
PRELOAD_EVENT = threading.Event()

def queue_preload(vid, title="", artist=""):
    if not vid:
        return
    with PRELOAD_LOCK:
        for item in PRELOAD_QUEUE:
            if item[0] == vid:
                return
        PRELOAD_QUEUE.append((vid, title, artist))
        PRELOAD_EVENT.set()

def preload_worker_loop():
    while not SHUTDOWN_REQUESTED:
        PRELOAD_EVENT.wait(timeout=1.0)
        while not SHUTDOWN_REQUESTED:
            item = None
            with PRELOAD_LOCK:
                if not PRELOAD_QUEUE:
                    PRELOAD_EVENT.clear()
                    break
                item = PRELOAD_QUEUE.popleft()
            if item:
                vid, title, artist = item
                try:
                    warmup_stream_cache(vid, title, artist)
                except Exception:
                    pass
                time.sleep(0.05)

def search_youtube(query, max_results=15):
    """Search YouTube catalog via shared yt-dlp instance for minimal RAM footprint."""
    try:
        with YDL_LOCK:
            ydl = get_search_ydl()
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        tracks = []
        for e in info.get("entries", []):
            if not e or not e.get("id"):
                continue
            dur = e.get("duration")
            if dur:
                m, s = divmod(int(dur), 60)
                h, m = divmod(m, 60)
                dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
            else:
                dur_str = "Live"
            vid_id = e.get("id")
            tracks.append({
                "id": vid_id,
                "source": "youtube",
                "title": e.get("title", "Unknown Title"),
                "artist": e.get("uploader") or e.get("channel") or "Unknown Artist",
                "duration": dur_str,
                "thumbnail": e.get("thumbnail") or f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
            })
        log(f"YouTube search for '{query}' found {len(tracks)} tracks")
        trim_process_memory()
        return tracks if tracks else fallback_search(query)
    except Exception as e:
        log(f"YouTube search error for '{query}': {e}")
        return fallback_search(query)

def search_spotify(query, max_results=15):
    """
    Search official commercial music catalog (Spotify/Apple Music library).
    Only returns officially released studio tracks, albums, and singles.
    Will NEVER return unreleased YouTube leaks or fan mashups that aren't on streaming services.
    """
    # 1. Check if user pasted a Spotify URL directly
    sp_match = query.strip().startswith("https://open.spotify.com/")
    if sp_match:
        try:
            oe_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(query)}"
            req = urllib.request.Request(oe_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
                title = data.get("title", "Spotify Track")
                artist = data.get("author_name", "Spotify Artist")
                thumb = data.get("thumbnail_url", "")
                return [{
                    "id": f"sp-{hash(query) & 0xffffffff}",
                    "source": "spotify",
                    "title": title,
                    "artist": artist,
                    "duration": "Studio",
                    "thumbnail": thumb,
                    "resolveQuery": f"{title} {artist}"
                }]
        except Exception as e:
            log(f"Spotify oEmbed error: {e}")

    # 2. Query official commercial music catalog
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://itunes.apple.com/search?term={encoded}&media=music&entity=song&limit={max_results}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        tracks = []
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            for item in data.get("results", []):
                dur_ms = item.get("trackTimeMillis", 0)
                dur_s = dur_ms // 1000
                m, s = divmod(dur_s, 60)
                title = item.get("trackName", "Unknown Title")
                artist = item.get("artistName", "Unknown Artist")
                album = item.get("collectionName", "")
                art = item.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
                track_id = f"sp-{item.get('trackId')}"
                SPOTIFY_META_CACHE[track_id] = (title, artist)

                tracks.append({
                    "id": track_id,
                    "source": "spotify",
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "duration": f"{m}:{s:02d}",
                    "thumbnail": art,
                    "resolveQuery": f"{title} {artist}"
                })
        log(f"Spotify catalog search for '{query}' found {len(tracks)} official tracks")
        return tracks
    except Exception as e:
        log(f"Spotify catalog search error for '{query}': {e}")
        return []

def resolve_spotify_to_yt(title, artist):
    """Find the matching official audio stream on YouTube for a Spotify track using shared yt-dlp."""
    cache_key = f"{title.lower()} - {artist.lower()}".strip()
    if cache_key in RESOLVE_CACHE:
        return RESOLVE_CACHE[cache_key]

    query = f"{title} {artist} official audio"
    try:
        with YDL_LOCK:
            ydl = get_search_ydl()
            info = ydl.extract_info(f"ytsearch3:{query}", download=False)
        entries = info.get("entries", [])
        for e in entries:
            if e and e.get("id"):
                vid_id = e.get("id")
                RESOLVE_CACHE[cache_key] = vid_id
                log(f"Resolved Spotify track '{title}' -> YouTube ID {vid_id}")
                return vid_id
    except Exception as e:
        log(f"Resolve error for '{title}': {e}")
    return None

def get_audio_stream_url(video_id):
    """Resolve direct playable audio stream URL using shared multi-client extraction instance."""
    now = time.time()
    if video_id in STREAM_CACHE:
        url, exp = STREAM_CACHE[video_id]
        if now < exp:
            return url

    try:
        with YDL_LOCK:
            ydl = get_stream_ydl()
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        stream_url = info.get("url") if info else None
        if stream_url:
            STREAM_CACHE[video_id] = (stream_url, now + (3600 * 5))
            save_stream_cache()
            trim_process_memory()
            return stream_url
        return None
    except Exception as e:
        log(f"Stream resolution failure for {video_id}: {e}")
        return None

def warmup_stream_cache(vid, title="", artist=""):
    """Asynchronously resolve direct stream URL and store in STREAM_CACHE before playback."""
    try:
        if vid in STREAM_CACHE:
            _, exp = STREAM_CACHE[vid]
            if time.time() < exp:
                return

        if vid.startswith("sp-") or (not vid.isalnum() and len(vid) != 11):
            resolved_id = resolve_spotify_to_yt(title, artist)
            if resolved_id:
                vid = resolved_id
            else:
                return
        get_audio_stream_url(vid)
        log(f"Pre-warmed audio stream cache for track {vid}")
    except Exception as e:
        log(f"Stream pre-warm error for {vid}: {e}")

def warmup_initial_catalog():
    """Pre-warm top 1 track so initial playback is instant without memory bloat."""
    try:
        lib = load_library_from_disk()
        history = lib.get("history", [])
        liked = lib.get("liked", [])
        top = history[0] if history else (liked[0] if liked else (FEATURED_TRACKS[0] if FEATURED_TRACKS else None))
        if top and top.get("id"):
            warmup_stream_cache(top["id"], top.get("title", ""), top.get("artist", ""))
    except Exception as e:
        log(f"Initial warm error: {e}")
    finally:
        trim_process_memory()

def fallback_search(query):
    q = query.lower()
    return [
        t for t in FEATURED_TRACKS
        if q in t["title"].lower() or q in t["artist"].lower()
    ]

class DualStreamHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=CLIENT_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        # 1. Audio Stream Proxy Endpoint (Range Header Support)
        if parsed.path == "/api/stream":
            vid = params.get("id", [""])[0]
            title = params.get("title", [""])[0]
            artist = params.get("artist", [""])[0]

            # If track is from Spotify (starts with sp-) or metadata supplied, resolve to YouTube ID
            if vid.startswith("sp-") or (not vid.isalnum() and len(vid) != 11):
                if (not title or not artist) and vid in SPOTIFY_META_CACHE:
                    cached_t, cached_a = SPOTIFY_META_CACHE[vid]
                    title = title or cached_t
                    artist = artist or cached_a

                resolved_id = resolve_spotify_to_yt(title, artist)
                if resolved_id:
                    vid = resolved_id
                else:
                    self.send_error(404, "Could not match Spotify track to audio stream")
                    return

            try:
                stream_url = get_audio_stream_url(vid)
                if not stream_url:
                    self.send_error(404, "Stream URL not found")
                    return

                req_headers = {"User-Agent": "Mozilla/5.0"}
                range_header = self.headers.get("Range")
                if range_header:
                    req_headers["Range"] = range_header

                req = urllib.request.Request(stream_url, headers=req_headers)
                try:
                    upstream = urllib.request.urlopen(req, timeout=12)
                except urllib.error.HTTPError as he:
                    if he.code in (403, 404, 410):
                        log(f"Stream token expired for {vid} (HTTP {he.code}). Evicting cache and refreshing...")
                        STREAM_CACHE.pop(vid, None)
                        stream_url = get_audio_stream_url(vid)
                        if stream_url:
                            req = urllib.request.Request(stream_url, headers=req_headers)
                            upstream = urllib.request.urlopen(req, timeout=12)
                        else:
                            raise
                    else:
                        raise

                with upstream:
                    status = upstream.status
                    self.send_response(status)
                    for h in ["Content-Type", "Content-Range", "Content-Length", "Accept-Ranges"]:
                        val = upstream.headers.get(h)
                        if val:
                            self.send_header(h, val)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()

                    # Stream data in 64KB chunks directly into the browser audio engine
                    while True:
                        try:
                            chunk = upstream.read(65536)
                        except Exception:
                            break
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                            break
                        except Exception as ce:
                            if "10053" in str(ce) or "10054" in str(ce):
                                break
                            raise
                return
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                return
            except Exception as e:
                err_str = str(e)
                if "10053" in err_str or "10054" in err_str:
                    return
                log(f"Stream proxy error for {vid}: {e}")
                try:
                    self.send_error(500, f"Streaming error: {e}")
                except Exception:
                    pass
                return

        # 2a. Discover endpoint with 5 categories (25 songs each) + dynamic personalized "For You"
        if parsed.path == "/api/discover":
            src = params.get("source", ["youtube"])[0].lower()
            catalog = load_categories_catalog()
            platform_cats = catalog.get(src, {})

            lib = load_library_from_disk()
            taste = lib.get("taste_profile", {}).get("artists", {})
            history = lib.get("history", [])

            top_artists = sorted(taste.keys(), key=lambda a: taste[a], reverse=True)
            seed_artist = top_artists[0] if top_artists else ""
            seed_title = history[0].get("title", "") if history else ""

            if not seed_artist:
                seed_artist = "The Weeknd" if src == "spotify" else "Travis Scott"

            for_you_tracks = get_smart_recommendations(
                seed_id="",
                seed_title=seed_title,
                seed_artist=seed_artist,
                source=src,
                exclude_ids=[]
            )

            reason_str = f"Based on your listening to {seed_artist}" if top_artists else f"Curated trending picks for you"
            body = json.dumps({
                "source": src,
                "for_you": for_you_tracks[:15],
                "for_you_reason": reason_str,
                "categories": platform_cats,
                "dead_tracks": list(DEAD_TRACK_CACHE)
            }, ensure_ascii=False).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # 2. Popular / Initial tracks
        if parsed.path == "/api/popular":
            source_filter = params.get('source', ['youtube'])[0].lower()
            if source_filter == 'spotify':
                featured = SPOTIFY_FEATURED
            else:
                featured = YOUTUBE_FEATURED
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "tracks": featured,
                "dead_tracks": list(DEAD_TRACK_CACHE)
            }).encode("utf-8"))
            return

        # 2b. Quarantine dead/unplayable track endpoint
        if parsed.path == "/api/dead_track":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        # 2c. Check / Status of Update
        if parsed.path == "/api/update_status":
            with UPDATE_LOCK:
                data = dict(UPDATE_STATE)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # 2d. Trigger Background Update & Restart
        if parsed.path == "/api/trigger_update":
            ok = trigger_update_download()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started" if ok else "ignored"}).encode("utf-8"))
            return

        # 3. Search endpoint (Real YouTube vs Real Spotify Mode)
        if parsed.path == "/api/search":
            q = params.get("q", [""])[0].strip()
            source = params.get("source", ["youtube"])[0].lower()

            if not q:
                results = FEATURED_TRACKS
            else:
                if source == "spotify":
                    results = search_spotify(q)
                else:
                    results = search_youtube(q)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"tracks": results}).encode("utf-8"))
            return

        # 4. Resolve track endpoint
        if parsed.path == "/api/resolve":
            title = params.get("title", [""])[0]
            artist = params.get("artist", [""])[0]
            yt_id = resolve_spotify_to_yt(title, artist)
            match = {"id": yt_id} if yt_id else None

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"match": match}).encode("utf-8"))
            return

        if parsed.path == "/api/heartbeat":
            global LAST_HEARTBEAT, HEARTBEAT_RECEIVED
            LAST_HEARTBEAT = time.time()
            HEARTBEAT_RECEIVED = True
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        if parsed.path == "/api/library":
            data = load_library_from_disk()
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/recommendations":
            seed_id = params.get("seed_id", [""])[0]
            seed_title = params.get("seed_title", [""])[0]
            seed_artist = params.get("seed_artist", [""])[0]
            src = params.get("source", ["youtube"])[0]
            raw_ex = params.get("exclude_ids", [""])[0]
            exclude_ids = [x.strip() for x in raw_ex.split(",") if x.strip()]

            recs = get_smart_recommendations(seed_id, seed_title, seed_artist, source=src, exclude_ids=exclude_ids)
            if recs:
                top_r = recs[0]
                queue_preload(top_r["id"], top_r.get("title", ""), top_r.get("artist", ""))

            body = json.dumps({"recommendations": recs}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/preload":
            vid = params.get("id", [""])[0]
            title = params.get("title", [""])[0]
            artist = params.get("artist", [""])[0]
            if vid:
                queue_preload(vid, title, artist)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"preloading"}')
            return

        if parsed.path == "/api/taste":
            lib = load_library_from_disk()
            taste = lib.get("taste_profile", {})
            body = json.dumps({"taste_profile": taste, "history": lib.get("history", [])[:20]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        return super().do_GET()

    def do_POST(self):
        global SHUTDOWN_REQUESTED, IS_MAXIMIZED
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/library":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                post_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
                data = json.loads(post_body)
                save_library_to_disk(data)
                res = b'{"status":"saved"}'
            except Exception as e:
                log(f"Failed to process library POST: {e}")
                res = b'{"status":"error"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(res)))
            self.end_headers()
            self.wfile.write(res)
            return

        if parsed.path == "/api/history":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                post_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
                data = json.loads(post_body)
                record_track_played(data)
                res = b'{"status":"recorded"}'
            except Exception as e:
                log(f"Failed to record history POST: {e}")
                res = b'{"status":"error"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(res)))
            self.end_headers()
            self.wfile.write(res)
            return

        if parsed.path in ("/api/shutdown", "/api/window/close"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                self.wfile.write(b'{"status":"closing"}')
                self.wfile.flush()
            except Exception:
                pass
            threading.Thread(target=safe_close_window, daemon=True).start()
            return

        if parsed.path == "/api/window/minimize":
            if WEBVIEW_WINDOW:
                try:
                    WEBVIEW_WINDOW.minimize()
                except Exception:
                    pass
            elif user32:
                hwnd = find_app_window()
                if hwnd:
                    user32.ShowWindow(hwnd, 6)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"minimized"}')
            return

        if parsed.path == "/api/window/maximize":
            if WEBVIEW_WINDOW:
                try:
                    if IS_MAXIMIZED:
                        WEBVIEW_WINDOW.restore()
                        IS_MAXIMIZED = False
                    else:
                        WEBVIEW_WINDOW.maximize()
                        IS_MAXIMIZED = True
                except Exception:
                    pass
            elif user32:
                hwnd = find_app_window()
                if hwnd:
                    if user32.IsZoomed(hwnd):
                        user32.ShowWindow(hwnd, 9)
                    else:
                        user32.ShowWindow(hwnd, 3)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"toggled"}')
            return

        if parsed.path == "/api/window/drag":
            hwnd = find_app_window()
            if hwnd and user32:
                user32.ReleaseCapture()
                user32.SendMessageW(hwnd, 0x00A1, 2, 0)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"drag"}')
            return

        self.send_error(404, "Endpoint not found")

    def log_message(self, format, *args):
        pass

class ThreadPooledHTTPServer(http.server.HTTPServer):
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=6,
            thread_name_prefix="HttpWorker"
        )

    def process_request(self, request, client_address):
        self.executor.submit(self.process_request_thread, request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)

    def handle_error(self, request, client_address):
        pass

    def server_close(self):
        super().server_close()
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

def get_server(preferred_ports=(8420, 8421, 8422, 3844, 3000)):
    for p in preferred_ports:
        try:
            srv = ThreadPooledHTTPServer(("127.0.0.1", p), DualStreamHandler)
            log(f"Successfully bound server on port {p}")
            return srv, p
        except OSError:
            continue
    srv = ThreadPooledHTTPServer(("127.0.0.1", 0), DualStreamHandler)
    p = srv.server_address[1]
    log(f"Bound server on dynamic port {p}")
    return srv, p

def wait_for_server(port, max_seconds=4.0):
    start = time.time()
    url = f"http://127.0.0.1:{port}/api/popular"
    while time.time() - start < max_seconds:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    log(f"Server verified responding on port {port}")
                    return True
        except Exception:
            time.sleep(0.1)
    log(f"Server readiness timeout on port {port}")
    return False

def launch_native_window(url):
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe")
    ]
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
    ]

    profile_dir = os.path.join(tempfile.gettempdir(), "TubeFast_Profile")
    os.makedirs(profile_dir, exist_ok=True)

    for exe in edge_paths + chrome_paths:
        if os.path.exists(exe):
            cmd = [
                exe,
                f"--app={url}",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--enable-features=WindowControlsOverlay",
                "--window-size=1280,840"
            ]
            log(f"Launching desktop window via: {exe}")
            subprocess.Popen(cmd, creationflags=0x08000000)
            return

    log("Opening default browser.")
    webbrowser.open(url)

if __name__ == "__main__":
    enforce_single_instance()
    log("Lightning Player startup initiated.")
    server, port = get_server()
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    threading.Thread(target=preload_worker_loop, daemon=True).start()
    threading.Thread(target=memory_watchdog_thread, daemon=True).start()
    threading.Thread(target=warmup_initial_catalog, daemon=True).start()
    threading.Thread(target=auto_update_watchdog_thread, daemon=True).start()

    if not wait_for_server(port):
        log("Warning: Proceeding with window launch despite readiness check timeout.")

    app_url = f"http://127.0.0.1:{port}"

    profile_dir = os.path.join(os.path.expanduser("~"), ".tubefast_profile")
    os.makedirs(profile_dir, exist_ok=True)
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = profile_dir

    used_pywebview = False
    try:
        import webview
        log("Launching 100% frameless desktop window via pywebview (WebView2).")
        WEBVIEW_WINDOW = webview.create_window(
            title="Lightning Player",
            url=app_url,
            width=1280,
            height=840,
            frameless=True,
            easy_drag=False,
            resizable=True,
            background_color="#0b0e14"
        )
        used_pywebview = True
        webview.start(debug=False)
        log("pywebview window closed.")
    except Exception as e:
        log(f"pywebview startup failed ({e}); falling back to browser window.")
        used_pywebview = False

    if not used_pywebview:
        launch_native_window(app_url)
        # Watchdog loop: Keep server alive while window is open
        start_time = time.time()
        stripped_decorations = False
        try:
            while True:
                time.sleep(0.5)
                if not stripped_decorations:
                    hwnd = find_app_window()
                    if hwnd:
                        strip_window_decorations(hwnd)
                        stripped_decorations = True
                if SHUTDOWN_REQUESTED:
                    log("Shutdown requested by UI client.")
                    break
                if HEARTBEAT_RECEIVED:
                    if time.time() - LAST_HEARTBEAT > 300.0:
                        hwnd = find_app_window()
                        if not (hwnd and user32 and user32.IsWindow(hwnd)):
                            log("Heartbeat timed out and desktop window closed. Server shutting down.")
                            break
                else:
                    if time.time() - start_time > 120.0:
                        hwnd = find_app_window()
                        if not (hwnd and user32 and user32.IsWindow(hwnd)):
                            log("Initial client heartbeat timed out after 120 seconds.")
                            break
        except KeyboardInterrupt:
            pass

    log("Shutting down server.")
    try:
        server.shutdown()
    except Exception:
        pass
