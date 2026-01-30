# MobilSoft Odoo 19 Modulleri

> Sunucu üzerindeki doküman haritası: `/joker/Mimar/INDEX.md`

![Odoo Version](https://img.shields.io/badge/Odoo-19.0-blue)
![License](https://img.shields.io/badge/License-LGPL--3-green)
![MobilSoft](https://img.shields.io/badge/MobilSoft-OCA%20Uyesi-orange)

Turkiye icin Odoo 19 Community modulleri. Herhangi bir Odoo 19 kurulumuna eklenebilir.

## Gelistirici

**MobilSoft** - Odoo Community Gelistiricisi | OCA Uyesi

- Website: [www.mobilsoft.net](https://www.mobilsoft.net)
- E-posta: info@mobilsoft.net
- Telefon: 0850 885 36 37

---

## Modul Listesi

### Turkiye Lokalizasyonu

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `l10n_tr_mobilsoft` | Turkiye Tek Duzen Hesap Plani | Aktif |
| `l10n_tr_bank_mobilsoft` | Turk Bankalari Listesi | Aktif |
| `l10n_tr_tax_office_mobilsoft` | Turkiye Vergi Daireleri | Aktif |
| `l10n_tr_city_mobilsoft` | Turkiye Il/Ilce Verileri | Aktif |

### On Muhasebe Entegrasyonlari

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_bizimhesap` | BizimHesap On Muhasebe Entegrasyonu | Aktif |

**BizimHesap Ozellikleri:**
- Cari hesap (musteri/tedarikci) senkronizasyonu
- Urun/hizmet senkronizasyonu
- Fatura senkronizasyonu (satis/alis)
- Cok sirketli yonlendirme (Joker Grubu / Joker Tedarik)
- VKN eslestirme ve duplike onleme
- Faturali/Faturasiz islem otomatik ayirimi

### e-Belge Entegrasyonlari

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_qnb_efatura` | QNB Finansbank e-Fatura/e-Arsiv/e-Irsaliye | Aktif |

**QNB e-Solutions Ozellikleri:**
- e-Fatura gonderimi (Temel/Ticari Fatura)
- e-Arsiv fatura gonderimi
- e-Irsaliye gonderimi
- Gelen belgeleri otomatik cekme
- Belge durumu otomatik kontrol
- Kontor uyari sistemi
- Musteri mukelleflik sorgulamasi

### Urun Yonetimi

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_xml_import` | XML Urun Ice Aktarma | Aktif |
| `mobilsoft_product_image_sync` | Urun Gorsel Senkronizasyonu | Aktif |
| `mobilsoft_consignment` | Konsinye Stok Yonetimi | Aktif |

**XML Import Ozellikleri:**
- URL veya dosya tabanli XML ice aktarma
- Esnek alan eslestirme sistemi
- Regex tabanli veri donusumu
- Otomatik zamanli ice aktarma
- Detayli ice aktarim loglari

### Banka Entegrasyonlari

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_bank_integration` | Turk Bankalari Open Banking API | Aktif |
| `mobilsoft_payment_paytr` | PayTR Odeme Entegrasyonu | Aktif |

### Muhasebe & Finans

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_chart_update` | Hesap Plani Guncelleme Sihirbazi | Aktif |
| `mobilsoft_chart_update_tr` | TR Hesap Plani Guncelleme | Aktif |
| `mobilsoft_onmuhasebe` | On Muhasebe Islemleri | Aktif |

### POS & Satis

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_pos_invoice` | POS Ozel Fatura Raporu | Aktif |

### Teknik Moduller

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_sequence_dynamic` | Dinamik Sira Numaralari | Aktif |
| `mobilsoft_api_services` | API Servisleri | Aktif |

---

## Mimari

### Cok Sirketli Yapi (Joker Grubu / Joker Tedarik)

```
+------------------+     +------------------+
|   Joker Grubu    |     |  Joker Tedarik   |
|   (Ana Sirket)   |     | (Ikincil Sirket) |
+------------------+     +------------------+
        |                        |
        v                        v
+------------------+     +------------------+
| Faturali Islemler|     |Faturasiz Islemler|
| (account.move)   |     |  (sale.order)    |
+------------------+     +------------------+
        |                        |
        +----------+-------------+
                   |
                   v
          +----------------+
          |  Ortak Depo    |
          +----------------+
```

### Entegrasyon Akisi

```
+-------------+       +-------------+       +-------------+
|  BizimHesap |<----->|    Odoo     |<----->| QNB e-Fatura|
+-------------+       +-------------+       +-------------+
      |                     |                     |
      v                     v                     v
  Cariler              Urunler               e-Fatura
  Urunler              Faturalar             e-Arsiv
  Faturalar            Stok                  e-Irsaliye
```

---

## Kurulum

### Docker ile Kurulum (Onerilen)

```bash
# Repoyu klonlayin
git clone https://github.com/JokerGrubu/joker-odoo.git
cd joker-odoo

# Docker compose ile baslatin
docker compose up -d
```

### Manuel Kurulum

1. Bu repoyu indirin
2. `custom-addons` klasorunu Odoo addons dizinine kopyalayin
3. `odoo.conf` dosyasina ekleyin:

```ini
addons_path = /odoo/addons,/path/to/custom-addons
```

4. Odoo'yu yeniden baslatin
5. Uygulamalar menusunden modulleri kurun

---

## Gereksinimler

### Sistem Gereksinimleri
- Odoo 19.0 Community veya Enterprise
- Python 3.10+
- PostgreSQL 14+ (pgvector onerilen)

### Python Bagimliliklari

```bash
pip install zeep lxml requests
```

### Docker Gereksinimleri
- Docker 20.10+
- Docker Compose 2.0+

---

## Yapilandirma

### BizimHesap Entegrasyonu

1. **Ayarlar > BizimHesap > Baglantılar** menusune gidin
2. API bilgilerini girin (URL, API Key)
3. Cok sirketli yonlendirme ayarlarini yapilandin
4. Senkronizasyonu baslatin

Detayli bilgi: [BizimHesap README](mobilsoft_bizimhesap/README.md)

### QNB e-Fatura Entegrasyonu

1. **Ayarlar > Sirketler** menusunden sirketinizi secin
2. QNB e-Solutions sekmesinde API bilgilerini girin
3. e-Fatura, e-Arsiv ve e-Irsaliye ayarlarini yapilandin
4. Cron job'lari aktif edin

Detayli bilgi: [QNB README](mobilsoft_qnb_efatura/README.md)

### XML Urun Ice Aktarma

1. **Stok > Yapilandirma > XML Kaynaklari** menusune gidin
2. XML kaynagi ve alan eslestirmelerini tanimlayın
3. Ice aktarimi baslatin

Detayli bilgi: [XML Import README](mobilsoft_xml_import/README.md)

---

## Guvenlik

### Kullanici Gruplari

| Modul | Grup | Yetkiler |
|-------|------|----------|
| BizimHesap | `group_bizimhesap_user` | Temel islemler |
| BizimHesap | `group_bizimhesap_manager` | Tam yetki |
| QNB | `group_qnb_user` | e-Fatura gonderimi |
| QNB | `group_qnb_manager` | Yapilandirma |

### Onerilen Guvenlik Ayarlari

- API anahtarlarini cevre degiskenlerinde saklayin
- Hassas verileri sifrelenmis baglantılarla aktarın
- Kullanici yetkilerini en az yetki prensibiyle verin

---

## Lisans

Bu moduller [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html) lisansi ile lisanslanmistir.

---

## Katkida Bulunma

1. Bu repoyu fork edin
2. Feature branch olusturun (`git checkout -b feature/YeniOzellik`)
3. Degisikliklerinizi commit edin (`git commit -m 'Yeni ozellik eklendi'`)
4. Branch'i push edin (`git push origin feature/YeniOzellik`)
5. Pull Request acin

---

## Destek

Teknik destek icin:
- E-posta: info@mobilsoft.net
- Telefon: 0850 885 36 37
- Website: [www.mobilsoft.net](https://www.mobilsoft.net)

---

## Degisiklik Gecmisi

### v19.0.1.0.0 (2026-01-30)
- BizimHesap entegrasyonu - Cok sirketli yonlendirme eklendi
- QNB e-Fatura entegrasyonu aktif edildi
- XML Import modulu guncellendi
- VKN normalizasyonu ve duplike onleme eklendi
- Modern UI guncellemeleri

---

*MobilSoft © 2026 - Tum haklari saklidir.*
