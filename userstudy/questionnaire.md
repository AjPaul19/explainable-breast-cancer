# Questionnaire (5-point Likert: 1 = strongly disagree ... 5 = strongly agree)

Adapted from the Explanation Satisfaction and Trust scales of Hoffman, Mueller, Klein and Litman (2018).
Answered once per case card.

1. **understand** - I understand why the model produced this risk score.
2. **useful** - The information shown is useful for judging this patient's risk.
3. **confidence** - I am confident that the model's prediction is correct for this patient.
4. **trust** - I trust this model's output for this patient.
5. **plausible** - The reasoning behind the score is clinically plausible.
6. **act** - I would use this output when deciding about follow-up intensity.
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
