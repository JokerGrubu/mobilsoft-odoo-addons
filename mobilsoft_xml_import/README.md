# MobilSoft XML Urun Ice Aktarma

![Odoo Version](https://img.shields.io/badge/Odoo-19.0-blue)
![License](https://img.shields.io/badge/License-LGPL--3-green)

XML formatindaki urun verilerini Odoo'ya aktaran entegrasyon modulu.

## Ozellikler

### Temel Ozellikler
- URL veya dosya tabanli XML ice aktarma
- Esnek alan eslestirme sistemi
- Otomatik zamanli ice aktarma
- Detayli ice aktarim loglari
- Regex tabanli veri donusumu

### Alan Eslestirme
- Odoo alanlari ile XML yollarini eslestirme
- Ic ice XML elementleri destegi (`Category/Name`)
- XML attribute destegi (`@id`)
- Dizi elemanlari destegi (`Images/Image[1]`)
- Varsayilan deger tanimlama
- Zorunlu alan kontrolu

### Donusum Secenekleri
- Buyuk harf donusumu
- Kucuk harf donusumu
- Baslik donusumu (ilk harfler buyuk)
- Regex ile ozel donusum

## Kurulum

1. Modulu `custom-addons` klasorune kopyalayin
2. Odoo'yu yeniden baslatin
3. Uygulamalar menusunden "XML Urun Ice Aktarma" modulu kurun

## Yapilandirma

### 1. XML Kaynagi Olusturma

1. **Stok > Yapilandirma > XML Kaynaklari** menusune gidin
2. "Olustur" butonuna tiklayin
3. Kaynak bilgilerini girin:
   - **Ad**: Kaynak icin tanitici isim
   - **URL**: XML dosyasinin web adresi
   - **Urun Xpath**: Urun elementlerinin yolu (ornek: `//Product`)
   - **Urun Eslestirme Alani**: Mevcut urunlerle eslestirme alani

### 2. Alan Eslestirmeleri

1. "Alan Eslestirmeleri" sekmesinde yeni satirlar ekleyin
2. Her satir icin:
   - **Odoo Alani**: Hedef alan (ornek: `default_code`, `name`, `list_price`)
   - **XML Yolu**: Kaynak XML yolu (ornek: `ProductCode`, `ProductName`)
   - **Donusum**: Uygulanacak donusum tipi
   - **Varsayilan Deger**: XML'de bulunmazsa kullanilacak deger
   - **Zorunlu**: Alan bos birakılamazsa isaretleyin

### XML Yolu Ornekleri

| XML Yolu | Aciklama |
|----------|----------|
| `ProductCode` | Dogrudan element |
| `Category/Name` | Ic ice element |
| `@id` | Attribute degeri |
| `Images/Image[1]` | Ilk dizi elementi |

### 3. Otomatik Ice Aktarma

1. "Otomatik Ice Aktar" secenegini isaretleyin
2. Ice aktarim aralıgını belirleyin (saat cinsinden)

## Kullanim

### Manuel Ice Aktarma

1. XML kaynagi kaydina gidin
2. "Ice Aktar" butonuna tiklayin
3. Ice aktarim tamamlandiginda sonuclari gorun

### Ice Aktarim Loglari

1. Kaynak kaydindaki "Loglar" butonuna tiklayin
2. Her ice aktarim icin:
   - Toplam urun sayisi
   - Olusturulan urun sayisi
   - Guncellenen urun sayisi
   - Atlanan urun sayisi
   - Hatali urunler ve nedenleri

## Ornek XML Yapisi

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Products>
  <Product>
    <ProductCode>URUN001</ProductCode>
    <ProductName>Ornek Urun</ProductName>
    <Description>Urun aciklamasi</Description>
    <Price>199.99</Price>
    <Category>
      <Name>Elektronik</Name>
    </Category>
    <Images>
      <Image>https://example.com/image1.jpg</Image>
    </Images>
  </Product>
</Products>
```

## Alan Eslestirme Ornegi

| Odoo Alani | XML Yolu | Donusum |
|------------|----------|---------|
| `default_code` | `ProductCode` | Yok |
| `name` | `ProductName` | Baslik |
| `description` | `Description` | Yok |
| `list_price` | `Price` | Yok |
| `categ_id` | `Category/Name` | Yok |
| `image_1920` | `Images/Image[1]` | Yok |

## Teknik Detaylar

### Model Yapisi

| Model | Aciklama |
|-------|----------|
| `xml.product.source` | XML kaynak ayarlari |
| `xml.field.mapping` | Alan eslestirme kayitlari |
| `xml.import.log` | Ice aktarim loglari |

## Sorun Giderme

### XML Okunamiyor

1. URL'nin erisilebilir oldugunu kontrol edin
2. XML formatinin gecerli oldugunu dogrulayin
3. Encoding'in dogru oldugunu kontrol edin (UTF-8 onerılir)

### Alan Eslestirme Calısmiyor

1. XML yolunun dogru oldugunu kontrol edin
2. Element isimlerinin buyuk/kucuk harf duyarli oldugunu unutmayin
3. Ic ice elementler icin tam yol belirtin

## Lisans

LGPL-3

## Destek

- Email: info@mobilsoft.net
- Tel: 0850 885 36 37
- Web: https://www.mobilsoft.net

---

*MobilSoft © 2026*
