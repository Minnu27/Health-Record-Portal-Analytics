-- =====================================================================
-- Health Record Portal Analytics — Data Warehouse Schema
-- Dialect: PostgreSQL (also loads cleanly into SQLite via etl_pipeline.py,
-- minus the native ENUM/date types which are relaxed to TEXT there)
-- =====================================================================
-- Star schema: one fact table per business process (encounters, portal
-- engagement, satisfaction, campaign response), surrounding conformed
-- dimensions (patients, providers, departments, campaigns, date).
-- =====================================================================

DROP TABLE IF EXISTS fact_campaign_responses CASCADE;
DROP TABLE IF EXISTS fact_satisfaction_surveys CASCADE;
DROP TABLE IF EXISTS fact_portal_engagement CASCADE;
DROP TABLE IF EXISTS fact_encounters CASCADE;
DROP TABLE IF EXISTS dim_campaigns CASCADE;
DROP TABLE IF EXISTS dim_providers CASCADE;
DROP TABLE IF EXISTS dim_patients CASCADE;
DROP TABLE IF EXISTS dim_departments CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;

-- ---------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------
CREATE TABLE dim_departments (
    department_id      TEXT PRIMARY KEY,
    department_name    TEXT NOT NULL,
    region_hub          TEXT
);

CREATE TABLE dim_providers (
    provider_id         TEXT PRIMARY KEY,
    provider_name        TEXT NOT NULL,
    department_id        TEXT REFERENCES dim_departments(department_id),
    region                TEXT,
    telehealth_enabled    BOOLEAN
);

CREATE TABLE dim_patients (
    patient_id              TEXT PRIMARY KEY,
    age                      INTEGER,
    gender                    TEXT,
    region                     TEXT,
    insurance_type              TEXT,
    primary_department_id        TEXT REFERENCES dim_departments(department_id),
    chronic_condition_flag        BOOLEAN,
    patient_since                  DATE,
    portal_enrolled                  BOOLEAN,
    portal_signup_date                DATE,
    preferred_device                    TEXT
);

CREATE TABLE dim_campaigns (
    campaign_id             TEXT PRIMARY KEY,
    campaign_name             TEXT NOT NULL,
    start_date                  DATE,
    end_date                     DATE,
    target_segment                 TEXT,
    target_department_id             TEXT REFERENCES dim_departments(department_id),
    channel                            TEXT
);

-- Standard date-spine dimension, generated once and reused by every fact
-- via a surrogate DATE join key — keeps Tableau/Power BI time intelligence
-- (YoY, rolling averages, fiscal calendars) off of raw fact date columns.
CREATE TABLE dim_date (
    date_key        DATE PRIMARY KEY,
    year             INTEGER,
    month             INTEGER,
    month_name         TEXT,
    year_month           TEXT,   -- 'YYYY-MM' for easy grouping
    quarter                TEXT,
    day_of_week              TEXT,
    is_weekend                 BOOLEAN
);

-- ---------------------------------------------------------------------
-- Facts
-- ---------------------------------------------------------------------
CREATE TABLE fact_encounters (
    encounter_id     TEXT PRIMARY KEY,
    patient_id        TEXT REFERENCES dim_patients(patient_id),
    provider_id        TEXT REFERENCES dim_providers(provider_id),
    department_id        TEXT REFERENCES dim_departments(department_id),
    encounter_date          DATE REFERENCES dim_date(date_key),
    encounter_type            TEXT,   -- In-Person Visit / Telehealth / Lab Work / Portal Message
    status                       TEXT    -- Completed / No-Show / Cancelled
);

CREATE TABLE fact_portal_engagement (
    event_id             TEXT PRIMARY KEY,
    patient_id             TEXT REFERENCES dim_patients(patient_id),
    event_date               DATE REFERENCES dim_date(date_key),
    event_type                 TEXT,   -- login / message_sent / appointment_scheduled / ...
    session_duration_sec         INTEGER,
    device_type                    TEXT
);

CREATE TABLE fact_satisfaction_surveys (
    survey_id         TEXT PRIMARY KEY,
    patient_id          TEXT REFERENCES dim_patients(patient_id),
    survey_date            DATE REFERENCES dim_date(date_key),
    nps_score                 SMALLINT,   -- 0-10
    csat_score                   NUMERIC(2,1)  -- 1.0-5.0
);

CREATE TABLE fact_campaign_responses (
    response_id        TEXT PRIMARY KEY,
    campaign_id           TEXT REFERENCES dim_campaigns(campaign_id),
    patient_id              TEXT REFERENCES dim_patients(patient_id),
    response_date              DATE REFERENCES dim_date(date_key),
    engaged_flag                  BOOLEAN
);

-- ---------------------------------------------------------------------
-- Indexes — tuned for the access patterns the Tableau/Power BI extracts
-- and executive dashboards use most (date-range scans + patient/department
-- rollups). Kept narrow and purposeful rather than indexing every column.
-- ---------------------------------------------------------------------
CREATE INDEX idx_engagement_patient_date  ON fact_portal_engagement (patient_id, event_date);
CREATE INDEX idx_engagement_date_type     ON fact_portal_engagement (event_date, event_type);
CREATE INDEX idx_encounters_patient_date  ON fact_encounters (patient_id, encounter_date);
CREATE INDEX idx_encounters_dept_date     ON fact_encounters (department_id, encounter_date);
CREATE INDEX idx_surveys_date             ON fact_satisfaction_surveys (survey_date);
CREATE INDEX idx_campaign_resp_campaign   ON fact_campaign_responses (campaign_id);
CREATE INDEX idx_patients_enrolled        ON dim_patients (portal_enrolled, portal_signup_date);
