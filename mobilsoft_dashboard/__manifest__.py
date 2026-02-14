{
    "name": "Pazaryeri & Hızlı Teslimat Dashboard",
    "version": "19.0.1.0.0",
    "category": "MobilSoft/Dashboard",
    "application": True,
    "icon": "/mobilsoft_dashboard/static/description/icon.png",
    "author": "MobilSoft",
    "depends": [
        "base",
        "sale",
        "stock",
        "mobilsoft_marketplace_core",
        "mobilsoft_marketplace_trendyol",
        "mobilsoft_marketplace_hepsiburada",
        "mobilsoft_marketplace_n11",
        "mobilsoft_marketplace_cicek_sepeti",
        "mobilsoft_qcommerce_core",
        "mobilsoft_qcommerce_getir",
        "mobilsoft_qcommerce_yemeksepeti",
        "mobilsoft_qcommerce_vigo",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/dashboard_views.xml",
        "views/dashboard_menu.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
    "description": """
    Pazaryeri (Trendyol, Hepsiburada, N11, Çiçek Sepeti) ve Hızlı Teslimat (Getir, Yemeksepeti, Vigo)
    platformlarının birleştirilmiş analitik dashboard'ı.

    Özellikler:
    - Unified KPI cards (toplam sipariş, beklemede, başarı oranı)
    - Platform karşılaştırma (Pazaryeri vs Q-Commerce)
    - Senkronizasyon durumu widget'ı
    - Sipariş trend grafikleri (günlük, haftalık, aylık)
    - Kanban board (Channel, Order, Delivery status'e göre)
    - Stok devir analizi
    - Kâr marjı raporları
    - PDF export, scheduled sync
    """,
}
