# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft Tedarikçi Fatura Kontrol',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Tedarikçi fatura fiyat doğrulama ve stok giriş kontrolü',
    'description': """
Tedarikçi Fatura Kontrol Sistemi
================================

Bu modül tedarikçi faturalarını otomatik kontrol eder:

* Fatura satır fiyatlarını tedarikçi USD maliyeti × güncel kur ile karşılaştırır
* Sıfır tolerans: Kuruş hassasiyetinde eşleşme gerektirir
* Eşleşen faturalar onaylanır ve SAYIM deposuna stok girişi oluşturulur
* Eşleşmeyen faturalar reddedilir, fark detayları gösterilir
* Muhasebe kaydı: 153 Ticari Mallar hesabına giriş
    """,
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'stock',
        'product',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
