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
        required=True
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

    def action_fetch_incoming_documents(self):
        """Manuel olarak gelen belgeleri çek"""
        company = self.env.company

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
            from .qnb_api import QNBeSolutionsAPI
            api = QNBeSolutionsAPI(company)

            # Son 7 günün belgelerini çek
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

            documents = api.get_incoming_documents(start_date, end_date)
            new_count = 0

            for doc in documents:
                # Daha önce alınmış mı kontrol et
                existing = self.search([
                    ('ettn', '=', doc.get('ettn')),
                    ('company_id', '=', company.id)
                ])
                if not existing:
                    self.create({
                        'name': doc.get('document_no', 'Yeni Belge'),
                        'ettn': doc.get('ettn'),
                        'document_type': doc.get('document_type', 'efatura'),
                        'direction': 'incoming',
                        'state': 'delivered',
                        'partner_id': self._find_or_create_partner(doc, company),
                        'company_id': company.id,
                        'document_date': doc.get('document_date'),
                        'amount_total': doc.get('amount_total', 0),
                    })
                    new_count += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Başarılı',
                    'message': f'{new_count} yeni belge indirildi!',
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
        """Gelen belgeleri otomatik çek (Cron Job)"""
        companies = self.env['res.company'].search([
            ('qnb_enabled', '=', True),
            ('qnb_auto_fetch_incoming', '=', True)
        ])

        for company in companies:
            try:
                from .qnb_api import QNBeSolutionsAPI
                api = QNBeSolutionsAPI(company)

                # Son 7 günün belgelerini çek
                from datetime import datetime, timedelta
                end_date = datetime.now()
                start_date = end_date - timedelta(days=7)

                documents = api.get_incoming_documents(start_date, end_date)

                for doc in documents:
                    # Daha önce alınmış mı kontrol et
                    existing = self.search([
                        ('ettn', '=', doc.get('ettn')),
                        ('company_id', '=', company.id)
                    ])
                    if not existing:
                        self.create({
                            'name': doc.get('document_no', 'Yeni Belge'),
                            'ettn': doc.get('ettn'),
                            'document_type': doc.get('document_type', 'efatura'),
                            'direction': 'incoming',
                            'state': 'delivered',
                            'partner_id': self._find_or_create_partner(doc, company),
                            'company_id': company.id,
                            'document_date': doc.get('document_date'),
                            'amount_total': doc.get('amount_total', 0),
                        })

                _logger.info(f"Fetched {len(documents)} incoming documents for {company.name}")

            except Exception as e:
                _logger.error(f"Error fetching incoming documents for {company.name}: {e}")

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
