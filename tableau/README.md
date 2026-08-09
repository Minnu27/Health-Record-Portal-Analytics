# Tableau — Health Record Portal Analytics

Tableau Desktop/Server can't be driven headlessly in this environment to
emit a `.twbx`, so this folder is the build spec plus the exact extracts
to connect to. Point Tableau at the CSVs below (or a live connection to
the SQLite/Postgres warehouse from `sql/schema.sql`), add the calculated
fields in `calculated_fields.txt`, and the workbook comes together
directly from the query library in `sql/queries/`.

## 1. Connect

**Recommended — connect to curated extracts** (fast, matches what
`sql/queries/*.sql` already computed):

- `data/processed/08_executive_summary_view.csv` → Executive Summary dashboard
- `data/processed/01_monthly_active_users.csv`, `02_patient_participation_rate.csv` → engagement trend
- `data/processed/03_engagement_by_department.csv` → department operational view
- `data/processed/04_cohort_retention.csv` → retention heatmap
- `data/processed/05_appointment_noshow_telehealth.csv` → ops KPI tab
- `data/processed/06_campaign_effectiveness.csv` → outreach ROI tab
- `data/processed/07_nps_csat_trends.csv` → patient-experience tab
- `data/processed/patient_engagement_scores.csv` → patient-level detail / engagement-tier filters

**Alternative — connect live to the warehouse** (for a workbook that
recalculates as new data lands): Tableau → Connect → More... → point a
SQLite/ODBC driver (or a deployed Postgres instance running
`sql/schema.sql`) at `data/processed/health_portal.db`, then build each
sheet as a custom SQL data source using the corresponding file in
`sql/queries/`.

## 2. Recommended workbook structure (4 dashboards, 1 story)

| Dashboard | Sheets | Primary audience |
|---|---|---|
| **Executive Summary** | MAU trend, Participation Rate KPI, NPS/CSAT KPI, Telehealth Adoption KPI | Hospital leadership |
| **Engagement Deep-Dive** | Engagement-tier donut, Department heatmap, Cohort retention matrix | Product/portal team |
| **Operational View** | No-show rate by department, Telehealth adoption by department, Provider drill-down | Support / ops leadership |
| **Outreach & Campaigns** | Campaign engagement rate bar, Engagement-lift waterfall | Medical outreach team |

A **Story** ("Two Years of Portal Growth") sequences 4-5 of the above
sheets with captions — useful for the leadership readout this bullet
point describes ("Designed executive summaries... showing active user
engagement and patient participation").

## 3. Key field mapping

- **Date hierarchy**: use `year_month` (string `YYYY-MM`) from the
  processed extracts directly, or build a real Tableau date hierarchy off
  `dim_date.date_key` if connecting live — enables drill Year → Quarter →
  Month for free.
- **Color**: engagement tiers (`patient_engagement_scores.engagement_tier`)
  should use a single consistent 4-step sequential palette
  (Inactive → Low → Medium → High) reused across every dashboard.
- **Filters**: `region`, `department_name`/`primary_department_id`,
  `insurance_type` as global (dashboard-level) filters so leadership can
  slice the same story by hospital region.

## 4. Calculated fields

See `calculated_fields.txt` for the Tableau calculation-editor syntax for
metrics not already pre-aggregated in the SQL extracts (e.g., a
dashboard-side MoM delta, or a LOD expression for participation rate that
still works after a department filter is applied).
