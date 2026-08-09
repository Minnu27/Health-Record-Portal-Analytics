-- =====================================================================
-- 08. Executive summary — one row per month, all headline KPIs
-- Powers: the Tableau/Power BI Executive Summary dashboard tab, and
-- dashboards/executive_summary.html. This is the query the "Designed
-- executive summaries and operational views" bullet refers to.
-- =====================================================================
-- Design notes:
--   * Every metric is pre-aggregated to (year_month) grain in its own CTE
--     first, then joined on that single narrow key — cheaper than joining
--     the wide fact tables together directly, and each CTE independently
--     matches the indexes on (event_date)/(encounter_date)/(survey_date).
--   * COALESCE guards months with no campaign activity / no surveys so
--     the view stays gap-free for a continuous BI time series.
-- =====================================================================
WITH months AS (
    SELECT DISTINCT year_month FROM dim_date WHERE date_key <= '2026-08-08'
),
mau AS (
    SELECT d.year_month, COUNT(DISTINCT e.patient_id) AS active_users
    FROM fact_portal_engagement e
    JOIN dim_date d ON d.date_key = e.event_date
    GROUP BY d.year_month
),
sessions AS (
    SELECT d.year_month,
           COUNT(*) AS total_events,
           ROUND(AVG(e.session_duration_sec), 0) AS avg_session_sec
    FROM fact_portal_engagement e
    JOIN dim_date d ON d.date_key = e.event_date
    GROUP BY d.year_month
),
ops AS (
    SELECT d.year_month,
           SUM(CASE WHEN en.status = 'No-Show' THEN 1 ELSE 0 END) AS no_shows,
           SUM(CASE WHEN en.encounter_type = 'In-Person Visit' THEN 1 ELSE 0 END) AS in_person,
           SUM(CASE WHEN en.encounter_type = 'Telehealth' THEN 1 ELSE 0 END) AS telehealth
    FROM fact_encounters en
    JOIN dim_date d ON d.date_key = en.encounter_date
    GROUP BY d.year_month
),
satisfaction AS (
    SELECT d.year_month,
           SUM(CASE WHEN s.nps_score >= 9 THEN 1 ELSE 0 END) AS promoters,
           SUM(CASE WHEN s.nps_score <= 6 THEN 1 ELSE 0 END) AS detractors,
           COUNT(*) AS responses,
           ROUND(AVG(s.csat_score), 2) AS avg_csat
    FROM fact_satisfaction_surveys s
    JOIN dim_date d ON d.date_key = s.survey_date
    GROUP BY d.year_month
),
campaigns AS (
    SELECT d.year_month,
           COUNT(*) AS campaign_touches,
           SUM(CASE WHEN cr.engaged_flag = 1 THEN 1 ELSE 0 END) AS campaign_engaged
    FROM fact_campaign_responses cr
    JOIN dim_date d ON d.date_key = cr.response_date
    GROUP BY d.year_month
)
SELECT
    m.year_month,
    COALESCE(mau.active_users, 0) AS active_users,
    COALESCE(sessions.total_events, 0) AS portal_events,
    sessions.avg_session_sec,
    COALESCE(ops.telehealth, 0) AS telehealth_visits,
    ROUND(100.0 * COALESCE(ops.telehealth, 0) / NULLIF(ops.telehealth + ops.in_person, 0), 1) AS telehealth_adoption_pct,
    ROUND(100.0 * COALESCE(ops.no_shows, 0) / NULLIF(ops.in_person, 0), 1) AS no_show_rate_pct,
    ROUND(100.0 * (COALESCE(satisfaction.promoters, 0) - COALESCE(satisfaction.detractors, 0))
          / NULLIF(satisfaction.responses, 0), 1) AS nps_score,
    satisfaction.avg_csat,
    COALESCE(campaigns.campaign_touches, 0) AS campaign_touches,
    COALESCE(campaigns.campaign_engaged, 0) AS campaign_engaged
FROM months m
LEFT JOIN mau ON mau.year_month = m.year_month
LEFT JOIN sessions ON sessions.year_month = m.year_month
LEFT JOIN ops ON ops.year_month = m.year_month
LEFT JOIN satisfaction ON satisfaction.year_month = m.year_month
LEFT JOIN campaigns ON campaigns.year_month = m.year_month
ORDER BY m.year_month;
