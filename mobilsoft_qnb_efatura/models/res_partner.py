# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    invoice_edi_format = fields.Selection(selection_add=[('ubl_tr_qnb', "Türkiye (UBL TR 1.2 - QNB)")])

    # e-Fatura Bilgileri — Nilvera ile ortak alanlar kullanılıyor (l10n_tr_nilvera_customer_status, l10n_tr_nilvera_customer_alias_id)
    # QNB sadece "son kontrol tarihi" için ek alan tutar (cron için)
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True
    )
    qnb_last_check_date = fields.Datetime(
        string='QNB Son Kontrol',
        help='QNB ile e-Fatura kaydı son kontrol edilme tarihi (cron için)'
    )

    balance_2025_receivable = fields.Monetary(
        string='2025 Alacak',
        currency_field='company_currency_id',
        compute='_compute_balance_2025',
        store=False
    )
    balance_2025_payable = fields.Monetary(
        string='2025 Borç',
        currency_field='company_currency_id',
        compute='_compute_balance_2025',
        store=False
    )
    balance_2025_net = fields.Monetary(
        string='2025 Net',
        currency_field='company_currency_id',
        compute='_compute_balance_2025',
        store=False
    )

    # e-İrsaliye Bilgileri
    is_eirsaliye_registered = fields.Boolean(
        string='e-İrsaliye Kayıtlı',
        default=False,
        help='Bu firma GİB e-İrsaliye sistemine kayıtlı mı?'
    )
    eirsaliye_alias = fields.Char(
        string='e-İrsaliye Posta Kutusu',
        help='Alıcının e-İrsaliye posta kutusu etiketi'
    )

    # Fatura Gönderim Tercihi
    invoice_send_method = fields.Selection([
        ('efatura', 'e-Fatura'),
        ('earsiv', 'e-Arşiv'),
        ('manual', 'Manuel')
    ], string='Fatura Gönderim Yöntemi',
        compute='_compute_invoice_send_method',
        store=True,
        help='Otomatik hesaplanan fatura gönderim yöntemi')

    @api.depends('l10n_tr_nilvera_customer_status', 'vat')
    def _compute_invoice_send_method(self):
        for partner in self:
            if getattr(partner, 'l10n_tr_nilvera_customer_status', None) == 'einvoice':
                partner.invoice_send_method = 'efatura'
            elif partner.vat:
                partner.invoice_send_method = 'earsiv'
            else:
                partner.invoice_send_method = 'manual'

    def _get_edi_builder(self, invoice_edi_format):
        if invoice_edi_format == 'ubl_tr_qnb':
            return self.env['account.edi.xml.ubl.tr.qnb']
        return super()._get_edi_builder(invoice_edi_format)

    def _get_ubl_cii_formats_info(self):
        formats_info = super()._get_ubl_cii_formats_info()
        formats_info['ubl_tr_qnb'] = {'countries': ['TR']}
        return formats_info

    def _get_suggested_invoice_edi_format(self):
        """TR partnerleri için otomatik UBL TR QNB formatı öner (Nilvera uyumlu)"""
        # EXTENDS 'account'
        res = super()._get_suggested_invoice_edi_format()
        if self.country_code == 'TR':
            return 'ubl_tr_qnb'
        return res

    def _check_qnb_customer(self):
        """QNB API ile e-fatura kaydını kontrol et; sonucu Nilvera alanlarına yaz (ortak yapı)."""
        self.ensure_one()
        if not self.vat:
            self.write({
                'l10n_tr_nilvera_customer_status': 'not_checked',
                'l10n_tr_nilvera_customer_alias_id': False,
                'qnb_last_check_date': fields.Datetime.now(),
            })
            return False

        vkn = ''.join(filter(str.isdigit, self.vat))
        if not vkn:
            self.write({
                'l10n_tr_nilvera_customer_status': 'not_checked',
                'qnb_last_check_date': fields.Datetime.now(),
            })
            return False

        api_client = self.env['qnb.api.client']
        result = api_client.check_registered_user(vkn)

        if result.get('success') and result.get('users'):
            user = result['users'][0]
            alias_name = (user.get('alias') or '').strip()
            # Nilvera yapısı: l10n_tr.nilvera.alias (name, partner_id)
            Alias = self.env['l10n_tr.nilvera.alias']
            existing = Alias.search([
                ('partner_id', '=', self.id),
                ('name', '=', alias_name),
            ], limit=1)
            if not existing and alias_name:
                existing = Alias.create({'name': alias_name, 'partner_id': self.id})
            self.write({
                'l10n_tr_nilvera_customer_status': 'einvoice',
                'l10n_tr_nilvera_customer_alias_id': existing.id if existing else False,
                'qnb_last_check_date': fields.Datetime.now(),
            })
            return True

        self.write({
            'l10n_tr_nilvera_customer_status': 'earchive' if self.vat else 'not_checked',
            'l10n_tr_nilvera_customer_alias_id': False,
            'qnb_last_check_date': fields.Datetime.now(),
        })
        return False

    def action_check_efatura_status(self):
        """e-Fatura kayıt durumunu kontrol et"""
        self.ensure_one()

        if not self.vat:
            raise UserError(_("VKN/TCKN bilgisi girilmemiş!"))

        result = self._check_qnb_customer()
        alias = self.l10n_tr_nilvera_customer_alias_id.name if self.l10n_tr_nilvera_customer_alias_id else ''
        if result:
            message = f"✅ {self.name} e-Fatura sistemine kayıtlı!\nPosta Kutusu: {alias or '-'}"
        else:
            message = f"ℹ️ {self.name} e-Fatura sistemine kayıtlı değil."

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'e-Fatura Kayıt Durumu',
                'message': message,
                'type': 'success' if self.l10n_tr_nilvera_customer_status == 'einvoice' else 'warning',
                'sticky': False,
            }
        }

    def _normalize_city_state_partner_data(self, partner_data):
        """XML'den gelen il/ilçe birleşik alanları ayır (partner_data dict üzerinde)."""
        raw_city = (partner_data.get('city') or '').strip()
        raw_state = (partner_data.get('state') or '').strip()
        if raw_city and not raw_state and '/' in raw_city:
            parts = [p.strip() for p in raw_city.split('/') if p.strip()]
            if len(parts) >= 2:
                partner_data['city'] = parts[0]
                partner_data['state'] = parts[1]
        if raw_state and not raw_city and '/' in raw_state:
            parts = [p.strip() for p in raw_state.split('/') if p.strip()]
            if len(parts) >= 2:
                partner_data['city'] = parts[0]
                partner_data['state'] = parts[1]

    def _get_latest_qnb_partner_data(self):
        """
        Bu partner'ın VKN'ına ait en son QNB belgesinden partner bilgilerini (adres, iletişim, vergi dairesi vb.) döndürür.
        Eşleşen belge yoksa None.
        """
        self.ensure_one()
        if not self.vat:
            return None
        digits = ''.join(filter(str.isdigit, str(self.vat)))
        if len(digits) not in (10, 11):
            return None
        vat_number = f"TR{digits}"

        QnbDoc = self.env['qnb.document']
        docs = QnbDoc.search([
            ('partner_id', '=', self.id),
            ('xml_content', '!=', False),
        ], order='document_date desc, id desc', limit=20)
        if not docs:
            docs = QnbDoc.search([
                ('xml_content', '!=', False),
            ], order='document_date desc, id desc', limit=100)
        for doc in docs:
            raw = doc.xml_content
            if not raw:
                continue
            if isinstance(raw, str):
                raw = raw.encode('utf-8')
            xml_bytes = raw
            try:
                decoded = base64.b64decode(raw, validate=True)
                if decoded.strip().startswith(b'<'):
                    xml_bytes = decoded
            except Exception:
                pass
            parsed = doc._parse_invoice_xml_full(xml_bytes, direction=doc.direction)
            partner_data = (parsed or {}).get('partner') or {}
            vat_raw = partner_data.get('vat') or ''
            doc_digits = ''.join(filter(str.isdigit, str(vat_raw)))
            doc_vat = f"TR{doc_digits}" if doc_digits else False
            if doc_vat == vat_number:
                return partner_data
        return None

    def _apply_qnb_partner_data(self, partner_data, skip_name=False):
        """
        XML'den gelen partner_data dict'ini bu partner'a uygula: adres, il, ilçe, posta kodu,
        vergi dairesi, telefon, e-posta, web sitesi, ülke/il; varsa IBAN.
        skip_name=True ise name alanı yazılmaz (mükellef güncellemesinde ünvan zaten GİB'den gelir).
        """
        self.ensure_one()
        update_vals = {}
        if not skip_name:
            name_raw = (partner_data.get('name') or '').strip()
            if name_raw and (self.name or '').strip() != name_raw:
                update_vals['name'] = name_raw
        for src_key, dst_key in [
            ('street', 'street'),
            ('street2', 'street2'),
            ('city', 'city'),
            ('zip', 'zip'),
            ('phone', 'phone'),
            ('mobile', 'mobile'),
            ('email', 'email'),
            ('website', 'website'),
        ]:
            val = (partner_data.get(src_key) or '').strip() if isinstance(partner_data.get(src_key), str) else (partner_data.get(src_key) or '')
            if not isinstance(val, str):
                continue
            val = val.strip()
            if val and (self[dst_key] or '').strip() != val:
                update_vals[dst_key] = val
        tax_office = (partner_data.get('tax_office') or '').strip()
        if tax_office:
            if 'l10n_tr_tax_office_id' in self._fields:
                tax_model = self.env['l10n.tr.tax.office']
                tax_rec = tax_model.search([('name', 'ilike', tax_office)], limit=1)
                if tax_rec and self.l10n_tr_tax_office_id != tax_rec:
                    update_vals['l10n_tr_tax_office_id'] = tax_rec.id
            elif 'l10n_tr_tax_office_name' in self._fields:
                if (self.l10n_tr_tax_office_name or '').strip() != tax_office:
                    update_vals['l10n_tr_tax_office_name'] = tax_office
        country_name = (partner_data.get('country') or '').strip()
        if country_name and 'country_id' in self._fields:
            country = self.env['res.country'].search([('name', 'ilike', country_name)], limit=1)
            if country and self.country_id != country:
                update_vals['country_id'] = country.id
        state_name = (partner_data.get('state') or '').strip()
        if state_name and 'state_id' in self._fields:
            domain = [('name', 'ilike', state_name)]
            if update_vals.get('country_id') or self.country_id:
                country_id = update_vals.get('country_id') or self.country_id.id
                domain.append(('country_id', '=', country_id))
            state = self.env['res.country.state'].search(domain, limit=1)
            if state and self.state_id != state:
                update_vals['state_id'] = state.id
        if update_vals:
            self.write(update_vals)
        iban = (partner_data.get('iban') or '').replace(' ', '')
        if iban:
            Bank = self.env['res.partner.bank']
            existing_bank = Bank.search([('partner_id', '=', self.id), ('acc_number', '=', iban)], limit=1)
            if not existing_bank:
                bank_vals = {'partner_id': self.id, 'acc_number': iban}
                if 'company_id' in Bank._fields and self.company_id:
                    bank_vals['company_id'] = self.company_id.id
                bank_name = (partner_data.get('bank_name') or '').strip()
                if bank_name and 'bank_id' in Bank._fields:
                    bank = self.env['res.bank'].search([('name', 'ilike', bank_name)], limit=1)
                    if bank:
                        bank_vals['bank_id'] = bank.id
                Bank.create(bank_vals)

    def action_update_from_qnb_mukellef(self):
        """
        QNB mükellef sorgusu (kayıtlı kullanıcı) ile partner bilgilerini güncelle.
        - GİB'den: ünvan, e-Fatura posta kutusu (alias), durum.
        - Ardından bu partner için QNB'de kayıtlı en son belgeden (XML) adres, il, ilçe, posta kodu,
          vergi dairesi, telefon, e-posta, web sitesi güncellenir (varsa).
        """
        company = self.env.company
        api_client = self.env['qnb.api.client'].with_company(company)
        Alias = self.env['l10n_tr.nilvera.alias']

        processed = 0
        updated_name = 0
        updated_alias = 0
        updated_xml = 0
        skipped = 0
        errors = 0

        for partner in self:
            processed += 1
            try:
                if not partner.vat:
                    skipped += 1
                    continue
                digits = ''.join(filter(str.isdigit, str(partner.vat)))
                if len(digits) not in (10, 11):
                    skipped += 1
                    continue

                result = api_client.check_registered_user(digits, company=company)
                if not (result.get('success') and result.get('users')):
                    if getattr(partner, 'l10n_tr_nilvera_customer_status', None) is not None:
                        partner.write({
                            'l10n_tr_nilvera_customer_status': 'earchive' if partner.vat else 'not_checked',
                            'l10n_tr_nilvera_customer_alias_id': False,
                            'qnb_last_check_date': fields.Datetime.now(),
                        })
                    skipped += 1
                    continue

                user = result['users'][0]
                title = (user.get('title') or '').strip()
                alias_name = (user.get('alias') or '').strip()

                vals = {
                    'l10n_tr_nilvera_customer_status': 'einvoice',
                    'qnb_last_check_date': fields.Datetime.now(),
                }
                if title and (partner.name or '').strip() != title:
                    vals['name'] = title
                    updated_name += 1
                if alias_name:
                    alias_rec = Alias.search([
                        ('partner_id', '=', partner.id),
                        ('name', '=', alias_name),
                    ], limit=1)
                    if not alias_rec:
                        alias_rec = Alias.create({'name': alias_name, 'partner_id': partner.id})
                        updated_alias += 1
                    vals['l10n_tr_nilvera_customer_alias_id'] = alias_rec.id
                else:
                    vals['l10n_tr_nilvera_customer_alias_id'] = False
                partner.write(vals)

                # XML'den adres, iletişim, vergi dairesi vb. güncelle (bu partner için QNB'de belge varsa)
                partner_data = partner._get_latest_qnb_partner_data()
                if partner_data:
                    partner._normalize_city_state_partner_data(partner_data)
                    partner._apply_qnb_partner_data(partner_data, skip_name=True)
                    updated_xml += 1
            except Exception as e:
                errors += 1
                _logger.warning("QNB mükellef güncelleme hatası partner id=%s: %s", partner.id, e)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('QNB Mükellef ile Güncelle'),
                'message': (
                    _('İşlenen: %s | Ünvan: %s | Alias: %s | XML (adres/iletişim): %s | Atlandı: %s | Hata: %s')
                    % (processed, updated_name, updated_alias, updated_xml, skipped, errors)
                ),
                'type': 'success' if (updated_name or updated_alias or updated_xml) else 'info',
                'sticky': False,
            },
        }

    def action_update_title_from_qnb(self):
        """QNB (kayıtlı kullanıcı) sorgusu ile ünvanı güncelle (VKN/TCKN ile) — eski davranış; mükellef güncelleme için action_update_from_qnb_mukellef kullanın."""
        return self.action_update_from_qnb_mukellef()

    def action_update_from_qnb_xml(self):
        """QNB XML içeriğinden partner bilgilerini güncelle (seçili partner için). Önce yerel belgeler, yoksa QNB'den indirilir."""
        self.ensure_one()

        if not self.vat:
            raise UserError(_("VKN/TCKN bilgisi girilmemiş!"))

        digits = ''.join(filter(str.isdigit, str(self.vat)))
        if len(digits) not in (10, 11):
            raise UserError(_("Geçersiz VKN/TCKN!"))

        vat_number = f"TR{digits}"
        QnbDoc = self.env['qnb.document']

        # Önce yerel XML'den güncelle (ortak yardımcı kullan)
        partner_data = self._get_latest_qnb_partner_data()
        if partner_data:
            self._normalize_city_state_partner_data(partner_data)
            self._apply_qnb_partner_data(partner_data, skip_name=False)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'QNB XML Güncelle',
                    'message': '✅ Partner bilgileri XML\'den güncellendi.',
                    'type': 'success',
                    'sticky': False,
                },
            }

        # Yerel belge yoksa QNB'den indirip dene
        api_client = self.env['qnb.api.client'].with_company(self.company_id)
        from datetime import date

        def parse_date(s):
            if not s:
                return None
            s = str(s)
            if len(s) == 8 and s.isdigit():
                return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
            return None

        def pick_best(items):
            items = [(parse_date(i.get('date')), i) for i in items if i.get('date')]
            items = [it for it in items if it[0]]
            items.sort(key=lambda x: x[0], reverse=True)
            return items[0][1] if items else None

        start = date(date.today().year - 2, 1, 1)
        end = date.today()
        incoming_types = ['EFATURA', 'IRSALIYE', 'UYGULAMA_YANITI', 'IRSALIYE_YANITI']
        outgoing_types = ['FATURA_UBL', 'FATURA', 'IRSALIYE_UBL', 'IRSALIYE',
                          'UYGULAMA_YANITI_UBL', 'UYGULAMA_YANITI', 'IRSALIYE_YANITI_UBL', 'IRSALIYE_YANITI']
        match = None
        match_direction = None
        match_type = None

        for t in incoming_types:
            res = api_client.get_incoming_documents(start, end, document_type=t, company=self.company_id)
            if res.get('success'):
                docs_list = [d for d in res.get('documents', []) if ''.join(filter(str.isdigit, str(d.get('sender_vkn', '')))) == digits]
                cand = pick_best(docs_list)
                if cand:
                    match = cand
                    match_direction = 'incoming'
                    match_type = t
                    break

        if not match:
            for t in outgoing_types:
                res = api_client.get_outgoing_documents(start, end, document_type=t, company=self.company_id)
                if res.get('success'):
                    docs_list = [d for d in res.get('documents', []) if ''.join(filter(str.isdigit, str(d.get('recipient_vkn', '')))) == digits]
                    cand = pick_best(docs_list)
                    if cand:
                        match = cand
                        match_direction = 'outgoing'
                        match_type = t
                        break

        if not match or not match.get('ettn'):
            raise UserError(_("Bu partner için QNB listesinde eşleşen belge bulunamadı."))

        ettn = match.get('ettn')
        if match_direction == 'incoming':
                xml_result = api_client.download_incoming_document(ettn, match_type, self.company_id)
                xml_bytes = xml_result.get('content') if xml_result and xml_result.get('success') else None
            else:
                download_type = match_type.replace('_UBL', '') if match_type else 'FATURA'
                xml_result = api_client.download_outgoing_document(ettn, document_type=download_type, company=self.company_id)
                xml_bytes = xml_result.get('content') if xml_result and xml_result.get('success') else None

            if not xml_bytes:
                raise UserError(_("QNB’den XML indirilemedi."))

            parsed = QnbDoc._parse_invoice_xml_full(xml_bytes, direction=match_direction)
            partner_data = (parsed or {}).get('partner') or {}
            vat_raw = partner_data.get('vat') or ''
            doc_digits = ''.join(filter(str.isdigit, str(vat_raw)))
            doc_vat = f"TR{doc_digits}" if doc_digits else False

            if doc_vat != vat_number:
                raise UserError(_("QNB XML içinde VKN eşleşmedi."))

            self._normalize_city_state_partner_data(partner_data)
            self._apply_qnb_partner_data(partner_data, skip_name=False)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QNB XML Güncelle',
                'message': '✅ Partner bilgileri XML’den güncellendi.',
                'type': 'success',
                'sticky': False,
            }
        }

    def _compute_balance_2025(self):
        """2019-2025 hareketlerinden 31.12.2025 itibarıyla bakiye"""
        cutoff = fields.Date.to_date('2025-12-31')
        company = self.env.company
        for partner in self:
            domain_base = [
                ('partner_id', '=', partner.id),
                ('company_id', '=', company.id),
                ('move_id.state', '=', 'posted'),
                ('date', '<=', cutoff),
            ]

            recv_domain = domain_base + [('account_id.account_type', '=', 'asset_receivable')]
            pay_domain = domain_base + [('account_id.account_type', '=', 'liability_payable')]

            recv = self.env['account.move.line'].read_group(recv_domain, ['balance'], []) or []
            pay = self.env['account.move.line'].read_group(pay_domain, ['balance'], []) or []

            receivable = recv[0]['balance'] if recv else 0.0
            payable = pay[0]['balance'] if pay else 0.0

            # receivable >0, payable <0 olabilir; neti normalize et
            partner.balance_2025_receivable = receivable
            partner.balance_2025_payable = -payable if payable < 0 else payable
            partner.balance_2025_net = receivable + payable

    @api.model
    def _cron_check_efatura_status(self):
        from datetime import datetime, timedelta
        started = datetime.now()
        time_budget_seconds = 45
        thirty_days_ago = started - timedelta(days=30)

        partners = self.search([
            ('vat', '!=', False),
            ('l10n_tr_nilvera_customer_status', 'in', ('not_checked', 'earchive', 'einvoice')),
            '|',
            ('qnb_last_check_date', '=', False),
            ('qnb_last_check_date', '<', thirty_days_ago)
        ], limit=20, order='qnb_last_check_date asc')  # küçük batch: timeout/lock azaltır

        for partner in partners:
            if (datetime.now() - started).total_seconds() > time_budget_seconds:
                break
            try:
                partner._check_qnb_customer()
            except Exception:
                continue

        return True
