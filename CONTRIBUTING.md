# Contributing

Thanks for helping out! The easiest way to contribute is **adding or improving a
translation**. You don't need to know Python for that.

## Add a new language (no Git needed)

1. Open [`locales/en.json`](locales/en.json) and click the **copy** button (top right of the file view).
2. Go to the [`locales`](locales) folder → **Add file → Create new file**.
3. Name it with your language code plus `.json`, e.g. `fr.json`, `es.json`, `pt-BR.json`.
4. Paste the text and translate the **values** (the right side). Do not change the keys (the left side).
5. Change `"language_name"` to the name of your language *in that language* (e.g. `"Français"`).
6. Click **Commit changes…**, choose **Create a new branch / Propose changes**, then **Create pull request**.

GitHub will check your file automatically and tell you if something is wrong.

## Add a language with Git

```bash
# 1. Fork the repo on GitHub, then:
git clone https://github.com/<you>/Keep-or-Delete-File-Cleaner.git
cd Keep-or-Delete-File-Cleaner

# 2. Create your translation
cp locales/en.json locales/fr.json
#    ...translate the values in locales/fr.json...

# 3. Check it
python check_translations.py

# 4. Try it: start the app and press L to switch to your language
python keep_or_delete.py

# 5. Commit, push and open a pull request
git checkout -b add-french
git add locales/fr.json
git commit -m "Add French translation"
git push -u origin add-french
```

## Translation rules

- Keep the **keys** exactly as in `en.json`; only translate the **values**.
- Keep `{placeholders}` such as `{i}`, `{n}`, `{kept}`, `{trash}`, `{name}`, `{err}` unchanged. You may move them within the sentence.
- Keep the shortcut letters in brackets, e.g. `(D)`, `(K)`, `(Z)`, `(O)`, `(L)`. The keys on the keyboard are fixed.
- Keep `\n` (line breaks) and technical commands like `pip install pillow` as they are.
- Save the file as **UTF-8**.
- Keep texts short: they have to fit on buttons.
- You don't have to translate everything. Missing keys fall back to English, but a complete translation is nicer.
- Right-to-left languages (Arabic, Hebrew, ...) may be displayed incorrectly because Tk has limited support for them.

`python check_translations.py` tells you about broken placeholders, unknown keys and missing translations.

## Improve an existing translation

Just edit the file in `locales/` and open a pull request. Typos and better wording are very welcome.

## Other contributions

Bug reports and ideas: please open an [issue](../../issues). For code changes, open an issue first for bigger things, keep the code in English, and run `python check_translations.py` before you push.
