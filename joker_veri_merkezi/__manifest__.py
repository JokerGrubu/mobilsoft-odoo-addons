{
    'name': 'Joker Veri Merkezi - Partner Senkronizasyonu',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Joker Veri Merkezindeki konsolide edilmiş CSV dosyalarından Mükerrer VKN kontrolüyle güvenli Odoo Partner aktarımı yapar.',
    'description': """
Joker Veri Merkezi Odoo Entegrasyon Modülü
==========================================
Bu modül, sunucudaki `/joker/JOKER_VERI_MERKEZI/` klasöründe derlenmiş olan 
ana ve ekstra partner CSV dosyalarını güvenli bir şekilde Odoo veritabanına aktarmak için kullanılır.

Özellikler:
- VKN / TC Kimlik Numarası tabanlı mükerrer kaydı engelleme
- Şirket / Şahıs (Kontak) / Şube yapılarını Odoo hiyerarşisine (parent_id) uygun bağlama
- Arkaplanda (Cron Job) otomatik veri çekme yeteneği
- Manuel tetikleme butonu
    """,
    'author': 'Antigravity (System Architect)',
    'depends': ['base', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/veri_aktarim_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
