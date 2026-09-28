-- Seed ~300 applications across 7 status paths (2024-06 to 2025-08)

DO $$
DECLARE
    i INT;
    v_status TEXT;
    v_login_date TIMESTAMP;
    v_loan_id TEXT;
    v_branch TEXT;
    v_product TEXT;
    v_amount DOUBLE PRECISION;
    branches TEXT[] := ARRAY['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Hyderabad', 'Pune'];
    products TEXT[] := ARRAY['Education Loan', 'Study Abroad', 'Domestic PG'];
BEGIN
    FOR i IN 1..300 LOOP
        v_loan_id := 'LN' || LPAD(i::text, 6, '0');
        v_branch := branches[1 + (i % array_length(branches, 1))];
        v_product := products[1 + (i % array_length(products, 1))];
        v_login_date := TIMESTAMP '2024-06-01' + ((i * 3) % 450) * INTERVAL '1 day' + (i % 24) * INTERVAL '1 hour';
        v_amount := 500000 + (i % 50) * 25000;

        -- Status distribution per plan
        IF i % 100 < 25 THEN
            v_status := 'logged';
            INSERT INTO application (
                application_id, loan_id, branch_location, product_group, institute_name,
                institute_state, study_country, stem_case, sales_executive, sales_manager,
                login_date, login_amount, status
            ) VALUES (
                i, v_loan_id, v_branch, v_product, 'Institute ' || (i % 20),
                'Maharashtra', CASE WHEN i % 3 = 0 THEN 'USA' ELSE 'India' END,
                CASE WHEN i % 4 = 0 THEN 'Yes' ELSE 'No' END,
                'SE_' || (i % 10), 'SM_' || (i % 5),
                v_login_date, v_amount, v_status
            );

        ELSIF i % 100 < 40 THEN
            v_status := 'under_cm_review';
            INSERT INTO application (
                application_id, loan_id, branch_location, product_group, institute_name,
                login_date, login_amount, status, credit_manager
            ) VALUES (
                i, v_loan_id, v_branch, v_product, 'Institute ' || (i % 20),
                v_login_date, v_amount, v_status, 'CM_' || (i % 8)
            );
            INSERT INTO credit_history (
                loan_id, credit_manager, recommended_date_by_cm, recommended_by_cm,
                first_cm_recommended_date, more_info_required_status, more_info_required_count,
                decision_status
            ) VALUES (
                v_loan_id, 'CM_' || (i % 8),
                v_login_date + INTERVAL '5 days', 'CM_' || (i % 8),
                v_login_date + INTERVAL '5 days',
                CASE WHEN i % 3 = 0 THEN 'pending' ELSE NULL END,
                CASE WHEN i % 3 = 0 THEN 1 ELSE 0 END,
                NULL
            );

        ELSIF i % 100 < 50 THEN
            v_status := 'credit_declined';
            INSERT INTO application (
                application_id, loan_id, branch_location, product_group,
                login_date, login_amount, credit_declined_date, status, credit_manager
            ) VALUES (
                i, v_loan_id, v_branch, v_product,
                v_login_date, v_amount,
                v_login_date + INTERVAL '12 days', v_status, 'CM_' || (i % 8)
            );
            INSERT INTO credit_history (
                loan_id, credit_manager, recommended_date_by_cm, recommended_by_cm,
                decision_status, decision_date, decisioned_by, first_cm_recommended_date
            ) VALUES (
                v_loan_id, 'CM_' || (i % 8),
                v_login_date + INTERVAL '5 days', 'CM_' || (i % 8),
                'declined', v_login_date + INTERVAL '12 days', 'CM_' || (i % 8),
                v_login_date + INTERVAL '5 days'
            );

        ELSIF i % 100 < 60 THEN
            v_status := 'customer_declined';
            INSERT INTO application (
                application_id, loan_id, branch_location, product_group,
                login_date, login_amount, sanction_date, sanction_amount, is_sanction,
                customer_declined_date, status
            ) VALUES (
                i, v_loan_id, v_branch, v_product,
                v_login_date, v_amount,
                v_login_date + INTERVAL '15 days', v_amount * 0.9, TRUE,
                v_login_date + INTERVAL '20 days', v_status
            );

        ELSIF i % 100 < 80 THEN
            v_status := 'sanctioned';
            INSERT INTO application (
                application_id, loan_id, branch_location, product_group,
                login_date, login_amount, sanction_date, sanction_amount, is_sanction, status, credit_manager
            ) VALUES (
                i, v_loan_id, v_branch, v_product,
                v_login_date, v_amount,
                v_login_date + INTERVAL '15 days', v_amount * 0.95, TRUE, v_status, 'CM_' || (i % 8)
            );
            INSERT INTO credit_history (
                loan_id, credit_manager, recommended_date_by_cm, recommended_by_cm,
                recommended_date_by_g1, recommended_by_g1,
                decision_status, decision_date, decisioned_by, first_cm_recommended_date
            ) VALUES (
                v_loan_id, 'CM_' || (i % 8),
                v_login_date + INTERVAL '5 days', 'CM_' || (i % 8),
                v_login_date + INTERVAL '10 days', 'G1_' || (i % 4),
                'approved', v_login_date + INTERVAL '15 days', 'G1_' || (i % 4),
                v_login_date + INTERVAL '5 days'
            );

        ELSIF i % 100 < 90 THEN
            v_status := 'disbursement_review';
            INSERT INTO application (
                application_id, loan_id, branch_location, product_group,
                login_date, login_amount, sanction_date, sanction_amount, is_sanction, status
            ) VALUES (
                i, v_loan_id, v_branch, v_product,
                v_login_date, v_amount,
                v_login_date + INTERVAL '15 days', v_amount * 0.95, TRUE, v_status
            );
            INSERT INTO disbursement (
                loan_id, application_id, tranche, drf_status, disb_review_date,
                first_drf_init_date, drf_amount, disbursement_amount
            ) VALUES (
                v_loan_id, i, 1, 'under_review',
                v_login_date + INTERVAL '25 days',
                v_login_date + INTERVAL '22 days',
                v_amount * 0.5, NULL
            );

        ELSE
            v_status := 'first_disbursed';
            INSERT INTO application (
                application_id, loan_id, branch_location, product_group,
                login_date, login_amount, sanction_date, sanction_amount, is_sanction,
                first_disbursed_date, first_disbursed_amount, status
            ) VALUES (
                i, v_loan_id, v_branch, v_product,
                v_login_date, v_amount,
                v_login_date + INTERVAL '15 days', v_amount * 0.95, TRUE,
                v_login_date + INTERVAL '30 days', v_amount * 0.5, v_status
            );
            INSERT INTO disbursement (
                loan_id, application_id, tranche, disbursement_date, disbursement_amount, drf_status
            ) VALUES (
                v_loan_id, i, 1,
                v_login_date + INTERVAL '30 days', v_amount * 0.5, 'disbursed'
            );
            IF i % 2 = 0 THEN
                INSERT INTO disbursement (
                    loan_id, application_id, tranche, disbursement_date, disbursement_amount, drf_status
                ) VALUES (
                    v_loan_id, i, 2,
                    v_login_date + INTERVAL '60 days', v_amount * 0.3, 'disbursed'
                );
            END IF;
        END IF;
    END LOOP;
END $$;
