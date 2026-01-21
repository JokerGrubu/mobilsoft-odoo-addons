-- disable paytr payment provider
UPDATE payment_provider
   SET paytr_merchant_key = NULL,
       paytr_merchant_salt = NULL;
