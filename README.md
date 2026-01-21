# MobilSoft Odoo 19 Modülleri

![Odoo Version](https://img.shields.io/badge/Odoo-19.0-blue)
![License](https://img.shields.io/badge/License-LGPL--3-green)
![MobilSoft](https://img.shields.io/badge/MobilSoft-OCA%20Üyesi-orange)

Türkiye için Odoo 19 Community modülleri. Herhangi bir Odoo 19 kurulumuna eklenebilir.

## 🏢 Geliştirici

**MobilSoft** - Odoo Community Geliştiricisi | OCA Üyesi

- 🌐 Website: [www.mobilsoft.net](https://www.mobilsoft.net)
- 📧 E-posta: info@mobilsoft.net
- 📞 Telefon: 0850 885 36 37

---

## 📦 Modül Listesi

### Türkiye Lokalizasyonu

| Modül | Açıklama |
|-------|----------|
| `l10n_tr_mobilsoft` | Türkiye Tek Düzen Hesap Planı |
| `l10n_tr_bank_mobilsoft` | Türk Bankaları Listesi |
| `l10n_tr_tax_office_mobilsoft` | Türkiye Vergi Daireleri |
| `l10n_tr_city_mobilsoft` | Türkiye İl/İlçe Verileri |

### e-Belge Entegrasyonları

| Modül | Açıklama |
|-------|----------|
| `mobilsoft_qnb_efatura` | QNB Finansbank e-Fatura/e-Arşiv |

### Banka Entegrasyonları

| Modül | Açıklama |
|-------|----------|
| `mobilsoft_bank_integration` | Türk Bankaları Open Banking API |
| `mobilsoft_payment_paytr` | PayTR Ödeme Entegrasyonu |

### Muhasebe & Finans

| Modül | Açıklama |
|-------|----------|
| `mobilsoft_chart_update` | Hesap Planı Güncelleme Sihirbazı |
| `mobilsoft_chart_update_tr` | TR Hesap Planı Güncelleme |
| `mobilsoft_account_patch` | Muhasebe Düzeltmeleri |
| `mobilsoft_bizimhesap` | BizimHesap Entegrasyonu |

### Stok & Ürün Yönetimi

| Modül | Açıklama |
|-------|----------|
| `mobilsoft_consignment` | Konsinye Stok Yönetimi |
| `mobilsoft_xml_import` | XML Ürün İçe Aktarma |
| `mobilsoft_product_image_sync` | Ürün Görsel Senkronizasyonu |

### POS & Satış

| Modül | Açıklama |
|-------|----------|
| `mobilsoft_pos_invoice` | POS Özel Fatura Raporu |

### Teknik Modüller

| Modül | Açıklama |
|-------|----------|
| `mobilsoft_sequence_dynamic` | Dinamik Sıra Numaraları |
| `mobilsoft_api_services` | API Servisleri |

---

## 🚀 Kurulum

### Yöntem 1: Git Clone (Önerilen)

```bash
cd /your/odoo/path
git clone https://github.com/JokerGrubu/mobilsoft-odoo-addons.git custom-addons/mobilsoft
```

Ardından `odoo.conf` dosyasına ekleyin:
```ini
addons_path = /odoo/addons,/odoo/custom-addons/mobilsoft
```

### Yöntem 2: Manuel Kopyalama

1. Bu repoyu indirin
2. İstediğiniz modülleri Odoo addons klasörüne kopyalayın
3. Odoo'yu yeniden başlatın
4. Uygulamalar menüsünden modülü kurun

---

## ⚙️ Gereksinimler

- Odoo 19.0 Community veya Enterprise
- Python 3.10+
- PostgreSQL 14+

### Python Bağımlılıkları

```bash
pip install zeep lxml requests
```

---

## 📄 Lisans

Bu modüller [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html) lisansı ile lisanslanmıştır.

---

## 🤝 Katkıda Bulunma

1. Bu repoyu fork edin
2. Feature branch oluşturun (`git checkout -b feature/YeniOzellik`)
3. Değişikliklerinizi commit edin (`git commit -m 'Yeni özellik eklendi'`)
4. Branch'i push edin (`git push origin feature/YeniOzellik`)
5. Pull Request açın

---

## 📞 Destek

Teknik destek için:
- 📧 info@mobilsoft.net
- 📞 0850 885 36 37
- 🌐 [www.mobilsoft.net](https://www.mobilsoft.net)

---

*MobilSoft © 2026 - Tüm hakları saklıdır.*
