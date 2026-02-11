# -*- coding: utf-8 -*-
"""
Migration 19.0.1.0.2: Masaüstünde çift "BizimHesap" görünümünü kaldır.

Artık tek kök "MobilSoft" var; BizimHesap onun altında.
Parent'sız (kökte) kalan eski "BizimHesap" menüleri devre dışı bırakılır.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    try:
        cr.execute("""
            UPDATE ir_ui_menu
            SET active = false
            WHERE name = 'BizimHesap'
              AND parent_id IS NULL
        """)
        n = cr.rowcount
        if n:
            _logger.info("mobilsoft_bizimhesap: %s adet eski 'BizimHesap' kök menü devre dışı bırakıldı.", n)
    except Exception as e:
        _logger.warning("mobilsoft_bizimhesap migration 19.0.1.0.2: %s", e)
