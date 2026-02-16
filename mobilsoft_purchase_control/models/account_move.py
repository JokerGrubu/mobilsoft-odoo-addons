# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    purchase_verification_status = fields.Selection([
        ('not_applicable', 'Uygulanmaz'),
        ('pending', 'Kontrol Bekliyor'),
        ('verified', 'Doğrulandı'),
        ('rejected', 'Reddedildi'),
    ], string='Fiyat Kontrol Durumu', default='not_applicable',
        copy=False, tracking=True)

    purchase_verification_date = fields.Datetime(
        string='Son Kontrol Tarihi', copy=False, readonly=True)

    purchase_verification_note = fields.Text(
        string='Kontrol Notu', copy=False, readonly=True)

    purchase_stock_picking_id = fields.Many2one(
        'stock.picking', string='Stok Girişi', copy=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if move.move_type == 'in_invoice':
                move.purchase_verification_status = 'pending'
        return moves

    def write(self, vals):
        res = super().write(vals)
        # Satır değişirse pending'e döndür
        if 'invoice_line_ids' in vals:
            for move in self:
                if (move.move_type == 'in_invoice'
                        and move.purchase_verification_status in ('verified', 'rejected')):
                    move.purchase_verification_status = 'pending'
        return res

    def action_verify_prices(self):
        """Tüm fatura satırlarının fiyatlarını tedarikçi maliyetiyle karşılaştır."""
        self.ensure_one()
        if self.move_type != 'in_invoice':
            raise UserError(_("Bu işlem sadece tedarikçi faturaları için geçerlidir."))

        if self.state != 'draft':
            raise UserError(_("Sadece taslak faturalar kontrol edilebilir."))

        lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        if not lines:
            raise UserError(_("Faturada ürün satırı bulunamadı."))

        all_match = True
        notes = []
        mismatch_count = 0
        no_price_count = 0

        for line in lines:
            line._compute_price_verification()

            if not line.expected_price_usd:
                all_match = False
                no_price_count += 1
                notes.append(
                    f"• {line.product_id.display_name}: "
                    f"Tedarikçi USD fiyatı tanımlanmamış"
                )
            elif not line.price_match:
                all_match = False
                mismatch_count += 1
                notes.append(
                    f"• {line.product_id.display_name}: "
                    f"Beklenen {line.expected_price_try:.2f} TRY "
                    f"(USD {line.expected_price_usd:.2f} × kur), "
                    f"Fatura {line.price_unit:.2f} TRY, "
                    f"Fark {line.price_difference:+.2f} TRY"
                )

        summary = f"Kontrol: {len(lines)} satır"
        if mismatch_count:
            summary += f", {mismatch_count} fiyat uyuşmazlığı"
        if no_price_count:
            summary += f", {no_price_count} fiyat tanımsız"
        if all_match:
            summary += " - TÜMÜ DOĞRU"

        self.write({
            'purchase_verification_status': 'verified' if all_match else 'rejected',
            'purchase_verification_date': fields.Datetime.now(),
            'purchase_verification_note': summary + ('\n' + '\n'.join(notes) if notes else ''),
        })

        notification_type = 'success' if all_match else 'danger'
        message = _("Tüm fiyatlar doğrulandı!") if all_match else _(
            "%d satırda uyuşmazlık tespit edildi.", mismatch_count + no_price_count)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fiyat Kontrolü'),
                'message': message,
                'type': notification_type,
                'sticky': not all_match,
            }
        }

    def action_approve_and_receive(self):
        """Doğrulanmış faturayı onayla ve SAYIM deposuna stok girişi oluştur."""
        self.ensure_one()
        if self.purchase_verification_status != 'verified':
            raise UserError(_("Sadece doğrulanmış faturalar onaylanabilir."))

        if self.state != 'draft':
            raise UserError(_("Fatura zaten onaylanmış."))

        # 1. Faturayı onayla
        self.action_post()

        # 2. SAYIM deposuna stok girişi oluştur
        picking = self._create_stock_receipt()
        if picking:
            self.purchase_stock_picking_id = picking.id

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Fatura Onaylandı'),
                'message': _("Fatura onaylandı ve %s numaralı stok girişi oluşturuldu.",
                             picking.name if picking else '-'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _create_stock_receipt(self):
        """SAYIM deposuna incoming stock picking oluştur."""
        self.ensure_one()

        # SAYIM deposu incoming picking type (ID: 103)
        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id.code', '=', 'SM'),
            ('code', '=', 'incoming'),
        ], limit=1)

        if not picking_type:
            raise UserError(_(
                "SAYIM deposu için alım (incoming) işlem tipi bulunamadı."))

        supplier_location = self.env['stock.location'].search([
            ('usage', '=', 'supplier'),
        ], limit=1)

        dest_location = picking_type.default_location_dest_id
        if not dest_location:
            raise UserError(_("SAYIM deposu hedef konumu bulunamadı."))

        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.product_id)

        if not product_lines:
            return False

        move_vals = []
        for line in product_lines:
            move_vals.append({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_uom_id.id,
                'price_unit': line.price_unit,
                'location_id': supplier_location.id,
                'location_dest_id': dest_location.id,
            })

        picking = self.env['stock.picking'].create({
            'partner_id': self.partner_id.id,
            'picking_type_id': picking_type.id,
            'location_id': supplier_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name or self.ref or '',
            'move_ids': [(0, 0, vals) for vals in move_vals],
        })

        _logger.info(
            "Fatura %s için SAYIM stok girişi oluşturuldu: %s (%d satır)",
            self.name, picking.name, len(move_vals))

        return picking

    def action_reject_invoice(self):
        """Faturayı manuel olarak reddet."""
        self.ensure_one()
        if self.move_type != 'in_invoice':
            raise UserError(_("Bu işlem sadece tedarikçi faturaları için geçerlidir."))
        self.write({
            'purchase_verification_status': 'rejected',
            'purchase_verification_date': fields.Datetime.now(),
        })

    def action_view_stock_picking(self):
        """İlgili stok girişini göster."""
        self.ensure_one()
        if not self.purchase_stock_picking_id:
            raise UserError(_("Bu faturaya bağlı stok girişi bulunamadı."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': self.purchase_stock_picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
