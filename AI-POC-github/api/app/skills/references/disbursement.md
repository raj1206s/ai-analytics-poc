# Disbursement Table

## Grain
One row per (loan_id, application_id, tranche).

## Key rules
- tranche = 1 means first disbursement (First Disbursed metrics)
- disbursement_review status: drf_status = under_review, disbursement_date IS NULL
- Do not double-count application_id across tranches for first disbursed metrics

## Join
disbursement.application_id = application.application_id
disbursement.loan_id = application.loan_id
