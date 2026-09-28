# Loan Analytics Router

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
