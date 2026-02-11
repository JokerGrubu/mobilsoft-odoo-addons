# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import logging
import json
import re
from datetime import datetime, timedelta

# Senkronizasyon protokolleri
try:
    from .sync_protocols import SyncProtocols
    SYNC_PROTOCOLS = SyncProtocols()
except ImportError:
    SYNC_PROTOCOLS = None

_logger = logging.getLogger(__name__)

# BizimHesap API Base URL - Doğru URL
BIZIMHESAP_API_BASE = "https://bizimhesap.com/api/b2b"


class BizimHesapBackend(models.Model):
    """
    BizimHesap Bağlantı Ayarları
    """
    _name = 'bizimhesap.backend'
    _description = 'BizimHesap Backend'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Bağlantı Adı',
        required=True,
        tracking=True,
        default='BizimHesap',
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Ana Şirket (Faturalı)',
        required=True,
        default=lambda self: self.env.company,
        help='Faturalı işlemler bu şirkete kaydedilir (örn: Joker Grubu)',
    )

    # ═══════════════════════════════════════════════════════════════
    # ÇOK ŞİRKETLİ YAPI - JOKER GRUBU / JOKER TEDARİK
    # ═══════════════════════════════════════════════════════════════

    secondary_company_id = fields.Many2one(
        'res.company',
        string='İkincil Şirket (Faturasız)',
        help='Faturasız işlemler bu şirkete kaydedilir (örn: Joker Tedarik)',
    )

    enable_multi_company_routing = fields.Boolean(
        string='Çok Şirketli Yönlendirme',
        default=False,
        help='Aktifleştirildiğinde faturalı/faturasız işlemler farklı şirketlere yönlendirilir',
    )

    # Faturasız tespit kuralları
    noninvoice_detection_rule = fields.Selection([
        ('invoice_empty', 'Fatura No Boş'),
        ('no_kdv', 'KDV Yok'),
        ('both', 'Fatura No Boş VE KDV Yok'),
        ('any', 'Fatura No Boş VEYA KDV Yok'),
    ], string='Faturasız Tespit Kuralı', default='both',
       help='Hangi kriterlere göre işlem faturasız sayılacak')

    # Vergiden muaf müşteri yönlendirmesi
    route_tax_exempt_to_secondary = fields.Boolean(
        string='Vergiden Muaf → İkincil Şirket',
        default=True,
        help='Vergiden muaf müşterilerin işlemlerini ikincil şirkete yönlendir',
    )

    # VKN'siz müşteri yönlendirmesi
    route_no_vkn_to_secondary = fields.Boolean(
        string='VKN\'siz Müşteri → İkincil Şirket',
        default=True,
        help='VKN/TCKN bilgisi olmayan müşterilerin işlemlerini ikincil şirkete yönlendir',
    )

    # Hiç faturalı alım yapmamış müşteri yönlendirmesi
    route_never_invoiced_to_secondary = fields.Boolean(
        string='Hiç Faturası Olmayan → İkincil Şirket',
        default=True,
        help='Sistemde hiç faturası bulunmayan müşterilerin işlemlerini ikincil şirkete yönlendir',
    )

    # Ortak depo ayarı
    shared_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Ortak Depo',
        help='Her iki şirketin ortak kullandığı depo',
    )

    # ═══════════════════════════════════════════════════════════════
    # API AYARLARI
    # ═══════════════════════════════════════════════════════════════
    
    api_url = fields.Char(
        string='API URL',
        default=BIZIMHESAP_API_BASE,
        required=True,
    )
    
    # Authentication - BizimHesap B2B API sadece API Key kullanıyor
    api_key = fields.Char(
        string='API Key (Firm ID)',
        required=True,
        help='BizimHesap tarafından sağlanan Firm ID / API Key',
    )
    
    username = fields.Char(
        string='Kullanıcı Adı',
        help='BizimHesap giriş e-posta adresi (opsiyonel)',
    )
    
    password = fields.Char(
        string='Şifre',
        help='BizimHesap giriş şifresi (opsiyonel)',
    )
    
    # Token - B2B API token gerektirmiyor
    access_token = fields.Text(
        string='Access Token',
        readonly=True,
    )
    token_expiry = fields.Datetime(
        string='Token Geçerlilik',
        readonly=True,
    )

    # ═══════════════════════════════════════════════════════════════
    # TEDARİKÇİ FİYAT AYARLARI
    # ═══════════════════════════════════════════════════════════════

    supplier_currency_rate = fields.Float(
        string='Tedarikçi Kur (USD→TRY)',
        default=38.0,
        help='BizimHesap buyingPrice USD cinsinden - TRY\'ye çevirmek için kur',
    )
    sync_supplier_price = fields.Boolean(
        string='Tedarikçi Fiyatı Senkronize Et',
        default=True,
        help='BizimHesap buyingPrice → Odoo xml_supplier_price',
    )

    # ═══════════════════════════════════════════════════════════════
    # BAĞLANTI DURUMU
    # ═══════════════════════════════════════════════════════════════
    
    state = fields.Selection([
        ('draft', 'Taslak'),
        ('connected', 'Bağlı'),
        ('error', 'Hata'),
    ], string='Durum', default='draft', tracking=True)
    
    last_test_date = fields.Datetime(
        string='Son Test Tarihi',
        readonly=True,
    )
    
    # ═══════════════════════════════════════════════════════════════
    # SENKRONIZASYON AYARLARI
    # ═══════════════════════════════════════════════════════════════
    
    sync_partner = fields.Boolean(
        string='Cari Senkronizasyonu',
        default=True,
        help='Müşteri ve tedarikçi senkronizasyonu',
    )
    sync_product = fields.Boolean(
        string='Ürün Senkronizasyonu',
        default=True,
    )
    sync_invoice = fields.Boolean(
        string='Fatura Senkronizasyonu',
        default=True,
    )
    sync_payment = fields.Boolean(
        string='Ödeme Senkronizasyonu',
        default=True,
    )
    
    # Senkronizasyon yönü
    sync_direction = fields.Selection([
        ('import', 'Sadece İçe Aktar (BizimHesap → Odoo)'),
        ('export', 'Sadece Dışa Aktar (Odoo → BizimHesap)'),
        ('both', 'Çift Yönlü'),
    ], string='Senkronizasyon Yönü', default='both')
    
    # Zamanlama
    auto_sync = fields.Boolean(
        string='Otomatik Senkronizasyon',
        default=True,
    )
    sync_interval = fields.Integer(
        string='Senkronizasyon Aralığı (dakika)',
        default=30,
    )
    
    # Son senkronizasyon tarihleri
    last_sync_date = fields.Datetime(
        string='Son Senkronizasyon',
        readonly=True,
    )
    last_partner_sync = fields.Datetime(
        string='Son Cari Sync',
        readonly=True,
    )
    last_product_sync = fields.Datetime(
        string='Son Ürün Sync',
        readonly=True,
    )
    last_invoice_sync = fields.Datetime(
        string='Son Fatura Sync',
        readonly=True,
    )
    
    # ═══════════════════════════════════════════════════════════════
    # VARSAYILAN DEĞERLER
    # ═══════════════════════════════════════════════════════════════
    
    default_customer_account_id = fields.Many2one(
        'account.account',
        string='Varsayılan Müşteri Hesabı',
        domain="[('account_type', '=', 'asset_receivable')]",
    )
    default_supplier_account_id = fields.Many2one(
        'account.account',
        string='Varsayılan Tedarikçi Hesabı',
        domain="[('account_type', '=', 'liability_payable')]",
    )
    default_income_account_id = fields.Many2one(
        'account.account',
        string='Varsayılan Gelir Hesabı',
        domain="[('account_type', '=', 'income')]",
    )
    default_expense_account_id = fields.Many2one(
        'account.account',
        string='Varsayılan Gider Hesabı',
        domain="[('account_type', '=', 'expense')]",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # LOG İLİŞKİSİ
    # ═══════════════════════════════════════════════════════════════
    
    sync_log_ids = fields.One2many(
        'bizimhesap.sync.log',
        'backend_id',
        string='Senkronizasyon Logları',
    )
    
    sync_log_count = fields.Integer(
        compute='_compute_sync_log_count',
        string='Log Sayısı',
    )
    
    # Binding sayıları
    partner_binding_count = fields.Integer(
        compute='_compute_binding_counts',
        string='Eşleşen Cari',
    )
    product_binding_count = fields.Integer(
        compute='_compute_binding_counts',
        string='Eşleşen Ürün',
    )
    invoice_binding_count = fields.Integer(
        compute='_compute_binding_counts',
        string='Eşleşen Fatura',
    )
    
    # ═══════════════════════════════════════════════════════════════
    # COMPUTE METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def _compute_sync_log_count(self):
        for record in self:
            record.sync_log_count = self.env['bizimhesap.sync.log'].search_count([
                ('backend_id', '=', record.id)
            ])
    
    def _compute_binding_counts(self):
        for record in self:
            record.partner_binding_count = self.env['bizimhesap.partner.binding'].search_count([
                ('backend_id', '=', record.id)
            ])
            record.product_binding_count = self.env['bizimhesap.product.binding'].search_count([
                ('backend_id', '=', record.id)
            ])
            record.invoice_binding_count = self.env['bizimhesap.invoice.binding'].search_count([
                ('backend_id', '=', record.id)
            ])
    
    # ═══════════════════════════════════════════════════════════════
    # API METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def _get_headers(self):
        """
        BizimHesap B2B API headers oluştur
        
        BizimHesap B2B API, hem 'Key' hem 'Token' header'ı olarak 
        aynı API Key değerini kullanıyor.
        """
        self.ensure_one()
        
        return {
            'Key': self.api_key,
            'Token': self.api_key,  # BizimHesap B2B API: Key ve Token aynı değer
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
    
    def _api_request(self, method, endpoint, data=None, params=None):
        """
        BizimHesap API isteği yap
        
        :param method: HTTP method (GET, POST, PUT, DELETE)
        :param endpoint: API endpoint (/api/contacts vs.)
        :param data: Request body (dict)
        :param params: Query parameters (dict)
        :return: Response data (dict)
        """
        self.ensure_one()
        
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            _logger.info(f"BizimHesap API Request: {method} {url}")
            
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=60,
            )
            
            # Log the request
            self._create_log(
                operation=f"{method} {endpoint}",
                status='success' if response.ok else 'error',
                request_data=json.dumps(data) if data else None,
                response_data=response.text[:5000] if response.text else None,
                status_code=response.status_code,
            )
            
            response.raise_for_status()
            
            if response.content:
                return response.json()
            return {}
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"BizimHesap API error: {e}")
            self._create_log(
                operation=f"{method} {endpoint}",
                status='error',
                error_message=str(e),
            )
            raise UserError(_(f"API Hatası: {e}"))
    
    def _create_log(self, operation, status, **kwargs):
        """Sync log oluştur"""
        self.env['bizimhesap.sync.log'].sudo().create({
            'backend_id': self.id,
            'operation': operation,
            'status': status,
            **kwargs,
        })
    
    # ═══════════════════════════════════════════════════════════════
    # B2B API ENDPOINT METHODS
    # ═══════════════════════════════════════════════════════════════
    
    # Warehouses (Depolar)
    def get_warehouses(self):
        """Tüm depoları getir - B2B API"""
        return self._api_request('GET', '/warehouses')
    
    # Products (Ürünler)
    def get_products(self):
        """Tüm ürünleri getir - B2B API"""
        return self._api_request('GET', '/products')
    
    # Categories (Kategoriler)
    def get_categories(self):
        """Tüm kategorileri getir - B2B API"""
        return self._api_request('GET', '/categories')
    
    # Customers (Müşteriler)
    def get_customers(self):
        """Tüm müşterileri getir - B2B API"""
        return self._api_request('GET', '/customers')
    
    # Suppliers (Tedarikçiler)
    def get_suppliers(self):
        """Tüm tedarikçileri getir - B2B API"""
        return self._api_request('GET', '/suppliers')
    
    # Inventory (Stok)
    def get_inventory(self, warehouse_id):
        """Belirli depodaki stok miktarlarını getir - B2B API"""
        return self._api_request('GET', f'/inventory/{warehouse_id}')
    
    # Invoices (Faturalar)
    def get_invoices(self, start_date=None, end_date=None):
        """
        Fatura listesini getir - B2B API.
        BizimHesap B2B API'de fatura listesi endpoint'i yoksa boş döner (çökme olmaz).
        """
        try:
            params = {}
            if start_date:
                params['startDate'] = start_date.strftime('%Y-%m-%d')
            if end_date:
                params['endDate'] = end_date.strftime('%Y-%m-%d') if end_date else fields.Date.today().strftime('%Y-%m-%d')
            result = self._api_request('GET', '/invoices', params=params if params else None)
            if isinstance(result, dict) and 'data' in result:
                return result
            if isinstance(result, list):
                return {'data': result}
            return {'data': []}
        except (UserError, Exception) as e:
            _logger.warning("BizimHesap fatura listesi alınamadı (API desteklemiyor olabilir): %s", e)
            return {'data': []}

    def create_invoice(self, data):
        """
        Yeni fatura oluştur - B2B API
        
        InvoiceType:
        - 3: Satış Faturası
        - 5: Alış Faturası
        """
        return self._api_request('POST', '/addinvoice', data=data)
    
    # ═══════════════════════════════════════════════════════════════
    # LEGACY API ENDPOINT METHODS (Uyumluluk için)
    # ═══════════════════════════════════════════════════════════════
    
    def get_contacts(self, page=1, page_size=100):
        """Tüm carileri getir - Müşteri ve tedarikçileri birleştir"""
        # Müşteri ve tedarikçileri birleştirerek döndür
        result = {'data': []}
        try:
            customers_response = self.get_customers()
            if customers_response.get('resultCode') == 1:
                customers = customers_response.get('data', {}).get('customers', [])
                for c in customers:
                    c['contactType'] = 1  # Müşteri
                result['data'].extend(customers)
            
            suppliers_response = self.get_suppliers()
            if suppliers_response.get('resultCode') == 1:
                suppliers = suppliers_response.get('data', {}).get('suppliers', [])
                for s in suppliers:
                    s['contactType'] = 2  # Tedarikçi
                result['data'].extend(suppliers)
        except Exception as e:
            _logger.error(f"get_contacts error: {e}")
        return result
    
    def get_contact(self, contact_id):
        """Tek cari getir - B2B API'de desteklenmiyor"""
        _logger.warning("get_contact is not supported in B2B API")
        return {}
    
    def create_contact(self, data):
        """Yeni cari oluştur - Bu B2B API'de desteklenmiyor"""
        _logger.warning("create_contact is not supported in B2B API")
        return {}
    
    def update_contact(self, contact_id, data):
        """Cari güncelle - Bu B2B API'de desteklenmiyor"""
        _logger.warning("update_contact is not supported in B2B API")
        return {}
    
    # Products - Legacy methods
    def get_product(self, product_id):
        """Tek ürün getir - B2B API'de yok"""
        _logger.warning("get_product is not supported in B2B API, use get_products instead")
        return {}
    
    def create_product(self, data):
        """Yeni ürün oluştur - Bu B2B API'de desteklenmiyor"""
        _logger.warning("create_product is not supported in B2B API")
        return {}
    
    def update_product(self, product_id, data):
        """Ürün güncelle - Bu B2B API'de desteklenmiyor"""
        _logger.warning("update_product is not supported in B2B API")
        return {}
    
    # ═══════════════════════════════════════════════════════════════
    # ACTION METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def action_test_connection(self):
        """
        Bağlantıyı test et - B2B API warehouses endpoint ile
        
        BizimHesap B2B API: Key ve Token header'ları aynı API Key değerini kullanır
        """
        self.ensure_one()
        try:
            # B2B API'ye basit bir istek at - warehouses listesi al
            url = f"{self.api_url}/warehouses"
            headers = self._get_headers()
            
            _logger.info(f"Testing BizimHesap connection: {url}")
            _logger.info(f"Using headers: Key and Token with API Key")
            
            response = requests.get(url, headers=headers, timeout=30)
            
            _logger.info(f"BizimHesap test response: {response.status_code}")
            _logger.debug(f"Response: {response.text[:500] if response.text else 'No response'}")
            
            if response.ok:
                result = response.json()
                
                # Başarılı mı kontrol et (resultCode == 1)
                if result.get('resultCode') == 1:
                    warehouses = result.get('data', {}).get('warehouses', [])
                    warehouse_count = len(warehouses)
                    
                    self.write({
                        'state': 'connected',
                        'last_test_date': fields.Datetime.now(),
                    })
                    
                    # Log başarılı bağlantı
                    self._create_log(
                        operation='Test Connection',
                        status='success',
                        message=f'Bağlantı başarılı. {warehouse_count} depo bulundu.',
                        response_data=response.text[:1000] if response.text else None,
                        status_code=response.status_code,
                    )
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Başarılı'),
                            'message': _(f'BizimHesap bağlantısı başarılı! {warehouse_count} depo bulundu.'),
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    error_text = result.get('errorText', 'Bilinmeyen hata')
                    self.write({'state': 'error'})
                    self._create_log(
                        operation='Test Connection',
                        status='error',
                        message=f'API Hatası: {error_text}',
                        response_data=response.text[:1000] if response.text else None,
                        status_code=response.status_code,
                    )
                    raise UserError(_(f"API Hatası: {error_text}"))
            else:
                self.write({'state': 'error'})
                self._create_log(
                    operation='Test Connection',
                    status='error',
                    message=f'Bağlantı hatası. Status: {response.status_code}',
                    response_data=response.text[:1000] if response.text else None,
                    status_code=response.status_code,
                )
                raise UserError(_(f"Bağlantı hatası: HTTP {response.status_code}"))
                
        except requests.exceptions.RequestException as e:
            self.write({'state': 'error'})
            self._create_log(
                operation='Test Connection',
                status='error',
                error_message=str(e),
            )
            raise UserError(_(f"Bağlantı hatası: {e}"))
    
    def action_sync_all(self):
        """Tüm verileri senkronize et"""
        self.ensure_one()
        
        total_created = total_updated = total_failed = 0
        
        # 1. Önce kategorileri senkronize et
        try:
            result = self.action_sync_categories()
            _logger.info(f"Categories sync completed")
        except Exception as e:
            _logger.error(f"Category sync error: {e}")
        
        # 2. Carileri senkronize et (Müşteri + Tedarikçi)
        if self.sync_partner:
            try:
                self.action_sync_partners()
            except Exception as e:
                _logger.error(f"Partner sync error: {e}")
        
        # 3. Ürünleri senkronize et
        if self.sync_product:
            try:
                self.action_sync_products()
            except Exception as e:
                _logger.error(f"Product sync error: {e}")
        
        self.last_sync_date = fields.Datetime.now()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Senkronizasyon Tamamlandı'),
                'message': _('Tüm veriler (kategoriler, cariler, ürünler) senkronize edildi.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_sync_categories(self):
        """Kategorileri senkronize et - B2B API"""
        self.ensure_one()
        _logger.info(f"Starting category sync for {self.name}")
        
        created = updated = 0
        
        try:
            response = self.get_categories()
            if response.get('resultCode') == 1:
                categories = response.get('data', {}).get('categories', [])
                _logger.info(f"Found {len(categories)} categories from BizimHesap")
                
                for cat_data in categories:
                    cat_name = cat_data.get('title') or cat_data.get('name', 'Bilinmiyor')
                    
                    # Mevcut kategori ara
                    existing = self.env['product.category'].search([
                        ('name', '=', cat_name)
                    ], limit=1)
                    
                    if not existing:
                        self.env['product.category'].create({
                            'name': cat_name,
                        })
                        created += 1
                    else:
                        updated += 1
                        
        except Exception as e:
            _logger.error(f"Category sync error: {e}")
        
        self._create_log(
            operation='Sync Categories',
            status='success',
            records_created=created,
            records_updated=updated,
            message=f"Oluşturulan: {created}, Mevcut: {updated}",
        )
        
        return {'created': created, 'updated': updated}
    
    def action_sync_warehouses(self):
        """Depoları senkronize et - B2B API"""
        self.ensure_one()
        _logger.info(f"Starting warehouse sync for {self.name}")
        
        created = updated = 0
        
        try:
            response = self.get_warehouses()
            if response.get('resultCode') == 1:
                warehouses = response.get('data', {}).get('warehouses', [])
                _logger.info(f"Found {len(warehouses)} warehouses from BizimHesap")
                
                for wh_data in warehouses:
                    wh_name = wh_data.get('title', 'Bilinmiyor')
                    external_id = wh_data.get('id')
                    
                    # Mevcut depo ara
                    existing = self.env['stock.warehouse'].search([
                        ('name', '=', wh_name)
                    ], limit=1)
                    
                    if not existing:
                        # Kısa kod oluştur (ilk 5 karakter)
                        code = wh_name[:5].upper().replace(' ', '')
                        self.env['stock.warehouse'].create({
                            'name': wh_name,
                            'code': code,
                            'company_id': self.company_id.id,
                        })
                        created += 1
                    else:
                        updated += 1
                        
        except Exception as e:
            _logger.error(f"Warehouse sync error: {e}")
        
        self._create_log(
            operation='Sync Warehouses',
            status='success',
            records_created=created,
            records_updated=updated,
            message=f"Oluşturulan: {created}, Mevcut: {updated}",
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Depo Senkronizasyonu'),
                'message': _(f'Oluşturulan: {created}, Mevcut: {updated}'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_sync_partners(self):
        """
        Müşteri ve Tedarikçileri senkronize et - B2B API
        
        /customers ve /suppliers endpoint'lerinden veri çeker
        """
        self.ensure_one()
        _logger.info(f"Starting partner sync for {self.name}")
        
        created = updated = failed = 0
        
        # Müşterileri senkronize et
        try:
            response = self.get_customers()
            if response.get('resultCode') == 1:
                customers = response.get('data', {}).get('customers', [])
                _logger.info(f"Found {len(customers)} customers from BizimHesap")
                
                for customer_data in customers:
                    customer_data['contactType'] = 1  # Müşteri
                    try:
                        result = self._import_partner(customer_data)
                        if result == 'created':
                            created += 1
                        elif result == 'updated':
                            updated += 1
                    except Exception as e:
                        failed += 1
                        _logger.error(f"Customer import error: {e}")
        except Exception as e:
            _logger.error(f"Customer sync error: {e}")
        
        # Tedarikçileri senkronize et
        try:
            response = self.get_suppliers()
            if response.get('resultCode') == 1:
                suppliers = response.get('data', {}).get('suppliers', [])
                _logger.info(f"Found {len(suppliers)} suppliers from BizimHesap")
                
                for supplier_data in suppliers:
                    supplier_data['contactType'] = 2  # Tedarikçi
                    try:
                        result = self._import_partner(supplier_data)
                        if result == 'created':
                            created += 1
                        elif result == 'updated':
                            updated += 1
                    except Exception as e:
                        failed += 1
                        _logger.error(f"Supplier import error: {e}")
        except Exception as e:
            _logger.error(f"Supplier sync error: {e}")
        
        self.last_partner_sync = fields.Datetime.now()
        
        self._create_log(
            operation='Sync Partners',
            status='success' if failed == 0 else 'warning',
            records_created=created,
            records_updated=updated,
            records_failed=failed,
            message=f"Oluşturulan: {created}, Güncellenen: {updated}, Hatalı: {failed}",
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cari Senkronizasyonu'),
                'message': _(f'Oluşturulan: {created}, Güncellenen: {updated}, Hatalı: {failed}'),
                'type': 'success' if failed == 0 else 'warning',
                'sticky': False,
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # ŞİRKET YÖNLENDİRME (COMPANY ROUTING)
    # Joker Grubu (Faturalı) / Joker Tedarik (Faturasız)
    # ═══════════════════════════════════════════════════════════════

    def _get_target_company(self, partner_data=None, transaction_data=None):
        """
        İşlem için hedef şirketi belirle

        Kurallar:
        1. Multi-company routing aktif değilse → Ana şirket
        2. VKN'siz müşteri → İkincil şirket (Joker Tedarik)
        3. Vergiden muaf müşteri → İkincil şirket
        4. Faturasız işlem → İkincil şirket
        5. Diğer durumlarda → Ana şirket (Joker Grubu)

        Returns:
            res.company: Hedef şirket
        """
        self.ensure_one()

        # Multi-company routing aktif değilse ana şirket
        if not self.enable_multi_company_routing or not self.secondary_company_id:
            return self.company_id

        # Partner bazlı kontroller
        if partner_data:
            # VKN'siz müşteri kontrolü
            if self.route_no_vkn_to_secondary:
                vkn = partner_data.get('taxno') or partner_data.get('taxNumber') or partner_data.get('vat')
                if not vkn or str(vkn).strip() == '':
                    _logger.info(f"VKN'siz müşteri → İkincil şirket: {partner_data.get('title', 'N/A')}")
                    return self.secondary_company_id

            # Vergiden muaf kontrolü (partner üzerinde flag varsa)
            if self.route_tax_exempt_to_secondary:
                is_tax_exempt = partner_data.get('is_tax_exempt') or partner_data.get('vergiden_muaf')
                if is_tax_exempt:
                    _logger.info(f"Vergiden muaf müşteri → İkincil şirket: {partner_data.get('title', 'N/A')}")
                    return self.secondary_company_id

        # İşlem bazlı kontroller
        if transaction_data:
            if self._is_noninvoice_transaction(transaction_data):
                _logger.info(f"Faturasız işlem → İkincil şirket")
                return self.secondary_company_id

        # Varsayılan: Ana şirket (Joker Grubu)
        return self.company_id

    def _is_noninvoice_transaction(self, transaction_data):
        """
        İşlemin faturasız olup olmadığını tespit et

        Kurallar (noninvoice_detection_rule'a göre):
        - invoice_empty: Fatura numarası boş
        - no_kdv: KDV tutarı 0 veya yok
        - both: Fatura No boş VE KDV yok
        - any: Fatura No boş VEYA KDV yok

        Returns:
            bool: True = Faturasız işlem
        """
        if not transaction_data:
            return False

        # Fatura numarası kontrolü
        invoice_no = transaction_data.get('invoice_no') or transaction_data.get('invoiceNo') or ''
        invoice_empty = str(invoice_no).strip() == ''

        # KDV kontrolü (BizimHesap formatları)
        kdv_amount = 0.0
        kdv_fields = ['kdv', 'tax', 'taxAmount', 'kdvAmount', 'vatAmount']
        for field in kdv_fields:
            val = transaction_data.get(field)
            if val:
                try:
                    # Türkçe format: 1.234,56 → 1234.56
                    if isinstance(val, str):
                        kdv_amount = float(val.replace('.', '').replace(',', '.'))
                    else:
                        kdv_amount = float(val)
                    break
                except (ValueError, TypeError):
                    continue

        no_kdv = kdv_amount == 0.0

        # Kurala göre karar ver
        rule = self.noninvoice_detection_rule or 'both'

        if rule == 'invoice_empty':
            return invoice_empty
        elif rule == 'no_kdv':
            return no_kdv
        elif rule == 'both':
            return invoice_empty and no_kdv
        elif rule == 'any':
            return invoice_empty or no_kdv

        return False

    def _check_partner_never_invoiced(self, partner):
        """
        Partner'ın hiç faturası olup olmadığını kontrol et

        Returns:
            bool: True = Hiç fatura yok
        """
        if not partner:
            return True

        invoice_count = self.env['account.move'].search_count([
            ('partner_id', '=', partner.id),
            ('move_type', 'in', ['out_invoice', 'in_invoice']),
            ('state', '=', 'posted'),
        ])

        return invoice_count == 0

    def _check_partner_tax_exempt(self, partner):
        """
        Partner'ın vergiden muaf olup olmadığını kontrol et

        Returns:
            bool: True = Vergiden muaf
        """
        if not partner:
            return False

        # Odoo standart alanları
        # fiscal_position_id ile kontrol
        if partner.property_account_position_id:
            # "Muaf" veya "Exempt" içeren fiscal position
            fp_name = (partner.property_account_position_id.name or '').lower()
            if 'muaf' in fp_name or 'exempt' in fp_name:
                return True

        # Custom alan kontrolü (varsa)
        if hasattr(partner, 'is_tax_exempt') and partner.is_tax_exempt:
            return True

        return False

    def _get_partner_target_company(self, partner):
        """
        Mevcut bir partner için hedef şirketi belirle

        Returns:
            res.company: Hedef şirket
        """
        self.ensure_one()

        if not self.enable_multi_company_routing or not self.secondary_company_id:
            return self.company_id

        # "Her Zaman Faturasız" işaretli ise ikincil şirkete git
        if hasattr(partner, 'never_invoice_customer') and partner.never_invoice_customer:
            return self.secondary_company_id

        # VKN'siz kontrol
        if self.route_no_vkn_to_secondary:
            if not partner.vat or str(partner.vat).strip() == '':
                return self.secondary_company_id

        # Vergiden muaf kontrol
        if self.route_tax_exempt_to_secondary:
            if self._check_partner_tax_exempt(partner):
                return self.secondary_company_id

        # Hiç faturası yok kontrol
        if self.route_never_invoiced_to_secondary:
            if self._check_partner_never_invoiced(partner):
                return self.secondary_company_id

        return self.company_id

    # ═══════════════════════════════════════════════════════════════
    # CARİ IMPORT
    # ═══════════════════════════════════════════════════════════════

    def _import_partner(self, data):
        """
        Tek cari import et - Protokollerle eşleştirme

        Eşleştirme sırası:
        1. VKN/TCKN (vergi numarası) → Kesin eşleşme
        2. Telefon → Kesin eşleşme
        3. E-posta → Kesin eşleşme
        4. İsim benzerliği ≥%80 + farklı adres → Şube olarak ekle
        5. İsim benzerliği ≥%50 → Güncelle
        6. Hiçbiri → Yeni oluştur
        """
        external_id = str(data.get('id'))
        
        # Mevcut binding kontrol
        binding = self.env['bizimhesap.partner.binding'].search([
            ('backend_id', '=', self.id),
            ('external_id', '=', external_id),
        ], limit=1)
        
        # Odoo değerlerine dönüştür
        partner_vals = self._map_partner_to_odoo(data)
        
        if binding:
            # Mevcut kayıt - güncelle
            # Şirket partnerlerini güncelleme (res.company koruması)
            company_partners = self.env['res.company'].search([]).mapped('partner_id')
            if binding.odoo_id.id in company_partners.ids:
                # ŞİRKET PARTNERİ - Binding'i sil ve atla
                _logger.warning(f"Şirket partneri için binding siliniyor: {binding.odoo_id.name}")
                binding.unlink()
                return 'skipped'

            if self._vat_match_or_empty(binding.odoo_id, partner_vals.get('vat')):
                update_vals = self._get_missing_partner_vals(binding.odoo_id, partner_vals)
                if update_vals:
                    # Context ile sync kaynağını belirt
                    binding.odoo_id.with_context(sync_source='bizimhesap').write(update_vals)
                self._ensure_authorized_contact(binding.odoo_id, data)
            else:
                _logger.warning(
                    f"VKN uyuşmadı, partner güncellenmedi: {binding.odoo_id.name}"
                )
            binding.write({
                'sync_date': fields.Datetime.now(),
                'external_data': json.dumps(data),
            })
            return 'updated'
        
        # Protokollerle eşleştirme
        source_partner = {
            'name': data.get('title', ''),
            'vat': data.get('taxno') or data.get('taxNumber'),
            'phone': data.get('phone'),
            'email': data.get('email'),
            'street': data.get('address'),
            'city': '',  # BizimHesap'da ayrı alan yok
        }
        
        # Tüm mevcut partnerları al (Odoo 19'da mobile alanı yok)
        all_partners = self.env['res.partner'].search_read(
            [('active', '=', True)],
            ['id', 'name', 'vat', 'phone', 'email', 'street', 'city', 'parent_id']
        )
        
        # Protokol ile eşleştir
        match = {'match_type': 'new'}
        if SYNC_PROTOCOLS:
            match = SYNC_PROTOCOLS.match_partner(source_partner, all_partners)
        
        if match['match_type'] == 'exact':
            # Kesin eşleşme - VKN/Telefon/E-posta ile bulundu
            partner_id = match['matched_partner']['id']
            partner = self.env['res.partner'].browse(partner_id)

            # Şirket partnerlerini güncelleme (res.company koruması)
            company_partners = self.env['res.company'].search([]).mapped('partner_id')
            if partner.id in company_partners.ids:
                # ŞİRKET PARTNERİ - Binding oluşturma, atla
                _logger.warning(f"Şirket partneri için binding OLUŞTURULMUYOR: {partner.name}")
                return 'skipped'

            if self._vat_match_or_empty(partner, partner_vals.get('vat')):
                update_vals = self._get_missing_partner_vals(partner, partner_vals)
                if update_vals:
                    partner.with_context(sync_source='bizimhesap').write(update_vals)
                self._ensure_authorized_contact(partner, data)
            else:
                _logger.warning(
                    f"VKN uyuşmadı, partner güncellenmedi: {partner.name}"
                )

            # Binding oluştur
            self.env['bizimhesap.partner.binding'].create({
                'backend_id': self.id,
                'external_id': external_id,
                'odoo_id': partner.id,
                'sync_date': fields.Datetime.now(),
                'external_data': json.dumps(data),
            })
            _logger.info(f"Partner eşleşti ({match['reason']}): {data.get('title')}")
            return 'updated'
        
        elif match['match_type'] == 'branch':
            # Şube tespit edildi - aynı isim, farklı adres
            parent_id = match['parent_id']
            branch_name = match['branch_name']
            
            partner_vals['name'] = branch_name
            partner_vals['parent_id'] = parent_id
            
            partner = self.env['res.partner'].create(partner_vals)
            
            self.env['bizimhesap.partner.binding'].create({
                'backend_id': self.id,
                'external_id': external_id,
                'odoo_id': partner.id,
                'sync_date': fields.Datetime.now(),
                'external_data': json.dumps(data),
            })
            _logger.info(f"Şube oluşturuldu: {branch_name} (Parent: {parent_id})")
            return 'created'
        
        elif match['match_type'] == 'similar':
            # Benzer isim - güncelle
            partner_id = match['matched_partner']['id']
            partner = self.env['res.partner'].browse(partner_id)

            # Şirket partnerlerini güncelleme (res.company koruması)
            company_partners = self.env['res.company'].search([]).mapped('partner_id')
            if partner.id in company_partners.ids:
                # ŞİRKET PARTNERİ - Binding oluşturma, atla
                _logger.warning(f"Şirket partneri için binding OLUŞTURULMUYOR: {partner.name}")
                return 'skipped'

            if self._vat_match_or_empty(partner, partner_vals.get('vat')):
                update_vals = self._get_missing_partner_vals(partner, partner_vals)
                if update_vals:
                    partner.with_context(sync_source='bizimhesap').write(update_vals)
                self._ensure_authorized_contact(partner, data)
            else:
                _logger.warning(
                    f"VKN uyuşmadı, partner güncellenmedi: {partner.name}"
                )

            self.env['bizimhesap.partner.binding'].create({
                'backend_id': self.id,
                'external_id': external_id,
                'odoo_id': partner.id,
                'sync_date': fields.Datetime.now(),
                'external_data': json.dumps(data),
            })
            _logger.info(f"Benzer partner güncellendi ({match['reason']}): {data.get('title')}")
            return 'updated'
        
        else:
            # Yeni cari oluştur
            partner = self.env['res.partner'].create(partner_vals)
            self._ensure_authorized_contact(partner, data)
            
            self.env['bizimhesap.partner.binding'].create({
                'backend_id': self.id,
                'external_id': external_id,
                'odoo_id': partner.id,
                'sync_date': fields.Datetime.now(),
                'external_data': json.dumps(data),
            })
            _logger.info(f"Yeni cari oluşturuldu: {data.get('title')}")
            return 'created'
    
    def _map_partner_to_odoo(self, data):
        """
        BizimHesap cari → Odoo partner dönüşümü
        
        BizimHesap B2B API Field Mapping:
        - id: External ID
        - code: Cari kodu
        - title: Cari adı
        - address: Adres
        - phone: Telefon
        - taxno: Vergi numarası
        - taxoffice: Vergi dairesi
        - authorized: Yetkili kişi
        - balance: Bakiye
        - chequeandbond: Çek/Senet bakiyesi
        - currency: Para birimi
        - email: E-posta
        """
        contact_type = data.get('contactType', 1)
        
        vals = {
            'name': data.get('title', 'Bilinmiyor'),
            'vat': data.get('taxno') or data.get('taxNumber'),  # taxno (B2B) veya taxNumber
            'phone': data.get('phone'),
            'email': data.get('email'),
            'street': data.get('address'),
            'comment': data.get('authorized'),  # Yetkili kişiyi nota ekle
            'ref': data.get('code') if data.get('code') else None,
        }
        
        # Bakiye bilgileri
        balance_str = data.get('balance', '0,00')
        chequeandbond_str = data.get('chequeandbond', '0,00')
        
        # Türkçe formatı Python float'a çevir (1.234,56 → 1234.56)
        try:
            balance = float(balance_str.replace('.', '').replace(',', '.'))
            vals['bizimhesap_balance'] = balance
        except (ValueError, AttributeError):
            vals['bizimhesap_balance'] = 0.0
        
        try:
            chequeandbond = float(chequeandbond_str.replace('.', '').replace(',', '.'))
            vals['bizimhesap_cheque_bond'] = chequeandbond
        except (ValueError, AttributeError):
            vals['bizimhesap_cheque_bond'] = 0.0
        
        # Para birimi ve son güncelleme
        vals['bizimhesap_currency'] = data.get('currency', 'TL')
        vals['bizimhesap_last_balance_update'] = fields.Datetime.now()
        
        # None değerleri temizle
        vals = {k: v for k, v in vals.items() if v is not None}
        
        # Cari tipi: 1=Müşteri, 2=Tedarikçi
        if contact_type == 1:
            vals['customer_rank'] = 1
        elif contact_type == 2:
            vals['supplier_rank'] = 1
        
        # Vergi dairesi
        tax_office = data.get('taxoffice') or data.get('taxOffice')
        if tax_office:
            # l10n_tr modülü yüklüyse
            if 'l10n_tr_tax_office_name' in self.env['res.partner']._fields:
                vals['l10n_tr_tax_office_name'] = tax_office

        # Şirket yönlendirmesi
        target_company = self._get_target_company(partner_data=data)
        vals['company_id'] = target_company.id

        return vals

    # ═══════════════════════════════════════════════════════════════
    # EKSİK ALAN GÜNCELLEME / YETKİLİ KİŞİ
    # ═══════════════════════════════════════════════════════════════

    def _normalize_vat(self, vat_value):
        if not vat_value:
            return ''
        return re.sub(r'\s+', '', str(vat_value)).upper()

    def _vat_match_or_empty(self, partner, incoming_vat):
        """VKN eşleşmesi kontrolü: Partner VKN boşsa izin ver, doluysa eşleşmeli."""
        partner_vat = self._normalize_vat(partner.vat)
        incoming_vat_norm = self._normalize_vat(incoming_vat)
        if not partner_vat:
            return True
        if not incoming_vat_norm:
            return False
        return partner_vat == incoming_vat_norm

    def _get_missing_partner_vals(self, partner, incoming_vals):
        """Sadece eksik alanları güncellemek için vals filtrele."""
        if not incoming_vals:
            return {}
        skip_fields = {'company_id'}
        missing_vals = {}
        for field, value in incoming_vals.items():
            if field in skip_fields:
                continue
            if value in (None, False, '', [], {}):
                continue
            if field not in partner._fields:
                continue
            current_value = partner[field]
            if not current_value:
                missing_vals[field] = value
        return missing_vals

    def _ensure_authorized_contact(self, partner, data):
        """Yetkili kişi yoksa alt kontak oluştur ve parent'a bağla."""
        authorized_name = (data.get('authorized') or '').strip()
        if not authorized_name:
            return
        existing = self.env['res.partner'].search([
            ('parent_id', '=', partner.id),
            ('name', 'ilike', authorized_name)
        ], limit=1)
        if existing:
            return
        self.env['res.partner'].create({
            'name': authorized_name,
            'parent_id': partner.id,
            'type': 'contact',
        })

    # ═══════════════════════════════════════════════════════════════
    # FATURASIZ İŞLEM YÖNETİMİ - SALE ORDER
    # (Joker Tedarik için)
    # ═══════════════════════════════════════════════════════════════

    def _create_sale_order_from_transaction(self, transaction_data, partner_id):
        """
        Faturasız işlem için satış siparişi oluştur

        Faturasız işlemler Joker Tedarik'e (ikincil şirket) sale.order olarak kaydedilir.
        Faturalı işlemler Joker Grubu'na (ana şirket) account.move olarak kaydedilir.

        Args:
            transaction_data: BizimHesap işlem verisi
            partner_id: Odoo partner ID

        Returns:
            sale.order: Oluşturulan sipariş
        """
        self.ensure_one()

        # Hedef şirket: İkincil şirket (Joker Tedarik)
        target_company = self.secondary_company_id or self.company_id

        # İşlem tarihi
        date_str = transaction_data.get('date') or transaction_data.get('transactionDate')
        order_date = fields.Datetime.now()
        if date_str:
            try:
                if 'T' in date_str:
                    order_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    order_date = datetime.strptime(date_str, '%Y-%m-%d')
            except (ValueError, TypeError):
                pass

        # Sipariş değerleri
        order_vals = {
            'partner_id': partner_id,
            'company_id': target_company.id,
            'date_order': order_date,
            'state': 'sale',  # Onaylı olarak oluştur
            'client_order_ref': transaction_data.get('reference') or transaction_data.get('ref'),
            'note': f"BizimHesap faturasız işlem. ID: {transaction_data.get('id')}",
        }

        # Ortak depo varsa kullan
        if self.shared_warehouse_id:
            order_vals['warehouse_id'] = self.shared_warehouse_id.id
        else:
            # Şirketin varsayılan deposunu bul
            warehouse = self.env['stock.warehouse'].search([
                ('company_id', '=', target_company.id)
            ], limit=1)
            if warehouse:
                order_vals['warehouse_id'] = warehouse.id

        # Sipariş oluştur
        order = self.env['sale.order'].with_company(target_company).create(order_vals)

        # Sipariş satırları
        lines_data = transaction_data.get('lines') or transaction_data.get('items') or []
        for line_data in lines_data:
            self._create_sale_order_line(order, line_data, target_company)

        _logger.info(f"Faturasız işlem için SO oluşturuldu: {order.name} (Şirket: {target_company.name})")
        return order

    def _create_sale_order_line(self, order, line_data, company):
        """
        Satış siparişi satırı oluştur

        Args:
            order: sale.order
            line_data: Satır verisi
            company: Hedef şirket
        """
        product_code = line_data.get('code') or line_data.get('productCode')
        product_name = line_data.get('title') or line_data.get('productName') or 'Bilinmeyen Ürün'

        # Ürün bul veya oluştur
        product = None
        if product_code:
            product = self.env['product.product'].search([
                ('default_code', '=', product_code)
            ], limit=1)

        if not product:
            product = self.env['product.product'].search([
                ('name', 'ilike', product_name)
            ], limit=1)

        if not product:
            # Ürün bulunamadı, genel ürün kullan veya oluştur
            product = self.env.ref('product.product_product_1', raise_if_not_found=False)
            if not product:
                product = self.env['product.product'].create({
                    'name': product_name,
                    'default_code': product_code,
                    'type': 'consu',
                })

        # Miktar ve fiyat
        qty = 1.0
        price = 0.0
        try:
            qty = float(line_data.get('quantity') or line_data.get('qty') or 1)
            price_str = str(line_data.get('price') or line_data.get('unitPrice') or '0')
            price = float(price_str.replace('.', '').replace(',', '.'))
        except (ValueError, TypeError):
            pass

        # Satır oluştur
        self.env['sale.order.line'].with_company(company).create({
            'order_id': order.id,
            'product_id': product.id,
            'name': product_name,
            'product_uom_qty': qty,
            'price_unit': price,
        })

    def action_sync_noninvoice_transactions(self):
        """
        Faturasız işlemleri senkronize et

        BizimHesap'tan çekilen işlemler arasında faturasız olanları
        Joker Tedarik'e sale.order olarak kaydeder.
        """
        self.ensure_one()
        _logger.info(f"Starting noninvoice transaction sync for {self.name}")

        if not self.enable_multi_company_routing or not self.secondary_company_id:
            raise UserError(_('Faturasız işlem senkronizasyonu için çok şirketli yönlendirme aktif olmalı ve ikincil şirket seçilmelidir.'))

        created = skipped = failed = 0

        # TODO: BizimHesap'tan işlemleri çek
        # Not: BizimHesap B2B API'de transaction endpoint'i henüz eklenmedi
        # Bu fonksiyon API endpoint eklendiğinde güncellenecek

        self._create_log(
            operation='Sync NonInvoice Transactions',
            status='success',
            records_created=created,
            message=f"Oluşturulan: {created}, Atlanan: {skipped}, Hatalı: {failed}",
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Faturasız İşlem Senkronizasyonu'),
                'message': _(f'Oluşturulan: {created}, Atlanan: {skipped}'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_sync_products(self):
        """
        Ürünleri senkronize et - B2B API formatı
        
        B2B API /products endpoint'i tek seferde tüm ürünleri döndürür.
        """
        self.ensure_one()
        _logger.info(f"Starting product sync for {self.name}")
        
        created = updated = failed = 0
        
        try:
            response = self.get_products()
            
            # B2B API response formatı: {"resultCode": 1, "data": {"products": [...]}}
            if response.get('resultCode') == 1:
                products = response.get('data', {}).get('products', [])
                
                _logger.info(f"Found {len(products)} products from BizimHesap")
                
                for product_data in products:
                    try:
                        result = self._import_product(product_data)
                        if result == 'created':
                            created += 1
                        elif result == 'updated':
                            updated += 1
                    except Exception as e:
                        failed += 1
                        _logger.error(f"Product import error: {e}")
            else:
                error_text = response.get('errorText', 'Bilinmeyen hata')
                _logger.error(f"BizimHesap API error: {error_text}")
                raise UserError(_(f"API Hatası: {error_text}"))
                
        except Exception as e:
            _logger.error(f"Product sync error: {e}")
            raise
        
        self.last_product_sync = fields.Datetime.now()
        
        self._create_log(
            operation='Sync Products',
            status='success',
            records_created=created,
            records_updated=updated,
            records_failed=failed,
            message=f"Oluşturulan: {created}, Güncellenen: {updated}, Hatalı: {failed}",
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Ürün Senkronizasyonu'),
                'message': _(f'Oluşturulan: {created}, Güncellenen: {updated}, Hatalı: {failed}'),
                'type': 'success' if failed == 0 else 'warning',
                'sticky': False,
            }
        }
    
    def _import_product(self, data):
        """
        Tek ürün import et - Protokollerle eşleştirme

        Eşleştirme sırası:
        1. Barkod → Kesin eşleşme
        2. Ürün kodu aynı + Barkod farklı → Varyant oluştur
        3. İsim benzerliği ≥%50 → Güncelle
        4. Hiçbiri → Yeni oluştur

        İsim Koruma Politikası:
        - Mevcut ürünlerde isim güncellenmez (XML birincil kaynak)
        - Sadece YENİ ürünlerde isim BizimHesap'tan alınır
        """
        external_id = str(data.get('id'))

        # Mevcut binding kontrol
        binding = self.env['bizimhesap.product.binding'].search([
            ('backend_id', '=', self.id),
            ('external_id', '=', external_id),
        ], limit=1)

        # Tüm değerleri al
        product_vals = self._map_product_to_odoo(data)

        # Mevcut ürünler için isim ve barkod güncellenmez - XML birincil kaynak
        # Barkod çakışması sorunlarını önlemek için barkod da korunur
        update_vals = {k: v for k, v in product_vals.items() if k not in ('name', 'barcode')}

        if binding:
            # Mevcut kayıt - isim HARİÇ güncelle
            binding.odoo_id.with_context(sync_source='bizimhesap').write(update_vals)
            binding.write({
                'sync_date': fields.Datetime.now(),
                'external_data': json.dumps(data),
            })
            return 'updated'
        
        # Protokollerle eşleştirme
        source_product = {
            'name': data.get('title', ''),
            'default_code': data.get('code'),
            'barcode': data.get('barcode'),
        }
        
        # Tüm mevcut ürünleri al
        all_products = self.env['product.product'].search_read(
            [],
            ['id', 'name', 'default_code', 'barcode', 'product_tmpl_id']
        )
        
        # Protokol ile eşleştir
        match = {'match_type': 'new'}
        if SYNC_PROTOCOLS:
            match = SYNC_PROTOCOLS.match_product(source_product, all_products)
        
        if match['match_type'] == 'exact':
            # Kesin eşleşme - barkod ile bulundu
            # İsim HARİÇ güncelle (XML birincil kaynak)
            product_id = match['matched_product']['id']
            product = self.env['product.product'].browse(product_id)
            product.with_context(sync_source='bizimhesap').write(update_vals)
            
            self.env['bizimhesap.product.binding'].create({
                'backend_id': self.id,
                'external_id': external_id,
                'odoo_id': product.id,
                'sync_date': fields.Datetime.now(),
                'external_data': json.dumps(data),
            })
            _logger.info(f"Ürün eşleşti (barkod): {data.get('title')}")
            return 'updated'
        
        elif match['match_type'] == 'variant':
            # Aynı ürün kodu, farklı barkod - varyant yerine mevcut ürünü güncelle
            # Odoo 19'da aynı template için boş combination_indices ile yeni varyant oluşturulamaz
            template_id = match['matched_template_id']
            
            # Mevcut product_product kaydını bul
            existing_product = self.env['product.product'].search([
                ('product_tmpl_id', '=', template_id),
                ('combination_indices', '=', ''),
            ], limit=1)
            
            if existing_product:
                # Mevcut ürünü güncelle - isim HARİÇ (XML birincil kaynak)
                existing_product.with_context(sync_source='bizimhesap').write(update_vals)
                product = existing_product
                _logger.info(f"Mevcut varyant güncellendi: {data.get('title')} (Barkod: {data.get('barcode')})")
            else:
                # Yeni oluştur (combination_indices olmadan) - isim DAHİL
                product_vals['product_tmpl_id'] = template_id
                product = self.env['product.product'].with_context(sync_source='bizimhesap').create(product_vals)
                _logger.info(f"Varyant oluşturuldu: {data.get('title')} (Barkod: {data.get('barcode')})")
            
            # Binding kontrolü - duplicate önle
            existing_binding = self.env['bizimhesap.product.binding'].search([
                ('backend_id', '=', self.id),
                ('external_id', '=', external_id),
            ], limit=1)
            
            if existing_binding:
                existing_binding.write({
                    'odoo_id': product.id,
                    'sync_date': fields.Datetime.now(),
                    'external_data': json.dumps(data),
                })
            else:
                self.env['bizimhesap.product.binding'].create({
                    'backend_id': self.id,
                    'external_id': external_id,
                    'odoo_id': product.id,
                    'sync_date': fields.Datetime.now(),
                    'external_data': json.dumps(data),
                })
            return 'updated'
        
        elif match['match_type'] == 'similar':
            # Benzer isim - isim HARİÇ güncelle (XML birincil kaynak)
            product_id = match['matched_product']['id']
            product = self.env['product.product'].browse(product_id)
            product.with_context(sync_source='bizimhesap').write(update_vals)
            
            self.env['bizimhesap.product.binding'].create({
                'backend_id': self.id,
                'external_id': external_id,
                'odoo_id': product.id,
                'sync_date': fields.Datetime.now(),
                'external_data': json.dumps(data),
            })
            _logger.info(f"Benzer ürün güncellendi ({match['reason']}): {data.get('title')}")
            return 'updated'
        
        else:
            # Yeni ürün oluştur - isim DAHİL (ilk kez)
            product = self.env['product.product'].with_context(sync_source='bizimhesap').create(product_vals)
            
            self.env['bizimhesap.product.binding'].create({
                'backend_id': self.id,
                'external_id': external_id,
                'odoo_id': product.id,
                'sync_date': fields.Datetime.now(),
                'external_data': json.dumps(data),
            })
            _logger.info(f"Yeni ürün oluşturuldu: {data.get('title')}")
            return 'created'
    
    def _map_product_to_odoo(self, data):
        """
        BizimHesap B2B API ürün → Odoo product dönüşümü
        
        B2B API Field Mapping:
        - id: External ID
        - isActive: Aktif durum
        - code: Ürün kodu
        - barcode: Barkod
        - title: Ürün adı
        - price: Satış fiyatı (KDV dahil)
        - buyingPrice: Alış fiyatı
        - currency: Para birimi (TL)
        - unit: Birim (Adet)
        - tax: KDV oranı (%)
        - photo: Ürün fotoğrafı JSON
        - description: Açıklama
        - brand: Marka
        - category: Kategori
        - quantity: Stok miktarı
        """
        vals = {
            'name': data.get('title', 'Bilinmiyor'),
            'default_code': data.get('code') or '',
            'barcode': data.get('barcode') or False,
            'description_sale': data.get('description') or data.get('ecommerceDescription', ''),
            'description_purchase': data.get('note', ''),
            'list_price': float(data.get('price', 0)),
            'standard_price': float(data.get('buyingPrice', 0)),
            'active': data.get('isActive', 1) == 1,
            'type': 'consu',  # Stoklanan ürün
            'sale_ok': True,
            'purchase_ok': True,
        }
        
        # Birim dönüşümü
        unit = data.get('unit', 'Adet')
        unit_mapping = {
            'Adet': 'Units',
            'Kg': 'kg',
            'Lt': 'Liters',
            'M': 'm',
            'Paket': 'Units',
            'Koli': 'Units',
        }
        odoo_unit = unit_mapping.get(unit, 'Units')
        uom = self.env['uom.uom'].search([('name', 'ilike', odoo_unit)], limit=1)
        if uom:
            vals['uom_id'] = uom.id
            # Odoo 19'da uom_po_id product.template'de, product.product'da değil
            # Sadece purchase modülü yüklüyse mevcut
            if 'uom_po_id' in self.env['product.product']._fields:
                vals['uom_po_id'] = uom.id
        
        # KDV oranı
        tax_rate = float(data.get('tax', 20))
        if tax_rate:
            tax = self.env['account.tax'].search([
                ('amount', '=', tax_rate),
                ('type_tax_use', '=', 'sale'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if tax:
                vals['taxes_id'] = [(6, 0, [tax.id])]
        
        # Marka ve Kategori notlara ekle
        brand = data.get('brand', '')
        category = data.get('category', '')
        if brand or category:
            notes = []
            if brand:
                notes.append(f"Marka: {brand}")
            if category:
                notes.append(f"Kategori: {category}")
            vals['description_purchase'] = '\n'.join(notes)

        # Tedarikçi fiyatı (USD → TRY dönüşümü)
        if self.sync_supplier_price:
            buying_price = float(data.get('buyingPrice', 0) or 0)
            if buying_price > 0:
                # BizimHesap buyingPrice muhtemelen USD - TRY'ye çevir
                supplier_price_try = buying_price * self.supplier_currency_rate
                vals['xml_supplier_price'] = supplier_price_try
                _logger.debug(f"Tedarikçi fiyatı: {buying_price} USD × {self.supplier_currency_rate} = {supplier_price_try} TRY")

        return vals
    
    def action_sync_invoices(self):
        """Faturaları senkronize et"""
        self.ensure_one()
        _logger.info(f"Starting invoice sync for {self.name}")
        
        created = updated = failed = 0
        
        # Son 30 günlük faturaları çek
        start_date = datetime.now() - timedelta(days=30)
        
        try:
            response = self.get_invoices(start_date=start_date)
            invoices = response.get('data', response) if isinstance(response, dict) else response
            
            for invoice_data in invoices:
                try:
                    result = self._import_invoice(invoice_data)
                    if result == 'created':
                        created += 1
                    elif result == 'updated':
                        updated += 1
                except Exception as e:
                    failed += 1
                    _logger.error(f"Invoice import error: {e}")
                    
        except Exception as e:
            _logger.error(f"Invoice sync error: {e}")
        
        self.last_invoice_sync = fields.Datetime.now()
        
        self._create_log(
            operation='Sync Invoices',
            status='success',
            records_created=created,
            records_updated=updated,
            records_failed=failed,
            message=f"Oluşturulan: {created}, Güncellenen: {updated}, Hatalı: {failed}",
        )
        
        return {'created': created, 'updated': updated, 'failed': failed}
    
    def _import_invoice(self, data):
        """
        Tek fatura import et.
        Mükerrer kayıt önleme: Aynı fatura QNB veya başka kaynaktan zaten varsa
        (partner + ref aynı) yeni kayıt oluşturulmaz; sadece binding varsa güncellenir.
        BizimHesap sadece geçmiş kayıt izleme için kullanıldığından, asıl fatura
        kaynağı QNB (Nilvera benzeri) ile çakışmamalı.
        """
        external_id = str(data.get('id'))
        
        binding = self.env['bizimhesap.invoice.binding'].search([
            ('backend_id', '=', self.id),
            ('external_id', '=', external_id),
        ], limit=1)
        
        if binding:
            # Fatura zaten var, atla
            return 'skipped'
        
        invoice_vals = self._map_invoice_to_odoo(data)
        
        if not invoice_vals:
            return 'skipped'
        
        # Mükerrer kayıt önleme: Aynı partner + ref (fatura no) ile kayıt var mı?
        # (QNB veya başka entegratörden gelmiş olabilir - tek fatura tek kayıt)
        ref_value = invoice_vals.get('ref') or data.get('invoiceNumber') or ''
        if ref_value and invoice_vals.get('partner_id') and invoice_vals.get('move_type'):
            existing = self.env['account.move'].search([
                ('company_id', '=', self.company_id.id),
                ('partner_id', '=', invoice_vals['partner_id']),
                ('ref', '=', ref_value),
                ('move_type', '=', invoice_vals['move_type']),
            ], limit=1)
            if existing:
                _logger.info(
                    "BizimHesap fatura atlandı (zaten mevcut kayıt - mükerrer önleme): "
                    "partner_id=%s ref=%s", invoice_vals['partner_id'], ref_value
                )
                # İsteğe bağlı: mevcut faturaya binding ekle (BizimHesap'tan da izlendiğini işaretle)
                self.env['bizimhesap.invoice.binding'].create({
                    'backend_id': self.id,
                    'external_id': external_id,
                    'odoo_id': existing.id,
                    'sync_date': fields.Datetime.now(),
                    'external_data': json.dumps(data),
                })
                return 'skipped'
        
        invoice = self.env['account.move'].create(invoice_vals)
        
        self.env['bizimhesap.invoice.binding'].create({
            'backend_id': self.id,
            'external_id': external_id,
            'odoo_id': invoice.id,
            'sync_date': fields.Datetime.now(),
            'external_data': json.dumps(data),
        })
        
        return 'created'
    
    def _map_invoice_to_odoo(self, data):
        """BizimHesap fatura → Odoo account.move dönüşümü"""
        # Partner bul
        contact_id = data.get('contactId')
        partner = None
        
        if contact_id:
            binding = self.env['bizimhesap.partner.binding'].search([
                ('backend_id', '=', self.id),
                ('external_id', '=', str(contact_id)),
            ], limit=1)
            if binding:
                partner = binding.odoo_id
        
        if not partner:
            _logger.warning(f"Partner not found for invoice: {data.get('invoiceNumber')}")
            return None
        
        # Fatura tipi
        invoice_type = data.get('invoiceType', 1)
        move_type = 'out_invoice' if invoice_type == 1 else 'in_invoice'
        
        vals = {
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_date': data.get('invoiceDate'),
            'ref': data.get('invoiceNumber'),
            'narration': data.get('description'),
        }
        
        # Fatura kalemleri
        lines = []
        for line_data in data.get('lines', []):
            line_vals = self._map_invoice_line_to_odoo(line_data, move_type)
            if line_vals:
                lines.append((0, 0, line_vals))
        
        if lines:
            vals['invoice_line_ids'] = lines
        
        return vals
    
    def _map_invoice_line_to_odoo(self, data, move_type):
        """Fatura kalemi dönüşümü"""
        # Ürün bul
        product = None
        product_id = data.get('productId')
        
        if product_id:
            binding = self.env['bizimhesap.product.binding'].search([
                ('backend_id', '=', self.id),
                ('external_id', '=', str(product_id)),
            ], limit=1)
            if binding:
                product = binding.odoo_id
        
        vals = {
            'name': data.get('productName', 'Ürün'),
            'quantity': float(data.get('quantity', 1)),
            'price_unit': float(data.get('unitPrice', 0)),
        }
        
        if product:
            vals['product_id'] = product.id
        
        # KDV
        vat_rate = data.get('vatRate', 20)
        if vat_rate:
            tax_type = 'sale' if move_type == 'out_invoice' else 'purchase'
            tax = self.env['account.tax'].search([
                ('amount', '=', vat_rate),
                ('type_tax_use', '=', tax_type),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if tax:
                vals['tax_ids'] = [(6, 0, [tax.id])]
        
        return vals
    
    # ═══════════════════════════════════════════════════════════════
    # EXPORT METHODS (Odoo → BizimHesap)
    # ═══════════════════════════════════════════════════════════════
    
    def export_partner(self, partner):
        """Partner'ı BizimHesap'a gönder"""
        self.ensure_one()
        
        # Mevcut binding kontrol
        binding = self.env['bizimhesap.partner.binding'].search([
            ('backend_id', '=', self.id),
            ('odoo_id', '=', partner.id),
        ], limit=1)
        
        data = self._map_partner_to_bizimhesap(partner)
        
        if binding:
            # Güncelle
            result = self.update_contact(binding.external_id, data)
        else:
            # Yeni oluştur
            result = self.create_contact(data)
            
            if result and result.get('id'):
                self.env['bizimhesap.partner.binding'].create({
                    'backend_id': self.id,
                    'external_id': str(result['id']),
                    'odoo_id': partner.id,
                    'sync_date': fields.Datetime.now(),
                })
        
        return result
    
    def _map_partner_to_bizimhesap(self, partner):
        """Odoo partner → BizimHesap cari dönüşümü"""
        # Cari tipi belirle
        if partner.customer_rank > 0 and partner.supplier_rank > 0:
            contact_type = 3
        elif partner.supplier_rank > 0:
            contact_type = 2
        else:
            contact_type = 1
        
        return {
            'code': partner.ref or '',
            'title': partner.name,
            'taxNumber': partner.vat or '',
            'taxOffice': getattr(partner, 'l10n_tr_tax_office_name', '') or '',
            'address': partner.street or '',
            'city': partner.city or '',
            'postalCode': partner.zip or '',
            'phone': partner.phone or '',
            'mobile': partner.mobile or '',
            'email': partner.email or '',
            'website': partner.website or '',
            'note': partner.comment or '',
            'contactType': contact_type,
            'currencyCode': 'TRY',
        }
    
    def export_product(self, product):
        """Ürünü BizimHesap'a gönder"""
        self.ensure_one()
        
        binding = self.env['bizimhesap.product.binding'].search([
            ('backend_id', '=', self.id),
            ('odoo_id', '=', product.id),
        ], limit=1)
        
        data = self._map_product_to_bizimhesap(product)
        
        if binding:
            result = self.update_product(binding.external_id, data)
        else:
            result = self.create_product(data)
            
            if result and result.get('id'):
                self.env['bizimhesap.product.binding'].create({
                    'backend_id': self.id,
                    'external_id': str(result['id']),
                    'odoo_id': product.id,
                    'sync_date': fields.Datetime.now(),
                })
        
        return result
    
    def _map_product_to_bizimhesap(self, product):
        """Odoo product → BizimHesap ürün dönüşümü"""
        # KDV oranı
        vat_rate = 20
        if product.taxes_id:
            vat_rate = product.taxes_id[0].amount
        
        return {
            'code': product.default_code or '',
            'name': product.name,
            'description': product.description_sale or '',
            'unit': product.uom_id.name if product.uom_id else 'Adet',
            'vatRate': int(vat_rate),
            'purchasePrice': product.standard_price,
            'salePrice': product.list_price,
            'currencyCode': 'TRY',
            'stockTracking': product.type == 'product',
        }
    
    def export_invoice(self, invoice):
        """
        Faturayı BizimHesap'a gönder
        
        BizimHesap B2B API /addinvoice endpoint'i kullanılır.
        InvoiceType: 3=Satış, 5=Alış
        """
        self.ensure_one()
        _logger.info(f"Exporting invoice {invoice.name} to BizimHesap")
        
        # Fatura zaten gönderilmiş mi?
        if invoice.bizimhesap_guid:
            _logger.warning(f"Invoice {invoice.name} already sent to BizimHesap")
            return {'guid': invoice.bizimhesap_guid, 'url': invoice.bizimhesap_url}
        
        # Fatura verisini hazırla
        data = self._map_invoice_to_bizimhesap(invoice)
        
        # API'ye gönder
        try:
            response = self._api_request('POST', '/addinvoice', data=data)
            
            if response.get('error'):
                raise UserError(f"BizimHesap Hata: {response.get('error')}")
            
            guid = response.get('guid')
            url = response.get('url')
            
            # Faturayı güncelle
            invoice.write({
                'bizimhesap_guid': guid,
                'bizimhesap_url': url,
                'bizimhesap_sent_date': fields.Datetime.now(),
            })
            
            # Binding oluştur
            self.env['bizimhesap.invoice.binding'].create({
                'backend_id': self.id,
                'external_id': guid,
                'odoo_id': invoice.id,
                'sync_date': fields.Datetime.now(),
                'external_data': json.dumps(data),
            })
            
            # Log
            self._create_log(
                operation='Export Invoice',
                status='success',
                records_created=1,
                message=f"Fatura {invoice.name} BizimHesap'a gönderildi: {guid}",
            )
            
            _logger.info(f"Invoice {invoice.name} exported successfully: {guid}")
            return response
            
        except Exception as e:
            _logger.error(f"Invoice export error: {e}")
            self._create_log(
                operation='Export Invoice',
                status='error',
                records_failed=1,
                message=f"Fatura {invoice.name} gönderilemedi: {str(e)}",
            )
            raise UserError(f"Fatura gönderilemedi: {str(e)}")
    
    def _map_invoice_to_bizimhesap(self, invoice):
        """
        Odoo account.move → BizimHesap fatura dönüşümü
        
        BizimHesap B2B API formatı:
        - firmId: API Key
        - invoiceNo: Fatura numarası
        - invoiceType: 3=Satış, 5=Alış
        - dates: {invoiceDate, dueDate, deliveryDate}
        - customer: {customerId, title, address, taxOffice, taxNo, email, phone}
        - amounts: {currency, gross, discount, net, tax, total}
        - details: [{productId, productName, taxRate, quantity, unitPrice, ...}]
        """
        partner = invoice.partner_id
        
        # Fatura tipi: out_invoice/out_refund = Satış (3), in_invoice/in_refund = Alış (5)
        if invoice.move_type in ('out_invoice', 'out_refund'):
            invoice_type = 3  # Satış
        else:
            invoice_type = 5  # Alış
        
        # Partner binding'den BizimHesap ID al
        partner_binding = self.env['bizimhesap.partner.binding'].search([
            ('backend_id', '=', self.id),
            ('odoo_id', '=', partner.id),
        ], limit=1)
        
        customer_id = partner_binding.external_id if partner_binding else ''
        
        # Tarihler
        invoice_date = invoice.invoice_date or fields.Date.today()
        due_date = invoice.invoice_date_due or invoice_date
        
        # Tutar hesapla
        gross = sum(line.price_unit * line.quantity for line in invoice.invoice_line_ids)
        discount = sum((line.price_unit * line.quantity * line.discount / 100) for line in invoice.invoice_line_ids)
        net = invoice.amount_untaxed
        tax = invoice.amount_tax
        total = invoice.amount_total
        
        # Para birimi
        currency = invoice.currency_id.name or 'TL'
        if currency == 'TRY':
            currency = 'TL'
        
        # Fatura kalemleri
        details = []
        for line in invoice.invoice_line_ids.filtered(lambda l: not l.display_type):
            # Ürün binding'den BizimHesap ID al
            product_id = ''
            if line.product_id:
                product_binding = self.env['bizimhesap.product.binding'].search([
                    ('backend_id', '=', self.id),
                    ('odoo_id', '=', line.product_id.id),
                ], limit=1)
                product_id = product_binding.external_id if product_binding else ''
            
            # KDV oranı
            tax_rate = 20
            if line.tax_ids:
                tax_rate = line.tax_ids[0].amount
            
            line_gross = line.price_unit * line.quantity
            line_discount = line_gross * line.discount / 100
            line_net = line_gross - line_discount
            line_tax = line_net * tax_rate / 100
            line_total = line_net + line_tax
            
            details.append({
                'productId': product_id,
                'productName': line.name or line.product_id.name if line.product_id else 'Ürün',
                'note': '',
                'barcode': line.product_id.barcode if line.product_id and line.product_id.barcode else '',
                'taxRate': f"{tax_rate:.2f}",
                'quantity': line.quantity,
                'unitPrice': f"{line.price_unit:,.2f}",
                'grossPrice': f"{line_gross:,.2f}",
                'discount': f"{line_discount:,.2f}",
                'net': f"{line_net:,.2f}",
                'tax': f"{line_tax:,.2f}",
                'total': f"{line_total:,.2f}",
            })
        
        return {
            'firmId': self.api_key,
            'invoiceNo': invoice.name,
            'invoiceType': invoice_type,
            'note': invoice.narration or '',
            'dates': {
                'invoiceDate': invoice_date.strftime('%Y-%m-%dT00:00:00.000+03:00'),
                'dueDate': due_date.strftime('%Y-%m-%dT00:00:00.000+03:00'),
                'deliveryDate': invoice_date.strftime('%Y-%m-%dT00:00:00.000+03:00'),
            },
            'customer': {
                'customerId': customer_id,
                'title': partner.name,
                'taxOffice': getattr(partner, 'l10n_tr_tax_office_name', '') or '',
                'taxNo': partner.vat or '',
                'email': partner.email or '',
                'phone': partner.phone or '',
                'address': partner.street or '',
            },
            'amounts': {
                'currency': currency,
                'gross': f"{gross:,.2f}",
                'discount': f"{discount:,.2f}",
                'net': f"{net:,.2f}",
                'tax': f"{tax:,.2f}",
                'total': f"{total:,.2f}",
            },
            'details': details,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # CRON
    # ═══════════════════════════════════════════════════════════════
    
    @api.model
    def _cron_sync_all(self):
        """Otomatik senkronizasyon cron job"""
        backends = self.search([
            ('active', '=', True),
            ('state', '=', 'connected'),
            ('auto_sync', '=', True),
        ])
        
        for backend in backends:
            try:
                backend.action_sync_all()
            except Exception as e:
                _logger.error(f"Cron sync failed for {backend.name}: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # VIEW ACTIONS
    # ═══════════════════════════════════════════════════════════════
    
    def action_view_logs(self):
        """Logları görüntüle"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Senkronizasyon Logları'),
            'res_model': 'bizimhesap.sync.log',
            'view_mode': 'tree,form',
            'domain': [('backend_id', '=', self.id)],
            'context': {'default_backend_id': self.id},
        }
    
    def action_view_partner_bindings(self):
        """Cari eşleşmelerini görüntüle"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cari Eşleşmeleri'),
            'res_model': 'bizimhesap.partner.binding',
            'view_mode': 'tree,form',
            'domain': [('backend_id', '=', self.id)],
        }
    
    def action_view_product_bindings(self):
        """Ürün eşleşmelerini görüntüle"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ürün Eşleşmeleri'),
            'res_model': 'bizimhesap.product.binding',
            'view_mode': 'tree,form',
            'domain': [('backend_id', '=', self.id)],
        }
    
    def action_view_invoice_bindings(self):
        """Fatura eşleşmelerini görüntüle"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fatura Eşleşmeleri'),
            'res_model': 'bizimhesap.invoice.binding',
            'view_mode': 'tree,form',
            'domain': [('backend_id', '=', self.id)],
        }
