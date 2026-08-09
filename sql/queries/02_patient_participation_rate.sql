-- =====================================================================
-- 02. Patient participation rate (portal-active vs. total patient panel)
-- Powers: Tableau/Power BI executive summary KPI — "Patient Participation"
-- =====================================================================
-- Design notes:
--   * Pre-aggregates active patients per month once (engaged_patients CTE)
--     instead of re-scanning fact_portal_engagement per department in the
--     outer query — the department breakdown reuses the same CTE result.
--   * Uses CASE-based conditional aggregation instead of separate FILTERed
--     subqueries so the whole rollup is a single pass per group.
-- =====================================================================
WITH engaged_patients AS (
    SELECT DISTINCT
        d.year_month,
        e.patient_id
    FROM fact_portal_engagement e
    JOIN dim_date d ON d.date_key = e.event_date
),
month_spine AS (
    -- One row per calendar month (not per day) so the panel-size join
    -- below stays small (~months x patients) instead of days x patients.
    SELECT DISTINCT year_month, MAX(date_key) AS month_end
    FROM dim_date
    GROUP BY year_month
),
panel_by_month AS (
    -- Total patients "in panel" (existing as a patient) as of each month,
    -- regardless of portal enrollment — the denominator for participation.
    SELECT
        ms.year_month,
        COUNT(DISTINCT p.patient_id) AS panel_size
    FROM month_spine ms
    JOIN dim_patients p ON p.patient_since <= ms.month_end
    GROUP BY ms.year_month
)
SELECT
    pm.year_month,
    pm.panel_size,
    COUNT(DISTINCT ep.patient_id) AS participating_patients,
    ROUND(100.0 * COUNT(DISTINCT ep.patient_id) / NULLIF(pm.panel_size, 0), 1) AS participation_rate_pct,
    SUM(CASE WHEN pt.chronic_condition_flag = 1 THEN 1 ELSE 0 END) AS chronic_participants
FROM panel_by_month pm
LEFT JOIN engaged_patients ep ON ep.year_month = pm.year_month
LEFT JOIN dim_patients pt ON pt.patient_id = ep.patient_id
GROUP BY pm.year_month, pm.panel_size
ORDER BY pm.year_month;
