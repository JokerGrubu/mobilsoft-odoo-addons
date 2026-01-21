# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft Konsinye Stok Yönetimi',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Joker Tedarik için konsinye stok takibi',
    'description': """
Joker Konsinye Stok Yönetimi
============================

Bu modül Joker Tedarik şirketi için konsinye stok takibi sağlar:

- Müşteriye konsinye mal teslimi
- Ön ödeme takibi
- Satılan malların faturalaması
- Satılmayan malların iade takibi
- Konsinye stok raporları

İş Akışı:
1. Konsinye teslimat oluştur
2. Ürünleri müşteriye teslim et (fatura kesilmez)
3. Ön ödeme al (varsa)
4. Müşteri sattıkça fatura kes
5. Satılmayanları iade al
    """,
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'stock',
        'sale',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/consignment_views.xml',
        'views/consignment_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
