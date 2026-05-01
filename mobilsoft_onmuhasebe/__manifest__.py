{
    'name': 'Mobilsoft Ön Muhasebe',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'VKN/TCKN partner alanları, çek/senet yönetimi',
    'depends': ['account', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/cheque_promissory_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
