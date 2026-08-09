-- =====================================================================
-- 06. Outreach campaign effectiveness (engagement lift)
-- Powers: Tableau "Outreach ROI" view, built with the medical outreach
-- team to show whether a campaign measurably moved portal engagement.
-- =====================================================================
-- Design notes:
--   * "Lift" is measured as each responder's portal-event count in the
--     30 days after their campaign response minus their count in the
--     30 days before — computed with a single correlated aggregate per
--     responder rather than exploding into a row-per-day comparison.
--   * julianday() gives portable day-difference arithmetic in SQLite;
--     the Postgres equivalent is response_date - event_date.
-- =====================================================================
WITH responders AS (
    SELECT
        cr.campaign_id,
        c.campaign_name,
        cr.patient_id,
        cr.response_date,
        cr.engaged_flag
    FROM fact_campaign_responses cr
    JOIN dim_campaigns c ON c.campaign_id = cr.campaign_id
),
pre_activity AS (
    SELECT
        r.campaign_id,
        r.patient_id,
        COUNT(e.event_id) AS events_before
    FROM responders r
    LEFT JOIN fact_portal_engagement e
        ON e.patient_id = r.patient_id
       AND julianday(e.event_date) BETWEEN julianday(r.response_date) - 30 AND julianday(r.response_date) - 1
    GROUP BY r.campaign_id, r.patient_id
),
post_activity AS (
    SELECT
        r.campaign_id,
        r.patient_id,
        COUNT(e.event_id) AS events_after
    FROM responders r
    LEFT JOIN fact_portal_engagement e
        ON e.patient_id = r.patient_id
       AND julianday(e.event_date) BETWEEN julianday(r.response_date) AND julianday(r.response_date) + 30
    GROUP BY r.campaign_id, r.patient_id
)
SELECT
    r.campaign_id,
    r.campaign_name,
    COUNT(DISTINCT r.patient_id) AS patients_reached,
    SUM(CASE WHEN r.engaged_flag = 1 THEN 1 ELSE 0 END) AS patients_engaged,
    ROUND(100.0 * SUM(CASE WHEN r.engaged_flag = 1 THEN 1 ELSE 0 END) / COUNT(DISTINCT r.patient_id), 1)
        AS campaign_engagement_rate_pct,
    ROUND(AVG(pa.events_before), 2) AS avg_events_30d_before,
    ROUND(AVG(po.events_after), 2) AS avg_events_30d_after,
    ROUND(AVG(po.events_after) - AVG(pa.events_before), 2) AS avg_engagement_lift
FROM responders r
JOIN pre_activity pa ON pa.campaign_id = r.campaign_id AND pa.patient_id = r.patient_id
JOIN post_activity po ON po.campaign_id = r.campaign_id AND po.patient_id = r.patient_id
GROUP BY r.campaign_id, r.campaign_name
ORDER BY avg_engagement_lift DESC;
