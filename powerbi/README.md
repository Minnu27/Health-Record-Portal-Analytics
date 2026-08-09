# Power BI — Health Record Portal Analytics

This folder documents the Power BI semantic model built on top of the star
schema produced by `sql/schema.sql` / `python/etl_pipeline.py`. A `.pbix`
can't be authored headlessly in this environment (Power BI Desktop is
Windows-only and closed-format), so this folder is the build spec: connect
Power BI Desktop to the CSVs below, wire up the model exactly as described,
paste in the DAX from `dax_measures.txt`, and the dashboards come together
in about 20-30 minutes.

## 1. Data sources

Point **Get Data → Text/CSV** (or a live SQL Server/Postgres connection, if
`sql/schema.sql` has been deployed to a warehouse) at:

| Table | Source file | Role |
|---|---|---|
| `dim_patients` | `data/raw/dim_patients.csv` | Dimension |
| `dim_providers` | `data/raw/dim_providers.csv` | Dimension |
| `dim_departments` | `data/raw/dim_departments.csv` | Dimension |
| `dim_campaigns` | `data/raw/dim_campaigns.csv` | Dimension |
| `fact_encounters` | `data/raw/fact_encounters.csv` | Fact |
| `fact_portal_engagement` | `data/raw/fact_portal_engagement.csv` | Fact |
| `fact_satisfaction_surveys` | `data/raw/fact_satisfaction_surveys.csv` | Fact |
| `fact_campaign_responses` | `data/raw/fact_campaign_responses.csv` | Fact |
| `patient_engagement_scores` | `data/processed/patient_engagement_scores.csv` | Analytics extract (from `python/advanced_analytics.py`) |
| `dim_date` | build in-model — see `powerquery_m_scripts.txt` | Dimension |

Apply the Power Query transforms in `powerquery_m_scripts.txt` on import
(column typing, trimming, and the `dim_date` calendar generator).

## 2. Model relationships (Model view)

Star schema, single-direction filters flowing from dimensions to facts:

```
dim_patients[patient_id]      1 ──< fact_portal_engagement[patient_id]
dim_patients[patient_id]      1 ──< fact_encounters[patient_id]
dim_patients[patient_id]      1 ──< fact_satisfaction_surveys[patient_id]
dim_patients[patient_id]      1 ──< fact_campaign_responses[patient_id]
dim_patients[patient_id]      1 ──< patient_engagement_scores[patient_id]
dim_providers[provider_id]    1 ──< fact_encounters[provider_id]
dim_departments[department_id]1 ──< fact_encounters[department_id]
dim_departments[department_id]1 ──< dim_patients[primary_department_id]
dim_campaigns[campaign_id]    1 ──< fact_campaign_responses[campaign_id]
dim_date[date_key]            1 ──< fact_portal_engagement[event_date]
dim_date[date_key]            1 ──< fact_encounters[encounter_date]
dim_date[date_key]            1 ──< fact_satisfaction_surveys[survey_date]
dim_date[date_key]            1 ──< fact_campaign_responses[response_date]
```

Mark `dim_date` as a **Date table** (Model view → column tools) so
built-in time-intelligence DAX (`TOTALYTD`, `SAMEPERIODLASTYEAR`, etc.)
works against it.

## 3. Report pages

1. **Executive Summary** — KPI cards (Active Patients, Participation Rate,
   NPS, Telehealth Adoption %) + a 12-month trend line, sourced from the
   measures in `dax_measures.txt`. Mirrors `sql/queries/08_executive_summary_view.sql`
   and `dashboards/executive_summary.html`.
2. **Engagement Deep-Dive** — engagement-tier donut (from
   `patient_engagement_scores`), department heatmap, cohort retention matrix.
3. **Operational View** — no-show rate and telehealth adoption by
   department/provider, filterable by region — the view built for hospital
   support/ops leadership.
4. **Outreach & Campaigns** — campaign engagement rate and engagement lift,
   built with the medical outreach team to track their KPI goals against
   actuals (`sql/queries/06_campaign_effectiveness.sql`).

## 4. Row-level security (optional, hospital-realistic)

Add an RLS role `Department Lead` filtering `dim_departments[department_id]
= USERPRINCIPALNAME()`-mapped lookup table, so department leads only see
their own operational view when the report is published to the Service.
