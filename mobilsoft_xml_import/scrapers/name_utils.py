# -*- coding: utf-8 -*-
"""
Ürün ismi normalleştirme — tüm XML kaynakları için ortak.

Ana kural: [Marka] [Kod] [Detay]
Tesan portalı ürünleri "KOD Marka Detay" formatında gönderir.
Bu modül gelen ismi normalize ederek "Marka KOD Detay" haline getirir.
"""

import re

# Desteklenen marka → canonical yazım
BRAND_MAP = {
    'ttec':       'ttec',
    'taks':       'taks',
    'mojue':      'mojue',
    'recharger':  'ReCharger',
    'easydrive':  'EasyDrive',
    'imou':       'IMOU',
    'hikvision':  'Hikvision',
    'formrack':   'Formrack',
    'reyee':      'Reyee',
    'teknim':     'Teknim',
    'jabra':      'Jabra',
    'zkteco':     'ZKTeco',
    'netgear':    'NetGear',
    'qnap':       'QNAP',
    'aselsan':    'Aselsan',
    'toshiba':    'Toshiba',
    'biwin':      'Biwin',
    'panasonic':  'Panasonic',
    'fanvil':     'Fanvil',
    'uniwiz':     'Uniwiz',
}

_BRAND_PATTERN = re.compile(
    r'^([A-Z0-9][A-Z0-9\-\.]{2,})\s+(' + '|'.join(BRAND_MAP.keys()) + r')\s*(.*)',
    re.IGNORECASE | re.DOTALL,
)


def normalize_product_name(name: str, brand: str = '') -> str:
    """
    Ürün ismini [Marka] [Ürün Kodu] [Detay] formatına getirir.

    Giriş örnekleri:
      "2CKP04S ttec SmartCharger Duo PD 83W ..."  →  "ttec 2CKP04S SmartCharger Duo PD 83W ..."
      "3DK35 mojue Ekstra Dayanıklı USB-A ..."     →  "mojue 3DK35 Ekstra Dayanıklı USB-A ..."
      "ttec 2CKP04S SmartCharger ..."              →  değişmez (zaten doğru)
    """
    if not name:
        return name

    # Satır sonu / fazla boşluk temizle
    name = name.replace('\n', ' ').replace('\r', ' ').strip()

    # "KOD Marka Detay" → "Marka KOD Detay"
    m = _BRAND_PATTERN.match(name)
    if m:
        code     = m.group(1)
        brand_lc = m.group(2).lower()
        details  = m.group(3).strip()

        # İlk token gerçek bir kod mu? (rakam içermeli)
        if re.search(r'\d', code):
            canonical = BRAND_MAP.get(brand_lc, m.group(2))
            # Detay yanlışlıkla yine kodla başlıyorsa kaldır (ör: "HR12 IMOU HR12")
            if details.upper().startswith(code.upper()):
                details = details[len(code):].strip()
            name = f"{canonical} {code} {details}".strip()

    # Çift boşluk → tek
    name = re.sub(r' {2,}', ' ', name)

    return name
