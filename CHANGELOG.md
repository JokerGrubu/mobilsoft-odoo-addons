# Degisiklik Gecmisi

Tum onemli degisiklikler bu dosyada belgelenmistir.

Format [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) standardini takip eder.

---

## [19.0.1.0.0] - 2026-01-30

### Eklenenler

#### BizimHesap Entegrasyonu
- Cok sirketli yonlendirme ozelligi (Joker Grubu / Joker Tedarik)
- Faturali islemler Ana Sirkete (account.move olarak)
- Faturasiz islemler Ikincil Sirkete (sale.order olarak)
- VKN normalizasyonu (TR prefix ve leading zeros)
- Duplike kayit onleme sistemi
- Akilli musteri eslestirme (VKN > Telefon > Email > Isim benzerlik)
- Modern Kanban ve List view'lar
- Detayli senkronizasyon loglari

#### QNB e-Fatura Entegrasyonu
- e-Fatura gonderimi (Temel/Ticari Fatura senaryolari)
- e-Arsiv fatura gonderimi
- e-Irsaliye gonderimi
- Otomatik gelen belge cekme
- Otomatik belge durumu kontrolu
- Kontor uyari sistemi
- Musteri e-Fatura mukelleflik sorgulamasi

#### XML Urun Ice Aktarma
- URL ve dosya tabanli XML destegi
- Esnek alan eslestirme sistemi
- Regex tabanli veri donusumu
- Otomatik zamanli ice aktarma
- Detayli ice aktarim loglari

### Degistirilenler
- Tum modullerde modern UI guncellemeleri
- Boolean alanlar icin toggle widget kullanimi
- Datetime alanlari icin widget eklendi
- Card component'ler ile yardim metinleri

### Duzeltmeler
- VKN format uyumsuzlugu giderildi (0 eslestirme sorunu)
- 'mobile' field hatasi duzeltildi (Odoo 19 uyumlulugu)
- Search view hatalari duzeltildi

---

## [19.0.0.1.0] - 2026-01-28

### Eklenenler
- Ilk BizimHesap entegrasyon modulu
- Temel cari ve urun senkronizasyonu
- QNB e-Fatura modulu
- XML Import modulu

---

## [19.0.0.0.1] - 2026-01-19

### Eklenenler
- Proje baslangici
- Turkiye lokalizasyon modulleri
- Temel altyapi

---

*MobilSoft © 2026*
