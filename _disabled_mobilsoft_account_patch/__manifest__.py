# -*- coding: utf-8 -*-
# Copyright (C) 2024 Odoo Turkey Community (https://github.com/orgs/Odoo-Turkey-Community/dashboard)
# License Other proprietary. Please see the license file in the Addon folder.

{
    'name': 'MobilSoft Muhasebe Düzeltmeleri',
    "version": "19.0.1.0.0",
    "summary": "Türkiye Lokalizasyonu Genişletme Paketi 2KB",
    "description": """
        Türkiye Lokalizasyonu Genişletme Paketi 2KB
    """,
    'maintainer': 'MobilSoft',
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'license': 'LGPL-3',
    "sequence": 1453,
    "category": "Accounting/Localizations/Account Charts",
    "depends": ["account"],
    "data": [],
    "installable": False,  # Disabled - causes KeyError: 'tax_src_id' in new databases
    "application": False,
    "auto_install": False,
    "images": ["images/main_screenshot.png"],
}
