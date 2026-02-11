# -*- coding: utf-8 -*-

import uuid
import base64
import logging
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # QNB e-Belge Bilgileri
    qnb_document_ids = fields.One2many(
        'qnb.document',
        'move_id',
        string='e-Belgeler'
    )
    qnb_document_count = fields.Integer(
        string='e-Belge Sayısı',
        compute='_compute_qnb_document_count'
    )

    qnb_state = fields.Selection([
        ('not_sent', 'Gönderilmedi'),
        ('sending', 'Gönderiliyor'),
        ('sent', 'Gönderildi'),
        ('delivered', 'Teslim Edildi'),
        ('accepted', 'Kabul Edildi'),
        ('rejected', 'Reddedildi'),
        ('error', 'Hata')
    ], string='e-Belge Durumu', default='not_sent', tracking=True)

    qnb_ettn = fields.Char(
        string='ETTN',
        help='Evrensel Tekil Tanımlayıcı Numara',
        copy=False
    )
    qnb_uuid = fields.Char(
        string='QNB UUID',
        copy=False
    )
    qnb_document_type = fields.Selection([
        ('efatura', 'e-Fatura'),
        ('earsiv', 'e-Arşiv'),
        ('manual', 'Manuel')
    ], string='e-Belge Türü', compute='_compute_qnb_document_type', store=True)

    @api.depends('qnb_document_ids')
    def _compute_qnb_document_count(self):
        for move in self:
            move.qnb_document_count = len(move.qnb_document_ids)

    @api.depends('partner_id', 'partner_id.l10n_tr_nilvera_customer_status')
    def _compute_qnb_document_type(self):
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund'):
                if getattr(move.partner_id, 'l10n_tr_nilvera_customer_status', None) == 'einvoice':
                    move.qnb_document_type = 'efatura'
                else:
                    move.qnb_document_type = 'earsiv'
            else:
                move.qnb_document_type = 'manual'

    def action_view_qnb_documents(self):
        self.ensure_one()
        raise UserError(_("QNB e-Belge ekranı devre dışı. Lütfen standart gönderim ekranını kullanın."))

    def action_send_efatura(self):
        self.ensure_one()
        raise UserError(_("QNB gönderimi artık standart EDI akışı üzerinden yapılmaktadır. Lütfen gönderim ekranını kullanın."))

    def action_send_earsiv(self):
        self.ensure_one()
        raise UserError(_("QNB gönderimi artık standart EDI akışı üzerinden yapılmaktadır. Lütfen gönderim ekranını kullanın."))

    def action_check_qnb_status(self):
        self.ensure_one()
        if not self.qnb_ettn:
            raise UserError(_("ETTN bilgisi bulunamadı!"))
        status_result = self._qnb_update_status_from_api()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QNB Durum',
                'message': status_result.get('status_description') or status_result.get('status') or 'OK',
                'type': 'success' if status_result.get('success') else 'warning',
                'sticky': False,
            }
        }

    def action_open_send_wizard(self):
        self.ensure_one()
        raise UserError(_("QNB gönderimi standart EDI akışına taşındı."))

    @api.model
    def cron_check_qnb_status(self):
        return self._cron_qnb_get_invoice_status()

    def _get_import_file_type(self, file_data):
        """QNB UBL-TR dosyaları Nilvera ile aynı Odoo UBL import akışını kullanır."""
        # EXTENDS 'account' — TR1.2 için Nilvera formatı (account.edi.xml.ubl.tr) kullan
        if (
            file_data['xml_tree'] is not None
            and (customization_id := file_data['xml_tree'].findtext('{*}CustomizationID'))
            and 'TR1.2' in customization_id
        ):
            return 'account.edi.xml.ubl.tr'
        return super()._get_import_file_type(file_data)

    @api.model
    def _get_ubl_cii_builder_from_xml_tree(self, tree):
        """XML ağacından UBL builder seç (Nilvera uyumlu)"""
        customization_id = tree.find('{*}CustomizationID')
        if customization_id is not None and 'TR1.2' in customization_id.text:
            return self.env['account.edi.xml.ubl.tr.qnb']
        return super()._get_ubl_cii_builder_from_xml_tree(tree)

    def button_draft(self):
        """Gönderilmiş faturanın draft yapılmasını engelle (Nilvera uyumlu)"""
        # EXTENDS account
        for move in self.filtered('qnb_uuid'):
            if move.qnb_state == 'error':
                move.message_post(body=_(
                    "Muhasebe bütünlüğünü korumak ve yasal gerekliliklere uymak için, "
                    "hata oluşan faturalar yeniden kullanılamaz. Lütfen yeni bir fatura oluşturun."
                ))
            elif move.qnb_state != 'not_sent':
                raise UserError(_(
                    "QNB'ye gönderilmiş bir faturayı taslak durumuna döndüremezsiniz."
                ))
        return super().button_draft()

    def _post(self, soft=True):
        for move in self:
            # Hatalı durumda yeniden onaylamayı engelle (Nilvera uyumlu)
            if move.qnb_state == 'error' and move.qnb_uuid:
                raise UserError(_(
                    "Muhasebe bütünlüğünü korumak ve yasal gerekliliklere uymak için, "
                    "hata oluşan faturalar yeniden kullanılamaz. Lütfen yeni bir fatura oluşturun."
                ))
            if move.country_code == 'TR' and not move.qnb_uuid:
                move.qnb_uuid = str(uuid.uuid4())

        result = super()._post(soft=soft)

        # Post sonrası PDF oluştur (Nilvera gibi)
        for move in self:
            if move.qnb_ettn and move.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                try:
                    move._qnb_generate_odoo_pdf()
                except Exception as e:
                    _logger.warning(f"Fatura {move.name} için PDF oluşturma hatası: {str(e)}")

        return result

    def _qnb_types_to_update_status(self):
        """Durum güncellemesi yapılacak fatura türleri"""
        return ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']

    def _qnb_check_negative_lines(self):
        return any(
            line.display_type not in {'line_note', 'line_section'}
            and (line.quantity < 0 or line.price_unit < 0)
            for line in self.invoice_line_ids
        )

    def _qnb_is_einvoice(self):
        self.ensure_one()
        if not self.partner_id.vat:
            return False
        if getattr(self.partner_id, 'l10n_tr_nilvera_customer_status', None) == 'not_checked':
            self.partner_id._check_qnb_customer()
        return getattr(self.partner_id, 'l10n_tr_nilvera_customer_status', None) == 'einvoice'

    def _qnb_get_partner_vkn(self):
        self.ensure_one()
        if not self.partner_id.vat:
            raise UserError(_("Müşteri VKN/TCKN bilgisi eksik!"))
        digits = ''.join(filter(str.isdigit, self.partner_id.vat))
        if not digits:
            raise UserError(_("Müşteri VKN/TCKN bilgisi eksik!"))
        return digits

    def _qnb_get_send_document_type(self):
        return 'FATURA_UBL' if self._qnb_is_einvoice() else 'EARSIV_FATURA'

    def _qnb_get_status_document_type(self):
        if self.qnb_document_type == 'efatura':
            return 'EFATURA'
        if self.qnb_document_type == 'earsiv':
            return 'EARSIV'
        return 'EFATURA' if self._qnb_is_einvoice() else 'EARSIV'

    def _qnb_send_ubl(self, xml_data):
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(_("Sadece onaylanmış faturalar gönderilebilir!"))
        if self.qnb_state not in ('not_sent', 'error'):
            raise UserError(_("Bu fatura zaten gönderilmiş veya işlem bekliyor!"))
        if not self.qnb_uuid:
            self.qnb_uuid = str(uuid.uuid4())

        api_client = self.env['qnb.api.client']
        vkn = self._qnb_get_partner_vkn()
        is_einvoice = self._qnb_is_einvoice()

        if is_einvoice and not self.company_id.qnb_efatura_enabled:
            raise UserError(_("QNB e-Fatura gönderimi ayarlarda kapalı!"))
        if not is_einvoice and not self.company_id.qnb_earsiv_enabled:
            raise UserError(_("QNB e-Arşiv gönderimi ayarlarda kapalı!"))

        if is_einvoice:
            result = api_client.send_invoice(
                xml_data,
                self.name,
                vkn,
                self.company_id,
                document_type='FATURA_UBL'
            )
        else:
            result = api_client.send_earchive_invoice(
                xml_data,
                self.name,
                self.company_id
            )

        if result.get('success'):
            self.write({
                'qnb_state': 'sent',
                'qnb_ettn': result.get('ettn'),
            })
            self.message_post(body=_("QNB e-Belgesi başarıyla gönderildi."))
            return result

        self.write({'qnb_state': 'error'})
        raise UserError(result.get('message', 'QNB gönderim hatası'))

    def _qnb_update_status_from_api(self):
        self.ensure_one()
        api_client = self.env['qnb.api.client']
        result = api_client.get_document_status(
            self.qnb_ettn,
            self._qnb_get_status_document_type(),
            self.company_id
        )

        if result.get('success'):
            status = (result.get('status') or '').upper()
            state_map = {
                'GONDERILDI': 'sent',
                'TESLIM_ALINDI': 'delivered',
                'KABUL': 'accepted',
                'RED': 'rejected',
                'HATA': 'error',
                'IPTAL': 'rejected',
            }
            new_state = state_map.get(status)
            if new_state and new_state != self.qnb_state:
                self.write({'qnb_state': new_state})
        return result

    def _qnb_add_pdf_to_invoice(self, pdf_content):
        self.ensure_one()
        if not pdf_content:
            return
        if isinstance(pdf_content, str):
            pdf_content = pdf_content.encode('utf-8')
        attachment = self.env['ir.attachment'].create({
            'name': f'{self.name}.pdf',
            'res_id': self.id,
            'res_model': 'account.move',
            'raw': pdf_content,
            'type': 'binary',
            'mimetype': 'application/pdf',
        })
        self.message_main_attachment_id = attachment
        self.with_context(no_new_invoice=True).message_post(attachment_ids=attachment.ids)

    def _qnb_fetch_outgoing_pdf(self):
        self.ensure_one()
        api_client = self.env['qnb.api.client']
        result = api_client.download_outgoing_document(
            self.qnb_ettn,
            document_type=self._qnb_get_send_document_type(),
            company=self.company_id,
            format_type='PDF'
        )
        if result.get('success'):
            self._qnb_add_pdf_to_invoice(result.get('content'))

    def _qnb_fetch_incoming_pdf(self):
        """Gelen e-fatura PDF'ini QNB'den indir ve faturaya ekle"""
        self.ensure_one()
        if not self.qnb_ettn:
            return
        api_client = self.env['qnb.api.client']
        result = api_client.download_document_pdf(
            self.qnb_ettn,
            document_type='EFATURA',
            company=self.company_id
        )
        if result.get('success'):
            self._qnb_add_pdf_to_invoice(result.get('content'))

    def _qnb_generate_odoo_pdf(self):
        """Odoo'nun standart fatura PDF'ini oluştur ve ekle (Nilvera tarzı)"""
        self.ensure_one()

        # Zaten PDF var mı kontrol et
        existing_pdf = self.env['ir.attachment'].search([
            ('res_model', '=', 'account.move'),
            ('res_id', '=', self.id),
            ('mimetype', '=', 'application/pdf'),
        ], limit=1)

        if existing_pdf:
            # PDF zaten var, tekrar oluşturma
            return

        try:
            # Odoo'nun standart fatura raporunu al
            report = self.env.ref('account.account_invoices', raise_if_not_found=False)
            if not report:
                _logger.warning(f"Fatura raporu bulunamadı: {self.name}")
                return

            # PDF oluştur
            pdf_content, _ = report._render_qweb_pdf([self.id])
            if pdf_content:
                attachment = self.env['ir.attachment'].create({
                    'name': f'{self.name or "INV"}.pdf',
                    'res_id': self.id,
                    'res_model': 'account.move',
                    'raw': pdf_content,
                    'type': 'binary',
                    'mimetype': 'application/pdf',
                })
                # Ana attachment olarak ayarla
                self.message_main_attachment_id = attachment.id
                # Chatter'a da ekle
                self.with_context(no_new_invoice=True).message_post(
                    body=_("PDF oluşturuldu"),
                    attachment_ids=[attachment.id]
                )
        except Exception as e:
            _logger.error(f"PDF oluşturma hatası ({self.name}): {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())

    def action_qnb_download_pdf(self):
        """QNB'nin resmi PDF'ini indir (opsiyonel - Odoo PDF zaten var)"""
        for move in self:
            if not move.qnb_ettn:
                continue
            try:
                if move.move_type in ('out_invoice', 'out_refund'):
                    move._qnb_fetch_outgoing_pdf()
                elif move.move_type in ('in_invoice', 'in_refund'):
                    move._qnb_fetch_incoming_pdf()
            except Exception as e:
                raise UserError(f"QNB PDF indirme hatası: {str(e)}")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Başarılı',
                'message': f'{len(self)} fatura için QNB resmi PDF indirildi.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_qnb_generate_pdf(self):
        """Odoo PDF'i oluştur (tüm faturalar için toplu kullanım)"""
        success_count = 0
        error_count = 0

        for move in self:
            try:
                move._qnb_generate_odoo_pdf()
                success_count += 1
            except Exception as e:
                error_count += 1
                _logger.warning(f"PDF oluşturma hatası - Fatura {move.name}: {str(e)}")

        if error_count > 0:
            message = f'{success_count} başarılı, {error_count} hatalı'
            msg_type = 'warning'
        else:
            message = f'{success_count} fatura için PDF oluşturuldu'
            msg_type = 'success'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'PDF Oluşturma Tamamlandı',
                'message': message,
                'type': msg_type,
                'sticky': False,
            }
        }

    def _qnb_get_purchase_journal(self, company):
        return self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', company.id),
        ], limit=1)

    def _qnb_get_sale_journal(self, company):
        return self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id),
        ], limit=1)

    def _qnb_get_last_fetch_date(self, company):
        param_key = f"qnb_incoming_last_fetch_date.{company.id}"
        last_fetched_date = self.env['ir.config_parameter'].sudo().get_param(param_key)
        if not last_fetched_date:
            last_fetched_date = (fields.Date.today() - relativedelta(months=1)).strftime("%Y-%m-%d")
            self.env['ir.config_parameter'].sudo().set_param(param_key, last_fetched_date)
        return last_fetched_date

    def _qnb_set_last_fetch_date(self, company, value):
        param_key = f"qnb_incoming_last_fetch_date.{company.id}"
        self.env['ir.config_parameter'].sudo().set_param(param_key, value)

    def _qnb_get_outgoing_last_fetch_date(self, company):
        param_key = f"qnb_outgoing_last_fetch_date.{company.id}"
        last_fetched_date = self.env['ir.config_parameter'].sudo().get_param(param_key)
        if not last_fetched_date:
            last_fetched_date = (fields.Date.today() - relativedelta(months=1)).strftime("%Y-%m-%d")
            self.env['ir.config_parameter'].sudo().set_param(param_key, last_fetched_date)
        return fields.Date.from_string(last_fetched_date)

    def _qnb_set_outgoing_last_fetch_date(self, company, value):
        param_key = f"qnb_outgoing_last_fetch_date.{company.id}"
        if not isinstance(value, str):
            value = fields.Date.to_string(value)
        self.env['ir.config_parameter'].sudo().set_param(param_key, value)

    def _qnb_find_or_create_partner_from_data(self, company, partner_data, fallback_data, is_einvoice):
        Partner = self.env['res.partner']
        match_by = company.qnb_match_partner_by or 'vat'
        create_new = company.qnb_create_new_partner

        vat = (partner_data.get('vat') or fallback_data.get('vat') or '').strip()
        name = (partner_data.get('name') or fallback_data.get('name') or '').strip()
        email = (partner_data.get('email') or '').strip()
        phone = (partner_data.get('phone') or '').strip()

        partner = None
        if vat and match_by in ('vat', 'both'):
            vat_number = vat if str(vat).upper().startswith('TR') else f"TR{vat}"
            partner = Partner.search([
                ('vat', 'ilike', vat_number),
                '|',
                ('company_id', '=', company.id),
                ('company_id', '=', False)
            ], limit=1)

        if not partner and name and match_by in ('name', 'both'):
            partner = Partner.search([
                ('name', 'ilike', name),
                '|',
                ('company_id', '=', company.id),
                ('company_id', '=', False)
            ], limit=1)

        if partner:
            return partner

        if create_new and (vat or name):
            vat_number = vat if str(vat).upper().startswith('TR') else (f"TR{vat}" if vat else False)
            create_vals = {
                'name': name or (f'Firma {vat}' if vat else 'Firma'),
                'vat': vat_number,
                'is_company': True,
                'customer_rank': 1,
                'supplier_rank': 1,
                'l10n_tr_nilvera_customer_status': 'einvoice' if (is_einvoice and vat) else ('earchive' if vat else 'not_checked'),
            }
            if email:
                create_vals['email'] = email
            if phone:
                create_vals['phone'] = phone
            if partner_data.get('street'):
                create_vals['street'] = (partner_data.get('street') or '').strip()
            if partner_data.get('street2'):
                create_vals['street2'] = (partner_data.get('street2') or '').strip()
            if partner_data.get('city'):
                create_vals['city'] = (partner_data.get('city') or '').strip()
            if partner_data.get('zip'):
                create_vals['zip'] = (partner_data.get('zip') or '').strip()
            if partner_data.get('website'):
                create_vals['website'] = (partner_data.get('website') or '').strip()
            if partner_data.get('country'):
                country = self.env['res.country'].search([
                    ('name', 'ilike', (partner_data.get('country') or '').strip())
                ], limit=1)
                if country:
                    create_vals['country_id'] = country.id
                    if partner_data.get('state'):
                        state = self.env['res.country.state'].search([
                            ('country_id', '=', country.id),
                            ('name', 'ilike', (partner_data.get('state') or '').strip())
                        ], limit=1)
                        if state:
                            create_vals['state_id'] = state.id
            elif not create_vals.get('country_id'):
                create_vals['country_id'] = self.env.ref('base.tr').id
            if partner_data.get('tax_office') and 'l10n_tr_tax_office_id' in Partner._fields:
                tax_office = (partner_data.get('tax_office') or '').strip()
                if tax_office:
                    tax_rec = self.env['l10n.tr.tax.office'].search([
                        ('name', 'ilike', tax_office)
                    ], limit=1)
                    if tax_rec:
                        create_vals['l10n_tr_tax_office_id'] = tax_rec.id
            partner = Partner.create(create_vals)
            if is_einvoice and partner and partner_data.get('alias'):
                alias_name = (partner_data.get('alias') or '').strip()
                if alias_name:
                    Alias = self.env['l10n_tr.nilvera.alias']
                    alias = Alias.create({'name': alias_name, 'partner_id': partner.id})
                    partner.l10n_tr_nilvera_customer_alias_id = alias
            return partner

        return False

    def _qnb_find_or_create_product_from_line(self, company, line_data, partner=None):
        Product = self.env['product.product']
        create_new = company.qnb_create_new_product

        product_code = (line_data.get('product_code') or '').strip()
        product_name = (line_data.get('product_name') or line_data.get('product_description') or '').strip()
        barcode = (line_data.get('barcode') or '').strip()

        if product_code and partner:
            si = self.env['product.supplierinfo'].search([
                ('partner_id', '=', partner.id),
                ('product_code', '=', product_code),
            ], limit=1)
            if si and si.product_tmpl_id:
                product = Product.search([('product_tmpl_id', '=', si.product_tmpl_id.id)], limit=1)
                if product:
                    return product

        if product_code:
            product = Product.search([('default_code', '=', product_code)], limit=1)
            if product:
                return product

        if barcode:
            product = Product.search([('barcode', '=', barcode)], limit=1)
            if product:
                return product

        if product_name:
            product = Product.search([('name', '=', product_name)], limit=1)
            if product:
                return product
            product = Product.search([('name', 'ilike', product_name)], limit=1)
            if product:
                return product

        if create_new and product_name:
            vals = {
                'name': product_name,
                'sale_ok': True,
                'purchase_ok': True,
            }
            if product_code:
                vals['default_code'] = product_code
            if barcode:
                vals['barcode'] = barcode
            new_product = Product.create(vals)
            if partner and product_code and new_product.product_tmpl_id:
                self.env['product.supplierinfo'].create({
                    'product_tmpl_id': new_product.product_tmpl_id.id,
                    'partner_id': partner.id,
                    'product_code': product_code,
                })
            return new_product

        return False

    def _qnb_find_tax(self, company, tax_percent, tax_use='sale'):
        if not tax_percent:
            return False
        return self.env['account.tax'].search([
            ('type_tax_use', '=', tax_use),
            ('amount', '=', tax_percent),
            ('company_id', '=', company.id)
        ], limit=1)

    def _qnb_normalize_xml_bytes(self, payload):
        if not payload:
            return None
        xml_bytes = payload
        if isinstance(payload, str):
            try:
                decoded = base64.b64decode(payload, validate=True)
                if decoded.strip().startswith((b'<', b'PK')):
                    xml_bytes = decoded
                else:
                    xml_bytes = payload.encode('utf-8')
            except Exception:
                xml_bytes = payload.encode('utf-8')
        elif isinstance(payload, (bytes, bytearray)):
            try:
                decoded = base64.b64decode(payload, validate=True)
                if decoded.strip().startswith((b'<', b'PK')):
                    xml_bytes = decoded
            except Exception:
                xml_bytes = payload
        return xml_bytes

    def _qnb_extract_uuid_from_xml(self, xml_bytes):
        """UBL-TR XML'den UUID değerini çıkar (Nilvera ile aynı yapı)."""
        try:
            from lxml import etree
            root = etree.fromstring(xml_bytes)
            uuid_val = root.findtext('.//{*}UUID') or root.findtext('./{*}UUID')
            return (uuid_val or '').strip() or None
        except Exception:
            return None

    def _qnb_fetch_incoming_documents(self):
        """
        Gelen e-belgeleri QNB API'den çeker; Odoo UBL import akışı (Nilvera ile aynı) ile fatura oluşturur.
        """
        company = self.env.company
        api_client = self.env['qnb.api.client']
        start_date = self._qnb_get_last_fetch_date(company)
        end_date = fields.Date.today().strftime("%Y-%m-%d")

        result = api_client.get_incoming_documents(start_date, end_date, document_type='EFATURA', company=company)
        if not result.get('success'):
            return

        journal = self._qnb_get_purchase_journal(company)
        if not journal:
            return

        for doc in result.get('documents', []):
            ettn = doc.get('ettn')
            if not ettn:
                continue
            if self.search_count([('qnb_ettn', '=', ettn), ('company_id', '=', company.id)]) > 0:
                continue

            download = api_client.download_incoming_document(ettn, document_type='EFATURA', company=company)
            if not download.get('success'):
                continue
            if self.search_count([('qnb_ettn', '=', ettn), ('company_id', '=', company.id)]) > 0:
                continue

            xml_bytes = self._qnb_normalize_xml_bytes(download.get('content'))
            if not xml_bytes:
                continue

            # Nilvera ile aynı: attachment oluştur, Odoo UBL import ile fatura üret
            attachment = self.env['ir.attachment'].create({
                'name': f'{ettn}.xml',
                'raw': xml_bytes,
                'type': 'binary',
                'mimetype': 'application/xml',
            })

            uuid_val = self._qnb_extract_uuid_from_xml(xml_bytes)
            try:
                invoices = journal.with_context(
                    default_move_type='in_invoice',
                )._create_document_from_attachment(attachment.id)
            except Exception as e:
                _logger.warning(f"QNB UBL import hatası (ETTN: {ettn}): {e}")
                # Nilvera gibi: hata olursa boş fatura + attachment ile devam et
                invoices = self.env['account.move'].create({
                    'move_type': 'in_invoice',
                    'company_id': company.id,
                    'journal_id': journal.id,
                    'qnb_ettn': ettn,
                    'qnb_uuid': uuid_val,
                    'qnb_state': 'delivered',
                    'message_main_attachment_id': attachment.id,
                })
                attachment.write({'res_model': 'account.move', 'res_id': invoices.id})
                invoices.message_post(body=_("QNB belge UBL import sırasında hata oluştu. Manuel kontrol gerekebilir."))

            # QNB alanlarını her durumda güncelle
            for move in invoices:
                move.write({
                    'qnb_ettn': ettn,
                    'qnb_uuid': uuid_val or move.qnb_uuid,
                    'qnb_state': 'delivered',
                })

            for move in invoices:
                try:
                    move._qnb_generate_odoo_pdf()
                except Exception as e:
                    _logger.warning(f"PDF oluşturma hatası (ETTN: {ettn}): {str(e)}")

        self._qnb_set_last_fetch_date(company, end_date)

    def _qnb_fetch_outgoing_documents(self, batch_size=50):
        company = self.env.company
        api_client = self.env['qnb.api.client']
        start_date = self._qnb_get_outgoing_last_fetch_date(company)
        end_date = fields.Date.today()

        journal = self._qnb_get_sale_journal(company)
        if not journal:
            return

        doc_types = []
        if company.qnb_efatura_enabled or company.qnb_earsiv_enabled:
            doc_types.append('FATURA_UBL')

        processed = 0
        last_processed_date = None

        for doc_type in doc_types:
            current_start = start_date
            while current_start <= end_date:
                current_end = min(current_start + timedelta(days=89), end_date)
                result = api_client.get_outgoing_documents(current_start, current_end, document_type=doc_type, company=company)
                if not result.get('success'):
                    current_start = current_end + timedelta(days=1)
                    continue

                documents = result.get('documents', []) or []
                def _doc_date_key(d):
                    raw = d.get('date') or ''
                    return raw
                documents = sorted(documents, key=_doc_date_key)

                for doc in documents:
                    ettn = doc.get('ettn')
                    if not ettn:
                        continue
                    if self.search_count([('qnb_ettn', '=', ettn), ('company_id', '=', company.id)]) > 0:
                        continue

                    download_type = doc_type.replace('_UBL', '') if isinstance(doc_type, str) else doc_type
                    download = api_client.download_outgoing_document(ettn, document_type=download_type, company=company, format_type='UBL')
                    if not download.get('success'):
                        continue

                    xml_bytes = self._qnb_normalize_xml_bytes(download.get('content'))
                    if not xml_bytes:
                        continue

                    parsed = self.env['qnb.document']._parse_invoice_xml_full(xml_bytes, direction='outgoing')
                    partner_data = parsed.get('partner') or {}
                    fallback = {
                        'vat': (doc.get('recipient_vkn') or doc.get('receiver_vkn') or '').strip(),
                        'name': (doc.get('recipient_title') or doc.get('receiver_title') or '').strip(),
                    }
                    profile = (parsed.get('document_info') or {}).get('profile') or ''
                    is_einvoice = str(profile).upper() != 'EARSIVFATURA'
                    partner = self._qnb_find_or_create_partner_from_data(company, partner_data, fallback, is_einvoice)
                    if not partner:
                        continue

                    invoice_lines = []
                    for line in (parsed.get('lines') or []):
                        product = self._qnb_find_or_create_product_from_line(company, line, partner=partner)
                        qty = line.get('quantity') or 1.0
                        unit_price = line.get('unit_price')
                        if not unit_price and line.get('line_total') and qty:
                            unit_price = float(line.get('line_total')) / float(qty)

                        line_vals = {
                            'name': line.get('product_description') or line.get('product_name') or (product.name if product else 'Ürün'),
                            'quantity': qty,
                            'price_unit': unit_price or 0.0,
                        }
                        if product:
                            line_vals['product_id'] = product.id

                        tax = self._qnb_find_tax(company, line.get('tax_percent'))
                        if tax:
                            line_vals['tax_ids'] = [(6, 0, [tax.id])]

                        invoice_lines.append((0, 0, line_vals))

                    if not invoice_lines:
                        total_amount = doc.get('total') or (parsed.get('amounts') or {}).get('total') or 0.0
                        invoice_lines.append((0, 0, {
                            'name': doc.get('belge_no') or (parsed.get('document_info') or {}).get('invoice_id') or 'QNB Fatura',
                            'quantity': 1.0,
                            'price_unit': float(total_amount or 0.0),
                        }))

                    doc_date = None
                    doc_info = parsed.get('document_info') or {}
                    doc_date_raw = doc_info.get('issue_date') or doc.get('date')
                    if doc_date_raw:
                        try:
                            if isinstance(doc_date_raw, str) and len(doc_date_raw) == 8:
                                doc_date_raw = f"{doc_date_raw[:4]}-{doc_date_raw[4:6]}-{doc_date_raw[6:8]}"
                            doc_date = fields.Date.from_string(doc_date_raw)
                        except Exception:
                            doc_date = fields.Date.today()

                    currency_name = (doc_info.get('currency') or doc.get('currency') or 'TRY')
                    currency = self.env['res.currency'].search([('name', '=', currency_name)], limit=1)

                    move = self.env['account.move'].create({
                        'move_type': 'out_invoice',
                        'partner_id': partner.id,
                        'invoice_date': doc_date or fields.Date.today(),
                        'ref': doc.get('belge_no') or doc_info.get('invoice_id') or ettn,
                        'company_id': company.id,
                        'currency_id': currency.id if currency else company.currency_id.id,
                        'invoice_line_ids': invoice_lines,
                        'qnb_ettn': ettn,
                        'qnb_state': 'sent',
                        'qnb_uuid': doc_info.get('uuid') or False,
                        'journal_id': journal.id,
                    })

                    attachment = self.env['ir.attachment'].create({
                        'name': f'{ettn}.xml',
                        'res_id': move.id,
                        'res_model': 'account.move',
                        'raw': xml_bytes,
                        'type': 'binary',
                        'mimetype': 'application/xml',
                    })
                    move.message_post(body=_("QNB giden e-Belge içe aktarıldı."), attachment_ids=attachment.ids)

                    # Odoo PDF'i oluştur ve ekle (Nilvera gibi)
                    try:
                        move._qnb_generate_odoo_pdf()
                    except Exception as e:
                        _logger.warning(f"PDF oluşturma hatası (ETTN: {ettn}): {str(e)}")

                    processed += 1
                    if doc_date:
                        last_processed_date = doc_date
                    if processed >= batch_size:
                        break

                if processed >= batch_size:
                    break

                current_start = current_end + timedelta(days=1)

            if processed >= batch_size:
                break

        if last_processed_date:
            self._qnb_set_outgoing_last_fetch_date(company, last_processed_date)
        else:
            self._qnb_set_outgoing_last_fetch_date(company, end_date)

    def _cron_qnb_get_new_incoming_documents(self):
        companies = self.env['res.company'].search([
            ('qnb_enabled', '=', True),
            ('qnb_auto_fetch_incoming', '=', True),
            ('qnb_efatura_enabled', '=', True),
        ])
        for company in companies:
            self.with_company(company)._qnb_fetch_incoming_documents()

    def _cron_qnb_get_invoice_status(self):
        companies = self.env['res.company'].search([
            ('qnb_enabled', '=', True),
            ('qnb_auto_check_status', '=', True),
        ])
        if not companies:
            return
        invoices_to_update = self.search([
            # Duplike/ürün/partner önlemleri ile birlikte, delivered durumundakileri tekrar sorgulamak gereksiz
            # ve bazı eski belgelerde “bulunamadı” uyarılarını artırabiliyor.
            ('qnb_state', 'in', ['sent', 'sending']),
            ('qnb_ettn', '!=', False),
            ('company_id', 'in', companies.ids),
        ], limit=200)
        for invoice in invoices_to_update:
            invoice._qnb_update_status_from_api()

    def _cron_qnb_get_sale_pdf(self, batch_size=100):
        companies = self.env['res.company'].search([
            ('qnb_enabled', '=', True),
            ('qnb_auto_fetch_outgoing', '=', True),
        ])
        if not companies:
            return
        for company in companies:
            self.with_company(company)._qnb_fetch_outgoing_documents(batch_size=3)
        invoices = self.search([
            ('qnb_state', 'in', ['sent', 'delivered', 'accepted']),
            ('qnb_ettn', '!=', False),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('company_id', 'in', companies.ids),
        ], limit=batch_size)
        invoices_to_fetch = invoices.filtered(lambda m: m.message_main_attachment_id == m.invoice_pdf_report_id)
        for invoice in invoices_to_fetch:
            invoice._qnb_fetch_outgoing_pdf()
