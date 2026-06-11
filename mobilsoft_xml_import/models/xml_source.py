# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import logging
import re
import json
import html
import base64
import time
from difflib import SequenceMatcher
from io import BytesIO
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse, urljoin

_logger = logging.getLogger(__name__)


class XmlProductSource(models.Model):
    """XML Ürün Kaynağı - Dropshipping Tedarikçi Feed'i"""
    _name = 'xml.product.source'
    _description = 'XML Ürün Kaynağı'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(
        string='Kaynak Adı',
        required=True,
        tracking=True,
        help='Tedarikçi veya feed adı',
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    # Tedarikçi Bilgileri
    supplier_id = fields.Many2one(
        'res.partner',
        string='Tedarikçi',
        domain=[('supplier_rank', '>', 0)],
        help='Bu XML kaynağına bağlı tedarikçi',
    )

    # XML Ayarları
    xml_url = fields.Char(
        string='XML URL',
        required=True,
        tracking=True,
        help='Ürün feed URL adresi',
    )
    xml_username = fields.Char(
        string='Kullanıcı Adı',
        help='HTTP Basic Auth kullanıcı adı (opsiyonel)',
    )
    xml_password = fields.Char(
        string='Şifre',
        help='HTTP Basic Auth şifresi (opsiyonel)',
    )
    xml_token = fields.Char(
        string='API Token',
        help='Token tabanlı servisler için opsiyonel API anahtarı',
    )
    soap_namespace = fields.Char(
        string='SOAP Namespace',
        default='http://tempuri.org/',
        help='SOAP Header ve Body içinde kullanılacak xmlns değeri',
    )
    soap_product_element = fields.Char(
        string='SOAP Urun Elementi',
        default='ProductList',
        help='Urun listesi sonucunda okunacak XML element adi',
    )
    soap_extra_body = fields.Text(
        string='SOAP Ek Body',
        default='<_departman>0</_departman>',
        help='Urun metodu cagrisinda gonderilecek ek body XML parcasi',
    )
    soap_method_products = fields.Char(
        string='Urun Metodu',
        default='GetProductLists',
    )
    soap_method_prices = fields.Char(
        string='Fiyat Metodu',
        default='GetStockPrices',
    )
    soap_method_stock = fields.Char(
        string='Stok Metodu',
        default='GetWareHouseStocks',
    )
    soap_method_images = fields.Char(
        string='Gorsel Metodu',
        default='GetProductImages',
    )
    soap_method_features = fields.Char(
        string='Ozellik Metodu',
        default='GetProductFeatures',
    )
    soap_method_categories = fields.Char(
        string='Kategori Metodu',
        default='GetProductCategories',
    )

    # Index Grup / Netex ayrı feed URL'leri
    xml_stock_url = fields.Char(
        string='Stok XML URL',
        help='Ayrı stok feed URL (Index Grup/Netex için)',
    )
    xml_price_url = fields.Char(
        string='Fiyat XML URL',
        help='Ayrı fiyat feed URL (Index Grup/Netex için)',
    )

    # IdeaSoft tabanlı mağaza vitrininden web stok senkronu (örn. asiamark.com)
    # XML feed'inde stok olmayan tedarikçiler için, vitrindeki ürün sayfalarından
    # barkod + stokAdedi okunarak stok durumu güncellenir.
    web_stock_url = fields.Char(
        string='Web Stok Mağaza URL',
        help='IdeaSoft/Ticimax tabanlı mağaza ana adresi (örn. https://asiamark.com). '
             'sitemap üzerinden ürün sayfaları taranıp barkod->stok eşlenir.',
    )
    auto_web_stock_sync = fields.Boolean(
        string='Web Stoğu Otomatik Senkronla (Cron)',
        default=False,
        help='Açıksa, web stok senkron cron\'u bu kaynağı otomatik tarar (günlük).',
    )

    # Bayi paneli (Ticimax katalog) USD alış fiyatı çekme
    web_price_url = fields.Char(
        string='Bayi Fiyat Panel URL',
        help='Ticimax bayi katalog ana adresi (örn. https://katalog.asyapasifikteknoloji.com). '
             'Login ile USD indirimli alış fiyatları çekilir.',
    )
    web_price_tel = fields.Char(string='Bayi Login (Tel/Kullanıcı)')
    web_price_password = fields.Char(string='Bayi Login Şifre')
    web_price_vendor_id = fields.Many2one(
        'res.partner', string='Fiyat Tedarikçisi',
        help='Alış fiyatının yazılacağı tedarikçi (product.supplierinfo). Boşsa kaynağın tedarikçisi kullanılır.',
    )
    auto_web_price_sync = fields.Boolean(
        string='Bayi Fiyatını Otomatik Senkronla (Cron)',
        default=False,
        help='Açıksa, fiyat senkron cron\'u bu kaynağı otomatik tarar (günlük).',
    )
    cost_currency_id = fields.Many2one(
        'res.currency', string='Maliyet Para Birimi',
        help='XML\'den gelen fiyatların para birimi (USD, EUR, TRY). '
             'TRY değilse satış fiyatı otomatik dönüştürülür.',
    )
    auto_price_recalc = fields.Boolean(
        string='Satış Fiyatını Otomatik Yeniden Hesapla (Cron)',
        default=False,
        help='Döviz kuru değiştiğinde satış fiyatlarını otomatik güncelle.',
    )

    # Powerway Online Sipariş Portalı
    powerway_url = fields.Char(
        string='Powerway Online URL',
        default='https://online.powerway.com.tr',
        help='Powerway B2B sipariş portalı (örn. https://online.powerway.com.tr)',
    )
    powerway_user = fields.Char(string='Powerway Kullanıcı (E-posta)')
    powerway_password = fields.Char(string='Powerway Şifre')
    auto_powerway_sync = fields.Boolean(
        string='Siparişleri Otomatik Senkronla (Cron)',
        default=False,
    )
    powerway_last_sync = fields.Datetime(string='Son Powerway Senkron', readonly=True)

    # Baytek B2B Sipariş Portalı
    baytek_b2b_url = fields.Char(
        string='Baytek B2B URL',
        default='https://www.bayiteknoloji.com',
        help='Baytek B2B sipariş portalı (örn. https://www.bayiteknoloji.com)',
    )
    baytek_b2b_dealer = fields.Char(string='Baytek Bayi Kodu')
    baytek_b2b_user = fields.Char(string='Baytek Kullanıcı Adı')
    baytek_b2b_password = fields.Char(string='Baytek Şifre')
    auto_baytek_sync = fields.Boolean(
        string='Baytek Siparişleri Otomatik Senkronla (Cron)',
        default=False,
    )
    baytek_last_sync = fields.Datetime(string='Son Baytek Senkron', readonly=True)

    # Kaynak Tipi
    source_type = fields.Selection([
        ('xml', 'XML Feed'),
        ('soap', 'SOAP Web Service'),
        ('web', 'Web Scraping'),
        ('api', 'REST API'),
    ], string='Kaynak Tipi', default='xml', required=True)

    # XML/Web Scraping Ayarları
    xml_template = fields.Selection([
        ('tsoft', 'T-Soft'),
        ('ticimax', 'Ticimax'),
        ('ideasoft', 'IdeaSoft'),
        ('akinsoft', 'Akinsoft (Wolvox)'),
        ('eminonu', 'Eminonu XML'),
        ('google_rss', 'Google RSS / Merchant Feed'),
        ('opencart', 'OpenCart'),
        ('woocommerce', 'WooCommerce'),
        ('woocommerce_api', 'WooCommerce API'),
        ('tesan_soap', 'Tesan SOAP'),
        ('tesan_web', 'Tesan Web Scraping'),
        ('linktech_web', 'LinkTech Web Scraping'),
        ('prestashop', 'PrestaShop'),
        ('shopify', 'Shopify'),
        ('magento', 'Magento'),
        ('google', 'Google Shopping'),
        ('n11', 'N11'),
        ('trendyol', 'Trendyol'),
        ('hepsiburada', 'Hepsiburada'),
        ('cimri', 'Cimri'),
        ('akakce', 'Akakçe'),
        ('indexgrup', 'Index Grup'),
        ('netex', 'Netex'),
        ('baytek', 'Baytek Bilişim'),
        ('custom', 'Özel (Custom)'),
    ], string='Şablon', default='custom', required=True)

    # Web Scraping Ayarları
    scraper_class = fields.Char(
        string='Scraper Sınıfı',
        help='Web scraper sınıf adı (örn: TesanScraper, LinkTechScraper)',
    )
    scraping_config = fields.Text(
        string='Scraping Konfigürasyonu',
        help='JSON formatında scraper konfigürasyonu',
    )
    scraping_keywords = fields.Text(
        string='Arama Anahtar Kelimeleri',
        help='Ürün arama için anahtar kelimeler (satır başına bir)',
    )

    root_element = fields.Char(
        string='Kök Element (XPath)',
        default='//Product',
        help='Ürün elementlerinin XPath yolu. Örnek: //Products/Product veya //item',
    )

    # Durum
    state = fields.Selection([
        ('draft', 'Taslak'),
        ('active', 'Aktif'),
        ('error', 'Hata'),
        ('paused', 'Duraklatıldı'),
    ], string='Durum', default='draft', tracking=True)

    last_sync = fields.Datetime(
        string='Son Senkronizasyon',
        readonly=True,
    )
    last_error = fields.Text(
        string='Son Hata',
        readonly=True,
    )

    # İstatistikler
    product_count = fields.Integer(
        string='Ürün Sayısı',
        compute='_compute_counts',
    )
    log_count = fields.Integer(
        string='Log Sayısı',
        compute='_compute_counts',
    )

    # İlişkiler
    field_mapping_ids = fields.One2many(
        'xml.field.mapping',
        'source_id',
        string='Alan Eşleştirmeleri',
    )
    import_log_ids = fields.One2many(
        'xml.import.log',
        'source_id',
        string='İçe Aktarım Logları',
    )

    # Dropshipping Fiyatlandırma
    price_markup_type = fields.Selection([
        ('percent', 'Yüzde (%)'),
        ('fixed', 'Sabit Tutar'),
        ('both', 'Her İkisi'),
    ], string='Kar Tipi', default='percent')

    price_markup_percent = fields.Float(
        string='Kar Marjı (%)',
        default=30.0,
        help='Tedarikçi fiyatına eklenecek yüzde',
    )
    price_markup_fixed = fields.Float(
        string='Sabit Kar',
        default=0.0,
        help='Tedarikçi fiyatına eklenecek sabit tutar',
    )
    price_round = fields.Boolean(
        string='Fiyatı Yuvarla',
        default=True,
        help='Satış fiyatını yuvarla (örn: 149.99)',
    )
    price_round_method = fields.Selection([
        ('99', '.99 ile bitir'),
        ('90', '.90 ile bitir'),
        ('00', 'Tam sayı'),
        ('none', 'Yuvarlamadan'),
    ], string='Yuvarlama', default='99')

    min_price = fields.Float(
        string='Minimum Fiyat',
        help='Bu fiyatın altındaki ürünleri atla',
    )
    max_price = fields.Float(
        string='Maksimum Fiyat',
        help='Bu fiyatın üstündeki ürünleri atla',
    )
    min_stock = fields.Integer(
        string='Minimum Stok',
        default=0,  # ⚠️ 0 yapıldı - Dropshipping ürünler stok kontrolü yapmaz
        help='Bu stok miktarının altındaki ürünleri atla (0 = Tüm ürünleri al)',
    )

    # Senkronizasyon Ayarları
    auto_sync = fields.Boolean(
        string='Otomatik Senkronizasyon',
        default=True,
    )
    sync_interval = fields.Integer(
        string='Senkronizasyon Aralığı (saat)',
        default=6,
    )
    next_sync = fields.Datetime(
        string='Sonraki Senkronizasyon',
        compute='_compute_next_sync',
    )

    # İçe Aktarım Seçenekleri
    create_new_products = fields.Boolean(
        string='Yeni Ürün Oluştur',
        default=True,
        help='XML\'de olup Odoo\'da olmayan ürünler için stok kartı oluştur',
    )
    update_existing = fields.Boolean(
        string='Mevcut Ürünleri Güncelle',
        default=True,
        help='Odoo\'da mevcut ürünlerin bilgilerini güncelle',
    )
    update_price = fields.Boolean(
        string='Fiyat Güncelle',
        default=True,
    )
    update_stock = fields.Boolean(
        string='Stok Güncelle',
        default=True,
    )
    update_images = fields.Boolean(
        string='Görselleri Güncelle',
        default=True,
    )
    download_images = fields.Boolean(
        string='Görselleri İndir',
        default=False,
        help='Görselleri URL\'den indirip Odoo\'ya kaydet (kapalıysa sadece URL linki ile gösterilir)',
    )
    update_description = fields.Boolean(
        string='Açıklamaları Güncelle',
        default=True,
        help='Ürün açıklamalarını güncelle',
    )

    # Stok Sıfır Politikası
    deactivate_zero_stock = fields.Boolean(
        string='Stok 0 Olunca Satışa Kapat',
        default=False,  # ⚠️ KAPATILDI - Dropshipping ürünler için stok kontrolü yapılmaz
        help='Stok miktarı 0 olan ürünleri satışa kapat (sale_ok = False)',
    )
    delete_unsold_zero_stock = fields.Boolean(
        string='Satışı Olmayan 0 Stokları Sil',
        default=False,  # ⚠️ KAPATILDI - Hiçbir zaman ürün silmeyecek
        help='Stok 0 olduğunda ve hiç satışı olmayan ürünleri sistemden sil',
    )

    # Varyant Ayarları
    create_variants = fields.Boolean(
        string='Varyant Oluştur',
        default=True,
        help='Aynı SKU farklı barkod = Varyant olarak aç',
    )
    variant_from_parentheses = fields.Boolean(
        string='Parantezden Varyant',
        default=True,
        help='Ürün adındaki parantez içeriğini varyant olarak kullan. Örn: "BOLD SPEAKER (KIRMIZI)" → Ana ürün: BOLD SPEAKER, Varyant: KIRMIZI',
    )
    variant_attribute_name = fields.Char(
        string='Varyant Özellik Adı',
        default='Renk',
        help='Varyantlar için kullanılacak özellik adı (Renk, Beden, vb.)',
    )

    # Eşleştirme Önceliği (Yeni Sıralama)
    match_by_sku_prefix = fields.Boolean(
        string='SKU Prefix ile Eşleştir',
        default=True,
        help='Ürün kodunun ilk kelimesi ile eşleştir (öncelik 1)',
    )
    match_by_barcode = fields.Boolean(
        string='Barkod ile Eşleştir',
        default=True,
        help='Barkod ile eşleştir (öncelik 2)',
    )
    match_by_sku = fields.Boolean(
        string='Ürün Kodu ile Eşleştir (Tam)',
        default=True,
        help='Tam ürün kodu ile eşleştir',
    )
    match_by_description = fields.Boolean(
        string='Açıklama ile Eşleştir',
        default=True,
        help='Açıklama benzerliği veya açıklamada ürün kodu varsa eşleştir (öncelik 3)',
    )
    match_by_name = fields.Boolean(
        string='İsim ile Eşleştir',
        default=True,
    )
    name_match_ratio = fields.Integer(
        string='İsim Benzerlik Oranı (%)',
        default=80,
        help='İsim eşleştirmesi için minimum benzerlik oranı',
    )
    description_match_ratio = fields.Integer(
        string='Açıklama Benzerlik Oranı (%)',
        default=50,
        help='Açıklama eşleştirmesi için minimum benzerlik oranı',
    )
    update_only_if_value = fields.Boolean(
        string='Sadece Değer Varsa Güncelle',
        default=True,
        help='Fiyat/stok boşsa mevcut değeri değiştirme',
    )

    # Kategori Ayarları
    update_category = fields.Boolean(
        string='Kategori Güncelle',
        default=True,
        help='Mevcut ürünlerin kategorisini XML\'den güncelle',
    )
    auto_create_category = fields.Boolean(
        string='Kategori Otomatik Oluştur',
        default=True,
        help='XML\'de gelen kategori Odoo\'da yoksa otomatik oluştur',
    )
    category_separator = fields.Char(
        string='Kategori Ayracı',
        default=' > ',
        help='Kategori yolu için ayraç (örn: "Ana Kategori > Alt Kategori")',
    )
    category_mapping_ids = fields.One2many(
        'xml.category.mapping',
        'source_id',
        string='Kategori Eşleştirmeleri',
        help='XML kategorilerini Odoo kategorilerine eşleştir',
    )
    default_category_id = fields.Many2one(
        'product.category',
        string='Varsayılan Kategori',
        help='XML\'de kategori yoksa veya bulunamazsa kullanılacak kategori',
    )
    default_product_type = fields.Selection([
        ('consu', 'Stoklanan Ürün'),  # Odoo 19: 'product' -> 'consu'
        ('service', 'Hizmet'),
    ], string='Varsayılan Ürün Tipi', default='consu')

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTE METHODS
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_counts(self):
        for record in self:
            record.product_count = self.env['product.template'].search_count([
                ('xml_source_id', '=', record.id)
            ])
            record.log_count = self.env['xml.import.log'].search_count([
                ('source_id', '=', record.id)
            ])

    def _compute_next_sync(self):
        for record in self:
            if record.last_sync and record.auto_sync:
                record.next_sync = record.last_sync + timedelta(hours=record.sync_interval)
            else:
                record.next_sync = False

    # ══════════════════════════════════════════════════════════════════════════
    # TEMPLATE METHODS
    # ══════════════════════════════════════════════════════════════════════════

    @api.onchange('xml_template')
    def _onchange_xml_template(self):
        """Şablon değiştiğinde varsayılan mapping'leri ayarla"""
        template_roots = {
            'tsoft': 'product',
            'ticimax': '//Products/Product',
            'ideasoft': '//ProductList/Product',
            'akinsoft': '//urun',
            'eminonu': '//products/product',
            'google_rss': '//rss/channel/item',
            'opencart': '//products/product',
            'woocommerce': '//rss/channel/item',
            'woocommerce_api': '//products/product',
            'tesan_soap': '//Products/Product',
            'prestashop': '//products/product',
            'shopify': '//products/product',
            'magento': '//products/product',
            'google': '//feed/entry',
            'n11': '//Products/Product',
            'trendyol': '//items/item',
            'hepsiburada': '//products/product',
            'cimri': '//products/product',
            'akakce': '//Products/Product',
            'indexgrup': './/URUN',
            'netex': './/URUN',
            'baytek': '//Products/Product',
        }
        if self.xml_template and self.xml_template != 'custom':
            self.root_element = template_roots.get(self.xml_template, '//Product')

    def action_load_template_mappings(self):
        """Şablona göre varsayılan alan eşleştirmelerini yükle"""
        self.ensure_one()

        # Mevcut mapping'leri sil
        self.field_mapping_ids.unlink()

        # Şablona göre mapping'ler
        templates = {
            'tsoft': {
                'sku': 'ws_code',
                'barcode': 'barcode',
                'name': 'name',
                'description': 'detail',
                'price': 'price_special',
                'cost_price': 'price',
                'stock': 'stock',
                'category': 'category',
                'brand': 'brand',
                'image': 'picture1',
                'weight': 'weight',
                'deci': 'deci',
                'model': 'model',
                'currency': 'currency',
                'tax': 'tax',
            },
            'ticimax': {
                'sku': 'ProductCode',
                'barcode': 'Barcode',
                'name': 'ProductName',
                'description': 'Description',
                'price': 'Price1',
                'cost_price': 'BuyingPrice',
                'stock': 'Stock',
                'category': 'Category/CategoryName',
                'brand': 'Brand',
                'image': 'Images/Image/Path',
                'weight': 'Weight',
                'deci': 'Deci',
            },
            'ideasoft': {
                'sku': 'Code',
                'barcode': 'Barcode',
                'name': 'Name',
                'description': 'Details',
                'price': 'Price',
                'cost_price': 'CostPrice',
                'stock': 'Quantity',
                'category': 'Categories/Category',
                'brand': 'Brand',
                'image': 'Images/Image/Url',
                'weight': 'Weight',
            },
            'akinsoft': {
                'sku': 'STOK_KODU',
                'barcode': 'BARKODU',
                'name': 'STOK_ADI',
                'description': 'DETAY',
                'category': 'KATEGORI',
                'brand': 'MARKA',
                'image': 'GORSEL1',
                'image2': 'GORSEL2',
                'image3': 'GORSEL3',
                'image4': 'GORSEL4',
                'extra1': 'ALTKATEGORI',
            },
            'eminonu': {
                'sku': 'Urun_Kodu',
                'barcode': 'Urun_Kodu',
                'name': 'Urun_Adi',
                'description': 'Aciklama',
                'price': 'Fiyat',
                'cost_price': 'Fiyat',
                'stock': 'Stok',
                'category': 'Kategori',
                'brand': 'Marka',
                'image': 'resim1',
                'image2': 'resim2',
                'image3': 'resim3',
                'image4': 'resim4',
            },
            'google_rss': {
                'sku': 'model_number',
                'barcode': 'barcode',
                'name': 'title',
                'description': 'description',
                'price': 'price',
                'cost_price': 'price',
                'stock': 'quantity',
                'category': 'category',
                'brand': 'brand',
                'image': 'image_link',
                'image2': 'additional_image_link1',
                'image3': 'additional_image_link2',
                'image4': 'additional_image_link3',
                'extra1': 'product_type',
            },
            'opencart': {
                'sku': 'model',
                'barcode': 'ean',
                'name': 'name',
                'description': 'description',
                'price': 'price',
                'stock': 'quantity',
                'category': 'category',
                'image': 'image',
                'weight': 'weight',
            },
            'woocommerce': {
                'sku': 'g:id',
                'barcode': 'g:gtin',
                'name': 'title',
                'description': 'description',
                'price': 'g:price',
                'stock': 'g:availability',
                'category': 'g:product_type',
                'brand': 'g:brand',
                'image': 'g:image_link',
            },
            'woocommerce_api': {
                'sku': 'SKU',
                'barcode': 'Barcode',
                'name': 'Name',
                'description': 'Description',
                'price': 'Price',
                'cost_price': 'RegularPrice',
                'stock': 'Stock',
                'category': 'Category',
                'brand': 'Brand',
                'image': 'Image',
                'images': 'Images/Image',
                'currency': 'Currency',
                'extra1': 'Attributes',
            },
            'tesan_soap': {
                'sku': 'SKU',
                'barcode': 'Barcode',
                'name': 'Name',
                'description': 'Description',
                'price': 'Price',
                'cost_price': 'CostPrice',
                'stock': 'Stock',
                'category': 'Category',
                'brand': 'Brand',
                'image': 'Image',
                'images': 'Images/Image',
                'currency': 'Currency',
                'extra1': 'SubCategory',
            },
            'prestashop': {
                'sku': 'reference',
                'barcode': 'ean13',
                'name': 'name',
                'description': 'description',
                'price': 'price',
                'stock': 'quantity',
                'category': 'category',
                'image': 'image',
                'weight': 'weight',
            },
            'shopify': {
                'sku': 'sku',
                'barcode': 'barcode',
                'name': 'title',
                'description': 'body_html',
                'price': 'price',
                'stock': 'inventory_quantity',
                'category': 'product_type',
                'brand': 'vendor',
                'image': 'image/src',
            },
            'magento': {
                'sku': 'sku',
                'barcode': 'barcode',
                'name': 'name',
                'description': 'description',
                'price': 'price',
                'stock': 'qty',
                'category': 'category',
                'image': 'image',
                'weight': 'weight',
            },
            'google': {
                'sku': 'g:id',
                'barcode': 'g:gtin',
                'name': 'title',
                'description': 'content',
                'price': 'g:price',
                'category': 'g:google_product_category',
                'brand': 'g:brand',
                'image': 'g:image_link',
            },
            'n11': {
                'sku': 'productSellerCode',
                'barcode': 'barcode',
                'name': 'title',
                'description': 'description',
                'price': 'price',
                'stock': 'quantity',
                'category': 'category/name',
                'image': 'images/image/url',
            },
            'trendyol': {
                'sku': 'stockCode',
                'barcode': 'barcode',
                'name': 'title',
                'description': 'description',
                'price': 'salePrice',
                'cost_price': 'listPrice',
                'stock': 'quantity',
                'category': 'categoryName',
                'brand': 'brand',
                'image': 'images/url',
            },
            'hepsiburada': {
                'sku': 'merchantSku',
                'barcode': 'barcode',
                'name': 'productName',
                'description': 'description',
                'price': 'price',
                'stock': 'availableStock',
                'category': 'categoryName',
                'image': 'image',
            },
            'cimri': {
                'sku': 'merchantItemId',
                'barcode': 'gtin',
                'name': 'name',
                'description': 'description',
                'price': 'price',
                'stock': 'availability',
                'category': 'category',
                'brand': 'brand',
                'image': 'imageUrl',
            },
            'akakce': {
                'sku': 'Code',
                'barcode': 'Barcode',
                'name': 'Name',
                'price': 'Price',
                'stock': 'Stock',
                'category': 'Category',
                'brand': 'Brand',
                'image': 'Image',
            },
            'indexgrup': {
                'sku': '@GLOBALKOD',
                'barcode': '@BARCODE',
                'name': '@AD',
                'brand': '@MARKA',
                'category': '@_KATEGORI',
                'extra1': '@_GRUP',
                'tax': 'VERGI',
                'image': 'RESIM',
            },
            'netex': {
                'sku': '@GLOBALKOD',
                'barcode': '@BARCODE',
                'name': '@AD',
                'brand': '@MARKA',
                'category': '@_KATEGORI',
                'extra1': '@_GRUP',
                'tax': 'VERGI',
                'image': 'RESIM',
            },
            'baytek': {
                'sku': 'ProductCode',
                'barcode': 'Barcode',
                'name': 'ProductName',
                'description': 'Description',
                'stock': 'Quantity',
                'cost_price': 'Price',
                'category': 'Category',
                'brand': 'Brand',
                'image': 'Image1',
                'image2': 'Image2',
                'image3': 'Image3',
                'image4': 'Image4',
                'tax': 'TaxRate',
            },
        }

        mapping_data = templates.get(self.xml_template, {})

        for odoo_field, xml_path in mapping_data.items():
            self.env['xml.field.mapping'].create({
                'source_id': self.id,
                'odoo_field': odoo_field,
                'xml_path': xml_path,
            })

        category_count = 0
        auto_matched_count = 0
        category_warning = None
        try:
            category_count, auto_matched_count = self._sync_template_category_mappings(mapping_data)
        except UserError as exc:
            category_warning = str(exc)
        except Exception as exc:
            _logger.warning("Şablon kategori eşlemeleri yüklenemedi (%s): %s", self.name, exc)
            category_warning = str(exc)

        message = _('%s alan eşleştirmesi yüklendi.') % len(mapping_data)
        if category_count:
            message += ' ' + _('%s XML kategorisi kategori eşleme sekmesine eklendi.') % category_count
        if auto_matched_count:
            message += ' ' + _('%s kategori otomatik eşleştirildi.') % auto_matched_count
        elif category_warning:
            message += ' ' + _('Kategori eşlemeleri yüklenemedi: %s') % category_warning

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Başarılı'),
                'message': message,
                'type': 'warning' if category_warning else 'success',
                'sticky': bool(category_warning),
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('XML Kaynağı'),
                    'res_model': 'xml.product.source',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'views': [(False, 'form')],
                    'target': 'current',
                },
            }
        }

    def _normalize_category_name(self, value):
        """Kategori adlarını kaba eşleştirme için normalize et."""
        value = (value or '').strip()
        if not value:
            return ''
        translate_map = str.maketrans({
            'Ç': 'c', 'ç': 'c',
            'Ğ': 'g', 'ğ': 'g',
            'I': 'i', 'İ': 'i', 'ı': 'i',
            'Ö': 'o', 'ö': 'o',
            'Ş': 's', 'ş': 's',
            'Ü': 'u', 'ü': 'u',
        })
        value = value.translate(translate_map).lower()
        value = re.sub(r'[^a-z0-9]+', ' ', value)
        return ' '.join(value.split())

    def _split_xml_category_path(self, xml_category):
        """XML kategori yolunu segmentlere ayır."""
        xml_category = (xml_category or '').strip()
        if not xml_category:
            return []

        separators = []
        if self.category_separator:
            separators.append(re.escape(self.category_separator))
        separators.extend([r'\s*>\s*', r'\s*/\s*', r'\s*\|\s*'])
        parts = re.split('|'.join(dict.fromkeys(separators)), xml_category)
        return [part.strip() for part in parts if part and part.strip()]

    def _normalized_category_key(self, category_name):
        """Kategori adını karşılaştırma için normalize eder."""
        return self._normalize_category_name(category_name)

    def _public_category_path_from_xml(self, xml_category):
        """TV Shop kurallarına göre XML kategorisini e-ticaret kategorisi yoluna çevir."""
        parts = self._split_xml_category_path(xml_category)
        if not parts:
            return []

        def _normalize_label(label):
            return self._normalized_category_key(label or '')

        if len(parts) > 3:
            parts = parts[:3]

        root_map = {
            _normalize_label('Ev ve Yaşam'): 'Ev & Yaşam',
            _normalize_label('Evcil Hayvan Ürünleri'): 'Evcil Hayvan Ürünleri',
            _normalize_label('Kozmetik'): 'Kozmetik & Kişisel Bakım',
            _normalize_label('Oto Aksesuar Ürünleri'): 'Oto Aksesuarları',
            _normalize_label('Outdoor Ürünleri'): 'Outdoor & Kamp',
            _normalize_label('Hırdavat Malzemeleri'): 'Hırdavat',
            _normalize_label('Oyuncak & Kırtasiye'): 'Oyuncak & Kırtasiye',
            _normalize_label('Parti & Organizasyon'): 'Parti & Organizasyon',
            _normalize_label('Hediyelik Eşya Ürünleri'): 'Hediyelik Eşya',
            _normalize_label('Promosyon Ürünleri'): 'Promosyon Ürünleri',
            _normalize_label('Spor ve Sağlık Ürünleri'): 'Spor & Sağlık',
            _normalize_label('Takı ve Aksesuar Ürünleri'): 'Takı & Moda Aksesuar',
            _normalize_label('Telefon - Tablet Aksesuar'): 'Telefon & Tablet Aksesuarları',
            _normalize_label('Özel Ürünler'): 'Özel Ürünler',
            _normalize_label('Tv Shop Ürünleri'): 'TV SHOP',
        }

        normalized_root = _normalize_label(parts[0])
        public_root = root_map.get(normalized_root)
        if not public_root:
            public_root = parts[0].strip()

        if public_root == 'TV SHOP':
            if len(parts) < 2:
                return [public_root]
            tv_sub = _normalize_label(parts[1])
            tv_shop_map = {
                _normalize_label('Elektronik Malzeme'): ('Elektronik & Hobi', 'Elektronik Malzeme'),
                _normalize_label('Hobi'): ('Elektronik & Hobi', 'Hobi'),
                _normalize_label('Kişisel Bakım Ürünleri'): ('Kozmetik & Kişisel Bakım', 'Kişisel Bakım Ürünleri'),
                _normalize_label('Masaj Aletleri'): ('Kozmetik & Kişisel Bakım', 'Masaj Aletleri'),
                _normalize_label('Pratik Ev Aletleri'): ('Ev & Yaşam', 'Pratik Ev Aletleri'),
                _normalize_label('Pratik Mutfak Aletleri'): ('Ev & Yaşam', 'Mutfak'),
                _normalize_label('Sağlık Bakım Kozmetik'): ('Spor & Sağlık', 'Sağlık Bakım Kozmetik'),
                _normalize_label('Spor Ürünleri'): ('Spor & Sağlık', 'Spor Ürünleri'),
                _normalize_label('Temizlik Aletleri'): ('Ev & Yaşam', 'Temizlik Aletleri'),
                _normalize_label('Tv Shop Oto'): ('Oto Aksesuarları',),
            }
            mapped_path = tv_shop_map.get(tv_sub, ())
            if not mapped_path:
                return []
            return list(mapped_path)

        cleaned = [p for p in [public_root] + parts[1:] if p]
        return cleaned[:3]

    def _find_public_category_path(self, parts):
        """E-ticaret public kategoriyi sadece mevcutsa döndürür. Asla oluşturmaz."""
        self.ensure_one()
        if not parts:
            return self.env['product.public.category'].browse()

        PublicCategory = self.env['product.public.category']
        parent = False
        current_path = []

        for name in parts:
            name = (name or '').strip()
            if not name:
                continue
            current_path.append(name)
            domain = [('name', '=', name)]
            if parent:
                domain.append(('parent_id', '=', parent.id))
            else:
                domain.append(('parent_id', '=', False))

            category = PublicCategory.search(domain, limit=1)
            if not category:
                _logger.info(
                    'E-ticaret kategorisi bulunamadı, otomatik oluşturma kapalı: %s',
                    ' > '.join(current_path)
                )
                return self.env['product.public.category'].browse()
            parent = category

        return parent

    def action_sync_ecommerce_categories(self):
        """XML kategori maplerinden e-ticaret kategorilerini oluştur ve eşleştir."""
        self.ensure_one()
        force_sync = bool(self.env.context.get('force_ecommerce_sync', True))

        mappings = self.env['xml.category.mapping'].search([
            ('source_id', '=', self.id),
        ], order='xml_category')

        if not mappings:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Eşleme Kaydı Yok'),
                    'message': _('Önce "Şablon Yükle" ile kategori eşleştirmeleri oluşturun.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }

        created_count = 0
        assigned_count = 0
        for mapping in mappings:
            public_path = self._public_category_path_from_xml(mapping.xml_category)
            if not public_path:
                continue
            public_category = self._find_public_category_path(public_path)
            if public_category and (force_sync or not mapping.ecommerce_category_ids):
                mapping.ecommerce_category_ids = [(6, 0, public_category.ids)]
                assigned_count += 1

            if public_category:
                created_count += 1

        message = _('%s kategori kaydı işlendi, %s ürün eşleşmesine e-ticaret kategorisi atandı.') % (
            len(mappings), assigned_count,
        )
        if created_count == 0 and assigned_count == 0:
            message = _('E-ticaret kategorisi için yeni bir eşleme bulunamadı.')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('E-Ticaret Kategorileri'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }

    def _category_alias_map(self):
        """XML kategori isimlerini mevcut kategori ağacına yaklaştır."""
        return {
            'akilli teknolojiler': 'Akıllı Teknolojiler',
            'aparat ceviriciler': 'Dönüştürücüler',
            'donusturucu aparatlar': 'Dönüştürücüler',
            'mini aparat ceviriciler': 'Dönüştürücüler',
            'arac aksesuarlari': 'Araç Aksesuarları',
            'arac sarjlari': 'Araç Şarjları',
            'hizli arac sarjlari': 'Araç Şarjları',
            'super hizli arac sarjlari': 'Süper Hızlı Şarjlar',
            'bluetooth kulakliklar': 'Kulaklıklar',
            'bt kulakliklar kulak ustu': 'Bluetooth Kulak Üstü',
            'bt kulakliklar kulak ici': 'Bluetooth Kulak İçi',
            'bluetooth speakerlar': 'Hoparlörler',
            'speakerlar': 'Hoparlörler',
            'kablosuz hoparloler': 'Taşınabilir Hoparlörler',
            'ses bombalari': 'Taşınabilir Hoparlörler',
            'ses sistemleri': 'Ses Sistemleri',
            'depolama aygitlari': 'Depolama',
            'micro': 'Hafıza Kartları',
            'micro elt': 'Hafıza Kartları',
            'micro prm': 'Hafıza Kartları',
            'otg iphone': 'Dönüştürücüler',
            'otg type c': 'Dönüştürücüler',
            'usb': 'USB Flash Bellek',
            'usb mini': 'USB Flash Bellek',
            'usb prm': 'USB Flash Bellek',
            'ev sarjlari': 'Şarj Cihazları',
            'duvar sarjlari': 'Duvar Şarjları',
            'hizli sarjlar': 'Süper Hızlı Şarjlar',
            'super hizli sarjlar': 'Süper Hızlı Şarjlar',
            'kablolar': 'Kablolar',
            'guc ve veri aktarim kablolari': 'Güç ve Veri Kabloları',
            'guc ve veri aktarim kablolari 2 m': 'Güç ve Veri Kabloları',
            'ses aktarim kablolari': 'Ses Kabloları',
            'yuksek hizli kablolar': 'Hızlı Şarj Kabloları',
            'kablolu kulakliklar': 'Kablolu Kulaklıklar',
            'kablolu kulakliklar 3 5 mm': 'Kablolu Kulaklıklar',
            'powerbanklar': 'Powerbanklar',
            'super hizli powerbanklar': 'Süper Hızlı Powerbanklar',
            'tablet aksesuarlari': 'Tablet Aksesuarları',
            'tabletler': 'Tabletler',
            'telefon aksesuarlari': 'Telefon Aksesuarları',
            'masa ustu standlar': 'Telefon Aksesuarları',
            'mobil cihaz aksesuarlari': 'Mobil Cihaz Aksesuarları',
        }

    def _find_matching_category_records(self, xml_category):
        """XML kategori adına göre en uygun iç ve website kategorilerini bul."""
        alias_map = self._category_alias_map()
        parts = self._split_xml_category_path(xml_category)
        normalized_parts = [self._normalize_category_name(part) for part in parts]

        candidates = []
        if xml_category:
            candidates.append(xml_category.strip())
        for normalized in reversed(normalized_parts):
            if normalized in alias_map:
                candidates.append(alias_map[normalized])
        for part in reversed(parts):
            candidates.append(part)

        seen = set()
        ordered_candidates = []
        for candidate in candidates:
            norm = self._normalize_category_name(candidate)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            ordered_candidates.append(candidate)

        ProductCategory = self.env['product.category']
        PublicCategory = self.env['product.public.category']

        product_category = False
        ecommerce_categories = PublicCategory.browse()

        for candidate in ordered_candidates:
            if not product_category:
                product_category = ProductCategory.search([('name', 'ilike', candidate)], limit=1)
            if not ecommerce_categories:
                ecommerce_categories = PublicCategory.search([('name', 'ilike', candidate)], limit=1)
            if product_category and ecommerce_categories:
                break

        return product_category, ecommerce_categories

    def _sync_template_category_mappings(self, mapping_data):
        """Şablon yüklendikten sonra XML içindeki kategorileri kategori eşleme sekmesine taşı."""
        self.ensure_one()

        category_path = mapping_data.get('category')
        if not category_path or not self.xml_url:
            return 0, 0

        subcategory_path = mapping_data.get('extra1')
        xml_content = self._fetch_xml()
        products = self._parse_xml(xml_content)
        if not products:
            return 0

        separator = self.category_separator or ' > '
        category_values = set()
        for element in products:
            category_name = self._get_element_value(element, category_path)
            subcategory_name = self._get_element_value(element, subcategory_path) if subcategory_path else None

            if not category_name:
                continue

            category_name = str(category_name).strip()
            subcategory_name = str(subcategory_name).strip() if subcategory_name else ''
            if not category_name:
                continue

            full_path = category_name
            if subcategory_name:
                full_path = f"{category_name}{separator}{subcategory_name}"
            category_values.add(full_path)

        if not category_values:
            return 0, 0

        Mapping = self.env['xml.category.mapping']
        existing_rows = Mapping.search_read(
            [('source_id', '=', self.id), ('xml_category', 'in', list(category_values))],
            ['xml_category', 'odoo_category_id', 'ecommerce_category_ids'],
        )
        existing_by_category = {
            row['xml_category']: row for row in existing_rows if row.get('xml_category')
        }

        to_create = sorted(category_values - set(existing_by_category))
        start_sequence = 10 * (len(existing_rows) + 1)
        auto_matched_count = 0

        for index, xml_category in enumerate(to_create):
            product_category, ecommerce_categories = self._find_matching_category_records(xml_category)
            ecommerce_path = self._public_category_path_from_xml(xml_category)
            if ecommerce_path:
                ecommerce_category = self._find_public_category_path(ecommerce_path)
                if ecommerce_category:
                    ecommerce_categories = ecommerce_category
            Mapping.create({
                'source_id': self.id,
                'sequence': start_sequence + (index * 10),
                'xml_category': xml_category,
                'match_type': 'contains',
                'odoo_category_id': product_category.id if product_category else False,
                'ecommerce_category_ids': [(6, 0, ecommerce_categories.ids)] if ecommerce_categories else False,
                'active': True,
            })
            if product_category or ecommerce_categories:
                auto_matched_count += 1

        existing_mappings = Mapping.search([
            ('source_id', '=', self.id),
            ('xml_category', 'in', list(category_values)),
        ])
        for mapping in existing_mappings:
            vals = {}
            if not mapping.odoo_category_id or not mapping.ecommerce_category_ids:
                product_category, ecommerce_categories = self._find_matching_category_records(mapping.xml_category)
                if not ecommerce_categories:
                    ecommerce_path = self._public_category_path_from_xml(mapping.xml_category)
                    if ecommerce_path:
                        ecommerce_category = self._find_public_category_path(ecommerce_path)
                        if ecommerce_category:
                            ecommerce_categories = ecommerce_category
                if not mapping.odoo_category_id and product_category:
                    vals['odoo_category_id'] = product_category.id
                if not mapping.ecommerce_category_ids and ecommerce_categories:
                    vals['ecommerce_category_ids'] = [(6, 0, ecommerce_categories.ids)]
            if vals:
                mapping.write(vals)
                auto_matched_count += 1

        return len(to_create), auto_matched_count

    # ══════════════════════════════════════════════════════════════════════════
    # XML PARSING
    # ══════════════════════════════════════════════════════════════════════════

    def _fetch_xml(self):
        """XML'i URL'den çek"""
        self.ensure_one()

        try:
            if self.xml_template == 'woocommerce_api':
                return self._fetch_woocommerce_api_xml()
            if self.xml_template == 'tesan_soap':
                return self._fetch_tesan_soap_xml()

            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/133.0.0.0 Safari/537.36'
                ),
                'Accept': 'application/xml, text/xml, application/xhtml+xml, text/html;q=0.9, */*;q=0.8',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
            }

            auth = None
            if self.xml_username and self.xml_password:
                auth = (self.xml_username, self.xml_password)

            # Bazı XML servisleri yavaş yanıt verebiliyor; timeout + retry ile daha stabil çalıştır.
            # timeout=(connect, read)
            last_exc = None
            response = None
            session = requests.Session()
            last_text = None
            for attempt in range(1, 4):
                try:
                    # Bazı OpenCart tabanlı feedlerde session/referer beklenebiliyor.
                    if 'tahtakale' in (self.xml_url or '').lower():
                        try:
                            home_url = 'https://www.tahtakaletoptanticaret.com/'
                            session.get(home_url, headers=headers, timeout=(15, 60))
                        except Exception:
                            pass

                    response = session.get(
                        self.xml_url,
                        headers=headers,
                        auth=auth,
                        allow_redirects=True,
                        timeout=(15, 600),
                    )
                    response.raise_for_status()
                    last_text = response.text or ''
                    if 'Maximum sınıra ulaştınız' in last_text and attempt < 3:
                        time.sleep(5 * attempt)
                        continue
                    break
                except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                    last_exc = e
                    if attempt >= 3:
                        raise
                    time.sleep(2 if attempt == 1 else 5)
            if response is None and last_exc:
                raise last_exc

            # Encoding düzeltme - content bytes olarak al
            # XML header'dan encoding'i oku
            content = response.content

            # XML declaration'dan encoding tespit et
            encoding = 'utf-8'
            if content.startswith(b'<?xml'):
                match = re.search(rb'encoding=["\']([^"\']+)["\']', content[:200])
                if match:
                    encoding = match.group(1).decode('ascii').lower()
                    _logger.debug(f"XML encoding tespit edildi: {encoding}")

            # Türkçe karakter sorunları için encoding denemeleri
            try:
                # Önce belirtilen encoding'i dene
                xml_text = content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                # Hata varsa sırayla encoding'leri dene
                for enc in ['utf-8', 'iso-8859-9', 'windows-1254', 'latin1']:
                    try:
                        xml_text = content.decode(enc)
                        _logger.info(f"XML {enc} encoding ile decode edildi")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # Hiçbiri çalışmazsa hataları ignore et
                    xml_text = content.decode('utf-8', errors='ignore')
                    _logger.warning("XML decode hatası - bazı karakterler kaybolabilir")

            stripped = (xml_text or '').lstrip().lstrip('﻿')
            content_type = (response.headers.get('Content-Type') or '').lower()
            if not stripped.startswith('<') or content_type.startswith('text/html'):
                preview = stripped[:200].replace('\n', ' ').strip()
                raise UserError(
                    _('XML yerine HTML/metin yaniti dondu. Icerik: %s') % (preview or _('Bos yanit'))
                )

            return xml_text

        except requests.exceptions.RequestException as e:
            raise UserError(_('XML çekilemedi: %s') % str(e))

    def _build_woocommerce_api_url(self, page=1, per_page=100):
        """WooCommerce Store API URL'ine sayfalama parametreleri ekle."""
        parsed = urlparse((self.xml_url or '').strip())
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query['page'] = str(page)
        query['per_page'] = str(per_page)
        new_query = urlencode(query)
        return urlunparse(parsed._replace(query=new_query))

    def _fetch_woocommerce_api_xml(self):
        """WooCommerce Store API'den ürünleri çekip normalize XML'e dönüştür."""
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/133.0.0.0 Safari/537.36'
            ),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }
        auth = None
        if self.xml_username and self.xml_password:
            auth = (self.xml_username, self.xml_password)

        session = requests.Session()
        products = []
        page = 1
        per_page = 100

        while True:
            url = self._build_woocommerce_api_url(page=page, per_page=per_page)
            response = session.get(
                url,
                headers=headers,
                auth=auth,
                allow_redirects=True,
                timeout=(15, 180),
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise UserError(_('WooCommerce API listesi bekleniyordu, farkli veri dondu.'))

            if not payload:
                break

            products.extend(payload)
            total_pages = response.headers.get('X-WP-TotalPages')
            if total_pages and page >= int(total_pages):
                break
            if len(payload) < per_page:
                break
            page += 1

        xml_text = self._woocommerce_api_payload_to_xml(products, session, headers, auth)
        _logger.info("WooCommerce API: %d ürün/variasyon normalize edildi", len(products))
        return xml_text

    def _woocommerce_api_payload_to_xml(self, products, session, headers, auth):
        """WooCommerce Store API ürün listesini standart XML parse akışına uydur."""

        def _minor_to_price(price_info):
            if not price_info:
                return ''
            minor_unit = int(price_info.get('currency_minor_unit') or 0)
            raw = str(price_info.get('price') or price_info.get('regular_price') or '0').strip()
            if not raw:
                return ''
            try:
                raw_int = int(raw)
                return str(raw_int / (10 ** minor_unit))
            except Exception:
                return raw

        def _minor_to_regular(price_info):
            if not price_info:
                return ''
            minor_unit = int(price_info.get('currency_minor_unit') or 0)
            raw = str(price_info.get('regular_price') or price_info.get('price') or '0').strip()
            if not raw:
                return ''
            try:
                raw_int = int(raw)
                return str(raw_int / (10 ** minor_unit))
            except Exception:
                return raw

        def _choose_category(product_data):
            categories = product_data.get('categories') or []
            if not categories:
                return ''
            names = [c.get('name') for c in categories if c.get('name')]
            return names[-1] if names else ''

        def _brand_name(product_data):
            brands = product_data.get('brands') or []
            return (brands[0].get('name') if brands and brands[0].get('name') else '')

        def _attributes_text(product_data):
            attrs = []
            for attr in product_data.get('attributes') or []:
                terms = [term.get('name') for term in (attr.get('terms') or []) if term.get('name')]
                if terms:
                    attrs.append('%s: %s' % (attr.get('name') or '', ', '.join(terms)))
            return ' | '.join([item for item in attrs if item])

        def _image_urls(product_data):
            urls = []
            for image in product_data.get('images') or []:
                src = (image.get('src') or '').strip()
                if src and src not in urls:
                    urls.append(src)
            return urls

        def _variation_label(parent_product, variation_data):
            attrs = variation_data.get('variation') or variation_data.get('attributes') or []
            if isinstance(attrs, str):
                return attrs.replace(':', ': ').strip()
            attr_terms = {attr.get('taxonomy'): {term.get('slug'): term.get('name') for term in (attr.get('terms') or [])}
                          for attr in (parent_product.get('attributes') or []) if attr.get('taxonomy')}
            labels = []
            for attr in attrs:
                if not isinstance(attr, dict):
                    continue
                name = (attr.get('name') or '').strip()
                value = (attr.get('value') or '').strip()
                mapped = attr_terms.get(name, {}).get(value)
                if mapped:
                    value = mapped
                value = value.replace('-', ' ').strip()
                if value:
                    labels.append(value.upper() if value.islower() else value)
            return ' / '.join(labels)

        def _fetch_variation(variation_id):
            base_url = (self.xml_url or '').split('?')[0].rstrip('/')
            response = session.get(
                '%s/%s' % (base_url, variation_id),
                headers=headers,
                auth=auth,
                allow_redirects=True,
                timeout=(15, 120),
            )
            response.raise_for_status()
            return response.json()

        root = ET.Element('products')

        for product in products:
            ptype = (product.get('type') or '').strip().lower()
            if ptype == 'variation':
                continue

            rows = []
            if ptype == 'variable' and product.get('variations'):
                for variation_ref in product.get('variations') or []:
                    variation_id = variation_ref.get('id')
                    if not variation_id:
                        continue
                    try:
                        variation = _fetch_variation(variation_id)
                    except Exception as exc:
                        _logger.warning("WooCommerce variation okunamadi (%s): %s", variation_id, exc)
                        continue
                    label = _variation_label(product, variation)
                    rows.append({
                        'external_id': str(product.get('id') or ''),
                        'stock_id': str(variation.get('id') or ''),
                        'variant_group': str(product.get('id') or product.get('sku') or ''),
                        'name': '%s (%s)' % (product.get('name') or '', label) if label else (product.get('name') or ''),
                        'sku': (variation.get('sku') or product.get('sku') or '').strip(),
                        'barcode': '',
                        'description': variation.get('description') or product.get('description') or '',
                        'short_description': variation.get('short_description') or product.get('short_description') or '',
                        'price': _minor_to_price(variation.get('prices') or {}),
                        'regular_price': _minor_to_regular(variation.get('prices') or product.get('prices') or {}),
                        'stock': '1' if variation.get('is_in_stock') else '0',
                        'currency': (variation.get('prices') or product.get('prices') or {}).get('currency_code') or '',
                        'category': _choose_category(product),
                        'brand': _brand_name(product),
                        'attributes': _attributes_text(product),
                        'images': _image_urls(variation) or _image_urls(product),
                    })
            else:
                rows.append({
                    'external_id': str(product.get('id') or ''),
                    'stock_id': str(product.get('id') or ''),
                    'variant_group': str(product.get('id') or product.get('sku') or ''),
                    'name': product.get('name') or '',
                    'sku': (product.get('sku') or '').strip(),
                    'barcode': '',
                    'description': product.get('description') or '',
                    'short_description': product.get('short_description') or '',
                    'price': _minor_to_price(product.get('prices') or {}),
                    'regular_price': _minor_to_regular(product.get('prices') or {}),
                    'stock': '1' if product.get('is_in_stock') else '0',
                    'currency': (product.get('prices') or {}).get('currency_code') or '',
                    'category': _choose_category(product),
                    'brand': _brand_name(product),
                    'attributes': _attributes_text(product),
                    'images': _image_urls(product),
                })

            for row in rows:
                item = ET.SubElement(root, 'product')
                for key, value in (
                    ('SKU', row['sku']),
                    ('Barcode', row['barcode']),
                    ('Name', row['name']),
                    ('Price', row['price']),
                    ('RegularPrice', row['regular_price']),
                    ('Stock', row['stock']),
                    ('Category', row['category']),
                    ('Brand', row['brand']),
                    ('Currency', row['currency']),
                    ('Attributes', row['attributes']),
                    ('ExternalProductId', row['external_id']),
                    ('SourceStockId', row['stock_id']),
                    ('VariantGroup', row['variant_group']),
                    ('UsageClass', 'commercial'),
                ):
                    child = ET.SubElement(item, key)
                    child.text = value or ''

                desc = ET.SubElement(item, 'Description')
                desc.text = row['description'] or ''
                short_desc = ET.SubElement(item, 'ShortDescription')
                short_desc.text = row['short_description'] or ''

                if row['images']:
                    img = ET.SubElement(item, 'Image')
                    img.text = row['images'][0]
                    images_el = ET.SubElement(item, 'Images')
                    for image_url in row['images']:
                        img_el = ET.SubElement(images_el, 'Image')
                        img_el.text = image_url

        return ET.tostring(root, encoding='unicode')

    def _fetch_tesan_soap_xml(self):
        """Tesan SOAP servislerinden ürün verilerini çekip normalize XML'e dönüştür."""

        namespace = (self.soap_namespace or 'http://tempuri.org/').strip()
        method_products = (self.soap_method_products or 'GetProductLists').strip()
        method_prices = (self.soap_method_prices or 'GetStockPrices').strip()
        method_stock = (self.soap_method_stock or 'GetWareHouseStocks').strip()
        method_images = (self.soap_method_images or 'GetProductImages').strip()
        method_features = (self.soap_method_features or 'GetProductFeatures').strip()
        method_categories = (self.soap_method_categories or 'GetProductCategories').strip()
        product_element = (self.soap_product_element or 'ProductList').strip()
        extra_body = (self.soap_extra_body or '<_departman>0</_departman>').strip()

        def _soap_url():
            return (self.xml_url or 'http://www.tesaniletisim.com/webservice/ProductServices.asmx').strip()

        def _soap_envelope(method, body_xml=''):
            header = (
                '<soap:Header>'
                '<AuthUsers xmlns="%s">'
                '<userName>%s</userName>'
                '<password>%s</password>'
                '<token>%s</token>'
                '</AuthUsers>'
                '</soap:Header>'
            ) % (
                namespace,
                self.xml_username or '',
                self.xml_password or '',
                self.xml_token or '',
            )
            body = '<soap:Body><%s xmlns="%s">%s</%s></soap:Body>' % (
                method,
                namespace,
                body_xml or '',
                method,
            )
            return (
                '<?xml version="1.0" encoding="utf-8"?>'
                '<soap:Envelope '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
                'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
                '%s%s</soap:Envelope>'
            ) % (header, body)

        def _soap_call(method, body_xml=''):
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '%s/%s' % (namespace.rstrip('/'), method),
                'User-Agent': 'mobilsoft_xml_import/tesan_soap',
            }
            auth = None
            if self.xml_username and self.xml_password:
                auth = (self.xml_username, self.xml_password)
            response = requests.post(
                _soap_url(),
                data=_soap_envelope(method, body_xml).encode('utf-8'),
                headers=headers,
                auth=auth,
                timeout=(15, 300),
            )
            response.raise_for_status()
            return ET.fromstring(response.text)

        def _strip_ns(elem):
            for el in elem.iter():
                if '}' in el.tag:
                    el.tag = el.tag.split('}', 1)[1]

        def _get_text(parent, tag, default=''):
            el = parent.find(tag)
            if el is None or el.text is None:
                return default
            return el.text.strip()

        def _parse_categories(root):
            _strip_ns(root)
            items = []
            for cat in root.findall('.//%sResult/ProductCategory' % method_categories):
                items.append({
                    'LowerGroupId': _get_text(cat, 'LowerGroupId'),
                    'MainGroup': _get_text(cat, 'MainGroup'),
                    'LowerGroup': _get_text(cat, 'LowerGroup'),
                    'Departman': _get_text(cat, 'Departman'),
                    'ProductCatId': _get_text(cat, 'ProductCatId'),
                    'ProductCat': _get_text(cat, 'ProductCat'),
                    'ProductTypeId': _get_text(cat, 'ProductTypeId'),
                    'ProductType': _get_text(cat, 'ProductType'),
                    'BrandId': _get_text(cat, 'BrandId'),
                    'Brand': _get_text(cat, 'Brand'),
                })
            return items

        def _parse_product_list(root):
            _strip_ns(root)
            items = []
            for product in root.findall('.//%sResult/%s' % (method_products, product_element)):
                items.append({
                    'StockId': _get_text(product, 'StockId'),
                    'StockCode': _get_text(product, 'StockCode'),
                    'ProductCode': _get_text(product, 'ProductCode'),
                    'Product': _get_text(product, 'Product'),
                    'Unit': _get_text(product, 'Unit'),
                    'Tax': _get_text(product, 'Tax'),
                    'LowerGroupId': _get_text(product, 'LowerGroupId'),
                    'SpecialCode': _get_text(product, 'SpecialCode'),
                    'ProductCatId': _get_text(product, 'ProductCatId'),
                    'ProductTypeId': _get_text(product, 'ProductTypeId'),
                    'BrandId': _get_text(product, 'BrandId'),
                    'ProductId': _get_text(product, 'ProductId'),
                    'ProductStatus': _get_text(product, 'ProductStatus'),
                    'StockStatus': _get_text(product, 'StockStatus'),
                    'Barcode': _get_text(product, 'Barcode'),
                })
            return items

        def _parse_features(root):
            _strip_ns(root)
            out = {}
            for feat in root.findall('.//%sResult/ProductFeatures' % method_features):
                product_id = _get_text(feat, 'ProductId')
                features = _get_text(feat, 'Features')
                if product_id and features:
                    out[product_id] = html.unescape(features)
            return out

        def _parse_images(root):
            _strip_ns(root)
            out = {}
            for image in root.findall('.//%sResult/ProductImages' % method_images):
                stock_id = _get_text(image, 'StockId')
                url = _get_text(image, 'Image')
                if stock_id and url:
                    out.setdefault(stock_id, []).append(url)
            return out

        def _parse_prices(root):
            _strip_ns(root)
            out = {}
            for price in root.findall('.//%sResult/StockPrice' % method_prices):
                stock_id = _get_text(price, 'StockId')
                product_id = _get_text(price, 'ProductId')
                if stock_id and product_id:
                    out[(stock_id, product_id)] = {
                        'Price': _get_text(price, 'Price'),
                        'Currency': _get_text(price, 'Currency'),
                        'StandartPrice': _get_text(price, 'StandartPrice'),
                        'StandartPriceCurrency': _get_text(price, 'StandartPriceCurrency'),
                    }
            return out

        def _parse_stocks(root):
            _strip_ns(root)
            out = {}
            for stock in root.findall('.//%sResult/WareHouseStock' % method_stock):
                stock_id = _get_text(stock, 'StockId')
                product_id = _get_text(stock, 'ProductId')
                qty = _get_text(stock, 'Quantity')
                if not stock_id or not product_id:
                    continue
                try:
                    quantity = int(float(qty))
                except Exception:
                    quantity = 0
                key = (stock_id, product_id)
                out[key] = out.get(key, 0) + quantity
            return out

        def _best_category(categories, product):
            if not categories:
                return {}
            full_key = (
                product.get('LowerGroupId'),
                product.get('ProductCatId'),
                product.get('ProductTypeId'),
                product.get('BrandId'),
            )
            for category in categories:
                if (
                    category.get('LowerGroupId'),
                    category.get('ProductCatId'),
                    category.get('ProductTypeId'),
                    category.get('BrandId'),
                ) == full_key:
                    return category
            for category in categories:
                if category.get('ProductCatId') and category.get('ProductCatId') == product.get('ProductCatId'):
                    return category
            for category in categories:
                if category.get('LowerGroupId') and category.get('LowerGroupId') == product.get('LowerGroupId'):
                    return category
            return categories[0]

        def _classify_usage(name, main_group, lower_group, description):
            haystack = ' '.join([name or '', main_group or '', lower_group or '', description or '']).lower()
            service_tokens = (
                ' hizmet', 'gider', 'masraf', 'nakliye', 'kargo', 'akaryakit',
                'telekom', 'seyahat', 'abonelik', 'komisyon', 'premium', 'kep',
            )
            operational_tokens = ('ambalaj', 'karton', 'bant', 'etiket', 'paketleme', 'koli')
            internal_tokens = ('demirbas', 'demirbaş', 'ofis', 'raf', 'ates olcer', 'ateş ölçer')
            if any(token in haystack for token in service_tokens):
                return 'service'
            if any(token in haystack for token in operational_tokens):
                return 'operational'
            if any(token in haystack for token in internal_tokens):
                return 'internal'
            return 'commercial'

        def _variant_group(sku, name, product_id, stock_id):
            base_sku = (sku or '').strip().split()[0]
            base_name = (name or '').strip()
            if '(' in base_name and ')' in base_name:
                base_name = base_name.split('(', 1)[0].strip()
            return base_sku or base_name or product_id or stock_id or ''

        if not (self.xml_username and self.xml_password and self.xml_token):
            raise UserError(_('Tesan SOAP için kullanıcı adı, şifre ve token zorunludur.'))

        categories = _parse_categories(_soap_call(method_categories))
        products = _parse_product_list(_soap_call(method_products, extra_body))
        features = _parse_features(_soap_call(method_features))
        images = _parse_images(_soap_call(method_images))
        prices = _parse_prices(_soap_call(method_prices))
        stocks = _parse_stocks(_soap_call(method_stock))

        root = ET.Element('Products', attrib={'generated_at': datetime.utcnow().isoformat() + 'Z'})

        for product in products:
            if product.get('ProductStatus', '').lower() not in ('true', '1', 'yes'):
                continue

            stock_id = product.get('StockId', '')
            product_id = product.get('ProductId', '')
            price_key = (stock_id, product_id)
            category = _best_category(categories, product)
            main_group = category.get('MainGroup') or category.get('Departman') or ''
            lower_group = category.get('LowerGroup') or category.get('ProductCat') or ''
            brand = category.get('Brand') or ''
            sku = product.get('ProductCode') or product.get('StockCode') or ''
            barcode = product.get('Barcode') or ''
            name = product.get('Product') or ''
            description = features.get(product_id, '')
            price_info = prices.get(price_key, {})
            usage_class = _classify_usage(name, main_group, lower_group, description)
            variant_group = _variant_group(sku, name, product_id, stock_id)
            image_urls = images.get(stock_id, [])
            stock_qty = stocks.get(price_key, 0)

            item = ET.SubElement(root, 'Product')
            for tag, value in (
                ('SKU', sku),
                ('Barcode', barcode),
                ('Name', name),
                ('Description', description),
                ('Category', main_group),
                ('SubCategory', lower_group),
                ('Brand', brand),
                ('Price', price_info.get('Price', '')),
                ('CostPrice', price_info.get('StandartPrice', '') or price_info.get('Price', '')),
                ('Currency', price_info.get('Currency', '') or price_info.get('StandartPriceCurrency', '')),
                ('Stock', str(stock_qty)),
                ('Tax', product.get('Tax') or ''),
                ('ProductId', product_id),
                ('StockId', stock_id),
                ('ExternalProductId', product_id),
                ('SourceStockId', stock_id),
                ('VariantGroup', variant_group),
                ('UsageClass', usage_class),
                ('SpecialCode', product.get('SpecialCode') or ''),
                ('Unit', product.get('Unit') or ''),
            ):
                child = ET.SubElement(item, tag)
                child.text = value or ''

            if image_urls:
                image = ET.SubElement(item, 'Image')
                image.text = image_urls[0]
                images_el = ET.SubElement(item, 'Images')
                for image_url in image_urls:
                    image_el = ET.SubElement(images_el, 'Image')
                    image_el.text = image_url

        _logger.info("Tesan SOAP: %d ürün normalize edildi", len(root.findall('./Product')))
        return ET.tostring(root, encoding='unicode')

    def _parse_xml(self, xml_content):
        """XML içeriğini parse et"""
        self.ensure_one()

        try:
            # String parse et - eğer byte ise decode et
            if isinstance(xml_content, bytes):
                # Encoding denemeleri
                for enc in ['utf-8', 'iso-8859-9', 'windows-1254', 'latin1']:
                    try:
                        xml_content = xml_content.decode(enc)
                        _logger.info(f"XML {enc} ile decode edildi")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    xml_content = xml_content.decode('utf-8', errors='ignore')
                    _logger.warning("XML decode hatası - bazı karakterler kaybolmuş olabilir")

            # WordPress / WooCommerce WXR exportlarını namespace'leri koruyarak işle.
            if 'wordpress.org/export/' in (xml_content or '') and '<rss' in (xml_content or ''):
                root = ET.fromstring(xml_content)
                products = self._parse_wordpress_wxr_xml(root)
                _logger.info(
                    "WordPress WXR Parse: %d ürün bulundu (attachment ve sayfalar filtrelendi)",
                    len(products),
                )
                return products

            # XML namespace'leri temizle
            xml_content = re.sub(r'\sxmlns[^"]*"[^"]*"', '', xml_content)
            xml_content = re.sub(r'\sxmlns=[^"]*"[^"]*"', '', xml_content)

            root = ET.fromstring(xml_content)

            # ═══════════════════════════════════════════════════════════════
            # INDEX GRUP / NETEX: İç içe yapıyı düzleştir
            # INDEXGRUP > KATEGORI > GRUP > URUN → düz URUN listesi
            # Her URUN elementine _KATEGORI ve _GRUP bilgisini attribute olarak enjekte et
            # ═══════════════════════════════════════════════════════════════
            if self.xml_template in ('indexgrup', 'netex'):
                products = self._parse_indexgrup_xml(root)
                _logger.info(
                    "Index Grup/Netex XML Parse: %d ürün bulundu (iç içe yapıdan düzleştirildi)",
                    len(products),
                )
                return products

            # XPath ile ürünleri bul
            xpath = self.root_element
            if xpath.startswith('//'):
                xpath = '.' + xpath

            products = root.findall(xpath)

            _logger.info(f"XML Parse: {len(products)} ürün bulundu (xpath: {xpath})")

            if not products:
                # Alternatif yolları dene (İngilizce ve Türkçe)
                alt_paths = ['.//Product', './/product', './/item', './/entry',
                            './/urun', './/Urun', './/URUN']
                for alt_path in alt_paths:
                    products = root.findall(alt_path)
                    if products:
                        _logger.info(f"Alternatif xpath ile {len(products)} ürün bulundu: {alt_path}")
                        break

            return products

        except ET.ParseError as e:
            raise UserError(_('XML parse hatası: %s') % str(e))

    def _parse_wordpress_wxr_xml(self, root):
        """WordPress/WooCommerce WXR exportunu ürün odaklı düzleştir."""
        ns = {
            'wp': 'http://wordpress.org/export/1.2/',
            'content': 'http://purl.org/rss/1.0/modules/content/',
            'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
        }
        channel = root.find('channel')
        items = channel.findall('item') if channel is not None else root.findall('.//item')
        attachment_map = {}

        def _meta_map(item):
            values = {}
            for meta in item.findall('wp:postmeta', ns):
                key = meta.findtext('wp:meta_key', default='', namespaces=ns)
                value = meta.findtext('wp:meta_value', default='', namespaces=ns)
                if key and key not in values:
                    values[key] = value or ''
            return values

        # Önce attachment'ları çöz.
        for item in items:
            post_type = item.findtext('wp:post_type', default='', namespaces=ns)
            if post_type != 'attachment':
                continue
            post_id = item.findtext('wp:post_id', default='', namespaces=ns)
            attachment_url = item.findtext('{http://wordpress.org/export/1.2/}attachment_url', default='') or ''
            if post_id and attachment_url:
                attachment_map[str(post_id).strip()] = attachment_url.strip()

        products = []
        for item in items:
            post_type = item.findtext('wp:post_type', default='', namespaces=ns)
            if post_type != 'product':
                continue

            metas = _meta_map(item)
            categories = []
            brands = []
            attrs = []
            for category in item.findall('category'):
                text = (category.text or '').strip()
                domain = (category.attrib.get('domain') or '').strip()
                if not text:
                    continue
                if domain == 'product_cat' and text not in categories:
                    categories.append(text)
                elif domain == 'product_brand' and text not in brands:
                    brands.append(text)
                elif domain.startswith('pa_'):
                    attrs.append(text)

            thumb_url = attachment_map.get((metas.get('_thumbnail_id') or '').strip(), '')
            gallery_urls = []
            gallery_ids = [gid.strip() for gid in (metas.get('_product_image_gallery') or '').split(',') if gid.strip()]
            for gid in gallery_ids:
                url = attachment_map.get(gid)
                if url and url not in gallery_urls:
                    gallery_urls.append(url)
            if thumb_url:
                gallery_urls = [thumb_url] + [url for url in gallery_urls if url != thumb_url]

            item.set('_WP_TITLE', (item.findtext('title', default='') or '').strip())
            item.set('_WP_CONTENT', (item.findtext('content:encoded', default='', namespaces=ns) or '').strip())
            item.set('_WP_EXCERPT', (item.findtext('excerpt:encoded', default='', namespaces=ns) or '').strip())
            item.set('_WP_SLUG', (item.findtext('wp:post_name', default='', namespaces=ns) or '').strip())
            item.set('_WP_STATUS', (item.findtext('wp:status', default='', namespaces=ns) or '').strip())
            item.set('_WP_SKU', (metas.get('_sku') or '').strip())
            item.set('_WP_PRICE', (metas.get('_price') or metas.get('_regular_price') or '').strip())
            item.set('_WP_REGULAR_PRICE', (metas.get('_regular_price') or '').strip())
            item.set('_WP_STOCK', (metas.get('_stock') or '').strip())
            item.set('_WP_STOCK_STATUS', (metas.get('_stock_status') or '').strip())
            item.set('_WP_CATEGORY', categories[0] if categories else '')
            item.set('_WP_BRAND', brands[0] if brands else '')
            item.set('_WP_ATTR_TERMS', ', '.join(attrs))
            item.set('_WP_IMAGE_GALLERY', ','.join(gallery_urls))
            products.append(item)

        return products

    # ══════════════════════════════════════════════════════════════════════
    # INDEX GRUP / NETEX — Özel XML parse yöntemleri
    # ══════════════════════════════════════════════════════════════════════

    def _parse_indexgrup_xml(self, root):
        """Index Grup / Netex iç içe Katalog XML'ini düzleştir.

        Yapı:
            <INDEXGRUP>
              <KATEGORI KOD="IDX1" TANIM="Bilgisayar">
                <GRUP KOD="1" TANIM="Masaüstü PC">
                  <URUN KOD=".." AD=".." MARKA=".." GLOBALKOD=".." BARCODE="..">
                    <VERGI>KDV18</VERGI>
                    <RESIM>http://...</RESIM>
                    <OZELLIK><OZL TANIM=".." DEGER=".."/></OZELLIK>
                  </URUN>

        Her URUN elementine _KATEGORI ve _GRUP sanal attribute'ları enjekte edilir,
        böylece standart field-mapping mekanizması (@_KATEGORI, @_GRUP) ile okunabilir.
        """
        products = []

        for kategori in root.iter('KATEGORI'):
            kat_tanim = kategori.get('TANIM', '')
            for grup in kategori.iter('GRUP'):
                grup_tanim = grup.get('TANIM', '')
                for urun in grup.iter('URUN'):
                    # Sanal attribute'lar ekle (parent bilgisi)
                    urun.set('_KATEGORI', kat_tanim)
                    urun.set('_GRUP', grup_tanim)
                    products.append(urun)

        # Kategorisiz ürünleri de yakala (düzensiz XML'ler için)
        if not products:
            products = list(root.iter('URUN'))

        return products

    def _fetch_indexgrup_stock_map(self):
        """Index Grup / Netex Stok XML'ini çekip GLOBALKOD → stok miktarı map'i döndürür.

        Stok XML yapısı:
            <INDEXGRUP>
              <URUN KOD="DT.VQEEM.027" STOK="1+" YOL=""/>
        """
        if not self.xml_stock_url:
            return {}

        try:
            original_url = self.xml_url
            self.xml_url = self.xml_stock_url
            xml_content = self._fetch_xml()
            self.xml_url = original_url

            xml_content = re.sub(r'\sxmlns[^"]*"[^"]*"', '', xml_content)
            root = ET.fromstring(xml_content)
            stock_map = {}
            for urun in root.iter('URUN'):
                kod = urun.get('KOD', '').strip()
                stok_raw = urun.get('STOK', '0').strip()
                # "1+", "5+", "10+", "50+", "100+" — sayısal kısmı al
                stok_num = re.sub(r'[^\d]', '', stok_raw)
                try:
                    stock_map[kod] = int(stok_num) if stok_num else 0
                except ValueError:
                    stock_map[kod] = 0
            _logger.info("Index Grup Stok XML: %d ürün stok bilgisi okundu", len(stock_map))
            return stock_map
        except Exception as e:
            _logger.warning("Index Grup Stok XML okunamadı: %s", e)
            return {}

    def _fetch_indexgrup_price_map(self):
        """Index Grup / Netex Fiyat XML'ini çekip GLOBALKOD → fiyat bilgisi map'i döndürür.

        Fiyat XML yapısı:
            <INDEXGRUP>
              <URUN KOD="DT.VQEEM.027" OZEL="123.45" BAYI="130.00" MUSTERI="150.00" PB="TL"/>
        """
        if not self.xml_price_url:
            return {}

        try:
            original_url = self.xml_url
            self.xml_url = self.xml_price_url
            xml_content = self._fetch_xml()
            self.xml_url = original_url

            xml_content = re.sub(r'\sxmlns[^"]*"[^"]*"', '', xml_content)
            root = ET.fromstring(xml_content)
            price_map = {}
            for urun in root.iter('URUN'):
                kod = urun.get('KOD', '').strip()
                ozel = urun.get('OZEL', '').strip()
                bayi = urun.get('BAYI', '').strip()
                musteri = urun.get('MUSTERI', '').strip()
                pb = urun.get('PB', 'TL').strip()
                try:
                    price_map[kod] = {
                        'cost_price': float(ozel.replace(',', '.')) if ozel else 0.0,
                        'dealer_price': float(bayi.replace(',', '.')) if bayi else 0.0,
                        'customer_price': float(musteri.replace(',', '.')) if musteri else 0.0,
                        'currency': pb,
                    }
                except (ValueError, TypeError):
                    pass
            _logger.info("Index Grup Fiyat XML: %d ürün fiyat bilgisi okundu", len(price_map))
            return price_map
        except Exception as e:
            _logger.warning("Index Grup Fiyat XML okunamadı: %s", e)
            return {}

    def _get_element_value(self, element, path):
        """Element içinden değer al (nested path desteği)"""
        if not path:
            return None

        # Path'i parçala (örn: "Images/Image/Url")
        parts = path.split('/')
        current = element

        for i, part in enumerate(parts):
            if current is None:
                return None

            # Attribute kontrolü (@attr)
            if part.startswith('@'):
                return current.get(part[1:])

            # Son parça mı kontrol et (çoklu değer için)
            is_last_part = (i == len(parts) - 1)

            # Child element bul
            found = current.find(part)
            if found is None:
                # Küçük/büyük harf duyarsız ara
                for child in current:
                    if child.tag.lower() == part.lower():
                        found = child
                        break

            current = found

        if current is not None:
            return current.text

        return None

    def _get_element_values(self, element, path):
        """Element içinden TÜM değerleri al (çoklu görsel için)"""
        if not path:
            return []

        values = []
        parts = path.split('/')

        # İlk parçaya kadar git (parent element)
        current = element
        for part in parts[:-1]:
            if current is None:
                return []
            found = current.find(part)
            if found is None:
                for child in current:
                    if child.tag.lower() == part.lower():
                        found = child
                        break
            current = found

        # Son parçadaki TÜM elementleri bul
        if current is not None and len(parts) > 0:
            last_part = parts[-1]
            for child in current:
                if child.tag.lower() == last_part.lower():
                    if child.text:
                        values.append(child.text.strip())

        return values

    def _extract_product_data(self, element):
        """XML elementinden ürün verilerini çıkar"""
        self.ensure_one()

        data = {}
        image_values = []

        for mapping in self.field_mapping_ids:
            value = self._get_element_value(element, mapping.xml_path)

            if value:
                # Dönüşüm uygula
                if mapping.transform:
                    value = mapping.apply_transform(value)

                if mapping.odoo_field in ('image', 'image2', 'image3', 'image4'):
                    # Tekli görsel alanlarını topla
                    if isinstance(value, str):
                        for candidate in value.split(','):
                            candidate = candidate.strip()
                            if candidate and candidate.startswith('http'):
                                image_values.append(candidate)
                    continue

                elif mapping.odoo_field == 'images':
                    # Tek path ile çoklu görsel alımını destekle
                    all_images = self._get_element_values(element, mapping.xml_path)
                    for candidate in all_images:
                        if candidate and str(candidate).startswith('http'):
                            image_values.append(str(candidate).strip())

                else:
                    data[mapping.odoo_field] = value

        # Mapping'e eklenmemiş olsa bile standart harici kimlik alanlarını otomatik oku.
        fallback_fields = {
            'external_product_id': ['ExternalProductId', 'ProductId'],
            'source_stock_id': ['SourceStockId', 'StockId'],
            'usage_class': ['UsageClass', 'ProductUsageClass'],
            'variant_group': ['VariantGroup', 'VariantKey'],
        }
        for key, paths in fallback_fields.items():
            if data.get(key):
                continue
            for path in paths:
                value = self._get_element_value(element, path)
                if value:
                    data[key] = value
                    break

        # Görselleri birleştir: ana görsel ve ek görseller
        if image_values:
            # Tekrarlı URL'leri temizle ve bozukları at
            cleaned_images = []
            for img in image_values:
                if img and img.startswith('http') and img not in cleaned_images:
                    cleaned_images.append(img)
            if cleaned_images:
                data['image'] = cleaned_images[0]
                if len(cleaned_images) > 1:
                    data['extra_images'] = cleaned_images[1:]

        # Tahtakale/Google benzeri feedlerde ek görselleri de topla
        # (xml templateinde farklı alanlarla gelebilir)
        extra_image_paths = [
            'additional_image_link1',
            'additional_image_link2',
            'additional_image_link3',
            'additional_image_link4',
            'extra_image_1',
            'extra_image_2',
        ]
        if self.xml_template == 'akinsoft':
            extra_image_paths.extend([f'GORSEL{i}' for i in range(1, 11)])
        current_image_list = []
        if data.get('image'):
            current_image_list.append(data['image'])
        if data.get('extra_images'):
            current_image_list.extend(data['extra_images'])

        for img_path in extra_image_paths:
            extra_img = self._get_element_value(element, img_path)
            if extra_img:
                extra_img = extra_img.strip()
                if extra_img and extra_img.startswith('http') and extra_img not in current_image_list:
                    current_image_list.append(extra_img)

        if current_image_list:
            # Ana görsel + ek görselleri tekilleştirilmiş olarak güncelle
            data['image'] = current_image_list[0]
            if len(current_image_list) > 1:
                data['extra_images'] = current_image_list[1:]

        # Eğer image hala boşsa alternatif yolları dene
        if not data.get('image'):
            # Alternatif görsel yollarını dene
            image_paths = [
                'images/img_item', 'Images/Image/Path', 'Images/Image/Url', 'Images/Image',
                'images/image/url', 'images/image', 'Image', 'image',
                'picture1', 'picture', 'photo', 'img', 'ImageUrl', 'imageUrl',
                'MainImage', 'mainimage', 'PrimaryImage', 'ProductImage',
            ]
            if self.xml_template == 'akinsoft':
                image_paths.extend([f'GORSEL{i}' for i in range(1, 11)])
            for path in image_paths:
                # Önce tekli, sonra çoklu dene
                img_val = self._get_element_value(element, path)
                if img_val and img_val.startswith('http'):
                    data['image'] = img_val
                    break
                # Çoklu görsel dene
                all_imgs = self._get_element_values(element, path)
                if all_imgs:
                    data['image'] = all_imgs[0]
                    if len(all_imgs) > 1:
                        data['extra_images'] = all_imgs[1:]
                    break

        # Açıklama alternatiflerini dene
        if not data.get('description'):
            desc_paths = [
                'detail', 'Detail', 'Description', 'description', 'Details', 'details',
                'LongDescription', 'longdescription', 'ProductDescription',
                'content', 'Content', 'body', 'Body', 'text', 'Text',
                'Aciklama', 'aciklama', 'detay', 'Detay',
            ]
            for path in desc_paths:
                desc_val = self._get_element_value(element, path)
                if desc_val and len(desc_val) > 10:
                    data['description'] = desc_val
                    break

        if self.xml_template == 'google_rss':
            # Google RSS kaynaklarında SKU bazen model_number yerine id/barcode'da gelir.
            if not data.get('sku'):
                for path in ('model_number', 'id', 'barcode'):
                    value = self._get_element_value(element, path)
                    if value:
                        data['sku'] = value.strip()
                        break

            # Tekrarlanan category/product_type alanlarından en detaylı olanı seç.
            category_values = []
            for path in ('category', 'product_type'):
                category_values.extend(self._get_element_values(element, path))
                value = self._get_element_value(element, path)
                if value:
                    category_values.append(value)
            cleaned_categories = []
            for value in category_values:
                value = (value or '').strip()
                if value and value not in cleaned_categories:
                    cleaned_categories.append(value)
            if cleaned_categories:
                cleaned_categories.sort(key=lambda item: ('>' not in item, -len(item)))
                data['category'] = cleaned_categories[0]
                if len(cleaned_categories) > 1 and not data.get('extra1'):
                    data['extra1'] = cleaned_categories[1]

            # quantity boşsa availability bilgisinden kaba stok üret.
            if not data.get('stock'):
                availability = (self._get_element_value(element, 'availability') or '').strip().lower()
                if availability:
                    data['stock'] = '0' if 'out' in availability else '1'

        # ═══════════════════════════════════════════════════════════
        # INDEX GRUP / NETEX — Özel veri çıkarma
        # ═══════════════════════════════════════════════════════════
        if self.xml_template in ('indexgrup', 'netex'):
            # KDV oranını VERGi etiketinden çıkar: "KDV18" → "18"
            tax_raw = data.get('tax', '')
            if tax_raw:
                tax_num = re.sub(r'[^\d]', '', tax_raw)
                if tax_num:
                    data['tax'] = tax_num

            # Kategori yolunu "Kategori > Grup" olarak birleştir
            kat = data.get('category', '')
            grp = data.pop('extra1', '') if data.get('extra1') else ''
            if kat and grp:
                data['category'] = '%s > %s' % (kat, grp)
            elif grp:
                data['category'] = grp

            # OZELLIK/OZL etiketlerinden ek bilgileri çıkar
            ozellik_el = element.find('OZELLIK')
            if ozellik_el is not None:
                specs = []
                for ozl in ozellik_el.findall('OZL'):
                    tanim = ozl.get('TANIM', '').strip()
                    deger = ozl.get('DEGER', '').strip()
                    if tanim and deger:
                        specs.append('%s: %s' % (tanim, deger))
                if specs and not data.get('description'):
                    data['description'] = '\n'.join(specs)

            # RESIM_DETAY varsa ek görsel olarak ekle
            resim_detay = element.find('RESIM_DETAY')
            if resim_detay is not None and resim_detay.text:
                detail_url = resim_detay.text.strip()
                if detail_url.startswith('http'):
                    if 'extra_images' not in data:
                        data['extra_images'] = []
                    if detail_url not in data.get('extra_images', []):
                        data['extra_images'].append(detail_url)

        return data

    def _should_skip_product_data(self, data):
        """İçe aktarım öncesi ürün bazlı atlama kuralları."""
        category = (data.get('category') or '').strip().upper()
        extra1 = (data.get('extra1') or '').strip().upper()
        combined = ' '.join([category, extra1])
        if 'YEDEK PARÇA' in combined or 'YEDEK PARCA' in combined:
            return True, _('Yedek parçalar kategorisi atlandı')
        return False, False

    def _classify_usage(self, data):
        """XML ürününü ticari / iç kullanım / hizmet sınıfına ayır."""
        explicit_value = (data.get('usage_class') or '').strip().lower()
        explicit_map = {
            'commercial': 'commercial',
            'ticari': 'commercial',
            'operational': 'operational',
            'operasyon': 'operational',
            'sarf': 'operational',
            'internal': 'internal',
            'company_internal': 'internal',
            'ic_kullanim': 'internal',
            'service': 'service',
            'expense': 'service',
            'gider': 'service',
        }
        if explicit_value in explicit_map:
            return explicit_map[explicit_value]

        haystack = ' '.join([
            str(data.get('name') or ''),
            str(data.get('category') or ''),
            str(data.get('extra1') or ''),
            str(data.get('description') or ''),
        ]).lower()

        service_keywords = (
            ' hizmet', 'gider', 'masraf', 'nakliye', 'kargo', 'akaryakit',
            'telekom', 'seyahat', 'abonelik', 'komisyon', 'premium', 'kep',
        )
        operational_keywords = (
            'ambalaj', 'karton', 'bant', 'etiket', 'paketleme', 'koli',
        )
        internal_keywords = (
            'demirbas', 'demirbaş', 'ofis', 'raf', 'ates olcer', 'ateş ölçer',
        )

        if any(token in haystack for token in service_keywords):
            return 'service'
        if any(token in haystack for token in operational_keywords):
            return 'operational'
        if any(token in haystack for token in internal_keywords):
            return 'internal'
        return 'commercial'

    def _normalized_product_defaults(self, data, protect_core=False):
        """Online Odoo ürün modeline yakın temel ürün ayarlarını üret."""
        usage_class = self._classify_usage(data)
        vals = {
            'xml_usage_class': usage_class,
        }

        if data.get('external_product_id'):
            vals['xml_external_id'] = str(data['external_product_id']).strip()
        if data.get('source_stock_id'):
            vals['xml_stock_id'] = str(data['source_stock_id']).strip()
        if data.get('variant_group'):
            vals['xml_variant_group'] = str(data['variant_group']).strip()

        if protect_core:
            return vals

        if usage_class == 'commercial':
            vals.update({
                'type': 'consu',
                'sale_ok': True,
                'purchase_ok': True,
                'invoice_policy': 'order',
                'purchase_method': 'receive',
            })
        elif usage_class == 'operational':
            vals.update({
                'type': 'consu',
                'sale_ok': False,
                'purchase_ok': True,
                'invoice_policy': 'order',
                'purchase_method': 'receive',
            })
        elif usage_class == 'internal':
            vals.update({
                'type': 'consu',
                'sale_ok': False,
                'purchase_ok': True,
                'invoice_policy': 'order',
                'purchase_method': 'receive',
            })
        else:
            vals.update({
                'type': 'service',
                'sale_ok': False,
                'purchase_ok': True,
                'invoice_policy': 'order',
                'purchase_method': 'purchase',
                'service_type': 'manual',
            })

        return vals

    def _default_category_for_usage(self, usage_class):
        """Online Odoo'daki ürün düzenine göre varsayılan kategori döndür."""
        self.ensure_one()
        category_names = {
            'service': 'Services / Masraf Kalemleri',
            'operational': 'Ambalj',
            'internal': 'Services / Masraf Kalemleri',
            'commercial': 'Özel Ürünler',
        }
        target_name = category_names.get(usage_class or 'commercial', 'Özel Ürünler')
        Category = self.env['product.category'].with_context(active_test=False)
        return Category.search([('complete_name', '=', target_name)], limit=1) or Category.search([('name', '=', target_name)], limit=1)

    def _product_has_invoice_links(self, product):
        """Muhasebe kayıtlarına bağlı ürünlerde kimlik alanlarını yerinden oynatma."""
        self.ensure_one()
        if not product or not product.exists():
            return False
        return bool(self.env['account.move.line'].search_count([
            ('product_id.product_tmpl_id', '=', product.id),
            ('parent_state', '=', 'posted'),
        ]))

    def _product_has_operational_links(self, product):
        """Stok hareketi olan ürünleri de yıkıcı işlemlerden koru."""
        self.ensure_one()
        if not product or not product.exists():
            return False
        return bool(self.env['stock.move'].search_count([
            ('product_id.product_tmpl_id', '=', product.id),
            ('state', '=', 'done'),
        ]))

    def _is_reference_locked_product(self, product):
        self.ensure_one()
        return self._product_has_invoice_links(product) or self._product_has_operational_links(product)

    def _can_rebind_product_identity(self, product, data):
        """Yanlis urun eslesmesinde ad/kod/xml kimligini bozmamaya calis."""
        self.ensure_one()
        if not product or not product.exists():
            return False

        incoming_external = str(data.get('external_product_id') or '').strip()
        incoming_stock = str(data.get('source_stock_id') or '').strip()
        incoming_sku = str(data.get('sku') or '').strip()
        incoming_name = str(data.get('name') or '').strip()
        incoming_barcode = str(data.get('barcode') or '').strip()
        base_sku, _variant = self._extract_base_and_variant(incoming_sku)

        if incoming_external and product.xml_external_id and product.xml_external_id != incoming_external:
            return False
        if incoming_stock and product.xml_stock_id and product.xml_stock_id != incoming_stock:
            return False

        if self._is_reference_locked_product(product):
            return False

        if product.default_code and base_sku and product.default_code != base_sku:
            return False

        if incoming_barcode and len(product.product_variant_ids) == 1:
            local_barcode = (product.product_variant_ids.barcode or '').strip()
            if local_barcode and local_barcode != incoming_barcode:
                return False

        if incoming_name and product.name:
            name_ratio = SequenceMatcher(None, incoming_name.lower(), product.name.lower()).ratio() * 100
            if name_ratio < 80 and not (base_sku and product.default_code == base_sku):
                return False

        return True

    def _download_image(self, url):
        """URL'den görsel indir ve base64 olarak döndür"""
        if not url:
            return None

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/*,*/*',
            }
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()

            # İçerik tipi kontrolü
            content_type = response.headers.get('Content-Type', '')
            if not any(t in content_type for t in ['image', 'octet-stream']):
                _logger.warning(f"Geçersiz görsel tipi: {content_type} - {url}")
                return None

            # Boyut kontrolü (max 10MB)
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > 10 * 1024 * 1024:
                _logger.warning(f"Görsel çok büyük: {content_length} bytes - {url}")
                return None

            # Base64'e çevir
            image_data = base64.b64encode(response.content).decode('utf-8')

            _logger.debug(f"Görsel indirildi: {url}")
            return image_data

        except requests.exceptions.RequestException as e:
            _logger.warning(f"Görsel indirilemedi: {url} - {e}")
            return None
        except Exception as e:
            _logger.warning(f"Görsel işleme hatası: {url} - {e}")
            return None

    def _clean_html(self, html_content):
        """HTML içeriğini temizle ve düzgün formatla"""
        if not html_content:
            return ''

        import re
        from html import unescape

        # HTML entity'leri decode et
        html_content = unescape(html_content)

        # Script ve style etiketlerini tamamen kaldır
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)

        # <BR> etiketlerini satır sonuna çevir
        html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)

        # Boş span/div etiketlerini kaldır
        html_content = re.sub(r'<span[^>]*>\s*</span>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<div[^>]*>\s*</div>', '', html_content, flags=re.IGNORECASE)

        # ID'siz, class'sız, boş div/span'leri kaldır
        html_content = re.sub(r'<div>\s*', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'\s*</div>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<span>\s*', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'\s*</span>', '', html_content, flags=re.IGNORECASE)

        # Inline style ve event handler'ları kaldır
        html_content = re.sub(r'\s+on\w+="[^"]*"', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'\s+style="[^"]*"', '', html_content, flags=re.IGNORECASE)

        # Gereksiz attribute'ları kaldır (sayısal ID'ler vs)
        html_content = re.sub(r'\s+\d{15,}', '', html_content)

        # <UL> ve <LI> etiketlerini temizle
        html_content = re.sub(r'<ul[^>]*>', '\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</ul>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<li[^>]*>', '• ', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</li>', '\n', html_content, flags=re.IGNORECASE)

        # Birden fazla boşluğu tekile indir
        html_content = re.sub(r' {2,}', ' ', html_content)

        # Birden fazla satır sonunu ikiye indir
        html_content = re.sub(r'\n{3,}', '\n\n', html_content)

        html_content = html_content.strip()

        return html_content

    def _extract_all_images(self, element):
        """XML elementinden tüm görsel URL'lerini çıkar"""
        images = []

        # Farklı görsel path'lerini dene
        image_paths = [
            './/Images/Image/Path', './/Images/Image/Url', './/Images/Image',
            './/images/image/url', './/images/image',
            './/Picture', './/picture', './/Photo', './/photo',
            './/image', './/Image', './/img', './/Img',
            './picture1', './picture2', './picture3', './picture4', './picture5',
        ]
        if self.xml_template == 'akinsoft':
            image_paths.extend([f'./GORSEL{i}' for i in range(1, 11)])

        for path in image_paths:
            found = element.findall(path)
            for img_elem in found:
                url = img_elem.text if img_elem.text else img_elem.get('url') or img_elem.get('src')
                if url and url.startswith('http') and url not in images:
                    images.append(url)

        return images

    # ══════════════════════════════════════════════════════════════════════════
    # PRICE CALCULATION
    # ══════════════════════════════════════════════════════════════════════════

    def _usd_to_try(self, amount_usd):
        """USD → TRY dönüşümü (Odoo güncel kuru ile)."""
        usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        try_cur = self.env['res.currency'].search([('name', '=', 'TRY')], limit=1)
        if not usd or not try_cur or not usd.rate:
            return amount_usd
        # usd.rate = USD_per_TRY → TRY_per_USD = 1/usd.rate
        return float(amount_usd) / usd.rate

    def _cost_to_company_currency(self, cost_price):
        """Maliyet fiyatını şirket para birimine (TRY) çevir."""
        if not cost_price:
            return 0.0
        cost = float(cost_price)
        if not self.cost_currency_id:
            return cost
        company_cur = self.env.company.currency_id
        if self.cost_currency_id.id == company_cur.id:
            return cost
        # Dönüşüm: cost_currency → TRY
        rate = self.cost_currency_id.rate  # currency_per_TRY
        if not rate:
            return cost
        return cost / rate  # cost / (USD_per_TRY) = cost_TRY

    def _calculate_sale_price(self, cost_price):
        """Tedarikçi fiyatından satış fiyatı hesapla (döviz dönüşümü dahil)."""
        self.ensure_one()

        if not cost_price:
            return 0.0

        # Maliyet fiyatını şirket para birimine (TRY) çevir
        cost = self._cost_to_company_currency(cost_price)
        sale_price = cost

        # Markup uygula
        if self.price_markup_type in ('percent', 'both'):
            sale_price = cost * (1 + self.price_markup_percent / 100)

        if self.price_markup_type in ('fixed', 'both'):
            sale_price += self.price_markup_fixed

        # Yuvarlama
        if self.price_round:
            if self.price_round_method == '99':
                sale_price = int(sale_price) + 0.99
            elif self.price_round_method == '90':
                sale_price = int(sale_price) + 0.90
            elif self.price_round_method == '00':
                sale_price = round(sale_price)

        return sale_price

    def _find_tax_by_value(self, tax_value):
        """XML'den gelen KDV değerinden Odoo satış vergisini bul.
        '18', '18%', '%18', 'KDV 18', '0.18' gibi formatları destekler.
        """
        if not tax_value:
            return False
        tax_str = str(tax_value).strip()
        match = re.search(r'\d+(?:[.,]\d+)?', tax_str)
        if not match:
            return False
        rate = float(match.group().replace(',', '.'))
        # '0.18' gibi ondalık format → yüzdeye çevir
        if rate < 1:
            rate = rate * 100
        tax = self.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', rate),
            ('active', '=', True),
        ], limit=1)
        if tax:
            _logger.debug("KDV eşleşti: %s → %s (%%%.0f)", tax_value, tax.name, rate)
        else:
            _logger.debug("KDV bulunamadı: %s (oran: %.0f)", tax_value, rate)
        return tax

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY MATCHING
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_category_mapping(self, category_name, subcategory_name=None):
        """
        Kategori eşleştirmesi uygula.

        Önce manuel eşleştirmeleri kontrol eder, bulunamazsa otomatik eşleştirme yapar.

        Returns:
            dict: {
                'categ_id': product.category ID veya False,
                'public_categ_ids': [(6, 0, [IDs])] veya False
            }
        """
        self.ensure_one()

        result = {
            'categ_id': False,
            'public_categ_ids': False,
        }

        if not category_name:
            if self.default_category_id:
                result['categ_id'] = self.default_category_id.id
            return result

        # Tam kategori yolunu oluştur
        full_category_path = str(category_name).strip()
        if subcategory_name:
            separator = self.category_separator or ' > '
            full_category_path = f"{full_category_path}{separator}{str(subcategory_name).strip()}"

        # 1. Manuel eşleştirmeleri kontrol et
        CategoryMapping = self.env['xml.category.mapping']
        mapping = CategoryMapping.find_mapping(self.id, full_category_path)

        # Alt kategori olmadan da dene
        if not mapping and subcategory_name:
            mapping = CategoryMapping.find_mapping(self.id, str(category_name).strip())

        if mapping:
            _logger.info(f"Kategori eşleştirmesi bulundu: '{full_category_path}' → "
                        f"Odoo: {mapping.odoo_category_id.name if mapping.odoo_category_id else 'Yok'}, "
                        f"E-Ticaret: {[c.name for c in mapping.ecommerce_category_ids]}")

            if mapping.odoo_category_id:
                result['categ_id'] = mapping.odoo_category_id.id

            if mapping.ecommerce_category_ids:
                result['public_categ_ids'] = [(6, 0, mapping.ecommerce_category_ids.ids)]

            # Eğer Odoo kategorisi yoksa varsayılanı kullan
            if not result['categ_id'] and self.default_category_id:
                result['categ_id'] = self.default_category_id.id

            return result

        # 2. Manuel eşleştirme yoksa otomatik eşleştirme yap
        category = self._find_or_create_category(category_name, subcategory_name)
        if category:
            result['categ_id'] = category.id

        return result

    def _find_or_create_category(self, category_name, subcategory_name=None):
        """Kategoriyi bul veya oluştur (otomatik eşleştirme)"""
        self.ensure_one()

        if not category_name:
            return self.default_category_id or None

        Category = self.env['product.category']
        category_name = str(category_name).strip()

        # 1. Tam eşleşme ara (büyük/küçük harf duyarsız)
        category = Category.search([
            ('name', '=ilike', category_name)
        ], limit=1)

        if category:
            # Alt kategori varsa onunla devam et
            if subcategory_name:
                subcategory_name = str(subcategory_name).strip()
                subcategory = Category.search([
                    ('name', '=ilike', subcategory_name),
                    ('parent_id', '=', category.id)
                ], limit=1)

                if subcategory:
                    return subcategory
                elif self.auto_create_category:
                    # Alt kategoriyi oluştur
                    return Category.create({
                        'name': subcategory_name,
                        'parent_id': category.id,
                    })
                else:
                    return category  # Alt kategori oluşturulamıyor, ana kategori döndür
            return category

        # 2. Benzer kategori ara (kısmi eşleşme)
        similar = Category.search([
            ('name', 'ilike', category_name)
        ], limit=1)

        if similar:
            _logger.info(f"Benzer kategori bulundu: '{category_name}' → '{similar.name}'")
            if subcategory_name:
                subcategory_name = str(subcategory_name).strip()
                subcategory = Category.search([
                    ('name', '=ilike', subcategory_name),
                    ('parent_id', '=', similar.id)
                ], limit=1)

                if subcategory:
                    return subcategory
                elif self.auto_create_category:
                    return Category.create({
                        'name': subcategory_name,
                        'parent_id': similar.id,
                    })
                else:
                    return similar
            return similar

        # 3. Kategori bulunamadı
        if not self.auto_create_category:
            # Otomatik oluşturma kapalı, varsayılan kategori döndür
            _logger.info(f"Kategori bulunamadı (otomatik oluşturma kapalı): {category_name}")
            return self.default_category_id or None

        # Yeni oluştur
        _logger.info(f"Yeni kategori oluşturuluyor: {category_name}")

        # Ana kategoriyi oluştur
        parent_category = Category.create({
            'name': category_name,
        })

        # Alt kategori varsa onu da oluştur
        if subcategory_name:
            subcategory_name = str(subcategory_name).strip()
            return Category.create({
                'name': subcategory_name,
                'parent_id': parent_category.id,
            })

        return parent_category

    # ══════════════════════════════════════════════════════════════════════════
    # PRODUCT MATCHING
    # ══════════════════════════════════════════════════════════════════════════

    def _find_existing_product(self, data):
        """Mevcut ürünü bul - Önce Odoo standart _retrieve_product, sonra kaynak özel kurallar"""
        self.ensure_one()
        ProductT = self.env['product.template'].with_context(active_test=False)
        ProductP = self.env['product.product'].with_context(active_test=False)

        sku = str(data.get('sku', '')).strip() if data.get('sku') else ''
        sku_prefix = sku.split()[0] if sku else ''

        external_product_id = str(data.get('external_product_id', '')).strip() if data.get('external_product_id') else ''
        if external_product_id:
            product = ProductT.search([('xml_external_id', '=', external_product_id)], limit=1)
            if product:
                return product, 'external_product_id'

        source_stock_id = str(data.get('source_stock_id', '')).strip() if data.get('source_stock_id') else ''
        if source_stock_id:
            product = ProductT.search([('xml_stock_id', '=', source_stock_id)], limit=1)
            if product:
                return product, 'source_stock_id'

        # 0. Odoo standart _retrieve_product (Nilvera/UBL ile aynı mantık) — öncelikli
        product_vals = {}
        if data.get('barcode'):
            product_vals['barcode'] = str(data['barcode']).strip()
        if sku:
            product_vals['default_code'] = sku
        if data.get('name'):
            product_vals['name'] = str(data['name']).strip().split('\n', 1)[0]
        if product_vals:
            product = ProductP._retrieve_product(
                company=self.env.company,
                **product_vals
            )
            if product and product.product_tmpl_id:
                if self._can_rebind_product_identity(product.product_tmpl_id, data):
                    return product.product_tmpl_id, 'odoo_standard'

        # 1. SKU Prefix (ilk kelime) ile eşleştir
        if self.match_by_sku_prefix and sku_prefix:
            # Önce tam prefix eşleşmesi
            product = ProductT.search([
                ('default_code', '=like', sku_prefix + '%')
            ], limit=1)
            if product and self._can_rebind_product_identity(product, data):
                return product, 'sku_prefix'

        # 2. Barkod ile eşleştir
        if self.match_by_barcode and data.get('barcode'):
            barcode = str(data['barcode']).strip()
            if barcode:
                # 2a. Önce product.product üzerinden (aktif+arşiv dahil) barkod ara
                variant = ProductP.search([('barcode', '=', barcode)], limit=1)
                if variant and variant.product_tmpl_id:
                    return variant.product_tmpl_id, 'barcode'

                # 2b. Barkod ürün adında olabilir (örn: "8699931326048-PROPODS3")
                product = ProductT.search([('name', 'ilike', barcode)], limit=1)
                if product and self._can_rebind_product_identity(product, data):
                    return product, 'barcode_in_name'

                # 2c. Barkod SKU'da olabilir
                product = ProductT.search([('default_code', '=', barcode)], limit=1)
                if product and self._can_rebind_product_identity(product, data):
                    return product, 'barcode_as_sku'

        # 3. SKU/Ürün kodu ile tam eşleştir
        if self.match_by_sku and sku:
            product = ProductT.search([('default_code', '=', sku)], limit=1)
            if product and self._can_rebind_product_identity(product, data):
                return product, 'sku_exact'

        # 4. Açıklama ile eşleştir
        if self.match_by_description and data.get('description'):
            description = str(data['description']).strip().lower()
            if description and len(description) > 10:
                all_products = ProductT.search([('description_sale', '!=', False)])
                for prod in all_products:
                    if not prod.description_sale:
                        continue
                    prod_desc = prod.description_sale.lower()

                    # 4a. Açıklamada ürün kodu var mı?
                    if sku_prefix and sku_prefix.lower() in prod_desc:
                        if self._can_rebind_product_identity(prod, data):
                            return prod, 'description_has_sku'

                    # 4b. Açıklama benzerliği kontrolü
                    ratio = SequenceMatcher(None, description[:200], prod_desc[:200]).ratio() * 100
                    if ratio >= self.description_match_ratio:
                        if self._can_rebind_product_identity(prod, data):
                            return prod, f'description_similar_{int(ratio)}%'

        # 5. İsim benzerliği ile eşleştir
        if self.match_by_name and data.get('name'):
            name = str(data['name']).strip()
            if name:
                # Önce tam eşleşme
                product = ProductT.search([('name', '=ilike', name)], limit=1)
                if product and self._can_rebind_product_identity(product, data):
                    return product, 'name_exact'

                # 5a. Parantezden varyant modu - ana isim ile ara
                if self.variant_from_parentheses:
                    base_name, variant_name = self._extract_base_and_variant(name)
                    if base_name and variant_name:
                        # Ana isim ile tam eşleşme ara
                        product = ProductT.search([('name', '=ilike', base_name)], limit=1)
                        if product and self._can_rebind_product_identity(product, data):
                            return product, 'base_name_exact'

                        # Ana isim ile benzerlik ara
                        all_products = ProductT.search([])
                        for prod in all_products:
                            ratio = SequenceMatcher(None, base_name.lower(), prod.name.lower()).ratio() * 100
                            if ratio >= 90:  # Ana isim için yüksek benzerlik
                                if self._can_rebind_product_identity(prod, data):
                                    return prod, f'base_name_similar_{int(ratio)}%'

                # 5b. Normal benzerlik kontrolü
                all_products = ProductT.search([])
                for prod in all_products:
                    ratio = SequenceMatcher(None, name.lower(), prod.name.lower()).ratio() * 100
                    if ratio >= self.name_match_ratio:
                        if self._can_rebind_product_identity(prod, data):
                            return prod, f'name_similar_{int(ratio)}%'

        return None, None

    def _get_sku_prefix(self, sku):
        """SKU'nun ilk kelimesini (prefix) al"""
        if not sku:
            return ''
        return str(sku).strip().split()[0] if sku else ''

    def _extract_base_and_variant(self, name):
        """Ürün adından ana isim ve varyantı ayıkla

        Örnek: "BOLD SPEAKER (KIRMIZI)" → ("BOLD SPEAKER", "KIRMIZI")
        Örnek: "BOLD (AÇIK YEŞİL)" → ("BOLD", "AÇIK YEŞİL")
        """
        import re
        if not name:
            return name, None

        name = str(name).strip()

        # Parantez içeriğini bul
        match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', name)
        if match:
            base_name = match.group(1).strip()
            variant = match.group(2).strip()
            return base_name, variant

        return name, None

    def _find_or_create_base_product(self, base_name, data, cost_price):
        """Ana ürünü bul veya oluştur (varyant için)"""
        self.ensure_one()
        Product = self.env['product.template']

        # Önce mevcut ürünü ara
        # 1. Tam isim eşleşmesi
        product = Product.search([('name', '=ilike', base_name)], limit=1)
        if product:
            return product

        # 2. SKU prefix ile ara (SKU'dan da parantez kısmını çıkar)
        sku = str(data.get('sku', '')).strip() if data.get('sku') else ''
        base_sku, _ = self._extract_base_and_variant(sku)
        if base_sku:
            product = Product.search([('default_code', '=', base_sku)], limit=1)
            if product:
                return product
            # Prefix ile ara
            product = Product.search([('default_code', '=like', base_sku.split()[0] + '%')], limit=1)
            if product:
                return product

        # Ürün bulunamadı, yeni oluştur
        sale_price = self._calculate_sale_price(cost_price)

        vals = {
            'name': base_name,
            'default_code': base_sku if base_sku else None,
            'description_sale': data.get('description'),
            'list_price': sale_price,
            'standard_price': cost_price or 0,
            'xml_source_id': self.id,
            'xml_supplier_price': cost_price,
            'xml_supplier_sku': data.get('sku'),
            'xml_last_sync': fields.Datetime.now(),
            'is_dropship': True,
        }
        vals.update(self._normalized_product_defaults(data))

        # Kategori (manuel eşleştirme + otomatik)
        category_result = self._apply_category_mapping(data.get('category'), data.get('extra1'))
        if category_result.get('categ_id'):
            vals['categ_id'] = category_result['categ_id']
        if category_result.get('public_categ_ids'):
            vals['public_categ_ids'] = category_result['public_categ_ids']
        if not vals.get('categ_id'):
            default_category = self._default_category_for_usage(vals.get('xml_usage_class'))
            if default_category:
                vals['categ_id'] = default_category.id

        # Tedarikçi
        if self.supplier_id:
            vals['xml_supplier_id'] = self.supplier_id.id

        product = Product.create(vals)
        _logger.info(f"Ana ürün oluşturuldu: {base_name}")

        return product

    def _create_color_variant(self, product_tmpl, variant_name, data, cost_price):
        """Renk/özellik bazlı varyant oluştur"""
        self.ensure_one()

        attr_name = self.variant_attribute_name or 'Renk'

        # Attribute'u bul veya oluştur
        attribute = self.env['product.attribute'].search([
            ('name', '=', attr_name),
        ], limit=1)

        if not attribute:
            attribute = self.env['product.attribute'].create({
                'name': attr_name,
                'display_type': 'radio',
                'create_variant': 'always',
            })

        # Attribute value bul veya oluştur
        attr_value = self.env['product.attribute.value'].search([
            ('attribute_id', '=', attribute.id),
            ('name', '=', variant_name),
        ], limit=1)

        if not attr_value:
            attr_value = self.env['product.attribute.value'].create({
                'attribute_id': attribute.id,
                'name': variant_name,
            })

        # Ürüne attribute line ekle veya güncelle
        attr_line = self.env['product.template.attribute.line'].search([
            ('product_tmpl_id', '=', product_tmpl.id),
            ('attribute_id', '=', attribute.id),
        ], limit=1)

        if attr_line:
            # Mevcut line'a value ekle
            if attr_value not in attr_line.value_ids:
                attr_line.write({
                    'value_ids': [(4, attr_value.id)]
                })
        else:
            # Yeni line oluştur
            self.env['product.template.attribute.line'].create({
                'product_tmpl_id': product_tmpl.id,
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, [attr_value.id])],
            })

        # Oluşan varyantı bul ve barkod ekle
        product_tmpl.invalidate_recordset()

        # Varyantı bul
        for variant in product_tmpl.product_variant_ids:
            variant_values = variant.product_template_attribute_value_ids.mapped('name')
            if variant_name in variant_values:
                # Barkod ekle
                barcode = data.get('barcode')
                if barcode:
                    variant.write({'barcode': barcode})

                # Tedarikçi fiyatı ekle (varsa pricelist veya supplierinfo ile)
                _logger.info(f"Varyant oluşturuldu: {product_tmpl.name} - {variant_name} ({barcode})")
                return variant

        return None

    # ══════════════════════════════════════════════════════════════════════════
    # IMPORT LOGIC
    # ══════════════════════════════════════════════════════════════════════════

    # ------------------------------------------------------------------
    # IdeaSoft Web Stok Senkronu (XML feed'inde stok olmayan tedarikçiler için)
    # ------------------------------------------------------------------
    def _ideasoft_web_headers(self):
        return {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/133.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
        }

    def _fetch_ideasoft_product_urls(self, base, session):
        """IdeaSoft mağaza sitemap'inden tüm ürün sayfası URL'lerini topla."""
        headers = self._ideasoft_web_headers()
        loc_re = re.compile(r'<loc>\s*([^<\s]+)\s*</loc>', re.IGNORECASE)
        product_sitemaps = []
        # sitemap index
        try:
            r = session.get(urljoin(base + '/', 'sitemap.xml'), headers=headers, timeout=(15, 60))
            if r.ok:
                for loc in loc_re.findall(r.text or ''):
                    if '/products/' in loc and loc.endswith('.xml'):
                        product_sitemaps.append(loc)
        except Exception as e:
            _logger.warning('IdeaSoft sitemap index okunamadı: %s', e)
        # index yoksa varsayılan ürün sitemap'ini dene
        if not product_sitemaps:
            product_sitemaps = [urljoin(base + '/', 'sitemap/products/0.xml')]
        product_urls = []
        for sm in product_sitemaps:
            try:
                r = session.get(sm, headers=headers, timeout=(15, 120))
                if r.ok:
                    product_urls.extend(loc_re.findall(r.text or ''))
            except Exception as e:
                _logger.warning('IdeaSoft ürün sitemap okunamadı (%s): %s', sm, e)
        # tekrarsız, sırayı koru
        return list(dict.fromkeys(product_urls))

    def _fetch_ideasoft_web_stock_items(self):
        """IdeaSoft tabanlı vitrinden ürün stok kalemlerini çıkar.

        Her ürün sayfasına gömülü JSON'dan barkod + stokKodu + urunAdi + stokAdedi
        okunur. Dönen liste: [{'barcode','sku','name','qty'}, ...]
        Barkod+SKU+isim birlikte döndürülür ki eşleştirme varyantları da yakalasın.
        """
        self.ensure_one()
        base = (self.web_stock_url or '').strip()
        if not base:
            raise UserError(_('Web Stok Mağaza URL girilmemiş.'))
        if not base.startswith('http'):
            base = 'https://' + base
        base = base.rstrip('/')

        session = requests.Session()
        headers = self._ideasoft_web_headers()
        product_urls = self._fetch_ideasoft_product_urls(base, session)
        if not product_urls:
            raise UserError(_('Mağaza sitemap\'inden ürün URL\'i bulunamadı: %s') % base)

        barkod_re = re.compile(r'"barkod"\s*:\s*"(\d+)"')
        stok_re = re.compile(r'"stokAdedi"\s*:\s*([0-9.]+)')
        sku_re = re.compile(r'"stokKodu"\s*:\s*"([^"]*)"')
        name_re = re.compile(r'"urunAdi"\s*:\s*"([^"]*)"')

        items = []
        for url in product_urls:
            try:
                r = session.get(url, headers=headers, timeout=(15, 60))
                if not r.ok:
                    continue
                txt = r.text or ''
                mb = barkod_re.search(txt)
                msku = sku_re.search(txt)
                # Barkod ya da stok kodu olmadan eşleştirilemez
                if not mb and not msku:
                    continue
                qty = 0
                ms = stok_re.search(txt)
                if ms:
                    try:
                        qty = int(float(ms.group(1)))
                    except (ValueError, TypeError):
                        qty = 0
                mname = name_re.search(txt)
                items.append({
                    'barcode': mb.group(1) if mb else '',
                    'sku': (msku.group(1).strip() if msku else ''),
                    'name': (mname.group(1).strip() if mname else ''),
                    'qty': qty,
                    'url': url,
                })
            except Exception as e:
                _logger.warning('IdeaSoft ürün sayfası okunamadı (%s): %s', url, e)
                continue
        _logger.info('IdeaSoft web stok: %s ürün okundu (%s)', len(items), base)
        return items

    def _match_product_for_stock(self, item):
        """Web stok kalemi için Odoo ürün şablonunu bul (barkod -> SKU -> varyant -> isim)."""
        self.ensure_one()
        ProductP = self.env['product.product'].with_context(active_test=False)
        ProductT = self.env['product.template'].with_context(active_test=False)

        # 1) Barkod (varyant seviyesi, normalize)
        bc_cands = self._barcode_match_candidates(item.get('barcode'))
        if bc_cands:
            p = ProductP.search([('barcode', 'in', bc_cands)], limit=1)
            if p:
                return p.product_tmpl_id, 'barcode'

        sku = (item.get('sku') or '').strip()
        # 2) SKU tam eşleşme (varyant ve şablon)
        if sku:
            p = ProductP.search([('default_code', '=', sku)], limit=1)
            if p:
                return p.product_tmpl_id, 'sku'
            t = ProductT.search([('default_code', '=', sku)], limit=1)
            if t:
                return t, 'sku'
            # 3) Varyant SKU'su: "TX108 (SİYAH)" -> ana kod "TX108"
            base = sku.split('(', 1)[0].strip()
            if base and base != sku:
                p = ProductP.search([('default_code', '=', base)], limit=1)
                if p:
                    return p.product_tmpl_id, 'sku_base'
                t = ProductT.search([
                    '|', ('default_code', '=', base), ('name', '=ilike', base)
                ], limit=1)
                if t:
                    return t, 'name_base'

        # 4) Modülün genel eşleştiricisi (barkod/SKU/isim kuralları)
        tmpl, reason = self._find_existing_product({
            'barcode': item.get('barcode'),
            'sku': sku,
            'name': item.get('name'),
        })
        if tmpl:
            return tmpl, reason

        # 5) İsimle son çare (parantez varyantını at, tam/yüksek benzerlik)
        name = (item.get('name') or '').strip()
        if name:
            base_name = name.split('(', 1)[0].strip()
            t = ProductT.search([('name', '=ilike', base_name or name)], limit=1)
            if t:
                return t, 'name'
        return ProductT.browse(), 'none'

    def _barcode_match_candidates(self, barcode):
        """Barkod normalizasyonu: GTIN-14/baştaki sıfır farklarını kapsa."""
        barcode = (barcode or '').strip()
        cands = {barcode}
        if barcode:
            cands.add(barcode.lstrip('0'))
            if len(barcode) > 13:
                cands.add(barcode[-13:])
        return [c for c in cands if c]

    def action_sync_stock_from_web(self):
        """Vitrinden web stok senkronu: barkodla eşle, xml_supplier_stock + sale_ok güncelle.

        Stok > 0  -> sale_ok=True (gerekirse tekrar aktifleştir)
        Stok = 0  -> sale_ok=False; deactivate_zero_stock açıksa active=False
        """
        self.ensure_one()
        log = self.env['xml.import.log'].create({
            'source_id': self.id,
            'start_time': fields.Datetime.now(),
            'state': 'running',
        })
        try:
            items = self._fetch_ideasoft_web_stock_items()
            log.total_products = len(items)

            updated = in_stock_n = out_stock_n = skipped = 0
            seen_tmpl = {}
            unmatched = []

            for item in items:
                tmpl, reason = self._match_product_for_stock(item)
                if not tmpl:
                    skipped += 1
                    unmatched.append('%s / %s' % (item.get('barcode') or '-', item.get('sku') or item.get('name') or '-'))
                    continue

                qty = item.get('qty', 0) or 0
                # Çok varyantlı şablonda aynı şablona düşen kalemlerin en yükseğini al
                # (herhangi bir varyant stokta ise şablon stokta sayılır)
                prev = seen_tmpl.get(tmpl.id)
                if prev is not None and prev >= qty:
                    continue
                seen_tmpl[tmpl.id] = qty

                vals = {'xml_supplier_stock': qty}
                if qty > 0:
                    in_stock_n += 1
                    if not tmpl.sale_ok:
                        vals['sale_ok'] = True
                    if not tmpl.active:
                        vals['active'] = True
                else:
                    out_stock_n += 1
                    if self.deactivate_zero_stock:
                        if tmpl.active:
                            vals['active'] = False
                    elif tmpl.sale_ok:
                        vals['sale_ok'] = False

                # Web'den gelen ürün adını güncelle (farklıysa)
                web_name = (item.get('name') or '').strip()
                if web_name and web_name.upper() != (tmpl.name or '').strip().upper():
                    if not tmpl.description_sale:
                        vals['description_sale'] = tmpl.name
                    vals['name'] = web_name

                tmpl.write(vals)
                updated += 1

            self.env.cr.commit()
            detail = _('Stokta var: %s | Tükendi: %s | Eşleşmeyen: %s') % (
                in_stock_n, out_stock_n, skipped)
            if unmatched:
                detail += '\n\nEşleşmeyenler:\n' + '\n'.join(unmatched[:100])
            log.write({
                'end_time': fields.Datetime.now(),
                'state': 'done',
                'products_updated': updated,
                'products_skipped': skipped,
                'products_created': 0,
                'products_failed': 0,
                'error_details': detail,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Web Stok Senkronu Tamamlandı'),
                    'message': _('Güncellenen: %s (stokta %s / tükendi %s), Eşleşmeyen: %s') % (
                        updated, in_stock_n, out_stock_n, skipped),
                    'type': 'success',
                    'sticky': True,
                },
            }
        except Exception as e:
            self.env.cr.rollback()
            log.write({
                'end_time': fields.Datetime.now(),
                'state': 'error',
                'error_details': str(e),
            })
            raise UserError(_('Web stok senkron hatası: %s') % str(e))

    def _scrape_web_product_detail(self, url, session):
        """Mağaza ürün sayfasından açıklama + ana görsel + ek görseller çıkar.

        Ticimax (static.ticimax.cloud) ve genel og:image / meta description desteği.
        Dönüş: {'description', 'image', 'extra_images': [...], 'category', 'brand'}
        """
        out = {'description': '', 'image': '', 'extra_images': [], 'category': '', 'brand': ''}
        try:
            r = session.get(url, headers=self._ideasoft_web_headers(), timeout=(15, 60))
            if not r.ok:
                return out
            txt = r.text or ''
        except Exception as e:
            _logger.warning('Ürün detay sayfası okunamadı (%s): %s', url, e)
            return out

        # Açıklama: meta description
        m = re.search(r'<meta name="description" content="([^"]*)"', txt)
        if m:
            out['description'] = html.unescape(m.group(1)).strip()

        # Kategori / marka (Ticimax JSON)
        mc = re.search(r'"kategori"\s*:\s*"([^"]+)"', txt)
        if mc:
            out['category'] = html.unescape(mc.group(1)).strip()
        mbr = re.search(r'"marka"\s*:\s*"([^"]+)"', txt)
        if mbr:
            out['brand'] = html.unescape(mbr.group(1)).strip()

        # Görseller: Ticimax static.ticimax.cloud/.../urunresimleri/buyuk/<dosya>
        # cdn-cgi/image/<param>/ önekini at, kanonik URL kur, dosya adına göre tekille
        tici = re.findall(
            r'static\.ticimax\.cloud/(?:cdn-cgi/image/[^/]+/)?(\d+/[Uu]ploads/[Uu]run[Rr]esimleri/buyuk/[^"?\s]+\.(?:jpg|jpeg|png|webp))',
            txt,
        )
        seen = set()
        images = []
        for path in tici:
            fname = path.rsplit('/', 1)[-1].lower()
            if fname in seen:
                continue
            seen.add(fname)
            images.append('https://static.ticimax.cloud/' + path)
        # Ticimax bulunmazsa og:image'a düş
        if not images:
            mog = re.search(r'<meta property="og:image" content="([^"]+)"', txt)
            if mog:
                images.append(mog.group(1).strip())
        if images:
            out['image'] = images[0]
            out['extra_images'] = images[1:11]
        return out

    def action_import_missing_from_web(self):
        """Web stoğunda olup Odoo'da eşleşmeyen ürünleri tam veri ile oluştur.

        Bilgi (isim/SKU/barkod/açıklama/kategori/marka) + ana görsel + ek görseller
        (product.image) + stok (xml_supplier_stock/sale_ok) doğru alanlara yazılır.
        Varyant parantezli isimler `_create_product` ile ana ürün + renk varyantına dönüşür.
        """
        self.ensure_one()
        log = self.env['xml.import.log'].create({
            'source_id': self.id,
            'start_time': fields.Datetime.now(),
            'state': 'running',
        })
        try:
            items = self._fetch_ideasoft_web_stock_items()
            log.total_products = len(items)
            session = requests.Session()
            created = matched = failed = 0
            created_names = []

            # Eksik ürün oluştururken görselleri indir
            prev_download = self.download_images
            for item in items:
                tmpl, _reason = self._match_product_for_stock(item)
                if tmpl:
                    matched += 1
                    continue
                if not (item.get('barcode') or item.get('sku')):
                    continue
                try:
                    detail = self._scrape_web_product_detail(item.get('url'), session)
                    qty = item.get('qty', 0) or 0
                    data = {
                        'name': item.get('name') or item.get('sku') or 'asiamark ürün',
                        'sku': item.get('sku') or '',
                        'barcode': item.get('barcode') or '',
                        'description': detail.get('description') or '',
                        'category': detail.get('category') or '',
                        'brand': detail.get('brand') or '',
                        'image': detail.get('image') or '',
                        'extra_images': detail.get('extra_images') or [],
                        'stock': str(qty),
                    }
                    product = self._create_product(data, 0.0, 0.0)
                    if product:
                        vals = {
                            'xml_source_id': self.id,
                            'sale_ok': qty > 0,
                            'enrichment_source': 'asiamark (web)',
                            'last_enrichment_date': fields.Datetime.now(),
                        }
                        product.write(vals)
                        # Ana görsel yoksa ekle (varyant dalı bazen atlıyor)
                        if data.get('image') and not product.image_1920:
                            img = self._download_image(data['image'])
                            if img:
                                product.image_1920 = img
                        # Ek görseller -> product.image (doğru alan). _add_extra_images helper'ı
                        # env.get() hatasıyla atlayabildiği için burada doğrudan oluştur.
                        if data.get('extra_images'):
                            ProductImage = self.env['product.image']
                            has_extra = ProductImage.search_count(
                                [('product_tmpl_id', '=', product.id)])
                            if not has_extra:
                                for i, iurl in enumerate(data['extra_images'][:9]):
                                    try:
                                        idata = self._download_image(iurl)
                                        if idata:
                                            ProductImage.create({
                                                'product_tmpl_id': product.id,
                                                'name': '%s - Görsel %s' % (product.name, i + 2),
                                                'image_1920': idata,
                                            })
                                    except Exception as ie:
                                        _logger.warning('Ek görsel eklenemedi (%s): %s', iurl, ie)
                        created += 1
                        created_names.append('%s (%s)' % (data['name'][:40], data['sku']))
                    self.env.cr.commit()
                except Exception as e:
                    self.env.cr.rollback()
                    _logger.error('Eksik ürün oluşturma hatası (%s): %s', item.get('sku'), e)
                    failed += 1

            detail_txt = _('Oluşturulan: %s | Zaten var: %s | Hata: %s') % (created, matched, failed)
            if created_names:
                detail_txt += '\n\nOluşturulanlar:\n' + '\n'.join(created_names[:100])
            log.write({
                'end_time': fields.Datetime.now(),
                'state': 'done',
                'products_created': created,
                'products_updated': 0,
                'products_skipped': matched,
                'products_failed': failed,
                'error_details': detail_txt,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Eksik Ürünler Oluşturuldu'),
                    'message': _('Oluşturulan: %s, Zaten var: %s, Hata: %s') % (created, matched, failed),
                    'type': 'success' if failed == 0 else 'warning',
                    'sticky': True,
                },
            }
        except Exception as e:
            self.env.cr.rollback()
            log.write({
                'end_time': fields.Datetime.now(),
                'state': 'error',
                'error_details': str(e),
            })
            raise UserError(_('Eksik ürün oluşturma hatası: %s') % str(e))

    @api.model
    def cron_sync_web_stock_all(self):
        """Cron: web_stock_url tanımlı ve otomatik açık kaynakların web stoğunu senkronla."""
        sources = self.search([
            ('state', '=', 'active'),
            ('auto_web_stock_sync', '=', True),
            ('web_stock_url', '!=', False),
        ])
        for source in sources:
            try:
                source.action_sync_stock_from_web()
            except Exception as e:
                _logger.error('Web stok cron hatası (%s): %s', source.name, e)

    # ------------------------------------------------------------------
    # Bayi paneli (Ticimax) USD alış fiyatı senkronu
    # ------------------------------------------------------------------
    def _fetch_katalog_price_map(self):
        """Ticimax bayi paneline login olup ürün stok kodu -> USD fiyat haritası çıkar."""
        self.ensure_one()
        base = (self.web_price_url or '').strip()
        if not base:
            raise UserError(_('Bayi Fiyat Panel URL girilmemiş.'))
        if not base.startswith('http'):
            base = 'https://' + base
        base = base.rstrip('/')
        if not (self.web_price_tel and self.web_price_password):
            raise UserError(_('Bayi login bilgileri (tel/şifre) eksik.'))

        session = requests.Session()
        headers = self._ideasoft_web_headers()
        try:
            session.get(base + '/login/', headers=headers, timeout=(15, 60))
            session.post(
                base + '/giris.asp', headers=headers,
                data={'tel': self.web_price_tel, 'password': self.web_price_password},
                timeout=(15, 60), allow_redirects=True,
            )
            resp = session.get(base + '/indirimli-fiyat/', headers=headers, timeout=(15, 180))
        except Exception as e:
            raise UserError(_('Bayi paneline bağlanılamadı: %s') % e)

        html_txt = resp.text or ''
        # Yapı: text-orange-500 span (fiyat) → h-[65px] div (ürün adı) → font-light div (SKU)
        cards = re.findall(
            r'text-orange-500[^>]*>\s*([\d.,]+)\$\s*</span>.*?h-\[65px\][^>]*>([^<]+?)</div>.*?font-light[^>]*>\s*([^<]+?)\s*</div>',
            html_txt, re.S,
        )
        price_map = {}
        for price, _name, sku in cards:
            try:
                usd = float(price.replace('.', '').replace(',', '.'))
            except (ValueError, TypeError):
                continue
            sku = sku.strip()
            if sku:
                price_map[sku] = usd
        if not price_map:
            raise UserError(_('Bayi panelinden fiyat okunamadı (login başarısız olabilir).'))
        _logger.info('Bayi fiyat: %s ürün okundu (%s)', len(price_map), base)
        return price_map

    def _match_tmpl_by_code(self, sku):
        """Stok koduna göre ürün şablonu bul (tam kod -> base/parantezsiz -> isim)."""
        ProductP = self.env['product.product'].with_context(active_test=False)
        ProductT = self.env['product.template'].with_context(active_test=False)
        p = ProductP.search([('default_code', '=', sku)], limit=1)
        if p:
            return p.product_tmpl_id
        t = ProductT.search([('default_code', '=', sku)], limit=1)
        if t:
            return t
        base = sku.split('(', 1)[0].strip()
        if base and base != sku:
            p = ProductP.search([('default_code', '=', base)], limit=1)
            if p:
                return p.product_tmpl_id
            t = ProductT.search([('default_code', '=', base)], limit=1)
            if t:
                return t
            t = ProductT.search([('name', '=ilike', base)], limit=1)
            if t:
                return t
        return ProductT.browse()

    def action_sync_prices_from_web(self):
        """Bayi panelinden USD alış fiyatlarını çek, product.supplierinfo (USD) olarak yaz."""
        self.ensure_one()
        log = self.env['xml.import.log'].create({
            'source_id': self.id,
            'start_time': fields.Datetime.now(),
            'state': 'running',
        })
        try:
            price_map = self._fetch_katalog_price_map()
            log.total_products = len(price_map)
            usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
            if not usd:
                raise UserError(_('USD para birimi bulunamadı.'))
            vendor = self.web_price_vendor_id or self.supplier_id
            if not vendor:
                raise UserError(_('Fiyat tedarikçisi (vendor) tanımlı değil.'))
            SI = self.env['product.supplierinfo']
            done = {}
            created = updated = skipped = 0
            unmatched = []
            for sku, val in price_map.items():
                tmpl = self._match_tmpl_by_code(sku)
                if not tmpl:
                    skipped += 1
                    unmatched.append(sku)
                    continue
                if tmpl.id in done:
                    continue
                done[tmpl.id] = val
                if not tmpl.xml_supplier_id:
                    tmpl.xml_supplier_id = vendor.id
                si = SI.search([
                    ('partner_id', '=', vendor.id),
                    ('product_tmpl_id', '=', tmpl.id),
                    ('currency_id', '=', usd.id),
                ], limit=1)
                if si:
                    si.write({'price': val, 'currency_id': usd.id, 'product_code': sku})
                    updated += 1
                else:
                    SI.create({
                        'product_tmpl_id': tmpl.id,
                        'partner_id': vendor.id,
                        'price': val,
                        'currency_id': usd.id,
                        'product_code': sku,
                    })
                    created += 1
            self.env.cr.commit()
            detail = _('Yeni: %s | Güncellenen: %s | Eşleşmeyen: %s') % (created, updated, skipped)
            if unmatched:
                detail += '\n\nEşleşmeyen kodlar:\n' + '\n'.join(unmatched[:100])
            log.write({
                'end_time': fields.Datetime.now(),
                'state': 'done',
                'products_created': created,
                'products_updated': updated,
                'products_skipped': skipped,
                'products_failed': 0,
                'error_details': detail,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Bayi Fiyatları Güncellendi'),
                    'message': _('USD alış fiyatı yazılan: %s (yeni %s / güncel %s), eşleşmeyen: %s') % (
                        created + updated, created, updated, skipped),
                    'type': 'success',
                    'sticky': True,
                },
            }
        except Exception as e:
            self.env.cr.rollback()
            log.write({
                'end_time': fields.Datetime.now(),
                'state': 'error',
                'error_details': str(e),
            })
            raise UserError(_('Bayi fiyat senkron hatası: %s') % str(e))

    @api.model
    def cron_sync_web_price_all(self):
        """Cron: bayi fiyatı otomatik açık kaynakların USD alış fiyatını senkronla."""
        sources = self.search([
            ('state', '=', 'active'),
            ('auto_web_price_sync', '=', True),
            ('web_price_url', '!=', False),
        ])
        for source in sources:
            try:
                source.action_sync_prices_from_web()
            except Exception as e:
                _logger.error('Bayi fiyat cron hatası (%s): %s', source.name, e)

    # ─────────────────────────────────────────────────────────────────
    # Powerway Online Sipariş Portalı Entegrasyonu
    # ─────────────────────────────────────────────────────────────────

    def _powerway_session(self):
        """Powerway Online portalına giriş yap, oturumlu session döndür."""
        import requests as _req
        session = _req.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120',
            'Accept-Language': 'tr-TR,tr;q=0.9',
        })
        base = (self.powerway_url or 'https://online.powerway.com.tr').rstrip('/')
        r = session.post(f'{base}/giris/', data={
            'email': self.powerway_user or '',
            'sifre': self.powerway_password or '',
            'beni_hatirla': '1',
            'istek': '',
        }, timeout=20)
        if '/uygulama/' not in r.url:
            raise UserError('Powerway giriş başarısız — kullanıcı adı/şifre kontrol edin.')
        return session, base

    def _fetch_powerway_orders(self, session, base):
        """Sipariş listesini çek, her biri için detay satırlarını getir."""
        import re as _re, base64 as _b64
        r = session.get(f'{base}/uygulama/siparislerim/', timeout=20)
        order_links = _re.findall(
            r'href="(/ajax/siparisdetay\.asp\?id=([A-Za-z0-9+/=]+))"', r.text
        )
        # Tarih + tutar + URL
        rows = _re.findall(
            r'<td[^>]*>(\d{1,2}\.\d{1,2}\.\d{4})</td>\s*<td[^>]*>([^<]+)</td>\s*'
            r'<td[^>]*>([\d.,]+ USD)</td>',
            r.text, _re.DOTALL
        )
        date_map = {url: (date, amt) for url, date, amt in
                    zip([u for u, _ in order_links], [r[0] for r in rows], [r[2] for r in rows])}
        orders = []
        for url, b64_id in order_links:
            try:
                order_id = _b64.b64decode(b64_id).decode()
            except Exception:
                order_id = b64_id
            date_str, amount_str = date_map.get(url, ('', ''))
            # Detay satırlarını çek
            det = session.get(f'{base}{url}', timeout=15)
            lines = _re.findall(
                r'&#9679;\s*([^<]+)</td><td[^>]*>([\d]+)</td><td[^>]*>[^<]*</td>'
                r'<td[^>]*>[^<]*</td><td[^>]*align=[\'"]right[\'"]>([\d.,]+ USD)</td>',
                det.text
            )
            orders.append({
                'portal_id': order_id,
                'date': date_str,
                'amount_str': amount_str,
                'lines': [{'name': l[0].strip(), 'qty': l[1].strip(), 'unit_price': l[2].strip()} for l in lines],
            })
            import time as _time
            _time.sleep(0.3)
        return orders

    def _parse_usd(self, s):
        """'19,9000 USD' veya '1.234,56 USD' → float"""
        s = (s or '').replace('\xa0', '').replace(' USD', '').strip()
        if ',' in s and '.' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
        try:
            return float(s)
        except Exception:
            return 0.0

    def _find_product_by_name(self, name):
        """Ürün adından product.template bul (tam + kısmi eşleşme)."""
        name_upper = (name or '').strip().upper()
        # Tam default_code eşleşmesi
        prod = self.env['product.template'].search(
            [('default_code', '=ilike', name_upper), ('active', '=', True)], limit=1
        )
        if prod:
            return prod
        # İlk kelime (SKU gibi) ile ara
        first_word = name_upper.split()[0] if name_upper.split() else ''
        if first_word:
            prod = self.env['product.template'].search(
                [('default_code', '=ilike', first_word), ('active', '=', True)], limit=1
            )
            if prod:
                return prod
        # İsim içinde ara
        prod = self.env['product.template'].search(
            [('name', 'ilike', name_upper[:20]), ('active', '=', True)], limit=1
        )
        return prod or False

    def action_sync_powerway_orders(self):
        """Powerway Online'dan sipariş geçmişini çekip Odoo'da purchase.order oluştur/güncelle."""
        self.ensure_one()
        if not self.powerway_user or not self.powerway_password:
            raise UserError('Powerway kullanıcı adı ve şifre gerekli.')

        session, base = self._powerway_session()
        orders = self._fetch_powerway_orders(session, base)

        PO = self.env['purchase.order']
        POL = self.env['purchase.order.line']
        usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        vendor = self.env['res.partner'].browse(
            (self.web_price_vendor_id or self.supplier_id).id
        )

        created = updated = 0
        for order in orders:
            if not order['lines']:
                continue
            # Portal sipariş ID'sini referans olarak kullan
            ref = f'PW-{order["portal_id"]}'
            # Tarih parse
            import datetime as _dt
            date_obj = _dt.date.today()
            try:
                parts = order['date'].split('.')
                date_obj = _dt.date(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception:
                pass

            # Var mı kontrol et
            existing_po = PO.search([('partner_ref', '=', ref)], limit=1)
            if existing_po:
                continue  # Zaten var, atla

            # Yeni PO oluştur
            po_vals = {
                'partner_id': vendor.id,
                'partner_ref': ref,
                'date_order': _dt.datetime.combine(date_obj, _dt.time(12, 0)),
                'currency_id': usd.id if usd else self.env.company.currency_id.id,
                'note': f'Powerway Online portal\'dan otomatik oluşturuldu (ID: {order["portal_id"]})',
                'state': 'draft',
            }
            po = PO.create(po_vals)

            for line in order['lines']:
                unit_price = self._parse_usd(line['unit_price'])
                try:
                    qty = float(line['qty'].replace(',', '.'))
                except Exception:
                    qty = 1.0

                product = self._find_product_by_name(line['name'])
                line_vals = {
                    'order_id': po.id,
                    'name': line['name'],
                    'product_qty': qty,
                    'price_unit': unit_price,
                    'date_planned': _dt.datetime.combine(date_obj, _dt.time(12, 0)),
                }
                if product:
                    line_vals['product_id'] = product.product_variant_ids[:1].id
                else:
                    # Ürün bulunamazsa dummy servis ürünü
                    fallback = self.env['product.product'].search(
                        [('name', 'ilike', line['name'][:15])], limit=1
                    )
                    if fallback:
                        line_vals['product_id'] = fallback.id
                POL.create(line_vals)

            created += 1

        self.write({'powerway_last_sync': fields.Datetime.now()})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Powerway Senkron Tamamlandı',
                'message': f'{created} yeni sipariş oluşturuldu, {updated} güncellendi. (Toplam: {len(orders)})',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_powerway_balance(self):
        """Powerway cari bakiye sayfasını tarayıcıda aç."""
        self.ensure_one()
        base = (self.powerway_url or 'https://online.powerway.com.tr').rstrip('/')
        return {
            'type': 'ir.actions.act_url',
            'url': f'{base}/uygulama/ayrintilicariekstre/',
            'target': 'new',
        }

    @api.model
    def cron_sync_powerway_orders(self):
        """Cron: Powerway siparişlerini otomatik senkronize et."""
        sources = self.search([
            ('state', '=', 'active'),
            ('auto_powerway_sync', '=', True),
            ('powerway_url', '!=', False),
            ('powerway_user', '!=', False),
        ])
        for source in sources:
            try:
                source.action_sync_powerway_orders()
            except Exception as e:
                _logger.error('Powerway cron hatası (%s): %s', source.name, e)

    # Baytek B2B Sipariş Portalı Entegrasyonu
    # ─────────────────────────────────────────────────────────────────

    def _baytek_session(self):
        """Baytek B2B portalına giriş yap, oturumlu session döndür."""
        import requests as _req
        session = _req.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120',
            'Accept-Language': 'tr-TR,tr;q=0.9',
        })
        base = (self.baytek_b2b_url or 'https://www.bayiteknoloji.com').rstrip('/')
        r = session.post(f'{base}/Uyelik/Giris', data={
            'cBayiKodu': self.baytek_b2b_dealer or '',
            'cKullaniciAdi': self.baytek_b2b_user or '',
            'cParola': self.baytek_b2b_password or '',
            'lBeniHatırla': 'false',
        }, timeout=20, allow_redirects=True)
        if 'Hesabım' not in r.text and 'HesabÄ±m' not in r.text and r.url.endswith('/Giris'):
            raise UserError('Baytek giriş başarısız — bayi kodu/kullanıcı/şifre kontrol edin.')
        return session, base

    def _fetch_baytek_orders(self, session, base):
        """Sipariş listesini çek, her biri için detay satırlarını getir."""
        import re as _re, datetime as _dt
        r = session.get(f'{base}/Siparis/SiparisIzleme', timeout=20)

        # Her sipariş satırını tam <tr>...</tr> olarak al; SS numarası içerenleri seç
        all_rows = _re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, _re.DOTALL)
        order_rows = {}
        for row_html in all_rows:
            ss_match = _re.search(r'(SS\d{8})', row_html)
            det_match = _re.search(r'/Siparis/SiparisDetay/(\d+)', row_html)
            if ss_match and det_match:
                siparis_no = ss_match.group(1)
                detail_id = det_match.group(1)
                tds = _re.findall(r'<td[^>]*>(.*?)</td>', row_html, _re.DOTALL)
                row_data = [_re.sub(r'<[^>]+>', '', td).strip() for td in tds]
                order_rows[siparis_no] = {'detail_id': detail_id, 'row_data': row_data}

        orders = []
        for siparis_no, info in order_rows.items():
            detail_id = info['detail_id']
            row_data = info['row_data']
            # Sütunlar: 0=İşlemTürü, 1=SiparisNo, 2=Tarih, 3=Kullanıcı,
            #           4=Durum, 5=KargoTakip, 6=OnayTarih, 7=Tutar, 8=KDV,
            #           9=ParaBirimi, 10=Açıklama
            date_str = row_data[2] if len(row_data) > 2 else ''
            status = _re.sub(r'\s+', ' ', row_data[4]).strip() if len(row_data) > 4 else ''
            amount_str = row_data[7] if len(row_data) > 7 else '0'
            currency = row_data[9] if len(row_data) > 9 else 'USD'

            # Detay satırlarını çek
            det = session.get(f'{base}/Siparis/SiparisDetay/{detail_id}', timeout=15)
            det_tables = _re.findall(r'<table[^>]*>(.*?)</table>', det.text, _re.DOTALL)
            lines = []
            for tbl in det_tables:
                rows2 = _re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, _re.DOTALL)
                if len(rows2) > 1:
                    header_tds = _re.findall(r'<th[^>]*>(.*?)</th>', rows2[0], _re.DOTALL)
                    header = [_re.sub(r'<[^>]+>', '', h).strip() for h in header_tds]
                    if 'Mal Adı' in header or 'Miktar' in header:
                        for rw in rows2[1:]:
                            tds = _re.findall(r'<td[^>]*>(.*?)</td>', rw, _re.DOTALL)
                            vals = [_re.sub(r'<[^>]+>', '', td).strip() for td in tds]
                            if len(vals) >= 3 and vals[0]:
                                # "Ürün Adı\n                40873" → ayrıştır
                                parts = vals[0].rsplit('\n', 1)
                                name = parts[0].strip()
                                product_code = parts[-1].strip() if len(parts) > 1 else ''
                                lines.append({
                                    'name': name,
                                    'product_code': product_code,
                                    'qty': vals[1] if len(vals) > 1 else '1',
                                    'unit_price': vals[2] if len(vals) > 2 else '0',
                                    'net_price': vals[4] if len(vals) > 4 else vals[2],
                                })
                        break
            orders.append({
                'detail_id': detail_id,
                'siparis_no': siparis_no,
                'date': date_str,
                'status': status,
                'amount_str': amount_str,
                'currency': currency,
                'lines': lines,
            })
            import time as _time
            _time.sleep(0.3)
        return orders

    def action_sync_baytek_orders(self):
        """Baytek B2B'den sipariş listesini çekip Odoo'da purchase.order oluştur."""
        self.ensure_one()
        if not self.baytek_b2b_user or not self.baytek_b2b_password:
            raise UserError('Baytek kullanıcı adı ve şifre gerekli.')

        session, base = self._baytek_session()
        orders = self._fetch_baytek_orders(session, base)

        PO = self.env['purchase.order']
        POL = self.env['purchase.order.line']
        usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        vendor = self.env['res.partner'].browse(
            (self.supplier_id).id if self.supplier_id else False
        )
        if not vendor:
            raise UserError('Baytek kaynağında tedarikçi (Satıcı) tanımlı değil.')

        created = skipped = 0
        import datetime as _dt
        for order in orders:
            if not order['lines']:
                skipped += 1
                continue
            ref = f'BT-{order["siparis_no"]}'
            existing = PO.search([('partner_ref', '=', ref)], limit=1)
            if existing:
                skipped += 1
                continue

            date_obj = _dt.date.today()
            try:
                parts = order['date'].split('-')
                date_obj = _dt.date(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception:
                pass

            cur = usd if order.get('currency', 'USD') == 'USD' else self.env.company.currency_id
            po = PO.create({
                'partner_id': vendor.id,
                'partner_ref': ref,
                'date_order': _dt.datetime.combine(date_obj, _dt.time(12, 0)),
                'currency_id': cur.id,
                'note': f'Baytek B2B portalından otomatik oluşturuldu (No: {order["siparis_no"]}, Durum: {order["status"]})',
                'state': 'draft',
            })

            for line in order['lines']:
                try:
                    qty = float(line['qty'].replace(',', '.'))
                except Exception:
                    qty = 1.0
                try:
                    price = float(line['net_price'].replace('.', '').replace(',', '.'))
                except Exception:
                    price = 0.0

                product = False
                if line.get('product_code'):
                    product = self.env['product.template'].search(
                        [('default_code', '=', line['product_code']), ('active', '=', True)], limit=1
                    )
                if not product and line.get('name'):
                    product = self.env['product.template'].search(
                        [('name', 'ilike', line['name'][:25]), ('active', '=', True)], limit=1
                    )

                line_vals = {
                    'order_id': po.id,
                    'name': line['name'],
                    'product_qty': qty,
                    'price_unit': price,
                    'date_planned': _dt.datetime.combine(date_obj, _dt.time(12, 0)),
                }
                if product:
                    line_vals['product_id'] = product.product_variant_ids[:1].id
                POL.create(line_vals)

            created += 1

        self.write({'baytek_last_sync': fields.Datetime.now()})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Baytek Senkron Tamamlandı',
                'message': f'{created} yeni sipariş oluşturuldu, {skipped} atlandı. (Toplam: {len(orders)})',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_baytek_balance(self):
        """Baytek hesap özeti sayfasını tarayıcıda aç."""
        self.ensure_one()
        base = (self.baytek_b2b_url or 'https://www.bayiteknoloji.com').rstrip('/')
        return {
            'type': 'ir.actions.act_url',
            'url': f'{base}/Odeme/HesapOzeti',
            'target': 'new',
        }

    @api.model
    def cron_sync_baytek_orders(self):
        """Cron: Baytek siparişlerini otomatik senkronize et."""
        sources = self.search([
            ('state', '=', 'active'),
            ('auto_baytek_sync', '=', True),
            ('baytek_b2b_user', '!=', False),
        ])
        for source in sources:
            try:
                source.action_sync_baytek_orders()
            except Exception as e:
                _logger.error('Baytek cron hatası (%s): %s', source.name, e)

    # Satış Fiyatı Yeniden Hesaplama
    # ─────────────────────────────────────────────────────────────────

    def action_recalculate_sale_prices(self):
        """Bu kaynaktaki tüm ürünlerin satış fiyatını güncel kur × kar marjıyla yeniden hesapla."""
        self.ensure_one()
        if not self.cost_currency_id:
            raise UserError('Maliyet para birimi tanımlı değil. Lütfen önce "Maliyet Para Birimi" seçin.')

        products = self.env['product.template'].search([
            ('xml_source_id', '=', self.id),
            ('active', '=', True),
        ])
        updated = skipped = 0
        for product in products:
            cost = product.xml_supplier_price or product.standard_price
            if not cost:
                skipped += 1
                continue
            new_price = self._calculate_sale_price(cost)
            if new_price and abs(new_price - product.list_price) > 0.01:
                product.write({'list_price': new_price})
                updated += 1
            else:
                skipped += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Satış Fiyatları Güncellendi',
                'message': f'{updated} ürün güncellendi, {skipped} atlandı.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_fix_supplier_currency(self):
        """Bu kaynaktaki tüm supplierinfo kayıtlarının para birimini cost_currency_id'ye güncelle."""
        self.ensure_one()
        if not self.cost_currency_id:
            raise UserError('Maliyet para birimi tanımlı değil.')
        SI = self.env['product.supplierinfo']
        records = SI.search([('product_tmpl_id.xml_source_id', '=', self.id)])
        records.write({'currency_id': self.cost_currency_id.id})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tedarikçi Para Birimi Güncellendi',
                'message': f'{len(records)} supplierinfo kaydı {self.cost_currency_id.name} olarak güncellendi.',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def cron_recalculate_prices(self):
        """Cron: Döviz kuru güncellendikten sonra satış fiyatlarını yeniden hesapla."""
        sources = self.search([
            ('state', '=', 'active'),
            ('auto_price_recalc', '=', True),
            ('cost_currency_id', '!=', False),
        ])
        for source in sources:
            try:
                source.action_recalculate_sale_prices()
            except Exception as e:
                _logger.error('Fiyat yeniden hesaplama cron hatası (%s): %s', source.name, e)

    # Powerway PO ↔ Asya Pasifik Fatura Eşleştirmesi
    # ─────────────────────────────────────────────────────────────────

    def action_match_vendor_bills(self):
        """Powerway satın alma siparişlerini Asya Pasifik vendor bill'leriyle eşleştir.

        Bill'ler TRY, PO'lar USD cinsinden. Eşleştirme:
        - Aynı tedarikçi
        - Tarih farkı ≤ 60 gün
        - Tutar farkı ≤ 30% (TRY→USD dönüşümü sonrası)
        """
        self.ensure_one()
        PO = self.env['purchase.order']
        AM = self.env['account.move']

        vendor = self.web_price_vendor_id or self.supplier_id
        if not vendor:
            raise UserError('Tedarikçi tanımlı değil.')

        # Powerway PO'ları — henüz faturaya bağlanmamış olanlar
        pw_orders = PO.search([
            ('partner_ref', 'like', 'PW-%'),
            ('partner_id', '=', vendor.id),
        ])
        unlinked_po = {po.id: po for po in pw_orders if not po.invoice_ids}

        # Aynı tedarikçinin tüm vendor bill'leri — invoice_origin boş olanlar (henüz eşleştirilmemiş)
        bills = AM.search([
            ('move_type', '=', 'in_invoice'),
            ('partner_id', '=', vendor.id),
            ('state', 'in', ('draft', 'posted')),
            ('invoice_origin', '=', False),
        ])

        # Güncel USD/TRY kuru
        usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        usd_rate = (1.0 / usd.rate) if usd and usd.rate else 46.0  # TRY_per_USD

        matched = already_linked = 0
        for bill in bills:
            bill_date = bill.invoice_date or (bill.date.date() if hasattr(bill.date, 'date') else bill.date)
            bill_currency = bill.currency_id.name if bill.currency_id else 'TRY'

            # Bill tutarını USD'ye çevir
            if bill_currency == 'USD':
                bill_usd = bill.amount_untaxed
            elif bill_currency == 'TRY' and usd_rate:
                bill_usd = bill.amount_untaxed / usd_rate
            else:
                bill_usd = bill.amount_untaxed

            best_po = None
            best_score = float('inf')
            for po in unlinked_po.values():
                po_date = po.date_order.date() if po.date_order else None
                day_diff = abs((bill_date - po_date).days) if (bill_date and po_date) else 999
                if po.amount_untaxed:
                    amount_diff_pct = abs(bill_usd - po.amount_untaxed) / max(po.amount_untaxed, 0.01) * 100
                else:
                    amount_diff_pct = 100

                if day_diff <= 60 and amount_diff_pct <= 30:
                    score = day_diff * 0.5 + amount_diff_pct
                    if score < best_score:
                        best_score = score
                        best_po = po

            if best_po:
                try:
                    # invoice_origin'e PO ismini yaz (en güvenilir stored link)
                    bill.write({'invoice_origin': best_po.name})
                    matched += 1
                    del unlinked_po[best_po.id]  # bir kez eşleştir
                    _logger.info(
                        'Powerway PO %s (%.2f USD) ↔ Fatura %s (%.2f TRY / %.2f USD)',
                        best_po.partner_ref, best_po.amount_untaxed,
                        bill.name or str(bill.id), bill.amount_untaxed, bill_usd
                    )
                except Exception as e:
                    _logger.warning('Fatura eşleştirme hatası %s: %s', bill.name, e)
            else:
                already_linked += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Fatura Eşleştirme Tamamlandı',
                'message': (
                    f'{matched} fatura Powerway siparişine bağlandı. '
                    f'{already_linked} fatura için uygun PO bulunamadı.'
                ),
                'type': 'info' if matched == 0 else 'success',
                'sticky': False,
            }
        }

    def action_test_connection(self):
        """Bağlantıyı test et"""
        self.ensure_one()

        try:
            xml_content = self._fetch_xml()
            products = self._parse_xml(xml_content)

            self.write({
                'state': 'active',
                'last_error': False,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Bağlantı Başarılı'),
                    'message': _('XML\'de %s ürün bulundu.') % len(products),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            self.write({
                'state': 'error',
                'last_error': str(e),
            })
            raise UserError(_('Bağlantı hatası: %s') % str(e))

    def action_preview_xml(self):
        """XML içeriğini önizle"""
        self.ensure_one()

        try:
            xml_content = self._fetch_xml()
            products = self._parse_xml(xml_content)

            if products:
                # İlk 3 ürünü göster
                preview = []
                for i, prod in enumerate(products[:3]):
                    data = self._extract_product_data(prod)
                    preview.append(f"Ürün {i+1}: {json.dumps(data, ensure_ascii=False, indent=2)}")

                preview_text = '\n\n'.join(preview)

                raise UserError(_('XML Önizleme (%s ürün bulundu):\n\n%s') % (len(products), preview_text))
            else:
                raise UserError(_('XML\'de ürün bulunamadı. Root element yolunu kontrol edin.'))

        except UserError:
            raise
        except Exception as e:
            raise UserError(_('Önizleme hatası: %s') % str(e))

    def _import_products_from_xml(self):
        """Ürünleri içe aktar"""
        self.ensure_one()

        # Log oluştur
        log = self.env['xml.import.log'].create({
            'source_id': self.id,
            'start_time': fields.Datetime.now(),
            'state': 'running',
        })

        created = updated = skipped = failed = 0
        processed_since_commit = 0
        errors = []

        try:
            # XML çek ve parse et
            xml_content = self._fetch_xml()
            products = self._parse_xml(xml_content)

            # Index Grup / Netex: Ayrı stok ve fiyat feedlerini önceden çek
            _ig_stock_map = {}
            _ig_price_map = {}
            if self.xml_template in ('indexgrup', 'netex'):
                _ig_stock_map = self._fetch_indexgrup_stock_map()
                _ig_price_map = self._fetch_indexgrup_price_map()

            log.total_products = len(products)

            _logger.info(f"XML Import: {len(products)} ürün bulundu - {self.name}")

            for element in products:
                try:
                    # Ürün bazında SQL hataları transaction'ı abort etmesin diye savepoint kullan.
                    # (Aksi halde bir ürün hatasından sonra self.write/log.write InFailedSqlTransaction'a düşer.)
                    with self.env.cr.savepoint():
                        # Ürün verilerini çıkar
                        data = self._extract_product_data(element)

                        # Index Grup / Netex: Stok ve fiyat bilgilerini birleştir
                        if self.xml_template in ('indexgrup', 'netex'):
                            globalkod = data.get('sku', '')
                            if globalkod and globalkod in _ig_stock_map:
                                data['stock'] = str(_ig_stock_map[globalkod])
                            if globalkod and globalkod in _ig_price_map:
                                pinfo = _ig_price_map[globalkod]
                                data['cost_price'] = str(pinfo.get('cost_price', 0))
                                data['price'] = str(pinfo.get('dealer_price', 0) or pinfo.get('cost_price', 0))
                                if pinfo.get('currency'):
                                    data['currency'] = pinfo['currency']
                        data = self._extract_product_data(element)

                        if not data.get('name'):
                            skipped += 1
                            continue

                        skip_product, skip_reason = self._should_skip_product_data(data)
                        if skip_product:
                            skipped += 1
                            _logger.info('XML import skip: %s - %s', data.get('name'), skip_reason)
                            continue

                        # Fiyat kontrolü (virgüllü ondalık ve binlik ayraçları normalize et)
                        def _to_float(v):
                            try:
                                s = str(v).strip()
                                if not s or s == '0':
                                    return 0.0
                                if ',' in s and '.' not in s:
                                    s = s.replace(',', '.')
                                elif ',' in s and '.' in s:
                                    s = s.replace('.', '').replace(',', '.')
                                return float(s)
                            except (ValueError, TypeError):
                                return 0.0
                        price = _to_float(data.get('price') or 0)
                        cost = _to_float(data.get('cost_price') or data.get('price') or 0)

                        if self.min_price and price < self.min_price:
                            skipped += 1
                            continue
                        if self.max_price and price > self.max_price:
                            skipped += 1
                            continue

                        # Stok kontrolü (sadece min_stock > 0 ise kontrol et)
                        stock = int(data.get('stock', 0) or 0)
                        if self.min_stock > 0 and stock < self.min_stock:
                            # Stok min_stock altında - mevcut ürünü kontrol et
                            existing, match_type = self._find_existing_product(data)
                            if existing and existing.exists():
                                # Tedarikçi stoğunu güncelle
                                existing.write({
                                    'xml_supplier_stock': stock,
                                    'xml_last_sync': fields.Datetime.now(),
                                })
                                # Stok 0 ise ve ayarlar aktifse işle
                                if stock == 0 and (self.deactivate_zero_stock or self.delete_unsold_zero_stock):
                                    self._handle_zero_stock_product(existing)
                                elif self.deactivate_zero_stock and existing.exists():
                                    # Stok min_stock altında ama 0 değil - sadece satışa kapat
                                    existing.write({'sale_ok': False})
                                    _logger.info(f"Stok yetersiz ({stock} < {self.min_stock}) - ürün satışa kapatıldı: {existing.name}")
                            skipped += 1
                            continue

                        # Mevcut ürün ara
                        existing, match_type = self._find_existing_product(data)
                        usage_class = self._classify_usage(data)

                        # Parantezden varyant kontrolü
                        name = str(data.get('name', '')).strip()
                        base_name, variant_name = self._extract_base_and_variant(name)

                        if existing:
                            # Arşivlenmiş ürün eşleştiyse aktif hale getir (tekilleştirme için)
                            if hasattr(existing, 'active') and not existing.active:
                                reactivate_vals = {'active': True, 'purchase_ok': True}
                                if usage_class == 'commercial':
                                    reactivate_vals['sale_ok'] = True
                                existing.write(reactivate_vals)
                                # Şablon aktif olurken varyantları da aktif et (aksi halde barkod eşleşmesi zorlaşır)
                                variants = existing.with_context(active_test=False).product_variant_ids
                                if variants:
                                    variants.write({'active': True})

                            # Eğer varyant modu aktif ve bu ürün varyantlı ise
                            if usage_class == 'commercial' and self.variant_from_parentheses and self.create_variants and variant_name:
                                # Bu varyant zaten var mı kontrol et (barkod ile)
                                barcode = data.get('barcode')
                                existing_variant = self.env['product.product'].with_context(active_test=False).search([
                                    ('barcode', '=', barcode)
                                ], limit=1) if barcode else None

                                if not existing_variant:
                                    # Yeni varyant ekle
                                    self._create_color_variant(existing, variant_name, data, cost)
                                    updated += 1
                                    _logger.info(f"Varyant eklendi: {existing.name} - {variant_name}")
                                elif self.update_existing:
                                    # Varyant zaten var, güncelle
                                    self._update_product(existing, data, cost, price)
                                    updated += 1
                                else:
                                    skipped += 1
                            elif self.update_existing:
                                self._update_product(existing, data, cost, price)
                                updated += 1
                            else:
                                skipped += 1
                        else:
                            if self.create_new_products:
                                self._create_product(data, cost, price)
                                created += 1
                            else:
                                skipped += 1

                except Exception as e:
                    failed += 1
                    errors.append(f"{data.get('name', 'Bilinmiyor')}: {str(e)}")
                    _logger.error(f"Ürün import hatası: {e}")

                processed_since_commit += 1
                if processed_since_commit >= 50:
                    self.env.cr.commit()
                    processed_since_commit = 0

            # Sonuçları kaydet
            if processed_since_commit:
                self.env.cr.commit()
            self.write({
                'last_sync': fields.Datetime.now(),
                'state': 'active',
                'last_error': False,
            })

            log.write({
                'end_time': fields.Datetime.now(),
                'state': 'done',
                'products_created': created,
                'products_updated': updated,
                'products_skipped': skipped,
                'products_failed': failed,
                'error_details': '\n'.join(errors) if errors else False,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('İçe Aktarım Tamamlandı'),
                    'message': _('Oluşturulan: %s, Güncellenen: %s, Atlanan: %s, Hatalı: %s') % (
                        created, updated, skipped, failed
                    ),
                    'type': 'success' if failed == 0 else 'warning',
                    'sticky': True,
                }
            }

        except Exception as e:
            self.write({
                'state': 'error',
                'last_error': str(e),
            })
            log.write({
                'end_time': fields.Datetime.now(),
                'state': 'error',
                'error_details': str(e),
            })
            raise UserError(_('İçe aktarım hatası: %s') % str(e))

    def _create_product(self, data, cost_price, xml_price):
        """Yeni ürün oluştur veya varyant ekle"""
        self.ensure_one()

        name = str(data.get('name', '')).strip() if data.get('name') else ''
        sku = str(data.get('sku', '')).strip() if data.get('sku') else ''
        barcode = str(data.get('barcode', '')).strip() if data.get('barcode') else ''

        # 🚀 BARKOD ÇAKIŞMA KONTROLÜ (Kritik Düzeltme)
        if barcode:
            existing_product = self.env['product.product'].with_context(active_test=False).search([
                ('barcode', '=', barcode)
            ], limit=1)
            if existing_product:
                _logger.info(f"Barkod çakışması engellendi: {barcode} zaten {existing_product.display_name} ürününe ait. Yeni kart açılmadı.")
                return existing_product.product_tmpl_id

        # ═══════════════════════════════════════════════════════════════
        # PARANTEZDEN VARYANT MODU
        # Örnek: "BOLD SPEAKER (KIRMIZI)" → Ana ürün: BOLD SPEAKER, Varyant: KIRMIZI
        # ═══════════════════════════════════════════════════════════════
        usage_class = self._classify_usage(data)

        if usage_class == 'commercial' and self.variant_from_parentheses and self.create_variants:
            base_name, variant_name = self._extract_base_and_variant(name)

            if variant_name:
                # Parantez içinde varyant bilgisi var
                # Aynı barkod zaten var mı kontrol et
                existing_barcode = self.env['product.product'].search([
                    ('barcode', '=', data.get('barcode')),
                ], limit=1)

                if existing_barcode:
                    # Bu barkod zaten var, güncelle
                    _logger.debug(f"Barkod zaten mevcut, güncelleme yapılacak: {data.get('barcode')}")
                    return existing_barcode.product_tmpl_id

                # Ana ürünü bul veya oluştur
                base_product = self._find_or_create_base_product(base_name, data, cost_price)

                # Varyant oluştur
                variant = self._create_color_variant(base_product, variant_name, data, cost_price)
                if variant:
                    return base_product

        # ═══════════════════════════════════════════════════════════════
        # STANDART VARYANT MODU (SKU prefix tabanlı)
        # ═══════════════════════════════════════════════════════════════
        sku_prefix = self._get_sku_prefix(sku)

        if usage_class == 'commercial' and self.create_variants and sku_prefix and data.get('barcode'):
            # SKU prefix ile eşleşen ürün ara
            existing_by_prefix = self.env['product.template'].search([
                ('default_code', '=like', sku_prefix + '%'),
            ], limit=1)

            if existing_by_prefix:
                # Aynı barkod zaten var mı kontrol et
                existing_barcode = self.env['product.product'].search([
                    ('barcode', '=', data.get('barcode')),
                ], limit=1)

                if not existing_barcode:
                    # Aynı SKU prefix var, farklı barkodlu varyant olarak ekle
                    return self._create_variant(existing_by_prefix, data, cost_price)

        # Barkod ve SKU yoksa isimle son bir duplikat kontrolü yap
        if not data.get('barcode') and not sku:
            name_check = str(data.get('name', '')).strip()
            if name_check:
                existing_by_name = self.env['product.template'].search(
                    [('name', '=ilike', name_check)], limit=1
                )
                if existing_by_name:
                    _logger.info(f"İsim eşleşmesiyle duplikat engellendi: {name_check} → ID {existing_by_name.id}")
                    return existing_by_name

        sale_price = self._calculate_sale_price(cost_price)

        vals = {
            'name': data.get('name'),
            'default_code': data.get('sku'),
            'barcode': data.get('barcode'),
            'description_sale': data.get('description'),
            'list_price': sale_price,
            'standard_price': cost_price,
            # Dropshipping alanları
            'xml_source_id': self.id,
            'xml_supplier_price': cost_price,
            'xml_supplier_sku': data.get('sku'),
            'xml_last_sync': fields.Datetime.now(),
            'is_dropship': True,
        }
        vals.update(self._normalized_product_defaults(data))

        # Görsel
        if data.get('image'):
            image_url = data.get('image')
            vals['xml_image_url'] = image_url
            # Görseli indir veya URL olarak ekle
            if self.download_images:
                image_data = self._download_image(image_url)
                if image_data:
                    vals['image_1920'] = image_data

        # Açıklama
        if data.get('description'):
            description = data.get('description')
            # HTML temizleme (opsiyonel)
            description = self._clean_html(description)
            vals['description_sale'] = description
            vals['description'] = description

        # Kısa açıklama → teslim notu alanı
        if data.get('description_short'):
            vals['description_picking'] = self._clean_html(data['description_short'])

        # Tedarikçi stok
        if data.get('stock'):
            try:
                vals['xml_supplier_stock'] = int(data.get('stock'))
            except (ValueError, TypeError):
                pass

        # Kategori eşleştirme (manuel + otomatik)
        category_result = self._apply_category_mapping(data.get('category'), data.get('extra1'))
        if category_result.get('categ_id'):
            vals['categ_id'] = category_result['categ_id']
        if category_result.get('public_categ_ids'):
            vals['public_categ_ids'] = category_result['public_categ_ids']
        if not vals.get('categ_id'):
            default_category = self._default_category_for_usage(vals.get('xml_usage_class'))
            if default_category:
                vals['categ_id'] = default_category.id

        if self.supplier_id:
            vals['xml_supplier_id'] = self.supplier_id.id

        # Desi/Ağırlık
        if data.get('weight'):
            try:
                vals['weight'] = float(data['weight'])
            except (ValueError, TypeError):
                pass

        if data.get('deci'):
            try:
                vals['volume'] = float(data['deci'])
                vals['deci'] = float(data['deci'])
            except (ValueError, TypeError):
                pass

        # Marka
        if data.get('brand'):
            vals['xml_brand'] = str(data['brand']).strip()

        # Garanti
        if data.get('warranty'):
            vals['xml_warranty'] = str(data['warranty']).strip()

        # Model
        if data.get('model'):
            vals['xml_model'] = str(data['model']).strip()

        # Menşei
        if data.get('origin'):
            vals['xml_origin'] = str(data['origin']).strip()

        # Ekstra alanlar
        if data.get('extra2'):
            vals['xml_extra2'] = str(data['extra2']).strip()
        if data.get('extra3'):
            vals['xml_extra3'] = str(data['extra3']).strip()

        # KDV (taxes_id)
        if data.get('tax'):
            tax = self._find_tax_by_value(data['tax'])
            if tax:
                vals['taxes_id'] = [(6, 0, [tax.id])]

        product = self.env['product.template'].create(vals)

        # Görsel URL olarak ekle (indirmeden)
        if data.get('image') and not self.download_images:
            self._set_image_from_url(product, data.get('image'))

        # Ek görseller ekle
        if data.get('extra_images'):
            if self.download_images:
                self._add_extra_images(product, data.get('extra_images'))
            else:
                self._add_extra_images_from_url(product, data.get('extra_images'))

        # Dropship rotası ekle (stock_dropshipping modülü)
        dropship_route = self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False)
        if dropship_route:
            product.write({'route_ids': [(4, dropship_route.id)]})

        # Tedarikçi fiyat/kod product.supplierinfo ile senkron (product_template inverse ile yazılıyor)

        _logger.info(f"Yeni ürün oluşturuldu (Dropship): {product.name}")

        return product

    def _add_extra_images(self, product, image_urls):
        """Ürüne ek görseller ekle"""
        if not image_urls:
            return

        ProductImage = self.env.get('product.image')
        if not ProductImage:
            # product.image modeli yoksa URL'leri text alanında sakla
            urls_text = '\n'.join(image_urls)
            product.write({'xml_image_urls': urls_text})
            return

        for i, url in enumerate(image_urls[:5]):  # Max 5 ek görsel
            try:
                image_data = self._download_image(url)
                if image_data:
                    ProductImage.create({
                        'product_tmpl_id': product.id,
                        'name': f"{product.name} - Görsel {i+2}",
                        'image_1920': image_data,
                    })
                    _logger.debug(f"Ek görsel eklendi: {product.name} - {i+2}")
            except Exception as e:
                _logger.warning(f"Ek görsel eklenemedi: {url} - {e}")

    def _set_image_from_url(self, product, image_url):
        """
        Ürüne görsel URL'sini kaydet.

        Not: Bu akış "download_images=False" iken kullanılır. Bu durumda görsel indirmek
        ürün güncellemesini çok yavaşlatabildiği için sadece URL saklanır.
        """
        if not image_url:
            return

        # URL'yi kaydet
        product.write({'xml_image_url': image_url})


    def _add_extra_images_from_url(self, product, image_urls):
        """Ürüne ek görsel URL'lerini ekle (indirmeden, sadece URL saklanır)"""
        if not image_urls:
            return

        # URL'leri text alanında sakla - disk tasarrufu
        urls_text = '\n'.join(image_urls[:10])  # Max 10 ek görsel URL
        product.write({'xml_image_urls': urls_text})
        _logger.debug(f"Ek görsel URL'leri kaydedildi: {product.name} - {len(image_urls)} adet")

    def _create_variant(self, product_tmpl, data, cost_price):
        """Mevcut ürüne varyant ekle (farklı barkod) — Barkod attribute kaldırıldı, ayrı ürün olarak devam et"""
        self.ensure_one()
        _logger.info(
            f"_create_variant: '{product_tmpl.name}' için barkod='{data.get('barcode')}' "
            f"ayrı ürün olarak oluşturulacak (Barkod attribute kullanılmıyor)"
        )
        return None

    def _update_product(self, product, data, cost_price, xml_price):
        """Mevcut ürünü güncelle"""
        self.ensure_one()
        protect_core = self._is_reference_locked_product(product) or not self._can_rebind_product_identity(product, data)
        usage_class = self._classify_usage(data)

        vals = {
            'xml_source_id': self.id,
            'xml_supplier_sku': data.get('sku'),
            'xml_last_sync': fields.Datetime.now(),
            'is_dropship': True,
        }
        vals.update(self._normalized_product_defaults(data, protect_core=protect_core))

        # Muhasebeye bağlanmış ürünlerde ad/kod gibi çekirdek kimlikleri oynatma.
        if data.get('name') and not protect_core:
            vals['name'] = data['name']

        # İç referans (default_code) güncelleme
        if data.get('sku') and not protect_core:
            base_sku, _ = self._extract_base_and_variant(str(data['sku']).strip())
            if base_sku:
                vals['default_code'] = base_sku

        # Fiyat güncelleme - sadece değer varsa güncelle kuralına göre
        if self.update_price:
            if cost_price and cost_price > 0:
                sale_price = self._calculate_sale_price(cost_price)
                vals['list_price'] = sale_price
                vals['standard_price'] = cost_price
                vals['xml_supplier_price'] = cost_price
            elif not self.update_only_if_value:
                # update_only_if_value kapalıysa, değer olmasa da güncelle
                sale_price = self._calculate_sale_price(cost_price or 0)
                vals['list_price'] = sale_price
                vals['standard_price'] = cost_price or 0
                vals['xml_supplier_price'] = cost_price or 0
        elif cost_price and cost_price > 0:
            # Fiyat güncellemesi kapalı ama tedarikçi fiyatını kaydet
            vals['xml_supplier_price'] = cost_price

        # Stok güncelleme - sadece değer varsa güncelle kuralına göre
        if self.update_stock:
            stock_val = data.get('stock')
            if stock_val is not None and str(stock_val).strip():
                try:
                    stock_qty = int(stock_val)
                    vals['xml_supplier_stock'] = stock_qty
                    # Stok yeterli, daha önce kapatıldıysa tekrar aç
                    if usage_class == 'commercial' and stock_qty >= self.min_stock and not product.sale_ok:
                        vals['sale_ok'] = True
                        _logger.info(f"Stok yeterli ({stock_qty}) - ürün satışa tekrar açıldı: {product.name}")
                except (ValueError, TypeError):
                    pass
            elif not self.update_only_if_value:
                # update_only_if_value kapalıysa, değer olmasa da güncelle (0 yap)
                vals['xml_supplier_stock'] = 0

        # Görsel güncelle
        if self.update_images and data.get('image'):
            image_url = data.get('image')
            vals['xml_image_url'] = image_url
            # Görseli indir veya URL olarak ekle
            if self.download_images:
                image_data = self._download_image(image_url)
                if image_data:
                    vals['image_1920'] = image_data

        # Açıklama güncelle
        if self.update_description and data.get('description'):
            description = data.get('description')
            description = self._clean_html(description)
            vals['description_sale'] = description
            vals['description'] = description

        # Kategori güncelleme (manuel + otomatik)
        if data.get('category'):
            category_result = self._apply_category_mapping(data.get('category'), data.get('extra1'))
            if category_result.get('categ_id'):
                vals['categ_id'] = category_result['categ_id']
            if category_result.get('public_categ_ids'):
                vals['public_categ_ids'] = category_result['public_categ_ids']
        if not vals.get('categ_id'):
            default_category = self._default_category_for_usage(usage_class)
            if default_category:
                vals['categ_id'] = default_category.id

        if self.supplier_id:
            vals['xml_supplier_id'] = self.supplier_id.id

        # Marka
        if data.get('brand'):
            vals['xml_brand'] = str(data['brand']).strip()

        # Garanti
        if data.get('warranty'):
            vals['xml_warranty'] = str(data['warranty']).strip()

        # Model
        if data.get('model'):
            vals['xml_model'] = str(data['model']).strip()

        # Menşei
        if data.get('origin'):
            vals['xml_origin'] = str(data['origin']).strip()

        # Kısa açıklama → teslim notu alanı
        if data.get('description_short'):
            vals['description_picking'] = self._clean_html(data['description_short'])

        # Ekstra alanlar
        if data.get('extra2'):
            vals['xml_extra2'] = str(data['extra2']).strip()
        if data.get('extra3'):
            vals['xml_extra3'] = str(data['extra3']).strip()

        # KDV (taxes_id) — sadece mevcut yoksa ekle, üzerine yazma
        if data.get('tax') and not product.taxes_id:
            tax = self._find_tax_by_value(data['tax'])
            if tax:
                vals['taxes_id'] = [(6, 0, [tax.id])]

        product.write(vals)

        # Barkod güncelleme — product.product varyantı üzerinde
        if data.get('barcode'):
            barcode = str(data['barcode']).strip()
            if barcode:
                variants = product.product_variant_ids
                if len(variants) == 1:
                    # Tek varyanttaki barkodu güncelle (farklıysa)
                    if variants.barcode != barcode and self._can_rebind_product_identity(product, data):
                        variants.write({'barcode': barcode})

        # Görsel URL olarak ekle (güncelleme sonrası)
        if self.update_images and data.get('image') and not self.download_images:
            self._set_image_from_url(product, data.get('image'))

        # Ek görselleri güncelle
        if self.update_images and data.get('extra_images'):
            if self.download_images:
                self._add_extra_images(product, data.get('extra_images'))
            else:
                self._add_extra_images_from_url(product, data.get('extra_images'))

        _logger.debug(f"Ürün güncellendi: {product.name}")

        return product

    def _handle_zero_stock_product(self, product):
        """Stok 0 olan ürünü işle"""
        self.ensure_one()

        if not product:
            return

        if self._is_reference_locked_product(product):
            if product.exists():
                product.write({'sale_ok': False})
                _logger.info(
                    "Stok 0 - iliskili urun sadece satisa kapatildi: %s",
                    product.name,
                )
            return

        # Ürünün satış geçmişi var mı kontrol et
        has_sales = self.env['sale.order.line'].search_count([
            ('product_id.product_tmpl_id', '=', product.id),
            ('state', 'in', ['sale', 'done']),
        ]) > 0

        if self.delete_unsold_zero_stock and not has_sales:
            # Satışı yok, sil
            product_name = product.name
            try:
                # Ürün hala var mı kontrol et
                if not product.exists():
                    return
                # Önce product.product kayıtlarını sil
                variants = product.product_variant_ids.exists()
                if variants:
                    variants.unlink()
                if product.exists():
                    product.unlink()
                _logger.info(f"Stok 0, satışı yok - ürün silindi: {product_name}")
            except Exception as e:
                _logger.warning(f"Ürün silinemedi ({product_name}): {e}")
                # Silinemezse satışa kapat
                if product.exists():
                    product.write({'sale_ok': False})
        elif self.deactivate_zero_stock:
            # Satışa kapat
            if product.exists():
                product.write({'sale_ok': False})
                _logger.info(f"Stok 0 - ürün satışa kapatıldı: {product.name}")

    # ══════════════════════════════════════════════════════════════════════════
    # CRON
    # ══════════════════════════════════════════════════════════════════════════

    @api.model
    def cron_sync_all_sources(self):
        """Tüm aktif kaynakları senkronize et (Cron job)"""
        sources = self.search([
            ('state', '=', 'active'),
            ('auto_sync', '=', True),
        ])

        for source in sources:
            if source.next_sync and source.next_sync <= fields.Datetime.now():
                try:
                    source.action_import_products()
                except Exception as e:
                    _logger.error(f"Cron sync hatası ({source.name}): {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def action_view_products(self):
        """Bu kaynaktan gelen ürünleri görüntüle"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ürünler - %s') % self.name,
            'res_model': 'product.template',
            'view_mode': 'list,form',
            'domain': [('xml_source_id', '=', self.id)],
            'context': {'default_xml_source_id': self.id},
        }

    def action_view_logs(self):
        """İçe aktarım loglarını görüntüle"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('İçe Aktarım Logları - %s') % self.name,
            'res_model': 'xml.import.log',
            'view_mode': 'list,form',
            'domain': [('source_id', '=', self.id)],
        }

    def action_activate(self):
        """Kaynağı aktifleştir"""
        self.write({'state': 'active'})

    def action_pause(self):
        """Kaynağı duraklat"""
        self.write({'state': 'paused'})

    def action_reset(self):
        """Kaynağı sıfırla"""
        self.write({
            'state': 'draft',
            'last_error': False,
        })
    def action_apply_dropship_route(self):
        """Tüm XML ürünlerine dropship rotası uygula"""
        self.ensure_one()

        dropship_route = self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False)
        if not dropship_route:
            raise UserError(_('Dropship rotası bulunamadı. stock_dropshipping modülü kurulu mu?'))

        products = self.env['product.template'].search([
            ('xml_source_id', '=', self.id),
            ('route_ids', 'not in', [dropship_route.id]),
        ])

        count = 0
        for product in products:
            if dropship_route.id not in product.route_ids.ids:
                product.write({'route_ids': [(4, dropship_route.id)]})
                count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Dropship Rotası Uygulandı'),
                'message': _('%s ürüne Transit Satış (Dropship) rotası eklendi.') % count,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_sync_suppliers(self):
        """Tüm XML ürünlerine tedarikçi bilgisi ekle"""
        self.ensure_one()

        if not self.supplier_id:
            raise UserError(_('Lütfen önce tedarikçi seçin.'))

        products = self.env['product.template'].search([
            ('xml_source_id', '=', self.id),
        ])

        count = 0
        for product in products:
            # Tedarikçi zaten ekli mi?
            existing = self.env['product.supplierinfo'].search([
                ('product_tmpl_id', '=', product.id),
                ('partner_id', '=', self.supplier_id.id),
            ], limit=1)

            si_vals = {
                'product_tmpl_id': product.id,
                'partner_id': self.supplier_id.id,
                'price': product.xml_supplier_price or product.standard_price,
                'product_code': product.xml_supplier_sku or product.default_code,
            }
            if self.cost_currency_id:
                si_vals['currency_id'] = self.cost_currency_id.id
            if not existing:
                self.env['product.supplierinfo'].create(si_vals)
                count += 1
            else:
                # Para birimini güncelle
                if self.cost_currency_id and existing.currency_id != self.cost_currency_id:
                    existing.write({'currency_id': self.cost_currency_id.id})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tedarikçi Senkronize Edildi'),
                'message': _('%s ürüne tedarikçi bilgisi eklendi.') % count,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_import_products(self):
        """Ürünleri içe aktar - XML veya Web Scraping"""
        self.ensure_one()
        
        if self.source_type == 'web':
            return self._import_products_from_web()
        else:
            return self._import_products_from_xml()

    def _import_products_from_web(self):
        """Web scraping ile ürünleri içe aktar"""
        _logger.info(f"Web scraping başlatılıyor: {self.name}")
        
        try:
            # Scraper sınıfını dinamik olarak yükle
            scraper_class = self.scraper_class or 'BaseScraper'
            
            # Konfigürasyonu parse et
            config = {}
            if self.scraping_config:
                try:
                    config = json.loads(self.scraping_config)
                except json.JSONDecodeError:
                    _logger.warning("Scraping konfigürasyonu geçersiz JSON formatında")
            
            # Anahtar kelimeleri parse et
            keywords = []
            if self.scraping_keywords:
                keywords = [k.strip() for k in self.scraping_keywords.split('\n') if k.strip()]
            
            # Scraper'ı çalıştır
            if self.xml_template == 'tesan_web':
                return self._run_tesan_scraper(keywords, config)
            elif self.xml_template == 'linktech_web':
                return self._run_linktech_scraper(keywords, config)
            else:
                raise UserError(f"Web scraping şablonu desteklenmiyor: {self.xml_template}")
                
        except Exception as e:
            _logger.error(f"Web scraping hatası: {e}")
            self.write({
                'state': 'error',
                'last_error': str(e),
            })
            raise UserError(f"Web scraping hatası: {e}")

    def _run_tesan_scraper(self, keywords, config):
        """Tesan scraper'ını çalıştır"""
        try:
            # Önce mutlak yolu dene
            try:
                from odoo.addons.mobilsoft_xml_import.scrapers.tesan.tesan_scraper import TesanScraper
            except ImportError:
                # Olmazsa göreceli yolu dene
                from ..scrapers.tesan.tesan_scraper import TesanScraper

            scraper = TesanScraper(
                base_url=self.xml_url or 'https://isortagim.tesan.com.tr',
                username=self.xml_username or 'info@jokergrubu.com',
                password=self.xml_password or 'XZsawq21-',
                config=config
            )

            if not scraper.login():
                raise UserError("Tesan API'ye giriş yapılamadı. Kullanıcı adı/şifre kontrol edin.")

            products = scraper.scrape_products()

            # Ürünleri Odoo'ya aktar — fiyat için get_product_data() çağır
            import time
            count = 0
            for product_data in products:
                product_id = product_data.get('id')
                if product_id:
                    detail = scraper.get_product_data(product_id)
                    if detail:
                        product_data.update(detail)
                    time.sleep(0.15)  # API rate limiting
                self._create_or_update_product_from_scraping(product_data)
                count += 1
            
            self.write({
                'state': 'active',
                'last_sync': fields.Datetime.now(),
                'last_error': False,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Web Scraping Başarılı'),
                    'message': _('%s ürün içe aktarıldı.') % count,
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Tesan scraper yükleme veya çalışma hatası: {e}")
            raise UserError(f"Tesan scraper modülü çalıştırılamadı: {e}")

    def _run_linktech_scraper(self, keywords, config):
        """LinkTech scraper'ını çalıştır"""
        try:
            from .scrapers.linktech_scraper import LinkTechScraper
            
            scraper = LinkTechScraper(
                base_url=self.xml_url or 'https://www.linktech.com.tr',
                keywords=keywords,
                config=config
            )
            
            products = scraper.scrape_products()
            
            # Ürünleri Odoo'ya aktar
            count = 0
            for product_data in products:
                self._create_or_update_product_from_scraping(product_data)
                count += 1
            
            self.write({
                'state': 'active',
                'last_sync': fields.Datetime.now(),
                'last_error': False,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Web Scraping Başarılı'),
                    'message': _('%s ürün içe aktarıldı.') % count,
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except ImportError:
            raise UserError("LinkTech scraper modülü bulunamadı. Lütfen scraper'ı kurun.")

    def _create_or_update_product_from_scraping(self, product_data):
        """Scraping verisinden ürün oluştur veya güncelle"""
        sku = product_data.get('sku')
        barcode = product_data.get('barcode')
        if not sku:
            return

        # 🚀 BARKOD ÇAKIŞMA KONTROLÜ
        if barcode:
            existing_barcode = self.env['product.product'].with_context(active_test=False).search([
                ('barcode', '=', barcode)
            ], limit=1)
            if existing_barcode:
                _logger.info(f"Scraping barkod çakışması engellendi: {barcode}")
                return
        
        # Mevcut ürünü ara
        product = self.env['product.template'].search([
            ('default_code', '=', sku),
        ], limit=1)
        
        incoming_cost  = float(product_data.get('cost_price') or 0)
        incoming_price = float(product_data.get('price') or 0)

        # USD maliyeti TRY'ye çevir (güncel kur kullan)
        incoming_cost_try = 0.0
        if incoming_cost:
            usd_currency = self.env['res.currency'].search([('name','=','USD')], limit=1)
            usd_rate = usd_currency.rate if usd_currency and usd_currency.rate else 1.0
            incoming_cost_try = incoming_cost / usd_rate  # USD → TRY

        if product:
            # Güncelle
            update_vals = {
                'name': product_data.get('name', product.name),
                'description_sale': product_data.get('description', product.description_sale),
                'xml_supplier_price': incoming_cost or product.xml_supplier_price,
                'xml_supplier_sku': sku,
                'xml_source_id': self.id,
            }
            if incoming_cost_try:
                update_vals['standard_price'] = incoming_cost_try
            if incoming_price:
                update_vals['list_price'] = incoming_price
            product.write(update_vals)
        else:
            # Yeni ürün oluştur
            product = self.env['product.template'].create({
                'default_code': sku,
                'name': product_data.get('name', 'Ürün'),
                'list_price': incoming_price,
                'standard_price': incoming_cost_try,
                'description_sale': product_data.get('description', ''),
                'xml_supplier_price': incoming_cost,
                'xml_supplier_sku': sku,
                'xml_source_id': self.id,
                'type': 'consu',
            })
        
        # Stok durumuna göre görünürlük ayarla
        raw_stock = float(product_data.get('raw_stock', 0) or 0)
        stock_status = product_data.get('stock_status', 'out_of_stock')
        
        is_available = (raw_stock > 0 or stock_status == 'in_stock')
        product.write({
            'sale_ok': is_available,
            'is_published': is_available
        })

        # Kategori ata
        if product_data.get('category'):
            self._assign_category_to_product(product, product_data['category'])
