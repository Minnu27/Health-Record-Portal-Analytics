-- =====================================================================
-- 03. Engagement intensity by department
-- Powers: Tableau "Department Operational View" bar/heatmap
-- =====================================================================
-- Design notes:
--   * Engagement events carry no department key directly (they belong to
--     the portal, not a visit), so department is attributed via the
--     patient's primary_department_id — attribution is resolved once in
--     the join rather than recomputed per metric.
--   * RANK() lets Tableau/Power BI highlight the top department per month
--     without a table calc on the BI side.
-- =====================================================================
WITH dept_month AS (
    SELECT
        dd.department_name,
        dt.year_month,
        COUNT(*) AS total_events,
        COUNT(DISTINCT e.patient_id) AS active_patients,
        ROUND(AVG(e.session_duration_sec), 0) AS avg_session_sec
    FROM fact_portal_engagement e
    JOIN dim_patients p ON p.patient_id = e.patient_id
    JOIN dim_departments dd ON dd.department_id = p.primary_department_id
    JOIN dim_date dt ON dt.date_key = e.event_date
    GROUP BY dd.department_name, dt.year_month
)
SELECT
    department_name,
    year_month,
    total_events,
    active_patients,
    avg_session_sec,
    RANK() OVER (PARTITION BY year_month ORDER BY total_events DESC) AS engagement_rank_in_month
FROM dept_month
ORDER BY year_month, engagement_rank_in_month;
