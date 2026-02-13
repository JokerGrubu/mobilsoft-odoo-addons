# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft Banka Entegrasyonu',
    'version': '19.0.2.0.0',
    'category': 'Accounting/Banking',
    'summary': 'Türk Bankaları Open Banking API Entegrasyonu',
    'description': """
Türk Bankaları Open Banking Entegrasyonu - Odoo 19

Desteklenen Bankalar:
* Garanti BBVA - OAuth 2.0 ile tam entegrasyon
* Ziraat Bankası - Kurumsal ve bireysel hesap desteği
* QNB Finansbank - Hesap ve işlem senkronizasyonu

Özellikler:
* Banka hesaplarını otomatik senkronize eder
* İşlemleri Odoo banka ekstresi satırı olarak kaydeder
* Döviz kurlarını bankadan günceller
* Mükerrer işlem önleme (unique import ref)
* Otomatik partner eşleştirme (VKN, IBAN, isim)
* Çoklu şirket desteği
* Güvenlik grupları ve yetkilendirme
    """,
    'author': 'MobilSoft',
    'website': 'https://www.jokergrubu.com',
    'license': 'LGPL-3',
    'depends': ['account', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/bank_data.xml',
        'data/cron_jobs.xml',
        'views/bank_connector_views.xml',
        'views/menu_views.xml',
        'wizards/bank_sync_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'external_dependencies': {'python': ['requests']},
}
