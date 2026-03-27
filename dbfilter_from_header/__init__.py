import logging
from odoo import http

_logger = logging.getLogger(__name__)

# Orijinal odoo.http.db_filter fonksiyonunu sakla
orig_db_filter = http.db_filter

def dbfilter_from_header(dbs, host=None, **kwargs):
    request = http.request
    if request and hasattr(request, 'httprequest'):
        custom_db = request.httprequest.headers.get('X-Odoo-dbfilter')
        if custom_db and custom_db in dbs:
            return [custom_db]
    return orig_db_filter(dbs, host=host, **kwargs)

http.db_filter = dbfilter_from_header
