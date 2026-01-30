# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class LucaExportWizard(models.TransientModel):
    """
    Luca Export Wizard
    Kullanıcının export parametrelerini seçmesini sağlar
    """
    _name = 'luca.export.wizard'
    _description = 'Luca Export Sihirbazı'

    # Export Tipi
    export_type = fields.Selection([
        ('journal_entries', 'Muhasebe Fişleri'),
        ('chart_of_accounts', 'Hesap Planı'),
        ('partners', 'Cari Bilgileri'),
    ], string='Export Tipi', required=True, default='journal_entries')

    # Tarih Aralığı (Muhasebe Fişleri için)
    date_from = fields.Date(
        string='Başlangıç Tarihi',
        default=lambda self: date(date.today().year, 1, 1),
    )
    date_to = fields.Date(
        string='Bitiş Tarihi',
        default=fields.Date.today,
    )

    # Fiş Durumu
    move_state = fields.Selection([
        ('posted', 'Sadece Onaylı'),
        ('draft', 'Sadece Taslak'),
        ('all', 'Tümü'),
    ], string='Fiş Durumu', default='posted')

    # Fiş Tipi
    move_type = fields.Selection([
        ('all', 'Tümü'),
        ('entry', 'Yevmiye Fişi'),
        ('out_invoice', 'Satış Faturası'),
        ('in_invoice', 'Alış Faturası'),
        ('out_refund', 'Satış İade'),
        ('in_refund', 'Alış İade'),
    ], string='Fiş Tipi', default='all')

    # Hesap Filtresi
    account_ids = fields.Many2many(
        'account.account',
        string='Hesap Filtresi',
        help='Boş bırakılırsa tüm hesaplar dahil edilir',
    )

    # Export Formatı
    file_format = fields.Selection([
        ('csv', 'CSV (Noktalı Virgül Ayraçlı)'),
        ('xlsx', 'Excel (.xlsx)'),
        ('xml', 'XML (Hesap Planı için)'),
    ], string='Dosya Formatı', default='csv')

    # Dosya bölme (50 fiş limiti)
    split_files = fields.Boolean(
        string='Dosyaları Böl (50 fiş/dosya)',
        default=True,
        help='Luca maksimum 50 fiş/yükleme kabul eder',
    )

    # Export Sonucu
    state = fields.Selection([
        ('choose', 'Seçim'),
        ('preview', 'Önizleme'),
        ('done', 'Tamamlandı'),
    ], string='Durum', default='choose')

    # Önizleme bilgileri
    preview_count = fields.Integer(string='Toplam Kayıt', readonly=True)
    preview_info = fields.Text(string='Önizleme', readonly=True)

    # İndirme dosyası
    file_data = fields.Binary(string='Dosya', readonly=True)
    file_name = fields.Char(string='Dosya Adı', readonly=True)

    # Çoklu dosya (bölünmüşse)
    file_data_2 = fields.Binary(string='Dosya 2', readonly=True)
    file_name_2 = fields.Char(string='Dosya Adı 2', readonly=True)
    file_data_3 = fields.Binary(string='Dosya 3', readonly=True)
    file_name_3 = fields.Char(string='Dosya Adı 3', readonly=True)

    @api.onchange('export_type')
    def _onchange_export_type(self):
        """Export tipine göre format ayarla"""
        if self.export_type == 'chart_of_accounts':
            self.file_format = 'xml'
        elif self.export_type == 'partners':
            self.file_format = 'csv'
        else:
            self.file_format = 'csv'

    def action_preview(self):
        """Önizleme göster"""
        self.ensure_one()

        if self.export_type == 'journal_entries':
            moves = self._get_moves()
            self.preview_count = len(moves)
            line_count = sum(len(m.line_ids) for m in moves)

            self.preview_info = _(
                "Toplam %(move_count)d fiş, %(line_count)d satır\n"
                "Tarih: %(date_from)s - %(date_to)s\n"
                "Durum: %(state)s\n"
                "Tip: %(type)s\n\n"
                "İlk 5 fiş:\n%(moves)s"
            ) % {
                'move_count': len(moves),
                'line_count': line_count,
                'date_from': self.date_from,
                'date_to': self.date_to,
                'state': dict(self._fields['move_state'].selection).get(self.move_state),
                'type': dict(self._fields['move_type'].selection).get(self.move_type),
                'moves': '\n'.join(['- %s (%s) - %d satır' % (m.name, m.date, len(m.line_ids)) for m in moves[:5]]),
            }

        elif self.export_type == 'chart_of_accounts':
            accounts = self._get_accounts()
            self.preview_count = len(accounts)

            # Hesap tiplerini say
            type_counts = {}
            for acc in accounts:
                acc_type = acc.account_type or 'other'
                type_counts[acc_type] = type_counts.get(acc_type, 0) + 1

            self.preview_info = _(
                "Toplam %(count)d hesap\n\n"
                "Hesap Tipleri:\n%(types)s\n\n"
                "İlk 10 hesap:\n%(accounts)s"
            ) % {
                'count': len(accounts),
                'types': '\n'.join(['- %s: %d' % (k, v) for k, v in type_counts.items()]),
                'accounts': '\n'.join(['- %s %s' % (a.code, a.name) for a in accounts[:10]]),
            }

        elif self.export_type == 'partners':
            partners = self._get_partners()
            self.preview_count = len(partners)

            company_count = len(partners.filtered(lambda p: p.is_company))
            person_count = len(partners) - company_count

            self.preview_info = _(
                "Toplam %(count)d cari\n"
                "Şirket: %(company)d\n"
                "Şahıs: %(person)d\n\n"
                "İlk 10 cari:\n%(partners)s"
            ) % {
                'count': len(partners),
                'company': company_count,
                'person': person_count,
                'partners': '\n'.join(['- %s (%s)' % (p.name, p.vat or 'VKN yok') for p in partners[:10]]),
            }

        self.state = 'preview'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'luca.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_export(self):
        """Export işlemini gerçekleştir"""
        self.ensure_one()

        if self.export_type == 'journal_entries':
            self._export_journal_entries()
        elif self.export_type == 'chart_of_accounts':
            self._export_chart_of_accounts()
        elif self.export_type == 'partners':
            self._export_partners()

        self.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'luca.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back(self):
        """Seçim ekranına geri dön"""
        self.state = 'choose'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'luca.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_moves(self):
        """Filtreli muhasebe fişlerini getir"""
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]

        if self.move_state == 'posted':
            domain.append(('state', '=', 'posted'))
        elif self.move_state == 'draft':
            domain.append(('state', '=', 'draft'))

        if self.move_type != 'all':
            domain.append(('move_type', '=', self.move_type))

        if self.account_ids:
            domain.append(('line_ids.account_id', 'in', self.account_ids.ids))

        return self.env['account.move'].search(domain, order='date, name')

    def _get_accounts(self):
        """Hesap planını getir"""
        domain = []
        if self.account_ids:
            domain = [('id', 'in', self.account_ids.ids)]
        return self.env['account.account'].search(domain, order='code')

    def _get_partners(self):
        """Carileri getir"""
        # Sadece müşteri veya tedarikçi olanlar
        domain = [
            '|',
            ('customer_rank', '>', 0),
            ('supplier_rank', '>', 0),
        ]
        return self.env['res.partner'].search(domain, order='name')

    def _export_journal_entries(self):
        """Muhasebe fişlerini export et"""
        moves = self._get_moves()

        if not moves:
            raise UserError(_('Export edilecek fiş bulunamadı!'))

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if self.file_format == 'xlsx':
            # Excel export
            data = moves.export_to_luca_excel()
            self.file_data = base64.b64encode(data)
            self.file_name = 'luca_fisler_%s.xlsx' % timestamp

        else:
            # CSV export
            if self.split_files and len(moves) > 50:
                # Dosyaları böl
                chunks = [moves[i:i+50] for i in range(0, len(moves), 50)]

                for idx, chunk in enumerate(chunks[:3]):  # Max 3 dosya
                    data = chunk.export_to_luca_csv(include_header=True)
                    encoded = base64.b64encode(data.encode('utf-8-sig'))

                    if idx == 0:
                        self.file_data = encoded
                        self.file_name = 'luca_fisler_%s_part1.csv' % timestamp
                    elif idx == 1:
                        self.file_data_2 = encoded
                        self.file_name_2 = 'luca_fisler_%s_part2.csv' % timestamp
                    elif idx == 2:
                        self.file_data_3 = encoded
                        self.file_name_3 = 'luca_fisler_%s_part3.csv' % timestamp

                if len(chunks) > 3:
                    self.preview_info = _(
                        'Uyarı: %d dosyadan sadece ilk 3 tanesi oluşturuldu. '
                        'Kalan fişler için tarihi daraltın.'
                    ) % len(chunks)
            else:
                data = moves.export_to_luca_csv(include_header=True)
                self.file_data = base64.b64encode(data.encode('utf-8-sig'))
                self.file_name = 'luca_fisler_%s.csv' % timestamp

    def _export_chart_of_accounts(self):
        """Hesap planını export et"""
        accounts = self._get_accounts()

        if not accounts:
            raise UserError(_('Export edilecek hesap bulunamadı!'))

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        data = accounts.export_to_luca_xml()
        self.file_data = base64.b64encode(data)
        self.file_name = 'luca_hesapplani_%s.xml' % timestamp

    def _export_partners(self):
        """Cari bilgilerini export et"""
        partners = self._get_partners()

        if not partners:
            raise UserError(_('Export edilecek cari bulunamadı!'))

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        data = partners.export_to_luca_csv(include_header=True)
        self.file_data = base64.b64encode(data.encode('utf-8-sig'))
        self.file_name = 'luca_cariler_%s.csv' % timestamp
