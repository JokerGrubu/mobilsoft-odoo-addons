# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft Banka Entegrasyonu',
    "version": "19.0.1.0.0",
    "category": "Accounting/Banking",
    "summary": "Turkish Banks Open Banking API Integration (Garanti BBVA, Ziraat, QNB, İş Bankası)",
    "description": """
Turkish Banks Open Banking Integration
========================================

Comprehensive banking integration for Turkish banks with Open Banking APIs.

Features:
---------
* **Garanti BBVA API** - Full integration with OAuth 2.0
* **Ziraat Bank API** - Corporate and retail accounts
* **Multi-Currency Support** - Auto exchange rate updates
* **Transaction Sync** - Automated transaction fetching
* **Account Management** - Real-time balance and account info
* **Payment Initiation** - Domestic and international transfers
* **Webhook Support** - Real-time payment notifications
* **Security** - Encrypted credentials, KVKK/GDPR compliant

Supported Banks:
----------------
* Garanti BBVA ✅ (Priority)
* Ziraat Bankası ✅ (Priority)
* QNB Finansbank ⏳ (Planned)
* İş Bankası ⏳ (Planned)
* TEB, Denizbank, Halk ⏳ (Future)

Technical Stack:
----------------
* OAuth 2.0 Authentication
* REST API Integration
* Automated Cron Jobs
* Multi-company Support
* Test Data / Sandbox Mode
    """,
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'license': 'LGPL-3',
    "depends": [
        "base",
        "account",
        "account_payment",
        "base_setup",
    ],
    "data": [
        # Security
        "security/security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/bank_data.xml",
        "data/cron_jobs.xml",
        # Views - order matters! actions must be defined before use
        "views/bank_account_views.xml",
        "views/bank_transaction_views.xml",
        "views/bank_connector_views.xml",
        "views/menu_views.xml",
        # Wizards
        "wizards/bank_sync_wizard_views.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "external_dependencies": {
        "python": ["requests"],
    },
}
