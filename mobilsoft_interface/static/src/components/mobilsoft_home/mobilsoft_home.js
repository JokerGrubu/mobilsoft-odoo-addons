/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { _t } from "@web/core/l10n/translation";

/**
 * MobilSoft Ana Sayfa - OWL Dashboard
 *
 * Odoo 19 uyumlu:
 * - `useService("rpc")` → `useService("orm")`
 * - `useService("user")` → `import { session } from "@web/session"`
 */
export class MobilSoftHome extends Component {
    static template = "mobilsoft_interface.MobilSoftHome";
    static props = {
        onNavigate: Function,
    };

    setup() {
        // Odoo 19: action, orm, notification servisleri
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");

        // Kullanıcı ve şirket bilgisi için session kullan (her zaman mevcut)
        this.session = session;

        // Bileşen hâlâ monte mi? (async işlemler için guard)
        this._mounted = false;

        this.state = useState({
            companyName: session.company_name || session.name || "MobilSoft",
            stats: {
                todaySales: 0,
                pendingInvoices: 0,
                stockAlerts: 0,
            },
            posConfig: null,
            loading: true,
            currentDate: this._getFormattedDate(),
        });

        onMounted(() => {
            this._mounted = true;
            this._loadDashboardData().catch((e) => {
                console.error("MobilSoft onMounted hatası:", e);
            });
        });

        onWillUnmount(() => {
            this._mounted = false;
        });
    }

    _getFormattedDate() {
        try {
            return new Date().toLocaleDateString("tr-TR", {
                weekday: "long",
                day: "numeric",
                month: "long",
            });
        } catch (e) {
            return new Date().toLocaleDateString();
        }
    }

    async _loadDashboardData() {
        try {
            // Şirket adını ORM ile doğrula (session.company_name bazen yanlış olabilir)
            const companyId = session.company_id;
            if (companyId) {
                const companies = await this.orm.read(
                    "res.company",
                    [companyId],
                    ["name"]
                );
                if (this._mounted && companies.length) {
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
            if (this._mounted) {
                this.state.stats.todaySales = totalSales;
            }

            // Bekleyen faturalar
            const pendingCount = await this.orm.searchCount(
                "account.move",
                [
                    ["move_type", "in", ["out_invoice", "in_invoice"]],
                    ["payment_state", "in", ["not_paid", "partial"]],
                    ["state", "=", "posted"],
                ]
            );
            if (this._mounted) {
                this.state.stats.pendingInvoices = pendingCount;
            }

            // Kritik stok uyarıları
            try {
                const alertCount = await this.orm.searchCount(
                    "product.product",
                    [["qty_available", "<=", 0], ["type", "=", "consu"]]
                );
                if (this._mounted) {
                    this.state.stats.stockAlerts = alertCount;
                }
            } catch (e) {
                // stok erişim hatası - sessizce geç
            }

            // POS konfigürasyonu
            try {
                const posConfigs = await this.orm.searchRead(
                    "pos.config",
                    [["active", "=", true]],
                    ["id", "name", "current_session_id"],
                    { limit: 1 }
                );
                if (this._mounted) {
                    this.state.posConfig = posConfigs.length ? posConfigs[0] : null;
                }
            } catch (e) {
                // POS erişim hatası - sessizce geç
            }

        } catch (e) {
            console.error("MobilSoft dashboard hatası:", e);
        } finally {
            if (this._mounted) {
                this.state.loading = false;
            }
        }
    }

    // === Navigasyon ===

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
        this.props.onNavigate("invoices");
    }

    openSales() {
        this.props.onNavigate("sales");
    }

    openStock() {
        this.props.onNavigate("stock");
    }

    openPartners() {
        this.props.onNavigate("customers");
    }

    openPurchases() {
        this.props.onNavigate("purchases");
    }

    openNewSaleInvoice() {
        this.props.onNavigate("invoices");
    }

    openNewProduct() {
        this.props.onNavigate("products");
    }

    formatCurrency(val) {
        return Number(val || 0).toLocaleString("tr-TR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }
}

registry.category("actions").add("mobilsoft_home", MobilSoftHome);
