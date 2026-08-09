# Advanced Analytics — Model & Test Results

_Generated as of 2026-08-08 from 2,418 enrolled patients (138,987 portal events, 42,000 encounters, 4,156 surveys)._

## 1. Engagement Score distribution

Composite score (0-100) blending recency (40%), 90-day frequency (30%), distinct active days (20%), and message/lab-view breadth (10%).

| Tier | Share of enrolled patients |
|---|---|
| Inactive | 10.1% |
| Low | 24.6% |
| Medium | 53.4% |
| High | 11.9% |

## 2. Disengagement-risk (churn) model

Label: enrolled ≥60 days with **no portal activity in the trailing 60 days** (positive rate in eligible population: 14.7%, n=2,406).

| Model | ROC-AUC (holdout) |
|---|---|
| Logistic Regression | 0.948 |
| Random Forest | 0.946 |

**Top predictors (Random Forest feature importance):**

- `distinct_active_days_180d`: 0.385
- `events_180d`: 0.329
- `avg_session_sec`: 0.086
- `lab_views`: 0.075
- `messages_180d`: 0.057
- `tenure_days`: 0.020
- `age`: 0.014
- `avg_csat`: 0.012
- `telehealth_visits`: 0.008
- `chronic_condition_flag`: 0.003

**Random Forest classification report (holdout, threshold=0.5):**

```
              precision    recall  f1-score   support

           0       0.98      0.85      0.91       514
           1       0.51      0.91      0.66        88

    accuracy                           0.86       602
   macro avg       0.75      0.88      0.78       602
weighted avg       0.91      0.86      0.87       602

```

## 3. Telehealth adoption vs. engagement (Welch's t-test)

- No telehealth visits: mean engagement = 55.4 (n=326)
- 1+ telehealth visits: mean engagement = 53.7 (n=2,092)
- t-statistic = -1.489, p-value = 0.137261
- Result: the engagement gap is **not** statistically significant at p < 0.05, and the raw gap points toward non-adopters. On this dataset, telehealth adoption alone isn't a reliable engagement signal — the outreach team should look for a confound (e.g. condition severity, tenure) rather than treating telehealth as a lever on its own.

## 4. Figures

- `outputs/figures/roc_curve.png` — churn model discrimination
- `outputs/figures/feature_importance.png` — top churn predictors
- `outputs/figures/telehealth_engagement_ttest.png` — telehealth vs. engagement boxplot
- `outputs/figures/cohort_retention_heatmap.png` — signup-cohort retention curve
