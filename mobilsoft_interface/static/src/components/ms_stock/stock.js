/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// ─────────────────────────────────────────────
// STOK SEVİYELERİ LİSTESİ
// ─────────────────────────────────────────────
class StockLevels extends Component {
    static template = "mobilsoft_interface.StockLevels";
    static props = {
        onAdjust: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this._mounted = false;

        this.state = useState({
            records: [],
            loading: true,
            search: "",
            filter: "all",   // all | low | out | normal
            offset: 0,
            limit: 25,
            total: 0,
            warehouses: [],
            selectedWarehouse: false,
            summary: {
                totalProducts: 0,
                outOfStock: 0,
                lowStock: 0,
            },
        });

        onMounted(() => {
            this._mounted = true;
            this._loadWarehouses();
            this._loadRecords();
        });
        onWillUnmount(() => { this._mounted = false; });
    }

    async _loadWarehouses() {
        try {
            const wh = await this.orm.searchRead(
                "stock.warehouse",
                [],
                ["id", "name"],
                { order: "name asc" }
            );
            if (this._mounted) this.state.warehouses = wh;
        } catch (_) {}
    }

    _buildDomain() {
        const domain = [
            ["type", "in", ["product", "consu"]],
            ["active", "=", true],
        ];

        if (this.state.filter === "out") {
            domain.push(["qty_available", "<=", 0]);
        } else if (this.state.filter === "low") {
            domain.push(["qty_available", ">", 0]);
            domain.push(["qty_available", "<=", 5]);
        } else if (this.state.filter === "normal") {
            domain.push(["qty_available", ">", 5]);
        }

        if (this.state.search.trim()) {
            const q = this.state.search.trim();
            domain.push("|", ["name", "ilike", q], ["barcode", "ilike", q]);
        }
        return domain;
    }

    async _loadRecords() {
        if (!this._mounted) return;
        this.state.loading = true;
        try {
            const domain = this._buildDomain();
            const count = await this.orm.searchCount("product.product", domain);

            const records = await this.orm.searchRead(
                "product.product",
                domain,
                ["id", "name", "barcode", "qty_available", "virtual_available",
                 "categ_id", "type", "uom_id", "standard_price", "list_price"],
                {
                    limit: this.state.limit,
                    offset: this.state.offset,
                    order: "qty_available asc, name asc",
                }
            );

            // Summary için ayrı sayımlar
            const [outCount, lowCount] = await Promise.all([
                this.orm.searchCount("product.product", [
                    ["type", "in", ["product", "consu"]], ["active", "=", true],
                    ["qty_available", "<=", 0]
                ]),
                this.orm.searchCount("product.product", [
                    ["type", "in", ["product", "consu"]], ["active", "=", true],
                    ["qty_available", ">", 0], ["qty_available", "<=", 5]
                ]),
            ]);

            if (this._mounted) {
                this.state.total = count;
                this.state.records = records;
                this.state.summary.totalProducts = count;
                this.state.summary.outOfStock = outCount;
                this.state.summary.lowStock = lowCount;
            }
        } catch (e) {
            console.error("Stok yükleme hatası:", e);
            if (this._mounted) {
                this.notification.add(_t("Stok bilgileri yüklenirken hata oluştu."), { type: "danger" });
            }
        } finally {
            if (this._mounted) this.state.loading = false;
        }
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
        this.state.offset = 0;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this._loadRecords(), 400);
    }

    setFilter(filter) {
        this.state.filter = filter;
        this.state.offset = 0;
        this._loadRecords();
    }

    prevPage() {
        if (this.state.offset <= 0) return;
        this.state.offset = Math.max(0, this.state.offset - this.state.limit);
        this._loadRecords();
    }

    nextPage() {
        if (this.state.offset + this.state.limit >= this.state.total) return;
        this.state.offset += this.state.limit;
        this._loadRecords();
    }

    get currentPage() { return Math.floor(this.state.offset / this.state.limit) + 1; }
    get totalPages() { return Math.ceil(this.state.total / this.state.limit) || 1; }
    get pageStart() { return this.state.offset + 1; }
    get pageEnd() { return Math.min(this.state.offset + this.state.limit, this.state.total); }

    formatQty(val) {
        const n = Number(val || 0);
        return n % 1 === 0 ? n.toString() : n.toFixed(2);
    }

    formatPrice(val) {
        return Number(val || 0).toLocaleString("tr-TR", {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        }) + " ₺";
    }

    getStockStatus(rec) {
        const qty = Number(rec.qty_available || 0);
        if (qty <= 0) return { cls: "ms-badge--danger", label: "Stok Yok", bar: "danger" };
        if (qty <= 5) return { cls: "ms-badge--warning", label: "Kritik Stok", bar: "warning" };
        return { cls: "ms-badge--success", label: "Stokta", bar: "success" };
    }
}

// ─────────────────────────────────────────────
// STOK HAREKETLERİ
// ─────────────────────────────────────────────
class StockMoves extends Component {
    static template = "mobilsoft_interface.StockMoves";
    static props = {
        onBack: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this._mounted = false;

        this.state = useState({
            records: [],
            loading: true,
            search: "",
            filter: "done",  // done | draft | all
            offset: 0,
            limit: 25,
            total: 0,
        });

        onMounted(() => {
            this._mounted = true;
            this._loadRecords();
        });
        onWillUnmount(() => { this._mounted = false; });
    }

    _buildDomain() {
        const domain = [];
        if (this.state.filter === "done") {
            domain.push(["state", "=", "done"]);
        } else if (this.state.filter === "draft") {
            domain.push(["state", "in", ["draft", "waiting", "confirmed", "assigned"]]);
        }
        if (this.state.search.trim()) {
            const q = this.state.search.trim();
            domain.push("|", ["name", "ilike", q], ["origin", "ilike", q]);
        }
        return domain;
    }

    async _loadRecords() {
        if (!this._mounted) return;
        this.state.loading = true;
        try {
            const domain = this._buildDomain();
            const count = await this.orm.searchCount("stock.picking", domain);
            const records = await this.orm.searchRead(
                "stock.picking",
                domain,
                ["id", "name", "picking_type_id", "partner_id", "origin",
                 "scheduled_date", "date_done", "state", "move_type"],
                {
                    limit: this.state.limit,
                    offset: this.state.offset,
                    order: "scheduled_date desc",
                }
            );
            if (this._mounted) {
                this.state.total = count;
                this.state.records = records;
            }
        } catch (e) {
            console.error("Stok hareketleri yükleme hatası:", e);
        } finally {
            if (this._mounted) this.state.loading = false;
        }
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
        this.state.offset = 0;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this._loadRecords(), 400);
    }

    setFilter(f) {
        this.state.filter = f;
        this.state.offset = 0;
        this._loadRecords();
    }

    prevPage() {
        if (this.state.offset <= 0) return;
        this.state.offset = Math.max(0, this.state.offset - this.state.limit);
        this._loadRecords();
    }

    nextPage() {
        if (this.state.offset + this.state.limit >= this.state.total) return;
        this.state.offset += this.state.limit;
        this._loadRecords();
    }

    get currentPage() { return Math.floor(this.state.offset / this.state.limit) + 1; }
    get totalPages() { return Math.ceil(this.state.total / this.state.limit) || 1; }
    get pageStart() { return this.state.offset + 1; }
    get pageEnd() { return Math.min(this.state.offset + this.state.limit, this.state.total); }

    formatDate(val) {
        if (!val) return "—";
        try { return new Date(val).toLocaleDateString("tr-TR"); } catch (_) { return val; }
    }

    getStateBadge(state) {
        const map = {
            draft:     { cls: "ms-badge--muted",   label: "Taslak" },
            waiting:   { cls: "ms-badge--muted",   label: "Bekliyor" },
            confirmed: { cls: "ms-badge--info",    label: "Onaylandı" },
            assigned:  { cls: "ms-badge--warning", label: "Hazır" },
            done:      { cls: "ms-badge--success", label: "Tamamlandı" },
            cancel:    { cls: "ms-badge--danger",  label: "İptal" },
        };
        return map[state] || { cls: "ms-badge--muted", label: state };
    }
}

// ─────────────────────────────────────────────
// STOK MODÜLÜ (ana wrapper)
// ─────────────────────────────────────────────
export class StockModule extends Component {
    static template = "mobilsoft_interface.StockModule";
    static props = {};
    static components = { StockLevels, StockMoves };

    setup() {
        this.state = useState({
            tab: "levels",   // 'levels' | 'moves'
        });
    }
}
