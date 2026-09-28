CREATE TABLE IF NOT EXISTS semantic.metric (
    metric_id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    alias VARCHAR(256),
    description TEXT,
    dax_source TEXT,
    sql_template TEXT NOT NULL,
    grain VARCHAR(128),
    time_axis VARCHAR(64),
    filters_json JSONB DEFAULT '{}',
    owner VARCHAR(128) DEFAULT 'analytics',
    version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS semantic.metric_dimension (
    metric_id INT REFERENCES semantic.metric(metric_id),
    dim_name VARCHAR(64) NOT NULL,
    column_expr VARCHAR(128) NOT NULL,
    description TEXT,
    PRIMARY KEY (metric_id, dim_name)
);

CREATE TABLE IF NOT EXISTS semantic.domain_doc (
    domain VARCHAR(64) PRIMARY KEY,
    markdown TEXT NOT NULL
);

INSERT INTO semantic.metric (name, alias, description, dax_source, sql_template, grain, time_axis, filters_json) VALUES
(
    'Logins (LD)',
    'logins_ld',
    'Distinct count of applications with a login date in the selected period.',
    'CALCULATE(DISTINCTCOUNT(dim_application[application_id]),FILTER(dim_application,NOT(ISBLANK(dim_application[login_date]))))',
    $sql$
SELECT COUNT(DISTINCT a.application_id) AS value
FROM application a
WHERE a.login_date IS NOT NULL
  AND a.login_date::date >= %(start_date)s::date
  AND a.login_date::date <= %(end_date)s::date
  {{GROUP_BY}}
$sql$,
    'application_id',
    'login_date',
    '{"login_date_not_null": true}'
),
(
    'Loan Amount (LD)',
    'loan_amount_ld',
    'Sum of login amounts for applications logged in the selected period.',
    'CALCULATE(SUM(dim_application[login_amount]),USERELATIONSHIP(dim_application[login_date],''fact_metrics''[Date]),NOT(ISBLANK(dim_application[login_date])))+0',
    $sql$
SELECT COALESCE(SUM(a.login_amount), 0) AS value
FROM application a
WHERE a.login_date IS NOT NULL
  AND a.login_date::date >= %(start_date)s::date
  AND a.login_date::date <= %(end_date)s::date
  {{GROUP_BY}}
$sql$,
    'sum_amount',
    'login_date',
    '{"login_date_not_null": true}'
),
(
    'Sanctions (All)',
    'sanctions_all',
    'Distinct sanctioned applications in the selected period.',
    'CALCULATE(DISTINCTCOUNT(dim_application[application_id]),USERELATIONSHIP(''fact_metrics''[Date],dim_application[sanction_date]),dim_application[sanction_amount]>0,NOT(ISBLANK(dim_application[sanction_date])),dim_application[Is_Sanction]=1)+0',
    $sql$
SELECT COUNT(DISTINCT a.application_id) AS value
FROM application a
WHERE a.sanction_amount > 0
  AND a.sanction_date IS NOT NULL
  AND a.is_sanction = TRUE
  AND a.sanction_date::date >= %(start_date)s::date
  AND a.sanction_date::date <= %(end_date)s::date
  {{GROUP_BY}}
$sql$,
    'application_id',
    'sanction_date',
    '{"sanction_amount_gt_zero": true, "is_sanction": true}'
),
(
    'Sanction Amount (All)',
    'sanction_amount_all',
    'Sum of sanction amounts in the selected period.',
    'CALCULATE(SUM(dim_application[sanction_amount]),USERELATIONSHIP(dim_application[sanction_date],''fact_metrics''[Date]),NOT(ISBLANK(dim_application[sanction_date])), dim_application[Is_Sanction]=1)+0',
    $sql$
SELECT COALESCE(SUM(a.sanction_amount), 0) AS value
FROM application a
WHERE a.sanction_amount > 0
  AND a.sanction_date IS NOT NULL
  AND a.is_sanction = TRUE
  AND a.sanction_date::date >= %(start_date)s::date
  AND a.sanction_date::date <= %(end_date)s::date
  {{GROUP_BY}}
$sql$,
    'sum_amount',
    'sanction_date',
    '{"sanction_amount_gt_zero": true, "is_sanction": true}'
),
(
    'First Disbursed (All)',
    'first_disbursed_all',
    'Distinct applications with first tranche disbursement in the selected period.',
    'CALCULATE(DISTINCTCOUNT(dim_disbursement[application_id]),USERELATIONSHIP(''fact_metrics''[Date],dim_disbursement[disbursement_date]),dim_disbursement[disbursement_amount]>0,dim_disbursement[tranche]=1,NOT(ISBLANK(dim_disbursement[disbursement_date])))+0',
    $sql$
SELECT COUNT(DISTINCT d.application_id) AS value
FROM disbursement d
WHERE d.disbursement_amount > 0
  AND d.tranche = 1
  AND d.disbursement_date IS NOT NULL
  AND d.disbursement_date::date >= %(start_date)s::date
  AND d.disbursement_date::date <= %(end_date)s::date
  {{GROUP_BY}}
$sql$,
    'application_id',
    'disbursement_date',
    '{"tranche": 1, "disbursement_amount_gt_zero": true}'
),
(
    'First Disbursed Amount (All)',
    'first_disbursed_amount_all',
    'Sum of first tranche disbursement amounts in the selected period.',
    'CALCULATE(SUM(dim_disbursement[disbursement_amount]),USERELATIONSHIP(dim_disbursement[disbursement_date],''fact_metrics''[Date]),dim_disbursement[disbursement_amount]>0,dim_disbursement[tranche]=1,NOT(ISBLANK(dim_disbursement[disbursement_date]))+0)+0',
    $sql$
SELECT COALESCE(SUM(d.disbursement_amount), 0) AS value
FROM disbursement d
WHERE d.disbursement_amount > 0
  AND d.tranche = 1
  AND d.disbursement_date IS NOT NULL
  AND d.disbursement_date::date >= %(start_date)s::date
  AND d.disbursement_date::date <= %(end_date)s::date
  {{GROUP_BY}}
$sql$,
    'sum_amount',
    'disbursement_date',
    '{"tranche": 1, "disbursement_amount_gt_zero": true}'
),
(
    'CM Review More Info Required',
    'cm_review_more_info_required',
    'Count of applications currently under CM review where additional information has been requested.',
    'N/A - pipeline snapshot metric',
    $sql$
SELECT COUNT(*) AS value
FROM application a
JOIN credit_history c ON a.loan_id = c.loan_id
WHERE a.status = 'under_cm_review'
  AND c.more_info_required_status IS NOT NULL
  {{GROUP_BY}}
$sql$,
    'application_id',
    'snapshot',
    '{"status": "under_cm_review", "more_info_required": true}'
),
(
    'Under CM Review',
    'under_cm_review',
    'Count of applications currently in CM review (decision pending).',
    'N/A - pipeline snapshot metric',
    $sql$
SELECT COUNT(*) AS value
FROM application a
WHERE a.status = 'under_cm_review'
  {{GROUP_BY}}
$sql$,
    'application_id',
    'snapshot',
    '{"status": "under_cm_review"}'
);

INSERT INTO semantic.metric_dimension (metric_id, dim_name, column_expr, description) VALUES
(1, 'branch_location', 'a.branch_location', 'Branch location'),
(1, 'product_group', 'a.product_group', 'Product group'),
(2, 'branch_location', 'a.branch_location', 'Branch location'),
(2, 'product_group', 'a.product_group', 'Product group'),
(3, 'branch_location', 'a.branch_location', 'Branch location'),
(3, 'product_group', 'a.product_group', 'Product group'),
(4, 'branch_location', 'a.branch_location', 'Branch location'),
(4, 'product_group', 'a.product_group', 'Product group'),
(5, 'branch_location', 'a.branch_location', 'Branch location via join'),
(5, 'product_group', 'a.product_group', 'Product group via join'),
(6, 'branch_location', 'a.branch_location', 'Branch location via join'),
(6, 'product_group', 'a.product_group', 'Product group via join'),
(7, 'branch_location', 'a.branch_location', 'Branch location'),
(7, 'product_group', 'a.product_group', 'Product group'),
(8, 'branch_location', 'a.branch_location', 'Branch location'),
(8, 'product_group', 'a.product_group', 'Product group');
