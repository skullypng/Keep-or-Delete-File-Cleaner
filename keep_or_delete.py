"""
Keep or Delete: a small game for cleaning up folders.

Controls:
  Right arrow / K  = keep
  Left arrow  / D  = delete (only moved into the "_to_delete" folder)
  Z                = undo the last decision
  Space            = play / stop video (muted)
  O                = open the file in the default program (e.g. video with sound)
  L                = switch language (German / English)

The language is asked on first start and saved in ~/.keep_or_delete.json
(delete that file to see the language selection again).

Previews:
  Images:  pip install pillow
  Videos:  pip install pillow opencv-python

Run:  python keep_or_delete.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageOps, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

TRASH_NAME = "_to_delete"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".keep_or_delete.json")
IGNORED_NAMES = {"thumbs.db", "desktop.ini"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".m4v", ".flv"}
TK_NATIVE_EXTS = {".png", ".gif"}

FONT = "Helvetica"
COLORS = {
    "bg": "#1b1d26",
    "panel": "#252836",
    "fg": "#eceef5",
    "muted": "#9498ad",
    "green": "#2fb67a",
    "green_hover": "#3ccf8e",
    "red": "#e5565b",
    "red_hover": "#f2686d",
    "neutral": "#353849",
    "neutral_hover": "#444860",
    "accent": "#6c8cff",
    "accent_hover": "#8aa3ff",
}

# ---------- Translations ----------

STRINGS = {
    "en": {
        "window_title": "Keep or Delete",
        "delete_btn": "← Delete (D)",
        "keep_btn": "Keep (K) →",
        "undo_btn": "Undo (Z)",
        "play_btn": "Play (Space)",
        "stop_btn": "Stop (Space)",
        "open_btn": "Open externally (O)",
        "lang_btn": "Auf Deutsch wechseln (L)",
        "progress": "File {i} of {n}",
        "kept_label": "Kept: {n}",
        "deleted_label": "Sorted out: {n}",
        "no_preview": "No preview available",
        "no_preview_pillow": "No preview.\nFor this format: pip install pillow",
        "preview_failed": "Preview not possible",
        "no_video_preview": "No video preview.\npip install pillow opencv-python",
        "done_header": "All done!",
        "done_empty": "No files found in this folder.",
        "done_stats": "Kept: {kept}   ·   Sorted out: {deleted}",
        "done_folder": "Sorted-out files are in the '{trash}' folder.\n"
                       "Nothing was permanently deleted.",
        "open_trash_btn": "Open '{trash}' folder",
        "undo_last_btn": "Undo last decision",
        "close_btn": "Close",
        "error_title": "Error",
        "open_error": "Could not open:\n{err}",
        "move_error": "Could not move '{name}':\n{err}",
        "restore_error": "Could not restore '{name}':\n{err}",
        "choose_folder": "Which folder do you want to clean up?",
    },
    "de": {
        "window_title": "Behalten oder Löschen",
        "delete_btn": "← Löschen (D)",
        "keep_btn": "Behalten (K) →",
        "undo_btn": "Rückgängig (Z)",
        "play_btn": "Abspielen (Leertaste)",
        "stop_btn": "Stopp (Leertaste)",
        "open_btn": "Extern öffnen (O)",
        "lang_btn": "Switch to English (L)",
        "progress": "Datei {i} von {n}",
        "kept_label": "Behalten: {n}",
        "deleted_label": "Aussortiert: {n}",
        "no_preview": "Keine Vorschau verfügbar",
        "no_preview_pillow": "Keine Vorschau.\nFür dieses Format: pip install pillow",
        "preview_failed": "Vorschau nicht möglich",
        "no_video_preview": "Keine Videovorschau.\npip install pillow opencv-python",
        "done_header": "Alles erledigt!",
        "done_empty": "In diesem Ordner liegen keine Dateien.",
        "done_stats": "Behalten: {kept}   ·   Aussortiert: {deleted}",
        "done_folder": "Aussortierte Dateien liegen im Ordner '{trash}'.\n"
                       "Es wurde nichts endgültig gelöscht.",
        "open_trash_btn": "Ordner '{trash}' öffnen",
        "undo_last_btn": "Letzte Entscheidung rückgängig",
        "close_btn": "Schließen",
        "error_title": "Fehler",
        "open_error": "Konnte nicht geöffnet werden:\n{err}",
        "move_error": "'{name}' konnte nicht verschoben werden:\n{err}",
        "restore_error": "'{name}' konnte nicht wiederhergestellt werden:\n{err}",
        "choose_folder": "Welchen Ordner willst du aufräumen?",
    },
}


# ---------- Config ----------

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f)
    except OSError:
        pass  # not critical: we just ask again next time


# ---------- Helpers ----------

def enable_dpi_awareness():
    """Avoid blurry text on high-DPI Windows screens."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def format_size(num_bytes):
    kb = num_bytes / 1024
    return f"{kb:.1f} KB" if kb < 1024 else f"{kb / 1024:.1f} MB"


def format_duration(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def shorten(text, max_len):
    return text if len(text) <= max_len else "…" + text[-(max_len - 1):]


def natural_key(name):
    """Sort 'img2' before 'img10'."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name)]


def unique_path(directory, name):
    """Return a path in `directory` that doesn't exist yet (adds ' (1)', ' (2)', ...).

    Prevents silently overwriting a file with the same name.
    """
    candidate = os.path.join(directory, name)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(name)
    n = 1
    while True:
        candidate = os.path.join(directory, f"{stem} ({n}){ext}")
        if not os.path.exists(candidate):
            return candidate
        n += 1


def list_files(folder):
    """All regular, non-hidden files in `folder`, naturally sorted."""
    names = []
    for f in os.listdir(folder):
        if f.startswith(".") or f.lower() in IGNORED_NAMES:
            continue
        if os.path.isfile(os.path.join(folder, f)):
            names.append(f)
    return sorted(names, key=natural_key)


class FlatButton(tk.Label):
    """Label-based button so colors and hover work on every platform (incl. macOS)."""

    def __init__(self, master, text, command, bg, hover, fg="#ffffff",
                 font=None, padx=18, pady=10, width=None):
        super().__init__(master, text=text, bg=bg, fg=fg, font=font,
                         padx=padx, pady=pady, cursor="hand2")
        if width:
            self.config(width=width)
        self._bg = bg
        self._hover = hover
        self._command = command
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))
        self.bind("<Button-1>", lambda e: self._command())


def ask_language(root):
    """Show a small bilingual dialog. Returns 'de', 'en' or None if closed."""
    c = COLORS
    result = {"lang": None}

    dlg = tk.Toplevel(root)
    dlg.title("Language / Sprache")
    dlg.configure(bg=c["bg"])
    dlg.geometry("340x170")
    dlg.resizable(False, False)

    def choose(code):
        result["lang"] = code
        dlg.destroy()

    tk.Label(dlg, text="Choose your language\nSprache auswählen",
             bg=c["bg"], fg=c["fg"], font=(FONT, 13)).pack(pady=(22, 16))
    row = tk.Frame(dlg, bg=c["bg"])
    row.pack()
    FlatButton(row, "Deutsch", lambda: choose("de"), c["accent"],
               c["accent_hover"], font=(FONT, 11, "bold"),
               width=11).pack(side="left", padx=8)
    FlatButton(row, "English", lambda: choose("en"), c["accent"],
               c["accent_hover"], font=(FONT, 11, "bold"),
               width=11).pack(side="left", padx=8)

    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
    dlg.lift()
    dlg.focus_force()
    dlg.grab_set()
    root.wait_window(dlg)
    return result["lang"]


# ---------- Main app ----------

class App:
    def __init__(self, root, folder, lang, config):
        self.root = root
        self.folder = folder
        self.lang = lang
        self.config = config
        self.trash = os.path.join(folder, TRASH_NAME)
        os.makedirs(self.trash, exist_ok=True)

        self.files = list_files(folder)
        self.index = 0
        self.kept = 0
        self.deleted = 0
        self.history = []  # dicts: name, action ("keep"/"delete"), trash_path
        self.photo = None  # keep a reference, otherwise the image disappears
        self.finished = False

        # Preview size follows the window size
        self.preview_w, self.preview_h = 460, 320
        self.resize_job = None

        # Video playback state
        self.cap = None
        self.play_job = None
        self.playing = False

        self.build_ui()
        self.bind_keys()
        self.apply_language()
        self.show()

    # ---------- UI construction ----------

    def build_ui(self):
        c = COLORS
        root = self.root
        root.configure(bg=c["bg"])
        root.minsize(560, 640)
        root.geometry("680x780")

        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Keep.Horizontal.TProgressbar",
                        troughcolor=c["panel"], background=c["accent"],
                        bordercolor=c["panel"], lightcolor=c["accent"],
                        darkcolor=c["accent"], thickness=8)

        # Header: progress text on the left, counters on the right
        header = tk.Frame(root, bg=c["bg"])
        header.pack(fill="x", padx=24, pady=(18, 6))
        self.progress = tk.Label(header, bg=c["bg"], fg=c["fg"],
                                 font=(FONT, 12, "bold"))
        self.progress.pack(side="left")
        self.kept_lbl = tk.Label(header, bg=c["bg"], fg=c["green"],
                                 font=(FONT, 11))
        self.kept_lbl.pack(side="right")
        self.deleted_lbl = tk.Label(header, bg=c["bg"], fg=c["red"],
                                    font=(FONT, 11))
        self.deleted_lbl.pack(side="right", padx=(0, 16))

        self.bar = ttk.Progressbar(root, style="Keep.Horizontal.TProgressbar",
                                   mode="determinate",
                                   maximum=max(1, len(self.files)))
        self.bar.pack(fill="x", padx=24)

        # Footer is packed before the content so it never gets squeezed out
        footer = tk.Frame(root, bg=c["bg"])
        footer.pack(side="bottom", fill="x", padx=24, pady=(4, 14))
        self.folder_lbl = tk.Label(footer, text=shorten(self.folder, 48),
                                   bg=c["bg"], fg=c["muted"], font=(FONT, 9))
        self.folder_lbl.pack(side="left")
        self.lang_btn = FlatButton(footer, "", self.toggle_language,
                                   c["neutral"], c["neutral_hover"],
                                   font=(FONT, 9), padx=10, pady=4)
        self.lang_btn.pack(side="right")

        self.content = tk.Frame(root, bg=c["bg"])
        self.content.pack(fill="both", expand=True)

        self.build_main_frame()
        self.build_done_frame()

    def build_main_frame(self):
        c = COLORS
        self.main_frame = tk.Frame(self.content, bg=c["bg"])
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.bind(
            "<Configure>",
            lambda e: self.name.config(wraplength=max(200, e.width - 48)))

        # Bottom widgets are packed first so the preview only takes the leftover space
        secondary = tk.Frame(self.main_frame, bg=c["bg"])
        secondary.pack(side="bottom", pady=(0, 10))
        self.undo_btn = FlatButton(secondary, "", self.undo, c["neutral"],
                                   c["neutral_hover"], font=(FONT, 10),
                                   padx=12, pady=6)
        self.undo_btn.pack(side="left", padx=5)
        self.play_btn = FlatButton(secondary, "", self.toggle_play,
                                   c["neutral"], c["neutral_hover"],
                                   font=(FONT, 10), padx=12, pady=6)
        self.play_btn.pack(side="left", padx=5)
        self.open_btn = FlatButton(secondary, "", self.open_external,
                                   c["neutral"], c["neutral_hover"],
                                   font=(FONT, 10), padx=12, pady=6)
        self.open_btn.pack(side="left", padx=5)

        actions = tk.Frame(self.main_frame, bg=c["bg"])
        actions.pack(side="bottom", pady=(6, 10))
        self.delete_btn = FlatButton(actions, "", self.delete, c["red"],
                                     c["red_hover"], font=(FONT, 13, "bold"),
                                     width=16)
        self.delete_btn.pack(side="left", padx=8)
        self.keep_btn = FlatButton(actions, "", self.keep, c["green"],
                                   c["green_hover"], font=(FONT, 13, "bold"),
                                   width=16)
        self.keep_btn.pack(side="left", padx=8)

        self.info = tk.Label(self.main_frame, bg=c["bg"], fg=c["muted"],
                             font=(FONT, 11))
        self.info.pack(side="bottom")
        self.name = tk.Label(self.main_frame, bg=c["bg"], fg=c["fg"],
                             font=(FONT, 14, "bold"), wraplength=560)
        self.name.pack(side="bottom", pady=(10, 2))

        # Preview panel: fixed requested size, grows with the window
        self.preview_box = tk.Frame(self.main_frame, bg=c["panel"],
                                    width=200, height=150)
        self.preview_box.pack_propagate(False)
        self.preview_box.pack(fill="both", expand=True, padx=24, pady=(14, 4))
        self.preview_box.bind("<Configure>", self.on_preview_resize)
        self.preview = tk.Label(self.preview_box, bg=c["panel"], fg=c["muted"],
                                font=(FONT, 12), justify="center")
        self.preview.place(relx=0.5, rely=0.5, anchor="center")

    def build_done_frame(self):
        c = COLORS
        self.done_frame = tk.Frame(self.content, bg=c["bg"])  # shown at the end
        inner = tk.Frame(self.done_frame, bg=c["bg"])
        inner.place(relx=0.5, rely=0.45, anchor="center")

        self.done_title = tk.Label(inner, bg=c["bg"], fg=c["green"],
                                   font=(FONT, 26, "bold"))
        self.done_title.pack(pady=(0, 14))
        self.done_stats = tk.Label(inner, bg=c["bg"], fg=c["fg"],
                                   font=(FONT, 14))
        self.done_stats.pack(pady=(0, 8))
        self.done_note = tk.Label(inner, bg=c["bg"], fg=c["muted"],
                                  font=(FONT, 11), justify="center")
        self.done_note.pack(pady=(0, 22))

        self.open_trash_btn = FlatButton(inner, "", self.open_trash,
                                         c["accent"], c["accent_hover"],
                                         font=(FONT, 12, "bold"), width=28)
        self.open_trash_btn.pack(pady=5)
        self.undo_last_btn = FlatButton(inner, "", self.undo, c["neutral"],
                                        c["neutral_hover"], font=(FONT, 11),
                                        width=28)
        self.undo_last_btn.pack(pady=5)
        self.close_btn = FlatButton(inner, "", self.close, c["neutral"],
                                    c["neutral_hover"], font=(FONT, 11),
                                    width=28)
        self.close_btn.pack(pady=5)

    def bind_keys(self):
        def bind(keys, func):
            for key in keys:
                self.root.bind(key, lambda e, f=func: f())

        # Upper- and lowercase, so Caps Lock doesn't break the shortcuts
        bind(("<Right>", "k", "K"), self.keep)
        bind(("<Left>", "d", "D"), self.delete)
        bind(("z", "Z"), self.undo)
        bind(("<space>",), self.toggle_play)
        bind(("o", "O"), self.open_external)
        bind(("l", "L"), self.toggle_language)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ---------- Language ----------

    def t(self, key, **kwargs):
        text = STRINGS[self.lang][key]
        return text.format(**kwargs) if kwargs else text

    def apply_language(self):
        """Set the text of all widgets in the current language."""
        self.root.title(self.t("window_title"))
        self.delete_btn.config(text=self.t("delete_btn"))
        self.keep_btn.config(text=self.t("keep_btn"))
        self.undo_btn.config(text=self.t("undo_btn"))
        self.open_btn.config(text=self.t("open_btn"))
        self.lang_btn.config(text=self.t("lang_btn"))
        self.play_btn.config(
            text=self.t("stop_btn" if self.playing else "play_btn"))
        self.open_trash_btn.config(text=self.t("open_trash_btn", trash=TRASH_NAME))
        self.undo_last_btn.config(text=self.t("undo_last_btn"))
        self.close_btn.config(text=self.t("close_btn"))
        self.update_header()
        if self.finished:
            self.render_done()

    def toggle_language(self):
        self.lang = "de" if self.lang == "en" else "en"
        self.config["language"] = self.lang
        save_config(self.config)
        self.apply_language()
        if not self.finished and not self.playing:
            self.show_preview()  # hints are translated, too

    # ---------- Helpers ----------

    def current_path(self):
        return os.path.join(self.folder, self.files[self.index])

    def current_ext(self):
        return os.path.splitext(self.files[self.index])[1].lower()

    def close(self):
        self.stop_video()
        self.root.destroy()

    def update_header(self):
        n = len(self.files)
        if self.finished or n == 0:
            self.progress.config(text="")
        else:
            self.progress.config(
                text=self.t("progress", i=self.index + 1, n=n))
        self.kept_lbl.config(text=self.t("kept_label", n=self.kept))
        self.deleted_lbl.config(text=self.t("deleted_label", n=self.deleted))
        self.bar.config(maximum=max(1, n))
        self.bar["value"] = min(self.index, n)

    def on_preview_resize(self, event):
        self.preview_w = max(100, event.width - 24)
        self.preview_h = max(100, event.height - 24)
        # Debounce: re-render only after the user stopped resizing
        if self.resize_job is not None:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(150, self.refresh_after_resize)

    def refresh_after_resize(self):
        self.resize_job = None
        if (not self.finished and not self.playing
                and self.index < len(self.files)):
            self.show_preview()

    def open_path(self, path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror(self.t("error_title"),
                                 self.t("open_error", err=e))

    def open_external(self):
        if self.finished or self.index >= len(self.files):
            return
        self.stop_video()
        self.open_path(self.current_path())

    def open_trash(self):
        os.makedirs(self.trash, exist_ok=True)
        self.open_path(self.trash)

    # ---------- Images ----------

    def load_image_preview(self, path):
        ext = os.path.splitext(path)[1].lower()
        try:
            if HAS_PIL:
                # "with" closes the file handle (important on Windows)
                with Image.open(path) as img:
                    img = ImageOps.exif_transpose(img)  # respect phone rotation
                    img.thumbnail((self.preview_w, self.preview_h))
                    if img.mode not in ("RGB", "RGBA", "L"):
                        img = img.convert("RGBA")
                    return ImageTk.PhotoImage(img)
            if ext in TK_NATIVE_EXTS:
                img = tk.PhotoImage(file=path)
                # tkinter can only shrink by integer factors
                factor = max(1, -(-img.width() // self.preview_w),
                             -(-img.height() // self.preview_h))
                return img.subsample(factor, factor) if factor > 1 else img
        except Exception:
            return None
        return None

    # ---------- Videos ----------

    def frame_to_photo(self, frame):
        """Convert an OpenCV frame (BGR) into a scaled tkinter PhotoImage."""
        h, w = frame.shape[:2]
        scale = min(self.preview_w / w, self.preview_h / h, 1.0)
        if scale < 1.0:
            frame = cv2.resize(frame, (max(1, int(w * scale)),
                                       max(1, int(h * scale))))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return ImageTk.PhotoImage(Image.fromarray(rgb))

    def load_video_preview(self, path):
        """Return (PhotoImage, info text) or (None, None) on failure."""
        cap = None
        try:
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                return None, None
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if frames > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frames // 2)
            ok, frame = cap.read()
            if not ok:
                return None, None
            info = f"{width}×{height}"
            if fps > 0 and frames > 0:
                info = f"{format_duration(frames / fps)} · " + info
            return self.frame_to_photo(frame), info
        except Exception:
            return None, None
        finally:
            if cap is not None:
                cap.release()

    def toggle_play(self):
        if self.finished or self.index >= len(self.files):
            return
        if self.current_ext() not in VIDEO_EXTS or not (HAS_CV2 and HAS_PIL):
            return
        if self.playing:
            self.stop_video()
            self.show_preview()  # back to the still frame
            return
        self.cap = cv2.VideoCapture(self.current_path())
        if not self.cap.isOpened():
            self.stop_video()
            return
        self.playing = True
        self.play_btn.config(text=self.t("stop_btn"))
        self.play_step()

    def play_step(self):
        if not self.playing or self.cap is None:
            return
        started = time.perf_counter()
        ok, frame = self.cap.read()
        if not ok:  # reached the end: loop from the start
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
            if not ok:
                self.stop_video()
                return
        self.photo = self.frame_to_photo(frame)
        self.preview.config(image=self.photo, text="")

        fps = self.cap.get(cv2.CAP_PROP_FPS) or 25
        if fps <= 0 or fps > 120:
            fps = 25
        # Subtract the time spent decoding/drawing so playback speed stays right
        elapsed = time.perf_counter() - started
        delay = max(1, int((1.0 / fps - elapsed) * 1000))
        self.play_job = self.root.after(delay, self.play_step)

    def stop_video(self):
        """Release the file handle, otherwise Windows won't let us move the file."""
        self.playing = False
        if self.play_job is not None:
            self.root.after_cancel(self.play_job)
            self.play_job = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.play_btn.config(text=self.t("play_btn"))

    # ---------- Display ----------

    def show_preview(self):
        path = self.current_path()
        ext = self.current_ext()
        try:
            size = format_size(os.path.getsize(path))
        except OSError:
            size = ""
        extra_info = ""
        self.photo = None
        hint = self.t("no_preview")

        if ext in IMAGE_EXTS:
            self.photo = self.load_image_preview(path)
            if not self.photo:
                hint = self.t("preview_failed" if HAS_PIL
                              else "no_preview_pillow")
        elif ext in VIDEO_EXTS:
            if HAS_CV2 and HAS_PIL:
                self.photo, extra_info = self.load_video_preview(path)
                hint = self.t("preview_failed")
            else:
                hint = self.t("no_video_preview")

        if self.photo:
            self.preview.config(image=self.photo, text="")
        else:
            self.preview.config(image="", text=hint)

        parts = [p for p in (size, extra_info) if p]
        self.info.config(text=" · ".join(parts))

    def show_main(self):
        if self.finished:
            self.done_frame.pack_forget()
            self.main_frame.pack(fill="both", expand=True)
            self.finished = False

    def show_done(self):
        self.stop_video()
        self.main_frame.pack_forget()
        self.done_frame.pack(fill="both", expand=True)
        self.finished = True
        self.render_done()
        self.update_header()

    def render_done(self):
        if not self.files:
            self.done_title.config(text=self.t("done_empty"), fg=COLORS["muted"])
            self.done_stats.config(text="")
            self.done_note.config(text="")
            return
        self.done_title.config(text=self.t("done_header"), fg=COLORS["green"])
        self.done_stats.config(text=self.t("done_stats", kept=self.kept,
                                           deleted=self.deleted))
        self.done_note.config(
            text=self.t("done_folder", trash=TRASH_NAME) if self.deleted else "")

    def show(self):
        self.stop_video()
        # Skip files that disappeared in the meantime (moved/deleted elsewhere)
        while (self.index < len(self.files)
               and not os.path.exists(self.current_path())):
            self.index += 1
        if self.index >= len(self.files):
            self.show_done()
            return
        self.show_main()
        self.update_header()
        self.name.config(text=self.files[self.index])
        self.show_preview()

    # ---------- Decisions ----------

    def keep(self):
        if self.finished:
            return
        self.stop_video()
        self.history.append({"name": self.files[self.index],
                             "action": "keep", "trash_path": None})
        self.kept += 1
        self.index += 1
        self.show()

    def delete(self):
        if self.finished:
            return
        self.stop_video()
        name = self.files[self.index]
        os.makedirs(self.trash, exist_ok=True)
        # Never overwrite something that is already in the trash folder
        target = unique_path(self.trash, name)
        try:
            shutil.move(self.current_path(), target)
        except Exception as e:
            messagebox.showerror(self.t("error_title"),
                                 self.t("move_error", name=name, err=e))
            return
        self.history.append({"name": name, "action": "delete",
                             "trash_path": target})
        self.deleted += 1
        self.index += 1
        self.show()

    def undo(self):
        if not self.history:
            return
        self.stop_video()
        entry = self.history[-1]
        try:
            pos = self.files.index(entry["name"])
        except ValueError:
            pos = max(0, self.index - 1)

        if entry["action"] == "delete":
            restored = unique_path(self.folder, entry["name"])
            try:
                shutil.move(entry["trash_path"], restored)
            except Exception as e:
                messagebox.showerror(
                    self.t("error_title"),
                    self.t("restore_error", name=entry["name"], err=e))
                return
            self.deleted -= 1
            # Rare case: the original name was taken meanwhile
            self.files[pos] = os.path.basename(restored)
        else:
            self.kept -= 1

        self.history.pop()
        self.index = pos
        self.show()


if __name__ == "__main__":
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()

    config = load_config()
    lang = config.get("language")
    if lang not in STRINGS:
        # First start (or broken config): let the user pick a language
        chosen = ask_language(root)
        lang = chosen or "en"  # dialog closed -> English, but don't save
        if chosen:
            config["language"] = chosen
            save_config(config)

    folder = filedialog.askdirectory(title=STRINGS[lang]["choose_folder"])
    if folder:
        root.deiconify()
        App(root, folder, lang, config)
        root.mainloop()
    else:
        root.destroy()
