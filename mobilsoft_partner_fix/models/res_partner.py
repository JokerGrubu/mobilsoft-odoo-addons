from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Override display_name to be stored and indexed
    # This fixes: ValueError: Cannot convert res.partner.display_name to SQL
    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
        index=True,
    )
