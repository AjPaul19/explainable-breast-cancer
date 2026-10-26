"""Build Chapters_3_4_5.docx (Methodology, Implementation and Results, Conclusions) from the artifacts.

Follows the structure of the revised proposal (Chapter 3 sections 3.2.1-3.2.11).  Every number is read from
``artifacts/``; the ``check`` calls assert the qualitative claims the prose relies on, so a re-run that changes the
picture stops the build instead of printing a stale conclusion.  Figure / table references are generated, not typed.
"""
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

import common as C
from common import KEYS, SHORT, pct

P, H = C.load()
FL, META = P.FL, P.meta
OUT = C.ROOT / "Chapters_3_4_5.docx"
EQ = META["explain_quality"]
SURV = META["survival"]
MAINM = "XGBoost (race-aware, primary)"


def check(cond, msg):
    if not cond:
        raise SystemExit(f"CLAIM NO LONGER HOLDS - rewrite the text: {msg}")


# ------------------------------------------------------------------ numbers used repeatedly
abl = P.ablation.set_index("variant")
ABL0, ABL_RT = abl.iloc[0].auc, abl.iloc[1].auc
lad = P.ladder
miss = P.miss.set_index("column")
rad, racem = miss.loc["RADIATION_THERAPY"], miss.loc["RACE"]
nxr = miss.loc["PATH_N_STAGE = NX"]; mxr = miss.loc["PATH_M_STAGE = MX"]
t1 = P.table1.set_index("characteristic")
rs = P.race_shap.set_index("patients")
unk = rs.loc["race NOT recorded"]
te = P.test_metrics
g_tpr, g_fpr = P.cv("aware", "tpr_gap"), P.cv("aware", "fpr_gap")
eods = {k: P.cv(k, "eod")[0] for k in KEYS}

check(P.align.feature.iloc[0] == "Radiation therapy", "radiation is the top SHAP feature of the as-proposed model")
check(ABL0 - ABL_RT > 0.04, "removing radiation lowers AUC by > 0.04")
check(g_tpr[1] < 0 < g_tpr[2], "baseline recall gap CI spans 0")
HW = (g_tpr[2] - g_tpr[1]) / 2          # half-width of the recall-gap CI
ms = P.msens
check(ms is not None and (ms[(ms.strategy == "blind") & (ms.metric == "tpr_gap")].estimate < 0).all(), "race-blind lowers the recall gap in every near-equivalent configuration")
check((ms[(ms.strategy == "gthr") & (ms.metric == "tpr_gap")].estimate.abs() < 0.03).all(), "group thresholds keep the recall gap within 3 points in every configuration")
for m_ in (24, 36, 60):
    check(P.sens_(m_, "aware", "fpr_gap")[1] < 0 < P.sens_(m_, "aware", "fpr_gap")[2], f"settled-outcome false-alarm gap CI spans 0 ({m_} mo)")
check(abs(META["risk_gap_total"]) < 0.02, "opposing terms cancel in the mean score gap")
check(g_fpr[1] < 0 < g_fpr[2], "baseline false-alarm gap CI spans 0")
check(P.paired_("reweigh", "tpr_gap")[2] < 0, "reweighing lowers Black recall relative to the baseline (paired CI below 0)")
check(min(eods, key=eods.get) in ("gthr", "reweigh_gthr"), "a group-threshold strategy has the smallest equalised-odds difference")
check(unk.share_of_total_attribution > 0.25, "race-not-recorded carries > 25 % of attribution")
check(P.direction.agrees.dropna().all(), "SHAP direction agrees with the clinical prior")
check(H.ov("aware", "auc_roc")[0] < P.ov("aware", "auc_roc")[0] - 0.03, "hardened AUC clearly below as-proposed AUC")
check(P.tm(MAINM, "recall")[2] >= 0.80, "the 80 % target lies inside the hold-out recall interval")

# ------------------------------------------------------------------ document plumbing
doc = Document()
st = doc.styles
st["Normal"].font.name = "Times New Roman"; st["Normal"].font.size = Pt(12)
st["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
for name, size in [("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)]:
    st[name].font.name = "Times New Roman"; st[name].font.size = Pt(size); st[name].font.bold = True
    st[name].font.color.rgb = RGBColor(0, 0, 0); st[name]._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
sec = doc.sections[0]
sec.left_margin = sec.right_margin = Inches(1); sec.top_margin = sec.bottom_margin = Inches(1)
fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = fp.add_run()
for tag, txt in [("begin", None), (None, "PAGE"), ("end", None)]:
    if tag:
        el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), tag)
    else:
        el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = txt
    run._r.append(el)

# ordered registries -> generated references ("Figure 4.7")
FIGS = {"3": ["workflow", "framework"],
        "4": ["survival", "leakage", "ablation", "benchmark", "curve", "forest", "pr", "beeswarm", "dependence", "wf_tp", "wf_fn", "wf_tn",
              "deletion", "racemiss", "rates", "gaps", "tradeoff", "sweep", "roc", "calib", "sensitivity", "holdout_race", "imp_race",
              "gapdecomp", "profile", "stability", "mitig", "h_rates", "h_beeswarm"]}
TABS = {"3": ["objectives", "variables", "strategies", "software"],
        "4": ["cohort", "missing", "ladder", "specs", "bench", "test", "rules", "explq", "fair", "paired", "msens", "calib", "holdrace", "compare"]}
fig_n, tab_n = {"3": 0, "4": 0}, {"3": 0, "4": 0}


def fr(key):
    for ch, lst in FIGS.items():
        if key in lst:
            return f"Figure {ch}.{lst.index(key) + 1}"
    raise KeyError(key)


def tr(key):
    for ch, lst in TABS.items():
        if key in lst:
            return f"Table {ch}.{lst.index(key) + 1}"
    raise KeyError(key)


def H1(t): doc.add_heading(t, 1)
def H2(t): doc.add_heading(t, 2)
def H3(t): doc.add_heading(t, 3)


def para(t, bold=False, italic=False, size=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6); p.paragraph_format.line_spacing = 1.15
    r = p.add_run(t); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def bullets(items):
    for t in items:
        p = doc.add_paragraph(style="List Bullet"); p.paragraph_format.space_after = Pt(2)
        if isinstance(t, tuple):
            r = p.add_run(t[0]); r.bold = True; p.add_run(t[1])
        else:
            p.add_run(t)


def caption(kind, ch, key, text):
    reg, cnt = (FIGS, fig_n) if kind == "Figure" else (TABS, tab_n)
    cnt[ch] += 1
    assert reg[ch][cnt[ch] - 1] == key, f"{kind} order mismatch: expected {reg[ch][cnt[ch] - 1]}, got {key}"
    p = doc.add_paragraph(); r = p.add_run(f"{kind} {ch}.{cnt[ch]}: {text}"); r.bold = True; r.font.size = Pt(10.5)
    p.paragraph_format.space_after = Pt(8)
    return p


def figure(ch, key, fname, text, width=6.2, spec=P):
    f = spec.fig / fname
    assert f.exists(), f
    doc.add_picture(str(f), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption("Figure", ch, key, text).alignment = WD_ALIGN_PARAGRAPH.CENTER


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), color); tcPr.append(sh)


def table(ch, key, text, df, widths=None, size=9):
    caption("Table", ch, key, text)
    t = doc.add_table(rows=1, cols=len(df.columns)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(df.columns):
        cell = t.rows[0].cells[i]; cell.text = ""; r = cell.paragraphs[0].add_run(str(c)); r.bold = True; r.font.size = Pt(size); shade(cell, "E8ECF1")
    for _, row in df.iterrows():
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""; r = cells[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def ci3(est, lo, hi, d=2):
    return f"{est:.{d}f} ({lo:.{d}f}-{hi:.{d}f})"


# =============================================================================================
# COVER NOTE
# =============================================================================================
tp = doc.add_paragraph(); tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = tp.add_run("UTILIZING SHAP TO EXPLAIN AN XGBOOST MODEL THAT PREDICTS DEATH DURING FOLLOW-UP IN BREAST CANCER"); r.bold = True; r.font.size = Pt(15)
para("Chapters 3, 4 and 5: Methodology, Implementation and Results, Conclusions", bold=True).alignment = WD_ALIGN_PARAGRAPH.CENTER
para("Department of Computer Science, University of Jos, Plateau State, Nigeria. Supervisors: Dr. G. Nentawe and Prof. A. C. Deme", italic=True).alignment = WD_ALIGN_PARAGRAPH.CENTER
para("These chapters implement the revised proposal (prognostic target; Section 3.2 of the revised proposal). They add one extension that is not among its five objectives, "
     "a Black-versus-White fairness audit with bias mitigation, and they report the proposal's predictor list as specified next to an audit-hardened variant. In the thesis the proposal's "
     "\"4.0 Conclusion\" becomes Chapter 5.", italic=True, size=10.5)
doc.add_page_break()

# =============================================================================================
# CHAPTER 3
# =============================================================================================
H1("3.0 Methodology")
H2("3.1 Introduction")
para("This chapter describes how the five objectives of the study were achieved. The work has two phases. Phase 1 is a computational experiment (Objectives 1 to 3): an XGBoost classifier is developed, evaluated and "
     "explained with SHapley Additive exPlanations (SHAP) on clinical data from The Cancer Genome Atlas (TCGA). Phase 2 is a physician user study (Objective 4); the instrument and analysis code are complete but no clinician has yet "
     "responded. Both phases inform a conceptual framework (Objective 5). Because every patient has a diagnosed malignancy, the task is prognostic (mortality-risk prediction), not diagnostic. "
     "One extension is added: an audit of racial fairness between Black and White patients, with a comparison of bias-mitigation strategies.")
H2("3.2 Research design")
para(f"The design is mixed-methods and two-phase. In Phase 1 the TCGA-BRCA clinical patient table is audited, cleaned and split 80/20 into development and hold-out sets; XGBoost is tuned and trained to predict overall-survival status; "
     f"its performance is compared with baseline models; and SHAP explains its predictions ({fr('workflow')}, {tr('objectives')}). Throughout, the recall metric is prioritised: a missed death is a more costly error than an unnecessary review.")
figure("3", "workflow", "00_workflow.png", "Workflow of the study", 6.5)
table("3", "objectives", "Objectives, methods and outputs", pd.DataFrame([
    ["1. Develop the model", "Stratified 80/20 split; repeated stratified 5-fold CV; Bayesian hyper-parameter search; class weighting; recall-first decision threshold", "Tuned XGBoost model (Sections 3.2.4, 4.5)"],
    ["2. Evaluate performance", "Accuracy, precision, recall, F1, AUC-ROC, PR-AUC, confusion matrix with bootstrap CIs; baselines", "Performance results (Sections 3.2.5, 4.6)"],
    ["3. Apply and assess SHAP", "TreeSHAP; global and local plots; fidelity, stability, clinical alignment, race check", "Interpretation of key prognostic features (Sections 3.2.6, 4.7)"],
    ["4. User study", "Within-subject questionnaire, condition A (score) vs B (score + SHAP)", "Kit and analysis code (Section 3.2.8); data not yet collected"],
    ["5. Conceptual framework", "Synthesis of Objectives 1-4", "Framework and discussion (Sections 3.2.9, 4.11)"],
    ["Extension: fairness", "5 mitigation strategies x repeated CV, paired bootstrap, sensitivity analyses", "Bias audit (Sections 3.2.7, 4.8)"]],
    columns=["Objective", "Method", "Output"]), widths=[1.5, 3.3, 1.7])

H3("3.2.1 Data collection")
para(f"The data are the TCGA PanCancer Atlas clinical patient table for breast cancer distributed by cBioPortal (Cerami et al., 2012; Liu et al., 2018): {FL['n_records']:,} patients and 38 variables, with a data dictionary. "
     f"All patients have a malignant tumour (ICD-O-3 morphology codes ending in /3). The target is overall-survival status (OS_STATUS): {FL['n_deaths']} patients ({pct(FL['prevalence'])}) are deceased and {FL['n_records'] - FL['n_deaths']} living at last contact. "
     f"The data are public and de-identified. Self-reported race gives the fairness groups: {FL['n_white']} White ({FL['deaths_white']} deaths) and {FL['n_black']} Black ({FL['deaths_black']} deaths); "
     f"{FL['n_asian']} Asian and {FL['n_unknown_race']} patients without recorded race are used for training but not audited.")
H3("3.2.2 Variable selection and leakage control")
para("Only variables available at or near diagnosis and primary treatment are predictors; variables recorded during follow-up or derived from the outcome are excluded (Kaufman et al., 2011). "
     f"{tr('variables')} reproduces the decisions of the revised proposal and adds the audit result for each.")
table("3", "variables", "Variable selection decisions (revised proposal, Table 3.2) with audit notes", pd.DataFrame([
    ["Included", "Diagnosis age; PAM50 subtype; AJCC pathologic T, N, M; histology (ductal / lobular / other); race; radiation therapy; neoadjuvant therapy; prior diagnosis",
     "Radiation therapy: blanks carry the outcome. NX / MX codes and race-not-recorded likewise (Section 4.4)"],
    ["Excluded: outcome-related", "OS months; DSS, DFS, PFS status and months; person neoplasm cancer status; new tumour event; days to last follow-up", "Leakage; reproduced in the leakage ladder"],
    ["Excluded: redundant or sparse", "Composite AJCC stage (used in a sensitivity model); days to birth; genetic ancestry (used in a sensitivity analysis); ethnicity (169 missing)", "Ethnicity blanks track the outcome too"],
    ["Excluded: uninformative", "Identifiers, cancer type, ICD-10, ICD-O-3 site, consent flag, form date, AJCC edition, pathway flag, weight (100 % missing), sex (98.9 % female)", "-"]],
    columns=["Category", "Variables", "Audit note"]), widths=[1.3, 3.5, 1.7])
para("The primary model uses T, N and M and omits the composite stage so that SHAP does not split credit between correlated variables; a sensitivity model uses stage group instead (Section 4.4).")
H3("3.2.3 Data preprocessing")
para("Technical codes (TX, NX, MX, STAGE X) and blanks are set to missing, and AJCC labels are harmonised (IIA to II, N1A to 1, T1C to 1, cM0(I+) to 0). XGBoost handles missing values natively, so no imputation is applied. "
     f"Subtype is missing for {int(miss.loc['SUBTYPE', 'n_missing'])} patients ({miss.loc['SUBTYPE', 'pct_missing']:.1f}%); a complete-case sensitivity analysis checks the effect. Ordinal variables are ordinally encoded, nominal variables one-hot encoded; "
     "feature scaling is not needed for trees and is applied only inside the logistic-regression baseline. All preprocessing is fitted on training data only. An audit-hardened specification additionally drops radiation and neoadjuvant therapy "
     "and sets NX and MX to N0 and M0 (the AJCC default); it exists to quantify the documentation artefacts discussed in Section 4.4.")
H3("3.2.4 Model development")
bullets([("Data split. ", f"Stratified 80/20 by race group x outcome: {FL['n_dev']} development and {FL['n_test']} hold-out patients (the hold-out set holds {FL['test_deaths']} deaths, of which {FL['test_black_deaths']} in Black patients); performance is therefore reported with bootstrap 95 % confidence intervals (1,000 resamples)."),
         ("Class imbalance. ", f"With {pct(FL['prevalence'])} of patients deceased, class weighting (scale_pos_weight = negatives / positives = {FL['spw']:.1f} in the development set) is used, not synthetic oversampling. Consequently raw scores are not probabilities; Section 4.8.5 recalibrates them."),
         ("Hyper-parameter tuning. ", f"Bayesian search (tree-structured Parzen estimator; Optuna), 60 trials, over learning rate, depth (1-3), number of trees, minimum child weight, subsampling and L1 / L2 regularisation, scored by repeated stratified 5-fold cross-validation (4 repeats) on the development set. The objective is aligned with the recall-first design: the lowest false-positive rate at 80 % recall."),
         ("Overfitting control. ", "Regularisation, a small search space, the number of trees chosen inside cross-validation (cross-validated early stopping), and a comparison of training, cross-validated and hold-out AUC along the boosting path."),
         ("Monotone constraints. ", "Larger T, N, M or stage group can never lower predicted risk, a clinical prior fixed before looking at results."),
         ("Decision threshold. ", f"Recall-first: the threshold is the highest score that still catches at least 80 % of deaths in out-of-fold training predictions (2 x 5-fold), and is therefore learned without any test data. The proposal's phrase \"acceptable precision\" is operationalised as a floor of 1.25 times the training prevalence ({FL['precision_floor']:.2f}); the chosen threshold must clear it. Alternative rules (maximum recall at the precision floor, F2, Youden, 0.5) are compared (Section 4.6)."),
         ("Baselines. ", "Logistic regression, random forest and a stage-only logistic model, tuned by the same repeated 5-fold CV, with thresholds from the same recall-first rule. Seeds are fixed (42).")])
H3("3.2.5 Performance evaluation")
para(f"The final model is evaluated once on the hold-out set with accuracy, precision, recall, F1-score, AUC-ROC and PR-AUC, a confusion matrix, and bootstrap confidence intervals. Because {pct(1 - FL['prevalence'], 0)} of patients are living, "
     f"a model that always predicts \"living\" has about {pct(1 - FL['test_deaths'] / FL['n_test'], 0)} accuracy on the hold-out set, so accuracy is interpreted against that baseline and recall, PR-AUC (no-skill value equal to the prevalence) and balanced accuracy are emphasised. "
     "Because a single hold-out set holds only 30 deaths, the headline operating characteristics are also estimated by 5 x 5-fold repeated cross-validation over all patients, in which every threshold is learned inside the training folds.")
H3("3.2.6 Explainability integration")
para("TreeSHAP (Lundberg et al., 2020) is applied to the final model. Global explanations use summary (beeswarm) and mean-absolute-SHAP plots; dependence plots show how feature values act; local explanations use waterfall plots for a true positive, a false negative and a true negative. The explanations are assessed as follows.")
bullets([("Fidelity. ", "Base value plus the sum of SHAP values must reproduce the model margin for every patient (local accuracy). A deletion test supplements this guarantee with a faithfulness check: blanking each patient's k most-attributed features should lower AUC more than blanking k random features."),
         ("Stability. ", "Spearman rank correlation of global importance across ten cross-validation fold models and across 100 bootstrap refits, and agreement with XGBoost's built-in gain, weight and cover importances."),
         ("Clinical alignment. ", "Comparison of the top-ranked features with established prognostic factors (age, nodal status, tumour size, metastasis, molecular subtype), and a check that the direction of each staging effect matches clinical expectation."),
         ("Fairness check. ", "The SHAP attribution carried by the race columns, separately for patients whose race is recorded and not recorded.")])
H3("3.2.7 Fairness audit and bias mitigation (extension)")
para("White patients are the reference group and Black patients the focus group. The primary criterion is equal opportunity (Hardt et al., 2016): among patients who die, the share flagged (recall) should not depend on race. "
     "Secondary criteria are the false-alarm rate among survivors, the equalised-odds difference (the larger absolute gap), discrimination within each group (AUC) and calibration within each group after one shared recalibration. Gaps are Black minus White. "
     f"Five strategies are compared ({tr('strategies')}); reweighing follows Kamiran and Calders (2012) and group thresholds are the post-processing route to equal opportunity.")
table("3", "strategies", "Strategies compared (same XGBoost settings)", pd.DataFrame([[SHORT[k], META["strategies"][k]["family"], META["strategies"][k]["note"]] for k in KEYS],
                                                                                    columns=["Strategy", "Family", "Description"]), widths=[1.9, 1.1, 3.5])
para("Uncertainty. With 30 Black deaths a recall estimate carries a margin of about 15 percentage points. Rates therefore carry 95 % percentile bootstrap intervals (1,000 resamples stratified by group) over 5 x 5-fold cross-validated decisions, "
     "and differences between strategies use a paired bootstrap on identical resamples (Efron and Tibshirani, 1993). Sensitivity analyses: the recall target (70-95 %); restricting evaluation to patients whose outcome is settled (died, or followed at least 24, 36 or 60 months); "
     "defining groups by genetic ancestry (Carrot-Zhang et al., 2020) instead of self-reported race.")
H3("3.2.8 Physician user study (Objective 4)")
para("The design follows the revised proposal. Participants: 15 to 30 practising oncologists, pathologists, radiologists and breast surgeons recruited by purposive sampling (exploratory). Design: within-subject; each participant reviews 12 real, de-identified, typical cases "
     "(six Black, six White; balanced by outcome and by model flag), six as condition A (predicted risk and recommendation only) and six as condition B (the same plus a SHAP waterfall), with assignment mirrored across consecutive participants and case order randomised. "
     "Instrument: six 5-point Likert items (understandability, usefulness, confidence, trust, plausibility, intention to act) adapted from the explanation-satisfaction and trust scales of Hoffman et al. (2018), a follow-up decision, and open questions. "
     "Analysis: participant-level means, Wilcoxon signed-rank tests for B versus A with Holm correction, rank-biserial effect sizes, bootstrap intervals, and thematic analysis of free text. With 20 participants the test detects only large effects (about r = 0.6 at 80 % power). "
     "The kit (case cards, design table, questionnaire, response template and analysis script, tested on synthetic data) is in the userstudy folder. No participant data exist yet.")
H3("3.2.9 Conceptual framework design")
para(f"Using Sections 3.2.4 to 3.2.8, a conceptual framework shows where SHAP fits in a clinical decision-support pipeline: data input, risk prediction, explanation, clinician review, decision and feedback ({fr('framework')}). "
     "Two additional gates came out of the implementation: a governance gate before data enter the model, and trust checks (fidelity, stability, direction, race attribution) before explanations reach a clinician. The framework is conceptual; it is not deployed or clinically validated.")
figure("3", "framework", "20_conceptual_framework.png", "Conceptual framework: SHAP in a clinical decision-support pipeline, with governance and monitoring gates", 6.4)
H3("3.2.10 Discussion, implications and contributions")
para("Quantitative results (performance, SHAP quality, fairness) and, when available, user-study findings are synthesised in Chapters 4 and 5.")
H3("3.2.11 Ethical considerations")
para("The TCGA data are public and de-identified; no re-identification is attempted. Ethical approval will be sought from the relevant institutional review board before the user study, participants will give informed consent, take part voluntarily and anonymously, "
     "and responses will be stored securely and reported in aggregate, in line with the Nigeria Data Protection Act (2023) and with reference to GDPR and HIPAA. The model is positioned as decision support and not as a replacement for clinical judgement. "
     "Race is used as an audit variable and, as in the proposal, as a predictor whose contribution is tested; no biological effect of race is claimed, and strategies that need race at prediction time are labelled as such.")
H3("3.2.12 Methodological limitations")
para(f"Variable follow-up (median {FL['median_followup']:.0f} months, maximum {FL['max_followup']:.0f}; {pct(FL['living_lt60'], 0)} of living patients under 60 months) means a binary status ignores censoring; "
     f"Section 4.8.6 quantifies this with settled-outcome analyses and an exploratory survival model (Harrell C-index {SURV['c_index_cox']:.2f} for XGBoost with a Cox objective against {SURV['c_index_binary']:.2f} for the binary score; formal survival modelling remains future work). "
     "Overall survival includes non-cancer deaths. Clinical variables give moderate discrimination, so the main contribution lies in interpretability and the audit. The cohort is a single, predominantly European-ancestry study.")
H2("3.3 Expected outcomes")
bullets(["A tuned XGBoost model with documented handling of imbalance, overfitting and leakage.", "A quantitative evaluation with bootstrap intervals and baselines.",
         "Interpretable SHAP explanations with fidelity, stability and clinical-alignment evidence.", "Evidence from the physician study on interpretability and trust (pending).",
         "A conceptual framework for SHAP in clinical prognostic pipelines.", "An audit of racial fairness and of bias-mitigation options."])
H2("3.4 Implementation, software and reproducibility")
v = META["versions"]
table("3", "software", "Software environment", pd.DataFrame([["Python", "3.12"], ["xgboost", v["xgboost"]], ["shap", v["shap"]], ["scikit-learn", v["sklearn"]], ["optuna", v["optuna"]],
                                                              ["pandas", v["pandas"]], ["Streamlit / Plotly", "dashboard"], ["python-docx", "document builder"]], columns=["Component", "Version / role"]), widths=[2, 4.5])
para("One command (python run_pipeline.py) regenerates every table, figure and model for both specifications; the notebook, the dashboard and these chapters read the same artifacts.")
H2("3.5 Resources required")
bullets(["Access to the clinical dataset (public).", "A laptop-class computer (the full study runs in about 15 minutes).", "Collaboration with healthcare institutions for the user study."])
doc.add_page_break()

# =============================================================================================
# CHAPTER 4
# =============================================================================================
H1("4.0 Implementation and Results")
H2("4.1 Introduction")
para("This chapter reports what was built and found. Sections 4.3 and 4.4 describe the cohort and the data audit; 4.5 to 4.7 the model, its performance and its explanations (Objectives 1 to 3); 4.8 the fairness extension; "
     "4.9 the audit-hardened specification; 4.10 the dashboard, user-study kit and framework (Objectives 4 and 5); and 4.11 a discussion. Unless stated, intervals are 95 % intervals and gaps are Black minus White.")
H2("4.2 Implementation environment")
para("The code is a Python package (src/brca_xai: data, audit, modeling, evaluate, fairness, explain, plots, pipeline), a command-line runner, an executed Jupyter notebook, a Streamlit dashboard and builders for these chapters. "
     "All use the same functions, so a patient's schema is defined once.")
H2("4.3 Cohort description")
T1 = P.table1.copy()
table("4", "cohort", "Characteristics of the cohort by race group (\"Other\" = Asian, Native American, race not recorded)", T1, widths=[2.2, 1.1, 1.1, 1.1, 1.1], size=8)
para(f"Crude mortality is {pct(FL['prevalence'])} overall ({pct(FL['deaths_white'] / FL['n_white'])} White, {pct(FL['deaths_black'] / FL['n_black'])} Black, {pct(FL['deaths_other'] / FL['n_other'])} in the other group). "
     f"Black patients differ in tumour biology (basal-like {t1.loc['PAM50 Basal', 'Black']} versus {t1.loc['PAM50 Basal', 'White']}; Luminal A {t1.loc['PAM50 LumA', 'Black']} versus {t1.loc['PAM50 LumA', 'White']}; DeSantis et al., 2019), "
     f"and the documentation differs too: the metastasis category is MX (not assessed) for {t1.loc['M unknown (MX)', 'Black']} of Black patients against {t1.loc['M unknown (MX)', 'White']} of White patients. "
     f"The \"other\" group has a much shorter follow-up (median {t1.loc['Follow-up months, median (IQR)', 'Other'].split(' ')[0]} months against {t1.loc['Follow-up months, median (IQR)', 'White'].split(' ')[0]}) and is used only for training.")
figure("4", "survival", "01_survival_followup.png", "Kaplan-Meier survival and follow-up distribution, White and Black patients")
H2("4.4 Data audit")
H3("4.4.1 Blanks that carry the outcome")
mt = P.miss.copy()
mt = mt[["column", "n_missing", "pct_missing", "death_rate_missing", "death_rate_recorded"]]
mt = pd.DataFrame({"Column / code": mt.column, "n": mt.n_missing, "% of patients": mt.pct_missing.round(1),
                   "Death rate if missing": mt.death_rate_missing.map(lambda x: pct(x, 1)), "Death rate if recorded": mt.death_rate_recorded.map(lambda x: pct(x, 1))})
table("4", "missing", "Death rate when a field or code is blank versus recorded (all 1,084 patients)", mt, widths=[2.8, 0.6, 0.9, 1.1, 1.1], size=8.5)
para(f"The revised proposal retains radiation therapy and sets NX / MX to missing, and XGBoost reads blanks natively. But radiation therapy is blank for {int(rad.n_missing)} patients, {pct(rad.death_rate_missing, 0)} of whom died against "
     f"{pct(rad.death_rate_recorded, 0)} of those recorded; NX has a death rate of {pct(nxr.death_rate_missing, 0)} (n = {int(nxr.n_missing)}); and the {int(racem.n_missing)} patients without a recorded race have a death rate of {pct(racem.death_rate_missing, 0)}. "
     "These are registry-documentation patterns, not biology, and a model will exploit them.")
H3("4.4.2 Leakage ladder and artefact ablation")
lt = pd.DataFrame({"Feature set": lad.rung.map(lambda s: s.split("  ", 1)[1]), "AUC": lad.auc.round(3), "PR-AUC": lad.pr_auc.round(3), "Precision at 80 % recall": lad.precision_at_80_recall.map(lambda x: pct(x, 1))})
table("4", "ladder", "Cross-validated performance as columns are added", lt, widths=[3.6, 0.7, 0.8, 1.4])
figure("4", "leakage", "02_leakage_ladder.png", "Apparent performance as excluded columns are added back", 5.8)
para(f"Starting from audit-hardened features (AUC {lad.auc.iloc[0]:.3f}), the proposal's predictor list reaches {lad.auc.iloc[1]:.3f}, adding ethnicity and node assessment {lad.auc.iloc[2]:.3f}, post-baseline tumour status {lad.auc.iloc[3]:.3f} and days to last follow-up {lad.auc.iloc[4]:.3f}, "
     f"at which a flagged patient would be a true death {pct(lad.precision_at_80_recall.iloc[4], 0)} of the time. The last two rungs are leakage and are rightly excluded by the revised proposal. The step from the first to the second rung is subtler and needs attention: "
     f"{tr('specs')} and {fr('ablation')} show where it comes from.")
sp = P.specs.set_index("spec")
abt = pd.DataFrame({"Variant": P.ablation.variant, "AUC": P.ablation.auc.round(3), "PR-AUC": P.ablation.pr_auc.round(3)})
table("4", "specs", "Where the as-specified model's extra AUC comes from (artefact ablation; 5 x 5 CV)", abt, widths=[4.3, 0.8, 0.9])
figure("4", "ablation", "24_artefact_ablation.png", "Cross-validated AUC after removing documentation artefacts one at a time", 5.8)
para(f"Removing radiation therapy alone lowers AUC from {ABL0:.3f} to {ABL_RT:.3f}; removing the NX / MX codes to {abl.iloc[3].auc:.3f}; removing the race-not-recorded signal to {abl.iloc[2].auc:.3f}; and all three to {abl.iloc[4].auc:.3f}. "
     f"The stage-group sensitivity model reaches {sp.loc['stage_group', 'auc']:.3f} and the complete-case subtype model {sp.loc['complete_case_subtype', 'auc']:.3f}. About {100 * (ABL0 - abl.iloc[4].auc):.0f} AUC points of the as-specified model are documentation artefacts. "
     "Both specifications are therefore carried through the study; the as-specified model is primary because it is the approved design, and the hardened model is the one this study would recommend for any use beyond the thesis.")
H2("4.5 Model development")
bp = P.P
para(f"The Bayesian search selected very shallow trees (depth {bp['max_depth']}, {bp['n_estimators']} trees, learning rate {bp['learning_rate']:.3f}, L2 penalty {bp['reg_lambda']:.1f}), i.e. at most pairwise interactions: with {FL['n_deaths']} events, higher-order interactions between clinical variables are not identifiable. "
     f"{tr('bench')} compares models on identical features. XGBoost, logistic regression and a random forest are statistically indistinguishable, and all are far better than the stage-only model, "
     f"which has almost no discrimination (AUC {P.bench.set_index('model').loc['Stage-only (logistic)', 'auc']:.2f}): composite stage alone is a poor predictor in this cohort.")
bt = P.bench
table("4", "bench", "Model benchmark (5 x 5 CV, all patients)", pd.DataFrame({"Model": bt.model.str.replace(" - used", " (used)"), "AUC": bt.auc.round(3), "PR-AUC": bt.pr_auc.round(3),
                                                                              "FPR at 80 % recall": bt.fpr_at_80_recall.map(lambda x: pct(x, 1)), "AUC White": bt.auc_White.round(3), "AUC Black": bt.auc_Black.round(3)}),
      widths=[2.7, 0.7, 0.8, 1.0, 0.8, 0.8], size=8.5)
figure("4", "benchmark", "03_model_benchmark.png", "Benchmark of candidate models", 5.8)
cv_ = P.curve
para(f"Overfitting control ({fr('curve')}): along the boosting path training AUC rises to {cv_.train.iloc[-1]:.3f}, cross-validated AUC plateaus at {cv_.cv.iloc[-1]:.3f} and hold-out AUC is {cv_.test.iloc[-1]:.3f}. The training-to-validation gap is modest "
     f"({cv_.train.iloc[-1] - cv_.cv.iloc[-1]:.2f}) and the cross-validated and hold-out curves are flat beyond about 150 trees, so the {bp['n_estimators']}-tree model sits on the plateau. The monotone constraint made no measurable difference ({tr('bench')}).")
figure("4", "curve", "21_learning_curve.png", "Training, cross-validated and hold-out AUC along the boosting path", 4.8)
H2("4.6 Performance at the recall-first operating point (Objective 2)")
oa = lambda m: P.ov("aware", m)
para(f"Cross-validated over all {FL['n_records']:,} patients (race-aware model), AUC-ROC is {oa('auc_roc')[0]:.3f} and PR-AUC {oa('pr_auc')[0]:.3f} against a no-skill value of {FL['prevalence']:.3f}. At the recall-first threshold the model catches {pct(oa('recall')[0])} of deaths "
     f"(CI {pct(oa('recall')[1])} to {pct(oa('recall')[2])}), flags {pct(oa('flag_rate')[0], 0)} of patients and has a precision of {pct(oa('precision')[0])}, which clears the floor of {FL['precision_floor']:.2f}.")
rows = []
for m in [MAINM, "XGBoost (race-blind)", "Logistic regression", "Random forest", "Stage-only (logistic)"]:
    rows.append([m.replace(" (race-aware, primary)", " (primary)")] + [ci3(*P.tm(m, k)) for k in ["recall", "precision", "f1", "auc_roc", "pr_auc"]] + [f"{P.tm(m, 'accuracy')[0]:.2f}"])
table("4", "test", f"Hold-out test results ({FL['n_test']} patients, {FL['test_deaths']} deaths; estimate (95 % bootstrap CI))", pd.DataFrame(rows, columns=["Model", "Recall", "Precision", "F1", "AUC-ROC", "PR-AUC", "Accuracy"]),
      widths=[1.4, 1.0, 1.0, 1.0, 1.0, 1.0, 0.7], size=8)
para(f"On the hold-out set the primary model flagged {int(P.confusion.iloc[0].tp)} of {FL['test_deaths']} deaths (recall {ci3(*P.tm(MAINM, 'recall'))}), with precision {P.tm(MAINM, 'precision')[0]:.2f}, AUC-ROC {ci3(*P.tm(MAINM, 'auc_roc'))} and PR-AUC {ci3(*P.tm(MAINM, 'pr_auc'))}. "
     f"The hold-out recall of {P.tm(MAINM, 'recall')[0]:.2f} is below the 80 % target that was met on the development data and in cross-validation ({pct(oa('recall')[0], 0)}), but the target lies inside its interval: with {FL['test_deaths']} deaths, one more or fewer caught death moves recall by three points. "
     f"Its accuracy of {P.tm(MAINM, 'accuracy')[0]:.2f} is far below the {1 - FL['test_deaths'] / FL['n_test']:.2f} of always predicting \"living\": this is the price of recall-first operation, and accuracy is the wrong yardstick here. "
     f"The intervals of XGBoost, logistic regression and the random forest overlap almost completely ({fr('forest')}), whereas the stage-only model is clearly worse in PR-AUC.")
figure("4", "forest", "23_test_forest.png", "Hold-out recall, AUC-ROC and PR-AUC with bootstrap intervals", 6.4)
rr = P.rules
rt_ = pd.DataFrame({"Rule": rr.rule, "Threshold": rr.threshold.round(3), "Recall (hold-out)": rr.recall.round(2), "Precision": rr.precision.round(2), "Share flagged": rr.flag_rate.map(lambda x: pct(x, 0)), "Recall (dev, OOF)": rr.dev_recall.round(2)})
table("4", "rules", "Threshold rules learned on the development set and applied to the hold-out set", rt_, widths=[2.3, 0.8, 0.9, 0.8, 0.8, 0.9], size=8.5)
para(f"The proposal asks for a threshold that \"maximises recall at an acceptable precision\". A rule that only maximises recall subject to a precision floor close to the prevalence returns a threshold that flags {pct(rr.flag_rate.iloc[2], 0)} of patients; "
     f"rules that balance precision and recall (Youden, default 0.5) each give up {pct(1 - rr.recall.iloc[4], 0)} of deaths on the hold-out set. The recall target of 80 % is the only rule that makes the recall-first priority explicit and reproducible ({fr('pr')}).")
figure("4", "pr", "22_precision_recall.png", "Hold-out precision-recall curve with the threshold rules of the table above", 5.0)
H2("4.7 SHAP analysis (Objective 3)")
H3("4.7.1 Global and local explanations")
al = P.align
para(f"{fr('beeswarm')} ranks the drivers of the as-specified model: {al.feature.iloc[0]} (mean |SHAP| {al.mean_abs_shap.iloc[0]:.2f} log-odds), {al.feature.iloc[1]} ({al.mean_abs_shap.iloc[1]:.2f}), {al.feature.iloc[2]} ({al.mean_abs_shap.iloc[2]:.2f}), "
     f"{al.feature.iloc[3]} ({al.mean_abs_shap.iloc[3]:.2f}) and {al.feature.iloc[4]} ({al.mean_abs_shap.iloc[4]:.2f}). Three of these five are established prognostic factors; the other two are not: radiation therapy is a treatment-documentation field and "
     f"the Asian-race indicator reflects three deaths among 60 patients. The staging effects point in the expected direction (Spearman correlation between value and SHAP: age {P.direction.spearman.iloc[0]:.2f}, T {P.direction.spearman.iloc[1]:.2f}, N {P.direction.spearman.iloc[2]:.2f}, M {P.direction.spearman.iloc[3]:.2f}).")
figure("4", "beeswarm", "12_shap_beeswarm.png", "SHAP summary (beeswarm) of the as-specified model", 5.6)
figure("4", "dependence", "14_dependence.png", "SHAP dependence plots for age, nodal status and tumour size by race", 6.4)
para(f"Local explanations ({fr('wf_tp')} to {fr('wf_tn')}) show the reasoning for a Black patient whose death was caught, a Black patient whose death was missed, and a White survivor correctly not flagged. "
     "They let a reviewer see why the missed death fell below the threshold: young age and node-negative status subtracted more risk than the weak positive signals added.")
for k, n_, t_ in [("wf_tp", "true_positive_black", "True positive (Black patient)"), ("wf_fn", "false_negative_black", "False negative (Black patient)"), ("wf_tn", "true_negative_white", "True negative (White patient)")]:
    figure("4", k, f"15_waterfall_{n_}.png", f"Waterfall explanation: {t_}", 4.6)
H3("4.7.2 Quality of the explanations")
dl = P.deletion.set_index("k")
eqt = pd.DataFrame([["Fidelity: max |base + sum(SHAP) - margin|", f"{EQ['fidelity']['max_abs_error']:.1e} over {EQ['fidelity']['n']:,} patients"],
                    ["Stability across 10 CV-fold models (mean / min Spearman)", f"{EQ['fold_stability']['mean_spearman']:.2f} / {EQ['fold_stability']['min_spearman']:.2f}"],
                    ["Stability across 100 bootstrap refits (mean Spearman)", f"{EQ['bootstrap_stability']:.2f}"],
                    ["Agreement with XGBoost gain / weight / cover importance (Spearman)", f"{EQ['builtin']['gain']:.2f} / {EQ['builtin']['weight']:.2f} / {EQ['builtin']['cover']:.2f}"],
                    ["Deletion test: AUC after blanking the top-1 / top-2 attributed features", f"{dl.loc[1, 'auc_top_shap']:.2f} / {dl.loc[2, 'auc_top_shap']:.2f} (random: {dl.loc[1, 'auc_random']:.2f} / {dl.loc[2, 'auc_random']:.2f}; intact {dl.loc[0, 'auc_top_shap']:.2f})"],
                    ["Clinical alignment: top-5 features that are established prognostic factors", f"{int(al.established_prognostic_factor.map(lambda x: not x.startswith('no')).sum())} of 5"]], columns=["Criterion", "Result"])
table("4", "explq", "Explanation quality of the as-specified model", eqt, widths=[3.8, 2.7])
check(dl.loc[1, "auc_top_shap"] < dl.loc[1, "auc_random"], "deletion of top-attributed feature hurts more than random")
para(f"Fidelity holds to numerical precision, as it must for TreeSHAP. Rankings are stable (rank correlation {EQ['fold_stability']['mean_spearman']:.2f} across fold models, {EQ['bootstrap_stability']:.2f} across bootstraps) and agree with XGBoost's own gain importance ({EQ['builtin']['gain']:.2f}). "
     f"The deletion test confirms that SHAP points at what the model really uses: blanking the single most-attributed feature takes AUC from {dl.loc[0, 'auc_top_shap']:.2f} to {dl.loc[1, 'auc_top_shap']:.2f}, against {dl.loc[1, 'auc_random']:.2f} for a random feature ({fr('deletion')}). "
     "Faithful and stable explanations of a model that leans on documentation artefacts are not the same as clinically meaningful explanations, which is why alignment is reported separately.")
figure("4", "deletion", "26_deletion_test.png", "Faithfulness (deletion) test", 4.4)
H3("4.7.3 The race check")
para(f"For the {int(rs.loc['race recorded', 'n'])} patients whose race is recorded the race columns carry {pct(rs.loc['race recorded', 'share_of_total_attribution'], 0)} of the attribution. For the {int(unk.n)} patients whose race is not recorded they carry "
     f"{pct(unk.share_of_total_attribution, 0)}, with a mean effect of {unk.mean_race_shap:+.2f} log-odds; their observed death rate is {pct(unk.death_rate, 1)}. The model has learned that a blank race field means low risk ({fr('racemiss')}). "
     f"The check therefore finds that the model does not rely on race itself, but it does rely on whether race was documented.")
figure("4", "racemiss", "25_race_missing_signal.png", "Attribution carried by the race columns, and observed mortality, by whether race was recorded", 5.4)
H2("4.8 Fairness audit and bias mitigation (extension)")
H3("4.8.1 Equal opportunity and false-alarm burden")
para(f"For the race-aware baseline, recall is {pct(P.cv('aware', 'tpr_W')[0])} for White and {pct(P.cv('aware', 'tpr_B')[0])} for Black patients: a gap of {P.ci('aware', 'tpr_gap', True)}. "
     f"The false-alarm rate is {pct(P.cv('aware', 'fpr_W')[0])} against {pct(P.cv('aware', 'fpr_B')[0])}, a gap of {P.ci('aware', 'fpr_gap', True)}. Neither gap is distinguishable from zero, but with {FL['deaths_black']} Black deaths the recall-gap interval is about ±{100 * HW:.0f} points wide, so a smaller gap could not be detected ({fr('rates')}, {fr('gaps')}, {tr('fair')}).")
figure("4", "rates", "05_rates_by_race.png", "Recall and false-alarm rate by race for the five strategies (5 x 5 CV, bootstrap CI)", 6.4)
fr_rows = [[SHORT[k], pct(P.cv(k, "tpr_W")[0]), pct(P.cv(k, "tpr_B")[0]), P.ci(k, "tpr_gap", True).replace(" percentage points", " pp"), P.ci(k, "fpr_gap", True).replace(" percentage points", " pp"), pct(P.cv(k, "eod")[0])] for k in KEYS]
table("4", "fair", "Fairness metrics by strategy (Black minus White; 95 % bootstrap CI)", pd.DataFrame(fr_rows, columns=["Strategy", "Recall White", "Recall Black", "Recall gap", "False-alarm gap", "Equalised-odds diff."]),
      widths=[1.5, 0.7, 0.7, 1.4, 1.4, 0.8], size=8)
figure("4", "gaps", "06_gap_forest.png", "Recall and false-alarm gaps with 95 % intervals", 6.2)
H3("4.8.2 What did mitigation do?")
pb, prw, pg, prg = P.paired_("blind", "tpr_gap"), P.paired_("reweigh", "tpr_gap"), P.paired_("gthr", "tpr_gap"), P.paired_("reweigh_gthr", "eod")
fb, frw, fg = P.paired_("blind", "fpr_gap"), P.paired_("reweigh", "fpr_gap"), P.paired_("gthr", "fpr_gap")
rb = P.imp.loc["race_black"]; rbs = P.gap.loc["race_black", "contribution_to_gap"]
para(f"Differences between strategies are small compared with the uncertainty of each, so a paired bootstrap is used ({tr('paired')}). "
     f"(i) Race is not inert in this model: the Black indicator adds {rbs:+.3f} log-odds to the average Black-minus-White score gap. Removing race (race-blind) lowers the false-alarm gap (paired change {fb[0]:+.3f}, CI {fb[1]:+.3f} to {fb[2]:+.3f}) "
     f"but also moves the recall gap by {pb[0]:+.3f} (CI {pb[1]:+.3f} to {pb[2]:+.3f}), so unawareness trades Black recall for fewer false alarms rather than being neutral. "
     f"(ii) Reweighing does the same more strongly: the recall gap falls by {-prw[0]:.3f} (CI {prw[1]:+.3f} to {prw[2]:+.3f}), i.e. fewer Black deaths are caught, while the false-alarm gap changes by {frw[0]:+.3f} (CI {frw[1]:+.3f} to {frw[2]:+.3f}). "
     f"In a recall-first system this is the wrong direction. (iii) Group-specific thresholds target equal opportunity directly: the gaps become {100 * P.cv('gthr', 'tpr_gap')[0]:+.1f} (recall) and {100 * P.cv('gthr', 'fpr_gap')[0]:+.1f} (false alarms) points, and the equalised-odds difference falls from {pct(P.cv('aware', 'eod')[0])} to {pct(P.cv('gthr', 'eod')[0])}. "
     f"Relative to the baseline, whose higher Black recall comes from the race term, their paired recall-gap change is {pg[0]:+.3f} (CI {pg[1]:+.3f} to {pg[2]:+.3f}); the improvement in the equalised-odds difference itself is not statistically distinguishable "
     f"(paired change {P.paired_('gthr', 'eod')[0]:+.3f}, CI {P.paired_('gthr', 'eod')[1]:+.3f} to {P.paired_('gthr', 'eod')[2]:+.3f}), and the Black-specific threshold is estimated from about 30 deaths and varies across folds (SD "
     f"{P.thr[(P.thr.strategy == 'gthr') & (P.thr.threshold == 'Black')]['sd'].iloc[0]:.3f} against {P.thr[(P.thr.strategy == 'gthr') & (P.thr.threshold == 'White')]['sd'].iloc[0]:.3f} for White). "
     f"(iv) Reweighing combined with group thresholds has the smallest equalised-odds difference ({pct(P.cv('reweigh_gthr', 'eod')[0])}) and near-equal recall ({P.ci('reweigh_gthr', 'tpr_gap', True).replace(' percentage points', ' points')}).")
pt = []
for k in KEYS[1:]:
    for m, nm in [("tpr_gap", "Recall gap"), ("fpr_gap", "False-alarm gap"), ("eod", "Equalised-odds diff.")]:
        d, lo, hi, p = P.paired_(k, m)
        pt.append([SHORT[k], nm, f"{d:+.3f}", f"[{lo:+.3f}, {hi:+.3f}]", "yes" if (lo > 0 or hi < 0) else "no"])
table("4", "paired", "Paired bootstrap change in each gap relative to the race-aware baseline", pd.DataFrame(pt, columns=["Strategy", "Metric", "Change", "95 % CI", "Distinguishable from 0?"]), widths=[1.9, 1.5, 0.8, 1.3, 1.1], size=8.5)
figure("4", "tradeoff", "07_tradeoff.png", "Cost of fairness: workload against equalised-odds difference", 4.5)
H3("4.8.3 Sensitivity to the recall target")
sw = P.sweep
sg = sw[(sw.metric == "tpr_gap") & (sw.strategy == "aware")].estimate
sf = sw[(sw.metric == "fpr_gap") & (sw.strategy == "aware")].estimate
para(f"Across recall targets from 70 % to 95 % the baseline recall gap stays between {sg.min():+.3f} and {sg.max():+.3f} and the false-alarm gap between {sf.min():+.3f} and {sf.max():+.3f} ({fr('sweep')}). "
     "The sign and rough size of the gaps do not depend on the 80 % target, and the intervals are as wide as at 80 %. The false-alarm gap of the group-threshold strategies changes sign at high targets, which again reflects noise in thresholds estimated from few deaths.")
figure("4", "sweep", "08_recall_target_sweep.png", "Gaps as the recall target varies from 70 % to 95 %", 6.2)
H3("4.8.4 Sensitivity to model selection")
mm = ms[ms.strategy.isin(["aware", "blind", "gthr"]) & ms.metric.isin(["tpr_gap", "fpr_gap"])].pivot_table(index=["strategy", "metric"], columns="config", values="estimate")
cols_ = list(mm.columns)
mrows = []
for (k, m), r_ in mm.iterrows():
    mrows.append([SHORT[k], "Recall gap" if m == "tpr_gap" else "False-alarm gap"] + [f"{100 * v:+.1f}" for v in r_.values])
table("4", "msens", "Gap estimates (percentage points, Black minus White) across near-equivalent tuned configurations (3 x 5-fold CV)",
      pd.DataFrame(mrows, columns=["Strategy", "Metric"] + [c.replace("top-", "#").replace(" trees", "t").replace("depth ", "d") for c in cols_]), widths=[1.3, 1.1] + [0.65] * len(cols_), size=7.5)
bl = mm.loc[("blind", "tpr_gap")]; ga = mm.loc[("aware", "tpr_gap")]; gt = mm.loc[("gthr", "tpr_gap")]
cva = ms.groupby("config").cv_auc.first()
para(f"The cross-validated AUC of these configurations differs by only {100 * (cva.max() - cva.min()):.1f} points, yet the baseline recall gap ranges from {100 * ga.min():+.1f} to {100 * ga.max():+.1f} points: "
     f"point estimates of group gaps are partly an accident of model selection and should not be quoted without that caveat ({tr('msens')}). Two conclusions are stable across all configurations: removing race lowers the recall gap "
     f"(to between {100 * bl.min():+.1f} and {100 * bl.max():+.1f} points, always negative), and group thresholds hold the recall gap within {100 * gt.abs().max():.1f} points of zero.")
H3("4.8.5 Discrimination and calibration by race")
cal = P.cal.set_index(["strategy", "group"])
para(f"Discrimination is similar but less certain for Black patients: AUC {ci3(*P.auc('aware', 'White'))} (White) against {ci3(*P.auc('aware', 'Black'))} (Black) ({fr('roc')}). Class weighting inflates raw scores, so they were recalibrated with one logistic (Platt) mapping fitted to all patients' out-of-fold scores. "
     f"With that shared mapping the observed-to-expected death ratio is {cal.loc[('aware', 'White'), 'oe_ratio']:.2f} for White and {cal.loc[('aware', 'Black'), 'oe_ratio']:.2f} for Black patients in the race-aware model, "
     f"and {cal.loc[('blind', 'White'), 'oe_ratio']:.2f} and {cal.loc[('blind', 'Black'), 'oe_ratio']:.2f} in the race-blind model: removing race increases the under-prediction of Black mortality from {100 * (cal.loc[('aware', 'Black'), 'oe_ratio'] - 1):.0f}% to {100 * (cal.loc[('blind', 'Black'), 'oe_ratio'] - 1):.0f}% ({fr('calib')}). "
     f"The within-group calibration slope is {cal.loc[('aware', 'White'), 'within_group_slope']:.2f} for White and {cal.loc[('aware', 'Black'), 'within_group_slope']:.2f} for Black patients: the score separates risk less sharply in the smaller group.")
ct = P.cal.copy()
table("4", "calib", "Calibration after one shared recalibration, by race", pd.DataFrame({"Model": ct.strategy.map({"aware": "Race-aware", "blind": "Race-blind"}), "Group": ct.group, "Observed death rate": ct.observed.map(pct),
                                                                                     "Mean recalibrated risk": ct.mean_recalibrated.map(pct), "Observed / expected": ct.oe_ratio.round(2), "Within-group slope": ct.within_group_slope.round(2)}), widths=[1.2, 0.8, 1.2, 1.4, 1.1, 1.0])
figure("4", "roc", "04_roc_by_group.png", "ROC curves by race (out-of-fold)", 4.2)
figure("4", "calib", "10_calibration.png", "Calibration by race after a shared Platt mapping", 4.2)
H3("4.8.6 Censoring, group definition and the hold-out set")
s24, s36, s60 = P.sens_(24, "aware", "fpr_gap"), P.sens_(36, "aware", "fpr_gap"), P.sens_(60, "aware", "fpr_gap")
anc = P.anc.set_index(["strategy", "group"])
para(f"Restricting evaluation to patients who died or were followed at least 24, 36 or 60 months (n = {P.sens_n(24)}, {P.sens_n(36)}, {P.sens_n(60)}) moves the baseline false-alarm gap from {s24[0]:+.3f} to {s36[0]:+.3f} and {s60[0]:+.3f} "
     f"(CIs {s24[1]:+.2f} to {s24[2]:+.2f}, {s36[1]:+.2f} to {s36[2]:+.2f}, {s60[1]:+.2f} to {s60[2]:+.2f}; {fr('sensitivity')}); none excludes zero, but the drift towards more false alarms for Black patients with longer follow-up is worth monitoring. "
     f"Using genetic ancestry instead of race, recall is {pct(anc.loc[('aware', 'AFR / AFR-admixed ancestry'), 'recall'], 0)} for African ancestry (n = {int(anc.loc[('aware', 'AFR / AFR-admixed ancestry'), 'n'])}, {int(anc.loc[('aware', 'AFR / AFR-admixed ancestry'), 'deaths'])} deaths) against {pct(anc.loc[('aware', 'EUR ancestry'), 'recall'], 0)} for European ancestry, in line with the race-based result.")
figure("4", "sensitivity", "11_sensitivity_settled.png", "Gaps when evaluation is restricted to patients with settled outcomes", 6.0)
hr = pd.DataFrame([[SHORT[k], g, int(P.ho(k, g).n), int(P.ho(k, g).deaths), f"{pct(P.ho(k, g).recall, 0)} ({pct(P.ho(k, g).recall_lo, 0)}-{pct(P.ho(k, g).recall_hi, 0)})", pct(P.ho(k, g).fpr, 0), f"{P.ho(k, g).auc:.2f}"]
                   for k in ["aware", "blind", "gthr"] for g in ["White", "Black"]], columns=["Strategy", "Group", "n", "Deaths", "Recall (Wilson CI)", "False-alarm rate", "AUC"])
table("4", "holdrace", "Hold-out results by race (single split; very wide intervals)", hr, widths=[1.6, 0.8, 0.5, 0.6, 1.5, 1.0, 0.6], size=8.5)
para(f"The hold-out set contains only {FL['test_black_deaths']} Black deaths. Its group-level recall ({pct(P.ho('aware', 'Black').recall, 0)} for Black patients) is an anecdote and supports no fairness statement; this is why the audit rests on repeated cross-validation ({fr('holdout_race')}).")
figure("4", "holdout_race", "09_holdout_recall.png", "Hold-out recall by race and strategy", 5.0)
H3("4.8.7 Why the groups are scored differently, and why deaths are missed")
gd = P.gap
para(f"The mean model score differs by only {META['risk_gap_total']:+.3f} log-odds between Black and White patients, but only because opposing terms cancel ({fr('gapdecomp')}): the Black indicator adds {gd.loc['race_black', 'contribution_to_gap']:+.3f}, "
     f"while the metastasis category contributes {gd.loc['m_stage', 'contribution_to_gap']:+.3f} and radiation {gd.loc['radiation', 'contribution_to_gap']:+.3f}, in the opposite direction. The last two come from documentation: Black patients are more often recorded as MX ({t1.loc['M unknown (MX)', 'Black']} against {t1.loc['M unknown (MX)', 'White']}), "
     f"a code with a low death rate ({pct(mxr.death_rate_missing, 0)}) that pulls their scores down. Missed deaths ({fr('profile')}) are younger and node-negative patients in both groups, so the mechanism of a miss is shared. "
     f"Feature importance is nearly the same in both groups ({fr('imp_race')}), and the importance ranking among Black patients is stable only at the top ({fr('stability')}).")
figure("4", "imp_race", "13_importance_by_race.png", "Mean absolute SHAP value by race", 5.3)
figure("4", "gapdecomp", "16_risk_gap_decomposition.png", "Contributions to the Black-minus-White gap in mean model score", 5.2)
figure("4", "profile", "17_missed_deaths_profile.png", "Mean SHAP of caught and missed deaths by race", 6.1)
figure("4", "stability", "18_shap_stability_black.png", "Bootstrap stability of the importance rank among Black patients", 5.2)
ag = META["agreement"]
para(f"Mitigation changes explanations moderately: the rank correlation of global importance between the race-aware model and the race-blind and reweighed models is {ag['main_vs_blind']['rank_corr']:.2f} and {ag['main_vs_reweigh']['rank_corr']:.2f} ({fr('mitig')}).")
figure("4", "mitig", "19_explanations_under_mitigation.png", "Feature importance of the race-aware, race-blind and reweighed models", 5.2)
H2("4.9 The audit-hardened specification")
pe, he = {k: P.ov("aware", k) for k in ["auc_roc", "pr_auc", "recall", "precision", "flag_rate"]}, {k: H.ov("aware", k) for k in ["auc_roc", "pr_auc", "recall", "precision", "flag_rate"]}
cmp_rows = []
for nm, S, e in [("As specified (Table 3.2)", P, pe), ("Audit-hardened", H, he)]:
    cmp_rows.append([nm, f"{e['auc_roc'][0]:.3f}", f"{e['pr_auc'][0]:.3f}", pct(e["recall"][0]), pct(e["precision"][0]), pct(e["flag_rate"][0], 0), S.ci("aware", "tpr_gap", True).replace(" percentage points", " pp"),
                     S.ci("aware", "fpr_gap", True).replace(" percentage points", " pp"), S.align.feature.iloc[0]])
table("4", "compare", "As-specified versus audit-hardened specification (5 x 5 CV; fairness on White and Black patients)",
      pd.DataFrame(cmp_rows, columns=["Specification", "AUC-ROC", "PR-AUC", "Recall", "Precision", "Flagged", "Recall gap", "False-alarm gap", "Top SHAP feature"]), widths=[1.1, 0.5, 0.5, 0.5, 0.6, 0.5, 1.1, 1.1, 0.9], size=7.5)
hh = H.tm(MAINM, "auc_roc"); hp = H.tm(MAINM, "pr_auc"); hr_ = H.tm(MAINM, "recall")
para(f"Without the documentation artefacts the model is a clinically cleaner but weaker one: cross-validated AUC-ROC falls from {pe['auc_roc'][0]:.3f} to {he['auc_roc'][0]:.3f} and PR-AUC from {pe['pr_auc'][0]:.3f} to {he['pr_auc'][0]:.3f} "
     f"(no-skill {FL['prevalence']:.3f}); at the same 80 % recall target it must flag {pct(he['flag_rate'][0], 0)} of patients with a precision of {pct(he['precision'][0], 0)}, "
     f"{'below' if he['precision'][0] < FL['precision_floor'] else 'at or above'} the floor of {FL['precision_floor']:.2f}. On the hold-out set its AUC-ROC is {ci3(*hh)} and recall {ci3(*hr_)}. "
     f"Its leading SHAP feature is {H.align.feature.iloc[0]}, a clinical factor; the top five are {', '.join(H.align.feature.head(5))}. "
     f"Its explanations are less stable than those of the as-specified model (rank correlation across fold models {H.meta['explain_quality']['fold_stability']['mean_spearman']:.2f} against {EQ['fold_stability']['mean_spearman']:.2f}). "
     f"Its fairness picture: recall gap {H.ci('aware', 'tpr_gap', True).replace(' percentage points', ' points')}; false-alarm gap {H.ci('aware', 'fpr_gap', True).replace(' percentage points', ' points')}. "
     f"Within the hardened specification the equalised-odds differences by strategy are: " + "; ".join(f"{SHORT[k].lower()} {pct(H.cv(k, 'eod')[0])}" for k in KEYS) + ".")
figure("4", "h_rates", "05_rates_by_race.png", "Hardened specification: recall and false-alarm rate by race", 6.0, spec=H)
figure("4", "h_beeswarm", "12_shap_beeswarm.png", "Hardened specification: SHAP summary", 5.2, spec=H)
H2("4.10 Dashboard, user-study kit and conceptual framework (Objectives 4 and 5)")
para("The Streamlit dashboard (app.py) lets a reviewer switch between the two specifications; enter a patient (including \"not recorded\" for radiation, race or N / M and watch the as-specified score move); choose any of the five strategies; "
     "read the score, the threshold that applies and the SHAP waterfall; inspect hold-out metrics with confidence intervals, confusion matrices, baselines and the threshold rules; explore recall and false-alarm rates by race under a global or group-specific threshold; "
     "examine explanation quality and the race check; and read the data audit. Objective 4 is delivered as an instrument: 12 case cards in two conditions, a counterbalanced design for 24 participant slots, a questionnaire, a response template and an analysis script "
     "(Wilcoxon signed-rank with Holm correction, rank-biserial effect sizes), self-tested on synthetic data. No physician data were collected, so no claim about trust or understanding is made. Objective 5 is the framework of Section 3.2.9.")
H2("4.11 Discussion")
para(f"Three findings stand out. First, the predictor list of the revised proposal performs better than it should. Its AUC-ROC of {pe['auc_roc'][0]:.2f} is roughly {100 * (pe['auc_roc'][0] - he['auc_roc'][0]):.0f} points above a clinically cleaner specification, and the leading SHAP feature is "
     f"{P.align.feature.iloc[0].lower()}, whose blanks track death. The explanation is faithful and stable, and it tells the reader something uncomfortable: what the model has learned is partly how the registry was filled in. "
     "Second, predictive performance is respectable for clinical covariates alone, comparable across XGBoost, logistic regression and a random forest, and the recall-first requirement has a visible price: to catch four in five deaths the model flags about half of all patients, "
     f"and only about one in five of them dies. Third, the fairness evidence is inconclusive rather than reassuring. No gap is statistically distinguishable from zero, but the recall-gap interval is about ±{100 * HW:.0f} points wide. "
     "Mitigation is not free: removing race or reweighing lowers Black recall in exchange for fewer false alarms, while group thresholds keep both gaps near zero without a demonstrable advantage over the baseline. "
     "Documentation differences between groups (more MX codes among Black patients, race not recorded) are themselves a source of group-specific scoring.")
para("These results echo Obermeyer et al. (2019) and Rajkomar et al. (2018): disparities in medical algorithms usually enter through the data and the label, and the first remedy is to audit with the right metric and the right uncertainty. "
     "For the thesis, the pragmatic position is to report the as-specified model as the approved design, to show the audit-hardened one beside it, and to recommend that the proposal's Table 3.2 be amended before any further use.")
doc.add_page_break()

# =============================================================================================
# CHAPTER 5
# =============================================================================================
H1("5.0 Conclusions")
H2("5.1 Summary of the study")
para(f"This study built an XGBoost classifier that predicts death during follow-up among {FL['n_records']:,} TCGA-BRCA patients from baseline clinicopathological data, with a recall-first threshold, explained it with SHAP, audited its inputs, "
     f"and tested whether it treats Black and White patients equally. The model reaches a cross-validated AUC-ROC of {pe['auc_roc'][0]:.2f} and catches {pct(pe['recall'][0], 0)} of deaths while flagging {pct(pe['flag_rate'][0], 0)} of patients. "
     f"Part of that performance is documentation: a hardened specification has an AUC-ROC of {he['auc_roc'][0]:.2f}. SHAP explanations are faithful and stable but, for the as-specified model, led by a treatment-documentation field. "
     "The fairness audit finds no statistically detectable gap and no mitigation that is demonstrably better than the baseline.")
H2("5.2 Conclusions per objective")
bullets([("Objective 1 (develop and optimise the classifier). ", f"A depth-{bp['max_depth']}, {bp['n_estimators']}-tree XGBoost with class weighting, monotone staging constraints and a threshold that catches 80 % of deaths was tuned by repeated cross-validation; the training, cross-validated and hold-out AUCs show no material overfitting."),
         ("Objective 2 (evaluate and benchmark). ", f"Hold-out recall {ci3(*P.tm(MAINM, 'recall'))}, AUC-ROC {ci3(*P.tm(MAINM, 'auc_roc'))}, PR-AUC {ci3(*P.tm(MAINM, 'pr_auc'))} (no-skill {FL['test_deaths'] / FL['n_test']:.2f}), accuracy {P.tm(MAINM, 'accuracy')[0]:.2f} against {1 - FL['test_deaths'] / FL['n_test']:.2f} for always predicting living. Logistic regression and a random forest perform alike; stage alone does not."),
         ("Objective 3 (SHAP). ", "Explanations are faithful (exact), stable (rank correlation above 0.75) and agree with XGBoost's own importances; three of the top five features are established prognostic factors, and staging effects have the expected direction. The model leans on radiation-therapy documentation and on whether race was recorded."),
         ("Objective 4 (clinician trust). ", "The study instrument and analysis are ready and tested on synthetic data; no clinician has responded, so no conclusion is drawn."),
         ("Objective 5 (framework). ", "A pipeline framework places SHAP at two points, as a pre-deployment trust check and as a bedside explanation, with a governance gate for inputs and group-wise monitoring after deployment."),
         ("Extension (fairness). ", f"Recall gap {P.ci('aware', 'tpr_gap', True)}; false-alarm gap {P.ci('aware', 'fpr_gap', True)}. Race-blind and reweighed models lower Black recall, group thresholds keep gaps near zero without demonstrable benefit, and calibration is looser for Black patients.")])
H2("5.3 Contributions to knowledge")
bullets(["A worked, auditable example of recall-first prognostic modelling in oncology that reports the price of recall (precision, share flagged) and not only accuracy.",
         "A leakage ladder and artefact ablation that quantify how much of a model's performance comes from documentation rather than biology, in a widely used TCGA table.",
         "An explanation-quality protocol (fidelity, deletion, stability, clinical alignment, race attribution) that goes beyond showing SHAP plots.",
         "A fairness protocol for very small subgroups: repeated cross-validation, in-fold thresholds, paired bootstrap comparison of mitigation strategies, settled-outcome and ancestry sensitivity analyses.",
         "An open-source dashboard, model card, data audit and physician user-study kit tied to the thesis numbers."])
H2("5.4 Limitations")
bullets([f"Small group: {FL['deaths_black']} Black deaths; {FL['test_black_deaths']} in the hold-out set. Absence of a detectable gap is not evidence of fairness.",
         "Censoring: a binary label ignores follow-up length; overall survival includes non-cancer deaths; treatment data other than radiation and neoadjuvant therapy are absent.",
         "Documentation artefacts: the as-specified model exploits blank fields; the hardened model avoids them at a cost in AUC.",
         "Single, predominantly European-ancestry cohort; no external validation. Race is a social variable and ancestry analysis is also small.",
         "Mitigation scope: pre- and post-processing only; group thresholds need race at prediction time.",
         "Objective 4 is not yet executed."])
H2("5.5 Recommendations and future work")
bullets(["Amend Table 3.2 of the proposal before further use: drop radiation therapy (or replace it by a reliable treatment field), set NX and MX to their AJCC defaults, and handle unrecorded race explicitly; keep the as-specified model only as the documented primary analysis.",
         "Define \"acceptable precision\" numerically in the thesis (here 1.25 times prevalence) and report precision and the share flagged next to recall.",
         "Collect or federate more data for under-represented groups, with external validation; this is the only remedy for the central uncertainty.",
         "Model time to event with censoring-aware methods (XGBoost Cox / AFT objectives) and add treatment and receptor variables.",
         "Monitor group-wise recall and false-alarm rates with confidence intervals at every model update; avoid group-specific thresholds until each group has several hundred events.",
         "Run the clinician study with the kit in the userstudy folder after ethical approval; pre-register trust and understandability as primary outcomes."])
doc.add_page_break()
H1("References cited in Chapters 3, 4 and 5")
refs = [
    "Carrot-Zhang, J. et al. (2020). Comprehensive analysis of genetic ancestry and its molecular correlates in cancer. Cancer Cell, 37(5), 639-654.",
    "Cerami, E. et al. (2012). The cBio Cancer Genomics Portal: an open platform for exploring multidimensional cancer genomics data. Cancer Discovery, 2(5), 401-404.",
    "Chen, T. and Guestrin, C. (2016). XGBoost: a scalable tree boosting system. Proceedings of the 22nd ACM SIGKDD Conference, 785-794.",
    "DeSantis, C. E. et al. (2019). Breast cancer statistics, 2019. CA: A Cancer Journal for Clinicians, 69(6), 438-451.",
    "Efron, B. and Tibshirani, R. J. (1993). An Introduction to the Bootstrap. Chapman and Hall.",
    "Hardt, M., Price, E. and Srebro, N. (2016). Equality of opportunity in supervised learning. Advances in Neural Information Processing Systems 29.",
    "Hoffman, R. R., Mueller, S. T., Klein, G. and Litman, J. (2018). Metrics for explainable AI: challenges and prospects. arXiv:1812.04608.",
    "Kamiran, F. and Calders, T. (2012). Data preprocessing techniques for classification without discrimination. Knowledge and Information Systems, 33(1), 1-33.",
    "Kaufman, S., Rosset, S. and Perlich, C. (2011). Leakage in data mining: formulation, detection, and avoidance. Proceedings of the 17th ACM SIGKDD Conference, 556-563.",
    "Liu, J. et al. (2018). An integrated TCGA pan-cancer clinical data resource to drive high-quality survival outcome analytics. Cell, 173(2), 400-416.",
    "Lundberg, S. M. and Lee, S.-I. (2017). A unified approach to interpreting model predictions. Advances in Neural Information Processing Systems 30, 4765-4774.",
    "Lundberg, S. M. et al. (2020). From local explanations to global understanding with explainable AI for trees. Nature Machine Intelligence, 2(1), 56-67.",
    "Obermeyer, Z., Powers, B., Vogeli, C. and Mullainathan, S. (2019). Dissecting racial bias in an algorithm used to manage the health of populations. Science, 366(6464), 447-453.",
    "Parker, J. S. et al. (2009). Supervised risk predictor of breast cancer based on intrinsic subtypes. Journal of Clinical Oncology, 27(8), 1160-1167.",
    "Rajkomar, A., Hardt, M., Howell, M. D., Corrado, G. and Chin, M. H. (2018). Ensuring fairness in machine learning to advance health equity. Annals of Internal Medicine, 169(12), 866-872.",
    "Akiba, T., Sano, S., Yanase, T., Ohta, T. and Koyama, M. (2019). Optuna: a next-generation hyperparameter optimization framework. Proceedings of the 25th ACM SIGKDD Conference, 2623-2631.",
]
for r_ in sorted(refs):
    p = para(r_); p.paragraph_format.left_indent = Inches(0.4); p.paragraph_format.first_line_indent = Inches(-0.4)

for ch in ("3", "4"):
    assert fig_n[ch] == len(FIGS[ch]), (ch, fig_n[ch], len(FIGS[ch]))
    assert tab_n[ch] == len(TABS[ch]), (ch, tab_n[ch], len(TABS[ch]))
doc.save(OUT)
print("saved", OUT, "words:", sum(len(p.text.split()) for p in doc.paragraphs))
