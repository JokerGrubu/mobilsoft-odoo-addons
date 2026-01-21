from odoo import models, fields, api


class L10nTrTaxOffice(models.Model):
    _name = 'l10n.tr.tax.office'
    _description = 'Türkiye Vergi Dairesi'
    _order = 'city_id, name'

    name = fields.Char(string='Vergi Dairesi Adı', required=True, index=True)
    code = fields.Char(string='Vergi Dairesi Kodu', required=True, index=True)
    city_id = fields.Many2one('res.country.state', string='İl', 
                              domain="[('country_id.code', '=', 'TR')]",
                              required=True)
    city_name = fields.Char(related='city_id.name', string='İl Adı', store=True)
    active = fields.Boolean(default=True)

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.name} ({record.code})"
            result.append((record.id, name))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('code', operator, name)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid, order=order)
