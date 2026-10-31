#!/usr/bin/env python3
"""Check all translation files in ./locales against en.json.

Run:  python check_translations.py

Errors (exit code 1): unreadable JSON, missing 'language_name', unknown keys,
wrong {placeholders}, bad file name.
Warnings: keys that are not translated yet (the app falls back to English).
"""
import json
import os
import re
import string
import sys

LOCALES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
CODE_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")  # fr, es, pt-BR, zh-Hans


def placeholders(text):
    """Names inside {braces}, or None if the braces are malformed."""
    try:
        return {name for _, name, _, _ in string.Formatter().parse(text)
                if name is not None}
    except ValueError:
        return None


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    try:
        reference = load(os.path.join(LOCALES, "en.json"))
    except (OSError, ValueError) as e:
        print(f"ERROR: cannot read locales/en.json: {e}")
        return 1

    errors, warnings = [], []
    filenames = sorted(f for f in os.listdir(LOCALES) if f.endswith(".json"))

    for filename in filenames:
        code = filename[:-5]
        label = f"locales/{filename}"
        if not CODE_RE.match(code):
            errors.append(f"{label}: file name should be a language code "
                          f"like 'fr' or 'pt-BR'")
        try:
            data = load(os.path.join(LOCALES, filename))
        except (OSError, ValueError) as e:
            errors.append(f"{label}: cannot be read ({e})")
            continue
        if not isinstance(data, dict):
            errors.append(f"{label}: must be a JSON object")
            continue
        if not str(data.get("language_name", "")).strip():
            errors.append(f"{label}: missing 'language_name'")

        for key, value in data.items():
            if not isinstance(value, str):
                errors.append(f"{label}: '{key}' must be text")
                continue
            if key not in reference:
                errors.append(f"{label}: unknown key '{key}'")
                continue
            want, got = placeholders(reference[key]), placeholders(value)
            if got is None:
                errors.append(f"{label}: '{key}' has a broken {{ }} placeholder")
            elif got != want:
                errors.append(f"{label}: '{key}' must contain exactly the "
                              f"placeholders {sorted(want)} (found {sorted(got)})")

        missing = [k for k in reference if k not in data]
        if missing:
            warnings.append(f"{label}: {len(missing)} key(s) not translated "
                            f"(English is used): {', '.join(missing)}")

    for w in warnings:
        print("WARNING:", w)
    for e in errors:
        print("ERROR:", e)
    print(f"Checked {len(filenames)} file(s): "
          f"{len(errors)} error(s), {len(warnings)} warning(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
