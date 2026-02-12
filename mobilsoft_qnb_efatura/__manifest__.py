# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft QNB e-Fatura Entegrasyonu',
    'version': '19.0.1.21.0',
    'category': 'Accounting/Localizations',
    'summary': 'QNB e-Solutions e-Fatura, e-Arşiv, e-İrsaliye Entegrasyonu',
    'description': """
QNB e-Solutions e-Belge Entegrasyonu
====================================

Bu modül Odoo 19 ile QNB e-Solutions arasında entegrasyon sağlar:

* e-Fatura gönderme ve alma
* e-Arşiv fatura oluşturma
* e-İrsaliye gönderme ve alma
* Belge durumu sorgulama
* Otomatik belge indirme
* GİB kayıtlı kullanıcı sorgulama

Gereksinimler:
- QNB e-Solutions hesabı
- API kullanıcı adı ve şifresi
- Test veya Canlı WSDL endpoint

Teknik Özellikler:
- SOAP tabanlı web servisi
- WS-Security ile kimlik doğrulama
- CS-XML ve UBL-TR formatı desteği
    """,
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'account_edi_ubl_cii',
        'sale',
        'stock',
        'contacts',
        'l10n_tr',
        'l10n_tr_nilvera_einvoice',
    ],
    'data': [
        'security/qnb_esolutions_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/ir_cron_data_update.xml',
        'data/nilvera_cron_override.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'views/qnb_document_views.xml',
        'wizard/qnb_wizard_views.xml',
        'views/qnb_menu_views.xml',
    ],
    'external_dependencies': {
        'python': ['zeep', 'lxml'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
