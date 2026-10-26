"""Loading, auditing, cleaning and encoding of the TCGA-BRCA clinical patient table.

Source: ``data/data_clinical_patient.csv`` (cBioPortal, TCGA PanCancer Atlas clinical patient table;
row 1 = display names, row 2 = machine names).  ``data/clinical_data_dictionary.xlsx`` documents every column.

The model follows Section 3.2.2 of the revised proposal (Table 3.2, "Variable selection decisions"):

* target ``died`` = ``OS_STATUS`` is ``1:DECEASED`` (all 1,084 patients, 151 deaths);
* predictors known at or near diagnosis / primary treatment (``PRIMARY``);
* outcome-related columns are excluded as leakage;
* technical codes (TX / NX / MX, "STAGE X") and blanks are set to missing and handled natively by XGBoost.

On top of the proposal the audit adds *sensitivity specifications* (``SPECS``) because two proposal choices
turned out to carry outcome information through their blanks (radiation therapy; NX / MX codes), see
``docs/DATA_AUDIT.md``.  The single source of truth for the model schema lives here so the notebook, the
pipeline and the dashboard cannot disagree.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "data_clinical_patient.csv"

TARGET = "died"
PRIVILEGED, UNPRIVILEGED = "White", "Black"       # reference group first
GROUPS = [PRIVILEGED, UNPRIVILEGED]                # groups of the fairness analysis
OTHER = "Other"                                    # Asian, Native American, race not recorded: trained on, not audited
RACE_MAP = {"White": "White", "Black or African American": "Black", "Asian": "Asian"}

# --------------------------------------------------------------------------------------------
# Column governance (mirrors Table 3.2 of the revised proposal, plus the audit note)
# --------------------------------------------------------------------------------------------
LEAKY = {
    "OS_MONTHS": "follow-up time that defines the outcome",
    "DAYS_LAST_FOLLOWUP": "follow-up time; blank for every patient who died",
    "DSS_STATUS": "disease-specific death: a subset of the outcome", "DSS_MONTHS": "survival time",
    "DFS_STATUS": "recurrence after treatment: known only after follow-up", "DFS_MONTHS": "survival time",
    "PFS_STATUS": "progression: known only after follow-up", "PFS_MONTHS": "survival time",
    "PERSON_NEOPLASM_CANCER_STATUS": "tumour status at last follow-up (outcome proxy)",
    "NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT": "post-treatment event (outcome proxy)",
}
REDUNDANT = {
    "AJCC_PATHOLOGIC_TUMOR_STAGE": "composite of T, N, M (used only in the stage-group sensitivity model)",
    "DAYS_TO_BIRTH": "duplicates age",
    "GENETIC_ANCESTRY_LABEL": "overlaps race (used only in the ancestry sensitivity analysis)",
    "ETHNICITY": "169 missing; blanks track the outcome (6 % deaths when blank vs 15 % when recorded)",
    "PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT": "36 % missing, post-operative; not in the proposal's predictor list",
}
UNINFORMATIVE = {
    "PATIENT_ID": "identifier", "OTHER_PATIENT_ID": "identifier", "CANCER_TYPE_ACRONYM": "constant (BRCA)",
    "ICD_10": "constant (C50.9)", "ICD_O_3_SITE": "constant", "INFORMED_CONSENT_VERIFIED": "constant",
    "FORM_COMPLETION_DATE": "administrative date", "AJCC_STAGING_EDITION": "administrative; missingness differs by race",
    "IN_PANCANPATHWAYS_FREEZE": "administrative (equals SUBTYPE missingness)", "WEIGHT": "100 % missing",
    "SEX": "98.9 % female (12 male patients)",
}
INCLUDED = {
    "AGE": ("age", ""), "SUBTYPE": ("sub_*", "103 missing; native missing"),
    "PATH_T_STAGE": ("t_stage", "TX -> missing"), "PATH_N_STAGE": ("n_stage", "NX -> missing; NX has a 61 % death rate (audit)"),
    "PATH_M_STAGE": ("m_stage", "MX -> missing"), "ICD_O_3_HISTOLOGY": ("histology_*", "ductal / lobular / other"),
    "RACE": ("race_black, race_asian", "also the fairness group; 90 not recorded"),
    "RADIATION_THERAPY": ("radiation", "101 blanks; death rate 42 % when blank vs 11 % recorded -> informative missingness (audit)"),
    "HISTORY_NEOADJUVANT_TRTYN": ("neoadjuvant", "only 6 'Yes'"), "PRIOR_DX": ("prior_dx", ""),
}

# --------------------------------------------------------------------------------------------
# Model schema
# --------------------------------------------------------------------------------------------
FEATURE_INFO = {
    "age": ("Age at diagnosis", "Age (years) at initial pathologic diagnosis"),
    "t_stage": ("Tumour size (T)", "AJCC pathologic T category, 1-4 (TX = missing)"),
    "n_stage": ("Nodal status (N)", "AJCC pathologic N category, 0-3 (NX = missing)"),
    "m_stage": ("Distant metastasis (M)", "1 = M1, 0 = M0 (MX = missing)"),
    "n_stage_h": ("Nodal status (N, NX=N0)", "N category with NX set to N0 (AJCC default)"),
    "m_stage_h": ("Distant metastasis (M, MX=M0)", "M category with MX set to M0 (AJCC default)"),
    "stage_group": ("AJCC stage group", "Stage I-IV (X = missing)"),
    "sub_luma": ("PAM50: Luminal A", "1 = Luminal A"), "sub_lumb": ("PAM50: Luminal B", "1 = Luminal B"),
    "sub_her2": ("PAM50: HER2-enriched", "1 = HER2-enriched"), "sub_basal": ("PAM50: Basal-like", "1 = Basal-like"),
    "sub_normal": ("PAM50: Normal-like", "1 = Normal-like"),
    "histology_lobular": ("Histology: lobular", "1 = infiltrating lobular (reference: ductal)"),
    "histology_other": ("Histology: other", "1 = other histology"),
    "prior_dx": ("Prior diagnosis", "1 = prior malignancy"),
    "neoadjuvant": ("Neoadjuvant therapy", "1 = neoadjuvant therapy before resection"),
    "radiation": ("Radiation therapy", "1 = yes, 0 = no, blank = not recorded"),
    "race_black": ("Race: Black", "1 = Black or African American (reference: White)"),
    "race_asian": ("Race: Asian", "1 = Asian (reference: White)"),
}
LABELS = {k: v[0] for k, v in FEATURE_INFO.items()}
SUBS = ["sub_luma", "sub_lumb", "sub_her2", "sub_basal", "sub_normal"]
RACE_FEATURES = ["race_black", "race_asian"]

# the proposal's predictor list (Table 3.2, "Included")
PRIMARY = ["age", "t_stage", "n_stage", "m_stage"] + SUBS + ["histology_lobular", "histology_other", "prior_dx",
                                                              "neoadjuvant", "radiation"] + RACE_FEATURES
PRIMARY_BLIND = [f for f in PRIMARY if f not in RACE_FEATURES]
SPECS = {
    "proposal": PRIMARY,                                                         # primary model (as specified)
    "stage_group": ["age", "stage_group"] + SUBS + ["histology_lobular", "histology_other", "prior_dx",
                                                    "neoadjuvant", "radiation"] + RACE_FEATURES,   # proposal 3.2.2 sensitivity
    "hardened": ["age", "t_stage", "n_stage_h", "m_stage_h"] + SUBS + ["histology_lobular", "histology_other",
                                                                        "prior_dx"] + RACE_FEATURES,  # audit sensitivity
}
ALL_FEATURES = list(FEATURE_INFO)
MONOTONE_COLS = ["t_stage", "n_stage", "m_stage", "n_stage_h", "m_stage_h", "stage_group"]

# direction a clinician expects (+1 = higher value raises mortality risk)
CLINICAL_PRIOR = {"age": +1, "t_stage": +1, "n_stage": +1, "m_stage": +1, "n_stage_h": +1, "m_stage_h": +1, "stage_group": +1}
ESTABLISHED_FACTORS = {  # proposal 3.2.6 "clinical alignment"
    "age": "Age at diagnosis", "n_stage": "Nodal status", "n_stage_h": "Nodal status", "t_stage": "Tumour size", "m_stage": "Metastasis",
    "m_stage_h": "Metastasis", "stage_group": "Stage group",
    "sub_luma": "Molecular subtype", "sub_lumb": "Molecular subtype", "sub_her2": "Molecular subtype",
    "sub_basal": "Molecular subtype", "sub_normal": "Molecular subtype"}
SUBTYPE_COLS = {"LumA": "sub_luma", "LumB": "sub_lumb", "Her2": "sub_her2", "Basal": "sub_basal", "Normal": "sub_normal"}


# --------------------------------------------------------------------------------------------
# Loading and cleaning
# --------------------------------------------------------------------------------------------
def load_raw(path: Path | str = DATA_PATH) -> pd.DataFrame:
    raw = pd.read_csv(path, header=1, dtype=str, keep_default_na=False, na_values=[""])
    for c in raw.columns:
        raw[c] = raw[c].str.strip().replace({"": np.nan})
    for c in ["AGE", "OS_MONTHS", "DAYS_LAST_FOLLOWUP", "DSS_MONTHS", "DFS_MONTHS", "PFS_MONTHS", "WEIGHT"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw[TARGET] = raw["OS_STATUS"].str.startswith("1").astype(int)
    return raw


def _ordinal(s: pd.Series, prefix: str) -> pd.Series:
    """'N1A' -> 1, 'T4B' -> 4, 'N0 (I+)' -> 0, 'cM0' -> 0, 'NX' -> NaN."""
    return s.str.extract(rf"^c?{prefix}(\d)")[0].astype(float)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """All patients with tidy columns.  ``race`` is the fairness group (White / Black / Other)."""
    df = raw
    c = pd.DataFrame(index=df.index)
    c["patient_id"] = df["PATIENT_ID"]
    detail = df["RACE"].map(RACE_MAP).fillna("Unknown")
    c["race_detail"] = detail
    c["race"] = np.where(detail.isin(GROUPS), detail, OTHER)
    c[TARGET] = df[TARGET]
    c["followup_months"] = df["OS_MONTHS"]
    c["age"] = df["AGE"]
    c["t_stage"] = _ordinal(df["PATH_T_STAGE"], "T")
    c["n_stage"] = _ordinal(df["PATH_N_STAGE"], "N")
    c["m_stage"] = _ordinal(df["PATH_M_STAGE"], "M")
    stage = df["AJCC_PATHOLOGIC_TUMOR_STAGE"].str.extract(r"STAGE (I{1,3}|IV)")[0]
    c["stage_group"] = stage.map({"I": 1.0, "II": 2.0, "III": 3.0, "IV": 4.0})
    c["subtype"] = df["SUBTYPE"].str.replace("BRCA_", "", regex=False)
    hist = df["ICD_O_3_HISTOLOGY"]
    c["histology"] = np.select([hist == "8500/3", hist == "8520/3"], ["Ductal", "Lobular"], default="Other")
    c["prior_dx"] = df["PRIOR_DX"].map({"Yes": 1.0, "No": 0.0})
    c["neoadjuvant"] = df["HISTORY_NEOADJUVANT_TRTYN"].map({"Yes": 1.0, "No": 0.0})
    c["radiation"] = df["RADIATION_THERAPY"].map({"Yes": 1.0, "No": 0.0})
    c["ancestry"] = df["GENETIC_ANCESTRY_LABEL"].fillna("not called")
    c["sex"] = df["SEX"]
    for k in ["PATH_N_STAGE", "PATH_M_STAGE", "PATH_T_STAGE", "ETHNICITY", "PERSON_NEOPLASM_CANCER_STATUS",
              "NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT", "PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT",
              "DAYS_LAST_FOLLOWUP"]:
        c["raw_" + k.lower()] = df[k]
    return c.reset_index(drop=True)


def encode(c: pd.DataFrame) -> pd.DataFrame:
    """Clean table -> superset model matrix (every column of ``ALL_FEATURES``); each specification picks its columns."""
    X = pd.DataFrame(index=c.index)
    X["age"] = c["age"].astype(float)
    for k in ["t_stage", "n_stage", "m_stage", "stage_group"]:
        X[k] = c[k].astype(float)
    X["n_stage_h"] = X["n_stage"].fillna(0.0)
    X["m_stage_h"] = X["m_stage"].fillna(0.0)
    known = c["subtype"].notna()
    for name, col in SUBTYPE_COLS.items():
        X[col] = np.where(known, (c["subtype"] == name).astype(float), np.nan)
    X["histology_lobular"] = (c["histology"] == "Lobular").astype(float)
    X["histology_other"] = (c["histology"] == "Other").astype(float)
    for k in ["prior_dx", "neoadjuvant", "radiation"]:
        X[k] = c[k].astype(float)
    unk = c["race_detail"] == "Unknown"
    X["race_black"] = np.where(unk, np.nan, (c["race_detail"] == "Black").astype(float))
    X["race_asian"] = np.where(unk, np.nan, (c["race_detail"] == "Asian").astype(float))
    return X[ALL_FEATURES]


def strata(c: pd.DataFrame) -> pd.Series:
    """race group x outcome strata so every split keeps Black patients and deaths among them."""
    return c["race"].astype(str) + "_" + c[TARGET].astype(int).astype(str)


def split_labels(c: pd.DataFrame, seed: int = 42, test: float = 0.2) -> pd.Series:
    """Stratified 80 / 20 development / hold-out assignment (proposal 3.2.4)."""
    from sklearn.model_selection import train_test_split
    idx = np.arange(len(c))
    _, te = train_test_split(idx, test_size=test, stratify=strata(c), random_state=seed)
    s = pd.Series("dev", index=c.index)
    s.iloc[te] = "test"
    return s


# --------------------------------------------------------------------------------------------
# Audit tables
# --------------------------------------------------------------------------------------------
def column_governance() -> pd.DataFrame:
    rows = []
    for k, (feat, note) in INCLUDED.items():
        rows.append({"column": k, "decision": "Included (predictor)", "reason": f"-> {feat}", "audit_note": note})
    for d, label in [(LEAKY, "Excluded: outcome-related (leakage)"), (REDUNDANT, "Excluded: redundant or sparse"),
                     (UNINFORMATIVE, "Excluded: uninformative or constant")]:
        rows += [{"column": k, "decision": label, "reason": v, "audit_note": ""} for k, v in d.items()]
    rows.append({"column": "OS_STATUS", "decision": "Target", "reason": "1:DECEASED -> died = 1", "audit_note": ""})
    return pd.DataFrame(rows)


def missingness_audit(raw: pd.DataFrame) -> pd.DataFrame:
    """Death rate when a column / code is missing vs recorded (all 1,084 patients)."""
    rows = []
    def add(name, m):
        rows.append({"column": name, "n_missing": int(m.sum()), "pct_missing": 100 * m.mean(),
                     "death_rate_missing": raw.loc[m, TARGET].mean(), "death_rate_recorded": raw.loc[~m, TARGET].mean()})
    for col in ["SUBTYPE", "RADIATION_THERAPY", "ETHNICITY", "PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT", "RACE",
                "PERSON_NEOPLASM_CANCER_STATUS", "NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT", "AJCC_STAGING_EDITION",
                "DAYS_LAST_FOLLOWUP"]:
        add(col, raw[col].isna())
    for col, code in [("PATH_N_STAGE", "NX"), ("PATH_M_STAGE", "MX"), ("PATH_T_STAGE", "TX")]:
        add(f"{col} = {code}", raw[col] == code)
    return pd.DataFrame(rows)


def table1(c: pd.DataFrame) -> pd.DataFrame:
    """Cohort characteristics: all patients, White, Black, and Asian / race not recorded."""
    cols = {"All": c, "White": c[c.race == "White"], "Black": c[c.race == "Black"], "Other": c[c.race == OTHER]}
    rows = []
    def add(name, fn):
        rows.append({"characteristic": name, **{k: fn(v) for k, v in cols.items()}})
    cnt = lambda m: (lambda d: f"{int(m(d).sum())} ({100 * m(d).mean():.0f}%)")
    add("Patients, n", lambda d: f"{len(d)}")
    add("Deaths during follow-up, n (%)", lambda d: f"{d[TARGET].sum()} ({100 * d[TARGET].mean():.1f}%)")
    iqr = lambda col: (lambda d: f"{d[col].median():.0f} ({d[col].quantile(.25):.0f}-{d[col].quantile(.75):.0f})")
    add("Age, median (IQR)", iqr("age")); add("Follow-up months, median (IQR)", iqr("followup_months"))
    for lvl in [1, 2, 3, 4]:
        add(f"T{lvl}", cnt(lambda d, l=lvl: d.t_stage == l))
    add("T unknown (TX)", cnt(lambda d: d.t_stage.isna()))
    for lvl in [0, 1, 2, 3]:
        add(f"N{lvl}", cnt(lambda d, l=lvl: d.n_stage == l))
    add("N unknown (NX)", cnt(lambda d: d.n_stage.isna()))
    add("M1", cnt(lambda d: d.m_stage == 1)); add("M unknown (MX)", cnt(lambda d: d.m_stage.isna()))
    for s in ["LumA", "LumB", "Her2", "Basal", "Normal"]:
        add(f"PAM50 {s}", cnt(lambda d, s=s: d.subtype == s))
    add("PAM50 not called", cnt(lambda d: d.subtype.isna()))
    for h in ["Ductal", "Lobular", "Other"]:
        add(f"Histology {h}", cnt(lambda d, h=h: d.histology == h))
    add("Radiation therapy: yes", cnt(lambda d: d.radiation == 1)); add("Radiation therapy: not recorded", cnt(lambda d: d.radiation.isna()))
    return pd.DataFrame(rows)
