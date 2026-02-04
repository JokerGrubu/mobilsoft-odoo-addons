# -*- coding: utf-8 -*-
{
    'name': 'Joker Enterprise Theme',
    'version': '19.0.1.0.0',
    'category': 'Themes/Backend',
    'summary': 'Enterprise-like theme for Odoo Community',
    'description': 'Makes Odoo Community look like Odoo Enterprise',
    'author': 'Joker Grubu',
    'website': 'https://www.jokergrubu.com',
    'license': 'LGPL-3',
    'depends': ['web'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'joker_enterprise_theme/static/src/css/enterprise_theme.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
