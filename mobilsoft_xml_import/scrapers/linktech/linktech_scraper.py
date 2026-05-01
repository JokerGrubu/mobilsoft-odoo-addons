# -*- coding: utf-8 -*-
"""
LinkTech Web Scraper
Odoo XML Import modülü için
"""

import requests
import re
import json
import time
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class LinkTechScraper:
    """LinkTech Web Scraper"""
    
    def __init__(self, base_url=None, keywords=None, config=None):
        self.base_url = base_url or 'https://www.linktech.com.tr'
        self.keywords = keywords or ['telefon', 'şarj', 'kablo', 'bluetooth', 'kulaklık']
        self.config = config or {}
        self.session = requests.Session()
        self.session_active = False
        
    def login(self):
        """LinkTech sitesine giriş yap (gerekirse)"""
        _logger.info("LinkTech sitesi kontrol ediliyor")
        
        try:
            # Ana sayfaya erişim testi
            resp = self.session.get(self.base_url, timeout=10)
            if resp.status_code == 200:
                self.session_active = True
                _logger.info("LinkTech sitesine erişim başarılı")
                return True
            else:
                _logger.error(f"LinkTech sitesine erişim hatası: {resp.status_code}")
                return False
                
        except Exception as e:
            _logger.error(f"LinkTech erişim hatası: {e}")
            return False
    
    def get_sitemap_products(self):
        """Sitemap'ten ürün URL'lerini al"""
        if not self.session_active:
            self.login()
        
        product_urls = []
        try:
            sitemap_url = f"{self.base_url}/sitemap.xml"
            resp = self.session.get(sitemap_url, timeout=15)
            
            if resp.status_code == 200:
                # URL'leri parse et
                url_pattern = r'<loc>(https://www\.linktech\.com\.tr/[^<]+)</loc>'
                urls = re.findall(url_pattern, resp.text)
                
                # Sadece ürün URL'lerini filtrele
                for url in urls:
                    if '/product/' in url or '/urun/' in url or len(url.split('/')[-1]) > 3:
                        product_urls.append(url)
                
                _logger.info(f"Sitemap'ten {len(product_urls)} ürün URL'si bulundu")
        
        except Exception as e:
            _logger.error(f"Sitemap okuma hatası: {e}")
        
        return product_urls
    
    def scrape_product_page(self, url):
        """Ürün sayfasından bilgileri çek"""
        try:
            resp = self.session.get(url, timeout=15)
            html = resp.text
            
            # JSON-LD verisi ara
            json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
            json_ld_match = re.search(json_ld_pattern, html, re.DOTALL)
            
            if json_ld_match:
                try:
                    product_data = json.loads(json_ld_match.group(1))
                    return self._parse_json_ld(product_data, url)
                except json.JSONDecodeError:
                    pass
            
            # HTML parse et (fallback)
            return self._parse_html_product(html, url)
            
        except Exception as e:
            _logger.error(f"Ürün sayfası hatası ({url}): {e}")
            return None
    
    def _parse_json_ld(self, data, url):
        """JSON-LD verisinden ürün bilgisi çıkar"""
        try:
            # SKU'yu URL'den al
            sku_match = re.search(r'/([A-Z0-9-]+)(?:/|$)', url)
            sku = sku_match.group(1) if sku_match else f"LT-{int(time.time())}"
            
            return {
                'sku': sku,
                'name': data.get('name', ''),
                'price': float(data.get('offers', {}).get('price', 0)),
                'description': data.get('description', ''),
                'category': self._extract_category(data.get('category', '')),
                'image_url': data.get('image', ''),
                'cost_price': float(data.get('offers', {}).get('price', 0)) * 0.7,
                'stock': 10,  # Varsayılan
                'url': url,
            }
        except Exception as e:
            _logger.error(f"JSON-LD parse hatası: {e}")
            return None
    
    def _parse_html_product(self, html, url):
        """HTML'den ürün bilgisi çıkar"""
        try:
            # Başlık
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html)
            title = title_match.group(1).strip() if title_match else ''
            
            # Fiyat
            price = 0.0
            price_patterns = [
                r'"price":\s*"([\d.]+)"',
                r'price["\']?\s*[:=]\s*["\']?([\d.,]+)',
                r'([\d.,]+)\s*₺',
                r'([\d.,]+)\s*TL'
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, html)
                if match:
                    price_str = match.group(1).replace('.', '').replace(',', '.')
                    try:
                        price = float(price_str)
                        break
                    except:
                        continue
            
            # SKU
            sku_match = re.search(r'/([A-Z0-9-]+)(?:/|$)', url)
            sku = sku_match.group(1) if sku_match else f"LT-{int(time.time())}"
            
            # Açıklama
            desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html)
            description = desc_match.group(1).strip() if desc_match else ''
            
            return {
                'sku': sku,
                'name': title,
                'price': price,
                'description': description,
                'category': 'Telefon & Tablet Aksesuarları',
                'cost_price': price * 0.7,
                'stock': 10,
                'url': url,
            }
            
        except Exception as e:
            _logger.error(f"HTML parse hatası: {e}")
            return None
    
    def _extract_category(self, category_str):
        """Kategori bilgisini çıkar"""
        if not category_str:
            return 'Telefon & Tablet Aksesuarları'
        
        # Kategori haritası
        category_map = {
            'şarj': 'Güç & Şarj Çözümleri',
            'kablo': 'Güç & Şarj Çözümleri',
            'bluetooth': 'Ses & Multimedya',
            'kulaklık': 'Ses & Multimedya',
            'speaker': 'Ses & Multimedya',
            'ekran': 'TELEFON & TABLET AKSESUARLARI',
            'kılıf': 'TELEFON & TABLET AKSESUARLARI',
            'koruyucu': 'TELEFON & TABLET AKSESUARLARI',
        }
        
        category_lower = category_str.lower()
        for key, value in category_map.items():
            if key in category_lower:
                return value
        
        return 'Telefon & Tablet Aksesuarları'
    
    def scrape_products(self):
        """Tüm ürünleri çek"""
        _logger.info("LinkTech ürün çekme başlatılıyor")
        
        all_products = []
        
        # Sitemap'ten ürün URL'lerini al
        product_urls = self.get_sitemap_products()
        
        # İlk 100 ürünü çek (limit)
        for i, url in enumerate(product_urls[:100]):
            if i % 10 == 0:
                _logger.info(f"İşleniyor: {i}/{len(product_urls)}")
            
            product = self.scrape_product_page(url)
            if product:
                all_products.append(product)
                _logger.info(f"Ürün eklendi: {product['sku']}")
            
            time.sleep(0.3)  # Rate limiting
        
        _logger.info(f"Toplam {len(all_products)} LinkTech ürünü çekildi")
        return all_products
