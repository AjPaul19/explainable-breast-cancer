# Physician user study kit (Objective 4)

**Status: instrument ready, no data collected.** Nothing here is a result.

1. Show case cards from `case_cards/` in the order given by `design.csv`.
2. Record answers in `responses_template.csv`.
3. Run `python analyze_user_study.py responses.csv` -> Wilcoxon signed-rank tests (B vs A per item, Holm-corrected), rank-biserial effect sizes, bootstrap CI.
4. `python analyze_user_study.py --self-test` runs the analysis on synthetic data to prove the code works (the synthetic numbers mean nothing).

Power note: with 20 participants a paired Wilcoxon test detects an effect of about r = 0.6 at 80 % power; smaller effects need more participants.
