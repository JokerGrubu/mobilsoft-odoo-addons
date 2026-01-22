# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft Ön Muhasebe',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Türkiye pazarına özel Ön Muhasebe uygulaması',
    'description': """
MobilSoft Ön Muhasebe
=====================

Türk KOBİ'lerine özel, basit ve kullanışlı ön muhasebe uygulaması.

Özellikler:
-----------
* Dashboard (Gösterge Paneli) - Nakit, Banka, Alacaklar, Borçlar
* Cari Hesaplar (VKN/TCKN, Vergi Dairesi, IBAN desteği)
* Faturalar (KDV 0%, 1%, 10%, 20%, Tevkifat desteği)
* Çek & Senet Yönetimi (Portföy, Tahsil, Ciro, Karşılıksız)
* Kasa & Banka İşlemleri
* Basit Stok Yönetimi

Geliştirici: MobilSoft
Website: https://www.mobilsoft.net
    """,
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'account',
        'account_accountant',
        'product',
        'sale',
        'purchase',
        'stock',
        'l10n_tr_tax_office_mobilsoft',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/ir_sequence.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/cheque_promissory_views.xml',
        'views/dashboard_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 10,
}
