from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FEIntegrationTemp(models.TransientModel):
    _name = 'fe.integration.temp'
    _description = 'FE Integration Temp (Transient)'

    name = fields.Char(required=True)
    external_id = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True)


class FESendOrderWizard(models.TransientModel):
    _name = 'fe.send.order.wizard'
    _description = 'Send Order to Fatura Entegrator Wizard'

    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True)
    integration_choice_id = fields.Many2one(
        'fe.integration.temp',
        string='Entegrasyon',
        domain="[('company_id','=',company_id)]",
        required=True,
    )
    line_ids = fields.One2many('fe.send.order.wizard.line', 'wizard_id', string='Satırlar', readonly=True)

    # Düzenlenebilir Müşteri Bilgileri
    customer_name = fields.Char(string='Unvan/Ad Soyad')
    customer_vat = fields.Char(string='Vergi No / TCKN')
    customer_email = fields.Char(string='E-posta')
    customer_phone = fields.Char(string='Telefon')
    street = fields.Char(string='Adres')
    city = fields.Char(string='İl')
    zip = fields.Char(string='Posta Kodu')
    country_code = fields.Char(string='Ülke Kodu')
    currency_id = fields.Many2one('res.currency', string='Para Birimi')
    amount_untaxed = fields.Monetary(string='Vergisiz Tutar', currency_field='currency_id', readonly=True)
    amount_tax = fields.Monetary(string='Vergi', currency_field='currency_id', readonly=True)
    amount_total = fields.Monetary(string='Toplam', currency_field='currency_id', readonly=True)

    # İnternet Satışı ve Kargo
    is_internet_sale = fields.Boolean(string='İnternet satışı mı?', default=False)
    payment_method = fields.Selection(
        selection=[
            ('credit_or_debit', 'Banka/Kredi Kartı'),
            ('direct_transfer', 'EFT/Havale'),
            ('cash_on_delivery', 'Kapıda Ödeme'),
            ('payment_agent', 'Ödeme Aracısı'),
            ('other', 'Diğer'),
        ],
        string='Ödeme Yöntemi',
        default='credit_or_debit',
    )
    payment_platform = fields.Char(string='Ödeme Aracı / Platform')
    payment_date = fields.Date(string='Ödeme Tarihi')
    is_need_shipment = fields.Boolean(string='Teslimat gerekli mi?', default=False)
    shipment_company_title = fields.Char(string='Kargo Firması')
    shipment_company_tax_number = fields.Char(string='Firma Vergi No')
    shipment_courier_name = fields.Char(string='Kurye Ad')
    shipment_courier_tax_number = fields.Char(string='Kurye Vergi No')
    shipment_delivery_date = fields.Date(string='Teslimat Tarihi')

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        company = self.env.company
        if vals.get('company_id'):
            company = self.env['res.company'].browse(vals['company_id'])
        # FE'den entegrasyon listesini çek
        client = self.env['fe.client'].with_company(company.id)
        data = client.integration_invoice_index()
        items = data.get('data') or data or []
        if isinstance(items, dict):
            items = items.get('items') or []
        for it in items:
            name = it.get('name') or it.get('title') or (it.get('vendor') and it['vendor'].get('name')) or 'Integration'
            ext_id = it.get('id') or it.get('uuid') or ''
            if ext_id:
                self.env['fe.integration.temp'].create({
                    'name': name,
                    'external_id': str(ext_id),
                    'company_id': company.id,
                })
        # Satırları One2many komutlarıyla set et
        if vals.get('order_id'):
            order = self.env['sale.order'].browse(vals['order_id'])
            partner = order.partner_invoice_id or order.partner_id
            # Varsayılan ayarları company'den al
            vals.update({
                'customer_name': partner.name,
                'customer_vat': partner.vat or '',
                'customer_email': partner.email or '',
                'customer_phone': partner.phone or partner.mobile or '',
                'street': ((partner.street or '') + ' ' + (partner.street2 or '')).strip(),
                'city': (partner.state_id and partner.state_id.name) or '',
                'zip': partner.zip or '',
                'country_code': partner.country_id and partner.country_id.code or '',
                'currency_id': order.currency_id.id,
                'amount_total': order.amount_total,
                'amount_untaxed': order.amount_untaxed,
                'amount_tax': order.amount_tax,
                'is_internet_sale': company.fe_is_internet_sale,
                'is_need_shipment': company.fe_is_need_shipment,
                'payment_method': company.fe_payment_method or 'credit_or_debit',
                'payment_platform': company.fe_payment_platform or ((order.payment_term_id and order.payment_term_id.name) or 'ODoo'),
                'payment_date': fields.Date.today(),
                'shipment_company_title': company.fe_shipment_company_title or '',
                'shipment_company_tax_number': company.fe_shipment_company_tax_number or '',
                'shipment_courier_name': company.fe_shipment_courier_name or '',
                'shipment_courier_tax_number': company.fe_shipment_courier_tax_number or '',
                'shipment_delivery_date': fields.Date.today(),
            })
            commands = []
            for line in order.order_line.filtered(lambda l: not l.display_type):
                taxes = ', '.join([f"{t.name} ({t.amount}%)" for t in line.tax_id])
                # Vergi oranını hesapla
                tax_rate = 0
                if line.tax_id:
                    tax = line.tax_id[0]
                    tax_rate = tax.amount or 0
                # Vergi sıfırsa varsayılan muafiyet bilgilerini ekle
                exemption_code = None
                exemption_reason = None
                if tax_rate == 0:
                    exemption_code = company.fe_exemption_code or None
                    exemption_reason = company.fe_exemption_reason or None
                commands.append((0, 0, {
                    'name': line.name,
                    'sku': line.product_id.default_code or '',
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'taxes': taxes,
                    'tax_rate': tax_rate,
                    'subtotal': line.price_subtotal,
                    'currency_id': order.currency_id.id,
                    'exemption_code': exemption_code,
                    'exemption_reason': exemption_reason,
                }))
            vals['line_ids'] = commands
        return vals

    def _prepare_shipment_data(self):
        """Kargo bilgilerini hazırla. İnternet satışı seçiliyse ve kargo firması/vergi no boşsa varsayılan değerler kullan."""
        company_title = self.shipment_company_title or ''
        company_tax_number = self.shipment_company_tax_number or ''
        
        # İnternet satışı seçiliyse ve kargo firması ile vergi no boşsa varsayılan değerler
        if self.is_internet_sale and not company_title and not company_tax_number:
            company_title = 'vendor'
            company_tax_number = '1' * 11
        
        return {
            'company_title': company_title,
            'company_tax_number': company_tax_number,
            'courier_name': self.shipment_courier_name or '',
            'courier_tax_number': self.shipment_courier_tax_number or '',
            'delivery_date': (self.shipment_delivery_date or fields.Date.today()).isoformat() if hasattr(self, 'shipment_delivery_date') else fields.Date.today().isoformat(),
        }

    def action_confirm(self):
        self.ensure_one()
        order = self.order_id
        if not self.integration_choice_id:
            raise UserError(_('Lütfen bir entegrasyon seçin.'))
        client = order.company_id.fe_get_client()
        # WordPress eklentisine uyumlu "create_request" şemasına göre payload hazırla
        # Satır verileri
        lines = []
        # Wizard line'ları product_id ve name ile eşleştirmek için bir dict oluştur
        wizard_lines_dict = {}
        for wl in self.line_ids:
            key = (wl.sku or '', wl.name or '')
            wizard_lines_dict[key] = wl
        
        for l in order.order_line.filtered(lambda x: not x.display_type and x.product_uom_qty):
            tax_rate = 0
            if l.tax_id:
                # İlk vergi oranını al
                tax = l.tax_id[0]
                tax_rate = int(round(tax.amount or 0))
            unit_price = l.price_subtotal / (l.product_uom_qty or 1)
            discount = (l.price_unit - unit_price) * l.product_uom_qty if l.price_unit and unit_price else 0
            
            # Wizard line'dan exemption bilgilerini al
            exemption_code = None
            exemption_reason = None
            wl_key = (l.product_id.default_code or '', l.name or '')
            if wl_key in wizard_lines_dict:
                wl = wizard_lines_dict[wl_key]
                exemption_code = wl.exemption_code or None
                exemption_reason = wl.exemption_reason or None
            
            # Vergi sıfırsa ve exemption bilgisi yoksa company defaults'tan al
            if tax_rate == 0 and not exemption_code:
                exemption_code = order.company_id.fe_exemption_code or None
                exemption_reason = order.company_id.fe_exemption_reason or None
            
            line_payload = {
                'id': l.product_id.id or '',
                'name': l.product_id.display_name or l.name,
                'description': '',
                'sku': l.product_id.default_code or '',
                'quantity': l.product_uom_qty,
                'unit': 'C62',
                'unit_price': unit_price,
                'discount_type': 'amount',
                'discount': max(discount, 0),
                'tax_rate': tax_rate,
                'exemption_code': exemption_code,
                'exemption_reason': exemption_reason,
            }
            lines.append(line_payload)

        # Müşteri verileri
        vat = (self.customer_vat or '').replace(' ', '')
        is_company = len(vat) == 10
        name = self.customer_name or ''
        first_name = name
        last_name = ''
        if not is_company and ' ' in name:
            parts = name.strip().split(' ')
            first_name = ' '.join(parts[:-1])
            last_name = parts[-1]

        # Temel alanlar (zorunlular)
        payload = {
            'sale_channel_id': order.company_id.fe_sale_channel_id,
            'invoice_integration_id': self.integration_choice_id.external_id,
            'type': 'SATIS',
            'order_id': order.id,
            'order_d_id': order.id,
            'order_created_at': fields.Date.to_string(order.create_date or fields.Datetime.now())[:10],
            'currency': order.currency_id.name,
            'currency_rate': 1,
            'issue_date': fields.Date.today().isoformat(),
            'issue_time': fields.Datetime.now().strftime('%H:%M'),
            'waybill_number': '',
            'waybill_date': '',
            'cash_sale': True,
            'payment_date': (self.payment_date or fields.Date.today()).isoformat() if hasattr(self, 'payment_date') else fields.Date.today().isoformat(),
            #'callback_url': self.env['ir.config_parameter'].sudo().get_param('web.base.url') + '/ginvoice-notification',
            'callback_url': 'https://11z27pqh6o.sharedwithexpose.com/ginvoice-notification',
            'lines': lines,
            'customer': {
                'id': order.partner_id.id,
                'type': 'company' if is_company else 'person',
                'tax_number': vat,
                'tax_office': '',
                'title': name if is_company else '',
                'name': first_name if not is_company else '',
                'surname': last_name if not is_company else '',
                'phone': self.customer_phone or '',
                'email': self.customer_email or '',
                'city': self.city or '',
                'district': (order.partner_invoice_id or order.partner_id).city or '',
                'address': (self.street or '')[:250],
                'postcode': self.zip or '',
                'country': self.country_code or '',
                'iban': None,
            },
            'is_need_shipment': bool(self.is_need_shipment),
            'shipment': self._prepare_shipment_data(),
            'is_internet_sale': bool(self.is_internet_sale),
            'internet_sale': {
                'web_address': self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
                'payment_method': self.payment_method or 'KREDIBANKAKARTI',
                'payment_platform': self.payment_platform or ((order.payment_term_id and order.payment_term_id.name) or 'ODoo'),
                'payment_date': (self.payment_date or fields.Date.today()).isoformat() if hasattr(self, 'payment_date') else fields.Date.today().isoformat(),
            },
            'description': order.company_id.fe_description or '',
        }

        try:
            data = client.invoice_store(payload)
        except UserError as e:
            # Client artık hatayı düz metne çeviriyor; doğrudan bildir
            full = str(e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Fatura Entegratör hata'),
                    'message': full,
                    'type': 'warning',
                    'sticky': False,
                }
            }
        external_id = (data.get('data') or {}).get('id') or data.get('id')
        if not external_id:
            raise UserError(_('Fatura Entegratör sipariş ID alınamadı.'))
        
        # Durum bilgisi
        status = (data.get('data') or {}).get('status') or data.get('status') or ''
        formal_status = (data.get('data') or {}).get('formal_status') or data.get('formal_status') or ''
        workflow_status = (data.get('data') or {}).get('workflow_status') or data.get('workflow_status') or ''
        
        # Durumu tek bir alana dönüştür
        fe_status = 'draft'
        if formal_status and 'formalized' in str(formal_status).lower():
            fe_status = 'formalized'
        elif workflow_status and 'approved' in str(workflow_status).lower():
            fe_status = 'formalized'
        elif status and 'sent' in str(status).lower():
            fe_status = 'sent'
        elif status and 'cancelled' in str(status).lower() or status and 'cancel' in str(status).lower():
            fe_status = 'cancelled'
        elif status and 'rejected' in str(status).lower() or status and 'reject' in str(status).lower():
            fe_status = 'rejected'
        elif status:
            fe_status = 'sent'
        
        # fe.invoice kaydı oluştur veya güncelle - sadece başarılı ise
        # fe_external_id ve fe_state artık fe_invoice_id üzerinden related field olarak geliyor
        if external_id:
            # Muafiyet bilgilerini topla (KDV 0 olan satırlardan)
            exemption_code = None
            exemption_reason = None
            if order.amount_tax == 0:
                # Tüm satırlarda KDV 0 ise, ilk satırdan muafiyet bilgisini al
                for line in order.order_line.filtered(lambda l: not l.display_type):
                    if line.tax_id and line.tax_id[0].amount == 0:
                        # Wizard line'dan exemption bilgilerini al
                        wl_key = (line.product_id.default_code or '', line.name or '')
                        for wl in self.line_ids:
                            if (wl.sku or '', wl.name or '') == wl_key:
                                exemption_code = wl.exemption_code or None
                                exemption_reason = wl.exemption_reason or None
                                break
                        if not exemption_code:
                            exemption_code = order.company_id.fe_exemption_code or None
                            exemption_reason = order.company_id.fe_exemption_reason or None
                        break
            
            fe_invoice = self.env['fe.invoice'].create_from_api_response(
                external_id=external_id,
                data={
                    **data,
                    'invoice': {
                        **(data.get('data') or data.get('invoice') or {}),
                        'number': order.name or '',
                        'date': fields.Date.today().isoformat(),
                        'move_type': 'out_invoice',
                        'status': status or '',
                        'formal_status': formal_status or '',
                        'workflow_status': workflow_status or '',
                        'exemption_code': exemption_code or '',
                        'exemption_reason': exemption_reason or '',
                    },
                    'callback_url': self.env['ir.config_parameter'].sudo().get_param('web.base.url') + '/fe-invoice-callback',
                },
                account_move_id=None,
                sale_order_id=order.id,
            )
        
        order.message_post(body=_('Sipariş FE\'ye gönderildi. ID: %s') % external_id)
        return {'type': 'ir.actions.act_window_close'}


class FESendOrderWizardLine(models.TransientModel):
    _name = 'fe.send.order.wizard.line'
    _description = 'Send Order Wizard Line'

    wizard_id = fields.Many2one('fe.send.order.wizard', ondelete='cascade')
    name = fields.Char(string='Açıklama')
    sku = fields.Char(string='SKU')
    quantity = fields.Float(string='Miktar')
    price_unit = fields.Monetary(string='Birim Fiyat', currency_field='currency_id')
    taxes = fields.Char(string='Vergiler')
    tax_rate = fields.Float(string='Vergi Oranı (%)', readonly=True)
    subtotal = fields.Monetary(string='Ara Toplam', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    exemption_code = fields.Char(string='Muafiyet Kodu')
    exemption_reason = fields.Char(string='Muafiyet Sebebi')


class FESendInvoiceWizard(models.TransientModel):
    _name = 'fe.send.invoice.wizard'
    _description = 'Send Invoice to Fatura Entegrator Wizard'

    move_id = fields.Many2one('account.move', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True)
    integration_choice_id = fields.Many2one(
        'fe.integration.temp',
        string='Entegrasyon',
        domain="[('company_id','=',company_id)]",
        required=True,
    )
    line_ids = fields.One2many('fe.send.invoice.wizard.line', 'wizard_id', string='Satırlar', readonly=True)

    # Düzenlenebilir Müşteri Bilgileri
    customer_name = fields.Char(string='Unvan/Ad Soyad')
    customer_vat = fields.Char(string='Vergi No / TCKN')
    customer_email = fields.Char(string='E-posta')
    customer_phone = fields.Char(string='Telefon')
    street = fields.Char(string='Adres')
    city = fields.Char(string='İl')
    zip = fields.Char(string='Posta Kodu')
    country_code = fields.Char(string='Ülke Kodu')
    currency_id = fields.Many2one('res.currency', string='Para Birimi')
    amount_untaxed = fields.Monetary(string='Vergisiz Tutar', currency_field='currency_id', readonly=True)
    amount_tax = fields.Monetary(string='Vergi', currency_field='currency_id', readonly=True)
    amount_total = fields.Monetary(string='Toplam', currency_field='currency_id', readonly=True)

    # İnternet Satışı ve Kargo
    is_internet_sale = fields.Boolean(string='İnternet satışı mı?', default=False)
    payment_method = fields.Selection(
        selection=[
            ('credit_or_debit', 'Banka/Kredi Kartı'),
            ('direct_transfer', 'EFT/Havale'),
            ('cash_on_delivery', 'Kapıda Ödeme'),
            ('payment_agent', 'Ödeme Aracısı'),
            ('other', 'Diğer'),
        ],
        string='Ödeme Yöntemi',
        default='credit_or_debit',
    )
    payment_platform = fields.Char(string='Ödeme Aracı / Platform')
    payment_date = fields.Date(string='Ödeme Tarihi')
    is_need_shipment = fields.Boolean(string='Teslimat gerekli mi?', default=False)
    shipment_company_title = fields.Char(string='Kargo Firması')
    shipment_company_tax_number = fields.Char(string='Firma Vergi No')
    shipment_courier_name = fields.Char(string='Kurye Ad')
    shipment_courier_tax_number = fields.Char(string='Kurye Vergi No')
    shipment_delivery_date = fields.Date(string='Teslimat Tarihi')

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        company = self.env.company
        if vals.get('company_id'):
            company = self.env['res.company'].browse(vals['company_id'])
        # FE'den entegrasyon listesini çek
        client = self.env['fe.client'].with_company(company.id)
        data = client.integration_invoice_index()
        items = data.get('data') or data or []
        if isinstance(items, dict):
            items = items.get('items') or []
        for it in items:
            name = it.get('name') or it.get('title') or (it.get('vendor') and it['vendor'].get('name')) or 'Integration'
            ext_id = it.get('id') or it.get('uuid') or ''
            if ext_id:
                self.env['fe.integration.temp'].create({
                    'name': name,
                    'external_id': str(ext_id),
                    'company_id': company.id,
                })
        # Satırları One2many komutlarıyla set et
        if vals.get('move_id'):
            move = self.env['account.move'].browse(vals['move_id'])
            partner = move.partner_id
            # Varsayılan ayarları company'den al
            vals.update({
                'customer_name': partner.name,
                'customer_vat': partner.vat or '',
                'customer_email': partner.email or '',
                'customer_phone': partner.phone or partner.mobile or '',
                'street': ((partner.street or '') + ' ' + (partner.street2 or '')).strip(),
                'city': (partner.state_id and partner.state_id.name) or '',
                'zip': partner.zip or '',
                'country_code': partner.country_id and partner.country_id.code or '',
                'currency_id': move.currency_id.id,
                'amount_total': move.amount_total,
                'amount_untaxed': move.amount_untaxed,
                'amount_tax': move.amount_tax,
                'is_internet_sale': company.fe_is_internet_sale,
                'is_need_shipment': company.fe_is_need_shipment,
                'payment_method': company.fe_payment_method or 'credit_or_debit',
                'payment_platform': company.fe_payment_platform or (move.payment_term_id and move.payment_term_id.name) or 'Odoo',
                'payment_date': fields.Date.today(),
                'shipment_company_title': company.fe_shipment_company_title or '',
                'shipment_company_tax_number': company.fe_shipment_company_tax_number or '',
                'shipment_courier_name': company.fe_shipment_courier_name or '',
                'shipment_courier_tax_number': company.fe_shipment_courier_tax_number or '',
                'shipment_delivery_date': fields.Date.today(),
            })
            commands = []
            for line in move.invoice_line_ids.filtered(lambda l: not l.display_type):
                taxes = ', '.join([f"{t.name} ({t.amount}%)" for t in line.tax_ids])
                # Vergi oranını hesapla
                tax_rate = 0
                if line.tax_ids:
                    tax = line.tax_ids[0]
                    tax_rate = tax.amount or 0
                # Vergi sıfırsa varsayılan muafiyet bilgilerini ekle
                exemption_code = None
                exemption_reason = None
                if tax_rate == 0:
                    exemption_code = company.fe_exemption_code or None
                    exemption_reason = company.fe_exemption_reason or None
                commands.append((0, 0, {
                    'name': line.name,
                    'sku': line.product_id.default_code or '',
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                    'taxes': taxes,
                    'tax_rate': tax_rate,
                    'subtotal': line.price_subtotal,
                    'currency_id': move.currency_id.id,
                    'exemption_code': exemption_code,
                    'exemption_reason': exemption_reason,
                }))
            vals['line_ids'] = commands
        return vals

    def _prepare_shipment_data(self):
        """Kargo bilgilerini hazırla."""
        company_title = self.shipment_company_title or ''
        company_tax_number = self.shipment_company_tax_number or ''
        
        if self.is_internet_sale and not company_title and not company_tax_number:
            company_title = 'vendor'
            company_tax_number = '1' * 11
        
        return {
            'company_title': company_title,
            'company_tax_number': company_tax_number,
            'courier_name': self.shipment_courier_name or '',
            'courier_tax_number': self.shipment_courier_tax_number or '',
            'delivery_date': (self.shipment_delivery_date or fields.Date.today()).isoformat(),
        }

    def action_confirm(self):
        self.ensure_one()
        move = self.move_id
        if not self.integration_choice_id:
            raise UserError(_('Lütfen bir entegrasyon seçin.'))
        client = move.company_id.fe_get_client()
        
        # Satır verileri
        lines = []
        wizard_lines_dict = {}
        for wl in self.line_ids:
            key = (wl.sku or '', wl.name or '')
            wizard_lines_dict[key] = wl
        
        for l in move.invoice_line_ids.filtered(lambda x: not x.display_type and x.quantity):
            tax_rate = 0
            if l.tax_ids:
                tax = l.tax_ids[0]
                tax_rate = int(round(tax.amount or 0))
            unit_price = l.price_subtotal / (l.quantity or 1)
            discount = (l.price_unit - unit_price) * l.quantity if l.price_unit and unit_price else 0
            
            # Wizard line'dan exemption bilgilerini al
            exemption_code = None
            exemption_reason = None
            wl_key = (l.product_id.default_code or '', l.name or '')
            if wl_key in wizard_lines_dict:
                wl = wizard_lines_dict[wl_key]
                exemption_code = wl.exemption_code or None
                exemption_reason = wl.exemption_reason or None
            
            if tax_rate == 0 and not exemption_code:
                exemption_code = move.company_id.fe_exemption_code or None
                exemption_reason = move.company_id.fe_exemption_reason or None
            
            line_payload = {
                'id': l.product_id.id or '',
                'name': l.product_id.display_name or l.name,
                'description': '',
                'sku': l.product_id.default_code or '',
                'quantity': l.quantity,
                'unit': 'C62',
                'unit_price': unit_price,
                'discount_type': 'amount',
                'discount': max(discount, 0),
                'tax_rate': tax_rate,
                'exemption_code': exemption_code,
                'exemption_reason': exemption_reason,
            }
            lines.append(line_payload)

        # Müşteri verileri
        vat = (self.customer_vat or '').replace(' ', '')
        is_company = len(vat) == 10
        name = self.customer_name or ''
        first_name = name
        last_name = ''
        if not is_company and ' ' in name:
            parts = name.strip().split(' ')
            first_name = ' '.join(parts[:-1])
            last_name = parts[-1]

        payload = {
            'sale_channel_id': move.company_id.fe_sale_channel_id,
            'invoice_integration_id': self.integration_choice_id.external_id,
            'type': 'SATIS',
            'order_id': move.id,
            'order_d_id': move.id,
            'order_created_at': fields.Date.to_string(move.create_date or fields.Datetime.now())[:10],
            'currency': move.currency_id.name,
            'currency_rate': 1,
            'issue_date': fields.Date.today().isoformat(),
            'issue_time': fields.Datetime.now().strftime('%H:%M'),
            'waybill_number': '',
            'waybill_date': '',
            'cash_sale': True,
            'payment_date': (self.payment_date or fields.Date.today()).isoformat(),
            'callback_url': self.env['ir.config_parameter'].sudo().get_param('web.base.url') + '/ginvoice-notification',
            'lines': lines,
            'customer': {
                'id': move.partner_id.id,
                'type': 'company' if is_company else 'person',
                'tax_number': vat,
                'tax_office': '',
                'title': name if is_company else '',
                'name': first_name if not is_company else '',
                'surname': last_name if not is_company else '',
                'phone': self.customer_phone or '',
                'email': self.customer_email or '',
                'city': self.city or '',
                'district': move.partner_id.city or '',
                'address': (self.street or '')[:250],
                'postcode': self.zip or '',
                'country': self.country_code or '',
                'iban': None,
            },
            'is_need_shipment': bool(self.is_need_shipment),
            'shipment': self._prepare_shipment_data(),
            'is_internet_sale': bool(self.is_internet_sale),
            'internet_sale': {
                'web_address': self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
                'payment_method': self.payment_method or 'KREDIBANKAKARTI',
                'payment_platform': self.payment_platform or (move.payment_term_id and move.payment_term_id.name) or 'Odoo',
                'payment_date': (self.payment_date or fields.Date.today()).isoformat(),
            },
            'description': move.company_id.fe_description or '',
        }

        try:
            data = client.invoice_store(payload)
        except UserError as e:
            full = str(e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Fatura Entegratör hata'),
                    'message': full,
                    'type': 'warning',
                    'sticky': False,
                }
            }
        external_id = (data.get('data') or {}).get('id') or data.get('id')
        if not external_id:
            raise UserError(_('Fatura Entegratör fatura ID alınamadı.'))
        
        status = (data.get('data') or {}).get('status') or data.get('status') or ''
        formal_status = (data.get('data') or {}).get('formal_status') or data.get('formal_status') or ''
        workflow_status = (data.get('data') or {}).get('workflow_status') or data.get('workflow_status') or ''
        
        fe_status = 'draft'
        if formal_status and 'formalized' in str(formal_status).lower():
            fe_status = 'formalized'
        elif workflow_status and 'approved' in str(workflow_status).lower():
            fe_status = 'formalized'
        elif status and 'sent' in str(status).lower():
            fe_status = 'sent'
        elif status and 'cancelled' in str(status).lower() or status and 'cancel' in str(status).lower():
            fe_status = 'cancelled'
        elif status and 'rejected' in str(status).lower() or status and 'reject' in str(status).lower():
            fe_status = 'rejected'
        elif status:
            fe_status = 'sent'
        
        if external_id:
            # Muafiyet bilgilerini topla
            exemption_code = None
            exemption_reason = None
            if move.amount_tax == 0:
                for line in move.invoice_line_ids.filtered(lambda l: not l.display_type):
                    if line.tax_ids and line.tax_ids[0].amount == 0:
                        wl_key = (line.product_id.default_code or '', line.name or '')
                        for wl in self.line_ids:
                            if (wl.sku or '', wl.name or '') == wl_key:
                                exemption_code = wl.exemption_code or None
                                exemption_reason = wl.exemption_reason or None
                                break
                        if not exemption_code:
                            exemption_code = move.company_id.fe_exemption_code or None
                            exemption_reason = move.company_id.fe_exemption_reason or None
                        break
            
            fe_invoice = self.env['fe.invoice'].create_from_api_response(
                external_id=external_id,
                data={
                    **data,
                    'invoice': {
                        **(data.get('data') or data.get('invoice') or {}),
                        'number': move.name or '',
                        'date': fields.Date.to_string(move.invoice_date) if move.invoice_date else fields.Date.today().isoformat(),
                        'move_type': move.move_type,
                        'status': status or '',
                        'formal_status': formal_status or '',
                        'workflow_status': workflow_status or '',
                        'exemption_code': exemption_code or '',
                        'exemption_reason': exemption_reason or '',
                    },
                    'callback_url': self.env['ir.config_parameter'].sudo().get_param('web.base.url') + '/fe-invoice-callback',
                },
                account_move_id=move.id,
                sale_order_id=None,
            )
        
        move.message_post(body=_('Fatura FE\'ye gönderildi. ID: %s') % external_id)
        return {'type': 'ir.actions.act_window_close'}


class FESendInvoiceWizardLine(models.TransientModel):
    _name = 'fe.send.invoice.wizard.line'
    _description = 'Send Invoice Wizard Line'

    wizard_id = fields.Many2one('fe.send.invoice.wizard', ondelete='cascade')
    name = fields.Char(string='Açıklama')
    sku = fields.Char(string='SKU')
    quantity = fields.Float(string='Miktar')
    price_unit = fields.Monetary(string='Birim Fiyat', currency_field='currency_id')
    taxes = fields.Char(string='Vergiler')
    tax_rate = fields.Float(string='Vergi Oranı (%)', readonly=True)
    subtotal = fields.Monetary(string='Ara Toplam', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    exemption_code = fields.Char(string='Muafiyet Kodu')
    exemption_reason = fields.Char(string='Muafiyet Sebebi')


