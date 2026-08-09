-- =====================================================================
-- 01. Monthly Active Users (MAU) & enrolled-base growth
-- Powers: Tableau "Portal Engagement Trend" line chart, Power BI KPI card
-- =====================================================================
-- Design notes:
--   * Joins fact_portal_engagement to dim_date on the pre-computed
--     year_month column instead of calling strftime()/DATE_TRUNC() on
--     every fact row — keeps the scan sargable and index-friendly.
--   * cumulative_enrolled is computed once via a window function rather
--     than a correlated subquery, so it stays O(n) instead of O(n^2).
-- =====================================================================
WITH monthly_active AS (
    SELECT
        d.year_month,
        COUNT(DISTINCT e.patient_id) AS active_users
    FROM fact_portal_engagement e
    JOIN dim_date d ON d.date_key = e.event_date
    GROUP BY d.year_month
),
enrollment_by_month AS (
    SELECT
        d.year_month,
        COUNT(*) AS new_signups
    FROM dim_patients p
    JOIN dim_date d ON d.date_key = p.portal_signup_date
    WHERE p.portal_enrolled = 1
    GROUP BY d.year_month
),
cumulative AS (
    SELECT
        year_month,
        SUM(new_signups) OVER (ORDER BY year_month
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_enrolled
    FROM enrollment_by_month
)
SELECT
    m.year_month,
    m.active_users,
    c.cumulative_enrolled,
    ROUND(100.0 * m.active_users / NULLIF(c.cumulative_enrolled, 0), 1) AS mau_rate_pct
FROM monthly_active m
LEFT JOIN cumulative c ON c.year_month = m.year_month
ORDER BY m.year_month;
