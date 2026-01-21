# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    """Ürün Şablonu - Dropshipping Alanları"""
    _inherit = 'product.template'

    # Dropshipping Bilgileri
    is_dropship = fields.Boolean(
        string='Dropship Ürünü',
        default=False,
        help='Bu ürün dropshipping ile satılıyor',
    )
    
    xml_source_id = fields.Many2one(
        'xml.product.source',
        string='XML Kaynağı',
        help='Bu ürünün geldiği XML kaynağı',
    )
    
    xml_supplier_id = fields.Many2one(
        'res.partner',
        string='Dropship Tedarikçisi',
        domain=[('supplier_rank', '>', 0)],
    )
    
    xml_supplier_sku = fields.Char(
        string='Tedarikçi Stok Kodu',
        help='Tedarikçinin kullandığı stok kodu',
    )
    
    xml_supplier_price = fields.Float(
        string='Tedarikçi Fiyatı',
        digits='Product Price',
        help='Tedarikçiden alış fiyatı',
    )
    
    xml_supplier_stock = fields.Integer(
        string='Tedarikçi Stoğu',
        help='Tedarikçideki stok miktarı',
    )
    
    xml_supplier_url = fields.Char(
        string='Tedarikçi Ürün URL',
        help='Tedarikçinin ürün sayfası',
    )
    
    xml_last_sync = fields.Datetime(
        string='Son XML Güncelleme',
        readonly=True,
    )
    
    # Fiyatlandırma
    xml_markup_percent = fields.Float(
        string='Kar Marjı (%)',
        help='Bu ürün için özel kar marjı (boşsa kaynaktaki kullanılır)',
    )
    
    xml_markup_fixed = fields.Float(
        string='Sabit Kar',
        help='Bu ürün için özel sabit kar',
    )
    
    xml_min_price = fields.Float(
        string='Minimum Satış Fiyatı',
        help='Bu fiyatın altına düşmez',
    )
    
    xml_max_price = fields.Float(
        string='Maksimum Satış Fiyatı',
        help='Bu fiyatın üstüne çıkmaz',
    )
    
    # Kargo Bilgileri
    deci = fields.Float(
        string='Desi',
        help='Kargo desi değeri',
    )
    
    # Görsel URL (indirilmeden sakla)
    xml_image_url = fields.Char(
        string='Görsel URL',
        help='Tedarikçi görsel URL adresi',
    )
    xml_image_urls = fields.Text(
        string='Ek Görsel URL\'leri',
        help='Birden fazla görsel URL\'i (her satırda bir URL)',
    )
    
    # Görsel URL'den compute edilen HTML (view için)
    xml_image_html = fields.Html(
        string='Görsel Önizleme',
        compute='_compute_xml_image_html',
        sanitize=False,
    )
    
    # Hesaplanan alanlar
    xml_profit = fields.Float(
        string='Kar',
        compute='_compute_xml_profit',
        store=False,
    )
    
    xml_profit_percent = fields.Float(
        string='Kar Oranı (%)',
        compute='_compute_xml_profit',
        store=False,
    )

    @api.depends('xml_image_url', 'xml_image_urls')
    def _compute_xml_image_html(self):
        for product in self:
            html_parts = []
            if product.xml_image_url:
                html_parts.append(f'<img src="{product.xml_image_url}" style="max-width:200px; max-height:200px; margin:5px; border:1px solid #ddd; border-radius:4px;" />')
            if product.xml_image_urls:
                for url in product.xml_image_urls.split('\n')[:5]:  # Max 5 ek görsel göster
                    url = url.strip()
                    if url:
                        html_parts.append(f'<img src="{url}" style="max-width:100px; max-height:100px; margin:3px; border:1px solid #ddd; border-radius:4px;" />')
            product.xml_image_html = '<div style="display:flex; flex-wrap:wrap; gap:5px;">' + ''.join(html_parts) + '</div>' if html_parts else ''

    @api.depends('list_price', 'xml_supplier_price')
    def _compute_xml_profit(self):
        for product in self:
            if product.xml_supplier_price:
                product.xml_profit = product.list_price - product.xml_supplier_price
                product.xml_profit_percent = (product.xml_profit / product.xml_supplier_price) * 100 if product.xml_supplier_price else 0
            else:
                product.xml_profit = 0
                product.xml_profit_percent = 0

    def action_update_from_xml(self):
        """Ürünü XML kaynağından güncelle"""
        for product in self:
            if product.xml_source_id:
                # Tek ürün güncelleme (ileride implement edilebilir)
                product.xml_source_id.action_import_products()
    
    def action_load_image_from_url(self):
        """Görsel URL'sini Odoo'ya indir"""
        for product in self:
            if product.xml_image_url:
                try:
                    import requests
                    import base64
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    }
                    response = requests.get(product.xml_image_url, headers=headers, timeout=30)
                    if response.ok:
                        image_data = base64.b64encode(response.content).decode('utf-8')
                        product.image_1920 = image_data
                except Exception as e:
                    pass
