{
    'name': 'Türkiye Vergi Daireleri - MobilSoft',
    "summary": "Türkiye'deki tüm vergi dairelerinin listesi",
    "description": """
        Bu modül Türkiye'deki vergi dairelerini Odoo'ya ekler.
        İş ortağı (partner) kartlarında vergi dairesi seçimi yapılabilir.
        
        Kaynak: Kıta Yazılım / 2KB konsepti temel alınmıştır.
    """,
    "version": "19.0.1.0.0",
    'license': 'LGPL-3',
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    "category": "Localization",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/tax_office_views.xml",
        "data/tax_office_data.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
