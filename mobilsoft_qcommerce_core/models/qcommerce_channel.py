"""
Q-Commerce Hızlı Teslimat Kanalı

Getir, Yemeksepeti, Vigo gibi hızlı teslimat platformları için kanal modeli.
"""

import json
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class QCommerceChannel(models.Model):
    """Q-Commerce (Hızlı Teslimat) Kanal Modeli"""

    _name = "qcommerce.channel"
    _description = "Q-Commerce Channel"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    # ==================== Temel Alanlar ====================

    name = fields.Char("Kanal Adı", required=True, tracking=True)
    platform_type = fields.Selection(
        [
            ("getir", "Getir"),
            ("yemeksepeti", "Yemeksepeti"),
            ("vigo", "Vigo"),
        ],
        "Platform Tipi",
        required=True,
        tracking=True,
    )

    active = fields.Boolean("Aktif", default=True, tracking=True)

    # ==================== API Kimlik Bilgileri ====================

    merchant_id = fields.Char(
        "Merchant ID", required=True, help="Platform merchant kimliği"
    )
    api_key = fields.Char("API Key", required=True, help="API anahtar bilgisi")
    api_secret = fields.Char("API Secret", help="API secret (imza için)")
    shop_id = fields.Char("Shop ID", help="Mağaza ID")

    # ==================== Teslimat Ayarları ====================

    delivery_zones = fields.Text(
        "Teslimat Bölgeleri", help="JSON formatında teslimat bölgeleri listesi"
    )

    preparation_time_minutes = fields.Integer(
        "Hazırlık Süresi (Dakika)",
        default=30,
        help="Siparişin hazırlanması için gereken süre",
    )

    max_delivery_time_minutes = fields.Integer(
        "Maksimum Teslimat Süresi (Dakika)", default=60, help="Maksimum teslimat süresi"
    )

    auto_accept_orders = fields.Boolean(
        "Siparişleri Otomatik Kabul Et",
        default=True,
        help="Gelen siparişleri otomatik olarak kabul et",
    )

    auto_request_courier = fields.Boolean(
        "Kurye Talebini Otomatik Gönder",
        default=True,
        help="Sipariş hazırlandıktan sonra kurye talebini otomatik gönder",
    )

    # ==================== İstatistikler ====================

    total_orders = fields.Integer(
        "Toplam Sipariş", compute="_compute_stats", store=True
    )
    total_deliveries = fields.Integer(
        "Toplam Teslimat", compute="_compute_stats", store=True
    )
    pending_orders_count = fields.Integer(
        "Beklemede", compute="_compute_stats", store=True
    )
    success_rate = fields.Float(
        "Başarı Oranı (%)", compute="_compute_stats", store=True
    )

    last_sync = fields.Datetime("Son Senkronizasyon", help="Son senkronizasyon zamanı")

    # ==================== İlişkiler ====================

    order_ids = fields.One2many("qcommerce.order", "channel_id", "Siparişler")
    sync_log_ids = fields.One2many(
        "qcommerce.sync.log", "channel_id", "Senkronizasyon Logları"
    )

    company_id = fields.Many2one(
        "res.company", "Şirket", default=lambda self: self.env.company, required=True
    )

    # ==================== Hesaplama Alanları ====================

    @api.depends("order_ids", "order_ids.status")
    def _compute_stats(self):
        """Kanal istatistiklerini hesapla"""
        for channel in self:
            orders = channel.order_ids
            deliveries = self.env["qcommerce.delivery"].search(
                [("order_id.channel_id", "=", channel.id)]
            )

            channel.total_orders = len(orders)
            channel.total_deliveries = len(deliveries)
            channel.pending_orders_count = len(
                orders.filtered(lambda o: o.status in ["pending", "confirmed"])
            )

            successful = len(orders.filtered(lambda o: o.status == "delivered"))
            channel.success_rate = (
                (successful / len(orders) * 100) if len(orders) > 0 else 0
            )

    # ==================== Constraint'ler ====================

    @api.constrains("preparation_time_minutes")
    def _check_preparation_time(self):
        for channel in self:
            if channel.preparation_time_minutes <= 0:
                raise ValidationError("Hazırlık süresi 0'dan büyük olmalıdır")

    @api.constrains("max_delivery_time_minutes")
    def _check_delivery_time(self):
        for channel in self:
            if channel.max_delivery_time_minutes <= 0:
                raise ValidationError("Maksimum teslimat süresi 0'dan büyük olmalıdır")

    # ==================== Yardımcı Metodlar ====================

    def _get_connector(self):
        """Platform connector'ını al"""
        self.ensure_one()
        connector_mapping = {
            "getir": "mobilsoft_qcommerce_getir.connectors.getir_connector.GetirConnector",
            "yemeksepeti": "mobilsoft_qcommerce_yemeksepeti.connectors.yemeksepeti_connector.YemeksepetiConnector",
            "vigo": "mobilsoft_qcommerce_vigo.connectors.vigo_connector.VigoConnector",
        }
        connector_path = connector_mapping.get(self.platform_type)
        if not connector_path:
            raise UserError(f"{self.platform_type} için connector bulunamadı!")

        module_path, class_name = connector_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        connector_class = getattr(module, class_name)
        return connector_class(self)

    def test_connection(self) -> bool:
        """Platform API bağlantısını test et"""
        self.ensure_one()
        try:
            connector = self._get_connector()
            return connector.test_connection()
        except Exception as e:
            _logger.error(f"Bağlantı testi başarısız: {str(e)}")
            return False

    def sync_orders(self):
        """Platformdan siparişleri senkronize et"""
        self.ensure_one()
        try:
            connector = self._get_connector()
            result = connector.sync_orders(self.last_sync)
            self.last_sync = fields.Datetime.now()
            return result
        except Exception as e:
            _logger.error(f"Sipariş senkronizasyonu başarısız: {str(e)}")

    def action_sync_orders(self):
        """Action: Siparişleri senkronize et"""
        self.sync_orders()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Başarılı",
                "message": "Siparişler senkronize edildi",
                "type": "success",
            },
        }

    def action_test_connection(self):
        """Action: Bağlantı testi"""
        self.ensure_one()
        result = self.test_connection()
        msg_type = "success" if result else "danger"
        msg = "Bağlantı başarılı!" if result else "Bağlantı başarısız!"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.name,
                "message": msg,
                "type": msg_type,
            },
        }

    def get_delivery_zones(self) -> list:
        try:
            if self.delivery_zones:
                return json.loads(self.delivery_zones)
            return []
        except Exception:
            return []

    def set_delivery_zones(self, zones: list):
        self.delivery_zones = json.dumps(zones)
