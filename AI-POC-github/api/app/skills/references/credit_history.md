# Credit History Table

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
- under_cm_review applications: application.status = 'under_cm_review'
- CM review with more info: status = 'under_cm_review' AND more_info_required_status IS NOT NULL
- credit_declined: decision_status = declined

## Safe listing SQL (no invented name columns)
```sql
SELECT a.application_id, a.loan_id, a.branch_location, a.institute_name,
       a.credit_manager, c.more_info_required_status, c.more_info_required_date
FROM application a
JOIN credit_history c ON a.loan_id = c.loan_id
WHERE a.status = 'under_cm_review'
  AND c.more_info_required_status IS NOT NULL
ORDER BY c.more_info_required_date NULLS LAST
```
