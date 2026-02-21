# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft Interface',
    'version': '19.0.2.0.0',
    'summary': 'MobilSoft - Tam ERP Arayüzü (SPA)',
    'description': """
        Odoo'nun gücünü kullanan, KOBİ için tam özel SPA (Single Page Application) arayüz.

        - Sidebar navigasyon (Ürünler, Cariler, Satışlar, Stok, Faturalar, Raporlar)
        - Tam özel OWL form ve liste görünümleri
        - Responsive tasarım (masaüstü + mobil)
        - PWA desteği (Android/iOS kurulabilir)
        - Hiçbir Odoo chrome görünmez
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
            # SCSS (önce yükle - temel tema ve yeni stiller)
            'mobilsoft_interface/static/src/scss/mobilsoft_theme.scss',
            'mobilsoft_interface/static/src/scss/ms_app.scss',
            'mobilsoft_interface/static/src/scss/ms_modules.scss',

            # Ana Dashboard bileşeni
            'mobilsoft_interface/static/src/components/mobilsoft_home/mobilsoft_home.js',
            'mobilsoft_interface/static/src/components/mobilsoft_home/mobilsoft_home.xml',

            # Ürünler modülü
            'mobilsoft_interface/static/src/components/ms_products/products.js',
            'mobilsoft_interface/static/src/components/ms_products/products.xml',

            # Cariler modülü
            'mobilsoft_interface/static/src/components/ms_customers/customers.js',
            'mobilsoft_interface/static/src/components/ms_customers/customers.xml',

            # Satışlar modülü
            'mobilsoft_interface/static/src/components/ms_sales/sales.js',
            'mobilsoft_interface/static/src/components/ms_sales/sales.xml',

            # Faturalar modülü
            'mobilsoft_interface/static/src/components/ms_invoices/invoices.js',
            'mobilsoft_interface/static/src/components/ms_invoices/invoices.xml',

            # Stok modülü
            'mobilsoft_interface/static/src/components/ms_stock/stock.js',
            'mobilsoft_interface/static/src/components/ms_stock/stock.xml',

            # Ana SPA Shell (son yüklenmeli - alt bileşenleri import ediyor)
            'mobilsoft_interface/static/src/app/mobilsoft_app.js',
            'mobilsoft_interface/static/src/app/mobilsoft_app.xml',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
