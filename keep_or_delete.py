"""
Keep or Delete: a small game for cleaning up folders.

Controls:
  Right arrow / K  = keep
  Left arrow  / D  = delete (only moved into the "_to_delete" folder)
  Z                = undo the last decision
  Space            = play / stop video (muted)
  O                = open the file in the default program (e.g. video with sound)
  Drag the card    = right to keep, left to delete (like on the website demo)
  L                = next language (or click the language button)

The language is asked on first start and saved in ~/.keep_or_delete.json
(delete that file to see the language selection again).

Translations are JSON files in the locales/ folder; see CONTRIBUTING.md.

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
DRAG_THRESHOLD = 110  # pixels the card must be dragged to count as a decision
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".m4v", ".flv"}
TK_NATIVE_EXTS = {".png", ".gif"}

FONT = "Helvetica"
COLORS = {
    "bg": "#252836",        # window
    "panel": "#1b1d26",     # stage behind the card
    "card": "#252836",
    "field": "#2e3144",     # preview background, chips
    "border": "#3a3e56",
    "fg": "#eceef5",
    "muted": "#9aa0b8",
    "green": "#2fb67a",
    "green_hover": "#3ccf8e",
    "red": "#e5565b",
    "red_hover": "#f2686d",
    "neutral": "#2e3144",
    "neutral_hover": "#3a3e56",
    "accent": "#6c8cff",
    "accent_hover": "#8aa3ff",
}

# ---------- Translations ----------
# Every language is a JSON file in the "locales" folder (en.json, de.json, ...).
# To add a language, copy en.json, translate the values and save it under a new
# name: no code changes needed. See CONTRIBUTING.md.

def locales_dir():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "locales")


def load_languages(directory=None):
    """Load all locale files. Returns {code: {key: text}}.

    Missing keys in a translation fall back to English, so a partly translated
    file never crashes the app. Broken files are skipped with a warning.
    """
    directory = directory or locales_dir()
    raw = {}
    try:
        filenames = sorted(os.listdir(directory))
    except OSError:
        filenames = []
    for filename in filenames:
        if not filename.endswith(".json"):
            continue
        code = filename[:-5]
        try:
            with open(os.path.join(directory, filename), "r",
                      encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print(f"Skipping {filename}: {e}", file=sys.stderr)
            continue
        if not isinstance(data, dict) or not data.get("language_name"):
            print(f"Skipping {filename}: needs a 'language_name'",
                  file=sys.stderr)
            continue
        raw[code] = {k: v for k, v in data.items() if isinstance(v, str)}
    if "en" not in raw:
        sys.exit(f"Missing or invalid {os.path.join(directory, 'en.json')}")
    return {code: {**raw["en"], **table} for code, table in raw.items()}


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


def shorten_name(name, max_len):
    """Shorten a file name in the middle but keep the extension."""
    if len(name) <= max_len:
        return name
    stem, ext = os.path.splitext(name)
    keep = max(1, max_len - len(ext) - 1)
    return stem[:keep] + "…" + ext


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


def ask_language(root, languages):
    """Show a small dialog with one button per language.

    Returns the language code, or None if the dialog was closed.
    """
    c = COLORS
    result = {"lang": None}

    dlg = tk.Toplevel(root)
    dlg.title("Language")
    dlg.configure(bg=c["bg"])
    dlg.resizable(False, False)

    def choose(code):
        result["lang"] = code
        dlg.destroy()

    tk.Label(dlg, text="Choose your language", bg=c["bg"], fg=c["fg"],
             font=(FONT, 13)).pack(padx=40, pady=(22, 12))

    codes = sorted(languages, key=lambda k: languages[k]["language_name"].lower())
    columns = 1 if len(codes) <= 8 else 3
    grid = tk.Frame(dlg, bg=c["bg"])
    grid.pack(padx=24, pady=(0, 20))
    for i, code in enumerate(codes):
        FlatButton(grid, languages[code]["language_name"],
                   lambda code=code: choose(code), c["accent"],
                   c["accent_hover"], font=(FONT, 11, "bold"),
                   width=18).grid(row=i // columns, column=i % columns,
                                  padx=4, pady=4)

    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
    dlg.lift()
    dlg.focus_force()
    dlg.grab_set()
    root.wait_window(dlg)
    return result["lang"]


# ---------- Main app ----------

class App:
    def __init__(self, root, folder, languages, lang, config):
        self.root = root
        self.languages = languages
        self.lang = lang
        self.config = config
        self.photo = None  # keep a reference, otherwise the image disappears
        self.finished = False

        # Card animation / swipe state
        self.busy = False
        self.drag_x = None
        self.card_offset = 0
        self.stage_w = 400
        self.tray_chips = []

        # Preview size follows the card size
        self.preview_w, self.preview_h = 420, 280
        self.resize_job = None

        # Video playback state
        self.cap = None
        self.play_job = None
        self.playing = False

        self.load_folder(folder)
        self.build_ui()
        self.bind_keys()
        self.apply_language()
        self.show()

    def load_folder(self, folder):
        """(Re)start the session for `folder`."""
        self.folder = folder
        self.trash = os.path.join(folder, TRASH_NAME)
        os.makedirs(self.trash, exist_ok=True)
        self.files = list_files(folder)
        self.index = 0
        self.kept = 0
        self.deleted = 0
        self.history = []  # dicts: name, action ("keep"/"delete"), trash_path

    # ---------- UI construction ----------

    def build_ui(self):
        c = COLORS
        root = self.root
        root.configure(bg=c["bg"])
        root.minsize(540, 720)
        root.geometry("620x840")

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
        self.lang_btn = FlatButton(footer, "", self.show_language_menu,
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

        # Bottom widgets are packed first so the stage only takes the leftover space
        self.hint = tk.Label(self.main_frame, bg=c["bg"], fg=c["muted"],
                             font=(FONT, 9))
        self.hint.pack(side="bottom", pady=(0, 6))

        secondary = tk.Frame(self.main_frame, bg=c["bg"])
        secondary.pack(side="bottom", pady=(0, 8))
        self.undo_btn = FlatButton(secondary, "", self.undo, c["neutral"],
                                   c["neutral_hover"], font=(FONT, 10),
                                   padx=14, pady=7)
        self.undo_btn.pack(side="left", padx=5)
        self.play_btn = FlatButton(secondary, "", self.toggle_play,
                                   c["neutral"], c["neutral_hover"],
                                   font=(FONT, 10), padx=14, pady=7)
        self.play_btn.pack(side="left", padx=5)
        self.open_btn = FlatButton(secondary, "", self.open_external,
                                   c["neutral"], c["neutral_hover"],
                                   font=(FONT, 10), padx=14, pady=7)
        self.open_btn.pack(side="left", padx=5)

        # Strip that shows what was set aside (like on the website)
        self.tray = tk.Frame(self.main_frame, bg=c["panel"], height=46)
        self.tray.pack_propagate(False)
        self.tray.pack(side="bottom", fill="x", padx=24, pady=(0, 12))
        tk.Label(self.tray, text=TRASH_NAME, bg=c["panel"], fg=c["red"],
                 font=("Courier", 10, "bold")).pack(side="left", padx=(12, 10))
        self.tray_items = tk.Frame(self.tray, bg=c["panel"])
        self.tray_items.pack(side="left", fill="y")

        actions = tk.Frame(self.main_frame, bg=c["bg"])
        actions.pack(side="bottom", fill="x", padx=24, pady=(8, 12))
        self.delete_btn = FlatButton(actions, "", self.delete, c["red"],
                                     c["red_hover"], font=(FONT, 14, "bold"),
                                     pady=13)
        self.delete_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.keep_btn = FlatButton(actions, "", self.keep, c["green"],
                                   c["green_hover"], font=(FONT, 14, "bold"),
                                   pady=13)
        self.keep_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

        # Stage with the card; its border glows green/red while you drag
        self.stage = tk.Frame(self.main_frame, bg=c["panel"],
                              highlightthickness=2,
                              highlightbackground=c["panel"],
                              highlightcolor=c["panel"])
        self.stage.pack(fill="both", expand=True, padx=24, pady=(14, 12))
        self.stage.bind("<Configure>", self.on_stage_resize)

        self.card = tk.Frame(self.stage, bg=c["card"], highlightthickness=1,
                             highlightbackground=c["border"])
        self.card.place(relx=0.5, rely=0.5, relwidth=0.86, relheight=0.92,
                        anchor="center")
        self.card.bind(
            "<Configure>",
            lambda e: self.name.config(wraplength=max(120, e.width - 32)))

        self.info = tk.Label(self.card, bg=c["card"], fg=c["muted"],
                             font=(FONT, 10))
        self.info.pack(side="bottom", pady=(0, 12))
        self.name = tk.Label(self.card, bg=c["card"], fg=c["fg"],
                             font=(FONT, 13, "bold"), wraplength=380)
        self.name.pack(side="bottom", pady=(10, 2))

        # Preview area: fixed requested size, grows with the card
        self.preview_box = tk.Frame(self.card, bg=c["field"], width=200,
                                    height=150)
        self.preview_box.pack_propagate(False)
        self.preview_box.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        self.preview_box.bind("<Configure>", self.on_preview_resize)
        self.preview = tk.Label(self.preview_box, bg=c["field"], fg=c["muted"],
                                font=(FONT, 12), justify="center")
        self.preview.place(relx=0.5, rely=0.5, anchor="center")

        # Dragging works from anywhere on the card
        for widget in (self.card, self.preview_box, self.preview, self.name,
                       self.info):
            widget.bind("<ButtonPress-1>", self.drag_start)
            widget.bind("<B1-Motion>", self.drag_move)
            widget.bind("<ButtonRelease-1>", self.drag_end)

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
                                         font=(FONT, 12, "bold"), width=30)
        self.open_trash_btn.pack(pady=5)
        self.another_btn = FlatButton(inner, "", self.choose_another_folder,
                                      c["neutral"], c["neutral_hover"],
                                      font=(FONT, 11), width=30)
        self.another_btn.pack(pady=5)
        self.undo_last_btn = FlatButton(inner, "", self.undo, c["neutral"],
                                        c["neutral_hover"], font=(FONT, 11),
                                        width=30)
        self.undo_last_btn.pack(pady=5)
        self.close_btn = FlatButton(inner, "", self.close, c["neutral"],
                                    c["neutral_hover"], font=(FONT, 11),
                                    width=30)
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
        bind(("l", "L"), self.cycle_language)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ---------- Language ----------

    def t(self, key, **kwargs):
        table = self.languages.get(self.lang) or self.languages["en"]
        text = table.get(key, key)
        if not kwargs:
            return text
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            # Broken placeholder in a translation: fall back to English
            return self.languages["en"].get(key, key).format(**kwargs)

    def apply_language(self):
        """Set the text of all widgets in the current language."""
        self.root.title(self.t("window_title"))
        self.delete_btn.config(text=self.t("delete_btn"))
        self.keep_btn.config(text=self.t("keep_btn"))
        self.undo_btn.config(text=self.t("undo_btn"))
        self.open_btn.config(text=self.t("open_btn"))
        self.lang_btn.config(text=self.t(
            "language_btn", name=self.languages[self.lang]["language_name"]))
        self.play_btn.config(
            text=self.t("stop_btn" if self.playing else "play_btn"))
        self.open_trash_btn.config(text=self.t("open_trash_btn", trash=TRASH_NAME))
        self.undo_last_btn.config(text=self.t("undo_last_btn"))
        self.close_btn.config(text=self.t("close_btn"))
        self.another_btn.config(text=self.t("another_btn"))
        self.hint.config(text=self.t("hint_keys"))
        self.update_header()
        self.update_tray()
        if self.finished:
            self.render_done()

    def language_codes(self):
        return sorted(self.languages,
                      key=lambda k: self.languages[k]["language_name"].lower())

    def set_language(self, code):
        if code not in self.languages:
            return
        self.lang = code
        self.config["language"] = code
        save_config(self.config)
        self.apply_language()
        if not self.finished and not self.playing:
            self.show_preview()  # hints are translated, too

    def cycle_language(self):
        codes = self.language_codes()
        self.set_language(codes[(codes.index(self.lang) + 1) % len(codes)])

    def show_language_menu(self):
        menu = tk.Menu(self.root, tearoff=0)
        for code in self.language_codes():
            menu.add_command(label=self.languages[code]["language_name"],
                             command=lambda code=code: self.set_language(code))
        menu.update_idletasks()
        # The button sits at the bottom, so open the menu upwards
        x = self.lang_btn.winfo_rootx()
        y = self.lang_btn.winfo_rooty() - (menu.winfo_reqheight() or 0)
        menu.tk_popup(x, y)

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
        self.update_tray()
        self.name.config(text=self.files[self.index])
        self.show_preview()

    # ---------- Card animation, swipe, tray ----------

    def on_stage_resize(self, event):
        self.stage_w = event.width

    def set_card_offset(self, x):
        self.card_offset = x
        self.card.place_configure(x=int(x))

    def set_glow(self, direction):
        c = COLORS
        color = (c["green"] if direction > 0
                 else c["red"] if direction < 0 else c["panel"])
        self.stage.config(highlightbackground=color)

    def animate_card(self, direction):
        """Slide the card out of the stage (+1 = right, -1 = left), then show the next file."""
        self.busy = True
        start = self.card_offset
        target = direction * max(self.stage_w, 320)
        frames = 9

        def step(n):
            t = n / frames
            eased = 1 - (1 - t) ** 3
            self.set_card_offset(start + (target - start) * eased)
            if n < frames:
                self.root.after(16, lambda: step(n + 1))
            else:
                self.set_card_offset(0)
                self.set_glow(0)
                self.busy = False
                self.show()

        step(1)

    def drag_start(self, event):
        if self.finished or self.busy:
            return
        self.drag_x = event.x_root

    def drag_move(self, event):
        if self.drag_x is None:
            return
        dx = event.x_root - self.drag_x
        self.set_card_offset(dx)
        self.set_glow(1 if dx > 40 else -1 if dx < -40 else 0)

    def drag_end(self, event):
        if self.drag_x is None:
            return
        dx = event.x_root - self.drag_x
        self.drag_x = None
        self.set_glow(0)
        if dx > DRAG_THRESHOLD:
            self.keep()
        elif dx < -DRAG_THRESHOLD:
            self.delete()
        else:
            self.set_card_offset(0)  # not far enough: snap back

    def update_tray(self):
        """Show the most recent sorted-out files in the strip below the buttons."""
        c = COLORS
        for chip in self.tray_chips:
            chip.destroy()
        self.tray_chips = []

        names = [h["name"] for h in self.history if h["action"] == "delete"]
        labels = []  # (text, is_chip)
        if not names:
            labels.append((self.t("tray_empty"), False))
        else:
            if len(names) > 3:
                labels.append((f"+{len(names) - 3}", False))
            labels.extend((shorten_name(n, 20), True) for n in names[-3:])

        for text, is_chip in labels:
            chip = tk.Label(self.tray_items, text=text, font=(FONT, 9),
                            bg=c["field"] if is_chip else c["panel"],
                            fg=c["fg"] if is_chip else c["muted"],
                            padx=8 if is_chip else 0, pady=2)
            chip.pack(side="left", padx=(0, 6), pady=10)
            self.tray_chips.append(chip)

    def choose_another_folder(self):
        self.stop_video()
        folder = filedialog.askdirectory(
            title=self.t("choose_folder"),
            initialdir=os.path.dirname(self.folder) or None)
        if not folder:
            return
        self.load_folder(folder)
        self.folder_lbl.config(text=shorten(folder, 48))
        self.show()

    # ---------- Decisions ----------

    def keep(self):
        if self.finished or self.busy:
            return
        self.stop_video()
        self.history.append({"name": self.files[self.index],
                             "action": "keep", "trash_path": None})
        self.kept += 1
        self.index += 1
        self.animate_card(1)

    def delete(self):
        if self.finished or self.busy:
            return
        self.stop_video()
        name = self.files[self.index]
        os.makedirs(self.trash, exist_ok=True)
        # Never overwrite something that is already in the trash folder
        target = unique_path(self.trash, name)
        try:
            shutil.move(self.current_path(), target)
        except Exception as e:
            self.set_card_offset(0)  # a dragged card snaps back
            messagebox.showerror(self.t("error_title"),
                                 self.t("move_error", name=name, err=e))
            return
        self.history.append({"name": name, "action": "delete",
                             "trash_path": target})
        self.deleted += 1
        self.index += 1
        self.animate_card(-1)

    def undo(self):
        if not self.history or self.busy:
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
    languages = load_languages()
    root = tk.Tk()
    root.withdraw()

    config = load_config()
    lang = config.get("language")
    if lang not in languages:
        # First start (or unknown language in config): let the user pick one
        chosen = ask_language(root, languages)
        lang = chosen or "en"  # dialog closed -> English, but don't save
        if chosen:
            config["language"] = chosen
            save_config(config)

    folder = filedialog.askdirectory(title=languages[lang]["choose_folder"])
    if folder:
        root.deiconify()
        App(root, folder, languages, lang, config)
        root.mainloop()
    else:
        root.destroy()
