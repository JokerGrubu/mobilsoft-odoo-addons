{
    "name": "MobilSoft Hızlı Teslimat - Core",
    "version": "19.0.1.0.0",
    "category": "Sales/Q-Commerce",
    "author": "MobilSoft",
    "depends": ["base", "sale", "stock", "account", "mail"],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Views
        "views/qcommerce_channel_views.xml",
        "views/qcommerce_order_views.xml",
        "views/qcommerce_delivery_views.xml",
        "views/qcommerce_sync_log_views.xml",
        "views/qcommerce_actions.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": "LGPL-3",
    "summary": "Getir, Yemeksepeti, Vigo gibi hızlı teslimat platformlarının entegrasyonu",
    "description": """
    Hızlı teslimat (Q-Commerce) platformlarıyla entegrasyon sağlar.

    Özellikler:
    - Otomatik sipariş kabulü
    - Hazırlık zamanlayıcısı
    - Anında kurye talebi
    - Teslimat takibi
    - Webhook desteği

    Desteklenen Platformlar:
    - Getir
    - Yemeksepeti
    - Vigo
    """,
    "external_dependencies": {
        "python": ["requests", "lxml", "python-dateutil"],
    },
}
