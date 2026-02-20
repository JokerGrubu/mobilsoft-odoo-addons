/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// ─────────────────────────────────────────────
// FATURA LİSTESİ
// ─────────────────────────────────────────────
class InvoicesList extends Component {
    static template = "mobilsoft_interface.InvoicesList";
    static props = {
        onOpen: Function,
        onNew: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this._mounted = false;

        this.state = useState({
            records: [],
            loading: true,
            search: "",
            filter: "all",         // all | unpaid | partial | paid | overdue
            moveType: "customer",  // customer | supplier
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
        // Tip: customer = müşteri faturaları, supplier = tedarikçi faturaları
        if (this.state.moveType === "customer") {
            domain.push(["move_type", "in", ["out_invoice", "out_refund"]]);
        } else {
            domain.push(["move_type", "in", ["in_invoice", "in_refund"]]);
        }
        // state filter: sadece posted faturaları göster (draft dahil tümü)
        domain.push(["state", "in", ["draft", "posted", "cancel"]]);

        // Ödeme durumu filtresi
        if (this.state.filter === "unpaid") {
            domain.push(["payment_state", "=", "not_paid"]);
            domain.push(["state", "=", "posted"]);
        } else if (this.state.filter === "partial") {
            domain.push(["payment_state", "=", "partial"]);
            domain.push(["state", "=", "posted"]);
        } else if (this.state.filter === "paid") {
            domain.push(["payment_state", "in", ["paid", "in_payment"]]);
        } else if (this.state.filter === "overdue") {
            const today = new Date().toISOString().split("T")[0];
            domain.push(["invoice_date_due", "<", today]);
            domain.push(["payment_state", "not in", ["paid", "in_payment"]]);
            domain.push(["state", "=", "posted"]);
        }

        if (this.state.search.trim()) {
            const q = this.state.search.trim();
            domain.push("|", "|",
                ["name", "ilike", q],
                ["partner_id.name", "ilike", q],
                ["ref", "ilike", q]
            );
        }
        return domain;
    }

    async _loadRecords() {
        if (!this._mounted) return;
        this.state.loading = true;
        try {
            const domain = this._buildDomain();
            const count = await this.orm.searchCount("account.move", domain);
            const records = await this.orm.searchRead(
                "account.move",
                domain,
                ["id", "name", "invoice_date", "invoice_date_due",
                 "partner_id", "amount_total", "amount_residual",
                 "payment_state", "state", "move_type", "ref"],
                {
                    limit: this.state.limit,
                    offset: this.state.offset,
                    order: "invoice_date desc, name desc",
                }
            );
            if (this._mounted) {
                this.state.total = count;
                this.state.records = records;
            }
        } catch (e) {
            console.error("Faturalar yükleme hatası:", e);
            if (this._mounted) {
                this.notification.add(_t("Faturalar yüklenirken hata oluştu."), { type: "danger" });
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

    setMoveType(moveType) {
        this.state.moveType = moveType;
        this.state.filter = "all";
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
        try {
            return new Date(val).toLocaleDateString("tr-TR");
        } catch (_) { return val; }
    }

    formatCurrency(val) {
        return Number(val || 0).toLocaleString("tr-TR", {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        }) + " ₺";
    }

    getPaymentBadge(rec) {
        if (rec.state === "draft") return { cls: "ms-badge--muted", label: "Taslak" };
        if (rec.state === "cancel") return { cls: "ms-badge--danger", label: "İptal" };
        switch (rec.payment_state) {
            case "paid":       return { cls: "ms-badge--success", label: "Ödendi" };
            case "in_payment": return { cls: "ms-badge--info",    label: "Ödeniyor" };
            case "partial":    return { cls: "ms-badge--warning",  label: "Kısmi Ödeme" };
            case "not_paid":   return { cls: "ms-badge--danger",  label: "Ödenmedi" };
            default:           return { cls: "ms-badge--muted",   label: rec.payment_state || "—" };
        }
    }

    getMoveTypeLabel(moveType) {
        const map = {
            out_invoice: "Satış Faturası",
            out_refund: "Satış İade",
            in_invoice: "Alış Faturası",
            in_refund: "Alış İade",
        };
        return map[moveType] || moveType;
    }

    isOverdue(rec) {
        if (!rec.invoice_date_due || rec.payment_state === "paid" || rec.payment_state === "in_payment") return false;
        return new Date(rec.invoice_date_due) < new Date();
    }
}

// ─────────────────────────────────────────────
// FATURA FORMU
// ─────────────────────────────────────────────
class InvoiceForm extends Component {
    static template = "mobilsoft_interface.InvoiceForm";
    static props = {
        id: { type: Number, optional: true },
        moveType: { type: String, optional: true },
        onBack: Function,
        onSaved: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this._mounted = false;
        this._searchTimer = null;

        const defaultMoveType = this.props.moveType || "out_invoice";

        this.state = useState({
            loading: !!this.props.id,
            saving: false,
            record: {
                move_type: defaultMoveType,
                partner_id: false,
                partner_name: "",
                invoice_date: new Date().toISOString().split("T")[0],
                invoice_date_due: new Date().toISOString().split("T")[0],
                ref: "",
                narration: "",
                lines: [],
            },
            errors: {},
            partnerSearch: "",
            partnerResults: [],
            showPartnerDropdown: false,
            productSearch: "",
            productResults: [],
            activeLineIdx: null,
        });

        onMounted(() => {
            this._mounted = true;
            if (this.props.id) this._loadRecord();
        });
        onWillUnmount(() => {
            this._mounted = false;
            clearTimeout(this._searchTimer);
        });
    }

    async _loadRecord() {
        try {
            const recs = await this.orm.read(
                "account.move",
                [this.props.id],
                ["move_type", "partner_id", "invoice_date", "invoice_date_due",
                 "ref", "narration", "invoice_line_ids", "state", "payment_state",
                 "amount_total", "amount_residual"]
            );
            if (!this._mounted || !recs.length) return;
            const r = recs[0];

            // Satırları yükle
            let lines = [];
            if (r.invoice_line_ids && r.invoice_line_ids.length) {
                const lineRecs = await this.orm.read(
                    "account.move.line",
                    r.invoice_line_ids,
                    ["product_id", "name", "quantity", "price_unit",
                     "tax_ids", "price_subtotal", "price_total", "discount"]
                );
                lines = lineRecs.map(l => ({
                    id: l.id,
                    product_id: l.product_id ? l.product_id[0] : false,
                    product_name: l.product_id ? l.product_id[1] : "",
                    name: l.name || "",
                    quantity: l.quantity || 1,
                    price_unit: l.price_unit || 0,
                    discount: l.discount || 0,
                    tax_ids: l.tax_ids || [],
                    price_subtotal: l.price_subtotal || 0,
                    price_total: l.price_total || 0,
                }));
            }

            if (this._mounted) {
                this.state.record = {
                    move_type: r.move_type,
                    partner_id: r.partner_id ? r.partner_id[0] : false,
                    partner_name: r.partner_id ? r.partner_id[1] : "",
                    invoice_date: r.invoice_date || "",
                    invoice_date_due: r.invoice_date_due || "",
                    ref: r.ref || "",
                    narration: r.narration || "",
                    lines,
                    state: r.state,
                    payment_state: r.payment_state,
                    amount_total: r.amount_total,
                    amount_residual: r.amount_residual,
                };
            }
        } catch (e) {
            if (this._mounted) {
                this.notification.add(_t("Fatura yüklenirken hata oluştu."), { type: "danger" });
            }
        } finally {
            if (this._mounted) this.state.loading = false;
        }
    }

    // --- Partner Arama ---
    onPartnerInput(ev) {
        this.state.partnerSearch = ev.target.value;
        this.state.record.partner_name = ev.target.value;
        this.state.record.partner_id = false;
        clearTimeout(this._searchTimer);
        if (ev.target.value.length < 2) {
            this.state.partnerResults = [];
            this.state.showPartnerDropdown = false;
            return;
        }
        this._searchTimer = setTimeout(() => this._searchPartners(ev.target.value), 300);
    }

    async _searchPartners(q) {
        try {
            const results = await this.orm.searchRead(
                "res.partner",
                ["|", ["name", "ilike", q], ["vat", "ilike", q]],
                ["id", "name", "vat"],
                { limit: 8 }
            );
            if (this._mounted) {
                this.state.partnerResults = results;
                this.state.showPartnerDropdown = results.length > 0;
            }
        } catch (_) {}
    }

    selectPartner(p) {
        this.state.record.partner_id = p.id;
        this.state.record.partner_name = p.name;
        this.state.partnerSearch = p.name;
        this.state.showPartnerDropdown = false;
        this.state.partnerResults = [];
        if (this.state.errors.partner_id) delete this.state.errors.partner_id;
    }

    // --- Satır işlemleri ---
    addLine() {
        this.state.record.lines.push({
            product_id: false,
            product_name: "",
            name: "",
            quantity: 1,
            price_unit: 0,
            discount: 0,
            tax_ids: [],
        });
    }

    removeLine(idx) {
        this.state.record.lines.splice(idx, 1);
    }

    updateLine(idx, field, value) {
        this.state.record.lines[idx][field] = value;
    }

    get invoiceTotal() {
        return this.state.record.lines.reduce((sum, l) => {
            const base = Number(l.quantity || 0) * Number(l.price_unit || 0);
            const disc = base * (Number(l.discount || 0) / 100);
            return sum + base - disc;
        }, 0);
    }

    formatCurrency(val) {
        return Number(val || 0).toLocaleString("tr-TR", {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        }) + " ₺";
    }

    // --- Kaydet ---
    _validate() {
        const errors = {};
        if (!this.state.record.partner_id) {
            errors.partner_id = _t("Cari zorunludur.");
        }
        if (!this.state.record.invoice_date) {
            errors.invoice_date = _t("Fatura tarihi zorunludur.");
        }
        if (this.state.record.lines.length === 0) {
            errors.lines = _t("En az bir fatura satırı gereklidir.");
        }
        this.state.errors = errors;
        return Object.keys(errors).length === 0;
    }

    async save() {
        if (!this._validate()) return;
        this.state.saving = true;
        try {
            const vals = {
                move_type: this.state.record.move_type,
                partner_id: this.state.record.partner_id,
                invoice_date: this.state.record.invoice_date || false,
                invoice_date_due: this.state.record.invoice_date_due || false,
                ref: this.state.record.ref || false,
                narration: this.state.record.narration || false,
                invoice_line_ids: this.state.record.lines.map(l => [0, 0, {
                    product_id: l.product_id || false,
                    name: l.name || l.product_name || "Ürün/Hizmet",
                    quantity: Number(l.quantity) || 1,
                    price_unit: Number(l.price_unit) || 0,
                    discount: Number(l.discount) || 0,
                }]),
            };

            if (this.props.id) {
                await this.orm.write("account.move", [this.props.id], vals);
                this.notification.add(_t("Fatura güncellendi."), { type: "success" });
            } else {
                await this.orm.create("account.move", [vals]);
                this.notification.add(_t("Fatura oluşturuldu."), { type: "success" });
            }
            this.props.onSaved();
        } catch (e) {
            console.error("Fatura kaydetme hatası:", e);
            this.notification.add(
                _t("Kaydetme sırasında hata oluştu: ") + (e.data?.message || e.message || ""),
                { type: "danger" }
            );
        } finally {
            if (this._mounted) this.state.saving = false;
        }
    }
}

// ─────────────────────────────────────────────
// FATURALAR MODÜLÜ (ana wrapper)
// ─────────────────────────────────────────────
export class InvoicesModule extends Component {
    static template = "mobilsoft_interface.InvoicesModule";
    static props = {};
    static components = { InvoicesList, InvoiceForm };

    setup() {
        this.state = useState({
            view: "list",     // 'list' | 'form'
            editId: null,
            moveType: "out_invoice",
        });
    }

    showList() {
        this.state.view = "list";
        this.state.editId = null;
    }

    showNew(moveType = "out_invoice") {
        this.state.view = "form";
        this.state.editId = null;
        this.state.moveType = moveType;
    }

    showEdit(id) {
        this.state.view = "form";
        this.state.editId = id;
    }

    onSaved() {
        this.showList();
    }
}
