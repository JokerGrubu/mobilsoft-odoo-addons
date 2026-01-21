{
    'name': 'Türkiye Banka Listesi - MobilSoft',
    "summary": "Türkiye'deki bankaların listesi ve SWIFT kodları",
    "description": """
        Bu modül Türkiye'deki tüm bankaları Odoo'ya ekler.
        SWIFT kodları ve iletişim bilgileri dahildir.
        
        Kaynak: Kıta Yazılım / 2KB konsepti temel alınmıştır.
    """,
    "version": "19.0.1.0.0",
    'license': 'LGPL-3',
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    "category": "Localization",
    "depends": ["base"],
    "data": [
        "data/bank_data.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
