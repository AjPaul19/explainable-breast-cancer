"""Build the physician user-study kit (Objective 4, proposal 3.2.7) from the fitted primary model.

Creates ``userstudy/``:
  case_cards/       12 patient cases x 2 conditions: A = risk score only, B = risk score + SHAP explanation
  design.csv        counterbalanced assignment of cases to conditions for 24 participant slots
  case_key.csv      researcher-only key (outcome, race, whether the model flagged the patient)
  questionnaire.md  5-point Likert items + open questions
  responses_template.csv
  analyze_user_study.py   Wilcoxon signed-rank analysis, Holm correction, effect sizes (tested on synthetic data)

No clinician has answered yet: nothing in this folder is a result.
"""
import shutil
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brca_xai import data as D  # noqa: E402

OUT = ROOT / "userstudy"
CARDS = OUT / "case_cards"
s = joblib.load(ROOT / "artifacts" / "proposal" / "_study.joblib")
rng = np.random.default_rng(2026)
CW, CB = "#4477AA", "#EE6677"

# ---------------------------------------------------------------- choose 12 cases: 6 Black + 6 White; per race 2 TP, 2 FN... balanced
p = s.oof_mean[s.main]
flag = s.flags[s.main].mean(0) >= 0.5
c = s.c.copy(); c["risk"] = p; c["flag"] = flag
picked = []
for race in ["Black", "White"]:
    for died, fl in [(1, True), (1, False), (0, True), (0, False)]:
        pool = c[(c.race == race) & (c[D.TARGET] == died) & (c.flag == fl)]
        n = 2 if (died, fl) in [(1, True), (0, False)] else 1
        pool = pool.iloc[np.argsort(np.abs(pool.risk.to_numpy() - pool.risk.median()))]       # typical, not extreme, cases
        picked += list(pool.index[:n])
picked = picked[:12]
order = rng.permutation(len(picked))
picked = [picked[i] for i in order]


def summary(i):
    r = c.loc[i]
    f = lambda v, fmt="{:.0f}": "not recorded" if pd.isna(v) else fmt.format(v)
    return [("Age at diagnosis", f(r.age)), ("Tumour size (T)", f(r.t_stage)), ("Lymph nodes (N)", f(r.n_stage)),
            ("Distant metastasis (M)", "M1" if r.m_stage == 1 else ("M0" if r.m_stage == 0 else "not recorded")),
            ("PAM50 subtype", r.subtype if isinstance(r.subtype, str) else "not called"), ("Histology", r.histology),
            ("Radiation therapy", {1.0: "yes", 0.0: "no"}.get(r.radiation, "not recorded"))]


def card(i, k, cond):
    sv = s.sv[s.main].iloc[i]
    thr = s.fits[s.main].thresholds["global"]
    risk = float(s.fits[s.main].proba(s.X.iloc[[i]])[0])
    fig = plt.figure(figsize=(10, 4.2) if cond == "B" else (5.4, 4.2))
    gs = fig.add_gridspec(1, 2 if cond == "B" else 1, width_ratios=[1, 1.35] if cond == "B" else [1])
    a0 = fig.add_subplot(gs[0]); a0.axis("off")
    a0.text(0, 1.0, f"Case {k + 1}", fontsize=14, fontweight="bold", va="top")
    for j, (lab, val) in enumerate(summary(i)):
        a0.text(0, .86 - j * .075, lab, fontsize=9, color="#555"); a0.text(.55, .86 - j * .075, val, fontsize=9.5, fontweight="bold")
    a0.text(0, .26, "Model output", fontsize=9, color="#555")
    a0.text(0, .15, f"Predicted risk of death during follow-up: {risk:.0%}", fontsize=10.5, fontweight="bold")
    a0.text(0, .06, "Model recommendation: " + ("FLAG for closer follow-up" if risk >= thr else "no flag"), fontsize=10.5, fontweight="bold",
            color=CB if risk >= thr else CW)
    if cond == "B":
        a1 = fig.add_subplot(gs[1])
        top = sv.abs().sort_values(ascending=False).head(6).index
        vals = list(sv[top]) + [sv.drop(top).sum()]
        names = [f"{D.LABELS[f]} = {s.X.iloc[i][f]:g}" if pd.notna(s.X.iloc[i][f]) else f"{D.LABELS[f]} = not recorded" for f in top] + ["all other features"]
        y = np.arange(len(vals))[::-1]
        a1.barh(y, vals, color=[CB if v > 0 else CW for v in vals], height=.6)
        a1.set_yticks(y, names, fontsize=8.5); a1.axvline(0, color="#666", lw=1)
        a1.set_xlabel("effect on risk (log-odds): red raises, blue lowers", fontsize=8.5)
        a1.set_title("Why did the model give this score?", fontsize=10, fontweight="bold")
        for sp in ("top", "right"):
            a1.spines[sp].set_visible(False)
    fig.savefig(CARDS / f"case{k + 1:02d}_{cond}.png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return risk


shutil.rmtree(OUT, ignore_errors=True)
CARDS.mkdir(parents=True)
key = []
for k, i in enumerate(picked):
    risk = card(i, k, "A"); card(i, k, "B")
    key.append(dict(case=k + 1, patient_id=c.loc[i, "patient_id"], race=c.loc[i, "race"], died=int(c.loc[i, D.TARGET]), model_risk=round(risk, 3),
                    flagged=int(risk >= s.fits[s.main].thresholds["global"])))
pd.DataFrame(key).to_csv(OUT / "case_key.csv", index=False)

# ---------------------------------------------------------------- counterbalanced design (6 cases per condition per participant; order randomised)
rows = []
for pid in range(1, 25):
    b_cases = set(rng.choice(np.arange(1, 13), 6, replace=False)) if pid % 2 else None
    if pid % 2 == 0:                                               # mirror of the previous participant
        b_cases = set(range(1, 13)) - set(prev)
    prev = b_cases if pid % 2 else prev
    order = rng.permutation(np.arange(1, 13))
    for pos, cs in enumerate(order, 1):
        rows.append(dict(participant=f"P{pid:02d}", position=pos, case=int(cs), condition="B" if cs in b_cases else "A"))
pd.DataFrame(rows).to_csv(OUT / "design.csv", index=False)

items = [("understand", "I understand why the model produced this risk score."),
         ("useful", "The information shown is useful for judging this patient's risk."),
         ("confidence", "I am confident that the model's prediction is correct for this patient."),
         ("trust", "I trust this model's output for this patient."),
         ("plausible", "The reasoning behind the score is clinically plausible."),
         ("act", "I would use this output when deciding about follow-up intensity.")]
pd.DataFrame(columns=["participant", "case", "condition"] + [k for k, _ in items] + ["decision_flag_followup", "comment"]).to_csv(OUT / "responses_template.csv", index=False)
(OUT / "questionnaire.md").write_text(f"""# Questionnaire (5-point Likert: 1 = strongly disagree ... 5 = strongly agree)

Adapted from the Explanation Satisfaction and Trust scales of Hoffman, Mueller, Klein and Litman (2018).
Answered once per case card.

{chr(10).join(f'{n + 1}. **{k}** - {t}' for n, (k, t) in enumerate(items))}
7. Would you recommend closer follow-up for this patient? (yes / no) - recorded as `decision_flag_followup`.

## Final open questions (after all 12 cases)
1. Which explanation elements helped most? Which were confusing?
2. Were there cases where the explanation made you trust the model *less*? Why?
3. Did any explanation contradict your clinical knowledge? Describe.
4. What would you need to see before relying on such a tool in practice?
5. Does it matter to you that the model uses race or whether race was recorded? Why?

## Protocol summary
* Within-subject: every participant sees 6 cases as card A (score only) and 6 as card B (score + SHAP); the assignment is mirrored for
  consecutive participants and the case order is randomised (`design.csv`).
* Participants: 15-30 practising oncologists, breast surgeons, pathologists and radiologists, purposively sampled. Exploratory study.
* Primary outcome: paired difference B - A in `trust` and `understand`; secondary: the other items, and agreement with the model flag.
* Cases are real de-identified TCGA patients selected to be typical (not extreme) and balanced by race and by outcome / model flag
  (`case_key.csv` is for the researcher only).
* Ethical approval and informed consent are required before any recruitment (Nigeria Data Protection Act 2023).
""", encoding="utf-8")

shutil.copy(ROOT / "tools" / "analyze_user_study.py", OUT / "analyze_user_study.py")
(OUT / "README.md").write_text("""# Physician user study kit (Objective 4)

**Status: instrument ready, no data collected.** Nothing here is a result.

1. Show case cards from `case_cards/` in the order given by `design.csv`.
2. Record answers in `responses_template.csv`.
3. Run `python analyze_user_study.py responses.csv` -> Wilcoxon signed-rank tests (B vs A per item, Holm-corrected), rank-biserial effect sizes, bootstrap CI.
4. `python analyze_user_study.py --self-test` runs the analysis on synthetic data to prove the code works (the synthetic numbers mean nothing).

Power note: with 20 participants a paired Wilcoxon test detects an effect of about r = 0.6 at 80 % power; smaller effects need more participants.
""", encoding="utf-8")
print("user-study kit written:", OUT, len(list(CARDS.glob('*.png'))), "cards")
