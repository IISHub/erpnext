// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Customer", {
	setup: function (frm) {
		frm.custom_make_buttons = {
			Opportunity: "Opportunity",
			Quotation: "Quotation",
			"Sales Order": "Sales Order",
			"Pricing Rule": "Pricing Rule",
			"Payment Entry": "Payment Entry",
		};
		frm.make_methods = {
			Quotation: () =>
				frappe.model.open_mapped_doc({
					method: "erpnext.selling.doctype.customer.customer.make_quotation",
					frm: frm,
				}),
			"Sales Order": () =>
				frappe.model.with_doctype("Sales Order", function () {
					var so = frappe.model.get_new_doc("Sales Order");
					so.customer = frm.doc.name; // Set the current customer as the SO customer
					frappe.set_route("Form", "Sales Order", so.name);
				}),
			Opportunity: () =>
				frappe.model.open_mapped_doc({
					method: "erpnext.selling.doctype.customer.customer.make_opportunity",
					frm: frm,
				}),
			"Payment Entry": () =>
				frappe.model.open_mapped_doc({
					method: "erpnext.selling.doctype.customer.customer.make_payment_entry",
					frm: frm,
				}),
			"Pricing Rule": () => erpnext.utils.make_pricing_rule(frm.doc.doctype, frm.doc.name),
		};

		frm.add_fetch("lead_name", "company_name", "customer_name");
		frm.add_fetch("default_sales_partner", "commission_rate", "default_commission_rate");
		frm.set_query("default_price_list", { selling: 1 });
		frm.set_query("account", "accounts", function (doc, cdt, cdn) {
			let d = locals[cdt][cdn];
			let filters = {
				account_type: "Receivable",
				root_type: "Asset",
				company: d.company,
				is_group: 0,
			};

			if (doc.party_account_currency) {
				$.extend(filters, { account_currency: doc.party_account_currency });
			}
			return {
				filters: filters,
			};
		});

		frm.set_query("advance_account", "accounts", function (doc, cdt, cdn) {
			let d = locals[cdt][cdn];
			return {
				filters: {
					account_type: "Receivable",
					root_type: "Liability",
					company: d.company,
					is_group: 0,
				},
			};
		});

		if (frm.doc.__islocal == 1) {
			frm.set_value("represents_company", "");
		}

		frm.set_query("customer_primary_contact", function (doc) {
			return {
				query: "erpnext.selling.doctype.customer.customer.get_customer_primary_contact",
				filters: {
					customer: doc.name,
				},
			};
		});
		frm.set_query("customer_primary_address", function (doc) {
			return {
				filters: {
					link_doctype: "Customer",
					link_name: doc.name,
				},
			};
		});

		frm.set_query("default_bank_account", function () {
			return {
				filters: {
					is_company_account: 1,
				},
			};
		});

		frm.set_query("user", "portal_users", function () {
			return {
				filters: {
					ignore_user_type: true,
				},
			};
		});
	},
	customer_primary_address: function (frm) {
		if (frm.doc.customer_primary_address) {
			frappe.call({
				method: "frappe.contacts.doctype.address.address.get_address_display",
				args: {
					address_dict: frm.doc.customer_primary_address,
				},
				callback: function (r) {
					frm.set_value("primary_address", r.message);
				},
			});
		}
		if (!frm.doc.customer_primary_address) {
			frm.set_value("primary_address", "");
		}
	},

	is_internal_customer: function (frm) {
		if (frm.doc.is_internal_customer == 1) {
			frm.toggle_reqd("represents_company", true);
		} else {
			frm.toggle_reqd("represents_company", false);
		}
	},

	customer_primary_contact: function (frm) {
		if (!frm.doc.customer_primary_contact) {
			frm.set_value("mobile_no", "");
			frm.set_value("email_id", "");
		}
	},

	loyalty_program: function (frm) {
		if (frm.doc.loyalty_program) {
			frm.set_value("loyalty_program_tier", null);
		}
	},

	refresh: function (frm) {
		if (frappe.defaults.get_default("cust_master_name") != "Naming Series") {
			frm.toggle_display("naming_series", false);
		} else {
			erpnext.toggle_naming_series();
		}

		if (!frm.doc.__islocal) {
			frappe.contacts.render_address_and_contact(frm);

			// custom buttons

			frm.add_custom_button(
				__("Accounts Receivable"),
				function () {
					frappe.set_route("query-report", "Accounts Receivable", {
						party_type: "Customer",
						party: frm.doc.name,
					});
				},
				__("View")
			);

			frm.add_custom_button(
				__("Accounting Ledger"),
				function () {
					frappe.set_route("query-report", "General Ledger", {
						party_type: "Customer",
						party: frm.doc.name,
						party_name: frm.doc.customer_name,
					});
				},
				__("View")
			);

			for (const doctype in frm.make_methods) {
				frm.add_custom_button(__(doctype), frm.make_methods[doctype], __("Create"));
			}

			frm.add_custom_button(
				__("Get Customer Group Details"),
				function () {
					frm.trigger("get_customer_group_details");
				},
				__("Actions")
			);

			if (cint(frappe.defaults.get_default("enable_common_party_accounting"))) {
				frm.add_custom_button(
					__("Link with Supplier"),
					function () {
						frm.trigger("show_party_link_dialog");
					},
					__("Actions")
				);
			}

			// indicator
			erpnext.utils.set_party_dashboard_indicators(frm);
		} else {
			frappe.contacts.clear_address_and_contact(frm);
		}

		var grid = cur_frm.get_field("sales_team").grid;
		grid.set_column_disp("allocated_amount", false);
		grid.set_column_disp("incentives", false);
	},
	validate: function (frm) {
		if (frm.doc.lead_name) frappe.model.clear_doc("Lead", frm.doc.lead_name);
	},
	get_customer_group_details: function (frm) {
		frappe.call({
			method: "get_customer_group_details",
			doc: frm.doc,
			callback: function () {
				frm.refresh();
			},
		});
	},
	show_party_link_dialog: function (frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Select a Supplier"),
			fields: [
				{
					fieldtype: "Link",
					label: __("Supplier"),
					options: "Supplier",
					fieldname: "supplier",
					reqd: 1,
				},
			],
			primary_action: function ({ supplier }) {
				frappe.call({
					method: "erpnext.accounts.doctype.party_link.party_link.create_party_link",
					args: {
						primary_role: "Customer",
						primary_party: frm.doc.name,
						secondary_party: supplier,
					},
					freeze: true,
					callback: function () {
						dialog.hide();
						frappe.msgprint({
							message: __("Successfully linked to Supplier"),
							alert: true,
						});
					},
					error: function () {
						dialog.hide();
						frappe.msgprint({
							message: __("Linking to Supplier Failed. Please try again."),
							title: __("Linking Failed"),
							indicator: "red",
						});
					},
				});
			},
			primary_action_label: __("Create Link"),
		});
		dialog.show();
	},
});

frappe.ui.form.on("Customer", {
    before_save(frm) {
        if (!validate_required(frm)) {
            return false; 
        }
        showSpinner();
    },
    before_submit(frm) {
        if (!validate_required(frm)) {
            return false;  
        }
        showSpinner();
    }
});

function validate_required(frm) {
    let missing = [];

    frm.meta.fields.forEach(df => {
        if (df.reqd && !frm.doc[df.fieldname]) {
            missing.push(df.label);
        }
    });

    if (missing.length > 0) {
        return false;
    }
    return true;
}

$(document).ajaxComplete(function(event, xhr, settings) {
    if (settings.url.includes("/api/method/frappe.desk.form.save.savedocs") ||
        settings.url.includes("/api/method/frappe.client.submit")) {
        hideSpinner();
    }
});

function showSpinner() {
    if (!$("#custom-spinner-modal").length) {
        $("body").append(`
            <div id="custom-spinner-modal" style="
                display: flex;
                align-items: center;
                justify-content: center;
                background: rgba(0,0,0,0.3);
                position: fixed;
                top: 0; left: 0;
                width: 100%; height: 100%;
                z-index: 9999;
            ">
                <div class="spinner-border text-light" role="status" style="width: 3rem; height: 3rem;">
                    <span class="sr-only">Loading...</span>
                </div>
            </div>
        `);
    }
}

function hideSpinner() {
    $("#custom-spinner-modal").remove();
}

// Form default value
frappe.ui.form.on("Customer", {
    refresh(frm) {
        if (!frm.doc.custom_submission_status || frm.doc.custom_submission_status === 0 || frm.doc.custom_submission_status === "0") {
            console.log("custom_submission_status is empty or 0 → setting to Pending");
            frm.set_df_property("custom_submission_status", "options", ["Pending"]);
            frm.set_value("custom_submission_status", "Pending");
        } else {
            console.log("custom_submission_status has value:", frm.doc.custom_submission_status);
        }
    }
});


frappe.listview_settings['Customer'] = {
    formatters: {
        custom_submission_status: function(value, row, column, data) {
            console.log("ListView formatter triggered for:", value); // test log
            if (value === 0 || value === "0" || !value) {
                return `<span style="color: orange;">Pending</span>`;
            }
            return value;
        }
    }
};
