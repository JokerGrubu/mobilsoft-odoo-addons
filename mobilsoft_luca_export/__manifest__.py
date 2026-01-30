# -*- coding: utf-8 -*-
{
    'name': 'Luca Muhasebe Export',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Odoo verilerini Luca muhasebe programına aktarma',
    'description': """
Luca Muhasebe Export Modülü
===========================

Bu modül Odoo'daki muhasebe verilerini Luca muhasebe programına
aktarmak için gerekli export fonksiyonlarını sağlar.

Özellikler:
-----------
* Hesap Planı XML Export (Logo uyumlu format)
* Muhasebe Fişleri Excel/CSV Export
* Cari Bilgileri CSV Export
* Tarih aralığı ve hesap filtresi
* Otomatik dosya bölme (50 fiş limiti)

Luca Format Gereksinimleri:
---------------------------
* Fiş No (Zorunlu)
* Fiş Tarihi (Zorunlu)
* Hesap Kodu (Zorunlu)
* Borç (Zorunlu)
* Alacak (Zorunlu)
* Açıklama (Opsiyonel)
* Belge No (Opsiyonel)

    """,
    'author': 'MobilSoft',
    'website': 'https://jokergrubu.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
    ],
    'data': [
        'security/luca_export_security.xml',
        'security/ir.model.access.csv',
        'views/luca_export_views.xml',
        'wizard/luca_export_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
