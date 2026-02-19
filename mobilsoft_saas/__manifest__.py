# -*- coding: utf-8 -*-
{
    'name': 'MobilSoft SaaS - Çoklu Şirket Yönetimi',
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'summary': 'MobilSoft SaaS platformu için çoklu şirket kayıt ve kurulum sistemi',
    'description': '''
        MobilSoft SaaS Modülü
        =====================
        - Yeni müşteri kaydında otomatik şirket kurulumu
        - Hesap planı (l10n_tr) otomatik yükleme
        - Depo ve kasa otomatik oluşturma
        - Kullanıcı izolasyon kuralları
        - API endpoint'leri (JSON-RPC)
    ''',
    'author': 'MobilSoft / Joker Grubu',
    'depends': [
        'base',
        'account',
        'stock',
        'sale',
        'purchase',
        'l10n_tr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/mobilsoft_security.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
