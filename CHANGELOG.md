# Degisiklik Gecmisi

Tum onemli degisiklikler bu dosyada belgelenmistir.

Format [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) standardini takip eder.

---

## [19.0.1.11.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Duzeltmeler
- action_view_invoice: move_id yoksa uyari doner (AttributeError oncesi).
- qnb_document: sanitize_account_number lazy import (modul yukleme hatasi riski azaltildi).

---

## [19.0.1.10.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Degistirilenler

#### UI ve modul duzenlemesi
- qnb_match_product_by kaldirildi (kullanilmiyordu).
- Config view: Urun eslestirme sadece "Yeni urun olustur" checkbox (Odoo standart sira aciklamasi).
- account_move._qnb_find_or_create_product_from_line: _retrieve_product kullanir (tedarikci kodu oncelikli).

---

## [19.0.1.9.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Degistirilenler

#### Partner eslestirme = Odoo standart _retrieve_partner
- res_partner_inherit.match_or_create_from_external: Odoo standart _retrieve_partner kullanir (vat, phone, email, name).
- account_move._qnb_find_or_create_partner_from_data: _retrieve_partner ile arama (match_by: vat/name/both).
- Banka hesabi eslestirme: sanitize_account_number + sanitized_acc_number (Odoo standart).
- _vat_normalize kaldirildi.

---

## [19.0.1.0.4] - 2026-02-11 (mobilsoft_bizimhesap)

### Degistirilenler

#### Partner import = Odoo standart oncelik
- _import_partner: Once Odoo standart _retrieve_partner (vat, phone, email, name, ref).
- Bulunamazsa SyncProtocols (branch/similar) fallback.

---

## [19.0.2.6.0] - 2026-02-11 (mobilsoft_xml_import)

### Degistirilenler
- _find_existing_product: Oncelikle Odoo standart _retrieve_product kullanir.
- Product Enrichment Import Wizard: _retrieve_product ile eslestirir.
- account dependency eklendi (_retrieve_product icin).

---

## [19.0.1.0.3] - 2026-02-11 (mobilsoft_bizimhesap)

### Degistirilenler
- _import_invoice_line_from_data: _retrieve_product ile urun eslestirir.
- _import_product: Oncelikle _retrieve_product; bulunamazsa SyncProtocols fallback.

---

## [19.0.1.8.0] - 2026-02-11

### Degistirilenler

#### QNB urun eslestirme = Nilvera/UBL standart
- product_product.match_or_create_from_external kaldirildi.
- qnb_document_line: Odoo standart _retrieve_product kullanir (barkod, default_code, name).
- Yeni urun olusturmaz; eslesmezse uyari verir.

---

## [19.0.1.7.0] - 2026-02-11

### Degistirilenler

#### QNB gelen belgeler = Nilvera ile ayni UBL import
- Gelen e-belgeler artik Odoo standart UBL import akisini kullaniyor (`account.edi.xml.ubl.tr`).
- Manuel partner/urun eslestirme (qnb_find_or_create_*) kaldirildi; Nilvera ile ayni `_create_document_from_attachment` akisi.
- Partner/urun eslestirmesi Odoo standart `_import_partner` ve UBL `_import_fill_invoice` ile yapilir.
- Hata durumunda Nilvera gibi bos fatura + attachment olusturulur.

---

## [19.0.1.6.0] - 2026-02-11

### Degistirilenler

#### Gelen belge eslestirme kurallari
- **qnb_create_new_partner** ve **qnb_create_new_product** varsayilan True: Eslesmeyen partner/urun icin yenisi olusturulur.
- Config ekrani: "Gelen Belge Eslestirme" blogu eklendi (Partner/Urun eslestirme kriteri ve yeni olusturma secenekleri).
- Yeni partner olusturulurken: adres (street, city, zip), ulke, il, vergi dairesi XML'den doldurulur.
- Yeni urun olusturulurken: purchase_ok=True (alis faturasi icin), supplierinfo tedarikci kodu ile eklenir.

---

## [19.0.1.5.0] - 2026-02-11

### Degistirilenler

#### Otomatik e-belge cekimi (15 dakikada bir)
- **QNB:** Gelen belgeler, giden PDF'ler ve belge durumu cron'lari 12 saatten 15 dakikaya indirildi.
- **Nilvera:** Gelen/giden belge ve durum cron'lari 15 dakikada bir calisacak sekilde guncellendi (mobilsoft_qnb_efatura uzerinden override).
- **qnb_auto_fetch_outgoing:** Varsayilan True yapildi; giden belgeler de otomatik cekilir.

Yeni belge geldiginde veya gittiginde en gec 15 dakika icinde Odoo'ya alinir.

---

## [19.0.1.4.0] - 2026-02-11

### Degistirilenler

#### Nilvera Tek Kaynak (QNB/GIB partner guncelleme kaldirildi)
- **l10n_tr_tax_office_mobilsoft:** VKN/TCKN girip Enter veya Tab ile Nilvera API (GetGlobalCustomerInfo) cagriliyor; cari alanlari (adres, il, ilce, vergi dairesi, telefon, e-posta, web sitesi) otomatik dolduruluyor.
- **mobilsoft_qnb_efatura:** QNB ve GIB ile cari guncelleme kaldirildi: wizard, toplu kontrol, config butonlari, partner cron'lari silindi. Cariler artik sadece Nilvera (VKN onchange) ile otomatik doldurulur.

#### UI Temizlik
- Cari form: "Nilvera'dan Sorgula", "e-Fatura Durumunu Kontrol Et" butonlari ve qnb_last_check_date alani kaldirildi.
- Konfigurasyon: Veri duzeltme blogu (Carileri Nilvera ile Guncelle, VAT Eksik, Carileri GIB ile Guncelle) kaldirildi.

#### QNB e-Belge Ekrani
- qnb_document_views.xml manifeste eklendi (onceden yuklenmiyordu).
- "Faturayi Goruntule" butonu action_view_invoice ile duzeltildi.
- qnb_wizard_views.xml manifeste eklendi (send invoice, reject, credit info wizard'lari).

### Silinenler
- qnb_check_partner_wizard, qnb_batch_check_wizard
- ir_cron_qnb_check_partners, ir_cron_qnb_update_partners_mukellef

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
