PayTR Ödeme Sağlayıcı Entegrasyonu
==================================

Bu modül, Odoo ile PayTR ödeme altyapısını entegre eder ve müşterilerinizin PayTR iframe çözümü ile güvenli şekilde ödeme yapmasını sağlar. PayTR, Türkiye'de yaygın olarak kullanılan ve kredi kartı, banka kartı, taksitli ödeme gibi birçok seçeneği destekleyen bir ödeme altyapısıdır.

Özellikler
----------
- PayTR iframe ödeme çözümü ile tam entegrasyon
- Kredi kartı ile ödeme desteği
- Taksitli ödeme seçenekleri
- Troy kart sistemi desteği
- Otomatik işlem durumu güncellemeleri
- Geliştirme ve test için test modu

Gereksinimler
-------------
- Odoo v16.0, v17.0, v18.0
- PayTR mağaza hesabı
- PayTR API bilgileri (Mağaza Numarası, API Key, API Salt)

Kurulum
-------
1. Bu repoyu Odoo eklenti dizininize klonlayın:

   ::

      git clone https://github.com/kitayazilim/odoo-addons.git /path/to/odoo/addons/payment_paytr_kt

2. Odoo'da Uygulamalar menüsüne gidin ve "Uygulama Listesini Güncelle" seçeneğine tıklayın.
3. "PayTR iFrame" araması yaparak modülü yükleyin.
4. Alternatif olarak ZIP dosyasını yükleyerek de kurulum yapabilirsiniz.

Yapılandırma
------------
1. Faturalandırma/Muhasebe > Yapılandırma > Ödeme Sağlayıcıları menüsüne gidin.
2. Yeni bir ödeme sağlayıcı oluşturun veya mevcut PayTR sağlayıcısını düzenleyin.
3. Sağlayıcıyı "PayTR" olarak seçin.
4. PayTR mağaza bilgilerinizi girin:

   - Mağaza Numarası (Merchant ID)
   - Mağaza API Key
   - Mağaza API Salt

5. Ek ayarları yapılandırın:

   - Tek çekim seçeneği
   - En fazla taksit sayısı
   - Zaman aşımı limiti

6. Test için "Test Modu", canlı kullanım için "Etkin" olarak ayarlayın.

PayTR Canlıya Alma
------------------
1. PayTR api hesabınıza girip Destek ve Kurulum Başlığı altındaki ayarlardan bildirim url'ini değiştir diyerek site adresinizin sonuna **/payment/paytr/return** kısmını ekleyin.
2. Odoo uygulamasında Muhasebe > Yapılandırma > Ödeme Sağlayıcıları menüsünden PayTR iFrame sağlayıcısına girin.
3. Ödeme Sistemini Test moduna geçirin ve web sayfanızdan sepetinize bir ürün ekleyerek ilk test isteğiniz ile ödemeyi tamamlayın.
4. Yukarıdaki adım PayTR hesabınızı canlıya almak için zorunludur.
5. İlk test isteğiyle sipariş geçtikten sonra PayTR api hesabınıza girip canlıya alma yönergelerini takip edin.
6. Son olarak daha önce Odoo'dan test moduna aldığınız PayTR Iframe'i etkinleştirerek canlı moda geçirebilirsiniz.

Kullanım
--------
Yapılandırma tamamlandığında, PayTR ödeme seçeneği web sitenizin ödeme sayfasında görünecektir. Müşteriler bu yöntemi seçtiğinde, PayTR iframe ekranına yönlendirilerek ödemelerini güvenli şekilde tamamlayabilirler.

Destek
------
Destek için Kıta Yazılım ile iletişime geçebilirsiniz:

- Web: https://kitayazilim.com
- E-posta: info@kitayazilim.com
- Yardım Masası: destek@kitayazilim.com

Lisans
------
Bu modül LGPL-3 lisansı ile lisanslanmıştır.
