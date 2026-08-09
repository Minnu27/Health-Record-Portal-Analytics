# KPI Dictionary

Definitions for every metric surfaced in the SQL query library, the
Tableau/Power BI dashboards, and `dashboards/executive_summary.html`. Each
entry names the owning source so a metric only has one place its logic can
change.

| KPI | Definition | Source of truth |
|---|---|---|
| **Monthly Active Users (MAU)** | Distinct patients with ≥1 portal engagement event in the calendar month | `sql/queries/01_monthly_active_users.sql` |
| **Patient Participation Rate** | Portal-active patients in the month ÷ total patient panel as of that month (not just portal-enrolled — the denominator is every patient in the hospital's care, matching how the outreach team measures reach) | `sql/queries/02_patient_participation_rate.sql` |
| **Engagement Score (0–100)** | Weighted composite: 40% recency (days since last activity), 30% 90-day event frequency, 20% distinct active days (180d), 10% message/lab-view breadth. Min-max normalized across the enrolled population | `python/advanced_analytics.py` |
| **Engagement Tier** | Engagement Score bucketed: Inactive (0–25), Low (25–50), Medium (50–75), High (75–100) | `python/advanced_analytics.py` |
| **Telehealth Adoption %** | Telehealth encounters ÷ (Telehealth + In-Person encounters) | `sql/queries/05_appointment_noshow_telehealth.sql` |
| **No-Show Rate %** | No-show in-person encounters ÷ total in-person encounters (excludes telehealth/lab/message, which can't no-show) | `sql/queries/05_appointment_noshow_telehealth.sql` |
| **NPS (Net Promoter Score)** | 100 × (Promoters [score 9–10] − Detractors [score 0–6]) ÷ total responses | `sql/queries/07_nps_csat_trends.sql` |
| **CSAT** | Mean post-interaction satisfaction score, 1.0–5.0 scale | `sql/queries/07_nps_csat_trends.sql` |
| **Cohort Retention %** | Of patients who signed up for the portal in month 0, the % with ≥1 engagement event N months later | `sql/queries/04_cohort_retention.sql` |
| **Campaign Engagement Rate %** | Patients marked `engaged_flag = true` on an outreach touch ÷ total patients touched by that campaign | `sql/queries/06_campaign_effectiveness.sql` |
| **Campaign Engagement Lift** | A responder's average portal events in the 30 days *after* their campaign response minus their average in the 30 days *before* — the outreach team's read on whether a specific campaign moved behavior, not just recorded a touch | `sql/queries/06_campaign_effectiveness.sql` |
| **Disengagement Risk (churn label)** | Enrolled ≥60 days AND no portal activity in the trailing 60 days, as of the reporting date — the target list the outreach team re-engages | `python/advanced_analytics.py` |

## Design decisions worth calling out

- **Participation rate is deliberately conservative.** Using total patient
  panel (not portal-enrolled count) as the denominator keeps the metric an
  honest "how much of our patient base do we actually reach digitally"
  figure — the number the outreach team's stated engagement goals are
  measured against — instead of a self-flattering enrolled-only rate.
- **NPS trend, not NPS snapshot.** The synthetic satisfaction data is
  generated with a realistic negative-to-improving trend rather than flat
  random noise, so the dashboards show what the metric is actually for:
  tracking whether outreach and portal investment moved the number.
- **Campaign lift, not just campaign reach.** A campaign can touch a lot of
  patients (`campaign_touches`) without changing behavior — lift isolates
  the before/after difference so "we sent 2,000 messages" doesn't get
  mistaken for "we moved engagement."
