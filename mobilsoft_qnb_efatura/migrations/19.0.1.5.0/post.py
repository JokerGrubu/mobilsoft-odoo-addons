# -*- coding: utf-8 -*-
"""
Migration 19.0.1.5.0: QNB ve Nilvera cron'larını 15 dakikada bir çalışacak şekilde güncelle.

Yeni gelen/giden e-belgeler otomatik olarak Odoo'ya alınır.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    xml_ids = [
        'mobilsoft_qnb_efatura.ir_cron_qnb_fetch_incoming',
        'mobilsoft_qnb_efatura.ir_cron_qnb_fetch_outgoing',
        'mobilsoft_qnb_efatura.ir_cron_qnb_check_status',
        'l10n_tr_nilvera_einvoice.ir_cron_nilvera_get_new_purchase_documents',
        'l10n_tr_nilvera_einvoice.ir_cron_nilvera_get_new_einvoice_sale_documents',
        'l10n_tr_nilvera_einvoice.ir_cron_nilvera_get_new_earchive_sale_documents',
        'l10n_tr_nilvera_einvoice.ir_cron_nilvera_get_invoice_status',
        'l10n_tr_nilvera_einvoice.ir_cron_nilvera_get_sale_pdf',
    ]

    for xml_id in xml_ids:
        try:
            cron = env.ref(xml_id, raise_if_not_found=False)
            if cron:
                cron.write({'interval_number': 15, 'interval_type': 'minutes'})
                _logger.info("Updated cron %s to 15 minutes", xml_id)
        except Exception as e:
            _logger.warning("Cron update %s: %s", xml_id, e)
