# Governed Metrics Catalog

Use run_metric for these DAX-aligned measures:

1. **Logins (LD)** - distinct applications logged, filter login_date
2. **Loan Amount (LD)** - sum login_amount on login_date
3. **Sanctions (All)** - distinct sanctioned apps, is_sanction=true, sanction_amount>0
4. **Sanction Amount (All)** - sum sanction_amount with same filters
5. **First Disbursed (All)** - distinct apps, disbursement tranche=1
6. **First Disbursed Amount (All)** - sum tranche=1 disbursement amounts
7. **CM Review More Info Required** - apps under CM review with more_info_required_status set
8. **Under CM Review** - apps currently in CM review status

All metrics accept start_date, end_date, and optional group_by (branch_location, product_group).
Snapshot metrics (7–8) ignore the date window and return current pipeline counts — any valid dates are fine (e.g. 2025-01-01 to 2025-08-31).

For "Applications under CM review with more info required", call run_metric name=`CM Review More Info Required` first.
