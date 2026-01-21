# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # e-Fatura Bilgileri
    is_efatura_registered = fields.Boolean(
        string='e-Fatura Kayıtlı',
        default=False,
        help='Bu firma GİB e-Fatura sistemine kayıtlı mı?'
    )
    efatura_alias = fields.Char(
        string='e-Fatura Posta Kutusu',
        help='Alıcının e-Fatura posta kutusu etiketi (örn: urn:mail:defaultpk@xxx.com)'
    )
    efatura_alias_type = fields.Selection([
        ('pk', 'Posta Kutusu (PK)'),
        ('gb', 'Gönderici Birimi (GB)')
    ], string='Etiket Tipi', default='pk',
        help='Posta Kutusu: Normal kullanıcı\nGönderici Birimi: Entegratör')

    efatura_registration_date = fields.Date(
        string='e-Fatura Kayıt Tarihi',
        help='GİB sistemine kayıt tarihi'
    )
    efatura_last_check = fields.Datetime(
        string='Son Kontrol Tarihi',
        help='e-Fatura kaydı son kontrol edilme tarihi'
    )

    # e-İrsaliye Bilgileri
    is_eirsaliye_registered = fields.Boolean(
        string='e-İrsaliye Kayıtlı',
        default=False,
        help='Bu firma GİB e-İrsaliye sistemine kayıtlı mı?'
    )
    eirsaliye_alias = fields.Char(
        string='e-İrsaliye Posta Kutusu',
        help='Alıcının e-İrsaliye posta kutusu etiketi'
    )

    # Fatura Gönderim Tercihi
    invoice_send_method = fields.Selection([
        ('efatura', 'e-Fatura'),
        ('earsiv', 'e-Arşiv'),
        ('manual', 'Manuel')
    ], string='Fatura Gönderim Yöntemi',
        compute='_compute_invoice_send_method',
        store=True,
        help='Otomatik hesaplanan fatura gönderim yöntemi')

    @api.depends('is_efatura_registered', 'vat')
    def _compute_invoice_send_method(self):
        for partner in self:
            if partner.is_efatura_registered:
                partner.invoice_send_method = 'efatura'
            elif partner.vat:
                partner.invoice_send_method = 'earsiv'
            else:
                partner.invoice_send_method = 'manual'

    def action_check_efatura_status(self):
        """e-Fatura kayıt durumunu kontrol et"""
        self.ensure_one()

        if not self.vat:
            raise UserError(_("VKN/TCKN bilgisi girilmemiş!"))

        # VKN'den sadece rakamları al
        vkn = ''.join(filter(str.isdigit, self.vat))

        api_client = self.env['qnb.api.client']
        result = api_client.check_registered_user(vkn)

        if result.get('success') and result.get('users'):
            users = result['users']
            if users:
                user = users[0]
                self.write({
                    'is_efatura_registered': True,
                    'efatura_alias': user.get('alias', ''),
                    'efatura_registration_date': user.get('first_creation_time', False),
                    'efatura_last_check': fields.Datetime.now()
                })
                message = f"✅ {self.name} e-Fatura sistemine kayıtlı!\nPosta Kutusu: {user.get('alias', '-')}"
            else:
                self.write({
                    'is_efatura_registered': False,
                    'efatura_alias': False,
                    'efatura_last_check': fields.Datetime.now()
                })
                message = f"ℹ️ {self.name} e-Fatura sistemine kayıtlı değil."
        else:
            self.write({
                'is_efatura_registered': False,
                'efatura_alias': False,
                'efatura_last_check': fields.Datetime.now()
            })
            message = result.get('message', 'Kayıtlı kullanıcı bulunamadı')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'e-Fatura Kayıt Durumu',
                'message': message,
                'type': 'success' if self.is_efatura_registered else 'warning',
                'sticky': False,
            }
        }

    @api.model
    def _cron_check_efatura_status(self):
        """Zamanlanmış görev: Tüm partnerlerin e-Fatura durumunu kontrol et"""
        # VKN'si olan ve son 30 gündür kontrol edilmemiş partnerler
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)

        partners = self.search([
            ('vat', '!=', False),
            '|',
            ('efatura_last_check', '=', False),
            ('efatura_last_check', '<', thirty_days_ago)
        ], limit=100)  # Her seferde 100 partner

        for partner in partners:
            try:
                partner.action_check_efatura_status()
            except Exception:
                continue

        return True
