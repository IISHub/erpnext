// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.listview_settings["Purchase Invoice"] = {
    // Defines the fields that will be fetched from the server and available in the list view.
    // This is crucial for the get_indicator function to work, as it needs access to these fields.
    add_fields: [
        "supplier",
        "supplier_name",
        "base_grand_total",
        "outstanding_amount",
        "due_date",
        "company",
        "currency",
        "is_return", // This field must be present for the custom indicator to work.
        "release_date",
        "on_hold",
        "represents_company",
        "is_internal_supplier",
    ],

    // This function is responsible for determining the color and text of the indicator for each row.
    get_indicator(doc) {
        // 🔁 Custom indicator for return invoices
        // This is the custom logic you added. It correctly checks if 'is_return' is truthy.
        if (doc.is_return) {
            return [__("Return"), "blue", "is_return,=,1"];
        }

        // Existing indicator for debit note
        if (doc.status == "Debit Note Issued") {
            return [__(doc.status), "gray", "status,=," + doc.status];
        }

        // Existing logic for on hold
        if (flt(doc.outstanding_amount) > 0 && doc.docstatus == 1 && cint(doc.on_hold)) {
            if (!doc.release_date) {
                return [__("On Hold"), "darkgrey"];
            } else if (frappe.datetime.get_diff(doc.release_date, frappe.datetime.nowdate()) > 0) {
                return [__("Temporarily on Hold"), "darkgrey"];
            }
        }

        // Existing status-based indicators.
        const status_colors = {
            Unpaid: "orange",
            Paid: "green",
            Return: "gray",
            Overdue: "red",
            "Partly Paid": "yellow",
            "Internal Transfer": "darkgrey",
        };

        // If a matching status exists in the map, return the corresponding indicator.
        if (status_colors[doc.status]) {
            return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
        }
    },

    // This function runs when the list view is loaded. It's used to add custom buttons or actions.
    onload: function (listview) {
        // Add "Purchase Receipt" bulk action
        if (frappe.model.can_create("Purchase Receipt")) {
            listview.page.add_action_item(__("Purchase Receipt"), () => {
                erpnext.bulk_transaction_processing.create(listview, "Purchase Invoice", "Purchase Receipt");
            });
        }

        // Add "Payment" bulk action
        if (frappe.model.can_create("Payment Entry")) {
            listview.page.add_action_item(__("Payment"), () => {
                erpnext.bulk_transaction_processing.create(listview, "Purchase Invoice", "Payment Entry");
            });
        }
    },
};