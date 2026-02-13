# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BankSyncWizard(models.TransientModel):
    """Wizard for batch syncing bank data across all connector types."""

    _name = 'bank.sync.wizard'
    _description = 'Banka Senkronizasyon Sihirbazı'

    connector_ids = fields.Many2many(
        'bank.connector',
        string='Konektörler',
        help='Senkronize edilecek banka bağlantılarını seçin',
    )
    sync_type = fields.Selection(
        [
            ('accounts', 'Sadece Hesaplar'),
            ('transactions', 'Sadece İşlemler'),
            ('rates', 'Sadece Döviz Kurları'),
            ('all', 'Hepsi'),
        ],
        string='Senkronizasyon Tipi',
        default='all',
        required=True,
    )
    date_from = fields.Date(
        string='Başlangıç Tarihi',
        default=lambda self: fields.Date.today() - timedelta(days=30),
    )
    date_to = fields.Date(
        string='Bitiş Tarihi',
        default=fields.Date.today,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        connectors = self.env['bank.connector'].search(
            [('state', '=', 'connected')],
        )
        res['connector_ids'] = [(6, 0, connectors.ids)]
        return res

    def action_sync(self):
        self.ensure_one()

        if not self.connector_ids:
            raise UserError(_('En az bir konektör seçin.'))

        results = []

        for connector in self.connector_ids:
            try:
                if self.sync_type in ('accounts', 'all'):
                    connector.sync_accounts()
                    results.append(f'{connector.name}: Hesaplar OK')

                if self.sync_type in ('transactions', 'all'):
                    connector.sync_transactions(
                        self.date_from, self.date_to,
                    )
                    results.append(f'{connector.name}: İşlemler OK')

                if self.sync_type in ('rates', 'all'):
                    connector.sync_exchange_rates()
                    results.append(f'{connector.name}: Kurlar OK')

            except Exception as e:
                results.append(f'{connector.name}: HATA - {e}')

        message = '\n'.join(results)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Senkronizasyon Tamamlandı'),
                'message': message,
                'type': 'success',
                'sticky': True,
            },
        }
