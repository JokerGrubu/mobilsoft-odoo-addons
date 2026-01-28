# -*- coding: utf-8 -*-
"""
QNB e-Solutions Belge Modeli
Gelen ve giden belgelerin takibi
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)


class QnbDocument(models.Model):
    _name = 'qnb.document'
    _description = 'QNB e-Belge'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Belge No',
        required=True,
        tracking=True
    )
    ettn = fields.Char(
        string='ETTN',
        help='Evrensel Tekil Tanımlayıcı Numara',
        tracking=True,
        index=True
    )

    document_type = fields.Selection([
        ('efatura', 'e-Fatura'),
        ('earsiv', 'e-Arşiv'),
        ('eirsaliye', 'e-İrsaliye'),
        ('eirsaliye_yanit', 'e-İrsaliye Yanıtı'),
        ('uygulama_yanit', 'Uygulama Yanıtı')
    ], string='Belge Türü', required=True, default='efatura', tracking=True)

    direction = fields.Selection([
        ('outgoing', 'Giden'),
        ('incoming', 'Gelen')
    ], string='Yön', required=True, default='outgoing', tracking=True)

    state = fields.Selection([
        ('draft', 'Taslak'),
        ('sending', 'Gönderiliyor'),
        ('sent', 'Gönderildi'),
        ('delivered', 'Teslim Edildi'),
        ('accepted', 'Kabul Edildi'),
        ('rejected', 'Reddedildi'),
        ('error', 'Hata'),
        ('cancelled', 'İptal')
    ], string='Durum', default='draft', tracking=True)

    # İlişkiler
    move_id = fields.Many2one(
        'account.move',
        string='Fatura',
        ondelete='cascade'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='İş Ortağı',
        required=False  # QNB'den gelen bazı belgelerde partner bilgisi olmayabilir
    )
    company_id = fields.Many2one(
        'res.company',
        string='Şirket',
        required=True,
        default=lambda self: self.env.company
    )

    # Tarih/Zaman
    document_date = fields.Date(
        string='Belge Tarihi',
        required=True,
        default=fields.Date.today
    )
    send_date = fields.Datetime(
        string='Gönderim Tarihi'
    )
    response_date = fields.Datetime(
        string='Yanıt Tarihi'
    )

    # Tutar Bilgileri
    currency_id = fields.Many2one(
        'res.currency',
        string='Para Birimi',
        default=lambda self: self.env.company.currency_id
    )
    amount_untaxed = fields.Monetary(
        string='Vergisiz Tutar',
        currency_field='currency_id'
    )
    amount_tax = fields.Monetary(
        string='Vergi Tutarı',
        currency_field='currency_id'
    )
    amount_total = fields.Monetary(
        string='Toplam Tutar',
        currency_field='currency_id'
    )

    # Dosyalar
    xml_content = fields.Binary(
        string='XML İçeriği',
        attachment=True
    )
    xml_filename = fields.Char(
        string='XML Dosya Adı'
    )
    pdf_content = fields.Binary(
        string='PDF İçeriği',
        attachment=True
    )
    pdf_filename = fields.Char(
        string='PDF Dosya Adı'
    )

    # XML'den parse edilen ürün satırları (JSON)
    invoice_lines_data = fields.Text(
        string='Fatura Satırları (JSON)',
        help='XML\'den çıkarılan ürün/hizmet satırları'
    )

    # Yanıt/Hata Bilgileri
    response_code = fields.Char(
        string='Yanıt Kodu'
    )
    response_message = fields.Text(
        string='Yanıt Mesajı'
    )
    error_message = fields.Text(
        string='Hata Mesajı'
    )
    rejection_reason = fields.Text(
        string='Red Sebebi'
    )

    # Senaryo
    scenario = fields.Selection([
        ('TEMELFATURA', 'Temel Fatura'),
        ('TICARIFATURA', 'Ticari Fatura'),
        ('YURTDISIFATURA', 'Yurtdışı Fatura'),
        ('IHRACAT', 'İhracat'),
    ], string='Senaryo', default='TEMELFATURA')

    invoice_type = fields.Selection([
        ('SATIS', 'Satış'),
        ('IADE', 'İade'),
        ('ISTISNA', 'İstisna'),
        ('OZELMATRAH', 'Özel Matrah'),
        ('TEVKIFAT', 'Tevkifat'),
        ('IHRACKAYITLI', 'İhraç Kayıtlı'),
        ('SGK', 'SGK'),
        ('KOMISYONCU', 'Komisyoncu'),
        ('HKSKOMISYONCU', 'HKS Komisyoncu'),
    ], string='Fatura Tipi', default='SATIS')

    # Fatura Satırları (Ürünler)
    line_ids = fields.One2many(
        'qnb.document.line',
        'document_id',
        string='Fatura İçeriği',
        help='XML\'den parse edilen ürün/hizmet satırları'
    )

    line_count = fields.Integer(
        string='Satır Sayısı',
        compute='_compute_line_count'
    )

    # Tarihçe
    status_history = fields.One2many(
        'qnb.document.history',
        'document_id',
        'Tarihçe'
    )

    @api.depends('line_ids')
    def _compute_line_count(self):
        for doc in self:
            doc.line_count = len(doc.line_ids)

    def action_send(self):
        """Belgeyi gönder"""
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_("Sadece taslak belgeler gönderilebilir!"))

        if not self.move_id:
            raise UserError(_("Fatura bilgisi eksik!"))

        self.state = 'sending'

        try:
            # XML oluştur
            xml_content = self._generate_xml()

            # API ile gönder
            api_client = self.env['qnb.api.client']

            if self.document_type == 'efatura':
                result = api_client.send_invoice(
                    xml_content,
                    self.name,
                    self.partner_id.vat,
                    self.company_id
                )
            elif self.document_type == 'earsiv':
                result = api_client.send_earchive_invoice(
                    xml_content,
                    self.name,
                    self.company_id
                )
            elif self.document_type == 'eirsaliye':
                result = api_client.send_despatch(
                    xml_content,
                    self.name,
                    self.partner_id.vat,
                    self.company_id
                )
            else:
                raise UserError(_("Desteklenmeyen belge türü!"))

            if result.get('success'):
                self.write({
                    'state': 'sent',
                    'ettn': result.get('ettn'),
                    'send_date': fields.Datetime.now(),
                    'xml_content': base64.b64encode(xml_content.encode('utf-8')),
                    'xml_filename': f"{self.name}.xml"
                })
                self._create_history('sent', 'Belge başarıyla gönderildi')
            else:
                self.write({
                    'state': 'error',
                    'error_message': result.get('message')
                })
                self._create_history('error', result.get('message'))

        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            self._create_history('error', str(e))
            raise UserError(_("Gönderim hatası: %s") % str(e))

        return True

    def action_check_status(self):
        """Belge durumunu kontrol et"""
        self.ensure_one()

        if not self.ettn:
            raise UserError(_("ETTN bilgisi bulunamadı!"))

        api_client = self.env['qnb.api.client']

        document_type_map = {
            'efatura': 'EFATURA',
            'earsiv': 'EARSIV',
            'eirsaliye': 'EIRSALIYE'
        }

        result = api_client.get_document_status(
            self.ettn,
            document_type_map.get(self.document_type, 'EFATURA'),
            self.company_id
        )

        if result.get('success'):
            status = result.get('status', '').upper()

            state_map = {
                'GONDERILDI': 'sent',
                'TESLIM_ALINDI': 'delivered',
                'KABUL': 'accepted',
                'RED': 'rejected',
                'HATA': 'error',
                'IPTAL': 'cancelled'
            }

            new_state = state_map.get(status, self.state)

            self.write({
                'state': new_state,
                'response_code': result.get('status_code'),
                'response_message': result.get('status_description')
            })

            if new_state != self.state:
                self._create_history(new_state, result.get('status_description', ''))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Belge Durumu',
                    'message': f"Durum: {result.get('status_description', status)}",
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError(_("Durum sorgulama hatası: %s") % result.get('message'))

    def action_download_pdf(self):
        """PDF indir"""
        self.ensure_one()

        if not self.ettn:
            raise UserError(_("ETTN bilgisi bulunamadı!"))

        api_client = self.env['qnb.api.client']

        document_type_map = {
            'efatura': 'EFATURA',
            'earsiv': 'EARSIV',
            'eirsaliye': 'EIRSALIYE'
        }

        result = api_client.download_document_pdf(
            self.ettn,
            document_type_map.get(self.document_type, 'EFATURA'),
            self.company_id
        )

        if result.get('success'):
            self.write({
                'pdf_content': base64.b64encode(result.get('content')),
                'pdf_filename': f"{self.name}.pdf"
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self._name}/{self.id}/pdf_content/{self.pdf_filename}?download=true',
                'target': 'self'
            }
        else:
            raise UserError(_("PDF indirme hatası: %s") % result.get('message'))

    def action_accept(self):
        """Gelen belgeyi kabul et"""
        self.ensure_one()

        if self.direction != 'incoming':
            raise UserError(_("Sadece gelen belgeler kabul edilebilir!"))

        api_client = self.env['qnb.api.client']
        result = api_client.accept_invoice(self.ettn, self.company_id)

        if result.get('success'):
            self.write({'state': 'accepted'})
            self._create_history('accepted', 'Belge kabul edildi')
        else:
            raise UserError(_("Kabul hatası: %s") % result.get('message'))

    def action_reject(self):
        """Gelen belgeyi reddet"""
        self.ensure_one()

        return {
            'name': _('Belge Reddet'),
            'type': 'ir.actions.act_window',
            'res_model': 'qnb.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_document_id': self.id}
        }

    def _generate_xml(self):
        """CS-XML formatında fatura XML oluştur"""
        # Bu metod fatura verilerinden CS-XML oluşturur
        # Tam implementasyon için QNB API dokümantasyonuna bakılmalı

        if not self.move_id:
            raise UserError(_("Fatura bilgisi eksik!"))

        invoice = self.move_id

        # Basit bir CS-XML şablonu
        xml_template = """<?xml version="1.0" encoding="UTF-8"?>
<fatura>
    <xsdVersion>3.0</xsdVersion>
    <ublVersionNumarasi>2.1</ublVersionNumarasi>
    <ublOzellestirmeNumarasi>TR1.2</ublOzellestirmeNumarasi>
    <faturaTuru>{scenario}</faturaTuru>
    <faturaNo>{invoice_no}</faturaNo>
    <faturaTarihi>{invoice_date}</faturaTarihi>
    <faturaZamani>{invoice_time}</faturaZamani>
    <faturaTipi>{invoice_type}</faturaTipi>
    <paraBirimi>{currency}</paraBirimi>
    <satici>
        <aliciSaticiTanimi schemeId="VKN">{seller_vat}</aliciSaticiTanimi>
        <unvan>{seller_name}</unvan>
        <postaAdresi>
            <caddeSokak>{seller_street}</caddeSokak>
            <ilce>{seller_city}</ilce>
            <sehir>{seller_state}</sehir>
            <ulke>Türkiye</ulke>
        </postaAdresi>
        <vergiDairesi>{seller_tax_office}</vergiDairesi>
    </satici>
    <alici>
        <aliciSaticiTanimi schemeId="VKN">{buyer_vat}</aliciSaticiTanimi>
        <unvan>{buyer_name}</unvan>
        <postaAdresi>
            <caddeSokak>{buyer_street}</caddeSokak>
            <ilce>{buyer_city}</ilce>
            <sehir>{buyer_state}</sehir>
            <ulke>Türkiye</ulke>
        </postaAdresi>
    </alici>
    <vergiler>
        <toplamVergiTutari paraBirimi="{currency}">{total_tax}</toplamVergiTutari>
    </vergiler>
    <parasalToplamlar>
        <toplamMalHizmetTutari paraBirimi="{currency}">{amount_untaxed}</toplamMalHizmetTutari>
        <vergiHaricTutar paraBirimi="{currency}">{amount_untaxed}</vergiHaricTutar>
        <vergiDahilTutar paraBirimi="{currency}">{amount_total}</vergiDahilTutar>
        <odenecekTutar paraBirimi="{currency}">{amount_total}</odenecekTutar>
    </parasalToplamlar>
    {invoice_lines}
</fatura>"""

        # Fatura satırlarını oluştur
        lines_xml = ""
        for idx, line in enumerate(invoice.invoice_line_ids.filtered(lambda l: not l.display_type), 1):
            lines_xml += f"""
    <faturaSatir>
        <siraNo>{idx}</siraNo>
        <miktar birimKodu="NIU">{line.quantity}</miktar>
        <malHizmetMiktari paraBirimi="{invoice.currency_id.name}">{line.price_subtotal}</malHizmetMiktari>
        <vergiler>
            <toplamVergiTutari paraBirimi="{invoice.currency_id.name}">{line.price_total - line.price_subtotal}</toplamVergiTutari>
        </vergiler>
        <malHizmetBilgileri>
            <adi>{line.name or line.product_id.name}</adi>
        </malHizmetBilgileri>
        <birimFiyat paraBirimi="{invoice.currency_id.name}">{line.price_unit}</birimFiyat>
    </faturaSatir>"""

        # Şirket ve partner bilgileri
        company = invoice.company_id
        partner = invoice.partner_id

        xml_content = xml_template.format(
            scenario=self.scenario or 'TEMELFATURA',
            invoice_no=self.name,
            invoice_date=invoice.invoice_date.strftime('%Y-%m-%d'),
            invoice_time=fields.Datetime.now().strftime('%H:%M:%S'),
            invoice_type=self.invoice_type or 'SATIS',
            currency=invoice.currency_id.name,
            seller_vat=company.vat or '',
            seller_name=company.name,
            seller_street=company.street or '',
            seller_city=company.city or '',
            seller_state=company.state_id.name if company.state_id else '',
            seller_tax_office='',  # Vergi dairesi
            buyer_vat=partner.vat or '',
            buyer_name=partner.name,
            buyer_street=partner.street or '',
            buyer_city=partner.city or '',
            buyer_state=partner.state_id.name if partner.state_id else '',
            total_tax=invoice.amount_tax,
            amount_untaxed=invoice.amount_untaxed,
            amount_total=invoice.amount_total,
            invoice_lines=lines_xml
        )

        return xml_content

    def _create_history(self, status, description):
        """Tarihçe kaydı oluştur"""
        self.env['qnb.document.history'].create({
            'document_id': self.id,
            'status': status,
            'description': description,
            'timestamp': fields.Datetime.now()
        })

    def action_fetch_all_documents(self):
        """Manuel olarak GELEN + GİDEN TÜM belgeleri çek (2025'ten itibaren)"""
        company = self.env.company

        # Sadece JOKER GRUBU için QNB aktif
        if company.id != 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'QNB Hatası',
                    'message': f'QNB e-Solutions sadece JOKER GRUBU için aktiftir. Şu anda: {company.name}',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if not company.qnb_enabled:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'QNB Hatası',
                    'message': 'QNB e-Solutions entegrasyonu aktif değil!',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        try:
            from datetime import datetime
            from dateutil.parser import parse as parse_date

            api_client = self.env['qnb.api.client'].with_company(company)
            start_date = parse_date('2025-01-01')
            end_date = datetime.now()

            total_new = 0

            # 1) GELEN BELGELERİ ÇEK
            _logger.info(f"Gelen belgeler çekiliyor: {company.name}")
            incoming_result = api_client.get_incoming_documents(start_date, end_date, company=company)

            if incoming_result.get('success'):
                documents = incoming_result.get('documents', [])
                incoming_new = self._process_documents(documents, company, 'incoming')
                total_new += incoming_new
                _logger.info(f"✓ {incoming_new} gelen belge eklendi")

            # 2) GİDEN BELGELERİ ÇEK
            _logger.info(f"Giden belgeler çekiliyor: {company.name}")
            outgoing_result = api_client.get_outgoing_documents(start_date, end_date, company=company)

            if outgoing_result.get('success'):
                documents = outgoing_result.get('documents', [])
                outgoing_new = self._process_documents(documents, company, 'outgoing')
                total_new += outgoing_new
                _logger.info(f"✓ {outgoing_new} giden belge eklendi")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Başarılı ✓',
                    'message': f'Toplam {total_new} yeni belge indirildi!',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Belgeler indirilemedi: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Hata',
                    'message': f'Belgeler indirilemedi: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def _process_documents(self, documents, company, direction):
        """Belgeleri işle ve Odoo'ya ekle"""
        new_count = 0

        for doc in documents:
            ettn = doc.get('ettn')
            if not ettn:
                continue

            # Daha önce alınmış mı kontrol et
            existing = self.search([
                ('ettn', '=', ettn),
                ('company_id', '=', company.id)
            ])

            if not existing:
                # Partner bul veya oluştur
                partner = None
                if direction == 'incoming':
                    sender_vkn = doc.get('sender_vkn')
                    sender_title = doc.get('sender_title', f'Firma {sender_vkn}')
                else:
                    sender_vkn = doc.get('receiver_vkn') or doc.get('partner_vkn')
                    sender_title = doc.get('receiver_title') or doc.get('partner_title', f'Firma {sender_vkn}')

                if sender_vkn:
                    partner = self.env['res.partner'].search([
                        ('vat', '=', f'TR{sender_vkn}')
                    ], limit=1)
                    if not partner:
                        partner = self.env['res.partner'].create({
                            'name': sender_title,
                            'vat': f'TR{sender_vkn}',
                            'is_company': True,
                        })

                # Tarih formatını düzelt (20250115 → 2025-01-15)
                doc_date = doc.get('date')
                if doc_date and isinstance(doc_date, str) and len(doc_date) == 8:
                    doc_date = f"{doc_date[:4]}-{doc_date[4:6]}-{doc_date[6:8]}"

                self.create({
                    'name': doc.get('belge_no', 'Yeni Belge'),
                    'ettn': ettn,
                    'document_type': 'efatura',
                    'direction': direction,
                    'state': 'delivered',
                    'partner_id': partner.id if partner else False,
                    'company_id': company.id,
                    'document_date': doc_date,
                    'amount_total': doc.get('total', 0),
                    'currency_id': self.env['res.currency'].search([
                        ('name', '=', doc.get('currency', 'TRY'))
                    ], limit=1).id,
                })
                new_count += 1

        return new_count

    def _parse_invoice_xml_full(self, xml_content, direction='incoming'):
        """
        XML'den TÜM bilgileri çıkar ve dict olarak döndür
        - Müşteri/Tedarikçi bilgileri (VKN, isim, adres, vergi dairesi, telefon, email)
        - Tutarlar (toplam, vergisiz, vergi)
        - Fatura satırları (ürünler, barkod, miktar, birim fiyat, vergi)
        - Ödeme bilgileri
        """
        from lxml import etree

        result = {
            'amounts': {},
            'partner': {},
            'lines': [],
            'payment': {},
            'document_info': {}
        }

        try:
            root = etree.fromstring(xml_content.encode() if isinstance(xml_content, str) else xml_content)

            # Namespace
            ns = {
                'inv': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
                'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
                'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
            }

            # === BELGE BİLGİLERİ ===
            result['document_info']['invoice_id'] = self._get_xml_text(root, './/cbc:ID', ns)
            result['document_info']['uuid'] = self._get_xml_text(root, './/cbc:UUID', ns)
            result['document_info']['issue_date'] = self._get_xml_text(root, './/cbc:IssueDate', ns)
            result['document_info']['issue_time'] = self._get_xml_text(root, './/cbc:IssueTime', ns)
            result['document_info']['invoice_type'] = self._get_xml_text(root, './/cbc:InvoiceTypeCode', ns)
            result['document_info']['currency'] = self._get_xml_text(root, './/cbc:DocumentCurrencyCode', ns)
            result['document_info']['profile'] = self._get_xml_text(root, './/cbc:ProfileID', ns)

            # === TUTARLAR ===
            result['amounts']['total'] = float(self._get_xml_text(root, './/cac:LegalMonetaryTotal/cbc:PayableAmount', ns) or 0)
            result['amounts']['untaxed'] = float(self._get_xml_text(root, './/cac:LegalMonetaryTotal/cbc:LineExtensionAmount', ns) or 0)
            result['amounts']['tax'] = float(self._get_xml_text(root, './/cac:TaxTotal/cbc:TaxAmount', ns) or 0)

            # === PARTNER BİLGİLERİ (Tedarikçi veya Müşteri) ===
            if direction == 'incoming':
                # Gelen faturalarda SUPPLIER (tedarikçi) bilgisi
                party_path = './/cac:AccountingSupplierParty/cac:Party'
            else:
                # Giden faturalarda CUSTOMER (müşteri) bilgisi
                party_path = './/cac:AccountingCustomerParty/cac:Party'

            party = root.find(party_path, ns)
            if party is not None:
                # VKN/TCKN
                vkn_elem = party.find('.//cac:PartyIdentification/cbc:ID[@schemeID="VKN"]', ns)
                if vkn_elem is None:
                    vkn_elem = party.find('.//cac:PartyIdentification/cbc:ID[@schemeID="TCKN"]', ns)
                if vkn_elem is None:
                    vkn_elem = party.find('.//cac:PartyIdentification/cbc:ID', ns)

                if vkn_elem is not None and vkn_elem.text:
                    result['partner']['vat'] = vkn_elem.text.strip()

                # Firma İsmi
                result['partner']['name'] = self._get_xml_text(party, './/cac:PartyName/cbc:Name', ns)

                # Adres
                address = party.find('.//cac:PostalAddress', ns)
                if address is not None:
                    result['partner']['street'] = self._get_xml_text(address, './/cbc:StreetName', ns)
                    result['partner']['street2'] = self._get_xml_text(address, './/cbc:BuildingNumber', ns)
                    result['partner']['city'] = self._get_xml_text(address, './/cbc:CityName', ns)
                    result['partner']['state'] = self._get_xml_text(address, './/cbc:CitySubdivisionName', ns)
                    result['partner']['zip'] = self._get_xml_text(address, './/cbc:PostalZone', ns)
                    result['partner']['country'] = self._get_xml_text(address, './/cac:Country/cbc:Name', ns)

                # Vergi Dairesi
                result['partner']['tax_office'] = self._get_xml_text(party, './/cac:PartyTaxScheme/cac:TaxScheme/cbc:Name', ns)

                # İletişim
                contact = party.find('.//cac:Contact', ns)
                if contact is not None:
                    result['partner']['phone'] = self._get_xml_text(contact, './/cbc:Telephone', ns)
                    result['partner']['email'] = self._get_xml_text(contact, './/cbc:ElectronicMail', ns)

            # === ÖDEME BİLGİLERİ ===
            payment = root.find('.//cac:PaymentMeans', ns)
            if payment is not None:
                result['payment']['means_code'] = self._get_xml_text(payment, './/cbc:PaymentMeansCode', ns)
                result['payment']['instruction'] = self._get_xml_text(payment, './/cbc:InstructionNote', ns)

            # === FATURA SATIRLARI (Ürünler) ===
            invoice_lines = root.findall('.//cac:InvoiceLine', ns)
            for line in invoice_lines:
                line_data = {}

                # Satır No
                line_data['line_id'] = self._get_xml_text(line, './/cbc:ID', ns)

                # Miktar ve Birim
                qty_elem = line.find('.//cbc:InvoicedQuantity', ns)
                if qty_elem is not None:
                    line_data['quantity'] = float(qty_elem.text or 0)
                    line_data['unit_code'] = qty_elem.get('unitCode', 'C62')

                # Tutar
                line_data['line_total'] = float(self._get_xml_text(line, './/cbc:LineExtensionAmount', ns) or 0)

                # Ürün Bilgileri
                item = line.find('.//cac:Item', ns)
                if item is not None:
                    line_data['product_name'] = self._get_xml_text(item, './/cbc:Name', ns)
                    line_data['product_description'] = self._get_xml_text(item, './/cbc:Description', ns)

                    # Ürün Kodu (internal_reference)
                    line_data['product_code'] = self._get_xml_text(item, './/cac:SellersItemIdentification/cbc:ID', ns)

                    # Barkod (GTIN)
                    line_data['barcode'] = self._get_xml_text(item, './/cac:StandardItemIdentification/cbc:ID[@schemeID="GTIN"]', ns)
                    if not line_data['barcode']:
                        line_data['barcode'] = self._get_xml_text(item, './/cac:StandardItemIdentification/cbc:ID', ns)

                # Birim Fiyat
                price = line.find('.//cac:Price', ns)
                if price is not None:
                    line_data['unit_price'] = float(self._get_xml_text(price, './/cbc:PriceAmount', ns) or 0)

                # Vergi (KDV)
                tax = line.find('.//cac:TaxTotal/cac:TaxSubtotal', ns)
                if tax is not None:
                    line_data['tax_amount'] = float(self._get_xml_text(tax, './/cbc:TaxAmount', ns) or 0)
                    line_data['tax_percent'] = float(self._get_xml_text(tax, './/cbc:Percent', ns) or 0)

                result['lines'].append(line_data)

        except Exception as e:
            _logger.error(f"XML parsing hatası: {e}")

        return result

    def _get_xml_text(self, element, xpath, namespaces):
        """XML element'ten text çıkar"""
        elem = element.find(xpath, namespaces)
        return elem.text.strip() if elem is not None and elem.text else None

    def action_create_invoice(self):
        """
        QNB Belgesinden Odoo Faturası Oluştur

        İŞ AKIŞI:
        1. Önce mevcut yevmiye kayıtları ile eşleştir
        2. Eşleşen yevmiye varsa → Ona bağla
        3. Eşleşen yevmiye yoksa → Yeni fatura oluştur

        - Partner eşleştirmesi yapılmış olmalı
        - XML'den gelen ürünleri eşleştirir (barkod/kod/isim)
        - Fatura satırlarını oluşturur
        - Vergiler otomatik hesaplanır
        """
        self.ensure_one()

        if self.move_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Fatura Mevcut',
                    'message': f'Bu belge için zaten fatura oluşturulmuş: {self.move_id.name}',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if not self.partner_id:
            raise UserError(_("Partner bilgisi eksik! Önce XML'den partner eşleştirmesi yapılmalı."))

        # ===== YEVMİYE EŞLEŞTİRMESİ =====
        existing_move = self._match_with_existing_journal_entry()

        if existing_move:
            # Mevcut yevmiye kaydına bağla
            self.write({
                'move_id': existing_move.id,
                'state': 'delivered'
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✅ Yevmiye Eşleşti',
                    'message': f'QNB belgesi mevcut yevmiye kaydına bağlandı: {existing_move.name}',
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'res_model': 'account.move',
                        'res_id': existing_move.id,
                        'views': [[False, 'form']],
                    }
                }
            }

        # Fatura tipi
        if self.direction == 'incoming':
            move_type = 'in_invoice'  # Satın Alma Faturası
        else:
            move_type = 'out_invoice'  # Satış Faturası

        # Fatura satırlarını hazırla (line_ids kullan)
        invoice_lines = []

        for line in self.line_ids:
            # Ürün yoksa otomatik eşleştir
            if not line.product_id:
                line.action_match_product()

            # Hala ürün yoksa atla
            if not line.product_id:
                _logger.warning(f"Satır '{line.product_name}' için ürün bulunamadı, atlanıyor")
                continue

            # Fatura satırı
            invoice_line_vals = {
                'product_id': line.product_id.id,
                'name': line.product_description or line.product_name or line.product_id.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
            }

            # Vergi (KDV)
            if line.tax_percent:
                tax_percent = line.tax_percent
                # Türkiye KDV oranları: %1, %10, %20
                tax = self.env['account.tax'].search([
                    ('type_tax_use', '=', 'purchase' if self.direction == 'incoming' else 'sale'),
                    ('amount', '=', tax_percent),
                    ('company_id', '=', self.company_id.id)
                ], limit=1)

                if tax:
                    invoice_line_vals['tax_ids'] = [(6, 0, [tax.id])]

            invoice_lines.append((0, 0, invoice_line_vals))

        if not invoice_lines:
            raise UserError(_("Fatura satırı bulunamadı! XML'den ürün bilgileri çıkarılamamış olabilir."))

        # Fatura oluştur
        invoice_vals = {
            'partner_id': self.partner_id.id,
            'move_type': move_type,
            'invoice_date': self.document_date,
            'ref': self.name,  # Belge No
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'invoice_line_ids': invoice_lines,
        }

        invoice = self.env['account.move'].create(invoice_vals)
        self.move_id = invoice.id
        self.state = 'delivered'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Fatura Oluşturuldu',
                'message': f'Fatura oluşturuldu: {invoice.name} ({len(invoice_lines)} satır)',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'res_id': invoice.id,
                    'views': [[False, 'form']],
                }
            }
        }

    def action_fetch_all_documents(self):
        """Gelen + Giden TÜM Belgeleri Al (2025'ten itibaren)"""
        company = self.env.company

        # Sadece JOKER GRUBU için QNB aktif
        if company.id != 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'QNB Hatası',
                    'message': f'QNB e-Solutions sadece JOKER GRUBU için aktiftir. Şu anda: {company.name}',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if not company.qnb_enabled:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'QNB Hatası',
                    'message': 'QNB e-Solutions entegrasyonu aktif değil!',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        try:
            api_client = self.env['qnb.api.client'].with_company(company)

            # 2025 Ocak 1'den itibaren tüm belgeler (GELEN + GİDEN)
            from datetime import datetime
            from dateutil.parser import parse as parse_date
            start_date = parse_date('2025-01-01')
            end_date = datetime.now()

            incoming_count = 0
            outgoing_count = 0

            # Tüm belge türleri
            document_types = [
                ('EFATURA', 'efatura'),
                ('IRSALIYE', 'eirsaliye'),
            ]

            # ===== GELEN BELGELERİ ÇEK (TÜM TÜRLER, AYLIK PARÇALARDA) =====
            # QNB API 100 belge limiti koyduğu için aylık parçalara bölüyoruz
            from datetime import timedelta

            for api_type, odoo_type in document_types:
                # Aylık parçalara böl
                current_start = start_date
                while current_start < end_date:
                    current_end = min(current_start + timedelta(days=30), end_date)

                    result_in = api_client.get_incoming_documents(current_start, current_end, document_type=api_type, company=company)
                    if result_in.get('success'):
                        documents = result_in.get('documents', [])
                        _logger.info(f"QNB: {api_type} gelen belgeler ({current_start.strftime('%Y-%m-%d')} - {current_end.strftime('%Y-%m-%d')}): {len(documents)} belge")
                    else:
                        documents = []
                        _logger.warning(f"QNB: {api_type} gelen belgeler alınamadı: {result_in.get('message')}")
                        current_start = current_end + timedelta(days=1)
                        continue
                    for doc in documents:
                        ettn = doc.get('ettn')
                        if not ettn:
                            continue

                        # Daha önce alınmış mı kontrol et
                        existing = self.search([
                            ('ettn', '=', ettn),
                            ('direction', '=', 'incoming'),
                            ('company_id', '=', company.id)
                        ])

                        if not existing:
                            # XML içeriğini indir ve parse et
                            xml_result = api_client.download_incoming_document(ettn, api_type, company)

                            # Tarih formatını düzelt (20250115 → 2025-01-15)
                            doc_date = doc.get('date')
                            if doc_date and isinstance(doc_date, str) and len(doc_date) == 8:
                                doc_date = f"{doc_date[:4]}-{doc_date[4:6]}-{doc_date[6:8]}"

                            # Varsayılan değerler
                            partner = None
                            amount_total = doc.get('total', 0)
                            amount_untaxed = 0
                            amount_tax = 0
                            invoice_lines = []

                            # XML içeriği varsa KAPSAMLI PARSE ET
                            if xml_result and xml_result.get('success'):
                                xml_content = xml_result.get('content')
                                if xml_content:
                                    # Yeni metod ile tam parsing
                                    parsed_data = self._parse_invoice_xml_full(xml_content, direction='incoming')

                                    # Tutarları al
                                    if parsed_data.get('amounts'):
                                        amount_total = parsed_data['amounts'].get('total', amount_total)
                                        amount_untaxed = parsed_data['amounts'].get('untaxed', amount_untaxed)
                                        amount_tax = parsed_data['amounts'].get('tax', amount_tax)

                                    # Partner bilgilerini al ve eşleştir/güncelle
                                    if parsed_data.get('partner') and parsed_data['partner'].get('vat'):
                                        partner_data = parsed_data['partner']
                                        vat_number = f"TR{partner_data['vat']}"

                                        # Partner ara
                                        partner = self.env['res.partner'].search([
                                            ('vat', '=', vat_number)
                                        ], limit=1)

                                        # Partner güncellenecek değerler
                                        partner_vals = {
                                            'name': partner_data.get('name') or f"Tedarikçi {partner_data['vat']}",
                                            'vat': vat_number,
                                            'is_company': True,
                                            'supplier_rank': 1,
                                        }

                                        # Ek bilgiler varsa ekle
                                        if partner_data.get('street'):
                                            partner_vals['street'] = partner_data['street']
                                        if partner_data.get('street2'):
                                            partner_vals['street2'] = partner_data['street2']
                                        if partner_data.get('city'):
                                            partner_vals['city'] = partner_data['city']
                                        if partner_data.get('zip'):
                                            partner_vals['zip'] = partner_data['zip']
                                        if partner_data.get('phone'):
                                            partner_vals['phone'] = partner_data['phone']
                                        if partner_data.get('email'):
                                            partner_vals['email'] = partner_data['email']

                                        # Country (Türkiye)
                                        if partner_data.get('country'):
                                            country = self.env['res.country'].search([
                                                ('name', 'ilike', partner_data['country'])
                                            ], limit=1)
                                            if country:
                                                partner_vals['country_id'] = country.id

                                        # Partner yoksa oluştur, varsa güncelle
                                        if not partner:
                                            partner = self.env['res.partner'].create(partner_vals)
                                            _logger.info(f"✅ Yeni partner oluşturuldu: {partner_vals['name']} ({vat_number})")
                                        else:
                                            # Mevcut partneri güncelle (eksik bilgileri doldur)
                                            update_vals = {}
                                            for key, val in partner_vals.items():
                                                if val and not partner[key]:  # Sadece boş alanları doldur
                                                    update_vals[key] = val
                                            if update_vals:
                                                partner.write(update_vals)
                                                _logger.info(f"✅ Partner güncellendi: {partner.name} - {list(update_vals.keys())}")

                                    # Fatura satırlarını sakla (ürün eşleştirmesi için)
                                    if parsed_data.get('lines'):
                                        invoice_lines = parsed_data['lines']

                            # Belgeyi oluştur
                            import json

                            # Fatura satırları için line_ids hazırla
                            line_vals = []
                            if invoice_lines:
                                for idx, line_data in enumerate(invoice_lines, 1):
                                    line_vals.append((0, 0, {
                                        'sequence': idx * 10,
                                        'product_name': line_data.get('product_name') or line_data.get('product_description') or 'Ürün',
                                        'product_description': line_data.get('product_description'),
                                        'product_code': line_data.get('product_code'),
                                        'barcode': line_data.get('barcode'),
                                        'quantity': line_data.get('quantity', 1.0),
                                        'uom_code': line_data.get('unit_code'),
                                        'price_unit': line_data.get('unit_price', 0.0),
                                        'price_subtotal': line_data.get('line_total', 0.0),
                                        'tax_percent': line_data.get('tax_percent', 0.0),
                                        'tax_amount': line_data.get('tax_amount', 0.0),
                                    }))

                            new_document = self.create({
                                'name': doc.get('belge_no', 'Yeni Belge'),
                                'ettn': ettn,
                                'document_type': odoo_type,
                                'direction': 'incoming',
                                'state': 'draft',  # TASLAK olarak kaydet
                                'partner_id': partner.id if partner else False,
                                'company_id': company.id,
                                'document_date': doc_date,
                                'amount_total': amount_total,
                                'amount_untaxed': amount_untaxed,
                                'amount_tax': amount_tax,
                                'xml_content': xml_result.get('content') if xml_result and xml_result.get('success') else None,
                                'xml_filename': f"{ettn}.xml" if xml_result and xml_result.get('success') else None,
                                'invoice_lines_data': json.dumps(invoice_lines, ensure_ascii=False) if invoice_lines else None,
                                'line_ids': line_vals,
                                'currency_id': self.env['res.currency'].search([
                                    ('name', '=', doc.get('currency', 'TRY'))
                                ], limit=1).id,
                            })
                            incoming_count += 1

                    # Sonraki aya geç
                    current_start = current_end + timedelta(days=1)

            # ===== GİDEN BELGELERİ ÇEK (TÜM TÜRLER, 90 GÜNLÜK PARÇALARDA) =====
            for api_type, odoo_type in document_types:
                # 90 günlük parçalara böl (giden belgeler için limit)
                current_start = start_date
                while current_start < end_date:
                    current_end = min(current_start + timedelta(days=89), end_date)

                    result_out = api_client.get_outgoing_documents(current_start, current_end, document_type=api_type, company=company)
                    if result_out.get('success'):
                        documents = result_out.get('documents', [])
                        _logger.info(f"QNB: {api_type} giden belgeler ({current_start.strftime('%Y-%m-%d')} - {current_end.strftime('%Y-%m-%d')}): {len(documents)} belge")
                    else:
                        documents = []
                        _logger.warning(f"QNB: {api_type} giden belgeler alınamadı: {result_out.get('message')}")
                        current_start = current_end + timedelta(days=1)
                        continue
                    for doc in documents:
                        ettn = doc.get('ettn')
                        if not ettn:
                            continue

                        # Daha önce alınmış mı kontrol et
                        existing = self.search([
                            ('ettn', '=', ettn),
                            ('direction', '=', 'outgoing'),
                            ('company_id', '=', company.id)
                        ])

                        if not existing:
                            # Partner bul veya oluştur
                            partner = None
                            recipient_vkn = doc.get('recipient_vkn') or doc.get('receiver_vkn')
                            recipient_title = doc.get('recipient_title') or doc.get('receiver_title')
                            if recipient_vkn:
                                partner = self.env['res.partner'].search([
                                    ('vat', '=', f'TR{recipient_vkn}')
                                ], limit=1)
                                if not partner:
                                    partner = self.env['res.partner'].create({
                                        'name': recipient_title or f'Firma {recipient_vkn}',
                                        'vat': f'TR{recipient_vkn}',
                                        'is_company': True,
                                    })

                            # Tarih formatını düzelt (20250115 → 2025-01-15)
                            doc_date = doc.get('date')
                            if doc_date and isinstance(doc_date, str) and len(doc_date) == 8:
                                doc_date = f"{doc_date[:4]}-{doc_date[4:6]}-{doc_date[6:8]}"

                            self.create({
                                'name': doc.get('belge_no', 'Yeni Belge'),
                                'ettn': ettn,
                                'document_type': odoo_type,
                                'direction': 'outgoing',
                                'state': 'sent',
                                'partner_id': partner.id if partner else False,
                                'company_id': company.id,
                                'document_date': doc_date,
                                'amount_total': doc.get('total', 0),
                                'currency_id': self.env['res.currency'].search([
                                    ('name', '=', doc.get('currency', 'TRY'))
                                ], limit=1).id,
                            })
                            outgoing_count += 1

            total_count = incoming_count + outgoing_count
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Başarılı',
                    'message': f'{incoming_count} gelen + {outgoing_count} giden = {total_count} toplam belge indirildi!',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Hata',
                    'message': f'Belgeler indirilemedi: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    @api.model
    def _cron_fetch_incoming_documents(self):
        """Gelen belgeleri otomatik çek (Cron Job - 2025'ten itibaren TÜM belgeler)"""
        # Sadece JOKER GRUBU (company_id=1) için QNB belgelerini çek
        companies = self.env['res.company'].search([
            ('id', '=', 1),  # JOKER GRUBU
            ('qnb_enabled', '=', True),
            ('qnb_auto_fetch_incoming', '=', True)
        ])

        for company in companies:
            try:
                api_client = self.env['qnb.api.client'].with_company(company)

                # 2025 Ocak 1'den itibaren TÜM gelen belgelerini çek
                from datetime import datetime
                from dateutil.parser import parse as parse_date
                start_date = parse_date('2025-01-01')
                end_date = datetime.now()

                result = api_client.get_incoming_documents(start_date, end_date, company=company)

                if not result.get('success'):
                    _logger.warning(f"Gelen belgeler alınamadı: {result.get('message')}")
                    continue

                documents = result.get('documents', [])
                new_count = 0

                for doc in documents:
                    ettn = doc.get('ettn')
                    if not ettn:
                        continue

                    # Daha önce alınmış mı kontrol et
                    existing = self.search([
                        ('ettn', '=', ettn),
                        ('company_id', '=', company.id)
                    ])
                    if not existing:
                        # Partner bul veya oluştur
                        partner = None
                        sender_vkn = doc.get('sender_vkn')
                        if sender_vkn:
                            partner = self.env['res.partner'].search([
                                ('vat', '=', f'TR{sender_vkn}')
                            ], limit=1)
                            if not partner:
                                partner = self.env['res.partner'].create({
                                    'name': doc.get('sender_title', f'Firma {sender_vkn}'),
                                    'vat': f'TR{sender_vkn}',
                                    'is_company': True,
                                })

                        self.create({
                            'name': doc.get('belge_no', 'Yeni Belge'),
                            'ettn': ettn,
                            'document_type': 'efatura',
                            'direction': 'incoming',
                            'state': 'delivered',
                            'partner_id': partner.id if partner else False,
                            'company_id': company.id,
                            'document_date': doc.get('date'),
                            'amount_total': doc.get('total', 0),
                            'currency_id': self.env['res.currency'].search([
                                ('name', '=', doc.get('currency', 'TRY'))
                            ], limit=1).id,
                        })
                        new_count += 1

                _logger.info(f"{new_count} yeni gelen belge indirildi: {company.name}")

            except Exception as e:
                _logger.error(f"Error fetching incoming documents for {company.name}: {e}")

    @api.model
    def _cron_fetch_outgoing_documents(self):
        """Giden belgeleri otomatik çek (Cron Job - 2025'ten itibaren TÜM belgeler)"""
        # Sadece JOKER GRUBU (company_id=1) için QNB belgelerini çek
        companies = self.env['res.company'].search([
            ('id', '=', 1),  # JOKER GRUBU
            ('qnb_enabled', '=', True),
            ('qnb_auto_fetch_outgoing', '=', True)
        ])

        for company in companies:
            try:
                api_client = self.env['qnb.api.client'].with_company(company)

                # 2025 Ocak 1'den itibaren TÜM giden belgelerini çek
                from datetime import datetime
                from dateutil.parser import parse as parse_date
                start_date = parse_date('2025-01-01')
                end_date = datetime.now()

                result = api_client.get_outgoing_documents(start_date, end_date, company=company)

                if not result.get('success'):
                    _logger.warning(f"Giden belgeler alınamadı: {result.get('message')}")
                    continue

                documents = result.get('documents', [])
                new_count = 0

                for doc in documents:
                    ettn = doc.get('ettn')
                    if not ettn:
                        continue

                    # Daha önce alınmış mı kontrol et
                    existing = self.search([
                        ('ettn', '=', ettn),
                        ('company_id', '=', company.id),
                        ('direction', '=', 'outgoing')
                    ])
                    if not existing:
                        # Partner bul (giden belgede müşteri)
                        partner = None
                        recipient_vkn = doc.get('recipient_vkn')
                        if recipient_vkn:
                            partner = self.env['res.partner'].search([
                                ('vat', '=', f'TR{recipient_vkn}')
                            ], limit=1)
                            if not partner:
                                partner = self.env['res.partner'].create({
                                    'name': doc.get('recipient_title', f'Müşteri {recipient_vkn}'),
                                    'vat': f'TR{recipient_vkn}',
                                    'is_company': True,
                                })

                        self.create({
                            'name': doc.get('belge_no', 'Yeni Belge'),
                            'ettn': ettn,
                            'document_type': 'efatura',
                            'direction': 'outgoing',
                            'state': 'sent',
                            'partner_id': partner.id if partner else False,
                            'company_id': company.id,
                            'document_date': doc.get('date'),
                            'amount_total': doc.get('total', 0),
                            'currency_id': self.env['res.currency'].search([
                                ('name', '=', doc.get('currency', 'TRY'))
                            ], limit=1).id,
                        })
                        new_count += 1

                _logger.info(f"{new_count} yeni giden belge indirildi: {company.name}")

            except Exception as e:
                _logger.error(f"Error fetching outgoing documents for {company.name}: {e}")

    @api.model
    def _cron_check_document_status(self):
        """Belge durumlarını otomatik kontrol et (Cron Job)"""
        companies = self.env['res.company'].search([
            ('qnb_enabled', '=', True),
            ('qnb_auto_check_status', '=', True)
        ])

        for company in companies:
            # Gönderilmiş ama henüz son durumu belli olmayan belgeler
            documents = self.search([
                ('company_id', '=', company.id),
                ('state', 'in', ['sent', 'sending']),
                ('ettn', '!=', False)
            ])

            for doc in documents:
                try:
                    doc.action_check_status()
                except Exception as e:
                    _logger.error(f"Error checking status for {doc.name}: {e}")

    def _match_with_existing_journal_entry(self):
        """
        Mevcut yevmiye kayıtları ile eşleştirme

        Eşleştirme Stratejisi:
        1. Fatura numarası varsa → ref veya name ile eşleştir
        2. Fatura numarası yoksa → Partner + Tarih ile eşleştir
        3. Eşleşen yevmiye varsa → QNB belgesini ona bağla (move_id set et)
        4. Eşleşme yoksa → None döndür (yeni fatura oluşturulacak)

        :return: account.move kaydı veya None
        """
        self.ensure_one()

        # Zaten eşleşmiş ise atla
        if self.move_id:
            return self.move_id

        AccountMove = self.env['account.move']

        # STRATEJİ 1: Fatura Numarası ile Eşleştirme
        if self.name:
            # QNB belge numarası ile ara (ref veya name alanında)
            domain = [
                ('move_type', 'in', ['in_invoice', 'in_refund', 'out_invoice', 'out_refund']),
                ('state', '=', 'draft'),  # Sadece draft kayıtlarda ara
                '|',
                ('ref', 'ilike', self.name),
                ('name', 'ilike', self.name)
            ]

            if self.company_id:
                domain.append(('company_id', '=', self.company_id.id))

            matching_move = AccountMove.search(domain, limit=1)

            if matching_move:
                _logger.info(f"✅ Yevmiye eşleşti (Fatura No): {self.name} → {matching_move.name}")
                return matching_move

        # STRATEJİ 2: Partner + Tarih ile Eşleştirme
        if self.partner_id and self.document_date:
            # Tolerans: ±3 gün
            from datetime import timedelta
            date_from = self.document_date - timedelta(days=3)
            date_to = self.document_date + timedelta(days=3)

            domain = [
                ('partner_id', '=', self.partner_id.id),
                ('invoice_date', '>=', date_from),
                ('invoice_date', '<=', date_to),
                ('move_type', 'in', ['in_invoice', 'in_refund']),  # Gelen belgeler için
                ('state', '=', 'draft'),
            ]

            if self.company_id:
                domain.append(('company_id', '=', self.company_id.id))

            # Tutar eşleşmesi varsa daha iyi
            if self.amount_total:
                domain.append(('amount_total', '=', self.amount_total))

            matching_move = AccountMove.search(domain, limit=1)

            if matching_move:
                _logger.info(f"✅ Yevmiye eşleşti (Partner+Tarih): {self.partner_id.name} [{self.document_date}] → {matching_move.name}")
                return matching_move

            # Tutar olmadan dene
            if self.amount_total:
                domain_without_amount = [d for d in domain if not (isinstance(d, tuple) and d[0] == 'amount_total')]
                matching_move = AccountMove.search(domain_without_amount, limit=1)

                if matching_move:
                    _logger.info(f"⚠️ Yevmiye eşleşti (Partner+Tarih, tutar farklı): {self.partner_id.name} [{self.document_date}] → {matching_move.name}")
                    return matching_move

        # Eşleşme bulunamadı
        _logger.info(f"ℹ️ Yevmiye eşleşmesi bulunamadı: {self.name} - Yeni fatura oluşturulacak")
        return None

    def _find_or_create_partner(self, doc_data, company):
        """Partneri bul veya oluştur"""
        vat = doc_data.get('sender_vat', '')
        if vat:
            partner = self.env['res.partner'].search([
                ('vat', 'ilike', vat),
                '|',
                ('company_id', '=', company.id),
                ('company_id', '=', False)
            ], limit=1)

            if partner:
                return partner.id

            # Yeni partner oluştur
            return self.env['res.partner'].create({
                'name': doc_data.get('sender_name', f'VKN: {vat}'),
                'vat': vat,
                'is_company': True,
                'is_efatura_registered': True,
            }).id

        return False


class QnbDocumentHistory(models.Model):
    _name = 'qnb.document.history'
    _description = 'QNB Belge Tarihçesi'
    _order = 'timestamp desc'

    document_id = fields.Many2one(
        'qnb.document',
        string='Belge',
        required=True,
        ondelete='cascade'
    )
    status = fields.Char(string='Durum')
    description = fields.Text(string='Açıklama')
    timestamp = fields.Datetime(string='Zaman', default=fields.Datetime.now)
