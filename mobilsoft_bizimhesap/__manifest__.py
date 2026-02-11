# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft BizimHesap Entegrasyonu',
    'version': '19.0.1.0.3',
    'category': 'MobilSoft/Integrations',
    'summary': 'BizimHesap Ön Muhasebe Entegrasyonu',
    'description': """
BizimHesap Entegrasyon Modülü
=============================

Bu modül BizimHesap ön muhasebe uygulaması ile Odoo arasında 
çift yönlü veri senkronizasyonu sağlar.

Özellikler:
-----------
* Cari Hesap Senkronizasyonu (Müşteri/Tedarikçi)
* Ürün/Hizmet Senkronizasyonu
* Fatura Senkronizasyonu (Satış/Alış)
* Tahsilat/Ödeme Senkronizasyonu
* Otomatik Zamanlı Senkronizasyon
* Manuel Senkronizasyon
* Detaylı Loglama

Geliştirici: Joker Grubu
Website: https://www.mobilsoft.com
    """,
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'product',
        'sale',
        'purchase',
        'account',
        'stock',
    ],
    'data': [
        # Security
        'security/bizimhesap_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        # Views
        'views/bizimhesap_backend_views.xml',
        'views/bizimhesap_sync_log_views.xml',
        'views/res_partner_views.xml',
        'views/product_views.xml',
        'views/account_move_views.xml',
        'views/menu_views.xml',
        # Wizards
        'wizards/sync_wizard_views.xml',
    ],
    'demo': [],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 10,
    'images': ['static/description/icon.png'],
}
