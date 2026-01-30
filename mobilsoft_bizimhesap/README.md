# MobilSoft BizimHesap Entegrasyonu

![Odoo Version](https://img.shields.io/badge/Odoo-19.0-blue)
![License](https://img.shields.io/badge/License-LGPL--3-green)

BizimHesap on muhasebe uygulamasi ile Odoo arasinda cift yonlu veri senkronizasyonu saglayan entegrasyon modulu.

## Ozellikler

### Temel Ozellikler
- Cari hesap (musteri/tedarikci) senkronizasyonu
- Urun/hizmet senkronizasyonu
- Fatura senkronizasyonu (satis/alis)
- Tahsilat/odeme senkronizasyonu
- Otomatik zamanli senkronizasyon
- Manuel senkronizasyon
- Detayli loglama

### Cok Sirketli Yonlendirme (Joker Grubu / Joker Tedarik)
- Faturali islemler Ana Sirkete (account.move)
- Faturasiz islemler Ikincil Sirkete (sale.order)
- VKN'siz musterileri otomatik yonlendirme
- Vergiden muaf musterileri yonlendirme
- Hic faturasi olmayan musterileri yonlendirme

### VKN Eslestirme ve Duplike Onleme
- TR prefix normalizasyonu (TR1234567890 -> 1234567890)
- Leading zero normalizasyonu (0012345678 -> 12345678)
- Telefon, email ve isim ile ikincil eslestirme
- Benzerlik skoru ile akilli eslestirme

## Kurulum

### Bagimliliklar

```bash
pip install requests
```

### Odoo Kurulumu

1. Modulu `custom-addons` klasorune kopyalayin
2. Odoo'yu yeniden baslatin
3. Uygulamalar menusunden "BizimHesap Entegrasyonu" modulu kurun

## Yapilandirma

### 1. BizimHesap Baglantisi Olusturma

1. **Ayarlar > BizimHesap > Baglantılar** menusune gidin
2. "Olustur" butonuna tiklayin
3. API bilgilerini girin:
   - **API URL**: `https://bizimhesap.com/api/b2b`
   - **API Key**: BizimHesap panelinizden alinacak API anahtari
4. "Baglantiyi Test Et" butonuna tiklayin

### 2. Cok Sirketli Yonlendirme (Opsiyonel)

Eger faturali ve faturasiz islemleri farkli sirketlerde takip etmek istiyorsaniz:

1. "Cok Sirketli Yonlendirme" sekmesine gidin
2. "Cok Sirketli Yonlendirmeyi Aktifestir" secenegini isaretleyin
3. Asagidaki ayarlari yapilandin:
   - **Ikincil Sirket**: Faturasiz islemlerin gidecegi sirket
   - **Ortak Depo**: Her iki sirketin kullanacagi depo
   - **Faturasiz Islem Tespit Kurali**:
     - `Her Ikisi (Onerilen)`: Fatura no bos VE KDV = 0
     - `Herhangi Biri`: Fatura no bos VEYA KDV = 0
     - `Fatura No Bos`: Sadece fatura numarasi kontrolu
     - `KDV Yok`: Sadece KDV tutari kontrolu

4. Musteri Yonlendirme Kurallari:
   - **VKN'siz Musterileri Yonlendir**: VKN'si olmayan musteriler
   - **Vergiden Muaf Musterileri Yonlendir**: Muafiyet isaretli musteriler
   - **Hic Faturasi Olmayanlari Yonlendir**: Sistemde faturasi bulunmayanlar

### 3. Senkronizasyon Ayarlari

1. "Senkronizasyon" sekmesinde:
   - Senkronize edilecek veri tiplerini secin (Cariler, Urunler, Faturalar, Odemeler)
   - Senkronizasyon yonunu belirleyin (BH -> Odoo, Odoo -> BH, Cift Yonlu)
   - Otomatik senkronizasyon icin "Otomatik Sync" secenegini aktifestirin

## Kullanim

### Manuel Senkronizasyon

1. BizimHesap baglanti kaydina gidin
2. Ust menuden istediginiz senkronizasyon butonuna tiklayin:
   - **Carileri Sync**: Musteri/tedarikci senkronizasyonu
   - **Urunleri Sync**: Urun/hizmet senkronizasyonu
   - **Faturalari Sync**: Fatura senkronizasyonu
   - **Tumunu Senkronize Et**: Tum verileri senkronize et

### Senkronizasyon Loglari

1. Baglanti kaydindaki "Loglar" butonuna tiklayin
2. Her senkronizasyon islemi icin detayli bilgi goruntuleyin:
   - Toplam islem sayisi
   - Olusturulan kayit sayisi
   - Guncellenen kayit sayisi
   - Atlanan kayit sayisi
   - Hatali kayit sayisi ve detaylari

### Cari Hesaplarda BizimHesap Bilgileri

1. Herhangi bir musteri/tedarikci kaydini acin
2. "BizimHesap" sekmesinde:
   - Cari bakiye bilgileri
   - Senkronizasyon durumu
   - Eslestirme kayitlari

## Teknik Detaylar

### Model Yapisi

| Model | Aciklama |
|-------|----------|
| `bizimhesap.backend` | API baglanti ayarlari |
| `bizimhesap.sync.log` | Senkronizasyon loglari |
| `bizimhesap.partner.binding` | Cari eslestirme kayitlari |
| `bizimhesap.product.binding` | Urun eslestirme kayitlari |
| `bizimhesap.invoice.binding` | Fatura eslestirme kayitlari |

### API Endpointleri

| Endpoint | Aciklama |
|----------|----------|
| `/Contacts/GetAll` | Tum carileri getir |
| `/Products/GetAll` | Tum urunleri getir |
| `/Invoices/GetAll` | Tum faturalari getir |
| `/Categories/GetAll` | Tum kategorileri getir |
| `/Warehouses/GetAll` | Tum depolari getir |

### VKN Normalizasyon Algoritmasi

```python
def normalize_vat(vat):
    # 1. TR prefix'i kaldir
    if vat.startswith('TR'):
        vat = vat[2:]

    # 2. Sadece rakamlari al
    vat = re.sub(r'\D', '', vat)

    # 3. Leading zeros kaldir
    vat = vat.lstrip('0') or '0'

    return vat
```

## Sorun Giderme

### Baglanti Hatasi

1. API URL'sinin dogru oldugundan emin olun
2. API Key'in gecerli oldugunu kontrol edin
3. Internet baglantinizi kontrol edin

### Duplike Kayitlar

Bu modül VKN normalizasyonu ile duplike kayıtları önler. Eger yine de duplike oluşuyorsa:
1. Mevcut eslestirmeleri kontrol edin
2. VKN formatlarini kontrol edin

### Senkronizasyon Hatalari

Senkronizasyon loglarinda hata detaylarini inceleyin:
1. BizimHesap > Loglar menusune gidin
2. "Hatali" filtresini secin
3. Hata detaylarini okuyun

## Guvenlik Gruplari

| Grup | Yetkiler |
|------|----------|
| `group_bizimhesap_user` | Temel kullanici yetkileri |
| `group_bizimhesap_manager` | Tam yetki |

## Lisans

LGPL-3

## Destek

- Email: info@mobilsoft.net
- Tel: 0850 885 36 37
- Web: https://www.mobilsoft.net

---

*MobilSoft © 2026*
