{
    'name': 'MobilSoft Partner Fix',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Fix display_name stored=False issue in res.partner',
    'description': """
        Odoo 19 res.partner.display_name is computed but not stored.
        The contacts list view sorts by display_name which causes:
        ValueError: Cannot convert res.partner.display_name to SQL
        
        This module makes display_name stored and indexed.
    """,
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'support': 'info@mobilsoft.net',
    'license': 'LGPL-3',
    'maintainer': 'MobilSoft',
    'depends': ['contacts'],
    'data': [],
    'installable': True,
    'auto_install': False,
}
