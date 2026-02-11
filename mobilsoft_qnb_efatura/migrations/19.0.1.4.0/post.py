# -*- coding: utf-8 -*-
"""
Migration 19.0.1.4.0: Kaldırılan alanların veritabanı sütunlarını temizle.

Bu sütunlar artık kodda yok; eski kurulumlarda kalan sütunları DROP eder.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # res_partner: QNB/Nilvera refaktöründe kaldırılan alanlar
    partner_columns = [
        'is_efatura_registered',
        'efatura_alias',
        'efatura_alias_type',
        'efatura_registration_date',
        'efatura_last_check',
        'qnb_customer_status',
        'qnb_partner_vkn',
    ]
    for col in partner_columns:
        try:
            # Sütun adı sabit listeden; SQL injection yok
            cr.execute(
                "ALTER TABLE res_partner DROP COLUMN IF EXISTS " + col
            )
            _logger.info("Dropped column res_partner.%s", col)
        except Exception as e:
            _logger.warning("res_partner.%s: %s", col, e)

    # product_product: Standart alan refaktöründe kaldırılan alan
    try:
        cr.execute(
            "ALTER TABLE product_product DROP COLUMN IF EXISTS qnb_product_code"
        )
        _logger.info("Dropped column product_product.qnb_product_code")
    except Exception as e:
        _logger.warning("product_product.qnb_product_code: %s", e)
