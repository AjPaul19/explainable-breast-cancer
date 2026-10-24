"""Rebuild the whole content file from the old website:  python tools/build_all.py [crawl-folder]
Steps: mirror_extract (offline copy) -> build_content -> build_sections -> build_mirror. Each step is safe to repeat."""
import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
crawl = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Segun\AppData\Local\Temp\gcmn\old"
for step, args in (("mirror_extract.py", []), ("build_content.py", [crawl]), ("build_sections.py", []), ("build_mirror.py", []), ("build_images.py", [])):
    print("==", step)
    subprocess.run([sys.executable, "-I", os.path.join(here, step)] + args, check=True)
