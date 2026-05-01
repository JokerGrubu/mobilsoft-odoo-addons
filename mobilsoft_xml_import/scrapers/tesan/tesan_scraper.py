# -*- coding: utf-8 -*-
import requests
import logging
import json
import time

_logger = logging.getLogger(__name__)

class TesanScraper:
    def __init__(self, base_url=None, username=None, password=None, config=None):
        self.base_url = base_url or 'https://isortagim.tesan.com.tr'
        self.api_url = 'https://api.tesan.com.tr/product/product'
        self.username = username or 'info@jokergrubu.com'
        self.password = password or 'XZsawq21-'
        self.config = config or {}
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self.access_token = None
        self.session_active = False

    def login(self):
        """Tesan portal'a giriş yap ve API token'ı al"""
        try:
            csrf_resp = self.session.get(f'{self.base_url}/api/auth/csrf', timeout=15)
            csrf_token = csrf_resp.json().get('csrfToken')
            
            login_data = {
                'username': self.username,
                'password': self.password,
                'csrfToken': csrf_token,
                'json': 'true',
                'callbackUrl': self.base_url + '/'
            }
            self.session.post(f'{self.base_url}/api/auth/callback/credentials', data=login_data)
            
            auth_session = self.session.get(f'{self.base_url}/api/auth/session').json()
            self.access_token = auth_session.get('accessToken')
            
            if self.access_token:
                self.session_active = True
                self.session.headers.update({'Authorization': f'Bearer {self.access_token}'})
                return True
            return False
        except Exception as e:
            _logger.error(f"Tesan login hatası: {e}")
            return False

    def scrape_products(self):
        """Odoo 'Ürünleri Çek' butonuna basıldığında tüm Tesan havuzunu sunar"""
        all_products = []
        scan_file = '/tmp/tesan_scan_results.json'
        
        import os
        if os.path.exists(scan_file):
            _logger.info(f"Tarama dosyasından ürünler yükleniyor: {scan_file}")
            with open(scan_file, 'r') as f:
                scan_data = json.load(f)
                for item in scan_data:
                    all_products.append({
                        'id': item.get('productId'),
                        'sku': item.get('modelCode') or f"TESAN-{item.get('productId')}",
                        'name': item.get('name'),
                        'barcode': item.get('barcode'),
                        'stock_status': 'in_stock' # Detay çekiminde netleşecek
                    })
            _logger.info(f"Dosyadan {len(all_products)} ürün havuzu oluşturuldu.")
        else:
            _logger.warning("Tarama dosyası bulunamadı, arama yöntemine dönülüyor.")
            # Yedek plan: Eski arama mantığı
            keywords = ['ttec', 'hikvision', 'hi-look', 'ruijie', 'xiaomi']
            for kw in keywords:
                try:
                    params = {'keyword': kw, 'size': 200}
                    r = self.session.get(f"{self.base_url}/api/search", params=params, timeout=20)
                    if r.status_code == 200:
                        items = r.json().get('data', [])
                        for item in items:
                            all_products.append({
                                'id': item.get('productId'),
                                'sku': item.get('specialCode') or f"TESAN-{item.get('productId')}",
                                'name': item.get('name'),
                                'barcode': item.get('barcode'),
                                'stock_status': 'in_stock'
                            })
                except Exception as e:
                    _logger.error(f"Arama hatası ({kw}): {e}")
        
        return all_products

    def get_product_data(self, product_id):
        """Tekil ürün detaylarını (Fiyat, Teknik Tablo) çekmek için Odoo tarafından çağrılır"""
        if not self.session_active:
            if not self.login(): return None
        
        try:
            # 1. Detay ve Teknik Bilgiler
            info = self._api_get(f'GetProductInfoById/{product_id}')
            if not info: return None
            
            # 2. Fiyat (Maliyet) Bilgisi
            prices = self._api_get(f'GetCustomerPriceList/{product_id}')
            price_info = prices[0] if prices else {}
            
            # 3. Varyant Resimleri
            variants = self._api_get(f'GetProductVariants/{product_id}')
            image_urls = [v.get('imagePath') for v in variants if v.get('imagePath')] if variants else []

            cost_usd = float(price_info.get('lastPrice', 0.0))
            return {
                'id': info.get('productId'),
                'sku': info.get('specialCode') or f"TESAN-{info.get('productId')}",
                'name': info.get('productName'),
                'barcode': info.get('barcode'),
                'brand': info.get('brandName'),
                'cost_price': cost_usd,      # USD maliyet → xml_supplier_price
                'price': 0.0,                # Satış fiyatı markup ile ayrıca hesaplanır
                'currency': price_info.get('currency', 'USD'),
                'description': self._format_technical_info(info.get('technicalInfos', [])),
                'image_url': image_urls[0] if image_urls else info.get('imagePath'),
                'image_urls': ",".join(image_urls) if image_urls else None,
                'raw_stock': info.get('stock', 0),
                'stock_status': 'in_stock' if info.get('stock', 0) > 0 else 'out_of_stock'
            }
        except Exception as e:
            _logger.error(f"Detay çekme hatası (ID: {product_id}): {e}")
            return None

    def _api_get(self, endpoint):
        try:
            r = self.session.get(f"{self.api_url}/{endpoint}", timeout=20)
            return r.json().get('data') if r.status_code == 200 else None
        except:
            return None

    def _format_technical_info(self, infos):
        if not infos: return ""
        html = "<table class='table table-sm table-striped'><tbody>"
        for info in infos:
            html += f"<tr><td><b>{info.get('specificationName')}</b></td><td>{info.get('specificationValue')}</td></tr>"
        html += "</tbody></table>"
        return html
