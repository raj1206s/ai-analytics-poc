-- Domain docs seeded from skills (also available as files in api/app/skills/)
-- Runtime prefers on-disk skills via get_domain_doc; this seed keeps DB in sync for fresh installs.

INSERT INTO semantic.domain_doc (domain, markdown) VALUES
('loan_analytics', '# Loan Analytics Router

Always try governed semantic metrics FIRST before writing raw SQL.

## Workflow
1. Clarify time period (default timezone: Asia/Kolkata, calendar months)
2. Search metrics via list_metrics
3. If metric matches, use run_metric with start_date and end_date
4. If no metric, load domain docs (application, credit_history, disbursement)
5. Write read-only SQL with proper joins and filters — only real columns from describe_table / domain docs
6. End every answer with provenance footer

## Date conventions
- "Last month" = previous complete calendar month in IST
- "MTD" = month-to-date through latest data
- Login, sanction, and disbursement use DIFFERENT date columns

## Status values on application.status
- logged, under_cm_review, credit_declined, customer_declined, sanctioned, disbursement_review, first_disbursed

## Pipeline shortcuts
- CM review / more info required → metric **CM Review More Info Required** (or **Under CM Review**)
- Never invent columns like applicant_name; use loan_id / application_id / institute_name

## PII
Do not expose student email, mobile, PAN, passport in responses.
'),
('application', '# Application Table

## Grain
One row per application_id.

## Join keys
- loan_id -> credit_history.loan_id
- application_id -> disbursement.application_id

## Columns (use ONLY these — do not invent names)
application_id, loan_id, branch_location, product_group, institute_name,
institute_state, study_country, stem_case, sales_executive, sales_manager,
credit_manager, login_date, login_amount, sanction_date, sanction_amount,
is_sanction, first_disbursed_date, first_disbursed_amount, credit_declined_date,
customer_declined_date, status, created_at

**There is NO applicant_name, customer_name, or student_name column.**
Identify applications by loan_id / application_id. Display institute_name when a label is needed.

## Status and date columns
| status | filter date column |
|--------|-------------------|
| logged | login_date |
| under_cm_review | login_date + credit_history |
| credit_declined | credit_declined_date |
| customer_declined | customer_declined_date |
| sanctioned | sanction_date |
| disbursement_review | sanction_date + disbursement review |
| first_disbursed | first_disbursed_date or disbursement tranche=1 |

## Gotchas
- is_sanction must be true for sanction metrics
- login_date, sanction_date, disbursement_date are different time axes
- Do not count credit_declined as sanctions
- Always call describe_table("application") before writing listing SQL if unsure of columns
'),
('credit_history', '# Credit History Table

## Grain
One row per loan_id (PK).

## Join
application.loan_id = credit_history.loan_id

## Key columns
- first_cm_recommended_date: first CM recommendation
- recommended_date_by_cm/g1/g2/g3: approval chain dates
- decision_status: approved, declined, more_info_required, or NULL if pending
- more_info_required_status: set when additional info requested
- more_info_required_date, more_info_required_by, more_info_required_count

## Usage
- Prefer governed metrics: **CM Review More Info Required**, **Under CM Review**
- under_cm_review applications: application.status = ''under_cm_review''
- CM review with more info: status = ''under_cm_review'' AND more_info_required_status IS NOT NULL
- credit_declined: decision_status = declined

## Safe listing SQL (no invented name columns)
SELECT a.application_id, a.loan_id, a.branch_location, a.institute_name,
       a.credit_manager, c.more_info_required_status, c.more_info_required_date
FROM application a
JOIN credit_history c ON a.loan_id = c.loan_id
WHERE a.status = ''under_cm_review''
  AND c.more_info_required_status IS NOT NULL
ORDER BY c.more_info_required_date NULLS LAST
'),
('disbursement', '# Disbursement Table

## Grain
One row per (loan_id, application_id, tranche).

## Key rules
- tranche = 1 means first disbursement (First Disbursed metrics)
- disbursement_review status: drf_status = under_review, disbursement_date IS NULL
- Do not double-count application_id across tranches for first disbursed metrics

## Join
disbursement.application_id = application.application_id
disbursement.loan_id = application.loan_id
'),
('metrics', '# Governed Metrics Catalog

Use run_metric for these DAX-aligned measures:

1. Logins (LD) - distinct applications logged, filter login_date
2. Loan Amount (LD) - sum login_amount on login_date
3. Sanctions (All) - distinct sanctioned apps, is_sanction=true, sanction_amount>0
4. Sanction Amount (All) - sum sanction_amount with same filters
5. First Disbursed (All) - distinct apps, disbursement tranche=1
6. First Disbursed Amount (All) - sum tranche=1 disbursement amounts
7. CM Review More Info Required - apps under CM review with more_info_required_status set
8. Under CM Review - apps currently in CM review status

All metrics accept start_date, end_date, and optional group_by (branch_location, product_group).
Snapshot metrics (7-8) ignore the date window and return current pipeline counts — any valid dates are fine.

For "Applications under CM review with more info required", call run_metric name=`CM Review More Info Required` first.
')
ON CONFLICT (domain) DO UPDATE SET markdown = EXCLUDED.markdown;
