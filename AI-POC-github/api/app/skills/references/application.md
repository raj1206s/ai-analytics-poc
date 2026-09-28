# Application Table

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
Identify applications by `loan_id` / `application_id`. Display `institute_name` when a label is needed.

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
