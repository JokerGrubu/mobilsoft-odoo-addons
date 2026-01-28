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

    # Tarihçe
    status_history = fields.One2many(
        'qnb.document.history',
        'document_id',
        string='Tarihçe'
    )

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

            # ===== GELEN BELGELERİ ÇEK (TÜM TÜRLER) =====
            for api_type, odoo_type in document_types:
                result_in = api_client.get_incoming_documents(start_date, end_date, document_type=api_type, company=company)
                if result_in.get('success'):
                    documents = result_in.get('documents', [])
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

                            # Partner bilgileri XML'den gelecek
                            partner = None
                            sender_vkn = None
                            sender_title = None

                            # Tarih formatını düzelt (20250115 → 2025-01-15)
                            doc_date = doc.get('date')
                            if doc_date and isinstance(doc_date, str) and len(doc_date) == 8:
                                doc_date = f"{doc_date[:4]}-{doc_date[4:6]}-{doc_date[6:8]}"

                            # XML'den tutarları parse et
                            amount_total = doc.get('total', 0)
                            amount_untaxed = 0
                            amount_tax = 0

                            # XML içeriği varsa parse et
                            if xml_result and xml_result.get('success'):
                                xml_content = xml_result.get('content')
                                if xml_content:
                                    try:
                                        from lxml import etree
                                        root = etree.fromstring(xml_content.encode() if isinstance(xml_content, str) else xml_content)

                                        # UBL namespace
                                        ns = {'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
                                              'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'}

                                        # Toplam tutar
                                        total_elem = root.find('.//cac:LegalMonetaryTotal/cbc:PayableAmount', ns)
                                        if total_elem is not None and total_elem.text:
                                            amount_total = float(total_elem.text)

                                        # Vergisiz tutar
                                        untaxed_elem = root.find('.//cac:LegalMonetaryTotal/cbc:LineExtensionAmount', ns)
                                        if untaxed_elem is not None and untaxed_elem.text:
                                            amount_untaxed = float(untaxed_elem.text)

                                        # Vergi tutarı
                                        tax_elem = root.find('.//cac:TaxTotal/cbc:TaxAmount', ns)
                                        if tax_elem is not None and tax_elem.text:
                                            amount_tax = float(tax_elem.text)

                                        # Sender VKN ve isim bilgilerini XML'den al
                                        supplier_party = root.find('.//cac:AccountingSupplierParty/cac:Party', ns)
                                        if supplier_party is not None:
                                            # VKN
                                            vkn_elem = supplier_party.find('.//cac:PartyIdentification/cbc:ID[@schemeID="VKN"]', ns)
                                            if vkn_elem is None:
                                                vkn_elem = supplier_party.find('.//cac:PartyIdentification/cbc:ID[@schemeID="TCKN"]', ns)
                                            if vkn_elem is None:
                                                vkn_elem = supplier_party.find('.//cac:PartyIdentification/cbc:ID', ns)

                                            if vkn_elem is not None and vkn_elem.text:
                                                sender_vkn = vkn_elem.text.strip()
                                                # Partner ara veya oluştur
                                                partner = self.env['res.partner'].search([
                                                    ('vat', '=', f'TR{sender_vkn}')
                                                ], limit=1)

                                            # İsim
                                            name_elem = supplier_party.find('.//cac:PartyName/cbc:Name', ns)
                                            if name_elem is not None and name_elem.text:
                                                sender_title = name_elem.text.strip()

                                            # Partner yoksa oluştur
                                            if sender_vkn and not partner:
                                                partner = self.env['res.partner'].create({
                                                    'name': sender_title or f'Tedarikçi {sender_vkn}',
                                                    'vat': f'TR{sender_vkn}',
                                                    'is_company': True,
                                                    'supplier_rank': 1,
                                                })
                                            # Partner varsa ismini güncelle
                                            elif partner and sender_title:
                                                partner.write({'name': sender_title})

                                    except Exception as e:
                                        _logger.warning(f"XML parse hatası {ettn}: {e}")

                            self.create({
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
                                'currency_id': self.env['res.currency'].search([
                                    ('name', '=', doc.get('currency', 'TRY'))
                                ], limit=1).id,
                            })
                            incoming_count += 1

            # ===== GİDEN BELGELERİ ÇEK (TÜM TÜRLER) =====
            for api_type, odoo_type in document_types:
                result_out = api_client.get_outgoing_documents(start_date, end_date, document_type=api_type, company=company)
                if result_out.get('success'):
                    documents = result_out.get('documents', [])
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
