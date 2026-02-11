# -*- coding: utf-8 -*-
"""
VKN/TCKN ile Nilvera'dan cari sorgulama ve otomatik oluşturma.
Tüm veri Nilvera GetGlobalCustomerInfo API'den alınır; QNB ve GİB kullanılmaz.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class QnbCheckPartnerWizard(models.TransientModel):
    _name = 'qnb.check.partner.wizard'
    _description = 'VKN/TCKN ile Cari Sorgula (Nilvera)'

    vkn_tckn = fields.Char(
        string='VKN/TCKN',
        required=True,
        help='Sorgulanacak VKN veya TCKN'
    )

    result_html = fields.Html(
        string='Sonuç',
        readonly=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Oluşturulan/Güncellenen Cari',
        readonly=True
    )

    def action_check(self):
        """Nilvera'dan VKN ile veri çek, cari oluştur veya güncelle"""
        self.ensure_one()

        if not self.vkn_tckn:
            raise UserError(_("VKN/TCKN giriniz!"))

        vkn = ''.join(filter(str.isdigit, self.vkn_tckn))
        if len(vkn) not in (10, 11):
            raise UserError(_("Geçersiz VKN/TCKN! VKN 10, TCKN 11 haneli olmalıdır."))

        Partner = self.env['res.partner']
        company = self.env.company

        # Nilvera API anahtarı kontrolü
        if not getattr(company, 'l10n_tr_nilvera_api_key', None) or not company.l10n_tr_nilvera_api_key:
            self.result_html = '''
            <div class="alert alert-danger">
                <h4>⚠️ Nilvera API Anahtarı Tanımlı Değil</h4>
                <p>Şirket ayarlarında Nilvera API anahtarı tanımlanmalıdır.</p>
            </div>
            '''
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'qnb.check.partner.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        # Nilvera'dan tüm veriyi çek
        partner_data = Partner._fetch_partner_data_from_nilvera_by_vkn(vkn, company)

        if not partner_data:
            self.result_html = f'''
            <div class="alert alert-warning">
                <h4>ℹ️ Nilvera'da Bulunamadı</h4>
                <p>Girilen VKN/TCKN ({vkn}) Nilvera sisteminde bulunamadı.</p>
                <p>VKN/TCKN'ı kontrol edin veya manuel cari oluşturun.</p>
            </div>
            '''
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'qnb.check.partner.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        vat_number = f"TR{vkn}"
        partner = Partner.search([
            '|', ('vat', '=', vat_number), ('vat', 'ilike', vkn)
        ], limit=1)

        created = False
        if partner:
            partner._normalize_city_state_partner_data(partner_data)
            partner._apply_qnb_partner_data(partner_data, skip_name=False, fill_empty_only=False)
            if not partner.vat:
                partner.vat = vat_number
        else:
            # Yeni cari oluştur — aynı _apply mantığı kullanılır
            create_vals = {
                'name': partner_data.get('name') or f'Firma {vkn}',
                'vat': vat_number,
                'is_company': True,
            }
            partner = Partner.create(create_vals)
            partner._normalize_city_state_partner_data(partner_data)
            partner._apply_qnb_partner_data(partner_data, skip_name=False, fill_empty_only=False)
            created = True

        # e-Fatura durumu ve posta kutusu (Nilvera Check API)
        if hasattr(partner, '_check_nilvera_customer'):
            try:
                partner._check_nilvera_customer()
            except Exception:
                pass

        self.partner_id = partner.id
        status_map = {'einvoice': 'e-Fatura', 'earchive': 'e-Arşiv', 'not_checked': 'Kontrol edilmedi'}
        efatura_status = status_map.get(
            getattr(partner, 'l10n_tr_nilvera_customer_status', None) or 'not_checked',
            'Kontrol edilmedi'
        )
        action = created and _('Yeni cari oluşturuldu') or _('Cari güncellendi')
        html = _('''
        <div class="alert alert-success">
            <h4>✅ %s</h4>
            <p><strong>%s</strong></p>
            <p>Adres: %s | İl/İlçe: %s / %s</p>
            <p>Telefon: %s | E-posta: %s</p>
            <p>e-Fatura: %s</p>
        </div>
        ''') % (
            action,
            partner.name,
            partner.street or '-',
            partner.city or '-',
            partner.state_id.name if partner.state_id else '-',
            partner.phone or '-',
            partner.email or '-',
            efatura_status,
        )
        self.result_html = html

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qnb.check.partner.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_partner(self):
        """Oluşturulan/güncellenen carisi formda aç"""
        self.ensure_one()
        if not self.partner_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
