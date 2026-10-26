# Data audit

Source: `data/data_clinical_patient.csv` (cBioPortal, TCGA PanCancer Atlas BRCA clinical patient table, 1,084 rows x 38 columns) with `data/clinical_data_dictionary.xlsx`.

## Cohort
1,084 patients; 151 deaths (13.9%); 751 White, 182 Black, 60 Asian, 91 race not recorded (+1 Native American, counted as not recorded).
Development / hold-out: 867 / 217 (37 Black patients and 6 Black deaths in the hold-out).

## Column governance (revised proposal Table 3.2 plus audit notes)
| column | decision | reason | audit_note |
|---|---|---|---|
| AGE | Included (predictor) | -> age | nan |
| SUBTYPE | Included (predictor) | -> sub_* | 103 missing; native missing |
| PATH_T_STAGE | Included (predictor) | -> t_stage | TX -> missing |
| PATH_N_STAGE | Included (predictor) | -> n_stage | NX -> missing; NX has a 61 % death rate (audit) |
| PATH_M_STAGE | Included (predictor) | -> m_stage | MX -> missing |
| ICD_O_3_HISTOLOGY | Included (predictor) | -> histology_* | ductal / lobular / other |
| RACE | Included (predictor) | -> race_black, race_asian | also the fairness group; 90 not recorded |
| RADIATION_THERAPY | Included (predictor) | -> radiation | 101 blanks; death rate 42 % when blank vs 11 % recorded -> informative missingness (audit) |
| HISTORY_NEOADJUVANT_TRTYN | Included (predictor) | -> neoadjuvant | only 6 'Yes' |
| PRIOR_DX | Included (predictor) | -> prior_dx | nan |
| OS_MONTHS | Excluded: outcome-related (leakage) | follow-up time that defines the outcome | nan |
| DAYS_LAST_FOLLOWUP | Excluded: outcome-related (leakage) | follow-up time; blank for every patient who died | nan |
| DSS_STATUS | Excluded: outcome-related (leakage) | disease-specific death: a subset of the outcome | nan |
| DSS_MONTHS | Excluded: outcome-related (leakage) | survival time | nan |
| DFS_STATUS | Excluded: outcome-related (leakage) | recurrence after treatment: known only after follow-up | nan |
| DFS_MONTHS | Excluded: outcome-related (leakage) | survival time | nan |
| PFS_STATUS | Excluded: outcome-related (leakage) | progression: known only after follow-up | nan |
| PFS_MONTHS | Excluded: outcome-related (leakage) | survival time | nan |
| PERSON_NEOPLASM_CANCER_STATUS | Excluded: outcome-related (leakage) | tumour status at last follow-up (outcome proxy) | nan |
| NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT | Excluded: outcome-related (leakage) | post-treatment event (outcome proxy) | nan |
| AJCC_PATHOLOGIC_TUMOR_STAGE | Excluded: redundant or sparse | composite of T, N, M (used only in the stage-group sensitivity model) | nan |
| DAYS_TO_BIRTH | Excluded: redundant or sparse | duplicates age | nan |
| GENETIC_ANCESTRY_LABEL | Excluded: redundant or sparse | overlaps race (used only in the ancestry sensitivity analysis) | nan |
| ETHNICITY | Excluded: redundant or sparse | 169 missing; blanks track the outcome (6 % deaths when blank vs 15 % when recorded) | nan |
| PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT | Excluded: redundant or sparse | 36 % missing, post-operative; not in the proposal's predictor list | nan |
| PATIENT_ID | Excluded: uninformative or constant | identifier | nan |
| OTHER_PATIENT_ID | Excluded: uninformative or constant | identifier | nan |
| CANCER_TYPE_ACRONYM | Excluded: uninformative or constant | constant (BRCA) | nan |
| ICD_10 | Excluded: uninformative or constant | constant (C50.9) | nan |
| ICD_O_3_SITE | Excluded: uninformative or constant | constant | nan |
| INFORMED_CONSENT_VERIFIED | Excluded: uninformative or constant | constant | nan |
| FORM_COMPLETION_DATE | Excluded: uninformative or constant | administrative date | nan |
| AJCC_STAGING_EDITION | Excluded: uninformative or constant | administrative; missingness differs by race | nan |
| IN_PANCANPATHWAYS_FREEZE | Excluded: uninformative or constant | administrative (equals SUBTYPE missingness) | nan |
| WEIGHT | Excluded: uninformative or constant | 100 % missing | nan |
| SEX | Excluded: uninformative or constant | 98.9 % female (12 male patients) | nan |
| OS_STATUS | Target | 1:DECEASED -> died = 1 | nan |

## Evidence 1: blanks that carry the outcome
| Column / code | n | % of cohort | Death rate if missing | Death rate if recorded |
|---|---|---|---|---|
| SUBTYPE | 103 | 9.502 | 0.184 | 0.135 |
| RADIATION_THERAPY | 101 | 9.317 | 0.416 | 0.111 |
| ETHNICITY | 169 | 15.590 | 0.059 | 0.154 |
| PRIMARY_LYMPH_NODE_PRESENTATION_ASSESSMENT | 364 | 33.579 | 0.148 | 0.135 |
| RACE | 90 | 8.303 | 0.078 | 0.145 |
| PERSON_NEOPLASM_CANCER_STATUS | 123 | 11.347 | 0.211 | 0.130 |
| NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT | 199 | 18.358 | 0.281 | 0.107 |
| AJCC_STAGING_EDITION | 140 | 12.915 | 0.121 | 0.142 |
| DAYS_LAST_FOLLOWUP | 104 | 9.594 | 1.000 | 0.048 |
| PATH_N_STAGE = NX | 20 | 1.845 | 0.550 | 0.132 |
| PATH_M_STAGE = MX | 162 | 14.945 | 0.086 | 0.149 |
| PATH_T_STAGE = TX | 3 | 0.277 | 0.333 | 0.139 |

## Evidence 2: where the as-proposed AUC comes from
| variant | auc | pr_auc |
|---|---|---|
| Proposal predictors (as specified) | 0.758 | 0.466 |
| minus radiation therapy (blank = 42 % death) | 0.699 | 0.343 |
| minus race recorded / not recorded signal (unknown -> White) | 0.746 | 0.394 |
| minus NX / MX codes (NX -> N0, MX -> M0) | 0.737 | 0.445 |
| minus all three artefacts | 0.648 | 0.294 |
| minus all three and neoadjuvant (= audit-hardened) | 0.649 | 0.298 |
| race-blind proposal predictors | 0.738 | 0.389 |

## Evidence 3: the leakage ladder
| Feature set | Why | AUC | PR-AUC | Precision at 80% recall |
|---|---|---|---|---|
| 0  Audit-hardened features | Age, T, N (NX->N0), M (MX->M0), PAM50, histology, prior dx, race | 0.666 | 0.314 | 0.181 |
| 1  Proposal Table 3.2 predictors (as specified) | Adds radiation therapy, neoadjuvant; NX / MX / TX left missing | 0.758 | 0.466 | 0.209 |
| 2  + ethnicity and node-assessment | Excluded by the proposal: blanks track the outcome | 0.768 | 0.476 | 0.220 |
| 3  + tumour status & new tumour event at follow-up | Outcome proxies recorded after diagnosis | 0.880 | 0.636 | 0.384 |
| 4  + days to last follow-up | Blank for every patient who died | 0.945 | 0.891 | 0.798 |

## Evidence 4: specifications compared
| spec | n_features | auc | pr_auc | fpr_at_80_recall | precision_at_80_recall |
|---|---|---|---|---|---|
| proposal | 16 | 0.758 | 0.466 | 0.490 | 0.209 |
| stage_group | 14 | 0.706 | 0.366 | 0.551 | 0.191 |
| hardened | 14 | 0.666 | 0.314 | 0.586 | 0.181 |
| complete_case_subtype | 16 | 0.752 | 0.468 | 0.493 | 0.203 |

## Other checks
* IDs unique; T, N, M parsed to ordinals (`T1C -> 1`, `N1MI -> 1`, `N0 (I+) -> 0`, `cM0 (I+) -> 0`); stage group parsed from `AJCC_PATHOLOGIC_TUMOR_STAGE` for the stage-group sensitivity model.
* PAM50 missing for 103 patients (death rate 18.4% vs 13.5%); complete-case sensitivity analysis in the specs table.
* Race not recorded: 90 patients, death rate 7.8% vs 14.5%.
