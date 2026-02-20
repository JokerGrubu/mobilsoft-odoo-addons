/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class SalesModule extends Component {
    static template = "mobilsoft_interface.SalesModule";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this._mounted = false;

        this.state = useState({
            records: [],
            loading: true,
            search: "",
            filter: "all",   // all | today | week | month | draft | sale | done | cancel
            offset: 0,
            limit: 20,
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
        const now = new Date();

        if (this.state.filter === "today") {
            const today = now.toISOString().split("T")[0];
            domain.push(["date_order", ">=", today + " 00:00:00"]);
        } else if (this.state.filter === "week") {
            const weekAgo = new Date(now - 7 * 86400000).toISOString().split("T")[0];
            domain.push(["date_order", ">=", weekAgo + " 00:00:00"]);
        } else if (this.state.filter === "month") {
            const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];
            domain.push(["date_order", ">=", monthStart + " 00:00:00"]);
        } else if (["draft", "sale", "done", "cancel"].includes(this.state.filter)) {
            domain.push(["state", "=", this.state.filter]);
        }

        if (this.state.search.trim()) {
            const q = this.state.search.trim();
            domain.push("|");
            domain.push(["name", "ilike", q]);
            domain.push(["partner_id.name", "ilike", q]);
        }
        return domain;
    }

    async _loadRecords() {
        if (!this._mounted) return;
        this.state.loading = true;
        try {
            const domain = this._buildDomain();
            const count = await this.orm.searchCount("sale.order", domain);
            const records = await this.orm.searchRead(
                "sale.order",
                domain,
                ["id", "name", "date_order", "partner_id", "amount_total", "state", "invoice_status"],
                {
                    limit: this.state.limit,
                    offset: this.state.offset,
                    order: "date_order desc",
                }
            );
            if (this._mounted) {
                this.state.total = count;
                this.state.records = records;
            }
        } catch (e) {
            this.notification.add(_t("Satışlar yüklenirken hata oluştu."), { type: "danger" });
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

    getStateBadge(state) {
        const map = {
            draft:  { label: "Taslak",    cls: "ms-badge--muted" },
            sent:   { label: "Gönderildi", cls: "ms-badge--info" },
            sale:   { label: "Onaylı",     cls: "ms-badge--success" },
            done:   { label: "Tamamlandı", cls: "ms-badge--purple" },
            cancel: { label: "İptal",      cls: "ms-badge--danger" },
        };
        return map[state] || { label: state, cls: "ms-badge--muted" };
    }

    formatDate(dateStr) {
        if (!dateStr) return "—";
        try {
            return new Date(dateStr).toLocaleDateString("tr-TR");
        } catch (e) { return dateStr; }
    }

    formatCurrency(val) {
        return "₺ " + Number(val || 0).toLocaleString("tr-TR", {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        });
    }

    // Sipariş detayı için Odoo native form
    openOrder(rec) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sale.order",
            res_id: rec.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    newOrder() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Yeni Satış Siparişi"),
            res_model: "sale.order",
            views: [[false, "form"]],
            target: "current",
        });
    }
}
