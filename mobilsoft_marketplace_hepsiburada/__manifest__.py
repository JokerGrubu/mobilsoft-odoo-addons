{
    "name": "MobilSoft Pazaryeri - Hepsiburada Entegrasyonu",
    "version": "19.0.1.0.0",
    "category": "Sales/Marketplace",
    "summary": "Hepsiburada REST API entegrasyonu",
    "author": "MobilSoft",
    "website": "https://www.jokergrubu.com",
    "depends": [
        "mobilsoft_marketplace_core",
        "sale",
        "stock",
    ],
    "data": [
        "views/menu.xml",
    ],
    "external_dependencies": {
        "python": ["requests", "python-dateutil"],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
