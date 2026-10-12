"""Data acquisition, cleaning and feature encoding for the TCGA-BRCA study.

Sources (both public, de-identified TCGA data):
  * UCSC Xena  - TCGA-BRCA clinical matrix (receptor status, histology, menopause ...)
  * cBioPortal - TCGA PanCancer Atlas 2018 patient table (RACE, AGE, TNM, overall survival)

The two tables are joined on the TCGA patient barcode.

The single source of truth for the model schema lives here (``FEATURES`` / ``encode``), so the
notebook that trains the model and the dashboard that serves it can never disagree about how a
patient is turned into a feature vector.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"

XENA_URL = ("https://tcga-xena-hub.s3.us-east-1.amazonaws.com/download/"
            "TCGA.BRCA.sampleMap%2FBRCA_clinicalMatrix")
CBIO_BASE = ("https://media.githubusercontent.com/media/cBioPortal/datahub/master/public/"
             "brca_tcga_pan_can_atlas_2018/")
SOURCES = {
    "xena_clinical.tsv": XENA_URL,
    "cbio_patient.tsv": CBIO_BASE + "data_clinical_patient.txt",
}

RACE_LEVELS = ["White", "Black or African American", "Asian"]
RACE_SHORT = {"White": "White", "Black or African American": "Black", "Asian": "Asian"}

# --------------------------------------------------------------------------------------------
# Model schema
# --------------------------------------------------------------------------------------------
# column name -> (display label, description)
FEATURE_INFO = {
    "age": ("Age at diagnosis", "Age (years) at initial pathologic diagnosis"),
    "race_black": ("Race: Black", "1 = Black or African American (reference: White)"),
    "race_asian": ("Race: Asian", "1 = Asian (reference: White)"),
    "t_stage": ("Tumour size (T)", "AJCC pathologic T category, 1-4"),
    "n_stage": ("Nodal status (N)", "AJCC pathologic N category, 0-3 (NX / not assessed is treated as N0)"),
    "m_stage": ("Distant metastasis (M1)", "1 = AJCC pathologic M1 (MX / not assessed is treated as M0, the AJCC default)"),
    "er_pos": ("ER positive", "Estrogen-receptor status by IHC"),
    "pr_pos": ("PR positive", "Progesterone-receptor status by IHC"),
    "her2_pos": ("HER2 positive", "HER2 positive by IHC / FISH (not recorded or equivocal is treated as not positive)"),
    "histology_lobular": ("Histology: lobular", "1 = infiltrating lobular carcinoma (reference: ductal)"),
    "histology_other": ("Histology: other", "1 = mucinous / medullary / metaplastic / mixed / other"),
}
FEATURES = list(FEATURE_INFO)

# Used ONLY for the missing-data audit in the notebook: the "naive" encoding keeps NaN as a signal
# and includes menopausal status. It is NOT what the final model uses (see notebook section 1.2).
NAIVE_EXTRA = {"menopause": ("Menopausal status", "0 = pre, 1 = peri, 2 = post (missing is informative - audit only)")}
LABELS = {k: v[0] for k, v in {**FEATURE_INFO, **NAIVE_EXTRA}.items()}
FEATURES_NAIVE = FEATURES + ["menopause"]

# The same model without the two race columns - used to test what race adds.
RACE_FEATURES = ["race_black", "race_asian"]
FEATURES_NO_RACE = [f for f in FEATURES if f not in RACE_FEATURES]

# Direction clinicians would expect: +1 = higher value should raise mortality risk, -1 = lower.
# Used in the notebook to check that SHAP agrees with established medical knowledge.
CLINICAL_PRIOR = {
    "age": +1, "t_stage": +1, "n_stage": +1, "m_stage": +1,
    "er_pos": -1, "pr_pos": -1,
}

TARGET = "died"          # 1 = deceased during follow-up (TCGA overall survival event)


# --------------------------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------------------------
def download_raw(force: bool = False) -> dict[str, Path]:
    """Fetch the two public source tables into ``data/raw`` (cached)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, url in SOURCES.items():
        path = RAW_DIR / name
        if force or not path.exists() or path.stat().st_size < 10_000:
            print(f"downloading {name} ...")
            req = urllib.request.Request(url, headers={"User-Agent": "brca-xai-research"})
            with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
                f.write(r.read())
        paths[name] = path
    return paths


# --------------------------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------------------------
def _pos_neg(s: pd.Series) -> pd.Series:
    """'Positive'/'Negative' -> 1.0/0.0 ; anything else (equivocal, indeterminate, NA) -> NaN."""
    return s.map({"Positive": 1.0, "Negative": 0.0})


def _ordinal_from_code(s: pd.Series, pattern: str) -> pd.Series:
    return s.astype("string").str.upper().str.extract(pattern)[0].astype(float)


def load_clean() -> pd.DataFrame:
    """Return one row per female primary-tumour patient with human-readable clinical columns.

    Missingness is preserved (NaN) rather than imputed: XGBoost and SHAP both handle missing
    values natively, and 'not recorded' is itself clinically meaningful.
    """
    paths = download_raw()
    cbio = pd.read_csv(paths["cbio_patient.tsv"], sep="\t", comment="#")
    xena = pd.read_csv(paths["xena_clinical.tsv"], sep="\t", low_memory=False)

    xena = xena[xena["sample_type"] == "Primary Tumor"].copy()
    xena["PATIENT_ID"] = xena["_PATIENT"]
    xena = xena.drop_duplicates("PATIENT_ID")
    keep = ["PATIENT_ID", "breast_carcinoma_estrogen_receptor_status",
            "breast_carcinoma_progesterone_receptor_status",
            "lab_proc_her2_neu_immunohistochemistry_receptor_status",
            "lab_procedure_her2_neu_in_situ_hybrid_outcome_type",
            "histological_type", "menopause_status"]
    df = cbio.merge(xena[keep], on="PATIENT_ID", how="inner")

    out = pd.DataFrame({"patient_id": df["PATIENT_ID"]})
    out["race_full"] = df["RACE"]
    out["race"] = df["RACE"].map(RACE_SHORT)
    out["age"] = df["AGE"].astype(float)
    out["t_stage"] = _ordinal_from_code(df["PATH_T_STAGE"], r"^T(\d)")
    out["n_stage"] = _ordinal_from_code(df["PATH_N_STAGE"], r"^N(\d)")
    m = df["PATH_M_STAGE"].astype("string").str.upper()
    out["m_stage"] = np.where(m.str.startswith("M1"), 1.0, np.where(m.str.contains("M0"), 0.0, np.nan))
    out["er_pos"] = _pos_neg(df["breast_carcinoma_estrogen_receptor_status"])
    out["pr_pos"] = _pos_neg(df["breast_carcinoma_progesterone_receptor_status"])
    her2 = _pos_neg(df["lab_proc_her2_neu_immunohistochemistry_receptor_status"])
    fish = _pos_neg(df["lab_procedure_her2_neu_in_situ_hybrid_outcome_type"])
    out["her2_pos"] = her2.fillna(fish)              # equivocal / missing IHC -> fall back to FISH
    hist = df["histological_type"].fillna("")
    out["histology"] = np.select(
        [hist.eq("Infiltrating Ductal Carcinoma"), hist.eq("Infiltrating Lobular Carcinoma"), hist.ne("")],
        ["Ductal", "Lobular", "Other"], default=None)
    out["menopause"] = df["menopause_status"].astype("string").str[:3].map(
        {"Pre": 0.0, "Per": 1.0, "Pos": 2.0})
    # descriptive-only columns (never fed to the model)
    stage = df["AJCC_PATHOLOGIC_TUMOR_STAGE"].astype("string").str.upper().str.replace("STAGE ", "", regex=False)
    out["stage_group"] = stage.str.extract(r"^(IV|III|II|I)")[0]
    out["pam50"] = df["SUBTYPE"].astype("string").str.replace("BRCA_", "", regex=False)
    out["os_months"] = df["OS_MONTHS"].astype(float)
    out[TARGET] = df["OS_STATUS"].astype("string").str.startswith("1").astype(float)
    out.loc[df["OS_STATUS"].isna(), TARGET] = np.nan

    # --- inclusion criteria -------------------------------------------------------------
    out = out[(df["SEX"].str.upper() == "FEMALE").values]                  # male breast cancer: n too small
    out = out[out["race"].isin(RACE_SHORT.values())]           # race recorded & n >= 60 per group
    out = out[out[TARGET].notna() & out["age"].notna()]
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------------------------
# Encoding (shared by training and the dashboard)
# --------------------------------------------------------------------------------------------
def encode(clean: pd.DataFrame, naive: bool = False) -> pd.DataFrame:
    """Human-readable patient table -> numeric model matrix with columns ``FEATURES``.

    The missing-data audit (notebook section 1.2) found that *not having a value recorded* for
    HER2, nodal status, M-stage and menopausal status is itself strongly associated with death
    (e.g. 33 % vs 11 % for HER2).  That is a documentation artefact of the registry, not biology,
    and a model that learns it would (a) look better than it is and (b) reward "unknown" inputs
    in the dashboard.  The default encoding therefore applies the clinical conventions:
        MX -> M0, NX -> N0, HER2 not recorded -> not positive, menopause dropped (collinear with age).
    ER / PR missingness is not outcome-associated and stays NaN (handled natively by XGBoost).
    ``naive=True`` reproduces the unprotected encoding, for the audit only.
    """
    X = pd.DataFrame(index=clean.index)
    X["age"] = clean["age"].astype(float)
    X["race_black"] = (clean["race"] == "Black").astype(float)
    X["race_asian"] = (clean["race"] == "Asian").astype(float)
    X["t_stage"] = clean["t_stage"].astype(float)
    X["n_stage"] = clean["n_stage"].astype(float)
    X["m_stage"] = clean["m_stage"].astype(float)
    X["er_pos"] = clean["er_pos"].astype(float)
    X["pr_pos"] = clean["pr_pos"].astype(float)
    X["her2_pos"] = clean["her2_pos"].astype(float)
    known = clean["histology"].notna()
    X["histology_lobular"] = np.where(known, (clean["histology"] == "Lobular").astype(float), np.nan)
    X["histology_other"] = np.where(known, (clean["histology"] == "Other").astype(float), np.nan)
    if naive:
        X["menopause"] = clean["menopause"].astype(float)
        return X[FEATURES_NAIVE]
    X["n_stage"] = X["n_stage"].fillna(0.0)
    X["m_stage"] = X["m_stage"].fillna(0.0)
    X["her2_pos"] = X["her2_pos"].fillna(0.0)
    return X[FEATURES]


def split_labels(clean: pd.DataFrame, seed: int = 42, val: float = 0.2, test: float = 0.2) -> pd.Series:
    """Stratified train/val/test assignment (stratified on race x outcome so every split keeps
    Black patients *and* deaths among them)."""
    from sklearn.model_selection import train_test_split
    strata = clean["race"].astype(str) + "_" + clean[TARGET].astype(int).astype(str)
    idx = np.arange(len(clean))
    tv, te = train_test_split(idx, test_size=test, stratify=strata, random_state=seed)
    tr, va = train_test_split(tv, test_size=val / (1 - test), stratify=strata.iloc[tv], random_state=seed)
    s = pd.Series("train", index=clean.index)
    s.iloc[va] = "val"
    s.iloc[te] = "test"
    return s
