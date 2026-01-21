# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # QNB e-Solutions Temel Ayarları
    qnb_enabled = fields.Boolean(
        related='company_id.qnb_enabled',
        readonly=False,
        string='QNB e-Solutions Aktif'
    )
    qnb_environment = fields.Selection(
        related='company_id.qnb_environment',
        readonly=False,
        string='QNB Ortam'
    )
    qnb_username = fields.Char(
        related='company_id.qnb_username',
        readonly=False,
        string='Kullanıcı Adı'
    )
    qnb_password = fields.Char(
        related='company_id.qnb_password',
        readonly=False,
        string='Şifre'
    )
    qnb_wsdl_url = fields.Char(
        related='company_id.qnb_wsdl_url',
        readonly=False,
        string='Özel WSDL URL'
    )

    # e-Fatura Ayarları
    qnb_efatura_enabled = fields.Boolean(
        related='company_id.qnb_efatura_enabled',
        readonly=False
    )
    qnb_efatura_scenario = fields.Selection(
        related='company_id.qnb_efatura_scenario',
        readonly=False
    )
    qnb_efatura_prefix = fields.Char(
        related='company_id.qnb_efatura_prefix',
        readonly=False
    )

    # e-Arşiv Ayarları
    qnb_earsiv_enabled = fields.Boolean(
        related='company_id.qnb_earsiv_enabled',
        readonly=False
    )
    qnb_earsiv_prefix = fields.Char(
        related='company_id.qnb_earsiv_prefix',
        readonly=False
    )
    qnb_earsiv_send_type = fields.Selection(
        related='company_id.qnb_earsiv_send_type',
        readonly=False
    )

    # e-İrsaliye Ayarları
    qnb_eirsaliye_enabled = fields.Boolean(
        related='company_id.qnb_eirsaliye_enabled',
        readonly=False
    )
    qnb_eirsaliye_prefix = fields.Char(
        related='company_id.qnb_eirsaliye_prefix',
        readonly=False
    )

    # Otomatik İşlemler
    qnb_auto_fetch_incoming = fields.Boolean(
        related='company_id.qnb_auto_fetch_incoming',
        readonly=False
    )
    qnb_auto_check_status = fields.Boolean(
        related='company_id.qnb_auto_check_status',
        readonly=False
    )

    # Şirket Bilgileri
    qnb_gib_alias = fields.Char(
        related='company_id.qnb_gib_alias',
        readonly=False
    )
    qnb_sender_alias = fields.Char(
        related='company_id.qnb_sender_alias',
        readonly=False
    )

    def action_test_qnb_connection(self):
        """QNB e-Solutions bağlantı testi"""
        self.ensure_one()

        api_client = self.env['qnb.api.client']

        try:
            # Kontör durumu sorgulayarak bağlantı testi
            result = api_client.get_credit_status(self.company_id)

            if result.get('success'):
                message = (
                    f"✅ Bağlantı başarılı!\n\n"
                    f"Kontör Durumu:\n"
                    f"• e-Fatura: {result.get('efatura_credit', 0)}\n"
                    f"• e-Arşiv: {result.get('earchive_credit', 0)}\n"
                    f"• e-İrsaliye: {result.get('edespatch_credit', 0)}"
                )
            else:
                message = f"❌ Bağlantı hatası: {result.get('message', 'Bilinmeyen hata')}"

        except Exception as e:
            message = f"❌ Bağlantı hatası: {str(e)}"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QNB e-Solutions Bağlantı Testi',
                'message': message,
                'type': 'success' if 'başarılı' in message else 'danger',
                'sticky': True,
            }
        }

    def action_sync_registered_users(self):
        """Kayıtlı kullanıcı listesini senkronize et"""
        self.ensure_one()

        api_client = self.env['qnb.api.client']

        try:
            result = api_client.get_registered_users_list(self.company_id)

            if result.get('success'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Kayıtlı Kullanıcılar',
                        'message': '✅ Kayıtlı kullanıcı listesi güncellendi.',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise Exception(result.get('message', 'Bilinmeyen hata'))

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Hata',
                    'message': f'❌ {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
