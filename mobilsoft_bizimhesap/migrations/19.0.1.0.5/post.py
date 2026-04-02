# -*- coding: utf-8 -*-
"""
Migration 19.0.1.0.5: bizimhesap_cancelled alanını account.move tablosuna ekle.

Yeni alan: bizimhesap_cancelled (boolean) — BizimHesap /cancelinvoice ile iptal
edilen faturalar için kullanılır.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    try:
        cr.execute("""
            ALTER TABLE account_move
            ADD COLUMN IF NOT EXISTS bizimhesap_cancelled boolean DEFAULT false
        """)
        _logger.info("mobilsoft_bizimhesap 19.0.1.0.5: bizimhesap_cancelled kolonu eklendi.")
    except Exception as e:
        _logger.warning("mobilsoft_bizimhesap migration 19.0.1.0.5: %s", e)
