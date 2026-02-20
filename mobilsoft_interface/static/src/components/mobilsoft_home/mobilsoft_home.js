/** @odoo-module **/

import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * MobilSoft Ana Sayfa - OWL Dashboard
 *
 * Odoo'nun karmaşık arayüzü yerine gösterilen,
 * bakkal/market/KOBİ için özelleştirilmiş sade dashboard.
 */
export class MobilSoftHome extends Component {
    static template = "mobilsoft_interface.MobilSoftHome";
    static props = {};

    setup() {
        this.action = useService("action");
        this.rpc = useService("rpc");
        this.user = useService("user");
        this.notification = useService("notification");

        this.state = useState({
            companyName: this.user.name || "Şirketim",
            userName: this.user.name || "",
            stats: {
                todaySales: 0,
                pendingInvoices: 0,
                stockAlerts: 0,
                cashBalance: 0,
            },
            posConfig: null,
            loading: true,
        });

        onMounted(() => this._loadDashboardData());
    }

    async _loadDashboardData() {
        try {
            // Şirket bilgisi
            const company = await this.rpc("/web/dataset/call_kw", {
                model: "res.company",
                method: "read",
                args: [[this.user.company.id], ["name", "currency_id"]],
                kwargs: {},
            });
            if (company && company[0]) {
                this.state.companyName = company[0].name;
            }

            // Bugünün satışları (satış siparişleri)
            const today = new Date().toISOString().split("T")[0];
            const todaySales = await this.rpc("/web/dataset/call_kw", {
                model: "sale.order",
                method: "search_read",
                args: [[
                    ["date_order", ">=", today + " 00:00:00"],
                    ["state", "in", ["sale", "done"]],
                ]],
                kwargs: { fields: ["amount_total"], limit: 0 },
            });
            this.state.stats.todaySales = todaySales
                .reduce((s, o) => s + (o.amount_total || 0), 0)
                .toFixed(2);

            // Bekleyen faturalar
            const pendingInvoices = await this.rpc("/web/dataset/call_kw", {
                model: "account.move",
                method: "search_count",
                args: [[
                    ["move_type", "in", ["out_invoice", "in_invoice"]],
                    ["payment_state", "in", ["not_paid", "partial"]],
                    ["state", "=", "posted"],
                ]],
                kwargs: {},
            });
            this.state.stats.pendingInvoices = pendingInvoices;

            // Kritik stok uyarıları (sıfır veya negatif)
            const stockAlerts = await this.rpc("/web/dataset/call_kw", {
                model: "product.product",
                method: "search_count",
                args: [[["qty_available", "<=", 0], ["type", "=", "consu"]]],
                kwargs: {},
            });
            this.state.stats.stockAlerts = stockAlerts;

            // POS konfigürasyonu
            const posConfigs = await this.rpc("/web/dataset/call_kw", {
                model: "pos.config",
                method: "search_read",
                args: [[["active", "=", true]]],
                kwargs: { fields: ["id", "name", "current_session_id"], limit: 1 },
            });
            this.state.posConfig = posConfigs && posConfigs[0] ? posConfigs[0] : null;

        } catch (e) {
            console.error("MobilSoft dashboard yükleme hatası:", e);
        } finally {
            this.state.loading = false;
        }
    }

    // === Navigasyon Metodları ===

    async openPOS() {
        if (!this.state.posConfig) {
            this.notification.add(_t("Kasa sistemi bulunamadı. Lütfen yöneticiye başvurun."), {
                type: "warning",
            });
            return;
        }
        try {
            await this.action.doAction({
                type: "ir.actions.act_url",
                url: `/odoo/point-of-sale/shop/${this.state.posConfig.id}`,
                target: "self",
            });
        } catch (e) {
            this.notification.add(_t("Kasa açılırken hata oluştu."), { type: "danger" });
        }
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
            context: { default_partner_id: false },
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
            name: _t("Satış Faturası"),
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

    openNewPartner() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Yeni Cari"),
            res_model: "res.partner",
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
