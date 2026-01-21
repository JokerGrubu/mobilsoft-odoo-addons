# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class QnbCheckPartnerWizard(models.TransientModel):
    _name = 'qnb.check.partner.wizard'
    _description = 'e-Fatura Kayıt Kontrolü Sihirbazı'

    vkn_tckn = fields.Char(
        string='VKN/TCKN',
        required=True,
        help='Kontrol edilecek VKN veya TCKN'
    )

    result_html = fields.Html(
        string='Sonuç',
        readonly=True
    )

    def action_check(self):
        """e-Fatura kaydını kontrol et"""
        self.ensure_one()

        if not self.vkn_tckn:
            raise UserError(_("VKN/TCKN giriniz!"))

        # Sadece rakamları al
        vkn = ''.join(filter(str.isdigit, self.vkn_tckn))

        if len(vkn) not in (10, 11):
            raise UserError(_("Geçersiz VKN/TCKN! VKN 10, TCKN 11 haneli olmalıdır."))

        api_client = self.env['qnb.api.client']
        result = api_client.check_registered_user(vkn)

        if result.get('success') and result.get('users'):
            users = result['users']
            html = '<div class="alert alert-success"><h4>✅ e-Fatura Sistemine Kayıtlı</h4><ul>'
            for user in users:
                html += f"""
                <li>
                    <strong>Unvan:</strong> {user.get('title', '-')}<br/>
                    <strong>VKN/TCKN:</strong> {user.get('vkn_tckn', '-')}<br/>
                    <strong>Posta Kutusu:</strong> {user.get('alias', '-')}<br/>
                    <strong>Kayıt Tarihi:</strong> {user.get('first_creation_time', '-')}
                </li>
                """
            html += '</ul></div>'
        else:
            html = f"""
            <div class="alert alert-warning">
                <h4>ℹ️ e-Fatura Sistemine Kayıtlı Değil</h4>
                <p>Girilen VKN/TCKN ({vkn}) GİB e-Fatura sisteminde bulunamadı.</p>
                <p>Bu müşteriye e-Arşiv fatura kesilmelidir.</p>
            </div>
            """

        self.result_html = html

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qnb.check.partner.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_update_partner(self):
        """Mevcut partneri güncelle"""
        self.ensure_one()

        vkn = ''.join(filter(str.isdigit, self.vkn_tckn))

        # VKN'ye göre partner bul
        partner = self.env['res.partner'].search([
            '|',
            ('vat', '=', vkn),
            ('vat', 'ilike', vkn)
        ], limit=1)

        if partner:
            partner.action_check_efatura_status()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Partner Güncellendi',
                    'message': f'{partner.name} e-Fatura bilgileri güncellendi.',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError(_("Bu VKN/TCKN ile kayıtlı partner bulunamadı!"))
