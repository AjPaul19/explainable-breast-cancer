# Data audit

Source: `data/data_clinical_patient.csv` (cBioPortal, TCGA PanCancer Atlas BRCA clinical patient table, 1,084 rows x 38 columns) with the
definitions in `data/clinical_data_dictionary.xlsx`.

## Cohort flow
| Step | n |
|---|---|
| Records in file | 1084 |
| Race not recorded | -90 |
| Asian / American Indian | -61 |
| **Study cohort (White or Black)** | **933** (751 White, 182 Black) |
| Deaths | 141 (111 White, 30 Black) |
| Development / hold-out | 746 / 187 (hold-out: 37 Black patients, 6 deaths) |

## What each column is allowed to do
| column | decision | reason |
|---|---|---|
| OS_MONTHS | Excluded: outcome leakage / post-baseline | the follow-up time that defines the outcome |
| DAYS_LAST_FOLLOWUP | Excluded: outcome leakage / post-baseline | follow-up time; blank for 100 % of deaths in the cohort (another label) |
| DSS_STATUS | Excluded: outcome leakage / post-baseline | disease-specific death: a subset of the outcome |
| DSS_MONTHS | Excluded: outcome leakage / post-baseline | survival time |
| DFS_STATUS | Excluded: outcome leakage / post-baseline | recurrence after treatment: only known after follow-up |
| DFS_MONTHS | Excluded: outcome leakage / post-baseline | survival time |
| PFS_STATUS | Excluded: outcome leakage / post-baseline | progression: only known after follow-up |
| PFS_MONTHS | Excluded: outcome leakage / post-baseline | survival time |
| PERSON_NEOPLASM_CANCER_STATUS | Excluded: outcome leakage / post-baseline | tumour status at last follow-up (post-baseline, outcome proxy) |
| NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT | Excluded: outcome leakage / post-baseline | post-treatment event (post-baseline, outcome proxy) |
| DAYS_TO_INITIAL_PATHOLOGIC_DIAGNOSIS | Excluded: outcome leakage / post-baseline | constant 0 reference day |
| FORM_COMPLETION_DATE | Excluded: outcome leakage / post-baseline | administrative date |
| RADIATION_THERAPY | Excluded: informative missingness | missing for 56 % deaths vs 12 % otherwise: a documentation artefact |
| ETHNICITY | Excluded: informative missingness | missing for 4 % deaths vs 16 % otherwise: reporting practice, not biology |
| PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT | Excluded: informative missingness | 36 % missing and largely post-operative |
| AJCC_STAGING_EDITION | Excluded: informative missingness | an administrative variable whose missingness differs by race (126 of 751 White vs 8 of 182 Black) |
| PATIENT_ID | Excluded: no signal / redundant | identifier |
| OTHER_PATIENT_ID | Excluded: no signal / redundant | identifier |
| CANCER_TYPE_ACRONYM | Excluded: no signal / redundant | constant (BRCA) |
| ICD_10 | Excluded: no signal / redundant | constant (C50.9) |
| ICD_O_3_SITE | Excluded: no signal / redundant | constant |
| INFORMED_CONSENT_VERIFIED | Excluded: no signal / redundant | constant |
| WEIGHT | Excluded: no signal / redundant | 100 % missing |
| IN_PANCANPATHWAYS_FREEZE | Excluded: no signal / redundant | administrative (equals SUBTYPE missingness) |
| DAYS_TO_BIRTH | Excluded: no signal / redundant | redundant with AGE |
| SEX | Excluded: no signal / redundant | 12 male patients: too few to model |
| HISTORY_NEOADJUVANT_TRTYN | Excluded: no signal / redundant | only 6 'Yes' |
| AJCC_PATHOLOGIC_TUMOR_STAGE | Excluded: no signal / redundant | redundant with T, N, M |
| GENETIC_ANCESTRY_LABEL | Excluded: no signal / redundant | used only for the sensitivity analysis, never as an input |
| AGE | Kept as model input | -> age |
| PATH_T_STAGE | Kept as model input | -> t_stage |
| PATH_N_STAGE | Kept as model input | -> n_stage |
| PATH_M_STAGE | Kept as model input | -> m_stage |
| SUBTYPE | Kept as model input | -> sub_* |
| ICD_O_3_HISTOLOGY | Kept as model input | -> histology_* |
| PRIOR_DX | Kept as model input | -> prior_dx |
| RACE | Kept as model input | -> race_black (aware model only) and the fairness group |
| OS_STATUS | Target | 1:DECEASED -> died = 1 |

## Evidence 1: informative missingness
A blank is not neutral if it predicts the outcome. Death rates inside the White + Black cohort:

| Column / code | n | % of cohort | Death rate if missing | Death rate if recorded |
|---|---|---|---|---|
| SUBTYPE | 96 | 10.289 | 0.198 | 0.146 |
| RADIATION_THERAPY | 71 | 7.610 | 0.563 | 0.117 |
| ETHNICITY | 81 | 8.682 | 0.037 | 0.162 |
| PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT | 266 | 28.510 | 0.173 | 0.142 |
| PERSON_NEOPLASM_CANCER_STATUS | 111 | 11.897 | 0.216 | 0.142 |
| NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT | 155 | 16.613 | 0.323 | 0.117 |
| AJCC_STAGING_EDITION | 134 | 14.362 | 0.119 | 0.156 |
| DAYS_LAST_FOLLOWUP | 98 | 10.504 | 1.000 | 0.051 |
| PATH_N_STAGE = NX | 18 | 1.929 | 0.611 | 0.142 |
| PATH_M_STAGE = MX | 154 | 16.506 | 0.091 | 0.163 |

Consequences: radiation, ethnicity and the node-presentation field are dropped; `NX` is treated as N0 and `MX` as M0 (AJCC convention),
so the model cannot reward "not assessed".

## Evidence 2: the leakage ladder
Cross-validated AUC of the same XGBoost as columns that should not be inputs are added back:

| Feature set | Why | AUC | FPR @ 80% recall |
|---|---|---|---|
| 0  Clean pre-treatment features (used) | Age, T, N (NX->N0), M (MX->M0), PAM50, histology, prior diagnosis | 0.657 | 0.596 |
| 1  + NX / MX left as 'missing' | Registry 'not assessed' codes: NX has a 61 % death rate | 0.678 | 0.560 |
| 2  + radiation, ethnicity, node-assessment (informative missingness) | Their blanks track the outcome (56 % vs 12 % for radiation) | 0.755 | 0.514 |
| 3  + tumour status & new-tumour event at follow-up (post-baseline) | Outcome proxies recorded after diagnosis | 0.859 | 0.303 |
| 4  + days to last follow-up | Blank for every patient who died | 0.914 | 0.080 |

An unprotected analysis would report AUC around 0.9 and look excellent; none of that is prediction (follow-up time is blank for every patient who died).

## Other checks
* Patient IDs unique (0 duplicates); T, N, M parsed to ordinal categories (`T1C -> 1`, `N1MI -> 1`, `N0 (I+) -> 0`, `CM0 (I+) -> M0`); TX (3 patients) stays missing.
* PAM50 subtype is missing for 96 patients; XGBoost treats unknown natively. The missing group's death rate is 19.8% vs 14.6%: a mild shift, kept as `unknown`.
* `WEIGHT` is 100 % empty. `SEX`: 12 male patients, not modelled.
* Follow-up is similar across races (median 32 (17-62) months White vs 27 (15-54) Black).
