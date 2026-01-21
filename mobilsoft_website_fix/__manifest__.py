# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft Website Login Fix',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Login sonrası database parametresi ekler',
    'description': """
        Website modülünün login redirect'ini düzeltir.
        Login sonrası /odoo route'una database parametresi ekler.
    """,
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'depends': ['website', 'web'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
