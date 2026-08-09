-- =====================================================================
-- 05. Appointment no-show rate & telehealth adoption
-- Powers: Tableau "Operational Health" dashboard (ops leadership view)
-- =====================================================================
-- Design notes:
--   * Single pass over fact_encounters with conditional (CASE-based)
--     aggregation computes no-show rate AND telehealth share together —
--     avoids scanning the fact table twice for two related KPIs.
-- =====================================================================
SELECT
    dt.year_month,
    dd.department_name,
    COUNT(*) AS total_encounters,
    SUM(CASE WHEN en.encounter_type = 'In-Person Visit' THEN 1 ELSE 0 END) AS in_person_visits,
    SUM(CASE WHEN en.encounter_type = 'Telehealth' THEN 1 ELSE 0 END) AS telehealth_visits,
    ROUND(100.0 * SUM(CASE WHEN en.encounter_type = 'Telehealth' THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN en.encounter_type IN ('In-Person Visit', 'Telehealth') THEN 1 ELSE 0 END), 0), 1)
          AS telehealth_adoption_pct,
    SUM(CASE WHEN en.status = 'No-Show' THEN 1 ELSE 0 END) AS no_shows,
    ROUND(100.0 * SUM(CASE WHEN en.status = 'No-Show' THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN en.encounter_type = 'In-Person Visit' THEN 1 ELSE 0 END), 0), 1)
          AS no_show_rate_pct
FROM fact_encounters en
JOIN dim_date dt ON dt.date_key = en.encounter_date
JOIN dim_departments dd ON dd.department_id = en.department_id
GROUP BY dt.year_month, dd.department_name
ORDER BY dt.year_month, dd.department_name;
