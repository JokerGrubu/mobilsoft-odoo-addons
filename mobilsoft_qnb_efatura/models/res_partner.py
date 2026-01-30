# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # e-Fatura Bilgileri
    is_efatura_registered = fields.Boolean(
        string='e-Fatura Kayıtlı',
        default=False,
        help='Bu firma GİB e-Fatura sistemine kayıtlı mı?'
    )
    efatura_alias = fields.Char(
        string='e-Fatura Posta Kutusu',
        help='Alıcının e-Fatura posta kutusu etiketi (örn: urn:mail:defaultpk@xxx.com)'
    )
    efatura_alias_type = fields.Selection([
        ('pk', 'Posta Kutusu (PK)'),
        ('gb', 'Gönderici Birimi (GB)')
    ], string='Etiket Tipi', default='pk',
        help='Posta Kutusu: Normal kullanıcı\nGönderici Birimi: Entegratör')

    efatura_registration_date = fields.Date(
        string='e-Fatura Kayıt Tarihi',
        help='GİB sistemine kayıt tarihi'
    )
    efatura_last_check = fields.Datetime(
        string='Son Kontrol Tarihi',
        help='e-Fatura kaydı son kontrol edilme tarihi'
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

    @api.depends('is_efatura_registered', 'vat')
    def _compute_invoice_send_method(self):
        for partner in self:
            if partner.is_efatura_registered:
                partner.invoice_send_method = 'efatura'
            elif partner.vat:
                partner.invoice_send_method = 'earsiv'
            else:
                partner.invoice_send_method = 'manual'

    def action_check_efatura_status(self):
        """e-Fatura kayıt durumunu kontrol et"""
        self.ensure_one()

        if not self.vat:
            raise UserError(_("VKN/TCKN bilgisi girilmemiş!"))

        # VKN'den sadece rakamları al
        vkn = ''.join(filter(str.isdigit, self.vat))

        api_client = self.env['qnb.api.client']
        result = api_client.check_registered_user(vkn)

        if result.get('success') and result.get('users'):
            users = result['users']
            if users:
                user = users[0]
                self.write({
                    'is_efatura_registered': True,
                    'efatura_alias': user.get('alias', ''),
                    'efatura_registration_date': user.get('first_creation_time', False),
                    'efatura_last_check': fields.Datetime.now()
                })
                message = f"✅ {self.name} e-Fatura sistemine kayıtlı!\nPosta Kutusu: {user.get('alias', '-')}"
            else:
                self.write({
                    'is_efatura_registered': False,
                    'efatura_alias': False,
                    'efatura_last_check': fields.Datetime.now()
                })
                message = f"ℹ️ {self.name} e-Fatura sistemine kayıtlı değil."
        else:
            self.write({
                'is_efatura_registered': False,
                'efatura_alias': False,
                'efatura_last_check': fields.Datetime.now()
            })
            message = result.get('message', 'Kayıtlı kullanıcı bulunamadı')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'e-Fatura Kayıt Durumu',
                'message': message,
                'type': 'success' if self.is_efatura_registered else 'warning',
                'sticky': False,
            }
        }

    def action_update_title_from_qnb(self):
        """QNB (kayıtlı kullanıcı) sorgusu ile ünvanı güncelle (VKN/TCKN ile)"""
        api_client = self.env['qnb.api.client']

        def is_placeholder_name(current_name, vat_number):
            current_name = (current_name or '').strip()
            if not current_name:
                return True
            if current_name.startswith(('Firma ', 'Tedarikçi ', 'VKN:')):
                return True
            if vat_number and current_name == vat_number:
                return True
            return False

        processed = 0
        updated = 0
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

                result = api_client.check_registered_user(digits)
                if not (result.get('success') and result.get('users')):
                    skipped += 1
                    continue

                title = (result['users'][0].get('title') or '').strip()
                if not title:
                    skipped += 1
                    continue

                if is_placeholder_name(partner.name, partner.vat) and (partner.name or '').strip() != title:
                    partner.write({'name': title})
                    updated += 1
                else:
                    skipped += 1
            except Exception:
                errors += 1
                continue

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QNB Ünvan Güncelle',
                'message': (
                    f'Partner: {processed}\n'
                    f'Güncellendi: {updated}\n'
                    f'Atlandı: {skipped}\n'
                    f'Hata: {errors}'
                ),
                'type': 'success' if updated else 'info',
                'sticky': False,
            }
        }

    def action_update_from_qnb_xml(self):
        """QNB XML içeriğinden partner bilgilerini güncelle (seçili partner için)"""
        self.ensure_one()

        if not self.vat:
            raise UserError(_("VKN/TCKN bilgisi girilmemiş!"))

        digits = ''.join(filter(str.isdigit, str(self.vat)))
        if len(digits) not in (10, 11):
            raise UserError(_("Geçersiz VKN/TCKN!"))

        vat_number = f"TR{digits}"
        QnbDoc = self.env['qnb.document']

        # Öncelik: partner_id bağlı belgeler
        docs = QnbDoc.search([
            ('partner_id', '=', self.id),
            ('xml_content', '!=', False),
        ], order='document_date desc, id desc', limit=50)

        # Bağlı belge yoksa son 50 XML belge içinde VKN eşleştir
        if not docs:
            docs = QnbDoc.search([
                ('xml_content', '!=', False),
            ], order='document_date desc, id desc', limit=50)

        def normalize_city_state(data):
            raw_city = (data.get('city') or '').strip()
            raw_state = (data.get('state') or '').strip()
            if raw_city and not raw_state and '/' in raw_city:
                parts = [p.strip() for p in raw_city.split('/') if p.strip()]
                if len(parts) >= 2:
                    data['city'] = parts[0]
                    data['state'] = parts[1]
            if raw_state and not raw_city and '/' in raw_state:
                parts = [p.strip() for p in raw_state.split('/') if p.strip()]
                if len(parts) >= 2:
                    data['city'] = parts[0]
                    data['state'] = parts[1]

        def apply_partner_update(partner_data):
            update_vals = {}
            name_raw = (partner_data.get('name') or '').strip()
            if name_raw and (self.name or '').strip() != name_raw:
                update_vals['name'] = name_raw

            for src_key, dst_key in [
                ('street', 'street'),
                ('street2', 'street2'),
                ('city', 'city'),
                ('zip', 'zip'),
                ('phone', 'phone'),
                ('email', 'email'),
                ('website', 'website'),
            ]:
                val = (partner_data.get(src_key) or '').strip()
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
                    bank_vals = {
                        'partner_id': self.id,
                        'acc_number': iban,
                    }
                    if 'company_id' in Bank._fields and self.company_id:
                        bank_vals['company_id'] = self.company_id.id
                    bank_name = (partner_data.get('bank_name') or '').strip()
                    if bank_name and 'bank_id' in Bank._fields:
                        bank = self.env['res.bank'].search([('name', 'ilike', bank_name)], limit=1)
                        if bank:
                            bank_vals['bank_id'] = bank.id
                    Bank.create(bank_vals)

        updated = False
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

            if doc_vat != vat_number:
                continue

            normalize_city_state(partner_data)
            apply_partner_update(partner_data)
            updated = True
            break

        if not updated:
            # XML yoksa QNB'den indirip dene
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

            normalize_city_state(partner_data)
            apply_partner_update(partner_data)
            updated = True

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

    @api.model
    def _cron_check_efatura_status(self):
        """Zamanlanmış görev: Tüm partnerlerin e-Fatura durumunu kontrol et"""
        # VKN'si olan ve son 30 gündür kontrol edilmemiş partnerler
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)

        partners = self.search([
            ('vat', '!=', False),
            '|',
            ('efatura_last_check', '=', False),
            ('efatura_last_check', '<', thirty_days_ago)
        ], limit=100)  # Her seferde 100 partner

        for partner in partners:
            try:
                partner.action_check_efatura_status()
            except Exception:
                continue

        return True
