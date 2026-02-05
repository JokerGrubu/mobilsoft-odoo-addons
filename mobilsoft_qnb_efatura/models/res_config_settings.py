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
    qnb_auto_fetch_outgoing = fields.Boolean(
        related='company_id.qnb_auto_fetch_outgoing',
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

    # Senkronizasyon Ayarları
    qnb_create_new_partner = fields.Boolean(
        related='company_id.qnb_create_new_partner',
        readonly=False,
        string='Yeni Partner Oluştur'
    )
    qnb_match_partner_by = fields.Selection(
        related='company_id.qnb_match_partner_by',
        readonly=False,
        string='Partner Eşleştirme Kriteri'
    )
    qnb_create_new_product = fields.Boolean(
        related='company_id.qnb_create_new_product',
        readonly=False,
        string='Yeni Ürün Oluştur'
    )
    qnb_match_product_by = fields.Selection(
        related='company_id.qnb_match_product_by',
        readonly=False,
        string='Ürün Eşleştirme Kriteri'
    )
    qnb_match_invoice_by = fields.Selection(
        related='company_id.qnb_match_invoice_by',
        readonly=False,
        string='Fatura Eşleştirme Kriteri'
    )

    def action_test_qnb_connection(self):
        """QNB e-Solutions bağlantı testi"""
        self.ensure_one()

        api_client = self.env['qnb.api.client']

        try:
            # Test bağlantı metodunu kullan
            result = api_client.test_connection(self.company_id)

            if result.get('success'):
                available_ops = result.get('available_operations', [])
                ops_text = '\n'.join([f"  • {op}" for op in available_ops[:10]])
                if len(available_ops) > 10:
                    ops_text += f"\n  ... ve {len(available_ops) - 10} daha"

                message = (
                    f"✅ QNB e-Solutions Bağlantısı Başarılı\n\n"
                    f"WSDL: {result.get('wsdl_url', 'N/A')}\n"
                    f"Toplam Metod: {result.get('total_operations', 0)}\n\n"
                    f"Kullanılabilir Metodlar:\n{ops_text}"
                )
                msg_type = 'success'
            else:
                message = f"❌ Bağlantı Hatası\n\n{result.get('message', 'Bilinmeyen hata')}"
                msg_type = 'danger'

        except Exception as e:
            message = f"❌ Bağlantı Hatası\n\n{str(e)}"
            msg_type = 'danger'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QNB e-Solutions Bağlantı Testi',
                'message': message,
                'type': msg_type,
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

    def action_qnb_fetch_all_documents(self):
        """QNB'den tüm belgeleri çek"""
        self.ensure_one()
        return self.env['qnb.document'].action_fetch_all_documents()

    def action_qnb_sync_partners_from_documents(self):
        """QNB belgelerinden partner bilgilerini XML'den güncelle"""
        self.ensure_one()
        return self.env['qnb.document'].action_sync_partners_from_documents()

    def action_qnb_fix_missing_partners_from_list(self):
        """Partneri boş QNB belgelerini liste verisiyle düzelt"""
        self.ensure_one()
        return self.env['qnb.document'].action_fix_missing_partners_from_qnb_list()

    def action_qnb_bulk_match_documents(self):
        """QNB belgelerini yevmiye/fatura kayıtlarıyla eşleştir"""
        self.ensure_one()
        return self.env['qnb.document'].action_bulk_match_documents()

    def action_qnb_rematch_products(self):
        """QNB belge satırlarında ürünleri yeniden eşleştir"""
        self.ensure_one()
        return self.env['qnb.document.line'].action_bulk_rematch_products()
