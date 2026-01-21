# Product Variant Image Sync

## English

### Overview
The **Product Variant Image Sync** module automatically synchronizes product images across variants that share the same attribute values. This eliminates the need to manually add the same image to multiple variants with identical attributes.

### Features

- **Automatic Image Synchronization**: Add an image to one variant, and it automatically syncs to all variants with matching attribute values
- **Configurable per Attribute**: Enable/disable image sync for each attribute individually using the "Sync Images" flag
- **Attribute-Based Matching**: Images are synced based on specific attribute values (e.g., all "Red" variants get the same images)
- **Multi-Attribute Support**: Works with any combination of product attributes (Color, Size, Material, etc.)
- **Smart Detection**: Only syncs to variants with identical attribute value combinations for sync-enabled attributes
- **Bidirectional Sync**: Updates are reflected across all matching variants automatically
- **No Duplicate Images**: Prevents creating duplicate images for the same variant

### Use Cases

**Fashion & Apparel**
- Add an image to "T-Shirt / Small / Red"
- Image automatically appears on "T-Shirt / Medium / Red" and "T-Shirt / Large / Red"
- Different colors maintain their unique images

**Electronics**
- Add images to "Laptop / 15 inch / Black"
- Same images apply to all "15 inch / Black" variants with different RAM or storage

**Furniture**
- Add images to "Chair / Oak / Armrest"
- Images sync to all oak chairs with armrests, regardless of other attributes

### Installation

1. Download or clone the module into your Odoo addons directory
2. Update the app list in Odoo (Apps → Update Apps List)
3. Search for "Product Variant Image Sync" in the Apps menu
4. Click the Install button

### Configuration

#### Enable Image Sync for Attributes

1. Navigate to **Sales → Configuration → Attributes**
2. Open or create an attribute (e.g., "Color")
3. Enable the **"Sync Images Across Variants"** toggle
4. Save the attribute

**Recommended Attributes to Enable:**
- ✓ Color
- ✓ Material
- ✓ Pattern
- ✗ Size (usually doesn't need sync)
- ✗ Dimensions (usually doesn't need sync)

The sync only applies to attributes where the flag is enabled!

### Usage

#### Adding Images to Variants

1. Navigate to **Sales → Products → Products**
2. Open a product with variants
3. Switch to any variant
4. Go to the **Sales** or **Images** section
5. Add an image to the variant
6. The image is automatically added to all variants with matching attribute values

#### Example Workflow

**Product**: Athletic Shoes
**Variants**:
- Size 8 / Red
- Size 9 / Red
- Size 10 / Red
- Size 8 / Blue
- Size 9 / Blue

**Steps**:
1. Open "Size 8 / Red" variant
2. Add a red shoe image
3. The image automatically appears on:
   - Size 9 / Red ✓
   - Size 10 / Red ✓
4. Blue variants are not affected (different color attribute)

### Technical Details

**Models Extended:**
- `product.attribute`: Adds `sync_images` boolean field
- `product.product`: Adds helper methods to find variants with matching attributes
- `product.image`: Overrides `create` and `write` methods to sync images automatically

**How It Works:**
1. When an image is added to a variant, the system identifies attribute values for sync-enabled attributes
2. It searches for other variants with identical attribute value combinations (only for sync-enabled attributes)
3. The image is automatically created/updated for all matching variants
4. Existing images with the same name are updated instead of duplicated

**Dependencies:**
- `product`
- `website_sale`

### Notes

- Only affects variants from the same product template
- Images are matched by attribute values, not by attribute names
- Syncing happens automatically - no manual action required
- Works with all types of product attributes

### Author
Kıta

### License
This module is licensed under LGPL-3.

### Support
For more information, visit: [kitayazilim.com](https://kitayazilim.com)

---

## Türkçe

### Genel Bakış
**Product Variant Image Sync** modülü, aynı özellik değerlerine sahip ürün varyantları arasında görüntüleri otomatik olarak senkronize eder. Bu, aynı özelliklere sahip birden fazla varyanta aynı görseli manuel olarak ekleme ihtiyacını ortadan kaldırır.

### Özellikler

- **Otomatik Görsel Senkronizasyonu**: Bir varyanta görsel ekleyin, eşleşen özellik değerlerine sahip tüm varyantlara otomatik olarak senkronize edilir
- **Özellik Başına Yapılandırılabilir**: Her özellik için "Görsel Senkronize Et" bayrağını kullanarak ayrı ayrı etkinleştirin/devre dışı bırakın
- **Özellik Tabanlı Eşleştirme**: Görseller belirli özellik değerlerine göre senkronize edilir (örn. tüm "Kırmızı" varyantlar aynı görselleri alır)
- **Çoklu Özellik Desteği**: Herhangi bir ürün özelliği kombinasyonu ile çalışır (Renk, Beden, Malzeme, vb.)
- **Akıllı Tespit**: Yalnızca senkronizasyon etkin özelliklerde aynı özellik değer kombinasyonuna sahip varyantlara senkronize eder
- **Çift Yönlü Senkronizasyon**: Güncellemeler tüm eşleşen varyantlara otomatik olarak yansır
- **Tekrarlanan Görsel Yok**: Aynı varyant için tekrarlanan görsel oluşturmayı önler

### Kullanım Senaryoları

**Moda & Tekstil**
- "Tişört / Small / Kırmızı" varyantına görsel ekleyin
- Görsel otomatik olarak "Tişört / Medium / Kırmızı" ve "Tişört / Large / Kırmızı" üzerinde görünür
- Farklı renkler kendi benzersiz görsellerini korur

**Elektronik**
- "Dizüstü / 15 inç / Siyah" varyantına görsel ekleyin
- Aynı görseller farklı RAM veya depolama kapasiteli tüm "15 inç / Siyah" varyantlara uygulanır

**Mobilya**
- "Sandalye / Meşe / Kolçaklı" varyantına görsel ekleyin
- Görseller, diğer özelliklerden bağımsız olarak kolçaklı tüm meşe sandalyelere senkronize edilir

### Kurulum

1. Modülü Odoo eklenti dizininize indirin veya klonlayın
2. Odoo'da uygulama listesini güncelleyin (Uygulamalar → Uygulama Listesini Güncelle)
3. Uygulamalar menüsünde "Product Variant Image Sync" arayın
4. Kurulum butonuna tıklayın

### Yapılandırma

#### Özellikler için Görsel Senkronizasyonunu Etkinleştirme

1. **Satış → Yapılandırma → Özellikler** menüsüne gidin
2. Bir özellik açın veya oluşturun (örn. "Renk")
3. **"Varyantlar Arasında Görselleri Senkronize Et"** anahtarını etkinleştirin
4. Özelliği kaydedin

**Etkinleştirmeniz Önerilen Özellikler:**
- ✓ Renk
- ✓ Malzeme
- ✓ Desen
- ✗ Beden (genellikle senkronizasyon gerektirmez)
- ✗ Boyutlar (genellikle senkronizasyon gerektirmez)

Senkronizasyon yalnızca bayrağın etkinleştirildiği özellikler için geçerlidir!

### Kullanım

#### Varyantlara Görsel Ekleme

1. **Satış → Ürünler → Ürünler** menüsüne gidin
2. Varyantlı bir ürünü açın
3. Herhangi bir varyanta geçin
4. **Satış** veya **Görseller** bölümüne gidin
5. Varyanta görsel ekleyin
6. Görsel, eşleşen özellik değerlerine sahip tüm varyantlara otomatik olarak eklenir

#### Örnek İş Akışı

**Ürün**: Spor Ayakkabı
**Varyantlar**:
- Numara 40 / Kırmızı
- Numara 41 / Kırmızı
- Numara 42 / Kırmızı
- Numara 40 / Mavi
- Numara 41 / Mavi

**Adımlar**:
1. "Numara 40 / Kırmızı" varyantını açın
2. Kırmızı ayakkabı görseli ekleyin
3. Görsel otomatik olarak şuralarda görünür:
   - Numara 41 / Kırmızı ✓
   - Numara 42 / Kırmızı ✓
4. Mavi varyantlar etkilenmez (farklı renk özelliği)

### Teknik Detaylar

**Genişletilen Modeller:**
- `product.attribute`: `sync_images` boolean alanı ekler
- `product.product`: Eşleşen özelliklere sahip varyantları bulmak için yardımcı metodlar ekler
- `product.image`: Görselleri otomatik olarak senkronize etmek için `create` ve `write` metodlarını geçersiz kılar

**Nasıl Çalışır:**
1. Bir varyanta görsel eklendiğinde, sistem senkronizasyon etkin özelliklerin değerlerini tanımlar
2. Aynı özellik değer kombinasyonuna sahip diğer varyantları arar (sadece senkronizasyon etkin özellikler için)
3. Görsel, eşleşen tüm varyantlar için otomatik olarak oluşturulur/güncellenir
4. Aynı ada sahip mevcut görseller çoğaltılmak yerine güncellenir

**Bağımlılıklar:**
- `product`
- `website_sale`

### Notlar

- Yalnızca aynı ürün şablonundaki varyantları etkiler
- Görseller özellik adlarına değil, özellik değerlerine göre eşleştirilir
- Senkronizasyon otomatik olarak gerçekleşir - manuel işlem gerekmez
- Tüm ürün özellik türleri ile çalışır

### Yazar
Kıta

### Lisans
Bu modül LGPL-3 lisansı ile lisanslanmıştır.

### Destek
Daha fazla bilgi için: [kitayazilim.com](https://kitayazilim.com)
