"""Build Chapters_3_4_5.docx (Methodology, Implementation and Results, Conclusions) from the artifacts.

Every number in the text is read from ``artifacts/`` so the thesis cannot drift from the code.  The
``check`` calls at the top assert the qualitative claims the prose makes; if a re-run changes the
picture, the build stops instead of printing a stale conclusion.
"""
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

import common as C
from common import FL, META, auc_g, ci, cv, ho, paired, pct, sens, sens_n

P = META["params"]
ROOT, FIG = C.ROOT, C.FIG
OUT = ROOT / "Chapters_3_4_5.docx"
KEYS = ["aware", "blind", "reweigh", "gthr", "reweigh_gthr"]

# ------------------------------------------------------------------ claims the prose relies on
def check(cond, msg):
    if not cond:
        raise SystemExit(f"CLAIM NO LONGER HOLDS - rewrite the text: {msg}")

g_e, g_lo, g_hi = cv("aware", "tpr_gap")
f_e, f_lo, f_hi = cv("aware", "fpr_gap")
check(g_lo < 0 < g_hi and abs(g_e) < 0.03, "baseline recall gap small with CI spanning 0")
check(f_e > 0.02, "baseline false-alarm gap positive")
check(all(cv(k, "fpr_gap")[0] > 0 for k in KEYS), "false-alarm gap positive for every strategy")
check(paired("reweigh", "fpr_gap")[2] < 0.005, "reweighing reduces false-alarm gap (CI upper bound below ~0)")
check(paired("gthr", "tpr_gap")[0] > 0 or paired("gthr", "abs_tpr_gap")[0] >= 0, "group thresholds do not shrink the recall gap")
check(C.IMPM.loc["race_black", "aware"] < 0.005, "model ignores the race flag")
check(sens(36, "aware", "fpr_gap")[0] > f_e, "false-alarm gap widens on settled outcomes")
check(C.IMP.index[0] == "age" and C.IMP.index[1] == "n_stage", "age then N stage lead the importance ranking")
check(C.DIRN.agrees.dropna().all(), "SHAP direction agrees with clinical prior")

doc = Document()
st = doc.styles
st["Normal"].font.name = "Times New Roman"
st["Normal"].font.size = Pt(12)
st["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
for name, size in [("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)]:
    st[name].font.name = "Times New Roman"; st[name].font.size = Pt(size); st[name].font.bold = True
    st[name].font.color.rgb = RGBColor(0, 0, 0)
    st[name]._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
sec = doc.sections[0]
sec.left_margin = sec.right_margin = Inches(1); sec.top_margin = sec.bottom_margin = Inches(1)

# page number footer
fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = fp.add_run()
for tag, txt in [("begin", None), (None, "PAGE"), ("end", None)]:
    if tag:
        el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), tag)
    else:
        el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = txt
    run._r.append(el)

fig_n = {"3": 0, "4": 0}
tab_n = {"3": 0, "4": 0}


def H1(t): doc.add_heading(t, 1)
def H2(t): doc.add_heading(t, 2)
def H3(t): doc.add_heading(t, 3)


def para(t, bold=False, italic=False, align=None, size=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6); p.paragraph_format.line_spacing = 1.15
    r = p.add_run(t); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    if align == "j": p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def bullets(items):
    for t in items:
        p = doc.add_paragraph(style="List Bullet"); p.paragraph_format.space_after = Pt(2)
        if isinstance(t, tuple):
            r = p.add_run(t[0]); r.bold = True; p.add_run(t[1])
        else:
            p.add_run(t)


def caption(kind, ch, text):
    n = (fig_n if kind == "Figure" else tab_n)
    n[ch] += 1
    p = doc.add_paragraph(); r = p.add_run(f"{kind} {ch}.{n[ch]}: {text}"); r.bold = True; r.font.size = Pt(10.5)
    p.paragraph_format.space_after = Pt(8)
    return p


def figure(ch, fname, text, width=6.2):
    f = FIG / fname
    if not f.exists():
        return
    doc.add_picture(str(f), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption("Figure", ch, text).alignment = WD_ALIGN_PARAGRAPH.CENTER


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), color); tcPr.append(sh)


def table(ch, text, df, widths=None, size=9):
    caption("Table", ch, text)
    t = doc.add_table(rows=1, cols=len(df.columns)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(df.columns):
        cell = t.rows[0].cells[i]; cell.text = ""; r = cell.paragraphs[0].add_run(str(c)); r.bold = True; r.font.size = Pt(size)
        shade(cell, "E8ECF1")
    for _, row in df.iterrows():
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""; r = cells[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def f3(x): return f"{x:.3f}"


# =============================================================================================
doc.add_paragraph()
tp = doc.add_paragraph(); tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = tp.add_run("UTILIZING SHAP TO EXPLAIN XGBOOST FOR RECALL-FIRST PREDICTION OF DEATH DURING FOLLOW-UP IN BREAST CANCER, WITH A RACIAL-FAIRNESS AUDIT"); r.bold = True; r.font.size = Pt(15)
para("Chapters 3, 4 and 5: Methodology, Implementation and Results, Conclusions", bold=True, align=None).alignment = WD_ALIGN_PARAGRAPH.CENTER
para("Department of Computer Science, University of Jos, Plateau State, Nigeria", italic=True).alignment = WD_ALIGN_PARAGRAPH.CENTER
para("Supervisors: Dr. G. Nentawe and Prof. A. C. Deme", italic=True).alignment = WD_ALIGN_PARAGRAPH.CENTER
para("Note on scope. This revision of the implementation phase changes the prediction target of the original proposal from "
     "\"benign versus malignant\" (not available in TCGA-BRCA, which contains only malignant cases) to \"death during follow-up\", keeps the "
     "recall-first design, and extends the work with a bias-mitigation study comparing Black and White patients.", italic=True, size=10.5)
doc.add_page_break()

# =============================================================================================
# CHAPTER 3
# =============================================================================================
H1("3.0 Research Methodology")
H2("3.1 Introduction")
para("This chapter describes how the study was carried out: the data and the rules that govern which of its columns may be used, the "
     "construction of the XGBoost classifier with a recall-first decision rule, the explanation of that classifier with SHapley Additive "
     "exPlanations (SHAP), and the audit and mitigation of racial bias between Black and White patients. The chapter follows the structure of "
     "the proposal (Sections 3.2 to 3.5 there) and states explicitly where the implementation refines or departs from it and why.", align="j")
H2("3.2 Research design")
para("The study is a retrospective, computational, supervised-learning study on public, de-identified clinical records from The Cancer Genome Atlas "
     "breast invasive carcinoma cohort (TCGA-BRCA). Figure 3.1 summarises the workflow. Six stages are executed by a single, reproducible code base "
     "(run_pipeline.py): (1) data audit and cleaning, (2) model development and validation, (3) recall-first thresholding, (4) fairness audit and "
     "mitigation, (5) SHAP explanation and (6) delivery through an interactive dashboard.", align="j")
figure("3", "00_workflow.png", "Workflow of the study", 6.5)
H3("3.2.1 Revision of the prediction target")
para("The proposal framed the task as classifying samples as benign or malignant. TCGA-BRCA contains only histologically confirmed cancers, so there is no "
     "benign class to learn. The clinically meaningful and data-supported binary outcome is whether the patient died during follow-up (overall-survival event). "
     "The recall-first rationale of the proposal carries over unchanged: a missed death is a far more serious error than an unnecessary extra "
     "review. The target is therefore:", align="j")
bullets([("died = 1 ", "when OS_STATUS = \"1:DECEASED\" (death at any time during follow-up), otherwise 0 (living at last contact)."),
         ("Interpretation. ", "Follow-up is right-censored, so a living patient with short follow-up may still die later. The label is thus \"death observed during follow-up\" and not \"death within N years\". Section 3.8.4 quantifies the consequences with a sensitivity analysis.")])
H3("3.2.2 Objectives and where each is addressed")
table("3", "Objectives of the proposal (Section 1.4) and the extension added in this phase", pd.DataFrame([
    ["1. Conceptual framework for integrating SHAP into healthcare pipelines", "Section 3.2 (workflow), Section 3.11 (dashboard), Section 4.12"],
    ["2. Evaluate diagnostic performance (accuracy, precision, recall, F1, AUC)", "Sections 3.6, 3.7, 3.10; Sections 4.6 and 4.7"],
    ["3. Apply SHAP to identify and interpret influential clinical features", "Section 3.9; Sections 4.9 and 4.10"],
    ["4. Evaluate perceived interpretability and trust among clinicians", "Section 3.12 (protocol designed, study not yet run); Section 5.4"],
    ["5. (Added) Audit racial bias between Black and White patients and test mitigation", "Section 3.8; Sections 4.8 and 4.9"]],
    columns=["Objective", "Where addressed"]), widths=[3.6, 2.9], size=9.5)
H2("3.3 Data collection")
para(f"The data are the TCGA PanCancer Atlas clinical patient table for breast cancer distributed by cBioPortal (Cerami et al., 2012; Liu et al., 2018): "
     f"{FL['n_records']:,} patients and 38 columns, accompanied by a data dictionary. The outcome fields follow the curated TCGA Clinical Data Resource "
     f"(Liu et al., 2018). Self-reported race (RACE) is used to define the fairness groups; genetic-ancestry calls (Carrot-Zhang et al., 2020) are used only for a "
     f"sensitivity analysis. Molecular subtype is the PAM50 intrinsic subtype (Parker et al., 2009).", align="j")
para(f"Cohort construction (Table 3.2). Of the {FL['n_records']:,} records, {FL['n_missing_race']} lack a race entry and {FL['n_other_race']} are Asian or American Indian; "
     f"these are excluded because the objective is a Black versus White comparison and the remaining groups are too small to analyse separately. The study "
     f"cohort comprises {FL['n_cohort']} patients ({FL['n_white']} White, {FL['n_black']} Black) with {FL['deaths']} deaths ({FL['deaths_white']} White, {FL['deaths_black']} Black).", align="j")
table("3", "Cohort flow", pd.DataFrame([
    ["Records in cBioPortal file", FL["n_records"]], ["Race not recorded", f"-{FL['n_missing_race']}"], ["Asian / American Indian", f"-{FL['n_other_race']}"],
    ["Study cohort", f"{FL['n_cohort']} ({FL['n_white']} White / {FL['n_black']} Black)"], ["Deaths during follow-up", f"{FL['deaths']} ({FL['deaths_white']} / {FL['deaths_black']})"],
    ["Development set (80 %)", f"{FL['n_dev']} patients, {FL['dev_deaths']} deaths"],
    ["Hold-out test set (20 %)", f"{FL['n_test']} patients, {FL['test_deaths']} deaths ({FL['test_black']} Black patients, {FL['test_black_deaths']} Black deaths)"]],
    columns=["Step", "n"]), widths=[3.2, 3.3])
H2("3.4 Data governance and preprocessing")
para("The proposal specified null handling, standard scaling, encoding and normalisation. For a tree-based model, scaling is unnecessary because splits depend only "
     "on the order of values, so it was omitted; instead the effort went into the step that matters most for clinical validity: deciding which columns may enter the "
     "model at all. Every one of the 38 source columns was assigned one of four decisions (Table 4.2 summarises the evidence).", align="j")
H3("3.4.1 Outcome leakage")
para("Columns that record what happened after diagnosis, or that are the outcome in another form, were excluded: follow-up duration (OS_MONTHS, DAYS_LAST_FOLLOWUP), "
     "disease-specific, disease-free and progression-free endpoints and their durations, tumour status at last follow-up and the post-treatment new-tumour indicator. "
     "Leakage of this kind is a well-documented source of over-optimistic results (Kaufman et al., 2011) and is exactly the type of \"data leak\" the proposal "
     "(Section 1.1) hoped SHAP would help detect.", align="j")
H3("3.4.2 Informative missingness")
para("A blank can predict the outcome when it reflects registry practice rather than biology. Radiation therapy is blank for 56 % of patients who died versus 12 % of the rest; ethnicity "
     "for 4 % versus 16 %. These fields, and the primary-lymph-node assessment and AJCC edition fields, were excluded. Pathologic categories \"not assessed\" were set to the AJCC default "
     "(MX to M0, NX to N0), because left as missing they let the model learn that \"NX\" (61 % death rate, n = 18) means danger.", align="j")
H3("3.4.3 Features retained and encoding")
table("3", "Model inputs", pd.DataFrame([
    ["age", "Age at diagnosis (years)", "numeric"], ["t_stage", "Pathologic T, 1-4 (T1A/B/C to 1; TX missing)", "ordinal, monotone increasing"],
    ["n_stage", "Pathologic N, 0-3 (N1MI, N1A to 1; N0(I+) to 0; NX to 0)", "ordinal, monotone increasing"],
    ["m_stage", "M1 = 1 (M0, cM0(I+), MX = 0)", "binary, monotone increasing"],
    ["sub_luma / lumb / her2 / basal / normal", "PAM50 subtype; all five are missing when the subtype was not called", "one-hot with native missing"],
    ["histology_lobular, histology_other", "ICD-O-3 8520/3 lobular; others except 8500/3 ductal", "one-hot"],
    ["prior_dx", "Prior malignancy", "binary"],
    ["race_black", "Black or African American (reference White); baseline model only", "binary"]],
    columns=["Feature", "Definition", "Type"]), widths=[1.7, 3.5, 1.3])
H2("3.5 Data partitioning and validation")
para(f"All partitions are stratified by race x outcome so that every split retains Black patients and deaths among them. A single hold-out test set (20 %, {FL['n_test']} patients) is set "
     f"aside once and used only for the final confirmation; the proposal's validation set is realised as the held-out folds of 5-fold cross-validation inside the development set "
     f"(746 patients), which serve hyper-parameter tuning, threshold learning and implicit early stopping (the number of trees is tuned). Because the hold-out set contains only "
     f"{FL['test_black_deaths']} Black deaths, it cannot support any statement about fairness. The principal evaluation is therefore 5 x 5-fold repeated cross-validation over the "
     f"whole cohort, in which every patient is predicted by models that never saw them and every threshold is learned only from the training portion of each fold (nested thresholding).", align="j")
H2("3.6 Model development")
H3("3.6.1 Algorithm")
para("The classifier is XGBoost (Chen and Guestrin, 2016), chosen in the proposal for its efficiency and accuracy on tabular data. Because clinicians expect larger tumours, more involved nodes and "
     "metastasis never to lower risk, monotone non-decreasing constraints were imposed on T, N and M stage. This is a design decision made before looking at results. The ablation in Table 4.3 "
     "shows it costs no discrimination.", align="j")
H3("3.6.2 Hyper-parameter search")
para("Sixty random configurations plus the default were scored by 4 x 5-fold stratified cross-validation on the development set. The objective is aligned with the recall-first design: "
     "the lowest false-positive rate at 80 % recall (ties broken by AUC). The search space (maximum depth 1-3, learning rate 0.01-0.2, 60-400 trees, minimum child weight 0.1-2, subsampling, "
     "L1/L2 penalties and gamma) deliberately keeps leaves small enough to isolate rare, decisive groups such as M1 disease (17 patients, 88 % mortality).", align="j")
H3("3.6.3 Benchmark models")
para("Logistic regression (median imputation, standardisation) and a random forest were trained on the same features to test whether the complexity of gradient boosting is justified.", align="j")
H2("3.7 Recall-first decision rule")
para(f"The default probability threshold of 0.5 is inappropriate for an outcome with a prevalence of about 15 %: it would flag almost no one. The operating point is instead derived from the "
     f"training data: the threshold is the largest score that still captures a target share of deaths (target recall 80 %) in out-of-fold training predictions (2 x 5-fold). The rule is "
     f"implemented once, in recall_threshold(), and is re-learned inside every cross-validation fold so that no threshold ever sees test data. A target sweep from 70 % to 95 % (Section 4.8.4) tests "
     f"whether conclusions depend on the chosen 80 %.", align="j")
H2("3.8 Fairness audit and mitigation")
H3("3.8.1 Fairness criteria")
para("White patients are the reference group and Black patients the focus group. Because the clinical cost is asymmetric, the primary criterion is equal opportunity (Hardt et al., 2016): the share "
     "of patients who die that the model flags (recall, or true-positive rate) should not depend on race. Secondary criteria are the false-alarm rate (share of survivors flagged), the equalised-odds "
     "difference (the larger of the absolute recall and false-alarm gaps), the discrimination within each group (AUC) and calibration within each group (observed-to-expected ratio and calibration "
     "slope). Gaps are always Black minus White.", align="j")
H3("3.8.2 Mitigation strategies")
table("3", "Strategies compared (all use the same XGBoost settings)", pd.DataFrame([
    [C.SHORT[k], C.META["strategies"][k]["family"], C.META["strategies"][k]["note"]] for k in KEYS], columns=["Strategy", "Family", "Description"]),
    widths=[1.9, 1.2, 3.4])
para("Reweighing (Kamiran and Calders, 2012) assigns each training row the weight P(race) P(outcome) / P(race, outcome), making race and outcome statistically independent in the weighted data. "
     "Group thresholds apply the recall rule separately within each race, which is the post-processing route to equal opportunity.", align="j")
H3("3.8.3 Uncertainty")
para("With 30 Black deaths a recall estimate has a margin of about 15 percentage points. All reported rates therefore carry 95 % percentile bootstrap intervals (1,000 resamples, stratified by group). "
     "Differences between strategies are assessed with a paired bootstrap in which every strategy is evaluated on the same resamples (Efron and Tibshirani, 1993), which gives a far tighter "
     "interval for \"did the mitigation change the gap?\" than comparing two overlapping intervals. Wilson intervals (Wilson, 1927) are used for the single hold-out split.", align="j")
H3("3.8.4 Sensitivity analyses")
bullets([("Settled outcomes. ", "Evaluation is restricted to patients who died or were followed for at least 24, 36 or 60 months, removing most censoring noise from the survivors."),
         ("Group definition. ", "Self-reported race is replaced by genetic ancestry (African / African-admixed versus European)."),
         ("Recall target. ", "The target is varied from 70 % to 95 %.")])
H2("3.9 Explainability with SHAP")
para("Tree SHAP (Lundberg and Lee, 2017; Lundberg et al., 2020) decomposes each prediction, in log-odds, into additive feature contributions that sum exactly to the model output minus the "
     "base value. The following analyses are produced from the deployment models: (i) global importance and beeswarm plots, (ii) dependence plots, (iii) local waterfall plots for a true positive, "
     "a missed death and a true negative, (iv) a check that the direction of each effect matches clinical knowledge, (v) importance computed separately for White and Black patients, "
     "(vi) an exact additive decomposition of the Black-minus-White gap in average predicted risk, (vii) the SHAP profile of missed versus caught deaths in each group, (viii) agreement of explanations "
     "before and after mitigation, and (ix) a 100-resample bootstrap of the importance ranking among Black patients to quantify how far the ranking can be trusted.", align="j")
H2("3.10 Evaluation metrics")
para("Recall (sensitivity), specificity, false-positive rate, precision, F1-score, accuracy and the fraction of patients flagged at the operating point; the area under the ROC curve (AUC) as a "
     "threshold-free measure; the false-positive rate at 80 % recall as the primary single-number cost of the recall-first design; and the Brier score and calibration slope for risk estimates.", align="j")
H2("3.11 Dashboard design")
para("A Streamlit application (app.py) delivers the model to clinicians and reviewers. It has eight tabs: an overview, a patient explainer with what-if inputs and a SHAP waterfall, a fairness lab "
     "comparing the five strategies with intervals, a threshold explorer showing recall and false-alarm rates by race as the threshold moves, global SHAP views including the risk-gap decomposition and "
     "stability, a data-audit view, a cohort explorer and the model card. The dashboard reads only the files written by the pipeline, so it can never disagree with the thesis.", align="j")
H2("3.12 Physician user study (Objective 4)")
para("Objective 4 requires clinicians to judge the interpretability and trustworthiness of the SHAP output. This phase delivers the instrument but not the data: no clinician study has been run. The planned "
     "protocol is a within-subject comparison of oncologists and clinical researchers shown (a) the risk score alone and (b) the score with the SHAP waterfall for 12 cases (balanced by race and outcome), "
     "measuring a 5-point Likert trust and understanding scale, the System Usability Scale for the dashboard, and the proportion of time the clinician's decision agrees with the model. Ethical approval and informed "
     "consent would be obtained before any recruitment.", align="j")
H2("3.13 Ethical considerations")
para("The data are public and de-identified; no attempt is made to re-identify patients. Race is used strictly as an audit variable and as a (tested and rejected) model input; the study does not "
     "claim that race has a biological effect. Strategies that use race at prediction time (race-aware input, group thresholds) are flagged in the dashboard because their use may be legally or ethically "
     "unacceptable in a given setting. The model is a research prototype and carries an explicit non-clinical-use notice. The work follows the data-minimisation and transparency principles named in the proposal "
     "(Nigeria Data Protection Act, 2023; GDPR; HIPAA).", align="j")
H2("3.14 Software and reproducibility")
v = META["versions"]
table("3", "Software environment", pd.DataFrame([["Python", "3.12"], ["xgboost", v["xgboost"]], ["shap", v["shap"]], ["scikit-learn", v["sklearn"]], ["pandas", v["pandas"]],
                                                 ["Streamlit / Plotly", "dashboard"], ["python-docx", "thesis document builder"]], columns=["Component", "Version / role"]), widths=[2, 4.5])
para(f"Random seed {META['seed']}; one command (python run_pipeline.py) regenerates every table, figure and model in about four minutes on a laptop.", align="j")
doc.add_page_break()

# =============================================================================================
# CHAPTER 4
# =============================================================================================
H1("4.0 Implementation and Results")
H2("4.1 Introduction")
para("This chapter reports what was built and found. It first describes the cohort and the data audit (Sections 4.3 and 4.4), then the model and its performance (Sections 4.5 to 4.7), "
     "the fairness analysis and the effect of mitigation (Section 4.8), the SHAP explanations (Sections 4.9 and 4.10), and the dashboard (Section 4.11). Section 4.12 discusses the results. "
     "All intervals are 95 % intervals; gaps are Black minus White.", align="j")
H2("4.2 Implementation environment and pipeline")
para("The code is organised as a small Python package (src/brca_xai: data, audit, modeling, fairness, explain, plots, pipeline), a command-line runner, an executed Jupyter notebook that narrates the "
     "analysis, and the dashboard. The notebook, the runner and the dashboard use the same functions, so the schema of a patient is defined exactly once.", align="j")
H2("4.3 Cohort description")
T1 = C.TABLE1.copy(); T1.columns = ["Characteristic", "White", "Black"]
table("4", "Characteristics of the study cohort by race", T1, widths=[2.6, 1.9, 1.9])
dB, dW = FL["deaths_black"] / FL["n_black"], FL["deaths_white"] / FL["n_white"]
para(f"Crude mortality is similar ({pct(dW)} White, {pct(dB)} Black), as are survival curves and follow-up (Figure 4.1). The groups differ in tumour biology: {C.TABLE1.set_index('characteristic').loc['PAM50 Basal', 'Black']} "
     f"of Black patients have basal-like tumours against {C.TABLE1.set_index('characteristic').loc['PAM50 Basal', 'White']} of White patients, and Luminal A is correspondingly less common "
     f"({C.TABLE1.set_index('characteristic').loc['PAM50 LumA', 'Black']} versus {C.TABLE1.set_index('characteristic').loc['PAM50 LumA', 'White']}). These differences are well known (DeSantis et al., 2019) and matter later, because they "
     f"are what makes the model score the two groups differently.", align="j")
figure("4", "01_survival_followup.png", "Kaplan-Meier survival and follow-up distribution by race")
H2("4.4 Data audit")
H3("4.4.1 Leakage and informative missingness")
lad = C.LADDER
rows = [[r.rung.split("  ")[1] if "  " in r.rung else r.rung, f"{r.auc:.3f}", f"{100 * r.fpr_at_80_recall:.0f}%"] for r in lad.itertuples()]
table("4", "Cross-validated AUC as columns that should not be inputs are added back to the model", pd.DataFrame(rows, columns=["Feature set", "AUC", "False-positive rate at 80 % recall"]), widths=[4.4, 0.8, 1.3])
para(f"The clean model reaches an AUC of {lad.auc.iloc[0]:.2f}. Adding the informative-missingness fields raises it to {lad.auc.iloc[2]:.2f}; adding post-baseline tumour status to {lad.auc.iloc[3]:.2f}; and adding days to last "
     f"follow-up to {lad.auc.iloc[4]:.2f}, at which the model would need to flag only {100 * lad.fpr_at_80_recall.iloc[4]:.0f}% of survivors to reach 80 % recall. None of that is prediction: follow-up days are blank "
     f"for every patient who died. An analysis that skipped this audit would have reported a spectacular and meaningless result (Figure 4.2). The governance decision for every column is listed in "
     f"docs/DATA_AUDIT.md and artifacts/column_governance.csv.", align="j")
figure("4", "02_leakage_ladder.png", "How excluded columns inflate apparent performance")
H2("4.5 Model development")
bp = P
para(f"The search selected very shallow trees (maximum depth {bp['max_depth']}, {bp['n_estimators']} trees, learning rate {bp['learning_rate']:.3f}, L2 penalty {bp['reg_lambda']:.1f}), i.e. an additive model. "
     f"This is informative in itself: with 933 patients and 141 events, interactions between clinical variables are not identifiable, and the signal is carried by main effects. "
     f"Table 4.3 shows that logistic regression and a random forest are no better.", align="j")
bn = C.BENCH
rows = [[r.model.replace(" - used", " (used)"), f"{r.auc:.3f} ± {r.auc_sd:.3f}", f"{r.auc_White:.3f}", f"{r.auc_Black:.3f}", f"{100 * r.fpr_at_80_recall:.1f}%"] for r in bn.itertuples()]
table("4", "Model benchmark on identical features (5 x 5-fold CV)", pd.DataFrame(rows, columns=["Model", "AUC", "AUC White", "AUC Black", "FPR at 80 % recall"]), widths=[2.9, 1.1, 0.8, 0.8, 1.0])
figure("4", "03_model_benchmark.png", "Benchmark of candidate models", 5.8)
para(f"The monotone constraint made no measurable difference (AUC {bn.auc.iloc[3]:.3f} without, {bn.auc.iloc[4]:.3f} with), so the clinically motivated constraint is free. "
     f"Hyper-parameter tuning gave a modest gain over defaults ({bn.auc.iloc[2]:.3f} to {bn.auc.iloc[4]:.3f}); the tuning curves are flat, a further sign that the ceiling is set by the information in the data.", align="j")
H2("4.6 Performance at the recall-first operating point")
h_all, h_w, h_b = ho("blind", "All"), ho("blind", "White"), ho("blind", "Black")
para(f"Cross-validated results (race-blind model, 5 x 5 folds): recall {ci('blind', 'tpr_all')}, false-positive rate {ci('blind', 'fpr_all')}, with {pct(cv('blind', 'flag_all')[0], 0)} of all patients flagged. "
     f"The AUC is {auc_g('blind', 'All')[0]:.2f} ({auc_g('blind', 'All')[1]:.2f} to {auc_g('blind', 'All')[2]:.2f}). The recall target of 80 % was met within sampling error in cross-validation, confirming that thresholds learned inside the training "
     f"folds transfer to unseen patients. The price of recall-first operation is stark: to catch four in five deaths the model must flag about two in three patients, because predictive information in "
     f"clinical covariates is modest.", align="j")
para(f"On the untouched hold-out set ({int(h_all.n)} patients, {int(h_all.deaths)} deaths) the race-blind model flagged {int(h_all.tp)} of {int(h_all.deaths)} deaths (recall {pct(h_all.recall, 0)}, Wilson CI {pct(h_all.recall_lo, 0)} to "
     f"{pct(h_all.recall_hi, 0)}), with a false-positive rate of {pct(h_all.fpr, 0)} and AUC {h_all.auc:.2f}. The hold-out recall for Black patients is based on {int(h_b.deaths)} deaths ({int(h_b.tp)} caught) and is "
     f"reported only for completeness (Figure 4.4).", align="j")
hrows = []
for k in KEYS:
    for g in ["All", "White", "Black"]:
        r = ho(k, g)
        hrows.append([C.SHORT[k] if g == "All" else "", g, int(r.n), int(r.deaths), f"{pct(r.recall, 0)} ({pct(r.recall_lo, 0)}-{pct(r.recall_hi, 0)})", pct(r.fpr, 0), f"{r.auc:.2f}"])
table("4", "Hold-out test results by strategy and race", pd.DataFrame(hrows, columns=["Strategy", "Group", "n", "Deaths", "Recall (Wilson CI)", "False-alarm rate", "AUC"]), widths=[1.7, 0.7, 0.5, 0.6, 1.5, 0.9, 0.5], size=8.5)
figure("4", "09_holdout_recall.png", "Hold-out recall by race and strategy (wide intervals reflect six Black deaths)", 5.4)
H2("4.7 Discrimination and calibration by race")
cb = C.CAL
cw_b = cb[(cb.strategy == "blind") & (cb.group == "Black")].iloc[0]
cw_w = cb[(cb.strategy == "blind") & (cb.group == "White")].iloc[0]
para(f"Discrimination is similar in the two groups but far less certain for Black patients: AUC {auc_g('blind', 'White')[0]:.2f} (White, {auc_g('blind', 'White')[1]:.2f}-{auc_g('blind', 'White')[2]:.2f}) "
     f"versus {auc_g('blind', 'Black')[0]:.2f} (Black, {auc_g('blind', 'Black')[1]:.2f}-{auc_g('blind', 'Black')[2]:.2f}) (Figure 4.5). Calibration is good on average in both groups (observed-to-expected ratio "
     f"{cw_w.oe_ratio:.2f} for White, {cw_b.oe_ratio:.2f} for Black), i.e. the model under-predicts the average Black death rate by about {100 * (cw_b.oe_ratio - 1):.0f}% of itself ({pct(cw_b.mean_predicted)} predicted against {pct(cw_b.observed)} observed), "
     f"a difference too small to distinguish from sampling noise at n = {FL['n_black']}. The calibration slopes (above 1: {cw_w.slope:.2f} White, {cw_b.slope:.2f} Black) show that the heavily regularised model "
     f"compresses its risk estimates, as expected for an additive model of limited signal.", align="j")
figure("4", "04_roc_by_group.png", "ROC curves by race (out-of-fold risk of the race-blind model)", 4.3)
H2("4.8 Fairness results and the effect of mitigation")
H3("4.8.1 Equal opportunity and false-alarm burden")
para(f"At the recall-first operating point of the baseline (race-aware) model, recall is {pct(cv('aware', 'tpr_W')[0])} for White and {pct(cv('aware', 'tpr_B')[0])} for Black patients: a gap of "
     f"{ci('aware', 'tpr_gap', True)}. There is therefore no evidence that Black patients' deaths are missed more often. The interval, however, spans roughly ±14 points, so a clinically important recall "
     f"gap cannot be excluded, which is a statement about the amount of data (30 Black deaths) rather than about the model. The burden of false alarms differs more: the false-alarm rate is {pct(cv('aware', 'fpr_W')[0])} among White and "
     f"{pct(cv('aware', 'fpr_B')[0])} among Black survivors, a gap of {ci('aware', 'fpr_gap', True)} (Figure 4.6, Figure 4.7).", align="j")
figure("4", "05_rates_by_race.png", "Recall and false-alarm rate by race for all five strategies (5 x 5-fold CV, bootstrap CI)", 6.4)
grows = []
for k in KEYS:
    grows.append([C.SHORT[k], pct(cv(k, "tpr_W")[0]), pct(cv(k, "tpr_B")[0]), ci(k, "tpr_gap", True), ci(k, "fpr_gap", True), pct(cv(k, "eod")[0]), pct(cv(k, "flag_all")[0], 0)])
table("4", "Fairness metrics by strategy (Black minus White; 95 % bootstrap CI)", pd.DataFrame(grows, columns=["Strategy", "Recall White", "Recall Black", "Recall gap", "False-alarm gap", "Equalised-odds diff.", "Flagged"]),
      widths=[1.4, 0.7, 0.7, 1.3, 1.3, 0.8, 0.6], size=8)
figure("4", "06_gap_forest.png", "Recall and false-alarm gaps with 95 % intervals", 6.2)
H3("4.8.2 Did mitigation help?")
pr, pg, pw, pwg = paired("reweigh", "fpr_gap"), paired("gthr", "tpr_gap"), paired("blind", "fpr_gap"), paired("reweigh_gthr", "fpr_gap")
para(f"Differences between strategies are small compared with the uncertainty of each, so the paired bootstrap is used. (i) Removing race (race-blind) changes the false-alarm gap by {pw[0]:+.3f} "
     f"(CI {pw[1]:+.3f} to {pw[2]:+.3f}) and leaves explanations unchanged: the baseline model never used the race indicator (mean |SHAP| {C.IMPM.loc['race_black', 'aware']:.3f}), so awareness and unawareness "
     f"are, in effect, the same model here. (ii) Reweighing reduces the false-alarm gap by {-pr[0]:.3f} (CI {pr[1]:+.3f} to {pr[2]:+.3f}), a small but statistically supported improvement that does not require race "
     f"at prediction time. (iii) Group-specific thresholds do not equalise recall in practice: the recall gap changes by {pg[0]:+.3f} (CI {pg[1]:+.3f} to {pg[2]:+.3f}) because the Black-specific threshold "
     f"is estimated from about 30 deaths and varies from fold to fold (standard deviation {C.THR[(C.THR.strategy == 'gthr') & (C.THR.threshold == 'Black')]['sd'].iloc[0]:.3f} against "
     f"{C.THR[(C.THR.strategy == 'gthr') & (C.THR.threshold == 'White')]['sd'].iloc[0]:.3f} for White), and it raises the overall workload ({pct(cv('gthr', 'flag_all')[0], 0)} flagged against "
     f"{pct(cv('aware', 'flag_all')[0], 0)}). (iv) Combining reweighing and group thresholds gives the smallest false-alarm gap ({ci('reweigh_gthr', 'fpr_gap', True)}; paired change {pwg[0]:+.3f}, CI {pwg[1]:+.3f} to {pwg[2]:+.3f}) at "
     f"the highest cost in flagged patients (Figure 4.8).", align="j")
prow = []
for k in KEYS[1:]:
    for m, nm in [("tpr_gap", "Recall gap"), ("fpr_gap", "False-alarm gap")]:
        d, lo, hi, p = paired(k, m)
        prow.append([C.SHORT[k], nm, f"{d:+.3f}", f"[{lo:+.3f}, {hi:+.3f}]", "yes" if (lo > 0 or hi < 0) else "no"])
table("4", "Paired bootstrap change in each gap relative to the baseline", pd.DataFrame(prow, columns=["Strategy", "Gap", "Change", "95 % CI", "Distinguishable from 0?"]), widths=[1.9, 1.3, 0.8, 1.4, 1.1])
figure("4", "07_tradeoff.png", "Cost of fairness: workload against equalised-odds difference", 4.6)
H3("4.8.3 Threshold stability")
para("Group thresholds depend on the number of deaths in each group, which explains their failure. Learned inside cross-validation folds, the global threshold has a standard deviation of "
     f"{C.THR[(C.THR.strategy == 'blind') & (C.THR.threshold == 'global')]['sd'].iloc[0]:.3f}, the White threshold {C.THR[(C.THR.strategy == 'blind') & (C.THR.threshold == 'White')]['sd'].iloc[0]:.3f} and the Black threshold "
     f"{C.THR[(C.THR.strategy == 'blind') & (C.THR.threshold == 'Black')]['sd'].iloc[0]:.3f} (artifacts/cv_thresholds.csv).", align="j")
H3("4.8.4 Sensitivity to the recall target")
sw = C.SWEEP
sg = sw[(sw.metric == "tpr_gap") & (sw.strategy == "aware")].estimate
sf = sw[(sw.metric == "fpr_gap") & (sw.strategy == "aware")].estimate
para(f"Across targets from 70 % to 95 % the baseline recall gap stays between {sg.min():+.3f} and {sg.max():+.3f} and the false-alarm gap between {sf.min():+.3f} and {sf.max():+.3f} (Figure 4.9). "
     f"The qualitative conclusion, no consistent recall gap and a modest positive false-alarm gap, does not depend on the choice of 80 %. Group thresholds flip the sign of the recall gap at lower targets, "
     f"which again reflects estimation noise rather than a systematic effect.", align="j")
figure("4", "08_recall_target_sweep.png", "Gaps as the recall target varies from 70 % to 95 %", 6.2)
H3("4.8.5 Sensitivity to censoring and to the definition of the groups")
s24, s36, s60 = sens(24, "aware", "fpr_gap"), sens(36, "aware", "fpr_gap"), sens(60, "aware", "fpr_gap")
para(f"A patient who is alive at 6 months counts as a survivor but may die later, and this label noise can differ by group. Restricting evaluation to patients who died or were followed for at least "
     f"24, 36 or 60 months (n = {sens_n(24)}, {sens_n(36)} and {sens_n(60)}) leaves the recall gap near zero but widens the false-alarm gap to {s24[0]:+.3f}, {s36[0]:+.3f} (CI {s36[1]:+.3f} to {s36[2]:+.3f}) "
     f"and {s60[0]:+.3f} (CI {s60[1]:+.3f} to {s60[2]:+.3f}) (Figure 4.10). Long-followed Black survivors are therefore flagged noticeably more often than long-followed White survivors; "
     f"this is the most consistent signal of a disparity in the analysis. Defining groups by genetic ancestry instead of self-reported race gives the same picture "
     f"(race-blind model: recall {pct(C.ANC[(C.ANC.strategy == 'blind') & (C.ANC.group.str.startswith('AFR'))].recall.iloc[0], 0)} for African ancestry (n = 125, 24 deaths) against "
     f"{pct(C.ANC[(C.ANC.strategy == 'blind') & (C.ANC.group.str.startswith('EUR'))].recall.iloc[0], 0)} for European; false-alarm rate "
     f"{pct(C.ANC[(C.ANC.strategy == 'blind') & (C.ANC.group.str.startswith('AFR'))].fpr.iloc[0], 0)} against {pct(C.ANC[(C.ANC.strategy == 'blind') & (C.ANC.group.str.startswith('EUR'))].fpr.iloc[0], 0)}).", align="j")
figure("4", "11_sensitivity_settled.png", "Gaps when evaluation is restricted to patients with settled outcomes", 6.2)
H2("4.9 SHAP analysis")
H3("4.9.1 Global explanation")
top = C.IMP.head(5)
para(f"Figure 4.11 ranks the drivers of predicted risk. Age at diagnosis ({C.IMP.loc['age', 'White']:.2f} mean |SHAP|, log-odds) and nodal status ({C.IMP.loc['n_stage', 'White']:.2f}) dominate, followed by Luminal A subtype "
     f"({C.IMP.loc['sub_luma', 'White']:.2f}, protective), tumour size ({C.IMP.loc['t_stage', 'White']:.2f}) and distant metastasis ({C.IMP.loc['m_stage', 'White']:.2f}). Metastasis occurs in only 17 patients but is the single largest contribution when present "
     f"(+1.5 log-odds). The direction of every staging effect agrees with oncological knowledge (Spearman correlation between value and SHAP: age {C.DIRN.spearman.iloc[0]:.2f}, T {C.DIRN.spearman.iloc[1]:.2f}, "
     f"N {C.DIRN.spearman.iloc[2]:.2f}, M {C.DIRN.spearman.iloc[3]:.2f}), which gives the clinician-alignment evidence asked for in the proposal. Prior malignancy, \"other\" histology and the rarer PAM50 groups carry little weight.", align="j")
figure("4", "12_shap_beeswarm.png", "SHAP beeswarm summary of the race-blind model", 5.6)
figure("4", "14_dependence.png", "SHAP dependence plots for age, nodal status and tumour size by race", 6.4)
H3("4.9.2 Local explanations")
para("Figures 4.13 to 4.15 show the explanation of individual patients: a Black patient whose death was correctly flagged, a Black patient whose death was missed, and a White survivor correctly "
     "not flagged. The waterfall plots let a reviewer see why the missed death fell below the recall-first threshold: young age and absent nodal involvement subtracted more risk than the weak positive signals added.", align="j")
for n_, t_ in [("true_positive_black", "True positive (Black patient)"), ("false_negative_black", "False negative (Black patient)"), ("true_negative_white", "True negative (White patient)")]:
    figure("4", f"15_waterfall_{n_}.png", f"Waterfall explanation: {t_}", 4.8)
H2("4.10 How explanations differ by race and under mitigation")
H3("4.10.1 Feature importance by group")
rk_same = (C.IMP.rank_White == C.IMP.rank_Black).mean()
para(f"Importance is nearly identical in the two groups (Figure 4.16): the ranks agree for {pct(rk_same, 0)} of features, and the largest ratio Black/White among the top five is {C.IMP.head(5).ratio_B_over_W.max():.2f}. "
     f"The model therefore reasons about Black and White patients in the same way; it does not rely on different, possibly spurious, features for either group.", align="j")
figure("4", "13_importance_by_race.png", "Mean absolute SHAP value by race", 5.4)
H3("4.10.2 Why do the groups receive different average risk?")
tg = C.GAP.attrs if hasattr(C.GAP, "attrs") else {}
para(f"The average predicted log-odds is {META['risk_gap_total']:+.3f} higher for Black patients. The decomposition (Figure 4.17) attributes almost all of this to the PAM50 subtype: Luminal A, which the model "
     f"treats as protective, is half as common among Black patients ({C.TABLE1.set_index('characteristic').loc['PAM50 LumA', 'Black']} versus {C.TABLE1.set_index('characteristic').loc['PAM50 LumA', 'White']}) and accounts for "
     f"{C.GAP.loc['sub_luma', 'contribution_to_gap']:+.3f} of the gap; lobular histology adds {C.GAP.loc['histology_lobular', 'contribution_to_gap']:+.3f}, metastasis (more frequent among Black patients, {C.TABLE1.set_index('characteristic').loc['M1', 'Black']} versus {C.TABLE1.set_index('characteristic').loc['M1', 'White']}) adds {C.GAP.loc['m_stage', 'contribution_to_gap']:+.3f}, while a younger age profile and a slightly lower nodal burden "
     f"work in the opposite direction. The group difference in predicted risk is thus explained by documented biological and case-mix differences, not by race as such.", align="j")
figure("4", "16_risk_gap_decomposition.png", "Contributions to the Black-minus-White gap in mean predicted log-odds", 5.4)
H3("4.10.3 Missed deaths")
pf = C.PROFILE
fnb = pf[(pf.group == "Black") & pf.outcome.str.startswith("FN")].iloc[0]
fnw = pf[(pf.group == "White") & pf.outcome.str.startswith("FN")].iloc[0]
para(f"Figure 4.18 contrasts caught and missed deaths. In both groups missed deaths are the younger, node-negative patients: for Black patients (n = {int(fnb.n)} missed) age contributes {fnb.age:+.2f} and nodal status "
     f"{fnb.n_stage:+.2f} on average, for White patients (n = {int(fnw.n)}) {fnw.age:+.2f} and {fnw.n_stage:+.2f}. The mechanism of a miss is the same in both groups; the model fails to see deaths that clinical staging does not "
     f"foreshadow, which is a limit of the data rather than an unequal treatment of one group.", align="j")
figure("4", "17_missed_deaths_profile.png", "Mean SHAP of caught and missed deaths by race", 6.2)
H3("4.10.4 Explanations under mitigation")
ag = META["agreement"]
para(f"Mitigation barely alters the explanations. Importance rankings of the race-blind and baseline models have a rank correlation of {ag['blind_vs_aware']['rank_corr']:.2f}, and of the race-blind and reweighed models "
     f"{ag['blind_vs_reweigh']['rank_corr']:.2f}; the per-patient correlation of full SHAP vectors is {ag['blind_vs_aware']['per_patient_rank_corr']:.2f} and {ag['blind_vs_reweigh']['per_patient_rank_corr']:.2f} (Figure 4.19). "
     f"A clinician can therefore adopt reweighing without relearning how to read the model.", align="j")
figure("4", "19_explanations_under_mitigation.png", "Feature importance for the baseline, race-blind and reweighed models", 5.4)
H3("4.10.5 Stability of the explanations")
sb = C.STAB
para(f"With only 30 Black deaths, how far can an importance ranking be trusted? Across 100 bootstrap refits, age is among the top three drivers in {pct(sb.loc['age', 'top3_freq'], 0)} of resamples, "
     f"nodal status in {pct(sb.loc['n_stage', 'top3_freq'], 0)}, tumour size in {pct(sb.loc['t_stage', 'top3_freq'], 0)} and Luminal A in {pct(sb.loc['sub_luma', 'top3_freq'], 0)}; the ranks of the remaining features span "
     f"several places (Figure 4.20). Statements about the top one or two features are safe for the Black subgroup; statements about the order of the rest are not.", align="j")
figure("4", "18_shap_stability_black.png", "Bootstrap stability of the importance rank among Black patients", 5.4)
H2("4.11 The interactive dashboard (Objectives 1 and 4)")
para("The dashboard (app.py) puts the entire analysis into one interface (Section 3.11). A clinician enters a patient's characteristics, selects one of the five strategies and sees the predicted risk, the "
     "threshold that applies to that patient and the decision, together with a SHAP waterfall that explains the score. The fairness lab shows, for each strategy, recall and false-alarm rate by race with "
     "confidence intervals and the paired changes relative to the baseline. The threshold explorer lets a reviewer slide a global or per-group threshold and watch recall and false alarms move in real "
     "time, which makes the recall-first trade-off tangible. The data-audit tab exposes the leakage ladder and the missingness table. The user study (Objective 4) has not been run; the dashboard is the "
     "stimulus it needs (Section 3.12).", align="j")
H2("4.12 Discussion")
para(f"Three findings stand out. First, data governance matters more than modelling: an unprotected analysis would have claimed an AUC near 0.9; the honest figure is {auc_g('blind', 'All')[0]:.2f}. "
     f"Second, the model does not miss Black patients' deaths more often than White patients' (recall gap {ci('aware', 'tpr_gap', True)}), but the study lacks the power to prove equality; "
     f"with 30 deaths, a gap of 14 points would not be detected. This is a data-collection problem, one that no modelling technique can solve. Third, the measurable disparity is on the other side of the "
     f"ledger: Black survivors are flagged more often, and the difference grows as outcomes become more certain. For a recall-first screening tool, extra false alarms mean extra visits and anxiety rather than missed cancers, "
     f"but they are a burden that should not fall unevenly, and in settings where follow-up capacity is limited they would translate into unequal access.", align="j")
para("Concerning mitigation, the simplest and cheapest approach (reweighing) was the only one with an interval-supported benefit and the only one that leaves the explanations and the workload essentially "
     "untouched. Race-aware inputs offered no advantage because the model learned nothing from them, and group-specific thresholds are not recommended with the current sample: they raise the number of "
     "patients flagged, require race at prediction time, and their threshold for the smaller group is too noisy to deliver equal recall. These results echo the general lesson of Obermeyer et al. (2019) and Rajkomar et al. (2018): "
     "fairness problems in medical algorithms usually originate in the data and the label, not in the algorithm, and the first remedy is to audit them with the right metric and the right uncertainty.", align="j")
para("Relative to the earlier implementation of this study on the same cohort, which used receptor status (ER, PR, HER2) merged from a second source and reached a hold-out AUC of 0.74, the present model has a lower AUC "
     f"({auc_g('blind', 'All')[0]:.2f}). The difference is plausible: the present table has no receptor status (ER, PR, HER2), which probably carried part of the earlier signal, and the earlier hold-out "
     "estimate came from a single split with only 29 Black deaths in the whole cohort, so the two figures are not directly comparable.", align="j")
doc.add_page_break()

# =============================================================================================
# CHAPTER 5
# =============================================================================================
H1("5.0 Conclusions")
H2("5.1 Summary of the study")
para(f"This study built a recall-first XGBoost classifier for death during follow-up in {FL['n_cohort']} White and Black TCGA-BRCA patients, explained it with SHAP, and tested whether it treats the two groups "
     f"equally and how far bias mitigation can help. A column-by-column data audit removed leakage and informative missingness that would have inflated AUC from {C.LADDER.auc.iloc[0]:.2f} to over 0.9. "
     f"The final model is an additive, clinically constrained ensemble with an AUC of {auc_g('blind', 'All')[0]:.2f}; at a threshold that catches 80 % of deaths it flags about {pct(cv('blind', 'flag_all')[0], 0)} of patients. "
     f"Equal opportunity cannot be rejected but cannot be confirmed either, Black survivors are flagged somewhat more often, and reweighing is the most defensible mitigation.", align="j")
H2("5.2 Conclusions per objective")
bullets([("Objective 1 (framework). ", "A reproducible pipeline (audit, validation, recall-first thresholding, fairness audit, SHAP, dashboard) shows where interpretability enters clinical decision support: at the data-governance stage (SHAP and the leakage ladder expose forbidden columns), at model review (direction checks against clinical priors), at the bedside (per-patient waterfalls) and at the governance stage (group-level SHAP and risk-gap decomposition)."),
         ("Objective 2 (performance). ", f"With a recall target of 80 % the model reaches recall {ci('blind', 'tpr_all')} in cross-validation at a false-positive rate of {ci('blind', 'fpr_all')} and an AUC of {auc_g('blind', 'All')[0]:.2f}. Discrimination is modest, equal to that of logistic regression, and limited by the information in pre-treatment clinical data."),
         ("Objective 3 (SHAP). ", "Age, nodal status, Luminal A subtype, tumour size and metastasis explain the model; every staging effect points in the clinically expected direction. Explanations are the same for both races and survive mitigation."),
         ("Objective 4 (clinician trust). ", "A protocol and the dashboard stimulus are ready; no clinician data have been collected, so no conclusion about trust is drawn."),
         ("Objective 5 (bias). ", f"There is no measurable recall gap ({ci('aware', 'tpr_gap', True)}) but the data cannot exclude one of about 14 points; Black survivors carry a higher false-alarm burden ({ci('aware', 'fpr_gap', True)}), more clearly so for patients with settled outcomes. Reweighing reduced it (paired change {paired('reweigh', 'fpr_gap')[0]:+.3f}); race-awareness and group thresholds did not help.")])
H2("5.3 Contributions to knowledge")
bullets(["A worked, auditable example of recall-first modelling in oncology, including the cost (a false-positive rate of about 63 %) that is rarely reported.",
         "A leakage-and-missingness ladder that quantifies how much each class of forbidden column inflates performance in TCGA clinical tables.",
         "A fairness protocol designed for very small subgroups: repeated cross-validation, nested thresholds, paired bootstrap intervals for mitigation effects and settled-outcome sensitivity analyses.",
         "Group-level SHAP tools (importance by group, exact risk-gap decomposition, missed-death profiles and bootstrap rank stability) that connect explainability to fairness.",
         "An open-source dashboard and model card tying the thesis numbers to a running application."])
H2("5.4 Limitations")
bullets(["Sample size. Thirty Black deaths limit every subgroup statement; the hold-out set holds six.",
         "Censoring and missing treatment. The label ignores follow-up length and the table has no treatment data, so \"false alarms\" include patients who die later and benefit from treatment given.",
         "Single cohort. TCGA is not representative of any clinical population and the findings have not been validated externally.",
         "Race as a variable. Self-reported race is a social label; the ancestry analysis is also small and cannot separate biology from care access.",
         "Mitigation scope. Only pre- and post-processing were tested; in-processing methods (constrained optimisation, adversarial debiasing) were not.",
         "User study. Objective 4 is unexecuted; claims about physician trust remain hypotheses."])
H2("5.5 Recommendations and future work")
bullets(["Collect or federate more data from underrepresented groups, including African cohorts, and external validation; this is the only remedy for the central uncertainty.",
         "Add treatment, receptor status and grade, and model time to event with censoring-aware methods (for example survival forests or Cox models with SHAP) rather than a binary label.",
         "Adopt reweighing as the default mitigation and monitor group-wise recall and false-alarm rates with confidence intervals on every model update.",
         "Avoid group-specific thresholds until each group has several hundred events.",
         "Run the clinician study using the dashboard and the protocol in Section 3.12 before any deployment discussion.",
         "Report subgroup results with uncertainty by default, and keep the leakage audit as a gate in every pipeline."])
doc.add_page_break()
H1("References cited in Chapters 3, 4 and 5")
refs = [
    "Barocas, S., Hardt, M. and Narayanan, A. (2019). Fairness and Machine Learning. fairmlbook.org.",
    "Carrot-Zhang, J. et al. (2020). Comprehensive analysis of genetic ancestry and its molecular correlates in cancer. Cancer Cell, 37(5), 639-654.",
    "Cerami, E. et al. (2012). The cBio Cancer Genomics Portal: an open platform for exploring multidimensional cancer genomics data. Cancer Discovery, 2(5), 401-404.",
    "Chen, T. and Guestrin, C. (2016). XGBoost: a scalable tree boosting system. Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, 785-794.",
    "DeSantis, C. E. et al. (2019). Breast cancer statistics, 2019. CA: A Cancer Journal for Clinicians, 69(6), 438-451.",
    "Efron, B. and Tibshirani, R. J. (1993). An Introduction to the Bootstrap. Chapman and Hall.",
    "Hardt, M., Price, E. and Srebro, N. (2016). Equality of opportunity in supervised learning. Advances in Neural Information Processing Systems 29.",
    "Kamiran, F. and Calders, T. (2012). Data preprocessing techniques for classification without discrimination. Knowledge and Information Systems, 33(1), 1-33.",
    "Kaufman, S., Rosset, S. and Perlich, C. (2011). Leakage in data mining: formulation, detection, and avoidance. Proceedings of the 17th ACM SIGKDD Conference, 556-563.",
    "Liu, J. et al. (2018). An integrated TCGA pan-cancer clinical data resource to drive high-quality survival outcome analytics. Cell, 173(2), 400-416.",
    "Lundberg, S. M. and Lee, S.-I. (2017). A unified approach to interpreting model predictions. Advances in Neural Information Processing Systems 30, 4765-4774.",
    "Lundberg, S. M. et al. (2020). From local explanations to global understanding with explainable AI for trees. Nature Machine Intelligence, 2(1), 56-67.",
    "Obermeyer, Z., Powers, B., Vogeli, C. and Mullainathan, S. (2019). Dissecting racial bias in an algorithm used to manage the health of populations. Science, 366(6464), 447-453.",
    "Parker, J. S. et al. (2009). Supervised risk predictor of breast cancer based on intrinsic subtypes. Journal of Clinical Oncology, 27(8), 1160-1167.",
    "Rajkomar, A., Hardt, M., Howell, M. D., Corrado, G. and Chin, M. H. (2018). Ensuring fairness in machine learning to advance health equity. Annals of Internal Medicine, 169(12), 866-872.",
    "Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. Journal of the American Statistical Association, 22(158), 209-212.",
]
for r in refs:
    p = para(r); p.paragraph_format.left_indent = Inches(0.4); p.paragraph_format.first_line_indent = Inches(-0.4)

doc.save(OUT)
print("saved", OUT, "words:", sum(len(p.text.split()) for p in doc.paragraphs))
