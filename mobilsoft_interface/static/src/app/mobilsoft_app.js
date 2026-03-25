/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { _t } from "@web/core/l10n/translation";

// Sub-modules
import { MobilSoftHome } from "../components/mobilsoft_home/mobilsoft_home";
import { ProductsModule } from "../components/ms_products/products";
import { CustomersModule } from "../components/ms_customers/customers";
import { SalesModule } from "../components/ms_sales/sales";
import { InvoicesModule } from "../components/ms_invoices/invoices";
import { StockModule } from "../components/ms_stock/stock";
import { MarketplaceModule } from "../components/ms_marketplace/marketplace";

/**
 * MobilSoftApp - Ana SPA Shell
 * Sidebar + Header + Router içerir.
 * Kullanıcılar Odoo'yu hiç görmeden tüm işlemlerini yapar.
 */
export class MobilSoftApp extends Component {
    static template = "mobilsoft_interface.MobilSoftApp";
    static props = {};

    static components = {
        MobilSoftHome,
        ProductsModule,
        CustomersModule,
        SalesModule,
        InvoicesModule,
        StockModule,
        MarketplaceModule,
    };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            currentPage: "home",
            sidebarOpen: false,  // mobilde kapalı başlar
            companyName: session.company_name || "MobilSoft",
            userName: session.name || "",
            // Badge sayıları
            badges: {
                pendingInvoices: 0,
                stockAlerts: 0,
            },
            posConfigId: null,
        });

        this._mounted = false;

        onMounted(() => {
            this._mounted = true;
            this._loadBadges().catch(() => {});
        });

        onWillUnmount(() => {
            this._mounted = false;
        });
    }

    async _loadBadges() {
        try {
            // Bekleyen fatura sayısı
            const invoiceCount = await this.orm.searchCount("account.move", [
                ["move_type", "in", ["out_invoice", "in_invoice"]],
                ["payment_state", "in", ["not_paid", "partial"]],
                ["state", "=", "posted"],
            ]);
            if (this._mounted) this.state.badges.pendingInvoices = invoiceCount;

            // Kritik stok
            const stockCount = await this.orm.searchCount("product.product", [
                ["qty_available", "<=", 0],
                ["type", "=", "consu"],
            ]);
            if (this._mounted) this.state.badges.stockAlerts = stockCount;

            // POS config
            const posConfigs = await this.orm.searchRead(
                "pos.config",
                [["active", "=", true]],
                ["id"],
                { limit: 1 }
            );
            if (this._mounted && posConfigs.length) {
                this.state.posConfigId = posConfigs[0].id;
            }
        } catch (e) {
            // Badge yüklenemezse sessizce geç
        }
    }

    // ============ NAVIGASYON ============

    navigate(page) {
        this.state.currentPage = page;
        // Mobilde sidebar kapat
        if (window.innerWidth <= 768) {
            this.state.sidebarOpen = false;
        }
    }

    toggleSidebar() {
        this.state.sidebarOpen = !this.state.sidebarOpen;
    }

    closeSidebar() {
        this.state.sidebarOpen = false;
    }

    async openPOS() {
        if (!this.state.posConfigId) {
            this.notification.add(
                _t("Kasa sistemi bulunamadı. Lütfen yöneticiye başvurun."),
                { type: "warning" }
            );
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_url",
            url: `/odoo/point-of-sale/shop/${this.state.posConfigId}`,
            target: "self",
        });
    }

    async logout() {
        window.location.href = "/web/session/logout?redirect=/web/login";
    }

    // ============ YARDIMCI ============

    get navItems() {
        return [
            {
                id: "home",
                icon: "🏠",
                label: _t("Ana Sayfa"),
                section: "main",
            },
            {
                id: "products",
                icon: "📦",
                label: _t("Ürünler"),
                section: "main",
            },
            {
                id: "customers",
                icon: "👥",
                label: _t("Cariler"),
                section: "main",
            },
            {
                id: "sales",
                icon: "🛒",
                label: _t("Satışlar"),
                section: "main",
            },
            {
                id: "invoices",
                icon: "🧾",
                label: _t("Faturalar"),
                badge: this.state.badges.pendingInvoices || null,
                section: "main",
            },
            {
                id: "stock",
                icon: "📊",
                label: _t("Stok"),
                badge: this.state.badges.stockAlerts || null,
                section: "main",
            },
            {
                id: "purchases",
                icon: "🚚",
                label: _t("Alışlar"),
                section: "main",
            },
            {
                id: "pos",
                icon: "🖥️",
                label: _t("Kasa (POS)"),
                action: "pos",
                section: "tools",
            },
            {
                id: "reports",
                icon: "📈",
                label: _t("Raporlar"),
                section: "tools",
            },
            {
                id: "integrations",
                icon: "🔌",
                label: _t("Entegrasyonlar"),
                section: "tools",
            },
            {
                id: "marketplace",
                icon: "🏪",
                label: _t("CepteTedarik"),
                section: "tools",
            },
        ];
    }

    onNavClick(item) {
        if (item.action === "pos") {
            this.openPOS();
        } else {
            this.navigate(item.id);
        }
    }
}

registry.category("actions").add("mobilsoft_app", MobilSoftApp);
