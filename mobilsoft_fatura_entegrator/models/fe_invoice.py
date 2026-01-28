import logging
import base64
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FEInvoice(models.Model):
    _name = 'fe.invoice'
    _description = 'Fatura Entegratör Fatura Takibi'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'invoice_number'
    
    @api.model_create_multi
    def create(self, vals_list):
        """Manuel oluşturmayı engelle - sadece API'den oluşturulabilir"""
        # Eğer context'te 'from_api' flag'i yoksa, manuel oluşturmayı engelle
        if not self.env.context.get('from_api'):
            raise UserError(_('Bu kayıtlar manuel olarak oluşturulamaz. Faturalar, sipariş veya fatura gönderildiğinde otomatik oluşturulur.'))
        return super().create(vals_list)

    # Temel Bilgiler
    external_id = fields.Char(string='FE Fatura ID', required=True, index=True, copy=False)
    fe_invoice_url = fields.Char(string='FE Fatura URL', compute='_compute_fe_invoice_url', store=False, readonly=True)
    invoice_number = fields.Char(string='Fatura Numarası', required=True, index=True)
    invoice_date = fields.Date(string='Fatura Tarihi', required=True)
    
    @api.depends('external_id')
    def _compute_fe_invoice_url(self):
        """FE fatura URL'ini hesapla"""
        for record in self:
            if record.external_id:
                record.fe_invoice_url = f'https://app.faturaentegrator.com/invoice/{record.external_id}'
            else:
                record.fe_invoice_url = False
    
    # Bağlantılar
    account_move_id = fields.Many2one('account.move', string='Odoo Faturası', ondelete='set null', index=True)
    sale_order_id = fields.Many2one('sale.order', string='Odoo Siparişi', ondelete='set null', index=True)
    partner_id = fields.Many2one('res.partner', string='Müşteri', related='account_move_id.partner_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Şirket', required=True, default=lambda self: self.env.company, index=True)
    
    # Durum Bilgileri - Tek bir durum alanı
    fe_status = fields.Selection(
        selection=[
            ('draft', 'Taslak'),
            ('sent', 'Gönderildi'),
            ('formalized', 'Resmileştirildi'),
            ('cancelled', 'İptal Edildi'),
            ('rejected', 'Reddedildi'),
        ],
        string='FE Durumu',
        default='draft',
        copy=False,
    )
    
    # Fatura Bilgileri
    amount_total = fields.Monetary(string='Toplam Tutar', currency_field='currency_id')
    amount_untaxed = fields.Monetary(string='Vergisiz Tutar', currency_field='currency_id')
    amount_tax = fields.Monetary(string='Vergi Tutarı', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Para Birimi', related='account_move_id.currency_id', store=True, readonly=True)
    
    # Muafiyet Bilgileri (KDV 0 ise gösterilir)
    exemption_code = fields.Char(string='Muafiyet Kodu', copy=False)
    exemption_reason = fields.Char(string='Muafiyet Sebebi', copy=False)
    
    # Callback Bilgileri
    callback_url = fields.Char(string='Callback URL', copy=False)
    last_callback_date = fields.Datetime(string='Son Callback Tarihi', copy=False)
    callback_data = fields.Text(string='Callback Verisi', copy=False)
    
    # Tarih Bilgileri
    fe_created_at = fields.Datetime(string='FE Oluşturulma Tarihi', copy=False)
    fe_updated_at = fields.Datetime(string='FE Güncellenme Tarihi', copy=False)
    
    # Ek Bilgiler
    move_type = fields.Selection(
        selection=[
            ('out_invoice', 'Müşteri Faturası'),
            ('out_refund', 'Müşteri İade Faturası'),
            ('in_invoice', 'Tedarikçi Faturası'),
            ('in_refund', 'Tedarikçi İade Faturası'),
        ],
        string='Fatura Tipi',
        copy=False,
    )
    
    # PDF Bilgileri
    pdf_url = fields.Char(string='PDF URL', copy=False)
    pdf_attachment_id = fields.Many2one('ir.attachment', string='PDF Dosyası', copy=False, readonly=True)
    
    
    def name_get(self):
        result = []
        for record in self:
            name = f"{record.invoice_number or 'Fatura'}"
            if record.external_id:
                name += f" [FE: {record.external_id}]"
            result.append((record.id, name))
        return result
    
    @api.model
    def create_from_api_response(self, external_id, data, account_move_id=None, sale_order_id=None):
        """API yanıtından fe.invoice kaydı oluştur"""
        invoice_data = data.get('invoice') or data.get('data') or data
        customer_data = data.get('customer') or {}
        
        # Fatura numarası ve tarihi
        invoice_number = invoice_data.get('number') or invoice_data.get('invoice_number') or ''
        invoice_date = invoice_data.get('date') or invoice_data.get('invoice_date') or fields.Date.today()
        
        # Durum bilgileri
        state = invoice_data.get('status') or invoice_data.get('state') or ''
        formal_status = invoice_data.get('formal_status') or ''
        workflow_status = invoice_data.get('workflow_status') or ''
        
        # Durumu tek bir alana dönüştür
        fe_status = 'draft'
        if formal_status and 'formalized' in str(formal_status).lower():
            fe_status = 'formalized'
        elif workflow_status and 'approved' in str(workflow_status).lower():
            fe_status = 'formalized'
        elif state and 'sent' in str(state).lower():
            fe_status = 'sent'
        elif state and 'cancelled' in str(state).lower() or state and 'cancel' in str(state).lower():
            fe_status = 'cancelled'
        elif state and 'rejected' in str(state).lower() or state and 'reject' in str(state).lower():
            fe_status = 'rejected'
        elif state:
            fe_status = 'sent'
        
        # Tutarlar
        amount_total = invoice_data.get('amount_total') or 0
        amount_untaxed = invoice_data.get('amount_untaxed') or 0
        amount_tax = invoice_data.get('amount_tax') or 0
        
        # Muafiyet bilgileri (KDV 0 ise)
        exemption_code = invoice_data.get('exemption_code') or ''
        exemption_reason = invoice_data.get('exemption_reason') or ''
        
        # Callback URL
        callback_url = data.get('callback_url') or ''
        
        # Tarih bilgileri - ISO formatını Odoo formatına çevir
        fe_created_at = fields.Datetime.now()
        fe_updated_at = fields.Datetime.now()
        if invoice_data.get('created_at'):
            try:
                # ISO format: '2025-11-07T06:15:35.000000Z' -> Odoo format: '2025-11-07 06:15:35'
                created_str = invoice_data.get('created_at')
                if 'T' in created_str:
                    created_str = created_str.split('T')[0] + ' ' + created_str.split('T')[1].split('.')[0].split('Z')[0]
                fe_created_at = fields.Datetime.to_datetime(created_str) if created_str else fields.Datetime.now()
            except Exception:
                fe_created_at = fields.Datetime.now()
        if invoice_data.get('updated_at'):
            try:
                updated_str = invoice_data.get('updated_at')
                if 'T' in updated_str:
                    updated_str = updated_str.split('T')[0] + ' ' + updated_str.split('T')[1].split('.')[0].split('Z')[0]
                fe_updated_at = fields.Datetime.to_datetime(updated_str) if updated_str else fields.Datetime.now()
            except Exception:
                fe_updated_at = fields.Datetime.now()
        
        # Move type
        move_type = invoice_data.get('move_type') or 'out_invoice'
        
        # Company
        company_id = self.env.company.id
        if account_move_id:
            move = self.env['account.move'].browse(account_move_id)
            company_id = move.company_id.id
        elif sale_order_id:
            order = self.env['sale.order'].browse(sale_order_id)
            company_id = order.company_id.id
        
        vals = {
            'external_id': str(external_id),
            'invoice_number': invoice_number,
            'invoice_date': invoice_date,
            'account_move_id': account_move_id,
            'sale_order_id': sale_order_id,
            'company_id': company_id,
            'fe_status': fe_status,
            'amount_total': amount_total,
            'amount_untaxed': amount_untaxed,
            'amount_tax': amount_tax,
            'exemption_code': exemption_code if amount_tax == 0 else '',
            'exemption_reason': exemption_reason if amount_tax == 0 else '',
            'callback_url': callback_url,
            'fe_created_at': fe_created_at,
            'fe_updated_at': fe_updated_at,
            'move_type': move_type,
        }
        
        # Mevcut kayıt var mı kontrol et
        existing = self.search([('external_id', '=', str(external_id))], limit=1)
        if existing:
            existing.write(vals)
            return existing
        
        # API'den geldiğini belirtmek için context'e flag ekle
        return self.with_context(from_api=True).create(vals)
    
    def update_from_callback(self, callback_data):
        """Callback'ten gelen verilerle güncelle"""
        for record in self:
            # Callback verisinden durum bilgilerini al
            state = callback_data.get('status') or callback_data.get('state') or ''
            formal_status = callback_data.get('formal_status') or ''
            workflow_status = callback_data.get('workflow_status') or ''
            
            # Durumu tek bir alana dönüştür
            fe_status = record.fe_status
            if formal_status and 'formalized' in str(formal_status).lower():
                fe_status = 'formalized'
            elif workflow_status and 'approved' in str(workflow_status).lower():
                fe_status = 'formalized'
            elif state and 'sent' in str(state).lower():
                fe_status = 'sent'
            elif state and 'cancelled' in str(state).lower() or state and 'cancel' in str(state).lower():
                fe_status = 'cancelled'
            elif state and 'rejected' in str(state).lower() or state and 'reject' in str(state).lower():
                fe_status = 'rejected'
            elif state:
                fe_status = 'sent'
            
            # Fatura bilgileri güncellenmiş olabilir
            invoice_data = callback_data.get('invoice') or callback_data.get('data') or {}
            amount_total = invoice_data.get('amount_total') or record.amount_total
            amount_untaxed = invoice_data.get('amount_untaxed') or record.amount_untaxed
            amount_tax = invoice_data.get('amount_tax') or record.amount_tax
            
            record.write({
                'fe_status': fe_status,
                'amount_total': amount_total,
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'last_callback_date': fields.Datetime.now(),
                'callback_data': str(callback_data),
                'fe_updated_at': fields.Datetime.now(),
            })
            
            # İlgili account.move varsa güncelle
            if record.account_move_id:
                record.account_move_id.write({
                    'fe_external_id': record.external_id,
                    'fe_state': fe_status,
                })
            
            # İlgili sale.order varsa güncelle
            if record.sale_order_id:
                record.sale_order_id.write({
                    'fe_external_id': record.external_id,
                    'fe_state': fe_status,
                })
            
            record.message_post(body=_('Callback ile durum güncellendi: %s') % fe_status)
    
    def action_view_account_move(self):
        """İlgili account.move'a git"""
        self.ensure_one()
        if not self.account_move_id:
            raise UserError(_('Bu fatura için Odoo faturası bulunamadı.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fatura'),
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_sale_order(self):
        """İlgili sale.order'a git"""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('Bu fatura için Odoo siparişi bulunamadı.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sipariş'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_open_fe_invoice(self):
        """Fatura Entegratör'de faturayı aç"""
        self.ensure_one()
        if not self.fe_invoice_url:
            raise UserError(_('FE fatura URL\'si bulunamadı.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.fe_invoice_url,
            'target': 'new',
        }
    
    def action_fe_download_formal_pdf(self):
        """FE Formal PDF'i indir - PDF URL'den direkt indirir"""
        self.ensure_one()
        if self.pdf_url:
            # PDF URL varsa, direkt linke git
            return {
                'type': 'ir.actions.act_url',
                'url': self.pdf_url,
                'target': 'new',
            }
        else:
            raise UserError(_('PDF URL bulunamadı. Fatura henüz formalize edilmemiş olabilir.'))
    
    def update_from_api(self):
        """API'den fatura bilgilerini çek ve güncelle (notification webhook için)"""
        for record in self:
            if not record.external_id:
                _logger.warning('FE Invoice update_from_api: external_id yok')
                continue
            if not record.company_id.fe_api_key:
                _logger.warning('FE Invoice update_from_api: company_id için API key yok')
                continue
            
            try:
                # API'den fatura bilgilerini çek
                client = record.company_id.fe_get_client()
                data = client.invoice_show(record.external_id)
                
                _logger.info('FE Invoice update_from_api: API response: %s', data)
                
                # API yanıtı: {'success': True, 'data': {...}, 'message': '...'}
                # data içinde invoice bilgileri var
                invoice_data = data.get('data') or {}
                
                # Durum bilgileri - WordPress plugin'deki gibi
                # formal_status: pending, running, completed, not_required, failed, canceled
                # workflow_status: processing, failed, completed
                formal_status = invoice_data.get('formal_status') or ''
                workflow_status = invoice_data.get('workflow_status') or ''
                
                # Durumu tek bir alana dönüştür
                # Öncelik: formal_status == 'completed' > workflow_status == 'completed' > diğerleri
                fe_status = record.fe_status or 'draft'
                if formal_status == 'completed':
                    fe_status = 'formalized'
                elif formal_status == 'canceled':
                    fe_status = 'cancelled'
                elif formal_status == 'failed':
                    fe_status = 'rejected'
                elif workflow_status == 'completed':
                    fe_status = 'sent'
                elif workflow_status == 'failed':
                    fe_status = 'rejected'
                elif workflow_status == 'processing' or formal_status == 'running':
                    fe_status = 'sent'
                
                # Fatura bilgileri - WordPress plugin'deki yapıyla uyumlu
                # API'de genelde 'id', 'order_id', 'order_d_id', 'created_at', 'updated_at' vs var
                invoice_number = invoice_data.get('invoice_number') or invoice_data.get('number') or record.invoice_number
                invoice_date_str = invoice_data.get('invoice_date') or invoice_data.get('date') or invoice_data.get('issue_date')
                if invoice_date_str:
                    try:
                        invoice_date = fields.Date.from_string(invoice_date_str) if isinstance(invoice_date_str, str) else invoice_date_str
                    except Exception:
                        invoice_date = record.invoice_date
                else:
                    invoice_date = record.invoice_date
                
                # Tutarlar API'de farklı yerlerde olabilir
                amount_total = invoice_data.get('total') or invoice_data.get('amount_total') or record.amount_total
                amount_untaxed = invoice_data.get('subtotal') or invoice_data.get('amount_untaxed') or record.amount_untaxed
                amount_tax = invoice_data.get('tax') or invoice_data.get('amount_tax') or record.amount_tax
                
                # Tarih bilgileri
                fe_updated_at = fields.Datetime.now()
                if invoice_data.get('updated_at'):
                    try:
                        updated_str = invoice_data.get('updated_at')
                        if 'T' in updated_str:
                            updated_str = updated_str.split('T')[0] + ' ' + updated_str.split('T')[1].split('.')[0].split('Z')[0]
                        fe_updated_at = fields.Datetime.to_datetime(updated_str) if updated_str else fields.Datetime.now()
                    except Exception:
                        fe_updated_at = fields.Datetime.now()
                
                # Güncelle
                record.write({
                    'invoice_number': invoice_number,
                    'invoice_date': invoice_date,
                    'fe_status': fe_status,
                    'amount_total': amount_total,
                    'amount_untaxed': amount_untaxed,
                    'amount_tax': amount_tax,
                    'fe_updated_at': fe_updated_at,
                })
                
                # İlgili account.move varsa güncelle
                if record.account_move_id:
                    record.account_move_id.write({
                        'fe_external_id': record.external_id,
                        'fe_state': fe_status,
                    })
                
                # İlgili sale.order varsa güncelle
                if record.sale_order_id:
                    record.sale_order_id.write({
                        'fe_external_id': record.external_id,
                        'fe_state': fe_status,
                    })
                
                # PDF URL'i kaydet
                pdf_url = invoice_data.get('pdf_url') or ''
                if pdf_url and pdf_url != record.pdf_url:
                    record.write({'pdf_url': pdf_url})
                
                # Formalize edilmişse ve PDF URL varsa, bir kere indir ve kaynak kaydına ekle
                if fe_status == 'formalized' and pdf_url and not record.pdf_attachment_id:
                    try:
                        # PDF'i URL'den indir
                        import requests
                        pdf_response = requests.get(pdf_url, timeout=30)
                        if pdf_response.status_code == 200:
                            pdf_content = pdf_response.content
                            pdf_data = base64.b64encode(pdf_content).decode('utf-8')
                            
                            # Kaynak kaydı belirle: önce sale_order, sonra account_move
                            target_model = None
                            target_id = None
                            target_record = None
                            
                            if record.sale_order_id:
                                target_model = 'sale.order'
                                target_id = record.sale_order_id.id
                                target_record = record.sale_order_id
                            elif record.account_move_id:
                                target_model = 'account.move'
                                target_id = record.account_move_id.id
                                target_record = record.account_move_id
                            
                            if target_model and target_id:
                                # Aynı PDF daha önce eklenmiş mi kontrol et
                                existing_pdf = self.env['ir.attachment'].search([
                                    ('res_model', '=', target_model),
                                    ('res_id', '=', target_id),
                                    ('name', 'like', 'fe-formal.pdf')
                                ], limit=1)
                                
                                if not existing_pdf:
                                    # PDF'i kaynak kaydına attachment olarak ekle
                                    attachment = self.env['ir.attachment'].create({
                                        'name': f"{record.invoice_number or 'invoice'}-fe-formal.pdf",
                                        'type': 'binary',
                                        'datas': pdf_data,
                                        'res_model': target_model,
                                        'res_id': target_id,
                                        'mimetype': 'application/pdf',
                                    })
                                    
                                    # fe.invoice'a attachment referansı kaydet
                                    record.write({'pdf_attachment_id': attachment.id})
                                    
                                    # Kaynak kaydın chatter'ına mesaj ekle
                                    target_record.message_post(
                                        body=_('FE Formal PDF eklendi: %s') % attachment.name,
                                        attachment_ids=[attachment.id]
                                    )
                                    
                                    _logger.info('FE Invoice update_from_api: PDF indirildi ve %s kaydına eklendi: %s', target_model, attachment.name)
                                else:
                                    # Mevcut attachment'ı kullan
                                    record.write({'pdf_attachment_id': existing_pdf.id})
                                    _logger.info('FE Invoice update_from_api: Mevcut PDF kullanıldı: %s', existing_pdf.name)
                            else:
                                _logger.warning('FE Invoice update_from_api: PDF için hedef kayıt bulunamadı (sale_order_id veya account_move_id gerekli)')
                        else:
                            _logger.warning('FE Invoice update_from_api: PDF indirilemedi. Status: %s', pdf_response.status_code)
                    except Exception as e:
                        _logger.warning('FE Invoice update_from_api: PDF eklenemedi: %s', str(e))
                
                record.message_post(body=_('API\'den güncellendi: %s') % fe_status)
                _logger.info('FE Invoice update_from_api: external_id=%s, durum=%s', record.external_id, fe_status)
                
            except Exception as e:
                _logger.exception('FE Invoice update_from_api hatası: %s', str(e))
                raise

