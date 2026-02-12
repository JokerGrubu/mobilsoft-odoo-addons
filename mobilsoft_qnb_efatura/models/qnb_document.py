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
        ondelete='set null'
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
                    'state': 'draft',  # Dış servislerden gelen belgeler taslak olarak kaydedilir
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
                    street2_raw = self._get_xml_text(address, './/cbc:BuildingNumber', ns)
                    city_raw = self._get_xml_text(address, './/cbc:CitySubdivisionName', ns)
                    # street2 = bina no; ilçe city'ye yazılır, street2'ye YAZILMAZ (bazı XML'lerde yanlış mapleniyor)
                    if street2_raw and city_raw and (street2_raw or '').strip().upper().replace('İ', 'I') == (city_raw or '').strip().upper().replace('İ', 'I'):
                        street2_raw = ''
                    result['partner']['street2'] = street2_raw
                    # UBL: CityName=İL, CitySubdivisionName=İLÇE
                    result['partner']['state'] = self._get_xml_text(address, './/cbc:CityName', ns)
                    result['partner']['city'] = city_raw
                    result['partner']['zip'] = self._get_xml_text(address, './/cbc:PostalZone', ns)
                    result['partner']['country'] = self._get_xml_text(address, './/cac:Country/cbc:Name', ns)

                # Vergi Dairesi
                result['partner']['tax_office'] = self._get_xml_text(party, './/cac:PartyTaxScheme/cac:TaxScheme/cbc:Name', ns)

                # İletişim
                contact = party.find('.//cac:Contact', ns)
                if contact is not None:
                    result['partner']['contact_name'] = self._get_xml_text(contact, './/cbc:Name', ns)
                    result['partner']['phone'] = self._get_xml_text(contact, './/cbc:Telephone', ns)
                    result['partner']['email'] = self._get_xml_text(contact, './/cbc:ElectronicMail', ns)
                    result['partner']['website'] = self._get_xml_text(contact, './/cbc:WebsiteURI', ns)
                if not result['partner'].get('website'):
                    result['partner']['website'] = self._get_xml_text(party, './/cbc:WebsiteURI', ns)

            # === ÖDEME BİLGİLERİ (tüm PaymentMeans; birden fazla IBAN olabilir) ===
            result['partner']['bank_accounts'] = []
            for payment in root.findall('.//cac:PaymentMeans', ns):
                if payment is None:
                    continue
                if not result['payment'].get('means_code'):
                    result['payment']['means_code'] = self._get_xml_text(payment, './/cbc:PaymentMeansCode', ns)
                    result['payment']['instruction'] = self._get_xml_text(payment, './/cbc:InstructionNote', ns)
                iban = self._get_xml_text(payment, './/cac:PayeeFinancialAccount/cbc:ID[@schemeID="IBAN"]', ns)
                if not iban:
                    iban = self._get_xml_text(payment, './/cac:PayeeFinancialAccount/cbc:ID', ns)
                bank_name = self._get_xml_text(payment, './/cac:PayeeFinancialAccount/cbc:Name', ns)
                if not bank_name:
                    bank_name = self._get_xml_text(
                        payment,
                        './/cac:PayeeFinancialAccount/cac:FinancialInstitutionBranch/cac:FinancialInstitution/cbc:Name',
                        ns
                    )
                if iban:
                    result['partner']['bank_accounts'].append({
                        'iban': iban,
                        'bank_name': (bank_name or '').strip(),
                    })
                    if not result['partner'].get('iban'):
                        result['partner']['iban'] = iban
                        result['partner']['bank_name'] = (bank_name or '').strip()

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

    def action_view_invoice(self):
        """Bağlı faturayı formda aç"""
        self.ensure_one()
        if not self.move_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Fatura Yok'),
                    'message': _('Bu belgeye bağlı fatura bulunamadı.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

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

        # ===== 2025 YILI İÇİN YENİ FATURA OLUŞTURMA! =====
        # 2025 yılı faturaları zaten yevmiye kayıtlarında var
        # Eşleşmedi ise hata ver, yeni fatura oluşturma!
        if self.document_date and self.document_date.year == 2025:
            _logger.warning(f"⚠️ 2025 yılı belgesi eşleşmedi: {self.name} - Partner: {self.partner_id.name if self.partner_id else 'N/A'} - Tarih: {self.document_date}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '⚠️ Yevmiye Eşleşmedi',
                    'message': f'2025 yılı belgesi için yevmiye kaydı bulunamadı!\n'
                               f'Belge: {self.name}\n'
                               f'Partner: {self.partner_id.name if self.partner_id else "N/A"}\n'
                               f'Tarih: {self.document_date}\n'
                               f'Manuel kontrol gerekli.',
                    'type': 'warning',
                    'sticky': True,
                }
            }

        # ===== 2026 ve SONRASI İÇİN YENİ FATURA OLUŞTUR =====
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

            # Tüm yıllar (GELEN + GİDEN) — QNB arşivi tam çekim
            from datetime import datetime
            from dateutil.parser import parse as parse_date
            start_date = parse_date('2019-01-01')
            end_date = datetime.now()

            incoming_count = 0
            outgoing_count = 0

            # GELEN belge türleri (gelenBelgeleriListele destekli)
            incoming_document_types = [
                ('EFATURA', 'efatura'),
                ('IRSALIYE', 'eirsaliye'),
                ('UYGULAMA_YANITI', 'uygulama_yanit'),
                ('IRSALIYE_YANITI', 'eirsaliye_yanit'),
            ]

            # GİDEN belge türleri (gidenBelgeleriListele destekli)
            # Not: QNB tarafında 2025 giden faturalar genelde FATURA_UBL altında geliyor.
            outgoing_document_types = [
                ('FATURA_UBL', 'efatura'),
                ('FATURA', 'efatura'),
                ('IRSALIYE_UBL', 'eirsaliye'),
                ('IRSALIYE', 'eirsaliye'),
                ('UYGULAMA_YANITI_UBL', 'uygulama_yanit'),
                ('UYGULAMA_YANITI', 'uygulama_yanit'),
                ('IRSALIYE_YANITI_UBL', 'eirsaliye_yanit'),
                ('IRSALIYE_YANITI', 'eirsaliye_yanit'),
            ]

            # ===== GELEN BELGELERİ ÇEK (TÜM TÜRLER, AYLIK PARÇALARDA) =====
            # QNB API 100 belge limiti koyduğu için aylık parçalara bölüyoruz
            from datetime import timedelta

            for api_type, odoo_type in incoming_document_types:
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
                                            'name': partner_data.get('name') or f"Firma {partner_data['vat']}",
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

                            xml_payload = xml_result.get('content') if xml_result and xml_result.get('success') else None
                            if xml_payload and isinstance(xml_payload, (bytes, bytearray)):
                                # Odoo Binary alanlar base64 bekler; QNB/zeep bazen ham bytes döndürebilir.
                                try:
                                    decoded = base64.b64decode(xml_payload, validate=True)
                                    if decoded.strip().startswith((b'<', b'PK')):
                                        # Zaten base64 (decode edince XML/ZIP çıkıyor)
                                        pass
                                    else:
                                        xml_payload = base64.b64encode(xml_payload)
                                except Exception:
                                    xml_payload = base64.b64encode(xml_payload)

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
                                'xml_content': xml_payload,
                                'xml_filename': f"{ettn}.xml" if xml_payload else None,
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
            for api_type, odoo_type in outgoing_document_types:
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
                            partner = None

                            # XML indir + parse (partner/line/amount için)
                            download_type = api_type.replace('_UBL', '') if isinstance(api_type, str) else api_type
                            xml_result = api_client.download_outgoing_document(ettn, document_type=download_type, company=company)
                            xml_bytes = xml_result.get('content') if xml_result and xml_result.get('success') else None
                            xml_payload = xml_bytes
                            if xml_payload and isinstance(xml_payload, (bytes, bytearray)):
                                try:
                                    decoded = base64.b64decode(xml_payload, validate=True)
                                    if decoded.strip().startswith((b'<', b'PK')):
                                        pass
                                    else:
                                        xml_payload = base64.b64encode(xml_payload)
                                except Exception:
                                    xml_payload = base64.b64encode(xml_payload)

                            parsed_data = {}
                            invoice_lines = []
                            amount_total = float(doc.get('total', 0) or 0)
                            amount_untaxed = 0.0
                            amount_tax = 0.0

                            if xml_bytes:
                                try:
                                    parsed_data = self._parse_invoice_xml_full(xml_bytes, direction='outgoing')
                                except Exception as _e:
                                    parsed_data = {}

                            if parsed_data:
                                doc_info = parsed_data.get('document_info') or {}
                                amounts = parsed_data.get('amounts') or {}
                                amount_total = float(amounts.get('total') or amount_total or 0)
                                amount_untaxed = float(amounts.get('untaxed') or 0)
                                amount_tax = float(amounts.get('tax') or 0)
                                invoice_lines = parsed_data.get('lines') or []

                                # Partner eşleştir / oluştur (XML öncelikli)
                                partner_data = parsed_data.get('partner') or {}
                                vat_number = (partner_data.get('vat') or '').strip()
                                partner_name = (partner_data.get('name') or '').strip()
                                if vat_number or partner_name:
                                    partner, matched, match_type = self.env['res.partner'].match_or_create_from_external('qnb', {
                                        'vat': vat_number,
                                        'name': partner_name,
                                        'email': partner_data.get('email') or '',
                                    })

                            # XML yoksa: liste verisinden partner eşleştir / oluştur
                            if not partner:
                                recipient_vkn = (doc.get('recipient_vkn') or doc.get('receiver_vkn') or '').strip()
                                recipient_title = (doc.get('recipient_title') or doc.get('receiver_title') or '').strip()
                                if recipient_vkn or recipient_title:
                                    partner, matched, match_type = self.env['res.partner'].match_or_create_from_external('qnb', {
                                        'vat': recipient_vkn,
                                        'name': recipient_title or (f'Firma {recipient_vkn}' if recipient_vkn else 'Firma'),
                                    })

                            # Belge no boş gelebiliyor; XML içinden ID veya en kötü ETTN ile doldur.
                            doc_no = (doc.get('belge_no') or '').strip()
                            if not doc_no and parsed_data:
                                doc_no = (doc_info.get('invoice_id') or '').strip()
                            if not doc_no:
                                doc_no = ettn

                            # Tarih formatını düzelt (20250115 → 2025-01-15)
                            doc_date = doc.get('date')
                            if doc_date and isinstance(doc_date, str) and len(doc_date) == 8:
                                doc_date = f"{doc_date[:4]}-{doc_date[4:6]}-{doc_date[6:8]}"

                            # Fatura satırları için line_ids hazırla
                            import json
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

                            self.create({
                                'name': doc_no,
                                'ettn': ettn,
                                'document_type': odoo_type,
                                'direction': 'outgoing',
                                'state': 'sent',
                                'partner_id': partner.id if partner else False,
                                'company_id': company.id,
                                'document_date': doc_date,
                                'amount_total': amount_total,
                                'amount_untaxed': amount_untaxed,
                                'amount_tax': amount_tax,
                                'xml_content': xml_payload if xml_payload else None,
                                'xml_filename': f"{ettn}.xml" if xml_payload else None,
                                'invoice_lines_data': json.dumps(invoice_lines, ensure_ascii=False) if invoice_lines else None,
                                'line_ids': line_vals,
                                'currency_id': self.env['res.currency'].search([
                                    ('name', '=', doc.get('currency', 'TRY'))
                                ], limit=1).id,
                            })
                            outgoing_count += 1

                    # Sonraki döneme geç
                    current_start = current_end + timedelta(days=1)

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
                        # Partner bul (duplike önlemi: önce eşleştir, otomatik oluşturma tercihe bağlı)
                        partner = None
                        sender_vkn = (doc.get('sender_vkn') or '').strip()
                        if sender_vkn:
                            vat_tr = f'TR{sender_vkn}'
                            partner = self.env['res.partner'].search([
                                '|', ('vat', '=', vat_tr), ('vat', '=', sender_vkn)
                            ], limit=1)
                            if not partner and company.qnb_create_new_partner:
                                partner = self.env['res.partner'].create({
                                    'name': doc.get('sender_title', f'Firma {sender_vkn}'),
                                    'vat': vat_tr,
                                    'is_company': True,
                                })
                            elif not partner:
                                _logger.warning(
                                    f"QNB gelen belge partner eşleşmedi (VKN={sender_vkn}). "
                                    f"Otomatik partner oluşturma kapalı, partner boş bırakıldı."
                                )

                        self.create({
                            'name': doc.get('belge_no', 'Yeni Belge'),
                            'ettn': ettn,
                            'document_type': 'efatura',
                            'direction': 'incoming',
                            'state': 'draft',  # Taslak olarak kaydedilir, manuel onay gerekir
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
                        # Partner bul (giden belgede müşteri) - duplike önlemi
                        partner = None
                        recipient_vkn = (doc.get('recipient_vkn') or '').strip()
                        if recipient_vkn:
                            vat_tr = f'TR{recipient_vkn}'
                            partner = self.env['res.partner'].search([
                                '|', ('vat', '=', vat_tr), ('vat', '=', recipient_vkn)
                            ], limit=1)
                            if not partner and company.qnb_create_new_partner:
                                partner = self.env['res.partner'].create({
                                    'name': doc.get('recipient_title', f'Müşteri {recipient_vkn}'),
                                    'vat': vat_tr,
                                    'is_company': True,
                                })
                            elif not partner:
                                _logger.warning(
                                    f"QNB giden belge partner eşleşmedi (VKN={recipient_vkn}). "
                                    f"Otomatik partner oluşturma kapalı, partner boş bırakıldı."
                                )

                        self.create({
                            'name': doc.get('belge_no', 'Yeni Belge'),
                            'ettn': ettn,
                            'document_type': 'efatura',
                            'direction': 'outgoing',
                            'state': 'draft',  # Taslak olarak kaydedilir, manuel onay gerekir
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
        1. (2025 ve öncesi) Önce yevmiye (account.move: entry) içinde ara:
           - account.move.line.name/ref içinde belge numarası geçiyor mu?
        2. (2026+) Önce fatura hareketlerinde (in/out invoice/refund) ref/name ile ara
        3. Bulunamazsa Partner + Tarih (+/- 3 gün) + Tutar ile entry satırlarından eşleştir
        4. Eşleşme yoksa → None

        :return: account.move kaydı veya None
        """
        self.ensure_one()

        # Zaten eşleşmiş ise atla
        if self.move_id:
            return self.move_id

        AccountMove = self.env['account.move']
        MoveLine = self.env['account.move.line']

        # 2025 ve öncesi: mevcut yevmiye kayıtları zaten yüklü.
        legacy_mode = bool(self.document_date and self.document_date.year <= 2025)

        # Yardımcı: entry move içinde partner var mı?
        def _entry_has_partner(move):
            if not self.partner_id:
                return True
            return bool(MoveLine.search([
                ('move_id', '=', move.id),
                ('partner_id', '=', self.partner_id.id),
            ], limit=1))

        # Yardımcı: entry move'dan partner çıkar (QNB partner boşsa doldurmak için)
        def _entry_guess_partner(move):
            partner_line = MoveLine.search([
                ('move_id', '=', move.id),
                ('partner_id', '!=', False),
            ], limit=1)
            return partner_line.partner_id if partner_line else False

        # ===== STRATEJİ A: Belge No ile Yevmiye (entry) eşleştir =====
        if self.name or self.ettn:
            base_line_domain = [
                ('move_id.move_type', '=', 'entry'),
                ('company_id', '=', self.company_id.id),
                ('move_id.state', 'in', ['draft', 'posted']),
            ]
            # Belge no / ETTN metni satır name/ref içinde geçiyor mu?
            search_terms = [t for t in [self.name, self.ettn] if t]
            if search_terms:
                # (name ilike t1) OR (ref ilike t1) OR (name ilike t2) OR (ref ilike t2) ...
                or_terms = []
                for t in search_terms:
                    or_terms.extend([('name', 'ilike', t), ('ref', 'ilike', t)])
                base_line_domain += (['|'] * (len(or_terms) - 1)) + or_terms

            # Tarih aralığı ile daralt (performans + yanlış eşleşme azaltma)
            date_domain = []
            if self.document_date:
                from datetime import timedelta
                date_from = self.document_date - timedelta(days=7)
                date_to = self.document_date + timedelta(days=7)
                date_domain = [('date', '>=', date_from), ('date', '<=', date_to)]

            # Önce dar aralıkta dene, bulunamazsa tarih filtresiz tekrar dene (bazı yevmiye tarihleri farklı olabiliyor)
            lines = MoveLine.search(base_line_domain + date_domain, limit=50) if date_domain else MoveLine.search(base_line_domain, limit=50)
            if not lines and date_domain:
                lines = MoveLine.search(base_line_domain, limit=50)
            candidate_moves = lines.mapped('move_id')

            # Partner varsa: önce partner uyumlu olanları tercih et (yoksa belge no eşleşmesi yeterli)
            if candidate_moves and self.partner_id:
                partner_moves = candidate_moves.filtered(_entry_has_partner)
                if partner_moves:
                    candidate_moves = partner_moves

            # En yakın tarihlisini seç
            if candidate_moves:
                if self.document_date:
                    candidate_moves = candidate_moves.sorted(lambda m: abs((m.date or self.document_date) - self.document_date))

                move = candidate_moves[0]
                if not self.partner_id:
                    guessed = _entry_guess_partner(move)
                    if guessed:
                        self.partner_id = guessed.id
                _logger.info(f"✅ Yevmiye eşleşti (Belge No satırda): {self.name} → {move.name}")
                return move

            # Bazı importlarda belge no satırlara değil, doğrudan move.ref alanına yazılmış olabilir.
            move_domain = [
                ('move_type', '=', 'entry'),
                ('company_id', '=', self.company_id.id),
                ('state', 'in', ['draft', 'posted']),
            ]
            if search_terms:
                or_terms = []
                for t in search_terms:
                    or_terms.extend([('ref', 'ilike', t), ('name', 'ilike', t)])
                move_domain += (['|'] * (len(or_terms) - 1)) + or_terms

            if self.document_date:
                from datetime import timedelta
                date_from = self.document_date - timedelta(days=7)
                date_to = self.document_date + timedelta(days=7)
                move_domain += [('date', '>=', date_from), ('date', '<=', date_to)]

            candidate_moves = AccountMove.search(move_domain, limit=20)
            if candidate_moves:
                if self.document_date:
                    candidate_moves = candidate_moves.sorted(lambda m: abs((m.date or self.document_date) - self.document_date))
                move = candidate_moves[0]
                if not self.partner_id:
                    guessed = _entry_guess_partner(move)
                    if guessed:
                        self.partner_id = guessed.id
                _logger.info(f"✅ Yevmiye eşleşti (Belge No move.ref): {self.name} → {move.name}")
                return move

        # ===== STRATEJİ B: (2026+) Fatura hareketlerinde ref/name ile eşleştir =====
        if not legacy_mode and self.name:
            invoice_domain = [
                ('move_type', 'in', ['in_invoice', 'in_refund', 'out_invoice', 'out_refund']),
                ('company_id', '=', self.company_id.id),
                '|',
                ('ref', 'ilike', self.name),
                ('name', 'ilike', self.name),
            ]

            # Tarih ile daralt
            if self.document_date:
                from datetime import timedelta
                date_from = self.document_date - timedelta(days=7)
                date_to = self.document_date + timedelta(days=7)
                invoice_domain += ['|', ('invoice_date', '=', False), '&', ('invoice_date', '>=', date_from), ('invoice_date', '<=', date_to)]

            matching_move = AccountMove.search(invoice_domain, limit=1)
            if matching_move:
                _logger.info(f"✅ Fatura eşleşti (Ref/Name): {self.name} → {matching_move.name}")
                return matching_move

        # ===== STRATEJİ C: Partner + Tarih (+/-3) + Tutar ile entry eşleştir =====
        if self.partner_id and self.document_date and self.amount_total:
            from datetime import timedelta
            date_from = self.document_date - timedelta(days=3)
            date_to = self.document_date + timedelta(days=3)

            # Payable/receivable satırında toplam genelde debit/credit olarak geçer.
            currency = self.currency_id or self.company_id.currency_id
            rounding = float(getattr(currency, 'rounding', 0.01) or 0.01)
            # Float eşitliği yerine küçük tolerans ile ara (kur/fark/yuvarlama kaynaklı kaçmalar için)
            amount = float(round(self.amount_total, 6))
            tolerance = max(rounding * 2, 0.02)
            amount_lo = amount - tolerance
            amount_hi = amount + tolerance
            amount_domain = ['|',
                             '&', ('debit', '>=', amount_lo), ('debit', '<=', amount_hi),
                             '&', ('credit', '>=', amount_lo), ('credit', '<=', amount_hi)]

            # Partner merge / VAT farklılığı durumlarında alternatif partnerleri de dene (standart vat)
            partner_ids = [self.partner_id.id]
            vat_raw = (self.partner_id.vat or '').strip()
            vat_candidates = {vat_raw} if vat_raw else set()
            if vat_raw:
                digits = ''.join(c for c in vat_raw if c.isdigit())
                if digits:
                    vat_candidates.add(digits)
                    vat_candidates.add(f"TR{digits}")
            if vat_candidates:
                Partner = self.env['res.partner'].sudo()
                alt_partners = Partner.search([('vat', 'in', list(vat_candidates))])
                if alt_partners:
                    partner_ids = list(set(partner_ids + alt_partners.ids))

            line_domain = [
                ('move_id.move_type', '=', 'entry'),
                ('company_id', '=', self.company_id.id),
                ('move_id.state', 'in', ['draft', 'posted']),
                ('partner_id', 'in', partner_ids),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ] + amount_domain

            lines = MoveLine.search(line_domain, limit=50)
            candidate_moves = lines.mapped('move_id')
            if candidate_moves:
                candidate_moves = candidate_moves.sorted(lambda m: abs((m.date or self.document_date) - self.document_date))
                move = candidate_moves[0]
                _logger.info(f"⚠️ Yevmiye eşleşti (Partner+Tarih+Tutar): {self.partner_id.name} [{self.document_date}] → {move.name}")
                return move

        # ===== STRATEJİ D (Güvenli): Partner yoksa, Tarih (+/-3) + Tutar ile TEKİL eşleşme ara =====
        if not self.partner_id and self.document_date and self.amount_total:
            from datetime import timedelta
            date_from = self.document_date - timedelta(days=3)
            date_to = self.document_date + timedelta(days=3)

            currency = self.currency_id or self.company_id.currency_id
            rounding = float(getattr(currency, 'rounding', 0.01) or 0.01)
            amount = float(round(self.amount_total, 6))
            tolerance = max(rounding * 2, 0.02)
            amount_lo = amount - tolerance
            amount_hi = amount + tolerance
            amount_domain = ['|',
                             '&', ('debit', '>=', amount_lo), ('debit', '<=', amount_hi),
                             '&', ('credit', '>=', amount_lo), ('credit', '<=', amount_hi)]

            line_domain = [
                ('move_id.move_type', '=', 'entry'),
                ('company_id', '=', self.company_id.id),
                ('move_id.state', 'in', ['draft', 'posted']),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ] + amount_domain

            lines = MoveLine.search(line_domain, limit=100)
            candidate_moves = lines.mapped('move_id')
            if len(candidate_moves) == 1:
                move = candidate_moves[0]
                guessed = _entry_guess_partner(move)
                if guessed:
                    self.partner_id = guessed.id
                _logger.info(f"✅ Yevmiye eşleşti (Tarih+Tutar tekil): {self.name} [{self.document_date}] → {move.name}")
                return move

        _logger.info(f"ℹ️ Yevmiye eşleşmesi bulunamadı: {self.name}")
        return None

    @api.model
    def action_cleanup_legacy_2025_draft_invoices(self):
        """
        2025 (ve öncesi) için QNB tarafından oluşturulmuş taslak vendor bill kayıtlarını temizle.
        - Yevmiye zaten yüklü olduğu için bu yıllarda yeni in_invoice oluşturulmamalı.
        - Güvenlik: sadece ref'i qnb_document.name ile eşleşen draft in_invoice'lar silinir.
        """
        from datetime import date

        company = self.env.company
        cutoff_end = date(2025, 12, 31)
        cutoff_start = date(2025, 1, 1)

        legacy_doc_numbers = self.search([
            ('company_id', '=', company.id),
            ('direction', '=', 'incoming'),
            ('name', '!=', False),
            ('document_date', '>=', cutoff_start),
            ('document_date', '<=', cutoff_end),
        ]).mapped('name')

        if not legacy_doc_numbers:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'QNB Temizlik',
                    'message': 'Silinecek 2025 QNB belge kaydı bulunamadı.',
                    'type': 'info',
                    'sticky': False,
                }
            }

        Move = self.env['account.move']
        draft_moves = Move.search([
            ('company_id', '=', company.id),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'draft'),
            ('invoice_date', '>=', cutoff_start),
            ('invoice_date', '<=', cutoff_end),
            ('ref', 'in', legacy_doc_numbers),
        ])

        # Olası cascade riskine karşı önce ilişkileri kaldır
        related_docs = self.search([('move_id', 'in', draft_moves.ids)])
        if related_docs:
            related_docs.write({'move_id': False})

        deleted_count = len(draft_moves)
        if draft_moves:
            draft_moves.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QNB Temizlik',
                'message': f'2025 için {deleted_count} adet taslak tedarikçi faturası silindi.',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def action_bulk_match_documents(self):
        """
        QNB belgelerini mevcut muhasebe kayıtları ile toplu eşleştir:
        - 2025 ve öncesi: entry (yevmiye) satırlarından eşleştirip move_id bağlar.
        - 2026+: varsa mevcut fatura kaydı ile bağlar (ref/name), yoksa dokunmaz.
        """
        company = self.env.company
        docs = self.search([
            ('company_id', '=', company.id),
            ('move_id', '=', False),
            ('name', '!=', False),
        ], order='document_date asc, id asc')

        matched = 0
        matched_entry = 0
        matched_invoice = 0
        missing = 0

        for doc in docs:
            move = doc._match_with_existing_journal_entry()
            if move:
                doc.write({'move_id': move.id})
                matched += 1
                if move.move_type == 'entry':
                    matched_entry += 1
                else:
                    matched_invoice += 1
            else:
                missing += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QNB Eşleştirme',
                'message': (
                    f'Toplam: {len(docs)}\n'
                    f'Eşleşti: {matched} (entry: {matched_entry}, invoice: {matched_invoice})\n'
                    f'Eşleşmedi: {missing}'
                ),
                'type': 'success' if matched else 'warning',
                'sticky': False,
            }
        }

    @api.model
    def action_sync_partners_from_documents(self):
        """
        QNB belgelerinin XML içeriğinden partner bilgilerini okuyup Odoo partnerlarını güncelle.
        - Öncelik: VKN/TCKN (vat) ile eşleştir
        - VAT yoksa: belge üzerindeki mevcut partner_id korunur
        """
        company = self.env.company

        docs = self.search([
            ('company_id', '=', company.id),
            ('xml_content', '!=', False),
        ], order='document_date asc, id asc')

        if not docs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'QNB Partner',
                    'message': 'XML içeriği olan QNB belgesi bulunamadı.',
                    'type': 'info',
                    'sticky': False,
                }
            }

        Partner = self.env['res.partner']

        updated = 0
        created = 0
        linked = 0
        skipped = 0

        for doc in docs:
            try:
                raw = doc.xml_content
                if not raw:
                    skipped += 1
                    continue

                if isinstance(raw, str):
                    raw = raw.encode('utf-8')

                # attachment=True Binary alanlar base64 dönebilir; güvenli decode
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
                name_raw = (partner_data.get('name') or '').strip()

                digits = ''.join(filter(str.isdigit, str(vat_raw)))
                vat_number = f"TR{digits}" if digits else False

                partner = False
                if vat_number:
                    partner = Partner.search([('vat', '=', vat_number)], limit=1)
                    if not partner:
                        partner = Partner.search([('vat', 'ilike', digits)], limit=1)

                # VAT yoksa ve belgede partner varsa onu kullan
                if not partner and doc.partner_id:
                    partner = doc.partner_id

                # Partner yoksa oluştur
                if not partner:
                    partner_vals = {
                        'name': name_raw or (f"Firma {digits}" if digits else (doc.partner_id.name if doc.partner_id else 'Firma')),
                        'vat': vat_number or False,
                        'is_company': True,
                    }
                    if doc.direction == 'incoming':
                        partner_vals['supplier_rank'] = 1
                    else:
                        partner_vals['customer_rank'] = 1

                    partner = Partner.create(partner_vals)
                    created += 1

                # İl/İlçe normalizasyonu ÖNCE (city/state doğru alanlara yazılsın)
                # Odoo: city=İlçe, state_id=İl
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
                # city/state boşsa, street sonundan "İLÇE İL" parse et (örn: ... Gömeç balıkesir)
                if not partner_data.get('city') and not partner_data.get('state'):
                    street = (partner_data.get('street') or '').strip()
                    if len(street) > 4:
                        words = [w.strip().rstrip(',;.-') for w in street.split() if w.strip()]
                        if len(words) >= 2:
                            last_word = (words[-1] or '').rstrip(',;.-').strip()
                            for st in self.env['res.country.state'].search([('country_id.code', '=', 'TR')]):
                                if st.name and last_word and st.name.upper().replace('İ', 'I') == last_word.upper().replace('İ', 'I'):
                                    partner_data['state'] = st.name
                                    partner_data['city'] = (words[-2] or '').rstrip(',;.-').strip()
                                    break

                # Partner güncelle (sadece eksik alanları doldur)
                update_vals = {}

                if vat_number and not (partner.vat or '').strip():
                    update_vals['vat'] = vat_number

                if name_raw and not (partner.name or '').strip():
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
                    if val and not (partner[dst_key] or '').strip():
                        update_vals[dst_key] = val

                # Vergi dairesi (l10n_tr_tax_office_mobilsoft varsa)
                tax_office = (partner_data.get('tax_office') or '').strip()
                if tax_office:
                    if 'l10n_tr_tax_office_id' in Partner._fields:
                        if not partner.l10n_tr_tax_office_id:
                            tax_model = self.env['l10n.tr.tax.office']
                            tax_rec = tax_model.search([('name', 'ilike', tax_office)], limit=1)
                            if tax_rec:
                                update_vals['l10n_tr_tax_office_id'] = tax_rec.id
                    elif 'l10n_tr_tax_office_name' in Partner._fields:
                        if not (partner.l10n_tr_tax_office_name or '').strip():
                            update_vals['l10n_tr_tax_office_name'] = tax_office

                # Ülke/İl eşleştirme
                country_name = (partner_data.get('country') or '').strip()
                if country_name and 'country_id' in Partner._fields and not partner.country_id:
                    country = self.env['res.country'].search([('name', 'ilike', country_name)], limit=1)
                    if country:
                        update_vals['country_id'] = country.id

                state_name = (partner_data.get('state') or '').strip()
                state = None
                if state_name and 'state_id' in Partner._fields and not partner.state_id:
                    domain = [('name', 'ilike', state_name)]
                    country_id = update_vals.get('country_id') or (partner.country_id and partner.country_id.id)
                    if country_id:
                        domain.append(('country_id', '=', country_id))
                    state = self.env['res.country.state'].search(domain, limit=1)
                    if state:
                        update_vals['state_id'] = state.id
                        if not country_id and not partner.country_id and state.country_id.code == 'TR':
                            update_vals['country_id'] = state.country_id.id

                # İlçe → res.city (city_id): 973 semt/ilçe l10n_tr_city_mobilsoft
                city_name = (partner_data.get('city') or '').strip()
                if city_name and 'city_id' in Partner._fields:
                    state_obj = state or (update_vals.get('state_id') and self.env['res.country.state'].browse(update_vals['state_id'])) or partner.state_id
                    country_id = update_vals.get('country_id') or (partner.country_id and partner.country_id.id) or self.env['res.country'].search([('code', '=', 'TR')], limit=1).id
                    if state_obj and country_id:
                        city_rec = self.env['res.city'].search([
                            ('name', 'ilike', city_name),
                            ('state_id', '=', state_obj.id),
                            ('country_id', '=', country_id),
                        ], limit=1)
                        if city_rec and not partner.city_id:
                            update_vals['city_id'] = city_rec.id
                            update_vals['city'] = city_rec.name

                if doc.direction == 'incoming' and partner.supplier_rank < 1:
                    update_vals['supplier_rank'] = 1
                if doc.direction == 'outgoing' and partner.customer_rank < 1:
                    update_vals['customer_rank'] = 1

                if update_vals:
                    partner.write(update_vals)
                    updated += 1

                # Yetkili kişi (Contact) oluştur: sadece yoksa
                contact_name = (partner_data.get('contact_name') or '').strip()
                if contact_name:
                    existing_contact = self.env['res.partner'].search([
                        ('parent_id', '=', partner.id),
                        ('name', 'ilike', contact_name)
                    ], limit=1)
                    if not existing_contact:
                        contact_vals = {
                            'name': contact_name,
                            'parent_id': partner.id,
                            'type': 'contact',
                        }
                        contact_phone = (partner_data.get('phone') or '').strip()
                        contact_email = (partner_data.get('email') or '').strip()
                        if contact_phone:
                            contact_vals['phone'] = contact_phone
                        if contact_email:
                            contact_vals['email'] = contact_email
                        self.env['res.partner'].create(contact_vals)

                # IBAN varsa partner banka hesabı oluştur/eşleştir (Odoo sanitize standard)
                iban_raw = (partner_data.get('iban') or '').replace(' ', '')
                if iban_raw:
                    from odoo.addons.base.models.res_bank import sanitize_account_number
                    Bank = self.env['res.partner.bank']
                    iban_sanitized = sanitize_account_number(iban_raw)
                    existing_bank = Bank.search([
                        ('partner_id', '=', partner.id),
                        ('sanitized_acc_number', '=', iban_sanitized)
                    ], limit=1)
                    if not existing_bank:
                        bank_vals = {
                            'partner_id': partner.id,
                            'acc_number': iban_raw,
                        }
                        if 'company_id' in Bank._fields and partner.company_id:
                            bank_vals['company_id'] = partner.company_id.id
                        bank_name = (partner_data.get('bank_name') or '').strip()
                        if bank_name and 'bank_id' in Bank._fields:
                            bank = self.env['res.bank'].search([('name', 'ilike', bank_name)], limit=1)
                            if bank:
                                bank_vals['bank_id'] = bank.id
                        Bank.create(bank_vals)

                # Belgeye bağla
                if doc.partner_id != partner:
                    doc.partner_id = partner.id
                    linked += 1

            except Exception:
                skipped += 1
                continue

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QNB Partner',
                'message': (
                    f'Belgeler: {len(docs)}\n'
                    f'Güncellendi: {updated}\n'
                    f'Oluşturuldu: {created}\n'
                    f'Bağlandı: {linked}\n'
                    f'Atlandı: {skipped}'
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def action_fix_missing_partners_from_qnb_list(self):
        """
        QNB belge listesinden (gelenBelgeleriListele) VKN + ünvan bilgisi alıp
        partner_id boş kalan QNB belgelerini partner ile eşleştir.

        Not: XML içeriği bozuk/eksik olsa bile, listeden VKN/ünvan çekilerek düzeltme yapılabilir.
        """
        company = self.env.company
        api_client = self.env['qnb.api.client'].with_company(company)
        Partner = self.env['res.partner']

        docs = self
        if not docs:
            docs = self.search([
                ('company_id', '=', company.id),
                ('direction', '=', 'incoming'),
                ('partner_id', '=', False),
                ('ettn', '!=', False),
            ], order='document_date asc, id asc')
        else:
            docs = docs.filtered(lambda d: d.company_id.id == company.id and d.direction == 'incoming' and not d.partner_id and d.ettn)

        if not docs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'QNB Partner (Liste)',
                    'message': 'Partneri boş QNB belgesi bulunamadı.',
                    'type': 'info',
                    'sticky': False,
                }
            }

        from datetime import date, timedelta
        import calendar

        api_type_by_doc_type = {
            'efatura': 'EFATURA',
            'eirsaliye': 'IRSALIYE',
            'uygulama_yanit': 'UYGULAMA_YANITI',
            'eirsaliye_yanit': 'IRSALIYE_YANITI',
        }

        def month_start(d):
            return date(d.year, d.month, 1)

        def month_end(d):
            last_day = calendar.monthrange(d.year, d.month)[1]
            return date(d.year, d.month, last_day)

        def next_month(d):
            return (d.replace(day=28) + timedelta(days=4)).replace(day=1)

        def normalize_digits(value):
            return ''.join(ch for ch in str(value or '') if ch.isdigit())

        def is_placeholder_name(current_name, vat_number):
            current_name = (current_name or '').strip()
            if not current_name:
                return True
            if current_name.startswith(('Firma ', 'Tedarikçi ', 'VKN:')):
                return True
            if vat_number and current_name == vat_number:
                return True
            return False

        # ETTN -> {sender_vkn, sender_title, ...}
        by_ettn = {}
        list_calls = 0
        list_failures = 0

        docs_by_api_type = {}
        for doc in docs:
            api_type = api_type_by_doc_type.get(doc.document_type)
            if not api_type:
                continue
            docs_by_api_type[api_type] = docs_by_api_type.get(api_type, self.browse()) | doc

        for api_type, api_docs in docs_by_api_type.items():
            dates = [d.document_date for d in api_docs if d.document_date]
            if not dates:
                continue
            start = month_start(min(dates))
            end = month_end(max(dates))
            current = start
            while current <= end:
                current_start = month_start(current)
                current_end = month_end(current)
                result = api_client.get_incoming_documents(current_start, current_end, document_type=api_type, company=company)
                list_calls += 1
                if result.get('success'):
                    for it in result.get('documents', []) or []:
                        ettn = (it.get('ettn') or '').strip()
                        if ettn:
                            by_ettn[ettn.lower()] = it
                else:
                    list_failures += 1
                current = next_month(current)

        created = 0
        linked = 0
        updated_name = 0
        missing_in_list = 0
        missing_vkn = 0
        errors = 0

        # VKN -> resmi ünvan cache (mükellef sorgu)
        title_cache = {}

        for doc in docs:
            try:
                info = by_ettn.get((doc.ettn or '').strip().lower())
                if not info:
                    missing_in_list += 1
                    continue

                digits = normalize_digits(info.get('sender_vkn'))
                if len(digits) not in (10, 11):
                    missing_vkn += 1
                    continue

                vat_number = f"TR{digits}"
                partner = Partner.search([('vat', '=', vat_number)], limit=1)
                if not partner:
                    partner = Partner.search([('vat', 'ilike', digits)], limit=1)

                if not partner:
                    partner = Partner.create({
                        'name': info.get('sender_title') or f"Firma {digits}",
                        'vat': vat_number,
                        'is_company': True,
                        'supplier_rank': 1,
                    })
                    created += 1

                # Resmi ünvanı VKN/TCKN ile sorgula (kayıtlı kullanıcı)
                if digits not in title_cache:
                    res = api_client.check_registered_user(digits, company=company)
                    title = ''
                    if res.get('success') and res.get('users'):
                        title = (res['users'][0].get('title') or '').strip()
                    title_cache[digits] = title

                best_title = title_cache.get(digits) or (info.get('sender_title') or '').strip()

                partner_vals = {}
                if partner.supplier_rank < 1:
                    partner_vals['supplier_rank'] = 1

                if best_title and is_placeholder_name(partner.name, partner.vat):
                    if (partner.name or '').strip() != best_title:
                        partner_vals['name'] = best_title
                        updated_name += 1

                if partner_vals:
                    partner.write(partner_vals)

                if doc.partner_id != partner:
                    doc.partner_id = partner.id
                    linked += 1

            except Exception:
                errors += 1
                continue

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QNB Partner (Liste)',
                'message': (
                    f'Belgeler: {len(docs)}\n'
                    f'Liste çağrısı: {list_calls} (hata: {list_failures})\n'
                    f'Partner oluşturuldu: {created}\n'
                    f'Bağlandı: {linked}\n'
                    f'Ünvan güncellendi: {updated_name}\n'
                    f'Listede bulunamadı: {missing_in_list}\n'
                    f'VKN/TCKN eksik: {missing_vkn}\n'
                    f'Hata: {errors}'
                ),
                'type': 'success' if linked or created or updated_name else 'warning',
                'sticky': False,
            }
        }

    @api.model
    def action_fill_partner_vat_from_qnb_list(self):
        """
        VAT eksik partner'ları QNB gelen belge listesinden (gelenBelgeleriListele) doldur.
        Bu partner'ların en az bir gelen QNB belgesi (ettn) olmalı; listeden sender_vkn alınır.
        """
        from datetime import date, timedelta
        import calendar

        company = self.env.company
        api_client = self.env['qnb.api.client'].with_company(company)
        Partner = self.env['res.partner']

        # Faturada geçen ama vat boş partner'lar
        move_partner_ids = self.env['account.move'].search([
            ('partner_id', '!=', False),
            ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
        ]).mapped('partner_id').ids
        partners_missing_vat = Partner.search([
            ('id', 'in', move_partner_ids),
            '|', ('vat', '=', False), ('vat', '=', ''),
        ])
        if not partners_missing_vat:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('VAT Doldur (QNB Liste)'),
                    'message': _('VAT eksik (faturada geçen) partner bulunamadı.'),
                    'type': 'info',
                    'sticky': False,
                },
            }

        # Bu partner'lara ait gelen belgeler (ettn dolu)
        docs = self.search([
            ('company_id', '=', company.id),
            ('direction', '=', 'incoming'),
            ('partner_id', 'in', partners_missing_vat.ids),
            ('ettn', '!=', False),
        ], order='document_date desc')
        if not docs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('VAT Doldur (QNB Liste)'),
                    'message': _('VAT eksik partner\'lara ait QNB gelen belge bulunamadı (%s partner).') % len(partners_missing_vat),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        api_type_by_doc_type = {
            'efatura': 'EFATURA',
            'eirsaliye': 'IRSALIYE',
        }

        def month_start(d):
            return date(d.year, d.month, 1)

        def month_end(d):
            last_day = calendar.monthrange(d.year, d.month)[1]
            return date(d.year, d.month, last_day)

        def next_month(d):
            return (d.replace(day=28) + timedelta(days=4)).replace(day=1)

        def normalize_digits(val):
            return ''.join(ch for ch in str(val or '') if ch.isdigit())

        by_ettn = {}
        dates = [d.document_date for d in docs if d.document_date]
        if dates:
            start = month_start(min(dates))
            end = min(month_end(max(dates)), date.today())
            current = start
            while current <= end:
                result = api_client.get_incoming_documents(
                    month_start(current), month_end(current),
                    document_type='EFATURA',
                    company=company,
                )
                if result.get('success'):
                    for it in (result.get('documents') or []):
                        ettn = (it.get('ettn') or '').strip()
                        if ettn:
                            by_ettn[ettn.lower()] = it
                current = next_month(current)

        updated = 0
        for partner in partners_missing_vat:
            partner_docs = docs.filtered(lambda d: d.partner_id == partner)
            for doc in partner_docs:
                info = by_ettn.get((doc.ettn or '').strip().lower())
                if not info:
                    continue
                digits = normalize_digits(info.get('sender_vkn'))
                if not digits or len(digits) not in (10, 11):
                    continue
                vat_number = 'TR%s' % digits
                try:
                    partner.write({'vat': vat_number})
                    updated += 1
                    _logger.info("VAT QNB listesinden dolduruldu: %s (id=%s) -> %s", partner.name, partner.id, vat_number)
                except Exception as e:
                    _logger.warning("VAT yazılamadı partner id=%s: %s", partner.id, e)
                break

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('VAT Doldur (QNB Liste)'),
                'message': _('VAT eksik: %s partner, QNB belgesi olan: %s, listeden güncellenen: %s.') % (
                    len(partners_missing_vat), len(docs.mapped('partner_id')), updated,
                ),
                'type': 'success' if updated else 'warning',
                'sticky': False,
            },
        }

    def _find_or_create_partner(self, doc_data, company):
        """
        Partneri bul veya oluştur

        Eşleştirme kriteri: company.qnb_match_partner_by
        - 'vat': VKN/TCKN ile eşleştir
        - 'name': İsim ile eşleştir
        - 'both': VKN + İsim ile eşleştir

        Yeni oluşturma: company.qnb_create_new_partner
        - True: Bulunamazsa yeni partner oluştur
        - False: Sadece mevcut partnerleri eşleştir, oluşturma
        """
        vat = doc_data.get('sender_vat') or doc_data.get('sender_vkn') or ''
        name = doc_data.get('sender_name') or doc_data.get('sender_title') or ''
        match_by = company.qnb_match_partner_by or 'vat'
        create_new = company.qnb_create_new_partner

        partner = None

        # VKN ile eşleştir
        if vat and match_by in ('vat', 'both'):
            vat_number = vat if str(vat).upper().startswith('TR') else f"TR{vat}"
            partner = self.env['res.partner'].search([
                ('vat', 'ilike', vat_number),
                '|',
                ('company_id', '=', company.id),
                ('company_id', '=', False)
            ], limit=1)

        # İsim ile eşleştir (VKN bulunamadıysa veya match_by = 'name' veya 'both')
        if not partner and name and match_by in ('name', 'both'):
            partner = self.env['res.partner'].search([
                ('name', 'ilike', name),
                '|',
                ('company_id', '=', company.id),
                ('company_id', '=', False)
            ], limit=1)

        if partner:
            return partner.id

        # Yeni partner oluştur (ayar aktifse) — Nilvera alanları ile
        if create_new and vat:
            vat_number = vat if str(vat).upper().startswith('TR') else f"TR{vat}"
            return self.env['res.partner'].create({
                'name': name or f'Firma {vat}',
                'vat': vat_number,
                'is_company': True,
                'l10n_tr_nilvera_customer_status': 'einvoice',
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
