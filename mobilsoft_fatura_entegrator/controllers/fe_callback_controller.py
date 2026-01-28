import json
import logging
import hmac
import hashlib
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class FECallbackController(http.Controller):
    
    @http.route('/fe-invoice-callback', type='json', auth='public', methods=['POST'], csrf=False)
    def fe_invoice_callback(self, **kwargs):
        """Fatura Entegratör'den gelen callback'i işle"""
        try:
            # JSON verisini al
            data = request.jsonrequest if hasattr(request, 'jsonrequest') else kwargs
            
            _logger.info('FE Callback alındı: %s', json.dumps(data))
            
            # External ID'yi al
            external_id = data.get('id') or data.get('invoice_id') or data.get('external_id')
            if not external_id:
                # Invoice data içinde olabilir
                invoice_data = data.get('invoice') or data.get('data') or {}
                external_id = invoice_data.get('id') or invoice_data.get('external_id')
            
            if not external_id:
                _logger.error('FE Callback: external_id bulunamadı. Data: %s', json.dumps(data))
                return {'status': 'error', 'message': 'external_id bulunamadı'}
            
            # fe.invoice kaydını bul
            fe_invoice = request.env['fe.invoice'].sudo().search([
                ('external_id', '=', str(external_id))
            ], limit=1)
            
            if not fe_invoice:
                _logger.warning('FE Callback: external_id=%s için fe.invoice kaydı bulunamadı', external_id)
                # Yeni kayıt oluşturmayı deneyelim
                # Ancak account_move_id veya sale_order_id olmadan oluşturulamaz
                return {'status': 'error', 'message': 'fe.invoice kaydı bulunamadı'}
            
            # Callback verisiyle güncelle
            fe_invoice.update_from_callback(data)
            
            _logger.info('FE Callback işlendi: external_id=%s, durum=%s', external_id, data.get('status'))
            
            return {'status': 'success', 'message': 'Callback işlendi'}
            
        except Exception as e:
            _logger.exception('FE Callback hatası: %s', str(e))
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/fe-invoice-callback', type='http', auth='public', methods=['POST'], csrf=False)
    def fe_invoice_callback_http(self, **kwargs):
        """HTTP POST ile gelen callback'i işle (alternatif endpoint)"""
        try:
            # JSON verisini al
            data = json.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else kwargs
            
            _logger.info('FE Callback (HTTP) alındı: %s', json.dumps(data))
            
            # External ID'yi al
            external_id = data.get('id') or data.get('invoice_id') or data.get('external_id')
            if not external_id:
                invoice_data = data.get('invoice') or data.get('data') or {}
                external_id = invoice_data.get('id') or invoice_data.get('external_id')
            
            if not external_id:
                _logger.error('FE Callback (HTTP): external_id bulunamadı. Data: %s', json.dumps(data))
                return request.make_response(
                    json.dumps({'status': 'error', 'message': 'external_id bulunamadı'}),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )
            
            # fe.invoice kaydını bul
            fe_invoice = request.env['fe.invoice'].sudo().search([
                ('external_id', '=', str(external_id))
            ], limit=1)
            
            if not fe_invoice:
                _logger.warning('FE Callback (HTTP): external_id=%s için fe.invoice kaydı bulunamadı', external_id)
                return request.make_response(
                    json.dumps({'status': 'error', 'message': 'fe.invoice kaydı bulunamadı'}),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )
            
            # Callback verisiyle güncelle
            fe_invoice.update_from_callback(data)
            
            _logger.info('FE Callback (HTTP) işlendi: external_id=%s, durum=%s', external_id, data.get('status'))
            
            return request.make_response(
                json.dumps({'status': 'success', 'message': 'Callback işlendi'}),
                headers=[('Content-Type', 'application/json')],
                status=200
            )
            
        except Exception as e:
            _logger.exception('FE Callback (HTTP) hatası: %s', str(e))
            return request.make_response(
                json.dumps({'status': 'error', 'message': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )
    
    @http.route('/ginvoice-notification', type='http', auth='public', methods=['POST'], csrf=False)
    def ginvoice_notification(self, **kwargs):
        """SaaS uygulamasından gelen notification webhook'u işle
        
        Gelen veri formatı:
        {
            "invoice_id": 77,
            "team_id": 1,
            "time": "2025-11-10 15:43:59",
            "hash": "f98fb1294108e8fae093bd8cda7ce7467150914c2d2ce6276cf7d224268e7bdb77bfe8a122ad1c8ae7c31ca8f37023e68fb626963a4c1351043ffe9053cd97ad"
        }
        """
        try:
            # JSON verisini al
            if request.httprequest.data:
                data = json.loads(request.httprequest.data.decode('utf-8'))
            else:
                data = kwargs
            
            _logger.info('GInvoice Notification alındı: %s', json.dumps(data))
            
            # Gerekli alanları kontrol et
            invoice_id = data.get('invoice_id')
            team_id = data.get('team_id')
            time_str = data.get('time')
            received_hash = data.get('hash')
            
            if not all([invoice_id, team_id, time_str, received_hash]):
                _logger.error('GInvoice Notification: Eksik alanlar. Data: %s', json.dumps(data))
                return request.make_response(
                    json.dumps({'status': 'error', 'message': 'Eksik alanlar'}),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )
            
            # Hash doğrulama: Tüm company'leri kontrol et
            # team_id'yi company_id olarak kullanabiliriz veya tüm company'leri kontrol edebiliriz
            # Şimdilik tüm company'leri kontrol edip hangi company'nin API key'i ile hash doğrulandığını bulalım
            companies = request.env['res.company'].sudo().search([('fe_api_key', '!=', False)])
            valid_company = None
            
            for company in companies:
                if not company.fe_api_key:
                    continue
                
                # Hash hesapla: SHA512 HMAC ile invoice_id + team_id + time
                message = f"{invoice_id}{team_id}{time_str}"
                calculated_hash = hmac.new(
                    company.fe_api_key.encode('utf-8'),
                    message.encode('utf-8'),
                    hashlib.sha512
                ).hexdigest()
                
                if calculated_hash == received_hash:
                    valid_company = company
                    _logger.info('GInvoice Notification: Hash doğrulandı. Company: %s', company.name)
                    break
            
            if not valid_company:
                _logger.warning('GInvoice Notification: Hash doğrulanamadı. invoice_id=%s, team_id=%s', invoice_id, team_id)
                return request.make_response(
                    json.dumps({'status': 'error', 'message': 'Hash doğrulanamadı'}),
                    headers=[('Content-Type', 'application/json')],
                    status=401
                )
            
            # fe.invoice kaydını bul (external_id = invoice_id)
            fe_invoice = request.env['fe.invoice'].sudo().with_company(valid_company.id).search([
                ('external_id', '=', str(invoice_id)),
                ('company_id', '=', valid_company.id)
            ], limit=1)
            
            if not fe_invoice:
                _logger.warning('GInvoice Notification: external_id=%s için fe.invoice kaydı bulunamadı (company_id=%s)', invoice_id, valid_company.id)
                return request.make_response(
                    json.dumps({'status': 'error', 'message': 'fe.invoice kaydı bulunamadı'}),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )
            
            # API'den fatura bilgilerini çek ve güncelle
            fe_invoice.update_from_api()
            
            _logger.info('GInvoice Notification işlendi: external_id=%s, company=%s', invoice_id, valid_company.name)
            
            return request.make_response(
                'OK',
                headers=[('Content-Type', 'text/plain')],
                status=200
            )
            
        except Exception as e:
            _logger.exception('GInvoice Notification hatası: %s', str(e))
            return request.make_response(
                json.dumps({'status': 'error', 'message': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

