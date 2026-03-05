# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import logging
import re
import json
import base64
import time
from difflib import SequenceMatcher
from io import BytesIO

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

    # XML Yapısı
    xml_template = fields.Selection([
        ('tsoft', 'T-Soft'),
        ('ticimax', 'Ticimax'),
        ('ideasoft', 'IdeaSoft'),
        ('akinsoft', 'Akinsoft (Wolvox)'),
        ('opencart', 'OpenCart'),
        ('woocommerce', 'WooCommerce'),
        ('prestashop', 'PrestaShop'),
        ('shopify', 'Shopify'),
        ('magento', 'Magento'),
        ('google', 'Google Shopping'),
        ('n11', 'N11'),
        ('trendyol', 'Trendyol'),
        ('hepsiburada', 'Hepsiburada'),
        ('cimri', 'Cimri'),
        ('akakce', 'Akakçe'),
        ('custom', 'Özel (Custom)'),
    ], string='XML Şablonu', default='custom', required=True)

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
            'opencart': '//products/product',
            'woocommerce': '//rss/channel/item',
            'prestashop': '//products/product',
            'shopify': '//products/product',
            'magento': '//products/product',
            'google': '//feed/entry',
            'n11': '//Products/Product',
            'trendyol': '//items/item',
            'hepsiburada': '//products/product',
            'cimri': '//products/product',
            'akakce': '//Products/Product',
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

    def _find_or_create_public_category_path(self, parts):
        """E-ticaret kategori yolunu var ise al, yoksa oluştur."""
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
                category = PublicCategory.create({
                    'name': name,
                    'parent_id': parent.id if parent else False,
                })
                _logger.info(
                    'Yeni e-ticaret kategorisi oluşturuldu: %s',
                    ' > '.join(current_path),
                )
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
            public_category = self._find_or_create_public_category_path(public_path)
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
                product_category = ProductCategory.search([('name', '=ilike', candidate)], limit=1)
            if not ecommerce_categories:
                ecommerce_categories = PublicCategory.search([('name', '=ilike', candidate)], limit=1)
            if product_category and ecommerce_categories:
                break

        return product_category, ecommerce_categories

    def _sync_template_category_mappings(self, mapping_data):
        """Şablon yüklendikten sonra XML içindeki kategorileri kategori eşleme sekmesine taşı."""
        self.ensure_one()

        category_path = mapping_data.get('category')
        if not category_path or not self.xml_url:
            return 0

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
                ecommerce_category = self._find_or_create_public_category_path(ecommerce_path)
                if ecommerce_category:
                    ecommerce_categories = ecommerce_category
            Mapping.create({
                'source_id': self.id,
                'sequence': start_sequence + (index * 10),
                'xml_category': xml_category,
                'match_type': 'exact',
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
                        ecommerce_category = self._find_or_create_public_category_path(ecommerce_path)
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
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; OdooBot/1.0)',
                'Accept': 'application/xml, text/xml, */*',
            }

            auth = None
            if self.xml_username and self.xml_password:
                auth = (self.xml_username, self.xml_password)

            # Bazı XML servisleri yavaş yanıt verebiliyor; timeout + retry ile daha stabil çalıştır.
            # timeout=(connect, read)
            last_exc = None
            response = None
            for attempt in range(1, 4):
                try:
                    response = requests.get(
                        self.xml_url,
                        headers=headers,
                        auth=auth,
                        timeout=(15, 600),
                    )
                    response.raise_for_status()
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

            return xml_text

        except requests.exceptions.RequestException as e:
            raise UserError(_('XML çekilemedi: %s') % str(e))

    def _parse_xml(self, xml_content):
        """XML içeriğini parse et"""
        self.ensure_one()

        try:
            # XML namespace'leri temizle
            xml_content = re.sub(r'\sxmlns[^"]*"[^"]*"', '', xml_content)
            xml_content = re.sub(r'\sxmlns=[^"]*"[^"]*"', '', xml_content)

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

            root = ET.fromstring(xml_content)

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

        return data

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

    def _calculate_sale_price(self, cost_price):
        """Tedarikçi fiyatından satış fiyatı hesapla"""
        self.ensure_one()

        if not cost_price:
            return 0.0

        cost = float(cost_price)
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
                return product.product_tmpl_id, 'odoo_standard'

        # 1. SKU Prefix (ilk kelime) ile eşleştir
        if self.match_by_sku_prefix and sku_prefix:
            # Önce tam prefix eşleşmesi
            product = ProductT.search([
                ('default_code', '=like', sku_prefix + '%')
            ], limit=1)
            if product:
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
                if product:
                    return product, 'barcode_in_name'

                # 2c. Barkod SKU'da olabilir
                product = ProductT.search([('default_code', '=', barcode)], limit=1)
                if product:
                    return product, 'barcode_as_sku'

        # 3. SKU/Ürün kodu ile tam eşleştir
        if self.match_by_sku and sku:
            product = ProductT.search([('default_code', '=', sku)], limit=1)
            if product:
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
                        return prod, 'description_has_sku'

                    # 4b. Açıklama benzerliği kontrolü
                    ratio = SequenceMatcher(None, description[:200], prod_desc[:200]).ratio() * 100
                    if ratio >= self.description_match_ratio:
                        return prod, f'description_similar_{int(ratio)}%'

        # 5. İsim benzerliği ile eşleştir
        if self.match_by_name and data.get('name'):
            name = str(data['name']).strip()
            if name:
                # Önce tam eşleşme
                product = ProductT.search([('name', '=ilike', name)], limit=1)
                if product:
                    return product, 'name_exact'

                # 5a. Parantezden varyant modu - ana isim ile ara
                if self.variant_from_parentheses:
                    base_name, variant_name = self._extract_base_and_variant(name)
                    if base_name and variant_name:
                        # Ana isim ile tam eşleşme ara
                        product = ProductT.search([('name', '=ilike', base_name)], limit=1)
                        if product:
                            return product, 'base_name_exact'

                        # Ana isim ile benzerlik ara
                        all_products = ProductT.search([])
                        for prod in all_products:
                            ratio = SequenceMatcher(None, base_name.lower(), prod.name.lower()).ratio() * 100
                            if ratio >= 90:  # Ana isim için yüksek benzerlik
                                return prod, f'base_name_similar_{int(ratio)}%'

                # 5b. Normal benzerlik kontrolü
                all_products = ProductT.search([])
                for prod in all_products:
                    ratio = SequenceMatcher(None, name.lower(), prod.name.lower()).ratio() * 100
                    if ratio >= self.name_match_ratio:
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
            'type': self.default_product_type,
            'sale_ok': True,
            'purchase_ok': True,
            'xml_source_id': self.id,
            'xml_supplier_price': cost_price,
            'xml_supplier_sku': data.get('sku'),
            'xml_last_sync': fields.Datetime.now(),
            'is_dropship': True,
        }

        # Kategori (manuel eşleştirme + otomatik)
        category_result = self._apply_category_mapping(data.get('category'), data.get('extra1'))
        if category_result.get('categ_id'):
            vals['categ_id'] = category_result['categ_id']
        if category_result.get('public_categ_ids'):
            vals['public_categ_ids'] = category_result['public_categ_ids']

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

    def action_import_products(self):
        """Ürünleri içe aktar"""
        self.ensure_one()

        # Log oluştur
        log = self.env['xml.import.log'].create({
            'source_id': self.id,
            'start_time': fields.Datetime.now(),
            'state': 'running',
        })

        created = updated = skipped = failed = 0
        errors = []

        try:
            # XML çek ve parse et
            xml_content = self._fetch_xml()
            products = self._parse_xml(xml_content)

            log.total_products = len(products)

            _logger.info(f"XML Import: {len(products)} ürün bulundu - {self.name}")

            for element in products:
                try:
                    # Ürün bazında SQL hataları transaction'ı abort etmesin diye savepoint kullan.
                    # (Aksi halde bir ürün hatasından sonra self.write/log.write InFailedSqlTransaction'a düşer.)
                    with self.env.cr.savepoint():
                        # Ürün verilerini çıkar
                        data = self._extract_product_data(element)

                        if not data.get('name'):
                            skipped += 1
                            continue

                        # Fiyat kontrolü
                        price = float(data.get('price', 0) or 0)
                        cost = float(data.get('cost_price', 0) or data.get('price', 0) or 0)

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

                        # Parantezden varyant kontrolü
                        name = str(data.get('name', '')).strip()
                        base_name, variant_name = self._extract_base_and_variant(name)

                        if existing:
                            # Arşivlenmiş ürün eşleştiyse aktif hale getir (tekilleştirme için)
                            if hasattr(existing, 'active') and not existing.active:
                                existing.write({'active': True, 'sale_ok': True, 'purchase_ok': True})
                                # Şablon aktif olurken varyantları da aktif et (aksi halde barkod eşleşmesi zorlaşır)
                                variants = existing.with_context(active_test=False).product_variant_ids
                                if variants:
                                    variants.write({'active': True})

                            # Eğer varyant modu aktif ve bu ürün varyantlı ise
                            if self.variant_from_parentheses and self.create_variants and variant_name:
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

            # Sonuçları kaydet
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

        # ═══════════════════════════════════════════════════════════════
        # PARANTEZDEN VARYANT MODU
        # Örnek: "BOLD SPEAKER (KIRMIZI)" → Ana ürün: BOLD SPEAKER, Varyant: KIRMIZI
        # ═══════════════════════════════════════════════════════════════
        if self.variant_from_parentheses and self.create_variants:
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

        if self.create_variants and sku_prefix and data.get('barcode'):
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
            'type': self.default_product_type,
            'sale_ok': True,
            'purchase_ok': True,
            # Dropshipping alanları
            'xml_source_id': self.id,
            'xml_supplier_price': cost_price,
            'xml_supplier_sku': data.get('sku'),
            'xml_last_sync': fields.Datetime.now(),
            'is_dropship': True,
        }

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

        # Tedarikçi stok
        if data.get('stock'):
            try:
                vals['xml_supplier_stock'] = int(data.get('stock'))
            except:
                pass

        # Kategori eşleştirme (manuel + otomatik)
        category_result = self._apply_category_mapping(data.get('category'), data.get('extra1'))
        if category_result.get('categ_id'):
            vals['categ_id'] = category_result['categ_id']
        if category_result.get('public_categ_ids'):
            vals['public_categ_ids'] = category_result['public_categ_ids']

        if self.supplier_id:
            vals['xml_supplier_id'] = self.supplier_id.id

        # Desi/Ağırlık
        if data.get('weight'):
            try:
                vals['weight'] = float(data['weight'])
            except:
                pass

        if data.get('deci'):
            try:
                vals['volume'] = float(data['deci'])
                vals['deci'] = float(data['deci'])
            except:
                pass

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
        """Mevcut ürüne varyant ekle (farklı barkod)"""
        self.ensure_one()

        # Barkod attribute'u bul veya oluştur
        barcode_attr = self.env['product.attribute'].search([
            ('name', '=', 'Barkod'),
        ], limit=1)

        if not barcode_attr:
            barcode_attr = self.env['product.attribute'].create({
                'name': 'Barkod',
                'display_type': 'radio',
                'create_variant': 'always',
            })

        barcode_value = data.get('barcode')

        # Attribute value bul veya oluştur
        attr_value = self.env['product.attribute.value'].search([
            ('attribute_id', '=', barcode_attr.id),
            ('name', '=', barcode_value),
        ], limit=1)

        if not attr_value:
            attr_value = self.env['product.attribute.value'].create({
                'attribute_id': barcode_attr.id,
                'name': barcode_value,
            })

        # Ürüne attribute line ekle
        attr_line = self.env['product.template.attribute.line'].search([
            ('product_tmpl_id', '=', product_tmpl.id),
            ('attribute_id', '=', barcode_attr.id),
        ], limit=1)

        if attr_line:
            # Mevcut line'a value ekle
            attr_line.write({'value_ids': [(4, attr_value.id)]})
        else:
            # Yeni attribute line oluştur
            self.env['product.template.attribute.line'].create({
                'product_tmpl_id': product_tmpl.id,
                'attribute_id': barcode_attr.id,
                'value_ids': [(6, 0, [attr_value.id])],
            })

        # Yeni varyantı bul ve güncelle
        new_variant = self.env['product.product'].search([
            ('product_tmpl_id', '=', product_tmpl.id),
            ('barcode', '=', False),
        ], limit=1)

        if new_variant:
            new_variant.write({
                'barcode': barcode_value,
                'default_code': f"{data.get('sku')}-{barcode_value[-4:]}",
            })

        _logger.info(f"Varyant eklendi: {product_tmpl.name} - Barkod: {barcode_value}")

        return product_tmpl

    def _update_product(self, product, data, cost_price, xml_price):
        """Mevcut ürünü güncelle"""
        self.ensure_one()

        vals = {
            'xml_source_id': self.id,
            'xml_supplier_sku': data.get('sku'),
            'xml_last_sync': fields.Datetime.now(),
            'is_dropship': True,
        }

        # İsim güncelleme — XML ana veri kaynağı, her zaman güncelle
        if data.get('name'):
            vals['name'] = data['name']

        # İç referans (default_code) güncelleme
        if data.get('sku'):
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
                    if stock_qty >= self.min_stock and not product.sale_ok:
                        vals['sale_ok'] = True
                        _logger.info(f"Stok yeterli ({stock_qty}) - ürün satışa tekrar açıldı: {product.name}")
                except:
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

        if self.supplier_id:
            vals['xml_supplier_id'] = self.supplier_id.id

        product.write(vals)

        # Barkod güncelleme — product.product varyantı üzerinde
        if data.get('barcode'):
            barcode = str(data['barcode']).strip()
            if barcode:
                variants = product.product_variant_ids
                if len(variants) == 1:
                    # Tek varyanttaki barkodu güncelle (farklıysa)
                    if variants.barcode != barcode:
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

            if not existing:
                self.env['product.supplierinfo'].create({
                    'product_tmpl_id': product.id,
                    'partner_id': self.supplier_id.id,
                    'price': product.xml_supplier_price or product.standard_price,
                    'product_code': product.xml_supplier_sku or product.default_code,
                })
                count += 1

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
