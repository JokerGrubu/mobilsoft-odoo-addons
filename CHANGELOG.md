# Degisiklik Gecmisi

Tum onemli degisiklikler bu dosyada belgelenmistir.

Format [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) standardini takip eder.

---

## [19.0.2.0.2] - 2026-02-13 (Modül Temizliği)

### Kaldırılanlar
- **11 kullanılmayan modül** kaldırıldı (uninstall + klasör silme):
  - `_disabled_mobilsoft_account_patch` — Bozuk (KeyError: tax_src_id), uninstallable
  - `mobilsoft_sequence_dynamic` — Odoo 16 versiyonu, Odoo 19 uyumsuz
  - `joker_enterprise_theme` — Kullanılmıyor
  - `mobilsoft_website_fix` — Kullanılmıyor
  - `mobilsoft_product_image_sync` — Kullanılmıyor
  - `mobilsoft_pos_invoice` — Kullanılmıyor
  - `mobilsoft_consignment` — Kullanılmıyor
  - `l10n_tr_bank_mobilsoft` — Banka verileri DB'de kaldı, modüle gerek yok
  - `l10n_tr_city_mobilsoft` — 973 ilçe verisi DB'de korundu (ir.model.data sahipliği __import__'a taşındı)
  - `l10n_tr_mobilsoft` — Hesap planı şablonu ve alanları kullanılmıyordu (0 kayıt)
  - `mobilsoft_chart_update` — Hesap planı güncelleme wizard'ı hiç kullanılmamıştı

---

## [19.0.2.0.1] - 2026-02-13 (mobilsoft_chart_update)

### Kaldırılanlar
- **mobilsoft_chart_update_tr** modülü kaldırıldı ve ana modülle birleştirildi.
  - TR modülü sadece `_prepare_fp_vals` metodunu override ediyordu ancak bu metot ana modülde mevcut değildi (ölü kod).
  - Modül uninstall edildi ve klasörü silindi.
  - Ana modül (`mobilsoft_chart_update`) değişiklik gerektirmedi.

---

## [19.0.2.0.0] - 2026-02-13 (mobilsoft_bank_integration)

### Eklenenler
- **Banka Entegrasyonu modülü** tamamen yeniden yazıldı — Odoo 19 ile %100 uyumlu.
- **Tek model mimarisi:** `bank.connector` modeli `bank_type` selection ile banka seçimi (abstract model kaldırıldı).
- **3 banka desteği:** Garanti BBVA, Ziraat Bankası, QNB Finansbank — tümü OAuth 2.0 ile.
- **Odoo standart entegrasyon:** İşlemler `account.bank.statement.line` üzerine yazılıyor (özel `bank.transaction` modeli kaldırıldı).
- **Mükerrer önleme:** `bank_import_ref` alanı ile UNIQUE constraint (`models.Constraint` — Odoo 19 formatı).
- **Döviz kuru senkronizasyonu:** Banka API'lerinden alınan kurlar `res.currency.rate` üzerine kaynak bilgisi ile yazılıyor.
- **Partner eşleştirme:** VKN → IBAN → İsim sırasıyla otomatik eşleştirme.
- **Senkronizasyon wizard'ı:** Tüm bankalar için toplu hesap/işlem/kur senkronizasyonu.
- **Güvenlik:** Kullanıcı/Yönetici grupları, çoklu şirket kuralı, ACL tanımları.
- **Cron:** Otomatik senkronizasyon (yapılandırılabilir aralık).

### Kaldırılanlar
- `bank.transaction` özel modeli (Odoo standart `account.bank.statement.line` kullanılıyor)
- `bank_account.py` (res.partner.bank extension sadeleştirildi)
- `currency_rate.py` (res_currency.py ile değiştirildi)
- `garantibbva_connector.py`, `ziraat_connector.py` (bank_connector_*.py ile değiştirildi)
- `demo/` klasörü
- `_sql_constraints` kullanımı (Odoo 19 `models.Constraint` ile değiştirildi)
- `category_id` res.groups referansı (Odoo 19'da `privilege_id` sistemi)

### Düzeltmeler
- `security.xml`: Odoo 19'da `res.groups` üzerinde `category_id` alanı kaldırıldı, `implied_ids` ile grup hiyerarşisi kuruldu.
- `account_bank_statement.py`: `_sql_constraints` → `models.Constraint` formatına dönüştürüldü.
- Search view: `expand` attribute kaldırıldı (Odoo 19 RNG şeması uyumsuzluğu).
- Manifest: Wizard view dosyası menü dosyasından önce yüklenmesi sağlandı (XML ID referans sıralaması).

---

## [19.0.1.25.0] - 2026-02-11 (petrol_bayilik_import)

### Düzeltmeler
- **İl/ilçe eşleştirme:** Excel'deki İl → state_id, İlçe → city/city_id doğru aktarılıyor. Türkçe karakter (İ/ı) farkları tolere edilir; ilike eşleşmezse normalized karşılaştırma yapılır.

---

## [19.0.1.24.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Düzeltmeler
- **street2'de ilçe:** İlçe bilgisi city alanına yazılır, adres 2. satırına (street2) yazılmaz. _apply_qnb_partner_data ve QNB XML parse'da street2=ilçe kontrolü eklendi; 100 mevcut partner'da street2 temizlendi.

---

## [19.0.2.7.0] - 2026-02-11 (mobilsoft_xml_import)

### Eklenenler
- ir_cron.xml: XML Import otomatik ürün senkronizasyonu için cron (saatte 1) — auto_sync açık kaynaklar artık otomatik çalışır.

---

## [19.0.1.18.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Degistirilenler
- **Nilvera cron:** Tüm şirketler ve ortak partnerler dahil (sudo) — partner bilgileri ortak kullanılıyor, firmalar ayrı. VKN (10 hane) ve TCKN (11 hane) desteklenir.
- **Batch script:** nilvera_unvan_tum_batch.py sudo ile tüm partnerleri kapsar.

---

## [19.0.1.2.0] - 2026-02-11 (l10n_tr_tax_office_mobilsoft)

### Düzeltmeler
- **VKN/TCKN onchange:** Partner şirketinde Nilvera API anahtarı yoksa, anahtarı olan şirket kullanılıyor. Böylece kontaklarda vergi kimlik no yazıldığında bilgiler otomatik gelir (Joker Tedarik vb. şirketlerde de).
- **city_id:** Nilvera'dan gelen ilçe, res.city ile eşleşirse city_id atanıyor.
- **l10n_tr_nilvera** bağımlılığı eklendi.

---

## [19.0.1.21.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Eklenenler
- **İlçe → res.city (city_id):** l10n_tr_city_mobilsoft ile 973 semt/ilçe kaydı varsa, ilçe adı res.city'de aranıp partner.city_id atanıyor. Böylece Semt/İlçe alanı doğru kayda bağlanıyor.

---

## [19.0.1.20.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Düzeltmeler
- **İl/İlçe doğru alanlara yazılıyor:** Odoo city=İlçe, state_id=İl. QNB XML sync'te normalizasyon (KARESİ/BALIKESİR ayrımı, street parse) artık for döngüsünden ÖNCE yapılıyor; böylece "KARESİ / BALIKESİR" gibi birleşik değerler city/state_id'e doğru ayrılıyor. Adres sonundan il/ilçe parse (örn: ... Gömeç balıkesir) eklendi.

---

## [19.0.1.17.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Düzeltmeler
- **Nilvera API anahtarı fallback:** Partner'ın şirketinde (örn. Joker Tedarik) Nilvera API anahtarı yoksa, anahtarı olan herhangi bir şirket kullanılıyor. Böylece Altınkılıçlar vb. Joker Tedarik partnerleri de Nilvera ünvan/bilgi güncellemesinden yararlanıyor.

---

## [19.0.1.16.0] - 2026-02-11 (mobilsoft_qnb_efatura, l10n_tr_tax_office_mobilsoft)

### Degistirilenler
- **mobilsoft_qnb_efatura:** Nilvera partner guncelleme: Nilvera sadece unvan dondurse bile, partner'da adres varsa street'ten il/ilce parse edilip city ve state_id doldurulur.
- **l10n_tr_tax_office_mobilsoft:** VKN onchange: Adres dolu ama City/District bos ise adres sonundan il/ilce parse edilir (ornek: ... Gomec balikesir). Il secildiginde ulke TR atanir.

---

## [19.0.1.15.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Eklenenler
- **Nilvera partner güncelleme cron** geri eklendi (`ir_cron_nilvera_update_partners`): VKN'ı olan carilerin adres/iletişim bilgilerini Nilvera GetGlobalCustomerInfo ile günceller (6 saatte bir). Önceki değişiklikte kaldırılmıştı.

---

## [19.0.1.14.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Degistirilenler
- "Simdi Cek" butonlari kaldirildi; gelen/giden belgeler tamamen otomatik (5 dakikada bir).
- Cron 15 dk -> 5 dk (ir_cron_data_update.xml ile mevcut kurulumlarda guncellenir).
- QNB ayar gorunurlugu: account.group_account_manager -> account.group_account_user (Muhasebeci yetkisi yeterli).

---

## [19.0.1.13.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Degistirilenler
- Giden belgeler "Simdi Cek" butonu (Ayarlar > QNB > Giden Belgeleri Otomatik Al): Son 7 gunu tarayarak giden e-fatura/e-Arsiv faturalarini manuel ceker.
- qnb_diagnostic.py: Giden bilgiler eklendi (son cekim giden, son 30 gun QNB giden sayisi, cron giden).

---

## [19.0.1.12.0] - 2026-02-11 (mobilsoft_qnb_efatura)

### Degistirilenler
- Gelen belgeler "Simdi Cek" butonu (Ayarlar > QNB): Son 7 gunu tarayarak gelen e-faturalari manuel ceker.
- qnb_diagnostic.py, qnb_manual_fetch.py (custom-addons/): Tani scriptleri.

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
