# POS Custom Invoice Report

## English

### Overview
The **POS Custom Invoice Report** module extends the functionality of Point of Sale in Odoo by allowing custom invoice report templates for each POS configuration. This module enables users to define specific invoice report templates for different POS locations or configurations, providing flexibility in invoice presentation and branding.

### Features

- **Custom Report Selection**: Configure a specific invoice report template for each POS configuration
- **Dynamic Report Assignment**: Automatically uses the configured report when generating invoices from POS orders
- **Easy Configuration**: User-friendly interface integrated into POS settings
- **Flexible Filtering**: Only invoice-compatible reports are available for selection
- **Fallback Support**: If no custom report is configured, the system uses the default invoice report

### Installation

1. Download or clone the module files into your Odoo addons directory
2. Update the app list in Odoo (Apps → Update Apps List)
3. Search for "POS Custom Invoice Report" in the Apps menu
4. Click the Install button

### Configuration

1. Navigate to **Point of Sale → Configuration → Point of Sale**
2. Open or create a POS configuration
3. Go to the **Invoicing** tab
4. In the **Invoice Report** section, select your preferred invoice report template
5. Save the configuration

![POS Custom Invoice Report Configuration](src/description/pos_custom_invoice.png)

### Usage

Once configured, the module works automatically:

1. Create a POS order and invoice it
2. When the invoice is generated or sent, the system will:
   - Check if the order is from a POS configuration
   - If a custom report template is configured for that POS, use it
   - Otherwise, use the default invoice report

### Technical Details

**Models Extended:**
- `pos.config`: Adds `report_template_id` field
- `account.move.send`: Overrides `_get_default_pdf_report_id` method

**Dependencies:**
- `point_of_sale`
- `account`

### Author
Kıta

### License
This module is licensed under LGPL-3.

### Support
For more information, visit: [kitayazilim.com](https://kitayazilim.com)

---

## Türkçe

### Genel Bakış
**POS Custom Invoice Report** modülü, Odoo'daki Satış Noktası işlevselliğini her POS yapılandırması için özel fatura rapor şablonlarına izin vererek genişletir. Bu modül, kullanıcıların farklı POS konumları veya yapılandırmaları için belirli fatura rapor şablonları tanımlamasına olanak tanıyarak, fatura sunumu ve markalaşmada esneklik sağlar.

### Özellikler

- **Özel Rapor Seçimi**: Her POS yapılandırması için belirli bir fatura rapor şablonu yapılandırın
- **Dinamik Rapor Ataması**: POS siparişlerinden fatura oluştururken yapılandırılmış raporu otomatik olarak kullanır
- **Kolay Yapılandırma**: POS ayarlarına entegre edilmiş kullanıcı dostu arayüz
- **Esnek Filtreleme**: Yalnızca fatura ile uyumlu raporlar seçilebilir
- **Yedek Destek**: Özel rapor yapılandırılmamışsa, sistem varsayılan fatura raporunu kullanır

### Kurulum

1. Modül dosyalarını Odoo eklenti dizininize indirin veya klonlayın
2. Odoo'da uygulama listesini güncelleyin (Uygulamalar → Uygulama Listesini Güncelle)
3. Uygulamalar menüsünde "POS Custom Invoice Report" arayın
4. Kurulum butonuna tıklayın

### Yapılandırma

1. **Satış Noktası → Yapılandırma → Satış Noktası** menüsüne gidin
2. Bir POS yapılandırması açın veya oluşturun
3. **Faturalama** sekmesine gidin
4. **Fatura Raporu** bölümünde tercih ettiğiniz fatura rapor şablonunu seçin
5. Yapılandırmayı kaydedin

![POS Özel Fatura Raporu Yapılandırması](src/description/pos_custom_invoice.png)

### Kullanım

Yapılandırıldıktan sonra, modül otomatik olarak çalışır:

1. Bir POS siparişi oluşturun ve faturalandırın
2. Fatura oluşturulduğunda veya gönderildiğinde, sistem:
   - Siparişin bir POS yapılandırmasından olup olmadığını kontrol eder
   - O POS için özel bir rapor şablonu yapılandırılmışsa, onu kullanır
   - Aksi takdirde, varsayılan fatura raporunu kullanır

### Teknik Detaylar

**Genişletilen Modeller:**
- `pos.config`: `report_template_id` alanı ekler
- `account.move.send`: `_get_default_pdf_report_id` metodunu geçersiz kılar

**Bağımlılıklar:**
- `point_of_sale`
- `account`

### Yazar
Kıta

### Lisans
Bu modül LGPL-3 lisansı ile lisanslanmıştır.

### Destek
Daha fazla bilgi için: [kitayazilim.com](https://kitayazilim.com)
