"""
generate_data.py
-----------------
Synthetic-but-realistic data generator for the Health Record Portal Analytics
project.

The dataset simulates two and a half years (Jan 2024 - Aug 2026) of a hospital
system's patient-portal usage: patient/provider dimensions, clinical
encounters, portal engagement events, satisfaction surveys, and outreach
campaigns run by the medical outreach team.

All randomness is seeded, so re-running this script always reproduces the
same dataset (important for the SQL/Tableau/Power BI layers built on top of
it to stay in sync).

Output: CSV files under ../data/raw/
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
os.makedirs(OUT_DIR, exist_ok=True)

START_DATE = pd.Timestamp("2024-01-01")
END_DATE = pd.Timestamp("2026-08-08")  # "today"

N_PATIENTS = 5000
N_PROVIDERS = 62

REGIONS = ["Northeast", "Midwest", "South", "West"]
REGION_WEIGHTS = [0.28, 0.24, 0.30, 0.18]

DEPARTMENTS = [
    ("D01", "Primary Care"),
    ("D02", "Cardiology"),
    ("D03", "Pediatrics"),
    ("D04", "Oncology"),
    ("D05", "Behavioral Health"),
    ("D06", "Endocrinology"),
]
DEPT_WEIGHTS = [0.34, 0.16, 0.18, 0.08, 0.14, 0.10]

INSURANCE_TYPES = ["Commercial", "Medicare", "Medicaid", "Uninsured"]
INSURANCE_WEIGHTS = [0.48, 0.27, 0.20, 0.05]

DEVICE_TYPES = ["Mobile App", "Desktop Web", "Mobile Web"]
DEVICE_WEIGHTS = [0.58, 0.27, 0.15]

EVENT_TYPES = [
    "login",
    "message_sent",
    "appointment_scheduled",
    "lab_result_viewed",
    "prescription_refill",
    "survey_completed",
    "education_content_viewed",
    "billing_viewed",
]
# relative frequency per active session
EVENT_WEIGHTS = [0.34, 0.12, 0.10, 0.16, 0.09, 0.03, 0.10, 0.06]

MONTHS = pd.period_range(START_DATE, END_DATE, freq="M")


def month_index(ts: pd.Timestamp) -> int:
    return (ts.year - START_DATE.year) * 12 + (ts.month - START_DATE.month)


N_MONTHS = month_index(END_DATE) + 1


# --------------------------------------------------------------------------
# Dimension: Departments
# --------------------------------------------------------------------------
dim_departments = pd.DataFrame(DEPARTMENTS, columns=["department_id", "department_name"])
dim_departments["region_hub"] = rng.choice(REGIONS, size=len(dim_departments))
dim_departments.to_csv(os.path.join(OUT_DIR, "dim_departments.csv"), index=False)


# --------------------------------------------------------------------------
# Dimension: Providers
# --------------------------------------------------------------------------
first_names = ["James", "Maria", "Wei", "Fatima", "David", "Priya", "John", "Elena",
               "Carlos", "Aisha", "Robert", "Yuki", "Sara", "Miguel", "Grace", "Omar"]
last_names = ["Chen", "Garcia", "Patel", "Smith", "Nguyen", "Johnson", "Kim", "Brown",
              "Rossi", "Khan", "Müller", "Davis", "Silva", "Cohen", "Adeyemi", "Novak"]

provider_ids = [f"PR{str(i).zfill(4)}" for i in range(1, N_PROVIDERS + 1)]
dim_providers = pd.DataFrame({
    "provider_id": provider_ids,
    "provider_name": [f"Dr. {rng.choice(first_names)} {rng.choice(last_names)}" for _ in provider_ids],
    "department_id": rng.choice([d[0] for d in DEPARTMENTS], size=N_PROVIDERS, p=DEPT_WEIGHTS),
    "region": rng.choice(REGIONS, size=N_PROVIDERS, p=REGION_WEIGHTS),
    "telehealth_enabled": rng.choice([True, False], size=N_PROVIDERS, p=[0.72, 0.28]),
})
dim_providers.to_csv(os.path.join(OUT_DIR, "dim_providers.csv"), index=False)


# --------------------------------------------------------------------------
# Dimension: Patients (+ portal enrollment)
# --------------------------------------------------------------------------
patient_ids = [f"PT{str(i).zfill(5)}" for i in range(1, N_PATIENTS + 1)]

ages = rng.normal(46, 18, size=N_PATIENTS).clip(1, 95).round().astype(int)
gender = rng.choice(["Female", "Male", "Nonbinary/Other"], size=N_PATIENTS, p=[0.51, 0.46, 0.03])
region = rng.choice(REGIONS, size=N_PATIENTS, p=REGION_WEIGHTS)
insurance = rng.choice(INSURANCE_TYPES, size=N_PATIENTS, p=INSURANCE_WEIGHTS)
primary_dept = rng.choice([d[0] for d in DEPARTMENTS], size=N_PATIENTS, p=DEPT_WEIGHTS)
chronic_flag = (rng.random(N_PATIENTS) < np.clip(0.10 + (ages - 30) * 0.006, 0.05, 0.65)).astype(int)

# Patient "arrival" (became a hospital patient) spread across the whole window,
# skewed toward the earlier months so there's a mature base plus new growth.
arrival_month = rng.triangular(0, 0, N_MONTHS - 1, size=N_PATIENTS).astype(int)
patient_arrival_date = START_DATE + pd.to_timedelta(arrival_month * 30 + rng.integers(0, 28, N_PATIENTS), unit="D")

dim_patients = pd.DataFrame({
    "patient_id": patient_ids,
    "age": ages,
    "gender": gender,
    "region": region,
    "insurance_type": insurance,
    "primary_department_id": primary_dept,
    "chronic_condition_flag": chronic_flag,
    "patient_since": patient_arrival_date,
})

# --- Portal enrollment ---
# Enrollment propensity rises over time (outreach campaigns + portal maturity),
# and is higher for younger/commercially-insured patients (mirrors real-world
# digital-engagement skew), lower for uninsured/older patients.
base_enroll_prob = 0.35 + 0.40 * (arrival_month / (N_MONTHS - 1))  # 0.35 -> 0.75 baseline by cohort
age_adj = np.select(
    [ages < 30, ages < 60, ages < 75, ages >= 75],
    [0.10, 0.03, -0.08, -0.22],
)
insurance_adj = pd.Series(insurance).map({
    "Commercial": 0.08, "Medicare": -0.05, "Medicaid": -0.03, "Uninsured": -0.18
}).values
enroll_prob = np.clip(base_enroll_prob + age_adj + insurance_adj, 0.05, 0.97)
enrolled = rng.random(N_PATIENTS) < enroll_prob

signup_lag_days = rng.exponential(25, N_PATIENTS).clip(0, 400).astype(int)
signup_date = patient_arrival_date + pd.to_timedelta(signup_lag_days, unit="D")
signup_date = signup_date.where(signup_date <= END_DATE, pd.NaT)
enrolled = enrolled & signup_date.notna()

dim_patients["portal_enrolled"] = enrolled
dim_patients["portal_signup_date"] = signup_date.where(enrolled, pd.NaT)
dim_patients["preferred_device"] = np.where(
    enrolled, rng.choice(DEVICE_TYPES, size=N_PATIENTS, p=DEVICE_WEIGHTS), None
)

dim_patients.to_csv(os.path.join(OUT_DIR, "dim_patients.csv"), index=False)


# --------------------------------------------------------------------------
# Fact: Portal engagement events (for enrolled patients only)
# --------------------------------------------------------------------------
enrolled_df = dim_patients[dim_patients["portal_enrolled"]].copy()

# Each enrolled patient gets an underlying "engagement propensity" (0-1) that
# drives how many sessions/month they generate. Chronic-condition patients and
# younger patients tend to engage more; propensity also decays slowly for a
# minority of patients (simulated churn) and can be boosted by campaigns later.
propensity = np.clip(
    rng.beta(2.2, 3.0, size=len(enrolled_df))
    + 0.12 * enrolled_df["chronic_condition_flag"].values
    + np.select([enrolled_df["age"].values < 40, enrolled_df["age"].values < 65], [0.06, 0.0], default=-0.05),
    0.03, 0.95,
)
enrolled_df["engagement_propensity"] = propensity
# ~14% of enrolled patients are "at risk" and drift toward disengagement over time
churn_track = rng.random(len(enrolled_df)) < 0.14
enrolled_df["is_churn_track"] = churn_track

events = []
event_id_counter = 1

for row in enrolled_df.itertuples(index=False):
    signup = row.portal_signup_date
    if pd.isna(signup):
        continue
    months_active = pd.period_range(signup, END_DATE, freq="M")
    if len(months_active) == 0:
        continue
    base_lambda = row.engagement_propensity * 3.4  # avg sessions/month at full engagement

    for i, m in enumerate(months_active):
        # seasonal dip in Jul/Aug/Dec, campaign-driven bump modeled later via campaigns file
        seasonal = {7: 0.85, 8: 0.85, 12: 0.8, 1: 1.15}.get(m.month, 1.0)
        churn_decay = 1.0
        if row.is_churn_track:
            churn_decay = max(0.05, 1.0 - 0.05 * i)  # fades out over ~20 months
        lam = max(0.05, base_lambda * seasonal * churn_decay)
        n_sessions = rng.poisson(lam)
        if n_sessions == 0:
            continue
        month_start = m.start_time
        month_end = min(m.end_time, END_DATE)
        span_days = max(1, (month_end - month_start).days)
        session_days = rng.integers(0, span_days + 1, size=n_sessions)
        for d in session_days:
            ev_date = month_start + pd.Timedelta(days=int(d))
            if ev_date > END_DATE:
                continue
            n_actions = rng.integers(1, 4)
            for _ in range(n_actions):
                ev_type = rng.choice(EVENT_TYPES, p=EVENT_WEIGHTS)
                duration = int(np.clip(rng.gamma(2.0, 90), 15, 1800))
                events.append((
                    f"EV{event_id_counter:08d}", row.patient_id, ev_date.date().isoformat(),
                    ev_type, duration, row.preferred_device,
                ))
                event_id_counter += 1

fact_portal_engagement = pd.DataFrame(
    events,
    columns=["event_id", "patient_id", "event_date", "event_type", "session_duration_sec", "device_type"],
)
fact_portal_engagement.to_csv(os.path.join(OUT_DIR, "fact_portal_engagement.csv"), index=False)


# --------------------------------------------------------------------------
# Fact: Clinical encounters
# --------------------------------------------------------------------------
ENCOUNTER_TYPES = ["In-Person Visit", "Telehealth", "Lab Work", "Portal Message"]
ENCOUNTER_WEIGHTS = [0.46, 0.24, 0.18, 0.12]

n_encounters_target = 42000
enc_patient_idx = rng.integers(0, N_PATIENTS, n_encounters_target)
enc_patient_ids = dim_patients["patient_id"].values[enc_patient_idx]
enc_patient_since = dim_patients["patient_since"].values[enc_patient_idx]

# encounter date: uniform between patient_since and END_DATE
days_span = (END_DATE - pd.Series(enc_patient_since)).dt.days.clip(lower=1).values
enc_offsets = (rng.random(n_encounters_target) * days_span).astype(int)
enc_dates = pd.Series(enc_patient_since) + pd.to_timedelta(enc_offsets, unit="D")

enc_dept = rng.choice([d[0] for d in DEPARTMENTS], size=n_encounters_target, p=DEPT_WEIGHTS)
enc_provider = rng.choice(dim_providers["provider_id"].values, size=n_encounters_target)
enc_type = rng.choice(ENCOUNTER_TYPES, size=n_encounters_target, p=ENCOUNTER_WEIGHTS)

status_probs = np.where(enc_type == "In-Person Visit",
                         rng.choice(["Completed", "No-Show", "Cancelled"], size=n_encounters_target,
                                    p=[0.84, 0.10, 0.06]),
                         "Completed")

fact_encounters = pd.DataFrame({
    "encounter_id": [f"ENC{str(i).zfill(7)}" for i in range(1, n_encounters_target + 1)],
    "patient_id": enc_patient_ids,
    "provider_id": enc_provider,
    "department_id": enc_dept,
    "encounter_date": enc_dates.dt.date.astype(str),
    "encounter_type": enc_type,
    "status": status_probs,
})
fact_encounters = fact_encounters[fact_encounters["encounter_date"] <= END_DATE.date().isoformat()]
fact_encounters.to_csv(os.path.join(OUT_DIR, "fact_encounters.csv"), index=False)


# --------------------------------------------------------------------------
# Fact: Satisfaction surveys (NPS / CSAT) - only from enrolled+engaged patients
# --------------------------------------------------------------------------
survey_rows = fact_portal_engagement[fact_portal_engagement["event_type"] == "survey_completed"].copy()
n_surveys = len(survey_rows)

# Scores trend upward over the program's life as the outreach team's KPI
# work (onboarding pushes, telehealth awareness, senior digital-access
# program, etc.) takes hold — modeled as a right-skewing Beta distribution
# rather than flat noise, so NPS/CSAT actually tell an improvement story.
survey_month_idx = np.array([month_index(pd.Timestamp(d)) for d in survey_rows["event_date"]])
trend = np.clip(survey_month_idx / max(1, N_MONTHS - 1), 0, 1)
nps_alpha = 2.0 + 2.5 * trend
nps_beta = 4.0 - 2.0 * trend
nps = np.round(rng.beta(nps_alpha, nps_beta, n_surveys) * 10).astype(int).clip(0, 10)
csat = np.clip(rng.normal(3.7 + 0.55 * trend, 0.7, n_surveys), 1, 5).round(1)

fact_satisfaction_surveys = pd.DataFrame({
    "survey_id": [f"SV{str(i).zfill(6)}" for i in range(1, n_surveys + 1)],
    "patient_id": survey_rows["patient_id"].values,
    "survey_date": survey_rows["event_date"].values,
    "nps_score": nps,
    "csat_score": csat,
})
fact_satisfaction_surveys.to_csv(os.path.join(OUT_DIR, "fact_satisfaction_surveys.csv"), index=False)


# --------------------------------------------------------------------------
# Dimension + Fact: Outreach campaigns (medical outreach team collaboration)
# --------------------------------------------------------------------------
campaigns = [
    ("CMP01", "New Patient Portal Onboarding", "2024-02-01", "2024-03-15", "All", None, "Email+SMS"),
    ("CMP02", "Chronic Care Check-In Push", "2024-06-01", "2024-07-01", "Chronic Condition", None, "Phone+Portal"),
    ("CMP03", "Telehealth Awareness Drive", "2024-09-01", "2024-10-01", "All", "D01", "Email"),
    ("CMP04", "Senior Digital Access Program", "2025-01-15", "2025-03-01", "65+", None, "Mail+Phone"),
    ("CMP05", "Behavioral Health Engagement Sprint", "2025-04-01", "2025-05-01", "All", "D05", "Portal+SMS"),
    ("CMP06", "Preventive Screening Reminder", "2025-08-01", "2025-09-01", "All", None, "SMS"),
    ("CMP07", "Oncology Support Portal Rollout", "2025-11-01", "2025-12-01", "All", "D04", "Phone+Portal"),
    ("CMP08", "Spring Wellness Portal Refresh", "2026-03-01", "2026-04-01", "All", None, "Email+SMS"),
    ("CMP09", "Uninsured/Medicaid Access Outreach", "2026-06-01", "2026-07-15", "Medicaid/Uninsured", None, "Phone+Mail"),
]
dim_campaigns = pd.DataFrame(
    campaigns, columns=["campaign_id", "campaign_name", "start_date", "end_date",
                         "target_segment", "target_department_id", "channel"]
)
dim_campaigns.to_csv(os.path.join(OUT_DIR, "dim_campaigns.csv"), index=False)

campaign_response_rows = []
resp_id = 1
for c in dim_campaigns.itertuples(index=False):
    seg = c.target_segment
    if seg == "All":
        pool = dim_patients
    elif seg == "Chronic Condition":
        pool = dim_patients[dim_patients["chronic_condition_flag"] == 1]
    elif seg == "65+":
        pool = dim_patients[dim_patients["age"] >= 65]
    elif seg == "Medicaid/Uninsured":
        pool = dim_patients[dim_patients["insurance_type"].isin(["Medicaid", "Uninsured"])]
    else:
        pool = dim_patients
    if pd.notna(c.target_department_id):
        pool = pool[pool["primary_department_id"] == c.target_department_id]
    if len(pool) == 0:
        continue
    sample_n = min(len(pool), rng.integers(int(len(pool) * 0.35), max(2, int(len(pool) * 0.65)) + 1))
    sampled = pool.sample(n=sample_n, random_state=int(rng.integers(0, 1_000_000)))
    start = pd.Timestamp(c.start_date)
    end = pd.Timestamp(c.end_date)
    resp_dates = start + pd.to_timedelta(rng.integers(0, max(1, (end - start).days) + 1, size=sample_n), unit="D")
    engaged = rng.random(sample_n) < rng.uniform(0.28, 0.55)
    for pid, rdate, eng in zip(sampled["patient_id"].values, resp_dates, engaged):
        campaign_response_rows.append((f"CR{resp_id:07d}", c.campaign_id, pid, rdate.date().isoformat(), bool(eng)))
        resp_id += 1

fact_campaign_responses = pd.DataFrame(
    campaign_response_rows,
    columns=["response_id", "campaign_id", "patient_id", "response_date", "engaged_flag"],
)
fact_campaign_responses.to_csv(os.path.join(OUT_DIR, "fact_campaign_responses.csv"), index=False)

# --------------------------------------------------------------------------
# Summary printout
# --------------------------------------------------------------------------
print("Synthetic data generated:")
print(f"  dim_patients:              {len(dim_patients):>8,} rows  ({enrolled_df.shape[0]:,} portal-enrolled)")
print(f"  dim_providers:             {len(dim_providers):>8,} rows")
print(f"  dim_departments:           {len(dim_departments):>8,} rows")
print(f"  dim_campaigns:             {len(dim_campaigns):>8,} rows")
print(f"  fact_encounters:           {len(fact_encounters):>8,} rows")
print(f"  fact_portal_engagement:    {len(fact_portal_engagement):>8,} rows")
print(f"  fact_satisfaction_surveys: {len(fact_satisfaction_surveys):>8,} rows")
print(f"  fact_campaign_responses:   {len(fact_campaign_responses):>8,} rows")
print(f"\nCSV files written to: {os.path.abspath(OUT_DIR)}")
