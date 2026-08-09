-- =====================================================================
-- 07. NPS / CSAT satisfaction trends
-- Powers: Tableau/Power BI "Patient Experience" KPI tile + trend line
-- =====================================================================
-- Design notes:
--   * NPS is computed with the standard promoter/detractor CASE bucketing
--     inline (no separate classification table) — the bucket boundaries
--     (0-6 detractor, 7-8 passive, 9-10 promoter) are the one place they
--     are defined, so a future rule change only touches this file.
--   * LAG() supplies the prior-month score for a MoM delta so the BI
--     layer doesn't need a table calculation for the trend arrow.
-- =====================================================================
WITH monthly_scores AS (
    SELECT
        d.year_month,
        COUNT(*) AS responses,
        SUM(CASE WHEN s.nps_score >= 9 THEN 1 ELSE 0 END) AS promoters,
        SUM(CASE WHEN s.nps_score <= 6 THEN 1 ELSE 0 END) AS detractors,
        ROUND(AVG(s.csat_score), 2) AS avg_csat
    FROM fact_satisfaction_surveys s
    JOIN dim_date d ON d.date_key = s.survey_date
    GROUP BY d.year_month
),
nps_calc AS (
    SELECT
        year_month,
        responses,
        avg_csat,
        ROUND(100.0 * (promoters - detractors) / NULLIF(responses, 0), 1) AS nps_score
    FROM monthly_scores
)
SELECT
    year_month,
    responses,
    nps_score,
    avg_csat,
    ROUND(nps_score - LAG(nps_score) OVER (ORDER BY year_month), 1) AS nps_mom_change,
    ROUND(avg_csat - LAG(avg_csat) OVER (ORDER BY year_month), 2) AS csat_mom_change
FROM nps_calc
ORDER BY year_month;
