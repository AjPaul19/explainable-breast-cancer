"""Run the whole study for the revised proposal.

    python run_pipeline.py                 # both specifications, full run (~10 min)
    python run_pipeline.py --spec proposal # only the primary specification
    python run_pipeline.py --quick         # smoke test (fewer trials / repeats / bootstraps)
    python run_pipeline.py --plots-only    # redraw figures from the cached studies (artifacts/<spec>/_study.joblib)

Specifications: ``proposal`` = predictors exactly as in Table 3.2 of the revised proposal (primary model);
``hardened`` = the same model without the documentation artefacts found by the audit (recommended for any real use).
"""
import argparse
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).parent / "src"))

from brca_xai import plots  # noqa: E402
from brca_xai.pipeline import ART_ROOT, Study  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", choices=["proposal", "hardened", "both"], default="both")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--plots-only", action="store_true")
    a = ap.parse_args()
    for spec in (["proposal", "hardened"] if a.spec == "both" else [a.spec]):
        cache = ART_ROOT / spec / "_study.joblib"
        if a.plots_only:
            s = joblib.load(cache)
        else:
            kw = dict(n_repeats=2, n_boot=150, n_stability=10, n_trials=10) if a.quick else {}
            s = Study(spec, **kw).run_all()
            s.save()
            joblib.dump(s, cache)
        plots.make_all(s)
        print(f"done [{spec}]: artifacts/{spec}/ and reports/figures/{spec}/ are up to date")


if __name__ == "__main__":
    main()
