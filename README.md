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
- **Translatable interface** — English and German included, more languages welcome (see below)

## Installation

You need Python 3.8 or newer. Tkinter ships with Python on Windows and macOS;
on Linux you may need `sudo apt install python3-tk`.

```bash
git clone https://github.com/skullypng/Keep-or-Delete-File-Cleaner.git
cd Keep-or-Delete-File-Cleaner
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
| `L`             | Switch to the next language                   |

## Languages

The language is chosen on first start. You can change it any time with the
language button at the bottom or by pressing `L`. The choice is stored in
`~/.keep_or_delete.json` (delete the file to see the selection again).

Currently included: English, Deutsch.

**Want to add your language?** It takes a few minutes and no programming:
copy `locales/en.json`, translate it and open a pull request. Step-by-step
instructions are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Notes

- Hidden files and system files like `Thumbs.db` are skipped.
- If a file with the same name is already in `_to_delete`, the new one gets a
  suffix like `name (1).ext` instead of overwriting it.

## License

MIT, see [LICENSE](LICENSE).
