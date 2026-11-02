SELECT CAST(customer_id AS VARCHAR2(100)) AS CUSTOMER_ID_TEXT, upper(name) AS NAME_UPPER FROM raw_customer WHERE deleted_flag = 0
