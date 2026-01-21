# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    # QNB e-Solutions API Ayarları
    qnb_enabled = fields.Boolean(
        string='QNB e-Solutions Aktif',
        default=False,
        help='QNB e-Solutions entegrasyonunu etkinleştir'
    )
    qnb_environment = fields.Selection([
        ('test', 'Test Ortamı'),
        ('production', 'Canlı Ortam')
    ], string='QNB Ortam', default='test',
        help='Test ortamı: connectortest.efinans.com.tr\nCanlı ortam: connector.efinans.com.tr')

    qnb_username = fields.Char(
        string='QNB Kullanıcı Adı',
        help='QNB e-Solutions API kullanıcı adı'
    )
    qnb_password = fields.Char(
        string='QNB Şifre',
        help='QNB e-Solutions API şifresi'
    )
    qnb_wsdl_url = fields.Char(
        string='Özel WSDL URL',
        help='Özel test ortamı için WSDL URL (boş bırakılırsa varsayılan kullanılır)\n'
             'Test1: https://erpefaturatest1.qnbesolutions.com.tr/efatura/ws/connectorService?wsdl\n'
             'Test2: https://erpefaturatest2.qnbesolutions.com.tr/efatura/ws/connectorService?wsdl'
    )

    # e-Fatura Ayarları
    qnb_efatura_enabled = fields.Boolean(
        string='e-Fatura Aktif',
        default=True,
        help='e-Fatura gönderimi aktif'
    )
    qnb_efatura_scenario = fields.Selection([
        ('TEMELFATURA', 'Temel Fatura'),
        ('TICARIFATURA', 'Ticari Fatura')
    ], string='e-Fatura Senaryosu', default='TEMELFATURA',
        help='Temel Fatura: Tek yönlü gönderim\nTicari Fatura: Kabul/Red yanıtı bekler')

    qnb_efatura_prefix = fields.Char(
        string='e-Fatura Seri Öneki',
        default='EF',
        size=3,
        help='e-Fatura numarası seri öneki (max 3 karakter)'
    )

    # e-Arşiv Ayarları
    qnb_earsiv_enabled = fields.Boolean(
        string='e-Arşiv Aktif',
        default=True,
        help='e-Arşiv fatura gönderimi aktif'
    )
    qnb_earsiv_prefix = fields.Char(
        string='e-Arşiv Seri Öneki',
        default='EA',
        size=3,
        help='e-Arşiv fatura numarası seri öneki'
    )
    qnb_earsiv_send_type = fields.Selection([
        ('KAGIT', 'Kağıt'),
        ('ELEKTRONIK', 'Elektronik')
    ], string='e-Arşiv Gönderim Tipi', default='ELEKTRONIK',
        help='Alıcıya gönderim yöntemi')

    # e-İrsaliye Ayarları
    qnb_eirsaliye_enabled = fields.Boolean(
        string='e-İrsaliye Aktif',
        default=True,
        help='e-İrsaliye gönderimi aktif'
    )
    qnb_eirsaliye_prefix = fields.Char(
        string='e-İrsaliye Seri Öneki',
        default='IR',
        size=3,
        help='e-İrsaliye numarası seri öneki'
    )

    # Otomatik İşlemler
    qnb_auto_fetch_incoming = fields.Boolean(
        string='Gelen Belgeleri Otomatik Al',
        default=True,
        help='Gelen belgeleri otomatik olarak indir'
    )
    qnb_auto_check_status = fields.Boolean(
        string='Durumu Otomatik Kontrol Et',
        default=True,
        help='Gönderilen belgelerin durumunu otomatik kontrol et'
    )

    # Şirket e-Fatura Bilgileri
    qnb_gib_alias = fields.Char(
        string='GİB Etiket (Posta Kutusu)',
        help='e-Fatura sistemindeki posta kutusu etiketi'
    )
    qnb_sender_alias = fields.Char(
        string='Gönderici Etiketi',
        help='Varsayılan gönderici etiketi'
    )

    @api.model
    def _cron_check_credit_alert(self):
        """Kontör uyarı kontrolü (Cron Job)"""
        companies = self.search([('qnb_enabled', '=', True)])
        
        for company in companies:
            try:
                from .qnb_api import QNBeSolutionsAPI
                api = QNBeSolutionsAPI(company)
                
                result = api.get_credit_status()
                
                # Kontör azaldıysa uyarı gönder
                threshold = 100  # Minimum kontör eşiği
                
                low_credits = []
                if result.get('efatura_credit', 0) < threshold:
                    low_credits.append(f"e-Fatura: {result.get('efatura_credit', 0)}")
                if result.get('earsiv_credit', 0) < threshold:
                    low_credits.append(f"e-Arşiv: {result.get('earsiv_credit', 0)}")
                if result.get('eirsaliye_credit', 0) < threshold:
                    low_credits.append(f"e-İrsaliye: {result.get('eirsaliye_credit', 0)}")
                
                if low_credits:
                    # Sistem yöneticilerine mail gönder
                    admin_users = self.env['res.users'].search([
                        ('groups_id', 'in', self.env.ref('base.group_system').id)
                    ])
                    
                    for user in admin_users:
                        if user.email:
                            self.env['mail.mail'].create({
                                'subject': f'⚠️ QNB e-Solutions Kontör Uyarısı - {company.name}',
                                'body_html': f'''
                                    <p>Sayın {user.name},</p>
                                    <p><strong>{company.name}</strong> için aşağıdaki kontörler kritik seviyede:</p>
                                    <ul>
                                        {"".join(f"<li>{c}</li>" for c in low_credits)}
                                    </ul>
                                    <p>Lütfen kontör satın alınız.</p>
                                ''',
                                'email_to': user.email,
                                'auto_delete': True,
                            }).send()
                
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Credit check error for {company.name}: {e}")
