import logging
from odoo import http
from odoo.tools import config

_logger = logging.getLogger(__name__)

# Orijinal odoo.http.db_filter fonksiyonunu sakla
orig_db_filter = http.db_filter

def dbfilter_from_header(dbs, httprequest=None):
    if httprequest:
        custom_db = httprequest.headers.get('X-Odoo-dbfilter')
        if custom_db and custom_db in dbs:
            return [custom_db]
    return orig_db_filter(dbs, httprequest)

http.db_filter = dbfilter_from_header
