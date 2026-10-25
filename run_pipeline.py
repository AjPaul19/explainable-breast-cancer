"""Run the whole study: audit -> tuning -> hold-out -> fairness CV -> SHAP -> artifacts and figures.

    python run_pipeline.py              # full run (~4 min on a laptop)
    python run_pipeline.py --quick      # smoke test (fewer repeats / bootstraps)
    python run_pipeline.py --plots-only # redraw figures from the cached study (artifacts/_study.joblib)
"""
import argparse
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).parent / "src"))

from brca_xai import plots  # noqa: E402
from brca_xai.pipeline import ART, Study  # noqa: E402

CACHE = ART / "_study.joblib"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--plots-only", action="store_true")
    a = ap.parse_args()
    if a.plots_only:
        s = joblib.load(CACHE)
    else:
        s = Study(n_repeats=2, n_boot=150, n_stability=20, tune_iter=10) if a.quick else Study()
        s.run_all()
        s.save()
        joblib.dump(s, CACHE)
    plots.make_all(s)
    print("done: artifacts/ and reports/figures/ are up to date")


if __name__ == "__main__":
    main()
