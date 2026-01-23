{
    'name': 'Fatura Entegrator',
    'version': '1.0.1',
    'summary': 'Fatura Entegratör ile sipariş ve fatura entegrasyonu.',
    'description': """
        Fatura Entegratör API ile çoklu şirket bazında sipariş (sale.order) ve fatura (account.move) gönderimi, formalize ve PDF alma işlemleri.
        
        Özellikler:
        - Çoklu şirket desteği
        - Sipariş gönderimi (sale.order)
        - Fatura gönderimi (account.move)
        - Otomatik formalize işlemleri
        - PDF indirme ve saklama
        - Durum takibi (Taslak, Gönderildi, Resmileştirildi)
        - İnternet satışı desteği
        - Kargo bilgileri yönetimi
        - Muafiyet yönetimi
        - Callback desteği
    """,
    'category': 'Accounting/Invoicing',
    'author': 'Gurmehub',
    'maintainer': 'Gurmehub',
    'website': 'https://faturaentegrator.com',
    'license': 'LGPL-3',
    'depends': ['base', 'sale_management', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'views/fe_invoice_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'faturaentegrator_odoo/static/description/icon.png',
        ],
    },
    'application': False,
    'installable': True,
    'images': [
        'static/description/icon.png',
        'static/description/banner.png',
        'static/description/main_screenshot.png',
        'static/description/fatura-entegrator-install.png',
        'static/description/settings-fatura-entegrator.png',
        'static/description/fatura-entegrator-wizard.png',
        'static/description/fatura-entegrator-status.png',
        'static/description/fatura-entegrator-invoice-list.png',
        'static/description/fatura-entegrator-invoice-detail.png',
        'static/description/bizim-hesap-integration.png',
    ],
}

