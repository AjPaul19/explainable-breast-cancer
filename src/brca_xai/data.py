"""Loading, auditing, cleaning and encoding of the TCGA-BRCA clinical patient table.

Source: ``data/data_clinical_patient.csv`` (cBioPortal, TCGA PanCancer Atlas 2018 clinical patient
table; header row 1 = display names, row 2 = machine names).  ``data/clinical_data_dictionary.xlsx``
documents every column.

Design rules (see docs/DATA_AUDIT.md for the evidence):

* The label is ``died`` = ``OS_STATUS`` is ``1:DECEASED`` (death during follow-up).
* Only information known at (or shortly after) diagnosis is used as input.  Columns that record what
  happened *after* diagnosis, or that are the outcome in another costume, are excluded (``LEAKY``).
* Columns whose *missingness* tracks the outcome (a registry artefact, not biology) are excluded
  (``INFORMATIVE_MISSING``) or neutralised with the clinical default (MX -> M0, NX -> N0).
* The single source of truth for the model schema is ``FEATURE_INFO`` / ``encode`` so that the
  notebook that trains the model and the dashboard that serves it cannot disagree.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "data_clinical_patient.csv"

TARGET = "died"
GROUP_COL = "race"
PRIVILEGED, UNPRIVILEGED = "White", "Black"   # reference group first
GROUPS = [PRIVILEGED, UNPRIVILEGED]
RACE_MAP = {"White": "White", "Black or African American": "Black"}

# --------------------------------------------------------------------------------------------
# Column governance
# --------------------------------------------------------------------------------------------
# Columns that must never be model inputs, with the reason (used verbatim in the audit table).
LEAKY = {
    "OS_MONTHS": "the follow-up time that defines the outcome",
    "DAYS_LAST_FOLLOWUP": "follow-up time; blank for 100 % of deaths in the cohort (another label)",
    "DSS_STATUS": "disease-specific death: a subset of the outcome",
    "DSS_MONTHS": "survival time",
    "DFS_STATUS": "recurrence after treatment: only known after follow-up",
    "DFS_MONTHS": "survival time",
    "PFS_STATUS": "progression: only known after follow-up",
    "PFS_MONTHS": "survival time",
    "PERSON_NEOPLASM_CANCER_STATUS": "tumour status at last follow-up (post-baseline, outcome proxy)",
    "NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT": "post-treatment event (post-baseline, outcome proxy)",
    "DAYS_TO_INITIAL_PATHOLOGIC_DIAGNOSIS": "constant 0 reference day",
    "FORM_COMPLETION_DATE": "administrative date",
}
# Usable in principle but their *missingness* encodes the outcome / registry practice.
INFORMATIVE_MISSING = {
    "RADIATION_THERAPY": "missing for 56 % deaths vs 12 % otherwise: a documentation artefact",
    "ETHNICITY": "missing for 4 % deaths vs 16 % otherwise: reporting practice, not biology",
    "PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT": "36 % missing and largely post-operative",
    "AJCC_STAGING_EDITION": "an administrative variable whose missingness differs by race (126 of 751 White vs 8 of 182 Black)",
}
# Carry no signal (constant, unique, empty or redundant with a kept column).
NO_SIGNAL = {
    "PATIENT_ID": "identifier", "OTHER_PATIENT_ID": "identifier", "CANCER_TYPE_ACRONYM": "constant (BRCA)",
    "ICD_10": "constant (C50.9)", "ICD_O_3_SITE": "constant", "INFORMED_CONSENT_VERIFIED": "constant",
    "WEIGHT": "100 % missing", "IN_PANCANPATHWAYS_FREEZE": "administrative (equals SUBTYPE missingness)",
    "DAYS_TO_BIRTH": "redundant with AGE", "SEX": "12 male patients: too few to model",
    "HISTORY_NEOADJUVANT_TRTYN": "only 6 'Yes'", "AJCC_PATHOLOGIC_TUMOR_STAGE": "redundant with T, N, M",
    "GENETIC_ANCESTRY_LABEL": "used only for the sensitivity analysis, never as an input",
}

# --------------------------------------------------------------------------------------------
# Model schema
# --------------------------------------------------------------------------------------------
FEATURE_INFO = {
    "age": ("Age at diagnosis", "Age (years) at initial pathologic diagnosis"),
    "t_stage": ("Tumour size (T)", "AJCC pathologic T category, 1-4 (TX = unknown)"),
    "n_stage": ("Nodal status (N)", "AJCC pathologic N category, 0-3 (NX / not assessed is treated as N0)"),
    "m_stage": ("Distant metastasis (M1)", "1 = AJCC pathologic M1 (MX / not assessed is treated as M0, the AJCC default)"),
    "sub_luma": ("PAM50: Luminal A", "1 = Luminal A (reference group of the PAM50 set)"),
    "sub_lumb": ("PAM50: Luminal B", "1 = Luminal B"),
    "sub_her2": ("PAM50: HER2-enriched", "1 = HER2-enriched"),
    "sub_basal": ("PAM50: Basal-like", "1 = Basal-like (triple-negative like)"),
    "sub_normal": ("PAM50: Normal-like", "1 = Normal-like"),
    "histology_lobular": ("Histology: lobular", "1 = infiltrating lobular carcinoma (reference: ductal)"),
    "histology_other": ("Histology: other", "1 = mucinous / medullary / metaplastic / mixed / other"),
    "prior_dx": ("Prior diagnosis", "1 = patient had a prior malignancy"),
    "race_black": ("Race: Black", "1 = Black or African American (reference: White)"),
}
RACE_FEATURES = ["race_black"]
FEATURES_BLIND = [f for f in FEATURE_INFO if f not in RACE_FEATURES]
FEATURES_AWARE = FEATURES_BLIND + RACE_FEATURES
LABELS = {k: v[0] for k, v in FEATURE_INFO.items()}

# Direction a clinician expects (+1 = higher value raises mortality risk).
CLINICAL_PRIOR = {"age": +1, "t_stage": +1, "n_stage": +1, "m_stage": +1}

SUBTYPE_COLS = {"BRCA_LumA": "sub_luma", "BRCA_LumB": "sub_lumb", "BRCA_Her2": "sub_her2",
                "BRCA_Basal": "sub_basal", "BRCA_Normal": "sub_normal"}


# --------------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------------
def load_raw(path: Path | str = DATA_PATH) -> pd.DataFrame:
    """Read the CSV (row 0 = display names, row 1 = machine names, data from row 2)."""
    raw = pd.read_csv(path, header=1, dtype=str, keep_default_na=False, na_values=[""])
    for c in raw.columns:
        raw[c] = raw[c].str.strip().replace({"": np.nan})
    for c in ["AGE", "OS_MONTHS", "DAYS_LAST_FOLLOWUP", "DSS_MONTHS", "DFS_MONTHS", "PFS_MONTHS", "WEIGHT"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw[TARGET] = raw["OS_STATUS"].str.startswith("1").astype(int)
    return raw


def _ordinal(s: pd.Series, prefix: str) -> pd.Series:
    """'N1A' -> 1, 'T4B' -> 4, 'N0 (I+)' -> 0, 'NX' -> NaN."""
    return s.str.extract(rf"^c?{prefix}(\d)")[0].astype(float)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Study cohort (self-reported White or Black) with tidy, human-readable columns."""
    df = raw.copy()
    df["race"] = df["RACE"].map(RACE_MAP)
    df = df[df["race"].notna()].copy()
    c = pd.DataFrame(index=df.index)
    c["patient_id"] = df["PATIENT_ID"]
    c["race"] = df["race"]
    c[TARGET] = df[TARGET]
    c["followup_months"] = df["OS_MONTHS"]
    c["age"] = df["AGE"]
    c["t_stage"] = _ordinal(df["PATH_T_STAGE"], "T")
    c["n_stage"] = _ordinal(df["PATH_N_STAGE"], "N")
    c["m_stage"] = np.where(df["PATH_M_STAGE"].str.startswith("M1"), 1.0,
                            np.where(df["PATH_M_STAGE"].isin(["M0", "CM0 (I+)", "MX"]), 0.0, np.nan))
    c["subtype"] = df["SUBTYPE"].str.replace("BRCA_", "", regex=False)
    hist = df["ICD_O_3_HISTOLOGY"]
    c["histology"] = np.select([hist == "8500/3", hist == "8520/3"], ["Ductal", "Lobular"], default="Other")
    c["prior_dx"] = df["PRIOR_DX"].map({"Yes": 1.0, "No": 0.0})
    c["ancestry"] = df["GENETIC_ANCESTRY_LABEL"].replace({"": np.nan}).fillna("not called")
    c["sex"] = df["SEX"]
    # kept only for the audit and the sensitivity analyses - never model inputs
    for k in ["PATH_N_STAGE", "PATH_M_STAGE", "PATH_T_STAGE", "RADIATION_THERAPY", "ETHNICITY",
              "PERSON_NEOPLASM_CANCER_STATUS", "NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT",
              "PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT", "DAYS_LAST_FOLLOWUP"]:
        c["raw_" + k.lower()] = df[k]
    return c.reset_index(drop=True)


def encode(c: pd.DataFrame) -> pd.DataFrame:
    """Clean table -> model matrix with every column in ``FEATURES_AWARE`` (blind models drop race)."""
    X = pd.DataFrame(index=c.index)
    X["age"] = c["age"].astype(float)
    X["t_stage"] = c["t_stage"].astype(float)                 # TX stays NaN (3 patients)
    X["n_stage"] = c["n_stage"].astype(float).fillna(0.0)     # NX -> N0 (audit: NX carries a documentation artefact)
    X["m_stage"] = c["m_stage"].astype(float).fillna(0.0)     # MX -> M0
    known = c["subtype"].notna()
    for name, col in SUBTYPE_COLS.items():
        X[col] = np.where(known, (c["subtype"] == name.replace("BRCA_", "")).astype(float), np.nan)
    X["histology_lobular"] = (c["histology"] == "Lobular").astype(float)
    X["histology_other"] = (c["histology"] == "Other").astype(float)
    X["prior_dx"] = c["prior_dx"].astype(float)
    X["race_black"] = (c["race"] == "Black").astype(float)
    return X[FEATURES_AWARE]


def strata(c: pd.DataFrame) -> pd.Series:
    """race x outcome strata: every split keeps Black patients *and* deaths among them."""
    return c["race"].astype(str) + "_" + c[TARGET].astype(int).astype(str)


def split_labels(c: pd.DataFrame, seed: int = 42, test: float = 0.2) -> pd.Series:
    """Stratified development ('dev') / hold-out ('test') assignment."""
    from sklearn.model_selection import train_test_split
    idx = np.arange(len(c))
    _, te = train_test_split(idx, test_size=test, stratify=strata(c), random_state=seed)
    s = pd.Series("dev", index=c.index)
    s.iloc[te] = "test"
    return s


# --------------------------------------------------------------------------------------------
# Audit tables (used by the notebook, the dashboard and the thesis)
# --------------------------------------------------------------------------------------------
def column_governance() -> pd.DataFrame:
    rows = []
    for d, label in [(LEAKY, "Excluded: outcome leakage / post-baseline"),
                     (INFORMATIVE_MISSING, "Excluded: informative missingness"),
                     (NO_SIGNAL, "Excluded: no signal / redundant")]:
        rows += [{"column": k, "decision": label, "reason": v} for k, v in d.items()]
    kept = {"AGE": "age", "PATH_T_STAGE": "t_stage", "PATH_N_STAGE": "n_stage", "PATH_M_STAGE": "m_stage",
            "SUBTYPE": "sub_*", "ICD_O_3_HISTOLOGY": "histology_*", "PRIOR_DX": "prior_dx",
            "RACE": "race_black (aware model only) and the fairness group"}
    rows += [{"column": k, "decision": "Kept as model input", "reason": f"-> {v}"} for k, v in kept.items()]
    rows.append({"column": "OS_STATUS", "decision": "Target", "reason": "1:DECEASED -> died = 1"})
    return pd.DataFrame(rows)


def missingness_audit(raw: pd.DataFrame) -> pd.DataFrame:
    """Death rate when a column is recorded vs missing, within the White + Black cohort."""
    b = raw[raw["RACE"].isin(RACE_MAP)]
    rows = []
    for col in ["SUBTYPE", "RADIATION_THERAPY", "ETHNICITY", "PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT",
                "PERSON_NEOPLASM_CANCER_STATUS", "NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT",
                "AJCC_STAGING_EDITION", "DAYS_LAST_FOLLOWUP"]:
        m = b[col].isna()
        rows.append({"column": col, "n_missing": int(m.sum()), "pct_missing": 100 * m.mean(),
                     "death_rate_missing": b.loc[m, TARGET].mean(), "death_rate_recorded": b.loc[~m, TARGET].mean()})
    nx = b["PATH_N_STAGE"] == "NX"
    mx = b["PATH_M_STAGE"] == "MX"
    rows.append({"column": "PATH_N_STAGE = NX", "n_missing": int(nx.sum()), "pct_missing": 100 * nx.mean(),
                 "death_rate_missing": b.loc[nx, TARGET].mean(), "death_rate_recorded": b.loc[~nx, TARGET].mean()})
    rows.append({"column": "PATH_M_STAGE = MX", "n_missing": int(mx.sum()), "pct_missing": 100 * mx.mean(),
                 "death_rate_missing": b.loc[mx, TARGET].mean(), "death_rate_recorded": b.loc[~mx, TARGET].mean()})
    return pd.DataFrame(rows)


def table1(c: pd.DataFrame) -> pd.DataFrame:
    """Cohort characteristics by race (counts and percentages)."""
    rows = []
    def add(name, w, b):
        rows.append({"characteristic": name, "White": w, "Black": b})
    W, B = c[c.race == "White"], c[c.race == "Black"]
    add("Patients, n", f"{len(W)}", f"{len(B)}")
    add("Deaths during follow-up, n (%)", f"{W[TARGET].sum()} ({100*W[TARGET].mean():.1f}%)", f"{B[TARGET].sum()} ({100*B[TARGET].mean():.1f}%)")
    add("Age, median (IQR)", f"{W.age.median():.0f} ({W.age.quantile(.25):.0f}-{W.age.quantile(.75):.0f})", f"{B.age.median():.0f} ({B.age.quantile(.25):.0f}-{B.age.quantile(.75):.0f})")
    add("Follow-up months, median (IQR)", f"{W.followup_months.median():.0f} ({W.followup_months.quantile(.25):.0f}-{W.followup_months.quantile(.75):.0f})", f"{B.followup_months.median():.0f} ({B.followup_months.quantile(.25):.0f}-{B.followup_months.quantile(.75):.0f})")
    for lvl in [1, 2, 3, 4]:
        add(f"T{lvl}", f"{(W.t_stage==lvl).sum()} ({100*(W.t_stage==lvl).mean():.0f}%)", f"{(B.t_stage==lvl).sum()} ({100*(B.t_stage==lvl).mean():.0f}%)")
    for lvl in [0, 1, 2, 3]:
        add(f"N{lvl}", f"{(W.n_stage==lvl).sum()} ({100*(W.n_stage==lvl).mean():.0f}%)", f"{(B.n_stage==lvl).sum()} ({100*(B.n_stage==lvl).mean():.0f}%)")
    add("M1", f"{int((W.m_stage==1).sum())} ({100*(W.m_stage==1).mean():.1f}%)", f"{int((B.m_stage==1).sum())} ({100*(B.m_stage==1).mean():.1f}%)")
    for s in ["LumA", "LumB", "Her2", "Basal", "Normal"]:
        add(f"PAM50 {s}", f"{(W.subtype==s).sum()} ({100*(W.subtype==s).mean():.0f}%)", f"{(B.subtype==s).sum()} ({100*(B.subtype==s).mean():.0f}%)")
    add("PAM50 not called", f"{W.subtype.isna().sum()} ({100*W.subtype.isna().mean():.0f}%)", f"{B.subtype.isna().sum()} ({100*B.subtype.isna().mean():.0f}%)")
    for h in ["Ductal", "Lobular", "Other"]:
        add(f"Histology {h}", f"{(W.histology==h).sum()} ({100*(W.histology==h).mean():.0f}%)", f"{(B.histology==h).sum()} ({100*(B.histology==h).mean():.0f}%)")
    return pd.DataFrame(rows)
