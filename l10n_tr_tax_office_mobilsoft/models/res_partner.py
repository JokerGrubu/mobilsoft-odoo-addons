from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_tr_tax_office_id = fields.Many2one(
        'l10n.tr.tax.office', 
        string='Vergi Dairesi',
        help='Türkiye vergi dairesi'
    )
    l10n_tr_tax_office_name = fields.Char(
        related='l10n_tr_tax_office_id.name',
        string='Vergi Dairesi Adı',
        store=True
    )
