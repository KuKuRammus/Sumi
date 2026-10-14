#!/usr/bin/env python3
"""Build Sumi from palette.toml and src/.

    ./build.py            build into dist/
    ./build.py install    build, then copy to ~/.themes/Sumi and ~/.config/Kvantum/Sumi

Every text file in src/ is a template: $name becomes the palette color, $name/0.5 the
same color at 50% opacity. Files under src/kvantum/ go to the Kvantum theme, the rest
to the GTK theme. Requires Python 3.11+, nothing else.
"""
import re
import shutil
import sys
import tomllib
from pathlib import Path

NAME = "Sumi"
ROOT = Path(__file__).resolve().parent
SRC, DIST = ROOT / "src", ROOT / "dist"
GTK_OUT, KVANTUM_OUT = DIST / NAME, DIST / "kvantum" / NAME
TEMPLATES = {".css", ".svg", ".kvconfig", ".theme", ""}  # "" = gtkrc

TOKEN = re.compile(r"\$([a-z][a-z0-9_]*)(?:/([0-9]*\.?[0-9]+))?")
HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
CSS_VALUE = re.compile(r"[-\w]+\s*:\s*([^;{}]+)(?=[;}])")


def load_palette():
    palette = tomllib.loads((ROOT / "palette.toml").read_text())
    for name, value in palette.items():
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            sys.exit(f"palette.toml: {name} = {value!r} is not a #rrggbb color")
    return palette


def color(value, alpha, css):
    if alpha is None:
        return value
    a = float(alpha)
    if not 0 <= a <= 1:
        raise ValueError(f"opacity {alpha} is outside 0..1")
    r, g, b = (int(value[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {a:g})" if css else f"{value}{round(a * 255):02x}"


def raw_colors(path, text):
    """Hex colors written directly in a template, which should come from the palette."""
    if path.suffix == ".css":  # only look at declaration values; selectors may contain '#id'
        return [m for v in CSS_VALUE.finditer(text) for m in HEX.findall(v.group(1))]
    return HEX.findall(text)


def render(path, palette, used, errors):
    text = path.read_text()
    rel = path.relative_to(SRC)
    for c in raw_colors(path, text):
        errors.append(f"{rel}: raw color {c}; add it to palette.toml and use $name")

    def sub(m):
        name, alpha = m.groups()
        if name not in palette:
            line = text.count("\n", 0, m.start()) + 1
            errors.append(f"{rel}:{line}: unknown color ${name}")
            return m.group(0)
        used.add(name)
        try:
            return color(palette[name], alpha, path.suffix == ".css")
        except ValueError as e:
            errors.append(f"{rel}: ${name}/{alpha}: {e}")
            return m.group(0)

    return TOKEN.sub(sub, text)


def build():
    palette = load_palette()
    used, errors = set(), []
    shutil.rmtree(DIST, ignore_errors=True)
    for path in sorted(p for p in SRC.rglob("*") if p.is_file()):
        rel = path.relative_to(SRC)
        out = KVANTUM_OUT / rel.relative_to("kvantum") if rel.parts[0] == "kvantum" else GTK_OUT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in TEMPLATES:
            out.write_text(render(path, palette, used, errors))
        else:
            shutil.copy2(path, out)
    for gtk in ("gtk-3.0", "gtk-4.0"):  # dark variant is the same theme
        (GTK_OUT / gtk / "gtk-dark.css").write_text('@import url("gtk.css");\n')
    if errors:
        sys.exit("\n".join(errors))
    for name in palette.keys() - used:
        print(f"note: palette color {name} is not used", file=sys.stderr)
    print(f"built {GTK_OUT.relative_to(ROOT)} and {KVANTUM_OUT.relative_to(ROOT)}")


def install():
    targets = {GTK_OUT: Path.home() / ".local/share/themes" / NAME,
               KVANTUM_OUT: Path.home() / ".config" / "Kvantum" / NAME}
    for src, dst in targets.items():
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)
        print(f"installed {dst}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "build"
    if command not in ("build", "install"):
        sys.exit(__doc__)
    build()
    if command == "install":
        install()
