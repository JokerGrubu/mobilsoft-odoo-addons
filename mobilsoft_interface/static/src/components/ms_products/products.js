/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// ─────────────────────────────────────────────
// ÜRÜN LİSTESİ
// ─────────────────────────────────────────────
class ProductsList extends Component {
    static template = "mobilsoft_interface.ProductsList";
    static props = {
        onEdit: Function,
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
            filter: "active",   // active | all | low_stock | archived
            offset: 0,
            limit: 20,
            total: 0,
            categories: [],
        });

        onMounted(() => {
            this._mounted = true;
            this._loadCategories();
            this._loadRecords();
        });
        onWillUnmount(() => { this._mounted = false; });
    }

    async _loadCategories() {
        try {
            const cats = await this.orm.searchRead(
                "product.category",
                [],
                ["id", "name"],
                { order: "name asc" }
            );
            if (this._mounted) this.state.categories = cats;
        } catch (e) { /* sessiz */ }
    }

    _buildDomain() {
        const domain = [];
        if (this.state.filter === "active") {
            domain.push(["active", "=", true]);
        } else if (this.state.filter === "archived") {
            domain.push(["active", "=", false]);
        } else if (this.state.filter === "low_stock") {
            domain.push(["active", "=", true]);
            domain.push(["qty_available", "<=", 5]);
            domain.push(["type", "!=", "service"]);
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
            const count = await this.orm.searchCount("product.template", domain);
            const records = await this.orm.searchRead(
                "product.template",
                domain,
                ["id", "name", "barcode", "list_price", "standard_price",
                 "categ_id", "qty_available", "type", "active", "image_128"],
                {
                    limit: this.state.limit,
                    offset: this.state.offset,
                    order: "name asc",
                    context: { active_test: false },
                }
            );
            if (this._mounted) {
                this.state.total = count;
                this.state.records = records;
            }
        } catch (e) {
            console.error("Ürünler yükleme hatası:", e);
            this.notification.add(_t("Ürünler yüklenirken hata oluştu."), { type: "danger" });
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

    formatPrice(val) {
        return Number(val || 0).toLocaleString("tr-TR", {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        });
    }

    getTypeLabel(type) {
        const labels = { consu: "Sarf", product: "Stoklu", service: "Hizmet" };
        return labels[type] || type;
    }

    getStockBadge(record) {
        if (record.type === "service") return null;
        const qty = record.qty_available || 0;
        if (qty <= 0) return { class: "ms-badge--danger", label: "Stok Yok" };
        if (qty <= 5) return { class: "ms-badge--warning", label: `${qty} adet` };
        return { class: "ms-badge--success", label: `${qty} adet` };
    }
}

// ─────────────────────────────────────────────
// ÜRÜN FORMU
// ─────────────────────────────────────────────
class ProductForm extends Component {
    static template = "mobilsoft_interface.ProductForm";
    static props = {
        id: { type: Number, optional: true },
        onBack: Function,
        onSaved: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this._mounted = false;

        this.state = useState({
            loading: !!this.props.id,
            saving: false,
            categories: [],
            record: {
                name: "",
                barcode: "",
                list_price: 0,
                standard_price: 0,
                categ_id: false,
                type: "consu",
                active: true,
                description_sale: "",
            },
            errors: {},
        });

        onMounted(() => {
            this._mounted = true;
            this._loadCategories();
            if (this.props.id) this._loadRecord();
        });
        onWillUnmount(() => { this._mounted = false; });
    }

    async _loadCategories() {
        try {
            const cats = await this.orm.searchRead(
                "product.category",
                [],
                ["id", "name"],
                { order: "name asc" }
            );
            if (this._mounted) this.state.categories = cats;
        } catch (e) { /* sessiz */ }
    }

    async _loadRecord() {
        try {
            const records = await this.orm.read(
                "product.template",
                [this.props.id],
                ["name", "barcode", "list_price", "standard_price",
                 "categ_id", "type", "active", "description_sale"],
                { context: { active_test: false } }
            );
            if (this._mounted && records.length) {
                const r = records[0];
                this.state.record = {
                    name: r.name || "",
                    barcode: r.barcode || "",
                    list_price: r.list_price || 0,
                    standard_price: r.standard_price || 0,
                    categ_id: r.categ_id ? r.categ_id[0] : false,
                    type: r.type || "consu",
                    active: r.active !== false,
                    description_sale: r.description_sale || "",
                };
            }
        } catch (e) {
            this.notification.add(_t("Ürün yüklenirken hata oluştu."), { type: "danger" });
        } finally {
            if (this._mounted) this.state.loading = false;
        }
    }

    updateField(field, value) {
        this.state.record[field] = value;
        if (this.state.errors[field]) delete this.state.errors[field];
    }

    _validate() {
        const errors = {};
        if (!this.state.record.name.trim()) {
            errors.name = _t("Ürün adı zorunludur.");
        }
        if (this.state.record.list_price < 0) {
            errors.list_price = _t("Fiyat negatif olamaz.");
        }
        this.state.errors = errors;
        return Object.keys(errors).length === 0;
    }

    async save() {
        if (!this._validate()) return;
        this.state.saving = true;
        try {
            const vals = {
                name: this.state.record.name.trim(),
                barcode: this.state.record.barcode || false,
                list_price: parseFloat(this.state.record.list_price) || 0,
                standard_price: parseFloat(this.state.record.standard_price) || 0,
                categ_id: this.state.record.categ_id || false,
                type: this.state.record.type,
                active: this.state.record.active,
                description_sale: this.state.record.description_sale || false,
            };

            if (this.props.id) {
                await this.orm.write("product.template", [this.props.id], vals);
                this.notification.add(_t("Ürün güncellendi."), { type: "success" });
            } else {
                const newId = await this.orm.create("product.template", [vals]);
                this.notification.add(_t("Ürün oluşturuldu."), { type: "success" });
            }
            this.props.onSaved();
        } catch (e) {
            console.error("Ürün kaydetme hatası:", e);
            this.notification.add(_t("Kaydetme sırasında hata oluştu: ") + (e.message || ""), { type: "danger" });
        } finally {
            if (this._mounted) this.state.saving = false;
        }
    }

    toggleActive() {
        this.state.record.active = !this.state.record.active;
    }
}

// ─────────────────────────────────────────────
// ÜRÜNLER MODÜLÜ (ana wrapper)
// ─────────────────────────────────────────────
export class ProductsModule extends Component {
    static template = "mobilsoft_interface.ProductsModule";
    static props = {};
    static components = { ProductsList, ProductForm };

    setup() {
        this.state = useState({
            view: "list",   // 'list' | 'form'
            editId: null,
        });
    }

    showList() {
        this.state.view = "list";
        this.state.editId = null;
    }

    showNew() {
        this.state.view = "form";
        this.state.editId = null;
    }

    showEdit(id) {
        this.state.view = "form";
        this.state.editId = id;
    }

    onSaved() {
        this.showList();
    }
}
