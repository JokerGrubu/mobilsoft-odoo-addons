# -*- coding: utf-8 -*-
# Copyright (C) 2024 Odoo Turkey Community (https://github.com/orgs/Odoo-Turkey-Community/dashboard)
# License Other proprietary. Please see the license file in the Addon folder.
# Updated for Odoo 19 compatibility - 21 Ocak 2026

from odoo.addons.account.models.chart_template import AccountChartTemplate


origin_try_loading = AccountChartTemplate.try_loading
AccountChartTemplate.origin_try_loading = origin_try_loading


def new_try_loading(self, template_code, company, install_demo=False, force_create=True):
    """
    Odoo 19 uyumlu try_loading override.
    Türkiye muhasebe şablonlarının otomatik yüklenmesini engeller,
    kullanıcının kendi seçmesine izin verir.
    """
    # Türkiye muhasebe şablonları
    tr_templates = ['tr', 'l10n_tr', 'tr_7a', 'tr_7b', 'l10n_tr_7a', 'l10n_tr_7b']
    
    # İlk kurulumda force gelmemiş ise Türkiyenin muhasebe hesap ve vergilerini yükleme
    # kullanıcı kendi seçsin
    if not self.env.context.get("force", False) and template_code in tr_templates:
        return
    return self.origin_try_loading(template_code, company, install_demo, force_create)


AccountChartTemplate.try_loading = new_try_loading
