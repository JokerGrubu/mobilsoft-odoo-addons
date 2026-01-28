# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Fatura Entegratör API Ayarları
    fe_api_key = fields.Char(
        string='Fatura Entegratör API Key',
        related='company_id.fe_api_key',
        readonly=False
    )
    fe_sale_channel_id = fields.Char(
        string='FE Satış Kanal ID',
        related='company_id.fe_sale_channel_id',
        readonly=True
    )
    fe_sale_channel_name = fields.Char(
        string='FE Satış Kanal Adı',
        related='company_id.fe_sale_channel_name',
        readonly=True
    )

    # İnternet Satışı Varsayılanları
    fe_is_internet_sale = fields.Boolean(
        string='İnternet Satışı',
        related='company_id.fe_is_internet_sale',
        readonly=False
    )
    fe_payment_method = fields.Selection(
        string='Ödeme Yöntemi',
        related='company_id.fe_payment_method',
        readonly=False
    )
    fe_payment_platform = fields.Char(
        string='Ödeme Platformu',
        related='company_id.fe_payment_platform',
        readonly=False
    )

    # Teslimat Varsayılanları
    fe_is_need_shipment = fields.Boolean(
        string='Teslimat Gerekli',
        related='company_id.fe_is_need_shipment',
        readonly=False
    )
    fe_shipment_company_title = fields.Char(
        string='Kargo Firması',
        related='company_id.fe_shipment_company_title',
        readonly=False
    )
    fe_shipment_company_tax_number = fields.Char(
        string='Kargo Firma VKN',
        related='company_id.fe_shipment_company_tax_number',
        readonly=False
    )
    fe_shipment_courier_name = fields.Char(
        string='Kurye Adı',
        related='company_id.fe_shipment_courier_name',
        readonly=False
    )
    fe_shipment_courier_tax_number = fields.Char(
        string='Kurye TC',
        related='company_id.fe_shipment_courier_tax_number',
        readonly=False
    )

    # Muafiyet Varsayılanları
    fe_exemption_code = fields.Selection(
        string='Varsayılan Muafiyet Kodu',
        related='company_id.fe_exemption_code',
        readonly=False
    )

    def fe_connect(self):
        """Fatura Entegratör'e bağlan"""
        return self.company_id.fe_connect()

    def fe_disconnect(self):
        """Fatura Entegratör bağlantısını kes"""
        return self.company_id.fe_disconnect()
