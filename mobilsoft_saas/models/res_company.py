# -*- coding: utf-8 -*-
"""
MobilSoft SaaS - Şirket Modeli Genişletme

Yeni şirket oluşturulduğunda otomatik kurulum tetikler.
"""

import logging
from odoo import api, models, fields

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    # MobilSoft SaaS alanları
    mobilsoft_tenant = fields.Boolean(
        string='MobilSoft Kiracısı',
        default=False,
        help='Bu şirket MobilSoft SaaS platformu üzerinden oluşturulmuştur.',
    )
    mobilsoft_plan = fields.Selection([
        ('free', 'Ücretsiz'),
        ('basic', 'Temel'),
        ('pro', 'Profesyonel'),
    ], string='MobilSoft Planı', default='free')
    mobilsoft_registered_date = fields.Datetime(
        string='Kayıt Tarihi',
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Şirket oluşturulduğunda MobilSoft alanlarını set et."""
        companies = super().create(vals_list)
        for company in companies:
            if company.mobilsoft_tenant:
                company.mobilsoft_registered_date = fields.Datetime.now()
                _logger.info('MobilSoft SaaS: Yeni kiracı şirket: %s', company.name)
        return companies
