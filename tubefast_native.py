#!/usr/bin/env python3
"""
TubeFast Native — Native desktop music player
Streams YouTube audio via yt-dlp + pygame, native tkinter GUI, no browser required.
"""

import io
import os
import queue
import sys
import tempfile
import threading
import time
import tkinter as tk
import tkinter.ttk as ttk
import urllib.request
import urllib.parse
from tkinter import font as tkfont

try:
    import pygame
    import yt_dlp
    from PIL import Image, ImageTk, ImageDraw
    import requests
except ImportError as e:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "pygame", "pillow", "requests", "-q"])
    import pygame
    import yt_dlp
    from PIL import Image, ImageTk, ImageDraw
    import requests

# ============================================================
# AUDIO ENGINE
# ============================================================
class AudioEngine:
    def __init__(self):
        pygame.mixer.pre_init(frequency=48000, size=-16, channels=2, buffer=4096)
        pygame.mixer.init()
        self.current_tmp = None
        self.duration = 0
        self._pos_start = 0
        self._paused_at = 0
        self._playing = False
        self._paused = False
        self._lock = threading.Lock()

    def load_and_play(self, stream_url, ext="webm"):
        """Download audio stream to temp file and play."""
        with self._lock:
            if self.current_tmp and os.path.exists(self.current_tmp):
                try:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    os.unlink(self.current_tmp)
                except Exception:
                    pass

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Range": "bytes=0-",
            }
            req = urllib.request.Request(stream_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()

            tmp = tempfile.NamedTemporaryFile(suffix="." + ext, delete=False)
            tmp.write(data)
            tmp.close()

            with self._lock:
                self.current_tmp = tmp.name

            pygame.mixer.music.load(tmp.name)
            pygame.mixer.music.set_volume(0.8)
            pygame.mixer.music.play()
            self._pos_start = time.time()
            self._paused_at = 0
            self._playing = True
            self._paused = False
            return True
        except Exception as e:
            print(f"[AudioEngine] load_and_play error: {e}")
            return False

    def play(self):
        if self._paused:
            pygame.mixer.music.unpause()
            self._pos_start = time.time() - self._paused_at
            self._paused = False
            self._playing = True

    def pause(self):
        if self._playing and not self._paused:
            pygame.mixer.music.pause()
            self._paused_at = time.time() - self._pos_start
            self._paused = True
            self._playing = False

    def stop(self):
        pygame.mixer.music.stop()
        self._playing = False
        self._paused = False

    def seek(self, seconds):
        """Seek to position (approximate via restart with offset - limited by pygame)."""
        try:
            pygame.mixer.music.set_pos(seconds)
            self._pos_start = time.time() - seconds
            self._paused_at = 0
        except Exception:
            pass

    def set_volume(self, vol):
        """vol: 0.0 to 1.0"""
        pygame.mixer.music.set_volume(max(0.0, min(1.0, vol)))

    def get_pos_seconds(self):
        if self._paused:
            return self._paused_at
        if self._playing:
            return time.time() - self._pos_start
        return 0.0

    def is_busy(self):
        return pygame.mixer.music.get_busy()

    def cleanup(self):
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass
        if self.current_tmp and os.path.exists(self.current_tmp):
            try:
                os.unlink(self.current_tmp)
            except Exception:
                pass


# ============================================================
# YOUTUBE SEARCH + STREAM RESOLVER
# ============================================================
class YouTubeBackend:
    YDL_SEARCH_OPTS = {
        "format": "bestaudio[acodec^=opus]/bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio",
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "extract_flat": True,
        "skip_download": True,
    }

    YDL_STREAM_OPTS = {
        "format": "bestaudio[acodec^=opus]/bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio",
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }

    def search(self, query, max_results=20):
        opts = dict(self.YDL_SEARCH_OPTS)
        opts["extract_flat"] = True
        results = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
                for entry in info.get("entries", []):
                    if not entry:
                        continue
                    vid_id = entry.get("id", "")
                    results.append({
                        "id": vid_id,
                        "title": entry.get("title", "Unknown"),
                        "artist": entry.get("uploader", entry.get("channel", "")),
                        "duration": self._fmt_duration(entry.get("duration", 0)),
                        "duration_s": int(entry.get("duration") or 0),
                        "thumbnail": entry.get("thumbnail") or f"https://i.ytimg.com/vi/{vid_id}/mqdefault.jpg",
                        "source": "youtube",
                    })
        except Exception as e:
            print(f"[Search] Error: {e}")
        return results

    def get_stream_url(self, video_id):
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            with yt_dlp.YoutubeDL(self.YDL_STREAM_OPTS) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None, None, 0
                stream_url = info.get("url", "")
                ext = info.get("ext", "webm")
                duration = int(info.get("duration") or 0)
                return stream_url, ext, duration
        except Exception as e:
            print(f"[Stream] Error: {e}")
            return None, None, 0

    @staticmethod
    def _fmt_duration(seconds):
        if not seconds:
            return "Live"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def fetch_thumbnail(self, url, size=(52, 52)):
        """Fetch and return a PIL Image thumbnail."""
        try:
            resp = requests.get(url, timeout=5)
            img = Image.open(io.BytesIO(resp.content))
            img = img.convert("RGB")
            img = img.resize(size, Image.LANCZOS)
            return img
        except Exception:
            return self._placeholder_thumb(size)

    @staticmethod
    def _placeholder_thumb(size=(52, 52)):
        img = Image.new("RGB", size, "#1c1f2c")
        draw = ImageDraw.Draw(img)
        cx, cy = size[0] // 2, size[1] // 2
        pts = [(cx - 8, cy - 10), (cx + 10, cy), (cx - 8, cy + 10)]
        draw.polygon(pts, fill="#38bdf8")
        return img


# ============================================================
# COLOURS + FONTS
# ============================================================
BG      = "#0c0d11"
SURFACE = "#14161f"
CARD    = "#1c1f2c"
CARD_H  = "#262a3d"
BORDER  = "#1f2235"
TEXT    = "#f3f4f6"
MUTED   = "#9ca3af"
DIM     = "#6b7280"
CYAN    = "#38bdf8"
YT_RED  = "#ff334b"
SP_GRN  = "#1ed760"
WHITE   = "#ffffff"


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def blend_color(c1, c2, t):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# ============================================================
# NATIVE APP WINDOW
# ============================================================
class TubeFastApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TubeFast")
        self.geometry("1200x740")
        self.minsize(900, 600)
        self.configure(bg=BG)
        self.iconbitmap(default="")

        # State
        self.backend = YouTubeBackend()
        self.engine = AudioEngine()
        self.track_queue = []
        self.queue_index = -1
        self.current_track = None
        self.is_playing = False
        self.is_shuffling = False
        self.is_looping = False
        self.volume = 0.8
        self.duration_s = 0
        self.active_source = tk.StringVar(value="youtube")
        self._search_job = None
        self._thumb_cache = {}
        self._thumb_refs = []
        self._track_frames = []
        self._worker_q = queue.Queue()

        self._build_ui()
        self._start_ticker()
        self._start_worker()
        self.after(300, lambda: self._load_popular())

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------------------------------------------
    # UI BUILD
    # ----------------------------------------------------------
    def _build_ui(self):
        self._setup_styles()
        # Layout: header | body | player_bar
        self._build_header()
        self._build_body()
        self._build_player_bar()

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TScrollbar",
            background=CARD, troughcolor=SURFACE, bordercolor=SURFACE,
            arrowcolor=MUTED, relief="flat", borderwidth=0)
        style.map("TScrollbar", background=[("active", CARD_H)])

    def _build_header(self):
        hdr = tk.Frame(self, bg=SURFACE, height=68)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        inner = tk.Frame(hdr, bg=SURFACE)
        inner.pack(fill="both", expand=True, padx=20, pady=0)

        # Brand
        brand = tk.Frame(inner, bg=SURFACE)
        brand.pack(side="left")
        logo_bg = tk.Frame(brand, bg="#38bdf8", width=36, height=36)
        logo_bg.pack(side="left", pady=16)
        logo_bg.pack_propagate(False)
        tk.Label(logo_bg, text="▶", bg="#38bdf8", fg=WHITE, font=("Arial", 14, "bold")).place(relx=0.5, rely=0.5, anchor="center")
        name_f = tk.Frame(brand, bg=SURFACE)
        name_f.pack(side="left", padx=(8, 0), pady=16)
        tk.Label(name_f, text="TubeFast", bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(name_f, text=" NATIVE", bg=SURFACE, fg=CYAN,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(4, 0))

        # Source picker + search
        search_zone = tk.Frame(inner, bg=SURFACE)
        search_zone.pack(side="left", fill="x", expand=True, padx=24)

        # Source picker buttons
        picker_frame = tk.Frame(search_zone, bg=CARD, bd=0)
        picker_frame.pack(side="left", pady=16)

        self._yt_btn = self._source_button(picker_frame, "▶  YouTube", "youtube")
        self._yt_btn.pack(side="left", padx=(4, 2), pady=4)
        self._sp_btn = self._source_button(picker_frame, "♪  Spotify", "spotify")
        self._sp_btn.pack(side="left", padx=(2, 4), pady=4)

        # Search input
        search_inp = tk.Frame(search_zone, bg=CARD, bd=1, relief="flat",
                              highlightbackground=BORDER, highlightthickness=1)
        search_inp.pack(side="left", fill="x", expand=True, padx=(10, 0), pady=14)

        tk.Label(search_inp, text="🔍", bg=CARD, fg=DIM,
                 font=("Segoe UI", 12)).pack(side="left", padx=(10, 4))

        self.search_var = tk.StringVar()
        self._search_entry = tk.Entry(
            search_inp, textvariable=self.search_var,
            bg=CARD, fg=TEXT, insertbackground=TEXT,
            font=("Segoe UI", 11), bd=0, relief="flat",
            highlightthickness=0
        )
        self._search_entry.pack(side="left", fill="both", expand=True, ipady=8)
        self._search_entry.bind("<Return>", lambda e: self._on_search())
        self._search_entry.bind("<KeyRelease>", self._on_search_typed)

        self._clear_btn = tk.Label(search_inp, text="✕", bg=CARD, fg=DIM,
                                   font=("Segoe UI", 13), cursor="hand2")
        self._clear_btn.pack(side="right", padx=8)
        self._clear_btn.bind("<Button-1>", lambda e: self._clear_search())

        search_btn = tk.Label(
            search_zone, text="  Search  ", bg=CARD_H, fg=TEXT,
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=0, pady=0, relief="flat"
        )
        search_btn.pack(side="left", padx=(8, 0), pady=14, ipadx=4, ipady=6)
        search_btn.bind("<Button-1>", lambda e: self._on_search())

        # Status
        self._status_lbl = tk.Label(inner, text="● Ready", bg=SURFACE, fg=SP_GRN,
                                    font=("Segoe UI", 9))
        self._status_lbl.pack(side="right", padx=(0, 8))

        # Separator line under header
        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x", side="top")

        self._update_source_buttons()

    def _source_button(self, parent, text, source):
        btn = tk.Label(
            parent, text=text, bg=CARD, fg=MUTED,
            font=("Segoe UI", 10, "bold"), padx=12, pady=5,
            cursor="hand2", relief="flat"
        )
        btn.bind("<Button-1>", lambda e, s=source: self._set_source(s))
        btn.bind("<Enter>", lambda e, b=btn: b.configure(fg=TEXT) if self.active_source.get() != b.cget("text").split()[-1].lower() else None)
        btn.bind("<Leave>", lambda e: self._update_source_buttons())
        return btn

    def _set_source(self, source):
        self.active_source.set(source)
        self._update_source_buttons()
        q = self.search_var.get().strip()
        if q:
            self._on_search()

    def _update_source_buttons(self):
        src = self.active_source.get()
        if src == "youtube":
            self._yt_btn.configure(bg=YT_RED, fg=WHITE)
            self._sp_btn.configure(bg=CARD, fg=MUTED)
        else:
            self._yt_btn.configure(bg=CARD, fg=MUTED)
            self._sp_btn.configure(bg=SP_GRN, fg="#0b0e14")

    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # Sidebar
        sidebar = tk.Frame(body, bg=SURFACE, width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(body, bg=BORDER, width=1).pack(side="left", fill="y")

        # Nav
        nav_title = tk.Label(sidebar, text="LIBRARY", bg=SURFACE, fg=DIM,
                             font=("Segoe UI", 8, "bold"), padx=16, pady=6)
        nav_title.pack(fill="x", pady=(14, 2))

        self._nav_btns = {}
        for label, tab in [("🧭  Discover", "discover"), ("☰  Queue", "queue")]:
            btn = tk.Label(sidebar, text=label, bg=SURFACE, fg=MUTED,
                           font=("Segoe UI", 10), padx=16, pady=10, cursor="hand2",
                           anchor="w")
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, t=tab: self._switch_tab(t))
            self._nav_btns[tab] = btn

        tk.Label(sidebar, text="STREAM ROUTING", bg=SURFACE, fg=DIM,
                 font=("Segoe UI", 8, "bold"), padx=16, pady=6).pack(fill="x", pady=(14, 2))

        routing = tk.Frame(sidebar, bg=CARD, bd=0)
        routing.pack(fill="x", padx=12, pady=4)
        tk.Label(routing, text="Smart Bridge", bg=CARD, fg=CYAN,
                 font=("Segoe UI", 9, "bold"), padx=10, pady=8).pack(anchor="w")
        tk.Label(routing, text="Spotify searches resolve\naudio via YouTube stream.",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 8), padx=10, pady=8,
                 justify="left", wraplength=180).pack(anchor="w")

        # Main content
        self._content_frame = tk.Frame(body, bg=BG)
        self._content_frame.pack(fill="both", expand=True)

        # View title
        title_bar = tk.Frame(self._content_frame, bg=BG)
        title_bar.pack(fill="x", padx=28, pady=(20, 10))

        self._view_title = tk.Label(title_bar, text="Discover Tracks",
                                    bg=BG, fg=TEXT, font=("Segoe UI", 18, "bold"))
        self._view_title.pack(side="left")
        self._view_sub = tk.Label(title_bar, text="Browse popular picks or search above.",
                                  bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self._view_sub.pack(side="left", padx=(12, 0), pady=(4, 0))

        # Scrollable track list
        list_wrapper = tk.Frame(self._content_frame, bg=BG)
        list_wrapper.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        canvas = tk.Canvas(list_wrapper, bg=BG, bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_wrapper, orient="vertical", command=canvas.yview)
        self._track_scroll_frame = tk.Frame(canvas, bg=BG)
        self._track_scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self._track_scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._switch_tab("discover")

    def _switch_tab(self, tab):
        self._active_tab = tab
        for t, btn in self._nav_btns.items():
            if t == tab:
                btn.configure(bg=CARD, fg=TEXT, font=("Segoe UI", 10, "bold"))
            else:
                btn.configure(bg=SURFACE, fg=MUTED, font=("Segoe UI", 10))

        if tab == "queue":
            self._view_title.configure(text="Current Queue")
            self._view_sub.configure(text=f"{len(self.track_queue)} tracks")
            self._render_track_list(self.track_queue, is_queue=True)
        else:
            self._view_title.configure(text="Discover Tracks")
            self._view_sub.configure(text="Browse popular picks or search above.")

    def _build_player_bar(self):
        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x", side="bottom")

        bar = tk.Frame(self, bg=SURFACE, height=88)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        inner = tk.Frame(bar, bg=SURFACE)
        inner.pack(fill="both", expand=True, padx=16)

        # LEFT: cover + meta
        left = tk.Frame(inner, bg=SURFACE, width=280)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        self._cover_lbl = tk.Label(left, bg=SURFACE)
        self._cover_lbl.pack(side="left", pady=16, padx=(4, 10))
        self._set_placeholder_cover()

        meta_f = tk.Frame(left, bg=SURFACE)
        meta_f.pack(side="left", fill="y", pady=16)
        self._track_name_lbl = tk.Label(meta_f, text="Select a track", bg=SURFACE, fg=TEXT,
                                        font=("Segoe UI", 10, "bold"), anchor="w")
        self._track_name_lbl.pack(anchor="w")
        self._track_artist_lbl = tk.Label(meta_f, text="TubeFast Native", bg=SURFACE, fg=MUTED,
                                          font=("Segoe UI", 9), anchor="w")
        self._track_artist_lbl.pack(anchor="w")
        self._source_lbl = tk.Label(meta_f, text="YT", bg=SURFACE, fg=YT_RED,
                                    font=("Segoe UI", 8, "bold"))
        self._source_lbl.pack(anchor="w", pady=(2, 0))

        # CENTER: controls + scrubber
        center = tk.Frame(inner, bg=SURFACE)
        center.pack(side="left", fill="both", expand=True, pady=8)

        # Buttons row
        btn_row = tk.Frame(center, bg=SURFACE)
        btn_row.pack(pady=(10, 4))

        self._shuffle_btn = self._ctrl_btn(btn_row, "⇄", self._toggle_shuffle, 20)
        self._prev_btn   = self._ctrl_btn(btn_row, "⏮", self._prev_track, 24)
        self._play_btn   = self._ctrl_btn(btn_row, "▶", self._toggle_play, 36, primary=True)
        self._next_btn   = self._ctrl_btn(btn_row, "⏭", self._next_track, 24)
        self._loop_btn   = self._ctrl_btn(btn_row, "↻", self._toggle_loop, 20)

        for b in [self._shuffle_btn, self._prev_btn, self._play_btn, self._next_btn, self._loop_btn]:
            b.pack(side="left", padx=6)

        # Scrubber row
        scrub_row = tk.Frame(center, bg=SURFACE)
        scrub_row.pack(fill="x", padx=20)

        self._cur_lbl = tk.Label(scrub_row, text="0:00", bg=SURFACE, fg=DIM,
                                 font=("Segoe UI", 8), width=4)
        self._cur_lbl.pack(side="left")

        self._progress = ttk.Scale(scrub_row, orient="horizontal", from_=0, to=100)
        self._progress.pack(side="left", fill="x", expand=True, padx=6)
        self._progress.bind("<ButtonPress-1>", self._scrub_press)
        self._progress.bind("<ButtonRelease-1>", self._scrub_release)
        self._scrubbing = False

        self._dur_lbl = tk.Label(scrub_row, text="0:00", bg=SURFACE, fg=DIM,
                                 font=("Segoe UI", 8), width=4)
        self._dur_lbl.pack(side="right")

        # RIGHT: volume + pipeline
        right = tk.Frame(inner, bg=SURFACE, width=240)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._pipeline_lbl = tk.Label(right, text="Idle", bg=CARD, fg=DIM,
                                      font=("Segoe UI", 8), padx=8, pady=3)
        self._pipeline_lbl.pack(anchor="e", pady=(20, 4), padx=8)

        vol_row = tk.Frame(right, bg=SURFACE)
        vol_row.pack(anchor="e", padx=8)

        mute_btn = tk.Label(vol_row, text="🔊", bg=SURFACE, fg=MUTED,
                            font=("Segoe UI", 13), cursor="hand2")
        mute_btn.pack(side="left")
        mute_btn.bind("<Button-1>", self._toggle_mute)
        self._muted = False
        self._prev_vol = self.volume

        self._vol_scale = ttk.Scale(vol_row, orient="horizontal", from_=0, to=100,
                                    value=int(self.volume * 100), length=100)
        self._vol_scale.pack(side="left", padx=(6, 0))
        self._vol_scale.bind("<Motion>", self._on_volume_change)
        self._vol_scale.bind("<ButtonRelease-1>", self._on_volume_change)

    def _ctrl_btn(self, parent, text, cmd, size, primary=False):
        if primary:
            btn = tk.Label(parent, text=text, bg=WHITE, fg="#0c0d11",
                           font=("Segoe UI", 16, "bold"),
                           width=2, height=1, cursor="hand2",
                           relief="flat", padx=4, pady=2)
        else:
            btn = tk.Label(parent, text=text, bg=SURFACE, fg=MUTED,
                           font=("Segoe UI", size), cursor="hand2",
                           relief="flat")
        btn.bind("<Button-1>", lambda e: cmd())
        btn.bind("<Enter>", lambda e: btn.configure(fg=TEXT if not primary else "#0c0d11"))
        btn.bind("<Leave>", lambda e: btn.configure(fg=DIM if not primary else "#0c0d11"))
        return btn

    def _set_placeholder_cover(self):
        img = Image.new("RGB", (56, 56), CARD)
        draw = ImageDraw.Draw(img)
        cx, cy = 28, 28
        draw.polygon([(cx - 10, cy - 13), (cx + 14, cy), (cx - 10, cy + 13)], fill=CYAN)
        tk_img = ImageTk.PhotoImage(img)
        self._cover_lbl.configure(image=tk_img)
        self._cover_img = tk_img

    # ----------------------------------------------------------
    # TRACK LIST RENDERING
    # ----------------------------------------------------------
    def _render_track_list(self, tracks, is_queue=False):
        for w in self._track_scroll_frame.winfo_children():
            w.destroy()
        self._thumb_refs.clear()
        self._track_frames.clear()

        if not tracks:
            msg = "Your queue is empty." if is_queue else "No tracks found."
            tk.Label(self._track_scroll_frame, text=msg, bg=BG, fg=DIM,
                     font=("Segoe UI", 10), pady=48).pack()
            return

        # Column header
        hdr = tk.Frame(self._track_scroll_frame, bg=BG)
        hdr.pack(fill="x", padx=8, pady=(4, 2))
        tk.Label(hdr, text="#", bg=BG, fg=DIM, font=("Segoe UI", 9), width=3, anchor="w").pack(side="left")
        tk.Label(hdr, text="TITLE", bg=BG, fg=DIM, font=("Segoe UI", 9), width=38, anchor="w").pack(side="left", padx=(64, 0))
        tk.Label(hdr, text="SOURCE", bg=BG, fg=DIM, font=("Segoe UI", 9), width=10, anchor="w").pack(side="left")
        tk.Label(hdr, text="DURATION", bg=BG, fg=DIM, font=("Segoe UI", 9), width=10, anchor="e").pack(side="right", padx=8)

        for i, track in enumerate(tracks):
            self._build_track_row(i, track)

    def _build_track_row(self, index, track):
        is_current = (self.current_track and self.current_track.get("id") == track.get("id"))

        row = tk.Frame(self._track_scroll_frame, bg=CARD if not is_current else blend_color(CARD, CYAN, 0.08),
                       cursor="hand2")
        row.pack(fill="x", padx=8, pady=2)
        self._track_frames.append(row)

        # Hover effects
        row_bg = CARD if not is_current else blend_color(CARD, CYAN, 0.08)
        hover_bg = CARD_H

        def on_enter(e, r=row, hb=hover_bg):
            for child in r.winfo_children():
                try:
                    child.configure(bg=hb)
                except Exception:
                    pass
            r.configure(bg=hb)

        def on_leave(e, r=row, rb=row_bg):
            for child in r.winfo_children():
                try:
                    child.configure(bg=rb)
                except Exception:
                    pass
            r.configure(bg=rb)

        row.bind("<Enter>", on_enter)
        row.bind("<Leave>", on_leave)
        row.bind("<Button-1>", lambda e, t=track: self._play_now(t))

        # Row number
        num_lbl = tk.Label(row, text=str(index + 1), bg=CARD, fg=DIM,
                           font=("Segoe UI", 9), width=3, anchor="w", padx=8)
        num_lbl.pack(side="left", pady=8)
        num_lbl.bind("<Enter>", on_enter)
        num_lbl.bind("<Leave>", on_leave)
        num_lbl.bind("<Button-1>", lambda e, t=track: self._play_now(t))

        # Thumbnail placeholder
        thumb_lbl = tk.Label(row, bg=CARD, width=52, height=52)
        thumb_lbl.pack(side="left", padx=(0, 10), pady=4)

        # Queue thumbnail loading
        def load_thumb(lbl=thumb_lbl, url=track.get("thumbnail", ""), rb=row_bg):
            tid = track.get("id", "")
            if tid in self._thumb_cache:
                tk_img = self._thumb_cache[tid]
            else:
                try:
                    img = self.backend.fetch_thumbnail(url, (52, 52))
                    tk_img = ImageTk.PhotoImage(img)
                    self._thumb_cache[tid] = tk_img
                except Exception:
                    img = self.backend._placeholder_thumb()
                    tk_img = ImageTk.PhotoImage(img)
            self._thumb_refs.append(tk_img)
            try:
                lbl.configure(image=tk_img)
            except tk.TclError:
                pass

        threading.Thread(target=load_thumb, daemon=True).start()

        # Track info
        info_f = tk.Frame(row, bg=CARD)
        info_f.pack(side="left", fill="x", expand=True, pady=8)
        info_f.bind("<Enter>", on_enter)
        info_f.bind("<Leave>", on_leave)
        info_f.bind("<Button-1>", lambda e, t=track: self._play_now(t))

        title_text = track.get("title", "Unknown")[:60]
        tk.Label(info_f, text=title_text, bg=CARD, fg=TEXT,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(anchor="w")
        tk.Label(info_f, text=track.get("artist", "")[:50], bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").pack(anchor="w")

        # Source badge
        src = track.get("source", "youtube")
        src_color = YT_RED if src == "youtube" else SP_GRN
        src_text = "YOUTUBE" if src == "youtube" else "SPOTIFY"
        src_lbl = tk.Label(row, text=src_text, bg=CARD, fg=src_color,
                           font=("Segoe UI", 8, "bold"), width=9, anchor="w")
        src_lbl.pack(side="left", padx=(0, 8))

        # Duration
        dur_lbl = tk.Label(row, text=track.get("duration", "--:--"), bg=CARD, fg=DIM,
                           font=("Segoe UI", 9), width=8, anchor="e", padx=10)
        dur_lbl.pack(side="right")
        dur_lbl.bind("<Enter>", on_enter)
        dur_lbl.bind("<Leave>", on_leave)

        # + Queue button
        q_lbl = tk.Label(row, text=" + ", bg=CARD, fg=DIM, font=("Segoe UI", 13),
                         cursor="hand2", padx=4)
        q_lbl.pack(side="right", padx=(0, 4))
        q_lbl.bind("<Button-1>", lambda e, t=track: self._add_to_queue(t))
        q_lbl.bind("<Enter>", lambda e: q_lbl.configure(fg=CYAN))
        q_lbl.bind("<Leave>", lambda e: q_lbl.configure(fg=DIM))

    def _show_loading(self, msg="Loading..."):
        for w in self._track_scroll_frame.winfo_children():
            w.destroy()
        tk.Label(self._track_scroll_frame, text=msg, bg=BG, fg=MUTED,
                 font=("Segoe UI", 10), pady=60).pack()

    # ----------------------------------------------------------
    # SEARCH
    # ----------------------------------------------------------
    def _on_search_typed(self, event=None):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(600, self._on_search)

    def _on_search(self, event=None):
        query = self.search_var.get().strip()
        if not query:
            self._load_popular()
            return

        self._view_title.configure(text=f'Search: "{query}"')
        src = self.active_source.get()
        self._view_sub.configure(text=f"Routing via {src.upper()}")
        self._show_loading(f"Searching {src.upper()} for '{query}'...")
        self._status_lbl.configure(text="⏳ Searching...", fg=CYAN)

        def do_search():
            if src == "spotify":
                results = self.backend.search(f"{query} official audio")
                for r in results:
                    r["source"] = "spotify"
            else:
                results = self.backend.search(query)
            self.after(0, lambda: self._render_track_list(results))
            self.after(0, lambda: self._status_lbl.configure(text="● Ready", fg=SP_GRN))

        threading.Thread(target=do_search, daemon=True).start()

    def _clear_search(self):
        self.search_var.set("")
        self._load_popular()

    def _load_popular(self):
        self._view_title.configure(text="Discover Tracks")
        self._view_sub.configure(text="Browse popular picks or search above.")
        self._show_loading("Loading featured tracks...")
        self._status_lbl.configure(text="⏳ Loading...", fg=CYAN)

        def fetch():
            results = self.backend.search("lofi hip hop beats music 2024")
            self.after(0, lambda: self._render_track_list(results))
            self.after(0, lambda: self._status_lbl.configure(text="● Ready", fg=SP_GRN))

        threading.Thread(target=fetch, daemon=True).start()

    # ----------------------------------------------------------
    # PLAYBACK
    # ----------------------------------------------------------
    def _play_now(self, track):
        self.current_track = track
        self._update_now_playing_meta(track)
        self._status_lbl.configure(text="⏳ Resolving stream...", fg=CYAN)
        self._pipeline_lbl.configure(text="Fetching stream...")
        self.is_playing = False
        self._play_btn.configure(text="▶")

        def resolve_and_play():
            vid_id = track.get("id", "")
            stream_url, ext, duration = self.backend.get_stream_url(vid_id)
            if not stream_url:
                self.after(0, lambda: self._status_lbl.configure(text="⚠ Stream unavailable", fg=YT_RED))
                return
            self.duration_s = duration
            fmt_dur = YouTubeBackend._fmt_duration(duration)
            self.after(0, lambda: self._dur_lbl.configure(text=fmt_dur))
            self.after(0, lambda: self._pipeline_lbl.configure(text="Downloading..."))

            ok = self.engine.load_and_play(stream_url, ext)
            if ok:
                self.is_playing = True
                self.after(0, lambda: self._play_btn.configure(text="⏸"))
                self.after(0, lambda: self._pipeline_lbl.configure(
                    text="YT Audio" if track.get("source") == "youtube" else "Spotify → YT Bridge"))
                self.after(0, lambda: self._status_lbl.configure(text="▶ Playing", fg=SP_GRN))
                # Update cover art from track thumbnail
                thumb_url = track.get("thumbnail", "")
                try:
                    img = self.backend.fetch_thumbnail(thumb_url, (56, 56))
                    tk_img = ImageTk.PhotoImage(img)
                    self.after(0, lambda i=tk_img: self._update_cover(i))
                except Exception:
                    pass
            else:
                self.after(0, lambda: self._status_lbl.configure(text="⚠ Playback error", fg=YT_RED))

        threading.Thread(target=resolve_and_play, daemon=True).start()

    def _update_now_playing_meta(self, track):
        title = track.get("title", "Unknown")[:55]
        artist = track.get("artist", "")[:40]
        src = track.get("source", "youtube")
        self._track_name_lbl.configure(text=title)
        self._track_artist_lbl.configure(text=artist)
        self._source_lbl.configure(
            text="YT" if src == "youtube" else "SP",
            fg=YT_RED if src == "youtube" else SP_GRN
        )

    def _update_cover(self, tk_img):
        self._cover_lbl.configure(image=tk_img)
        self._cover_img = tk_img

    def _toggle_play(self):
        if self.current_track is None:
            return
        if self.is_playing:
            self.engine.pause()
            self.is_playing = False
            self._play_btn.configure(text="▶")
        else:
            self.engine.play()
            self.is_playing = True
            self._play_btn.configure(text="⏸")

    def _next_track(self):
        if not self.track_queue:
            return
        if self.is_shuffling:
            import random
            self.queue_index = random.randint(0, len(self.track_queue) - 1)
        else:
            self.queue_index = (self.queue_index + 1) % len(self.track_queue)
        self._play_now(self.track_queue[self.queue_index])

    def _prev_track(self):
        if not self.track_queue:
            return
        self.queue_index = (self.queue_index - 1) % len(self.track_queue)
        self._play_now(self.track_queue[self.queue_index])

    def _toggle_shuffle(self):
        self.is_shuffling = not self.is_shuffling
        self._shuffle_btn.configure(fg=CYAN if self.is_shuffling else DIM)

    def _toggle_loop(self):
        self.is_looping = not self.is_looping
        self._loop_btn.configure(fg=CYAN if self.is_looping else DIM)

    def _add_to_queue(self, track):
        self.track_queue.append(track)
        if self.queue_index == -1:
            self.queue_index = 0
        # Update queue badge in nav
        nav_btn = self._nav_btns.get("queue")
        if nav_btn:
            nav_btn.configure(text=f"☰  Queue ({len(self.track_queue)})")

    # ----------------------------------------------------------
    # SCRUBBER
    # ----------------------------------------------------------
    def _scrub_press(self, event):
        self._scrubbing = True

    def _scrub_release(self, event):
        val = self._progress.get()
        if self.duration_s > 0:
            target = (val / 100) * self.duration_s
            self.engine.seek(target)
        self._scrubbing = False

    # ----------------------------------------------------------
    # VOLUME
    # ----------------------------------------------------------
    def _on_volume_change(self, event=None):
        val = self._vol_scale.get() / 100.0
        self.volume = val
        self.engine.set_volume(val)

    def _toggle_mute(self, event=None):
        if self._muted:
            self.engine.set_volume(self._prev_vol)
            self._vol_scale.set(int(self._prev_vol * 100))
            self._muted = False
        else:
            self._prev_vol = self.volume
            self.engine.set_volume(0)
            self._vol_scale.set(0)
            self._muted = True

    # ----------------------------------------------------------
    # TIMER TICKER
    # ----------------------------------------------------------
    def _start_ticker(self):
        self._tick()

    def _tick(self):
        if self.is_playing:
            pos = self.engine.get_pos_seconds()
            if self.duration_s > 0 and not self._scrubbing:
                pct = (pos / self.duration_s) * 100
                self._progress.set(min(100, pct))
            self._cur_lbl.configure(text=YouTubeBackend._fmt_duration(pos))

            # Auto-advance
            if self.duration_s > 0 and not self.engine.is_busy() and pos > 1:
                if self.is_looping and self.current_track:
                    self._play_now(self.current_track)
                else:
                    self._next_track()

        self.after(500, self._tick)

    # ----------------------------------------------------------
    # WORKER THREAD (keeps main thread free)
    # ----------------------------------------------------------
    def _start_worker(self):
        def worker():
            while True:
                fn = self._worker_q.get()
                if fn is None:
                    break
                try:
                    fn()
                except Exception as e:
                    print(f"[Worker] Error: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self):
        self.engine.cleanup()
        self._worker_q.put(None)
        self.destroy()


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    app = TubeFastApp()
    app.mainloop()
