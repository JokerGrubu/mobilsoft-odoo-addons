# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


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

    @api.onchange('vat')
    def _onchange_vat_fetch_from_nilvera(self):
        """
        VKN/TCKN yazıp Enter/Tab yaptığınızda Nilvera'dan ünvan, adres, telefon
        vb. bilgiler otomatik gelir. Nilvera kurulu ve API anahtarı tanımlı olmalı.
        """
        if not self.vat:
            return

        digits = ''.join(filter(str.isdigit, str(self.vat)))
        if len(digits) not in (10, 11):
            return

        try:
            company = self.company_id or self.env.company
            if not getattr(company, 'l10n_tr_nilvera_api_key', None) or not company.l10n_tr_nilvera_api_key:
                return

            from odoo.addons.l10n_tr_nilvera.lib.nilvera_client import _get_nilvera_client
            with _get_nilvera_client(company, timeout_limit=10) as client:
                resp = client.request(
                    'GET',
                    f'/general/GlobalCompany/GetGlobalCustomerInfo/{digits}',
                    params={'globalUserType': 'Invoice'}
                )
        except Exception as e:
            _logger.debug("Nilvera VKN %s sorgu hatası: %s", digits, e)
            return

        if not resp:
            return
        if isinstance(resp, list) and resp:
            resp = resp[0]
        if not isinstance(resp, dict):
            return

        if resp.get('Title'):
            self.name = (resp.get('Title') or '').strip()
        if resp.get('Address'):
            self.street = (resp.get('Address') or '').strip()
        if resp.get('City'):
            state_name = (resp.get('City') or '').strip()
            state = self.env['res.country.state'].search([
                ('country_id.code', '=', 'TR'),
                ('name', 'ilike', state_name)
            ], limit=1)
            if state:
                self.state_id = state
        if resp.get('District'):
            self.city = (resp.get('District') or '').strip()
        # City/District boşsa adres sonundan il/ilçe parse et (örn: ... Gömeç balıkesir)
        if not self.city and not self.state_id and self.street:
            words = [w.strip().rstrip(',;.-') for w in self.street.split() if w.strip()]
            if len(words) >= 2:
                last_word = (words[-1] or '').rstrip(',;.-').strip()
                for st in self.env['res.country.state'].search([('country_id.code', '=', 'TR')]):
                    if st.name and last_word and st.name.upper().replace('İ', 'I') == last_word.upper().replace('İ', 'I'):
                        self.state_id = st
                        self.city = (words[-2] or '').rstrip(',;.-').strip()
                        break
        if resp.get('PostalCode'):
            self.zip = (resp.get('PostalCode') or '').strip()
        if resp.get('Country'):
            country = self.env['res.country'].search([
                ('name', 'ilike', (resp.get('Country') or '').strip())
            ], limit=1)
            if country:
                self.country_id = country
        if self.state_id and not self.country_id:
            tr = self.env['res.country'].search([('code', '=', 'TR')], limit=1)
            if tr:
                self.country_id = tr
        if resp.get('TaxDepartment'):
            tax_office = (resp.get('TaxDepartment') or '').strip()
            if tax_office and 'l10n_tr_tax_office_id' in self._fields:
                try:
                    tax_rec = self.env['l10n.tr.tax.office'].search([
                        ('name', 'ilike', tax_office)
                    ], limit=1)
                    if tax_rec:
                        self.l10n_tr_tax_office_id = tax_rec
                except Exception:
                    pass
        if resp.get('Phone'):
            self.phone = (resp.get('Phone') or '').strip()
        elif resp.get('Fax'):
            self.phone = (resp.get('Fax') or '').strip()
        if resp.get('Email'):
            self.email = (resp.get('Email') or '').strip()
        if resp.get('WebSite'):
            self.website = (resp.get('WebSite') or '').strip()
