# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft Interface',
    'version': '19.0.1.0.0',
    'summary': 'MobilSoft - Kullanıcı Dostu KOBİ ERP Arayüzü',
    'description': """
        Odoo'nun gücünü arkasına alan, bakkal/market/KOBİ için
        sadeleştirilmiş arayüz modülü.

        - Özel ana sayfa (OWL Dashboard)
        - POS hızlı başlatma
        - Basitleştirilmiş navigasyon
        - Kiracı bazlı izolasyon
    """,
    'category': 'MobilSoft',
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'account',
        'stock',
        'sale_management',
        'purchase',
        'point_of_sale',
        'mobilsoft_saas',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/mobilsoft_interface_data.xml',
        'views/mobilsoft_home_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mobilsoft_interface/static/src/scss/mobilsoft_theme.scss',
            'mobilsoft_interface/static/src/components/mobilsoft_home/mobilsoft_home.js',
            'mobilsoft_interface/static/src/components/mobilsoft_home/mobilsoft_home.xml',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
