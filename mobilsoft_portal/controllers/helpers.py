# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Yardımcı Fonksiyonlar
Şirket filtreleme mantığı:
  - MobilSoft Platform (id=1): Tüm şirketlerin verilerini görür
  - Diğer şirketler: Sadece kendi verilerini görür
  - Ürünler: Ortak (company filtresi yok)
"""
from odoo.http import request

ADMIN_COMPANY_ID = 1  # MobilSoft Platform — tüm verileri görür


def get_company_domain():
    """
    Şirket bazlı domain filtresi döndürür.
    MobilSoft Platform (id=1) tüm verileri görür, diğerleri sadece kendilerini.
    Returns: list — Odoo domain parçası, örn: [('company_id', 'in', [1,2,3])]
    """
    env = request.env
    user_company = env.company.id

    if user_company == ADMIN_COMPANY_ID:
        # Admin şirket: tüm şirketleri gör
        all_ids = env['res.company'].sudo().search([]).ids
        return [('company_id', 'in', all_ids)]
    else:
        # Normal şirket: sadece kendi verisini gör
        return [('company_id', '=', user_company)]


def get_company_ids():
    """
    Erişilebilir şirket ID listesi döndürür.
    MobilSoft Platform → tüm şirketler, diğerleri → sadece kendi.
    Returns: list of int
    """
    env = request.env
    user_company = env.company.id

    if user_company == ADMIN_COMPANY_ID:
        return env['res.company'].sudo().search([]).ids
    else:
        return [user_company]


def get_default_company_id():
    """Yeni kayıt oluştururken kullanılacak şirket ID'si."""
    return request.env.company.id


def is_admin_company():
    """Kullanıcı MobilSoft Platform şirketinde mi?"""
    return request.env.company.id == ADMIN_COMPANY_ID


def check_record_access(record):
    """Kayda erişim kontrolü. True ise erişim var."""
    if not record.exists():
        return False
    if is_admin_company():
        return True
    if hasattr(record, 'company_id') and record.company_id:
        return record.company_id.id == request.env.company.id
    return True
