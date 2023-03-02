-- disable bml payment provider
UPDATE payment_provider
   SET bml_merchant_id = NULL,
       bml_passcode = NULL,
       bml_acquirer_id = NULL,
       bml_live_url = NULL,
       bml_test_url = NULL;
