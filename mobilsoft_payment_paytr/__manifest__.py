# Part of Kitayazilim. See LICENSE file for full copyright and licensing details.

{
    'name': 'MobilSoft PayTR Ödeme Entegrasyonu',
    "version": "19.0.1.0.0",
    "category": "Accounting/Payment Providers",
    "sequence": 350,
    "summary": "A PayTR payment provider.",
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    "depends": ["payment", "account_payment", "sale", "website_sale"],
    "data": [
        "data/payment_provider_data.xml",
        "views/payment_provider_views.xml",
    ],
    "application": False,
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "assets": {
        "web.assets_frontend": [
            "mobilsoft_payment_paytr/static/src/js/payment_form.js",
        ],
    },
    'license': 'LGPL-3',
}
