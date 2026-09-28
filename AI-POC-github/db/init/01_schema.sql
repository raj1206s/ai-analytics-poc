CREATE SCHEMA IF NOT EXISTS semantic;

CREATE TABLE IF NOT EXISTS dim_date (
    date DATE PRIMARY KEY,
    year INT NOT NULL,
    quarter INT NOT NULL,
    month INT NOT NULL,
    month_name VARCHAR(16) NOT NULL,
    month_start DATE NOT NULL,
    month_end DATE NOT NULL,
    is_month_end BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS application (
    application_id INT PRIMARY KEY,
    loan_id VARCHAR(50) NOT NULL UNIQUE,
    branch_location VARCHAR(128),
    product_group VARCHAR(128),
    institute_name VARCHAR(512),
    institute_state VARCHAR(128),
    study_country VARCHAR(128),
    stem_case VARCHAR(32),
    sales_executive VARCHAR(256),
    sales_manager VARCHAR(256),
    credit_manager VARCHAR(512),
    login_date TIMESTAMP,
    login_amount DOUBLE PRECISION,
    sanction_date TIMESTAMP,
    sanction_amount DOUBLE PRECISION,
    is_sanction BOOLEAN DEFAULT FALSE,
    first_disbursed_date TIMESTAMP,
    first_disbursed_amount DOUBLE PRECISION,
    credit_declined_date TIMESTAMP,
    customer_declined_date TIMESTAMP,
    status VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_application_login_date ON application(login_date);
CREATE INDEX IF NOT EXISTS idx_application_sanction_date ON application(sanction_date);
CREATE INDEX IF NOT EXISTS idx_application_status ON application(status);
CREATE INDEX IF NOT EXISTS idx_application_loan_id ON application(loan_id);

CREATE TABLE IF NOT EXISTS disbursement (
    loan_id VARCHAR(50) NOT NULL,
    application_id INT NOT NULL,
    tranche INT NOT NULL,
    disbursement_date TIMESTAMP,
    disbursement_amount DOUBLE PRECISION,
    drf_status VARCHAR(64),
    disb_review_date TIMESTAMP,
    first_drf_init_date TIMESTAMP,
    drf_amount DOUBLE PRECISION,
    PRIMARY KEY (loan_id, application_id, tranche),
    FOREIGN KEY (application_id) REFERENCES application(application_id)
);

CREATE INDEX IF NOT EXISTS idx_disbursement_date ON disbursement(disbursement_date);

CREATE TABLE IF NOT EXISTS credit_history (
    loan_id VARCHAR(50) PRIMARY KEY,
    credit_manager VARCHAR(256),
    recommended_date_by_cm TIMESTAMP,
    recommended_by_cm VARCHAR(256),
    regional_credit_manager VARCHAR(256),
    recommended_date_by_g1 TIMESTAMP,
    recommended_by_g1 VARCHAR(256),
    senior_members_of_branch VARCHAR(256),
    recommended_date_by_g2 TIMESTAMP,
    recommended_by_g2 VARCHAR(256),
    area_credit_manager VARCHAR(256),
    recommended_date_by_g3 TIMESTAMP,
    recommended_by_g3 VARCHAR(256),
    hdfc_credila_credit_committee VARCHAR(256),
    recommended_date_by_hccc TIMESTAMP,
    recommended_by_hccc VARCHAR(256),
    more_info_required_by VARCHAR(256),
    more_info_required_date TIMESTAMP,
    more_info_required_status VARCHAR(128),
    more_info_required_count INT,
    decision_status VARCHAR(128),
    decision_date TIMESTAMP,
    decisioned_by VARCHAR(256),
    first_cm_recommended_date TIMESTAMP,
    FOREIGN KEY (loan_id) REFERENCES application(loan_id)
);

-- Populate calendar dimension (2024-01-01 to 2026-12-31)
INSERT INTO dim_date (date, year, quarter, month, month_name, month_start, month_end, is_month_end)
SELECT
    d::date,
    EXTRACT(YEAR FROM d)::int,
    EXTRACT(QUARTER FROM d)::int,
    EXTRACT(MONTH FROM d)::int,
    TO_CHAR(d, 'Mon'),
    DATE_TRUNC('month', d)::date,
    (DATE_TRUNC('month', d) + INTERVAL '1 month - 1 day')::date,
    d = (DATE_TRUNC('month', d) + INTERVAL '1 month - 1 day')::date
FROM generate_series('2024-01-01'::date, '2026-12-31'::date, '1 day') AS d
ON CONFLICT (date) DO NOTHING;
