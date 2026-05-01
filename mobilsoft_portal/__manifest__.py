# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft Portal',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'MobilSoft muhasebe portalı — Odoo Website/Portal tabanlı',
    'description': '''
        MobilSoft Portal
        ================
        React + FastAPI yerine Odoo Website/Portal kullanarak
        muhasebe arayüzü sağlar.

        Özellikler:
        - Özel login/kayıt sayfaları
        - Dashboard (KPI kartları)
        - Müşteri/Tedarikçi yönetimi
        - Ürün/Hizmet yönetimi
        - Fatura yönetimi
        - Stok/Kasa/Banka
        - Raporlar
        - POS entegrasyonu
        - CepteTedarik pazaryeri
    ''',
    'author': 'MobilSoft / Joker Grubu',
    'depends': [
        'website',
        'portal',
        'account',
        'sale',
        'purchase',
        'stock',
        'point_of_sale',
        'mobilsoft_saas',
        'mobilsoft_marketplace_core',
    ],
    'data': [
        'views/templates/layout.xml',
        'views/templates/login.xml',
        'views/templates/dashboard.xml',
        'views/templates/register.xml',
        'views/templates/cariler_list.xml',
        'views/templates/cari_detail.xml',
        'views/templates/cari_form.xml',
        'views/templates/cari_ekstre.xml',
        'views/templates/urunler_list.xml',
        'views/templates/urun_detail.xml',
        'views/templates/urun_form.xml',
        'views/templates/urun_stok.xml',
        'views/templates/faturalar_list.xml',
        'views/templates/fatura_detail.xml',
        'views/templates/fatura_form.xml',
        'views/templates/siparisler_list.xml',
        'views/templates/siparis_detail.xml',
        'views/templates/siparis_form.xml',
        'views/templates/kasa_banka_list.xml',
        'views/templates/kasa_banka_detail.xml',
        'views/templates/raporlar_index.xml',
        'views/templates/rapor_gelir_gider.xml',
        'views/templates/rapor_alacak_yaslandirma.xml',
        'views/templates/rapor_en_cok_satanlar.xml',
        'views/templates/masraflar_list.xml',
        'views/templates/masraf_form.xml',
        'views/templates/calisanlar_list.xml',
        'views/templates/ayarlar_index.xml',
        'views/templates/ayarlar_sirket.xml',
        'views/templates/ayarlar_profil.xml',
        'views/templates/ayarlar_gelismis.xml',
        'views/templates/odemeler_list.xml',
        'views/templates/odeme_form.xml',
        'views/templates/ebelge_list.xml',
        'views/templates/ebelge_detail.xml',
        'views/templates/cek_senet_list.xml',
        'views/templates/cek_senet_detail.xml',
        'views/templates/irsaliye_list.xml',
        'views/templates/irsaliye_detail.xml',
        'views/templates/cari_mutabakat.xml',
        'views/templates/bildirimler_list.xml',
        'views/templates/placeholder_page.xml',
        'views/templates/pos_index.xml',
        'views/templates/pazaryeri_index.xml',
        'views/templates/pazaryeri_kanal_form.xml',
        'views/templates/ayarlar_entegrasyonlar.xml',
        'views/templates/veri_aktarimi.xml',
        'views/templates/kullanicilar_list.xml',
        'views/templates/kullanici_form.xml',
        'views/templates/roller_list.xml',
        'views/templates/rol_form.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'mobilsoft_portal/static/src/scss/portal.scss',
            'mobilsoft_portal/static/src/js/portal.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
