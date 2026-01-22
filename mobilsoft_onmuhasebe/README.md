# MobilSoft Ön Muhasebe

Türkiye pazarına özel, basit ve kullanışlı ön muhasebe uygulaması.

## Özellikler

### 📊 Dashboard (Gösterge Paneli)
- Toplam Kasa
- Toplam Banka
- Toplam Alacaklar
- Toplam Borçlar
- Hızlı işlemler

### 👥 Cari Hesaplar
- **VKN/TCKN:** Otomatik ayırma ve doğrulama
- **IBAN:** TR ile başlamalı, otomatik formatlama
- **Vergi Dairesi:** Türkiye vergi daireleri entegrasyonu
- **e-Fatura:** GİB e-Fatura kullanıcı bilgileri
- **Durum Badge'leri:** Aktif, Pasif, Bloke
- **Otomatik Bakiye:** Alacak, Borç, Net Bakiye hesaplama

### 💰 Çek & Senet Yönetimi
- Çek ve Senet kayıtları
- Durumlar: Portföy, Tahsil Edildi, Ödendi, Ciro Edildi, Karşılıksız
- Vade takibi ve vadesi geçmiş uyarıları
- Kanban, Tree, Form, Calendar view'ları
- Banka bilgileri (Banka, Şube, Hesap No)

### 📄 Faturalar
- Türkiye KDV oranları desteği (0%, 1%, 10%, 20%)
- Tevkifat desteği için hazır yapı
- Basitleştirilmiş form görünümü

## Kurulum

1. Odoo'yu yeniden başlatın:
   ```bash
   docker restart joker-odoo
   ```

2. Odoo'da Apps menüsünden "MobilSoft Ön Muhasebe" modülünü yükleyin.

3. Modül yüklendikten sonra "Ön Muhasebe" menüsü görünecektir.

## Bağımlılıklar

- `base`
- `contacts`
- `account`
- `account_accountant`
- `product`
- `sale`
- `purchase`
- `stock`
- `l10n_tr_tax_office_mobilsoft`

## Geliştirici

MobilSoft - https://www.mobilsoft.net

## Lisans

LGPL-3
