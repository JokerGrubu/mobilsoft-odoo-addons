# -*- coding: utf-8 -*-
# Copyright (C) 2024 Odoo Turkey Community (https://github.com/orgs/Odoo-Turkey-Community/dashboard)
# License Other proprietary. Please see the license file in the Addon folder.

{
    'name': 'Türkiye Hesap Planı - MobilSoft',
    "version": "19.0.1.0.0",
    "summary": "Türkiye Lokalizasyonu 2KB",
    "description": """
        Türkiye Lokalizasyonu 2KB
    """,
    'maintainer': 'MobilSoft',
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'license': 'LGPL-3',
    "sequence": 1453,
    "category": "Accounting/Localizations/Account Charts",
    "depends": ["account"],
    "data": [
        "views/account_fiscal_position_views.xml",
        "views/account_tax_group_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
    "external_dependencies": {
        "python": [],
    },
    "images": ["static/description/images/main_screenshot.png"],
}
