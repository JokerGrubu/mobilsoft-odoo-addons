{
    'name': 'MobilSoft POS Fatura Raporu',
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Custom invoice report template for POS orders",
    "description": """
        This module adds a custom invoice report template selection for POS configurations.
        When sending invoices for POS orders, the system will use the report template 
        configured in the POS config if available.
    """,
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'license': 'LGPL-3',
    "depends": [
        "point_of_sale",
        "account",
    ],
    "data": [
        "views/pos_config_views.xml",
    ],
    "images": ["static/description/main_description.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
