# -*- coding: utf-8 -*-
"""
Tesan İş Ortağım B2B Portal — paralel REST API scraper.

Auth akışı:
  1. GET  /api/auth/csrf
  2. POST /api/auth/callback/credentials
  3. GET  /api/auth/session  → accessToken
  4. POST /customer/customer/GetCustomerByToken {Token1: accessToken} → customerId
  5. GET  /customer/customer/GetCustomerTokenById/{customerId} → customerToken

Ürün akışı (tek paralel geçiş):
  - Tüm ID'ler için GetProductInfoById paralel taranır
  - Var olan her ürün için GetCustomerPriceList + GetPictureByProductId aynı anda çekilir
"""

import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

_logger = logging.getLogger(__name__)

API_URL = 'https://api.tesan.com.tr'
MAX_ID  = 2500
WORKERS = 15   # paralel iş parçacığı


class TesanScraper:
    def __init__(self, base_url=None, username=None, password=None, config=None):
        self.base_url       = (base_url or 'https://isortagim.tesan.com.tr').rstrip('/')
        self.username       = username or 'info@jokergrubu.com'
        self.password       = password or 'XZsawq21-'
        self.config         = config or {}
        self.session        = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        self.access_token   = None
        self.customer_token = ''
        self.session_active = False

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def login(self):
        try:
            csrf = self.session.get(
                f'{self.base_url}/api/auth/csrf', verify=False, timeout=15
            ).json().get('csrfToken')

            self.session.post(
                f'{self.base_url}/api/auth/callback/credentials',
                data={'username': self.username, 'password': self.password,
                      'csrfToken': csrf, 'json': 'true',
                      'callbackUrl': self.base_url + '/'},
                verify=False, timeout=15,
            )

            sess = self.session.get(
                f'{self.base_url}/api/auth/session', verify=False, timeout=15
            ).json()
            self.access_token = sess.get('accessToken')
            if not self.access_token:
                return False

            self._resolve_customer_token()
            self.session_active = True
            return True
        except Exception as e:
            _logger.error('Tesan login hatası: %s', e)
            return False

    def _resolve_customer_token(self):
        hdrs = self._auth_headers()
        try:
            r = self.session.post(
                f'{API_URL}/customer/customer/GetCustomerByToken',
                json={'Token1': self.access_token},
                headers=hdrs, verify=False, timeout=15,
            )
            if r.status_code == 200:
                cid = (r.json().get('data') or {}).get('customerId')
                if cid:
                    r2 = self.session.get(
                        f'{API_URL}/customer/customer/GetCustomerTokenById/{cid}',
                        headers=hdrs, verify=False, timeout=15,
                    )
                    if r2.status_code == 200:
                        self.customer_token = (r2.json().get('data') or {}).get('Token', '')
        except Exception as e:
            _logger.warning('customerToken çözümlenemedi: %s', e)

    def _auth_headers(self):
        return {
            'Authorization': f'Bearer {self.access_token}',
            'CustomerToken': self.customer_token or '',
        }

    # ------------------------------------------------------------------
    # Ana tarama — tek paralel geçiş (info + fiyat + görsel)
    # ------------------------------------------------------------------

    def scrape_products(self):
        """
        Tüm Tesan ürünlerini tek paralel geçişte çek.
        Her ürün için info+fiyat+görsel aynı anda alınır.
        Sonuç: _create_or_update_product_from_scraping'in beklediği dict listesi.
        """
        if not self.session_active and not self.login():
            return []

        max_id  = int(self.config.get('max_product_id', MAX_ID))
        workers = int(self.config.get('workers', WORKERS))
        brand_filter = [b.lower() for b in self.config.get('brands', [])]

        _logger.info('Tesan tarama başlıyor: ID 1-%d, %d worker', max_id, workers)

        hdrs = self._auth_headers()

        def _fetch_full(pid):
            """Tek ürün için info + fiyat + görsel"""
            try:
                info_r = requests.get(
                    f'{API_URL}/product/product/GetProductInfoById/{pid}',
                    headers=hdrs, verify=False, timeout=12,
                )
                if info_r.status_code != 200:
                    return None
                info = info_r.json().get('data')
                if not info:
                    return None

                brand = (info.get('brandName') or '').lower()
                if brand_filter and brand not in brand_filter:
                    return None

                # Fiyat
                price_r = requests.get(
                    f'{API_URL}/product/product/GetCustomerPriceList/{pid}',
                    headers=hdrs, verify=False, timeout=12,
                )
                prices = price_r.json().get('data', []) if price_r.status_code == 200 else []
                price_info = prices[0] if prices else {}

                # Görsel
                img_r = requests.get(
                    f'{API_URL}/Product/Product/GetPictureByProductId/{pid}',
                    headers=hdrs, verify=False, timeout=12,
                )
                images = img_r.json().get('data', []) if img_r.status_code == 200 else []
                img_urls = [i.get('virtualPath') for i in (images or []) if i.get('virtualPath')]

                tech_infos = info.get('technicalInfos', []) or []
                category = next(
                    (t.get('specificationValue', '')
                     for t in tech_infos if t.get('specificationName') == 'Kategori'),
                    ''
                )

                cost      = float(price_info.get('lastPrice') or 0)
                currency  = price_info.get('currency', 'USD')
                cost_usd  = cost if currency == 'USD' else 0.0
                cost_try  = cost if currency == 'TL'  else 0.0
                raw_stock = int(info.get('stock') or 0)
                sku       = info.get('specialCode') or f'TESAN-{pid}'

                return {
                    'id':           pid,
                    'sku':          sku,
                    'name':         info.get('productName', ''),
                    'barcode':      info.get('barcode'),
                    'brand':        info.get('brandName', ''),
                    'cost_price':   cost_usd,
                    'cost_try':     cost_try,
                    'currency':     currency,
                    'price':        0.0,
                    'description':  self._format_tech_info(tech_infos),
                    'image_url':    img_urls[0] if img_urls else info.get('imagePath'),
                    'image_urls':   ','.join(img_urls) if img_urls else None,
                    'raw_stock':    raw_stock,
                    'stock_status': 'in_stock' if raw_stock > 0 else 'out_of_stock',
                    'category':     category,
                }
            except Exception as ex:
                _logger.debug('Tesan ID %d hata: %s', pid, ex)
                return None

        products = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_fetch_full, pid): pid for pid in range(1, max_id + 1)}
            for fut in as_completed(futs):
                data = fut.result()
                if data:
                    products.append(data)

        _logger.info('Tesan tarama tamamlandı: %d ürün', len(products))
        return products

    # ------------------------------------------------------------------
    # get_product_data — artık scrape_products tam veri verdiğinden
    # sadece uyumluluk için burada bırakıldı (boş döner)
    # ------------------------------------------------------------------

    def get_product_data(self, product_id):
        """
        _run_tesan_scraper bu metodu çağırır; ancak scrape_products
        zaten tam veri döndürdüğü için burada None dönmek yeterli —
        caller mevcut product_data'yı kullanır.
        """
        return None

    # ------------------------------------------------------------------
    # Yardımcı
    # ------------------------------------------------------------------

    def _format_tech_info(self, infos):
        if not infos:
            return ''
        rows = ''.join(
            f"<tr><td><b>{i.get('specificationName','')}</b></td>"
            f"<td>{i.get('specificationValue','')}</td></tr>"
            for i in infos
        )
        return f"<table class='table table-sm table-striped'><tbody>{rows}</tbody></table>"
