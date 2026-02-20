/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * MobilSoft Ana Sayfa - OWL Dashboard
 *
 * Odoo 19 uyumlu: `rpc` servisi kaldırıldı, `orm` servisi kullanılıyor.
 */
export class MobilSoftHome extends Component {
    static template = "mobilsoft_interface.MobilSoftHome";
    static props = {};

    setup() {
        // Odoo 19: rpc servisi yok, orm kullan
        this.action = useService("action");
        this.orm = useService("orm");
        this.user = useService("user");
        this.notification = useService("notification");

        this.state = useState({
            companyName: "",
            stats: {
                todaySales: "0,00",
                pendingInvoices: 0,
                stockAlerts: 0,
            },
            posConfig: null,
            loading: true,
        });

        onMounted(() => this._loadDashboardData());
    }

    async _loadDashboardData() {
        try {
            // Şirket adı
            const companyId = this.user.context.allowed_company_ids
                ? this.user.context.allowed_company_ids[0]
                : this.user.company?.id;

            if (companyId) {
                const companies = await this.orm.read(
                    "res.company",
                    [companyId],
                    ["name"]
                );
                if (companies.length) {
                    this.state.companyName = companies[0].name;
                }
            }

            // Bugünün satışları
            const today = new Date().toISOString().split("T")[0];
            const todaySales = await this.orm.searchRead(
                "sale.order",
                [
                    ["date_order", ">=", today + " 00:00:00"],
                    ["state", "in", ["sale", "done"]],
                ],
                ["amount_total"]
            );
            const totalSales = todaySales.reduce(
                (s, o) => s + (o.amount_total || 0),
                0
            );
            this.state.stats.todaySales = this.formatCurrency(totalSales);

            // Bekleyen faturalar
            this.state.stats.pendingInvoices = await this.orm.searchCount(
                "account.move",
                [
                    ["move_type", "in", ["out_invoice", "in_invoice"]],
                    ["payment_state", "in", ["not_paid", "partial"]],
                    ["state", "=", "posted"],
                ]
            );

            // Kritik stok uyarıları (storable, sıfırın altında)
            this.state.stats.stockAlerts = await this.orm.searchCount(
                "product.product",
                [["qty_available", "<=", 0], ["type", "=", "consu"], ["is_storable", "=", true]]
            );

            // POS konfigürasyonu (bu şirkete ait)
            const posConfigs = await this.orm.searchRead(
                "pos.config",
                [["active", "=", true]],
                ["id", "name", "current_session_id"],
                { limit: 1 }
            );
            this.state.posConfig = posConfigs.length ? posConfigs[0] : null;

        } catch (e) {
            console.error("MobilSoft dashboard yükleme hatası:", e);
        } finally {
            this.state.loading = false;
        }
    }

    // === Navigasyon Metodları ===

    async openPOS() {
        if (!this.state.posConfig) {
            this.notification.add(
                _t("Kasa sistemi bulunamadı. Lütfen yöneticiye başvurun."),
                { type: "warning" }
            );
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_url",
            url: `/odoo/point-of-sale/shop/${this.state.posConfig.id}`,
            target: "self",
        });
    }

    openInvoices() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Faturalar"),
            res_model: "account.move",
            domain: [["move_type", "in", ["out_invoice", "in_invoice"]]],
            views: [[false, "list"], [false, "form"]],
            context: { default_move_type: "out_invoice" },
        });
    }

    openSales() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Satış Siparişleri"),
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
        });
    }

    openStock() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Stok"),
            res_model: "product.product",
            domain: [["type", "=", "consu"]],
            views: [[false, "list"], [false, "form"]],
        });
    }

    openPartners() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Cariler"),
            res_model: "res.partner",
            domain: ["|", ["customer_rank", ">", 0], ["supplier_rank", ">", 0]],
            views: [[false, "list"], [false, "form"]],
        });
    }

    openPurchases() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Alış Siparişleri"),
            res_model: "purchase.order",
            views: [[false, "list"], [false, "form"]],
        });
    }

    openNewSaleInvoice() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Yeni Satış Faturası"),
            res_model: "account.move",
            views: [[false, "form"]],
            context: { default_move_type: "out_invoice" },
        });
    }

    openNewProduct() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Yeni Ürün"),
            res_model: "product.product",
            views: [[false, "form"]],
        });
    }

    formatCurrency(val) {
        return Number(val || 0).toLocaleString("tr-TR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }
}

registry.category("actions").add("mobilsoft_home", MobilSoftHome);
