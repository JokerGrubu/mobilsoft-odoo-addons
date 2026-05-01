/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * MarketplaceModule - CepteTedarik Pazaryeri Yonetimi
 * Urun yayinlama, siparis takibi, istatistikler
 */
export class MarketplaceModule extends Component {
    static template = "mobilsoft_interface.MarketplaceModule";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this._mounted = false;

        this.state = useState({
            loading: true,
            activeTab: "overview",  // overview, products, orders
            stats: {
                publishedCount: 0,
                totalProducts: 0,
                orderCount: 0,
                totalRevenue: 0,
            },
            products: [],
            orders: [],
            productSearch: "",
        });

        onMounted(() => {
            this._mounted = true;
            this._loadData().catch(() => {});
        });

        onWillUnmount(() => {
            this._mounted = false;
        });
    }

    async _loadData() {
        try {
            // Yayinlanan urun sayisi
            const publishedCount = await this.orm.searchCount("product.template", [
                ["mobilsoft_marketplace_publish", "=", true],
            ]);

            const totalProducts = await this.orm.searchCount("product.template", [
                ["type", "!=", "service"],
            ]);

            // Siparisler (website uzerinden gelenler)
            let orderCount = 0;
            let totalRevenue = 0;
            try {
                const orders = await this.orm.searchRead("sale.order", [
                    ["website_id", "!=", false],
                ], ["amount_total"]);
                orderCount = orders.length;
                totalRevenue = orders.reduce((s, o) => s + (o.amount_total || 0), 0);
            } catch (e) {}

            if (this._mounted) {
                this.state.stats.publishedCount = publishedCount;
                this.state.stats.totalProducts = totalProducts;
                this.state.stats.orderCount = orderCount;
                this.state.stats.totalRevenue = totalRevenue;
            }

            // Urunleri yukle
            await this._loadProducts();

            // Siparisleri yukle
            await this._loadOrders();

        } catch (e) {
            console.error("CepteTedarik veri hatasi:", e);
        } finally {
            if (this._mounted) this.state.loading = false;
        }
    }

    async _loadProducts() {
        try {
            const products = await this.orm.searchRead("product.template", [
                ["type", "!=", "service"],
            ], ["name", "list_price", "default_code", "mobilsoft_marketplace_publish", "qty_available"], {
                limit: 50,
                order: "name asc",
            });
            if (this._mounted) this.state.products = products;
        } catch (e) {}
    }

    async _loadOrders() {
        try {
            const orders = await this.orm.searchRead("sale.order", [
                ["website_id", "!=", false],
            ], ["name", "partner_id", "date_order", "amount_total", "state"], {
                limit: 50,
                order: "date_order desc",
            });
            if (this._mounted) this.state.orders = orders;
        } catch (e) {}
    }

    setTab(tab) {
        this.state.activeTab = tab;
    }

    async togglePublish(product) {
        try {
            const newVal = !product.mobilsoft_marketplace_publish;
            await this.orm.write("product.template", [product.id], {
                mobilsoft_marketplace_publish: newVal,
            });
            product.mobilsoft_marketplace_publish = newVal;

            if (newVal) {
                this.state.stats.publishedCount++;
            } else {
                this.state.stats.publishedCount = Math.max(0, this.state.stats.publishedCount - 1);
            }

            this.notification.add(
                newVal ? _t("Urun CepteTedarik'te yayinlandi") : _t("Urun CepteTedarik'ten kaldirildi"),
                { type: "success" }
            );
        } catch (e) {
            this.notification.add(_t("Islem basarisiz"), { type: "danger" });
        }
    }

    formatCurrency(val) {
        return Number(val || 0).toLocaleString("tr-TR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    formatDate(dateStr) {
        if (!dateStr) return "-";
        try {
            return new Date(dateStr).toLocaleDateString("tr-TR");
        } catch (e) {
            return dateStr;
        }
    }

    getStateLabel(state) {
        const labels = {
            draft: "Taslak",
            sent: "Gonderildi",
            sale: "Onaylandi",
            done: "Tamamlandi",
            cancel: "Iptal",
        };
        return labels[state] || state;
    }

    get filteredProducts() {
        const q = (this.state.productSearch || "").toLowerCase();
        if (!q) return this.state.products;
        return this.state.products.filter(p =>
            (p.name || "").toLowerCase().includes(q) ||
            (p.default_code || "").toLowerCase().includes(q)
        );
    }
}
