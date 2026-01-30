# MobilSoft QNB e-Fatura/e-Arsiv Entegrasyonu

![Odoo Version](https://img.shields.io/badge/Odoo-19.0-blue)
![License](https://img.shields.io/badge/License-LGPL--3-green)

QNB Finansbank e-Solutions platformu ile Odoo arasinda e-Fatura, e-Arsiv ve e-Irsaliye entegrasyonu.

## Ozellikler

### e-Fatura
- Temel Fatura ve Ticari Fatura senaryolari
- Otomatik fatura numaralama (seri oneki destegi)
- GIB onayı takibi
- PDF ve XML gorsellestirme

### e-Arsiv
- Kagit ve Elektronik gonderim tipleri
- Otomatik fatura numaralama
- PDF olusturma

### e-Irsaliye
- Sevk irsaliyesi gonderimi
- Durum takibi

### Genel Ozellikler
- Test ve canli ortam destegi
- Gelen belgeleri otomatik cekme
- Giden belge durumlarini otomatik kontrol
- Kontor uyari sistemi
- Musteri e-Fatura mukelleflik kontrolu

## Kurulum

### Bagimliliklar

```bash
pip install zeep lxml
```

### Odoo Kurulumu

1. Modulu `custom-addons` klasorune kopyalayin
2. Odoo'yu yeniden baslatin
3. Uygulamalar menusunden "QNB e-Fatura/e-Arsiv" modulu kurun

## Yapilandirma

### 1. Sirket Ayarlari

1. **Ayarlar > Sirketler** menusune gidin
2. Sirketinizi secin
3. "QNB e-Solutions" sekmesinde:

#### API Ayarlari
- **QNB e-Solutions Aktif**: Entegrasyonu etkinlestirin
- **QNB Ortam**: Test veya Canli ortam secin
- **Kullanici Adi**: QNB'den alinan kullanici adi
- **Sifre**: QNB API sifresi

#### e-Fatura Ayarlari
- **e-Fatura Aktif**: e-Fatura gonderimini etkinlestirin
- **e-Fatura Senaryosu**: TEMELFATURA veya TICARIFATURA
- **Seri Oneki**: Fatura numarasi oneki (ornek: EF)

#### e-Arsiv Ayarlari
- **e-Arsiv Aktif**: e-Arsiv gonderimini etkinlestirin
- **Seri Oneki**: e-Arsiv fatura oneki (ornek: EA)
- **Gonderim Tipi**: KAGIT veya ELEKTRONIK

#### e-Irsaliye Ayarlari
- **e-Irsaliye Aktif**: e-Irsaliye gonderimini etkinlestirin
- **Seri Oneki**: Irsaliye numarasi oneki (ornek: IR)

#### Otomatik Islemler
- **Gelen Belgeleri Otomatik Al**: Gelen e-faturalar otomatik indirilir
- **Durumu Otomatik Kontrol Et**: Gonderilen belgelerin durumu kontrol edilir

### 2. GIB Etiketleri

- **GIB Etiket (Posta Kutusu)**: e-Fatura posta kutusu etiketi
- **Gonderici Etiketi**: Varsayilan gonderici etiketi

## Kullanim

### e-Fatura Gonderimi

1. Bir satis faturasi olusturun ve onaylayin
2. Fatura formunda "e-Fatura Gonder" butonuna tiklayin
3. Gonderim tamamlandiginda QNB referans numarasini gorun

### e-Arsiv Gonderimi

1. e-Fatura mukellefı olmayan musteriler icin fatura olusturun
2. "e-Arsiv Gonder" butonuna tiklayin
3. PDF belgeyi indirin

### Musteri e-Fatura Kontrolu

1. Musteri kaydinda "e-Fatura Mukelleflik Kontrolu" butonuna tiklayin
2. Sistemden VKN/TCKN ile mukelleflik sorgulamasi yapin
3. Musteri e-Fatura mukellefi ise bilgiler otomatik kaydedilir

### Kontor Durumu

1. Sirket ayarlarinda "Kontor Durumu" butonuna tiklayin
2. Mevcut kontor bakiyelerini gorun:
   - e-Fatura kontoru
   - e-Arsiv kontoru
   - e-Irsaliye kontoru

### Gelen Belgeler

1. **Muhasebe > QNB > Gelen Belgeler** menusune gidin
2. Gelen e-Faturalari gorun
3. Kabul veya Red islemi yapin (Ticari Fatura icin)

## Cron Isleri

| Cron | Varsayilan | Aciklama |
|------|------------|----------|
| Gelen Belgeleri Cek | 1 saat | Gelen e-faturaları indirir |
| Giden Belgeleri Cek | 1 saat | Giden belgelerin PDF/XML'ini indirir |
| Belge Durumlarini Kontrol Et | 30 dk | GIB onay durumunu kontrol eder |
| Musteri Mukellefilik Guncelle | 1 gun | Musteri e-Fatura durumlarini gunceller |
| Kontor Uyari Kontrolu | 1 gun | Dusuk kontor uyarisi gonderir |

## Teknik Detaylar

### Model Yapisi

| Model | Aciklama |
|-------|----------|
| `qnb.api.client` | SOAP API istemcisi |
| `qnb.document` | Gelen/giden belgeler |
| `qnb.document.line` | Belge satirlari |

### WSDL Endpointleri

| Ortam | URL |
|-------|-----|
| Test1 | https://erpefaturatest1.qnbesolutions.com.tr/efatura/ws/connectorService?wsdl |
| Test2 | https://erpefaturatest2.qnbesolutions.com.tr/efatura/ws/connectorService?wsdl |
| Canli | https://connector.qnbefinans.com/connector/ws/connectorService?wsdl |

## Sorun Giderme

### Baglanti Hatasi

1. Kullanici adi ve sifrenin dogru oldugunu kontrol edin
2. Ortam ayarinin (Test/Canli) dogru oldugunu dogrulayin
3. Zeep kutuphanesinin kurulu oldugunu kontrol edin

### Fatura Gonderilemedi

1. Musteri VKN/TCKN bilgisinin dogru oldugunu kontrol edin
2. Musterinin e-Fatura mukellefı olup olmadigını dogrulayin
3. Fatura tutarlarinin dogru oldugunu kontrol edin

### GIB Reddi

1. Red nedenini log kayitlarindan okuyun
2. Fatura bilgilerini duzeltin
3. Yeniden gonderin

## Lisans

LGPL-3

## Destek

- Email: info@mobilsoft.net
- Tel: 0850 885 36 37
- Web: https://www.mobilsoft.net

---

*MobilSoft © 2026*
