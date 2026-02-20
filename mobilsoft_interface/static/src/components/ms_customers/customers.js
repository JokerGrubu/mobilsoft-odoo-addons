/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// ─────────────────────────────────────────────
// CARİLER LİSTESİ
// ─────────────────────────────────────────────
class CustomersList extends Component {
    static template = "mobilsoft_interface.CustomersList";
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
            filter: "all",   // all | customers | suppliers
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
        const domain = [["active", "=", true]];
        if (this.state.filter === "customers") {
            domain.push(["customer_rank", ">", 0]);
        } else if (this.state.filter === "suppliers") {
            domain.push(["supplier_rank", ">", 0]);
        } else {
            // Hepsi: müşteri VEYA tedarikçi
            domain.push("|");
            domain.push(["customer_rank", ">", 0]);
            domain.push(["supplier_rank", ">", 0]);
        }
        if (this.state.search.trim()) {
            const q = this.state.search.trim();
            domain.push("|", "|");
            domain.push(["name", "ilike", q]);
            domain.push(["vat", "ilike", q]);
            domain.push(["phone", "ilike", q]);
        }
        return domain;
    }

    async _loadRecords() {
        if (!this._mounted) return;
        this.state.loading = true;
        try {
            const domain = this._buildDomain();
            const count = await this.orm.searchCount("res.partner", domain);
            const records = await this.orm.searchRead(
                "res.partner",
                domain,
                ["id", "name", "vat", "phone", "email", "city",
                 "is_company", "customer_rank", "supplier_rank", "commercial_partner_id"],
                {
                    limit: this.state.limit,
                    offset: this.state.offset,
                    order: "name asc",
                }
            );
            if (this._mounted) {
                this.state.total = count;
                this.state.records = records;
            }
        } catch (e) {
            console.error("Cariler yükleme hatası:", e);
            this.notification.add(_t("Cariler yüklenirken hata oluştu."), { type: "danger" });
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

    getTypeLabel(rec) {
        const isCustomer = rec.customer_rank > 0;
        const isSupplier = rec.supplier_rank > 0;
        if (isCustomer && isSupplier) return { label: "Müşteri + Tedarikçi", cls: "ms-badge--purple" };
        if (isCustomer) return { label: "Müşteri", cls: "ms-badge--success" };
        if (isSupplier) return { label: "Tedarikçi", cls: "ms-badge--info" };
        return { label: "Diğer", cls: "ms-badge--muted" };
    }
}

// ─────────────────────────────────────────────
// CARİ FORMU
// ─────────────────────────────────────────────
class CustomerForm extends Component {
    static template = "mobilsoft_interface.CustomerForm";
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
            record: {
                name: "",
                is_company: true,
                vat: "",
                phone: "",
                mobile: "",
                email: "",
                street: "",
                city: "",
                zip: "",
                is_customer: true,
                is_supplier: false,
                comment: "",
            },
            errors: {},
        });

        onMounted(() => {
            this._mounted = true;
            if (this.props.id) this._loadRecord();
        });
        onWillUnmount(() => { this._mounted = false; });
    }

    async _loadRecord() {
        try {
            const records = await this.orm.read(
                "res.partner",
                [this.props.id],
                ["name", "is_company", "vat", "phone", "mobile", "email",
                 "street", "city", "zip", "customer_rank", "supplier_rank", "comment"]
            );
            if (this._mounted && records.length) {
                const r = records[0];
                this.state.record = {
                    name: r.name || "",
                    is_company: r.is_company !== false,
                    vat: r.vat || "",
                    phone: r.phone || "",
                    mobile: r.mobile || "",
                    email: r.email || "",
                    street: r.street || "",
                    city: r.city || "",
                    zip: r.zip || "",
                    is_customer: r.customer_rank > 0,
                    is_supplier: r.supplier_rank > 0,
                    comment: r.comment || "",
                };
            }
        } catch (e) {
            this.notification.add(_t("Cari yüklenirken hata oluştu."), { type: "danger" });
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
            errors.name = _t("Cari adı zorunludur.");
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
                is_company: this.state.record.is_company,
                vat: this.state.record.vat || false,
                phone: this.state.record.phone || false,
                mobile: this.state.record.mobile || false,
                email: this.state.record.email || false,
                street: this.state.record.street || false,
                city: this.state.record.city || false,
                zip: this.state.record.zip || false,
                comment: this.state.record.comment || false,
                // customer/supplier rank
                customer_rank: this.state.record.is_customer ? 1 : 0,
                supplier_rank: this.state.record.is_supplier ? 1 : 0,
            };

            if (this.props.id) {
                await this.orm.write("res.partner", [this.props.id], vals);
                this.notification.add(_t("Cari güncellendi."), { type: "success" });
            } else {
                await this.orm.create("res.partner", [vals]);
                this.notification.add(_t("Cari oluşturuldu."), { type: "success" });
            }
            this.props.onSaved();
        } catch (e) {
            console.error("Cari kaydetme hatası:", e);
            this.notification.add(_t("Kaydetme sırasında hata oluştu."), { type: "danger" });
        } finally {
            if (this._mounted) this.state.saving = false;
        }
    }
}

// ─────────────────────────────────────────────
// CARİLER MODÜLÜ (ana wrapper)
// ─────────────────────────────────────────────
export class CustomersModule extends Component {
    static template = "mobilsoft_interface.CustomersModule";
    static props = {};
    static components = { CustomersList, CustomerForm };

    setup() {
        this.state = useState({
            view: "list",
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
