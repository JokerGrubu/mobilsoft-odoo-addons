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
| `l10n_tr_tax_office_mobilsoft` | Turkiye Vergi Daireleri | Aktif |

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

### Pazaryeri Entegrasyonlari

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_marketplace_core` | Pazaryeri Temel Altyapisi | Aktif |
| `mobilsoft_marketplace_trendyol` | Trendyol Connector | Aktif |
| `mobilsoft_marketplace_hepsiburada` | Hepsiburada Connector | Aktif |
| `mobilsoft_marketplace_n11` | N11 Connector | Aktif |
| `mobilsoft_marketplace_cicek_sepeti` | Cicek Sepeti Connector | Aktif |

**Pazaryeri Ozellikleri:**
- Coklu kanal yonetimi (Trendyol, Hepsiburada, N11, Cicek Sepeti)
- Siparis senkronizasyonu (pending → confirmed → shipped → delivered)
- Urun listeleme ve stok guncelleme
- Kanban ve list gorunumleri
- Detayli senkronizasyon loglari

### Q-Commerce (Hizli Teslimat) Entegrasyonlari

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_qcommerce_core` | Q-Commerce Temel Altyapisi | Aktif |
| `mobilsoft_qcommerce_getir` | Getir Connector | Aktif |
| `mobilsoft_qcommerce_yemeksepeti` | Yemeksepeti Connector | Aktif |
| `mobilsoft_qcommerce_vigo` | Vigo Connector | Aktif |

**Q-Commerce Ozellikleri:**
- Hizli teslimat platformlari (Getir, Yemeksepeti, Vigo)
- Siparis durumu takibi (pending → preparing → ready → on_way → delivered)
- Teslimat takibi (kurye, sure, konum)
- Kanban board ile gorsel siparis yonetimi
- Statusbar ile siparis akisi

### Birlestik Dashboard

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_dashboard` | Pazaryeri & Q-Commerce Analitik Dashboard | Aktif |

**Dashboard Ozellikleri:**
- Unified KPI kartlari (toplam siparis, beklemede, basari orani)
- Platform karsilastirma (Pazaryeri vs Q-Commerce)
- Channel istatistik tablolari
- Senkronizasyon durumu takibi
- Siparis tutar ozeti

### Urun Yonetimi

| Modul | Aciklama | Durum |
|-------|----------|-------|
| `mobilsoft_xml_import` | XML Urun Ice Aktarma | Aktif |

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
|  BizimHesap |<----->|             |<----->| QNB e-Fatura|
+-------------+       |             |       +-------------+
                       |    Odoo     |
+-------------+       |             |       +-------------+
|  Pazaryeri  |<----->|  Dashboard  |<----->| Q-Commerce  |
| Trendyol    |       |             |       | Getir       |
| Hepsiburada |       +-------------+       | Yemeksepeti |
| N11         |            |                | Vigo        |
| Cicek Sepeti|            v                +-------------+
+-------------+     +-------------+
                    | XML Import  |
                    | Banka API   |
                    +-------------+
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

### v19.0.3.0.0 (2026-02-15)
- 10 yeni modul: Pazaryeri (5), Q-Commerce (4), Dashboard (1)
- Tum moduller Odoo 19 uyumlu (tree→list, states→invisible, kanban-box→card)

### v19.0.2.0.2 (2026-02-13)
- 11 kullanilmayan modul kaldirildi
- mobilsoft_bank_integration Odoo 19 uyumlu yeniden yazildi

### v19.0.1.0.0 (2026-01-30)
- BizimHesap entegrasyonu - Cok sirketli yonlendirme eklendi
- QNB e-Fatura entegrasyonu aktif edildi
- XML Import modulu guncellendi
- VKN normalizasyonu ve duplike onleme eklendi
- Modern UI guncellemeleri

---

*MobilSoft © 2026 - Tum haklari saklidir.*
