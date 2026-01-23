import json
import logging
from typing import Dict, Any, Optional

import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FEClient(models.Model):
    _name = 'fe.client'
    _description = 'Fatura Entegratör API Client'

    @api.model
    def _get_company(self) -> models.Model:
        return self.env.company

    @api.model
    def _headers(self) -> Dict[str, str]:
        company = self._get_company()
        if not company.fe_api_key:
            raise UserError(_('Lütfen şirket için Fatura Entegratör API Key tanımlayın.'))
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {company.fe_api_key}',
        }

    @api.model
    def _base_url(self) -> str:
        # Tek sabit taban adresi kullanılır
        # Referans: https://documenter.getpostman.com/view/25047990/2sB3HrmHeZ#intro
        return 'https://staging.faturaentegrator.com/api'

    @api.model
    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self._base_url()}/{path.lstrip('/')}"
        try:
            resp = requests.request(method=method.upper(), url=url, headers=self._headers(), json=payload, params=params, timeout=30)
        except Exception as exc:  # noqa: BLE001
            _logger.exception('Fatura Entegratör isteği başarısız: %s %s', method, url)
            raise UserError(_('Fatura Entegratör bağlantı hatası: %s') % exc)

        if resp.status_code >= 400:
            _logger.error('Fatura Entegratör hata %s: %s', resp.status_code, resp.text)
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                raise UserError(_('Fatura Entegratör hata: HTTP %s') % resp.status_code)
            message = self._format_error_payload(data) or resp.text
            raise UserError(_('Fatura Entegratör hata: %s') % message)

        try:
            return resp.json() if resp.content else {}
        except Exception:  # noqa: BLE001
            return {}

    # Yardımcı uçlar (WordPress eklentisindeki helper fonksiyonlarına paralel)
    @api.model
    def check_connection(self) -> Dict[str, Any]:
        # PHP client: Helper::checkConnection() -> POST check/auth
        return self._request('POST', 'check/auth')

    @api.model
    def invoice_store(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request('POST', '/invoices', payload)

    @api.model
    def invoice_patch(self, external_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request('PATCH', f"/invoices/{external_id}", payload)

    @api.model
    def invoice_show(self, external_id: str) -> Dict[str, Any]:
        return self._request('GET', f"/invoices/{external_id}")

    @api.model
    def invoice_destroy(self, external_id: str) -> Dict[str, Any]:
        return self._request('DELETE', f"/invoices/{external_id}")

    @api.model
    def invoice_formalize(self, external_id: str) -> Dict[str, Any]:
        return self._request('POST', f"/invoices/{external_id}/formalize")

    @api.model
    def invoice_formal_pdf(self, external_id: str) -> bytes:
        url = f"{self._base_url()}/invoices/{external_id}/formal-pdf"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            raise UserError(_('Formal PDF alınamadı (HTTP %s)') % resp.status_code)
        return resp.content

    @api.model
    def integration_invoice_index(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # PHP client endpoint: integrations/invoice
        return self._request('GET', 'integrations/invoice', params=params)

    @api.model
    def integration_sale_channel_index(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # PHP client endpoint: integrations/sale-channel
        return self._request('GET', 'integrations/sale-channel', params=params)

    @api.model
    def integration_sale_channel_create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # PHP client endpoint: integrations/sale-channel
        return self._request('POST', 'integrations/sale-channel', payload)

    @api.model
    def integration_sale_channel_destroy(self, sale_channel_id: str) -> Dict[str, Any]:
        # PHP client endpoint: integrations/sale-channel/{id}
        return self._request('DELETE', f"integrations/sale-channel/{sale_channel_id}")

    # Bölgesel: Hata biçimlendirme
    @api.model
    def _format_error_payload(self, payload: Any) -> str:
        """FaturaEntegrator'un döndüğü hata yükünü okunabilir metne dönüştür.

        Desteklenen yapılar:
        - Top seviyede dict veya list
        - Dict içinde: message/error/detail + errors/client alanları (dict/list)
        - List öğeleri: dict veya string
        """
        try:
            lines = []
            base_message = ''
            # Top-level list
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        field = item.get('field') or item.get('name') or ''
                        text = item.get('message') or item.get('detail') or item.get('error') or json.dumps(item, ensure_ascii=False)
                        lines.append(f"{field}: {text}" if field else f"{text}")
                    else:
                        lines.append(str(item))
            elif isinstance(payload, dict):
                base_message = payload.get('message') or payload.get('error') or payload.get('detail') or ''
                candidates = payload.get('errors')
                if candidates is None:
                    candidates = payload.get('client')
                if candidates is None and isinstance(payload.get('data'), dict):
                    # Bazı API'ler errors'ı data içinde taşır
                    data_obj = payload.get('data') or {}
                    candidates = data_obj.get('errors') or data_obj.get('client')
                if isinstance(candidates, dict):
                    for key, val in candidates.items():
                        if isinstance(val, list):
                            for s in val:
                                lines.append(f"{key}: {s}")
                        elif isinstance(val, dict):
                            text = val.get('message') or val.get('detail') or json.dumps(val, ensure_ascii=False)
                            lines.append(f"{key}: {text}")
                        else:
                            lines.append(f"{key}: {val}")
                elif isinstance(candidates, list):
                    for item in candidates:
                        if isinstance(item, dict):
                            field = item.get('field') or item.get('name') or ''
                            text = item.get('message') or item.get('detail') or item.get('error') or json.dumps(item, ensure_ascii=False)
                            lines.append(f"{field}: {text}" if field else f"{text}")
                        else:
                            lines.append(str(item))
            result = (base_message or '').strip()
            details = '\n'.join([ln for ln in lines if ln]).strip()
            if result and details:
                return f"{result}\n{details}"
            return result or details
        except Exception:  # noqa: BLE001
            # Beklenmeyen durumda payload'ı stringleştir
            try:
                return json.dumps(payload, ensure_ascii=False)
            except Exception:  # noqa: BLE001
                return str(payload)

