"""Analyse the physician user study (proposal 3.2.7): paired comparison of condition A (risk only) and B (risk + SHAP).

    python analyze_user_study.py responses.csv
    python analyze_user_study.py --self-test        # synthetic data, checks the code only
"""
import sys

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

ITEMS = ["understand", "useful", "confidence", "trust", "plausible", "act"]


def analyse(df: pd.DataFrame, n_boot: int = 2000, seed: int = 0) -> pd.DataFrame:
    """One row per item.  Responses are first averaged within participant x condition (the unit of analysis is the participant)."""
    per = df.groupby(["participant", "condition"])[ITEMS].mean().unstack("condition")
    rng = np.random.default_rng(seed)
    rows = []
    for it in ITEMS:
        a, b = per[(it, "A")].dropna(), per[(it, "B")].dropna()
        idx = a.index.intersection(b.index)
        a, b = a.loc[idx], b.loc[idx]
        d = (b - a).to_numpy()
        nz = d[d != 0]
        if len(nz) >= 1:
            stat, p = wilcoxon(b, a, zero_method="wilcox", alternative="two-sided", method="auto")
        else:
            p = np.nan
        ranks = pd.Series(np.abs(nz)).rank().to_numpy() if len(nz) else np.array([])
        rbc = float((ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum()) if len(ranks) else np.nan   # matched-pairs rank-biserial
        boot = [rng.choice(d, len(d)).mean() for _ in range(n_boot)]
        rows.append(dict(item=it, n=len(d), mean_A=a.mean(), mean_B=b.mean(), mean_diff=d.mean(),
                         ci_lo=np.percentile(boot, 2.5), ci_hi=np.percentile(boot, 97.5), p=p, rank_biserial=rbc))
    t = pd.DataFrame(rows)
    # Holm step-down correction
    order = t.p.rank(method="first").fillna(len(t)).astype(int)
    m = t.p.notna().sum()
    holm = pd.Series(np.nan, index=t.index)
    srt = t.p.sort_values().dropna()
    run = 0.0
    for k, (i, pv) in enumerate(srt.items()):
        run = max(run, min(1.0, (m - k) * pv)); holm[i] = run
    t["p_holm"] = holm
    return t


def agreement(df: pd.DataFrame, key: pd.DataFrame) -> pd.DataFrame:
    """Share of 'flag for follow-up' decisions that match the model flag, by condition (secondary outcome)."""
    d = df.merge(key[["case", "flagged"]], on="case")
    d["agree"] = (d.decision_flag_followup.astype(int) == d.flagged).astype(int)
    return d.groupby("condition").agree.mean().to_frame("agreement_with_model_flag")


def self_test():
    rng = np.random.default_rng(1)
    rows = []
    for p in range(20):
        base = rng.normal(3.0, .5)
        for case in range(1, 13):
            cond = "B" if (case + p) % 2 else "A"
            row = dict(participant=f"S{p:02d}", case=case, condition=cond)
            for it in ITEMS:
                row[it] = int(np.clip(round(base + (0.8 if (cond == "B" and it in ("understand", "plausible")) else 0.0) + rng.normal(0, .8)), 1, 5))
            row["decision_flag_followup"] = int(rng.random() < .5)
            rows.append(row)
    res = analyse(pd.DataFrame(rows))
    print(res.round(3).to_string(index=False))
    assert res.set_index("item").loc["understand", "mean_diff"] > 0 and res.set_index("item").loc["understand", "p"] < 0.05
    print("self-test passed (synthetic data: the numbers carry no meaning)")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        print(analyse(pd.read_csv(sys.argv[1])).round(3).to_string(index=False))
