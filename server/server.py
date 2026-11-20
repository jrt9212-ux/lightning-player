#!/usr/bin/env python3
"""
server/server.py - Standalone Web Server for TubeFast
Powered by native HTML5 audio streaming proxy + real-time yt-dlp metadata.
"""
import http.server
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

try:
    import yt_dlp
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])
    import yt_dlp

PORT = int(os.environ.get("PORT", 3000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR = os.path.join(os.path.dirname(BASE_DIR), "client")

STREAM_CACHE = {}
RESOLVE_CACHE = {}
SPOTIFY_META_CACHE = {}

FEATURED_TRACKS = [
    {
        "id": "ya8_AwKmv6U",
        "source": "youtube",
        "title": "From The D To The A (ft. Lil Yachty)",
        "artist": "Tee Grizzley",
        "duration": "2:39",
        "thumbnail": "https://i.ytimg.com/vi/ya8_AwKmv6U/hqdefault.jpg"
    },
    {
        "id": "34Na4j8AVgA",
        "source": "spotify",
        "title": "Starboy (feat. Daft Punk)",
        "artist": "The Weeknd, Daft Punk",
        "duration": "3:50",
        "thumbnail": "https://i.ytimg.com/vi/34Na4j8AVgA/hqdefault.jpg"
    },
    {
        "id": "rFZHOHl-L8A",
        "source": "youtube",
        "title": "lofi hip hop radio - beats to relax/study to",
        "artist": "Lofi Girl",
        "duration": "Live",
        "thumbnail": "https://i.ytimg.com/vi/rFZHOHl-L8A/hqdefault.jpg"
    },
    {
        "id": "5yx6BWlEVcY",
        "source": "youtube",
        "title": "Chillhop Essentials Summer 2024",
        "artist": "Chillhop Music",
        "duration": "2:15:40",
        "thumbnail": "https://i.ytimg.com/vi/5yx6BWlEVcY/hqdefault.jpg"
    },
    {
        "id": "4xDzrJKXOOY",
        "source": "youtube",
        "title": "Synthwave Radio - Chill synth / retro beats",
        "artist": "Lofi Girl Synthwave",
        "duration": "Live",
        "thumbnail": "https://i.ytimg.com/vi/4xDzrJKXOOY/hqdefault.jpg"
    },
    {
        "id": "CevxZvSJLk8",
        "source": "spotify",
        "title": "Roar",
        "artist": "Katy Perry",
        "duration": "4:30",
        "thumbnail": "https://i.ytimg.com/vi/CevxZvSJLk8/hqdefault.jpg"
    }
]

def search_youtube(query, max_results=15):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
        'ignoreerrors': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
            return tracks if tracks else fallback_search(query)
    except Exception as e:
        print(f"[YouTube Search] Error for '{query}': {e}")
        return fallback_search(query)

def search_spotify(query, max_results=15):
    """Search official commercial music catalog (Spotify/Apple Music library)."""
    # 1. Spotify direct URL support
    if query.strip().startswith("https://open.spotify.com/"):
        try:
            oe_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(query)}"
            req = urllib.request.Request(oe_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
                title = data.get("title", "Spotify Track")
                artist = data.get("author_name", "Spotify Artist")
                thumb = data.get("thumbnail_url", "")
                track_id = f"sp-{hash(query) & 0xffffffff}"
                SPOTIFY_META_CACHE[track_id] = (title, artist)
                return [{
                    "id": track_id,
                    "source": "spotify",
                    "title": title,
                    "artist": artist,
                    "duration": "Studio",
                    "thumbnail": thumb,
                    "resolveQuery": f"{title} {artist}"
                }]
        except Exception as e:
            print(f"[Spotify oEmbed] Error: {e}")

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
        return tracks
    except Exception as e:
        print(f"[Spotify Catalog] Search error for '{query}': {e}")
        return []

def resolve_spotify_to_yt(title, artist):
    """Find matching official audio stream on YouTube for a Spotify track."""
    cache_key = f"{title.lower()} - {artist.lower()}".strip()
    if cache_key in RESOLVE_CACHE:
        return RESOLVE_CACHE[cache_key]

    query = f"{title} {artist} official audio"
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
        'ignoreerrors': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch3:{query}", download=False)
            entries = info.get("entries", [])
            for e in entries:
                if e and e.get("id"):
                    vid_id = e.get("id")
                    RESOLVE_CACHE[cache_key] = vid_id
                    return vid_id
    except Exception as e:
        print(f"[Resolve] Error for '{title}': {e}")
    return None

def get_audio_stream_url(video_id):
    now = time.time()
    if video_id in STREAM_CACHE:
        url, exp = STREAM_CACHE[video_id]
        if now < exp:
            return url

    ydl_opts = {
        'format': '140/bestaudio[ext=m4a]/bestaudio',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'ignoreerrors': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        stream_url = info.get("url") if info else None
        if stream_url:
            STREAM_CACHE[video_id] = (stream_url, now + 3600)
        return stream_url

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
                with urllib.request.urlopen(req, timeout=12) as upstream:
                    status = upstream.status
                    self.send_response(status)
                    for h in ["Content-Type", "Content-Range", "Content-Length", "Accept-Ranges"]:
                        val = upstream.headers.get(h)
                        if val:
                            self.send_header(h, val)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()

                    while True:
                        chunk = upstream.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                return
            except Exception as e:
                try:
                    self.send_error(500, f"Streaming error: {e}")
                except Exception:
                    pass
                return

        if parsed.path == "/api/popular":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"tracks": FEATURED_TRACKS}).encode("utf-8"))
            return

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

        return super().do_GET()

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    with ThreadingHTTPServer(("", PORT), DualStreamHandler) as httpd:
        print(f"[TubeFast Web Player] Server online at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
