# Keep or Delete

A small desktop app that turns cleaning up a folder into a quick game: you see
one file at a time and decide **keep** or **delete**. Nothing is ever deleted
permanently — sorted-out files are only moved into a `_to_delete` folder that
you can review afterwards.

## Features

- Image preview (JPG, PNG, GIF, WebP, BMP, TIFF), respects photo rotation
- Video preview with still frame, duration and resolution; muted playback in the window
- Undo for every decision, even after the last file
- Progress bar and live counters
- Resizable window, dark theme
- English and German interface (asked on first start, switchable any time)

## Installation

You need Python 3.8 or newer. Tkinter ships with Python on Windows and macOS;
on Linux you may need `sudo apt install python3-tk`.

```bash
git clone https://github.com/<your-username>/keep-or-delete.git
cd keep-or-delete
pip install -r requirements.txt   # optional: needed for previews
python keep_or_delete.py
```

Without the optional packages the app still works, but previews are limited to
PNG and GIF images.

## Controls

| Key             | Action                                        |
| --------------- | --------------------------------------------- |
| `→` / `K`       | Keep the file                                 |
| `←` / `D`       | Move the file to `_to_delete`                 |
| `Z`             | Undo the last decision                        |
| `Space`         | Play / stop video (muted)                     |
| `O`             | Open the file in the default program          |
| `L`             | Switch language                               |

## Notes

- Hidden files and system files like `Thumbs.db` are skipped.
- If a file with the same name is already in `_to_delete`, the new one gets a
  suffix like `name (1).ext` instead of overwriting it.
- The language is stored in `~/.keep_or_delete.json`. Delete that file to see
  the language selection again.

## License

MIT, see [LICENSE](LICENSE).
