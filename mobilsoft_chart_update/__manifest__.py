# Copyright 2016 Jairo Llopis <jairo.llopis@tecnativa.com>
# Copyright 2016 Jacques-Etienne Baudoux <je@bcim.be>
# Copyright 2016 Sylvain Van Hoof <sylvain@okia.be>
# Copyright 2015-2018 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'MobilSoft Hesap Planı Güncelleme',
    "summary": "Wizard to update a company's account chart from a template",
    "version": "19.0.1.1.4",
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    "depends": ["account"],
    "category": "Accounting",
    'license': 'LGPL-3',
    "data": [
        "security/ir.model.access.csv",
        "wizard/wizard_chart_update_view.xml",
        "views/account_config_settings_view.xml",
    ],
    "installable": True,
}
