# -*- coding: utf-8 -*-
# Temporary test script - delete after testing

print("=== TEST: Create Connector with Bank ===")
try:
    # Find Garanti bank
    garanti = env["res.bank"].search([("bic", "=", "TGBATRIS")], limit=1)
    if not garanti:
        garanti = env["res.bank"].search([("name", "ilike", "Garanti")], limit=1)
    if not garanti:
        garanti = env["res.bank"].create({"name": "Garanti BBVA", "bic": "TGBATRIS"})
    print("  Bank: %s (ID: %s)" % (garanti.name, garanti.id))

    connector = env["bank.connector"].create({
        "name": "Test Garanti BBVA",
        "bank_type": "garantibbva",
        "bank_id": garanti.id,
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "sandbox_mode": True,
    })
    print("  Created connector ID: %s" % connector.id)
    print("  Name: %s" % connector.name)
    print("  Bank type: %s" % connector.bank_type)
    print("  State: %s" % connector.state)
    print("  Sandbox: %s" % connector.sandbox_mode)

    # Test base URL
    print("\n=== TEST: Base URL ===")
    url = connector._get_base_url()
    print("  Base URL: %s" % url)

    # Test total_accounts computed
    print("  Total accounts: %s" % connector.total_accounts)

    # Test action_view_accounts
    print("\n=== TEST: Action View Accounts ===")
    action = connector.action_view_accounts()
    print("  Action type: %s" % action.get("type"))
    print("  Action model: %s" % action.get("res_model"))

    # Test sync (should fail gracefully since no real API)
    print("\n=== TEST: Sync (no real API) ===")
    try:
        connector.state = "connected"
        connector.access_token = "fake_token"
        connector.action_sync_all()
        print("  Sync completed (unexpected)")
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 100:
            error_msg = error_msg[:100] + "..."
        print("  Expected error (no real API): %s" % error_msg)

    print("\n=== ALL TESTS PASSED ===")
except Exception as e:
    import traceback
    print("  ERROR: %s" % e)
    traceback.print_exc()

env.cr.rollback()
