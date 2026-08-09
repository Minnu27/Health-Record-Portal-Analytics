"""
advanced_analytics.py
----------------------
Advanced analytics layer on top of the curated warehouse
(data/processed/health_portal.db). Produces:

  1. A per-patient composite Engagement Score + tiering (High/Medium/Low/
     Inactive), exported for use as a Tableau/Power BI calculated field
     substitute and as model input.
  2. A disengagement-risk (churn) classification model — logistic
     regression vs. random forest — predicting which currently-active
     enrolled patients are likely to go dark in the next 60 days.
  3. A statistical significance test on whether telehealth adoption is
     associated with higher portal engagement (Welch's t-test).
  4. Cohort retention heatmap and model diagnostic figures.

Outputs:
  data/processed/patient_engagement_scores.csv
  outputs/model_metrics.md
  outputs/figures/*.png
"""
from __future__ import annotations

import os
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

BASE = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE, "..", "data", "processed", "health_portal.db")
PROCESSED_DIR = os.path.join(BASE, "..", "data", "processed")
FIG_DIR = os.path.join(BASE, "..", "outputs", "figures")
METRICS_PATH = os.path.join(BASE, "..", "outputs", "model_metrics.md")
os.makedirs(FIG_DIR, exist_ok=True)

AS_OF = pd.Timestamp("2026-08-08")

conn = sqlite3.connect(DB_PATH)


# ==========================================================================
# 1. Per-patient feature build (trailing-180-day window, as of AS_OF)
# ==========================================================================
patients = pd.read_sql_query("SELECT * FROM dim_patients WHERE portal_enrolled = 1", conn,
                              parse_dates=["patient_since", "portal_signup_date"])

events = pd.read_sql_query(
    "SELECT patient_id, event_date, event_type, session_duration_sec FROM fact_portal_engagement",
    conn, parse_dates=["event_date"],
)
encounters = pd.read_sql_query(
    "SELECT patient_id, encounter_date, encounter_type, status FROM fact_encounters",
    conn, parse_dates=["encounter_date"],
)
surveys = pd.read_sql_query(
    "SELECT patient_id, survey_date, nps_score, csat_score FROM fact_satisfaction_surveys",
    conn, parse_dates=["survey_date"],
)

window_180 = AS_OF - pd.Timedelta(days=180)
window_90 = AS_OF - pd.Timedelta(days=90)
window_60 = AS_OF - pd.Timedelta(days=60)

ev_180 = events[events["event_date"] >= window_180]
ev_90 = events[events["event_date"] >= window_90]

agg_180 = ev_180.groupby("patient_id").agg(
    events_180d=("event_type", "count"),
    avg_session_sec=("session_duration_sec", "mean"),
    distinct_active_days_180d=("event_date", "nunique"),
).reset_index()

agg_90 = ev_90.groupby("patient_id").agg(events_90d=("event_type", "count")).reset_index()

last_active = events.groupby("patient_id")["event_date"].max().rename("last_active_date").reset_index()

msg_counts = (
    events[events["event_type"] == "message_sent"].groupby("patient_id").size().rename("messages_180d")
)
lab_counts = (
    events[events["event_type"] == "lab_result_viewed"].groupby("patient_id").size().rename("lab_views")
)

telehealth_counts = (
    encounters[encounters["encounter_type"] == "Telehealth"].groupby("patient_id").size().rename("telehealth_visits")
)
noshow_counts = (
    encounters[encounters["status"] == "No-Show"].groupby("patient_id").size().rename("no_shows")
)

avg_csat = surveys.groupby("patient_id")["csat_score"].mean().rename("avg_csat")

feat = patients[["patient_id", "age", "gender", "region", "insurance_type",
                  "chronic_condition_flag", "patient_since", "portal_signup_date",
                  "preferred_device"]].copy()
feat["tenure_days"] = (AS_OF - feat["portal_signup_date"]).dt.days

for piece in [agg_180, agg_90, last_active, msg_counts, lab_counts,
              telehealth_counts, noshow_counts, avg_csat]:
    feat = feat.merge(piece, on="patient_id", how="left")

fill_zero_cols = ["events_180d", "avg_session_sec", "distinct_active_days_180d",
                   "events_90d", "messages_180d", "lab_views", "telehealth_visits", "no_shows"]
for c in fill_zero_cols:
    feat[c] = feat[c].fillna(0)
feat["avg_csat"] = feat["avg_csat"].fillna(feat["avg_csat"].median())
feat["days_since_last_active"] = (AS_OF - feat["last_active_date"]).dt.days
feat["days_since_last_active"] = feat["days_since_last_active"].fillna(feat["tenure_days"])


# ==========================================================================
# 2. Composite Engagement Score (0-100) + tiering
# ==========================================================================
# Weighted, min-max-normalized blend of recency, frequency, depth, and
# breadth signals — the same feature families a Tableau "Engagement Score"
# calculated field would use, just computed once here and pushed to the
# extract so the BI tools don't need row-level scripting.
def minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    if hi - lo == 0:
        return pd.Series(0.0, index=s.index)
    return (s - lo) / (hi - lo)


recency_score = 1 - minmax(feat["days_since_last_active"].clip(upper=180))
frequency_score = minmax(feat["events_90d"].clip(upper=feat["events_90d"].quantile(0.98)))
depth_score = minmax(feat["distinct_active_days_180d"])
breadth_score = minmax(feat["messages_180d"] + feat["lab_views"])

feat["engagement_score"] = (
    100 * (0.40 * recency_score + 0.30 * frequency_score + 0.20 * depth_score + 0.10 * breadth_score)
).round(1)

feat["engagement_tier"] = pd.cut(
    feat["engagement_score"],
    bins=[-0.1, 25, 50, 75, 100],
    labels=["Inactive", "Low", "Medium", "High"],
)

score_cols = ["patient_id", "age", "region", "insurance_type", "chronic_condition_flag",
              "tenure_days", "events_180d", "events_90d", "avg_session_sec",
              "distinct_active_days_180d", "messages_180d", "lab_views",
              "telehealth_visits", "no_shows", "avg_csat", "days_since_last_active",
              "engagement_score", "engagement_tier"]
feat[score_cols].to_csv(os.path.join(PROCESSED_DIR, "patient_engagement_scores.csv"), index=False)

tier_summary = feat["engagement_tier"].value_counts(normalize=True).mul(100).round(1).sort_index()


# ==========================================================================
# 3. Disengagement-risk (churn) model
# ==========================================================================
# Label: patient is enrolled 60+ days and has had NO portal activity in the
# trailing 60 days as of AS_OF -> "disengaged". This is a realistic proxy
# for the outreach team's re-engagement target list.
eligible = feat[feat["tenure_days"] >= 60].copy()
eligible["disengaged"] = (eligible["days_since_last_active"] >= 60).astype(int)

feature_cols_num = ["age", "tenure_days", "events_180d", "avg_session_sec",
                     "distinct_active_days_180d", "messages_180d", "lab_views",
                     "telehealth_visits", "no_shows", "avg_csat", "chronic_condition_flag"]
X_num = eligible[feature_cols_num].copy()
X_cat = pd.get_dummies(eligible[["insurance_type", "region"]], drop_first=True)
X = pd.concat([X_num, X_cat], axis=1)
y = eligible["disengaged"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

logit = LogisticRegression(max_iter=1000, class_weight="balanced")
logit.fit(X_train_s, y_train)
logit_proba = logit.predict_proba(X_test_s)[:, 1]
logit_auc = roc_auc_score(y_test, logit_proba)

rf = RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=10,
                             class_weight="balanced", random_state=42)
rf.fit(X_train, y_train)
rf_proba = rf.predict_proba(X_test)[:, 1]
rf_auc = roc_auc_score(y_test, rf_proba)

rf_importance = (
    pd.Series(rf.feature_importances_, index=X.columns)
    .sort_values(ascending=False)
    .head(10)
)

# ROC curve figure
fig, ax = plt.subplots(figsize=(6, 5))
for name, proba, auc in [("Logistic Regression", logit_proba, logit_auc), ("Random Forest", rf_proba, rf_auc)]:
    fpr, tpr, _ = roc_curve(y_test, proba)
    ax.plot(fpr, tpr, label=f"{name} (AUC={auc:.3f})")
ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
ax.set_xlabel("False Positive Rate")
ax.set_ylabel("True Positive Rate")
ax.set_title("Disengagement-Risk Model — ROC Curve")
ax.legend(loc="lower right")
fig.tight_layout()
fig.savefig(os.path.join(FIG_DIR, "roc_curve.png"), dpi=140)
plt.close(fig)

# Feature importance figure
fig, ax = plt.subplots(figsize=(7, 5))
rf_importance.sort_values().plot(kind="barh", ax=ax, color="#3B6E8F")
ax.set_title("Top Predictors of Patient Disengagement (Random Forest)")
ax.set_xlabel("Feature Importance")
fig.tight_layout()
fig.savefig(os.path.join(FIG_DIR, "feature_importance.png"), dpi=140)
plt.close(fig)

report = classification_report(y_test, (rf_proba >= 0.5).astype(int), zero_division=0)


# ==========================================================================
# 4. Statistical test — does telehealth adoption relate to engagement?
# ==========================================================================
adopters = feat[feat["telehealth_visits"] > 0]["engagement_score"]
non_adopters = feat[feat["telehealth_visits"] == 0]["engagement_score"]
t_stat, p_val = stats.ttest_ind(adopters, non_adopters, equal_var=False)

fig, ax = plt.subplots(figsize=(6.5, 5))
ax.boxplot([non_adopters, adopters], tick_labels=["No Telehealth Visits", "1+ Telehealth Visits"],
           patch_artist=True,
           boxprops=dict(facecolor="#A9CCE3"), medianprops=dict(color="#1B4F72"))
ax.set_ylabel("Engagement Score (0-100)")
ax.set_title(f"Engagement by Telehealth Adoption (Welch t-test p={p_val:.4f})")
fig.tight_layout()
fig.savefig(os.path.join(FIG_DIR, "telehealth_engagement_ttest.png"), dpi=140)
plt.close(fig)


# ==========================================================================
# 5. Cohort retention heatmap (reads the SQL-materialized extract)
# ==========================================================================
cohort = pd.read_csv(os.path.join(PROCESSED_DIR, "04_cohort_retention.csv"))
pivot = cohort.pivot(index="cohort_month", columns="months_since_signup", values="retention_pct")
pivot = pivot.sort_index()

fig, ax = plt.subplots(figsize=(11, 7))
im = ax.imshow(pivot.values, cmap="YlGnBu", aspect="auto", vmin=0, vmax=100)
ax.set_xticks(range(len(pivot.columns)))
ax.set_xticklabels(pivot.columns)
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels(pivot.index, fontsize=7)
ax.set_xlabel("Months Since Portal Signup")
ax.set_ylabel("Signup Cohort")
ax.set_title("Patient Portal Retention by Signup Cohort")
fig.colorbar(im, ax=ax, label="Retention %")
fig.tight_layout()
fig.savefig(os.path.join(FIG_DIR, "cohort_retention_heatmap.png"), dpi=140)
plt.close(fig)


# ==========================================================================
# Write metrics report
# ==========================================================================
lines = []
lines.append("# Advanced Analytics — Model & Test Results\n")
lines.append(f"_Generated as of {AS_OF.date()} from {len(feat):,} enrolled patients "
             f"({len(events):,} portal events, {len(encounters):,} encounters, "
             f"{len(surveys):,} surveys)._\n")

lines.append("## 1. Engagement Score distribution\n")
lines.append("Composite score (0-100) blending recency (40%), 90-day frequency (30%), "
              "distinct active days (20%), and message/lab-view breadth (10%).\n")
lines.append("| Tier | Share of enrolled patients |")
lines.append("|---|---|")
for tier, pct in tier_summary.items():
    lines.append(f"| {tier} | {pct}% |")
lines.append("")

lines.append("## 2. Disengagement-risk (churn) model\n")
lines.append(f"Label: enrolled ≥60 days with **no portal activity in the trailing 60 days** "
             f"(positive rate in eligible population: {y.mean():.1%}, n={len(eligible):,}).\n")
lines.append("| Model | ROC-AUC (holdout) |")
lines.append("|---|---|")
lines.append(f"| Logistic Regression | {logit_auc:.3f} |")
lines.append(f"| Random Forest | {rf_auc:.3f} |")
lines.append("")
lines.append("**Top predictors (Random Forest feature importance):**\n")
for name, val in rf_importance.items():
    lines.append(f"- `{name}`: {val:.3f}")
lines.append("")
lines.append("**Random Forest classification report (holdout, threshold=0.5):**\n")
lines.append("```")
lines.append(report)
lines.append("```")
lines.append("")

lines.append("## 3. Telehealth adoption vs. engagement (Welch's t-test)\n")
lines.append(f"- No telehealth visits: mean engagement = {non_adopters.mean():.1f} (n={len(non_adopters):,})")
lines.append(f"- 1+ telehealth visits: mean engagement = {adopters.mean():.1f} (n={len(adopters):,})")
lines.append(f"- t-statistic = {t_stat:.3f}, p-value = {p_val:.6f}")
higher_group = "telehealth adopters" if adopters.mean() > non_adopters.mean() else "non-adopters"
if p_val < 0.05:
    conclusion = (f"statistically significant (p < 0.05) — {higher_group} show measurably higher "
                  "engagement, a data point in favor of continued telehealth-awareness outreach.")
else:
    conclusion = (f"**not** statistically significant at p < 0.05, and the raw gap points toward "
                  f"{higher_group}. On this dataset, telehealth adoption alone isn't a reliable engagement "
                  "signal — the outreach team should look for a confound (e.g. condition severity, tenure) "
                  "rather than treating telehealth as a lever on its own.")
lines.append(f"- Result: the engagement gap is {conclusion}\n")

lines.append("## 4. Figures\n")
lines.append("- `outputs/figures/roc_curve.png` — churn model discrimination")
lines.append("- `outputs/figures/feature_importance.png` — top churn predictors")
lines.append("- `outputs/figures/telehealth_engagement_ttest.png` — telehealth vs. engagement boxplot")
lines.append("- `outputs/figures/cohort_retention_heatmap.png` — signup-cohort retention curve")

with open(METRICS_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

conn.close()

print("Advanced analytics complete.")
print(f"  Engagement tiers: {dict(tier_summary)}")
print(f"  Logistic AUC={logit_auc:.3f}  RandomForest AUC={rf_auc:.3f}")
print(f"  Telehealth t-test: t={t_stat:.3f} p={p_val:.6f}")
print(f"  Metrics written to: {os.path.abspath(METRICS_PATH)}")
print(f"  Figures written to: {os.path.abspath(FIG_DIR)}")
