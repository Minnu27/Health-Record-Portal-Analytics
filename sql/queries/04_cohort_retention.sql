-- =====================================================================
-- 04. Monthly signup-cohort retention curve
-- Powers: Tableau retention heatmap ("month 0..N since signup")
-- =====================================================================
-- Design notes:
--   * cohort_month is computed once per patient (signup month) and reused
--     as the partition key for the retention window, avoiding a
--     self-join between "signup event" and "activity event" tables.
--   * months_since_signup uses the dim_date year_month ordinal distance
--     rather than string manipulation, keeping the comparison numeric
--     and index/plan friendly.
-- =====================================================================
WITH month_index AS (
    SELECT DISTINCT
        year_month,
        (year * 12 + month) AS month_ordinal
    FROM dim_date
),
cohorts AS (
    SELECT
        p.patient_id,
        mi.year_month AS cohort_month,
        mi.month_ordinal AS cohort_ordinal
    FROM dim_patients p
    JOIN dim_date d ON d.date_key = p.portal_signup_date
    JOIN month_index mi ON mi.year_month = d.year_month
    WHERE p.portal_enrolled = 1
),
activity AS (
    SELECT DISTINCT
        e.patient_id,
        mi.month_ordinal AS active_ordinal
    FROM fact_portal_engagement e
    JOIN dim_date d ON d.date_key = e.event_date
    JOIN month_index mi ON mi.year_month = d.year_month
),
cohort_activity AS (
    SELECT
        c.cohort_month,
        (a.active_ordinal - c.cohort_ordinal) AS months_since_signup,
        COUNT(DISTINCT a.patient_id) AS active_patients
    FROM cohorts c
    JOIN activity a ON a.patient_id = c.patient_id AND a.active_ordinal >= c.cohort_ordinal
    GROUP BY c.cohort_month, months_since_signup
),
cohort_size AS (
    SELECT cohort_month, COUNT(*) AS cohort_patients
    FROM cohorts
    GROUP BY cohort_month
)
SELECT
    ca.cohort_month,
    cs.cohort_patients,
    ca.months_since_signup,
    ca.active_patients,
    ROUND(100.0 * ca.active_patients / NULLIF(cs.cohort_patients, 0), 1) AS retention_pct
FROM cohort_activity ca
JOIN cohort_size cs ON cs.cohort_month = ca.cohort_month
WHERE ca.months_since_signup BETWEEN 0 AND 12
ORDER BY ca.cohort_month, ca.months_since_signup;
