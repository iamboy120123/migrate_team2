SELECT `customer_id` AS CUSTOMER_ID, upper(name) AS NAME_UPPER, ifnull(country, 'UNKNOWN') AS COUNTRY FROM raw_customer WHERE deleted_flag = 0
