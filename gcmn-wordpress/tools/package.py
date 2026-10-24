"""Build installable zips: dist/gcmn-core.zip (plugin) and dist/gcmn-theme.zip (theme).
Test fixtures in tools/ are never included. Run:  python tools/package.py
"""
import pathlib
import zipfile

root = pathlib.Path(__file__).resolve().parent.parent
dist = root / "dist"
dist.mkdir(exist_ok=True)

for name in ("gcmn-core", "gcmn-theme"):
    out = dist / f"{name}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((root / name).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".bak":
                z.write(f, f.relative_to(root).as_posix())
    print(out.name, round(out.stat().st_size / 1024), "KB")
