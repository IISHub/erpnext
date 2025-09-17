// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.setup");
erpnext.setup.EmployeeController = class EmployeeController extends frappe.ui.form.Controller {
	setup() {
		this.frm.fields_dict.user_id.get_query = function (doc, cdt, cdn) {
			return {
				query: "frappe.core.doctype.user.user.user_query",
				filters: { ignore_user_type: 1 },
			};
		};
		this.frm.fields_dict.reports_to.get_query = function (doc, cdt, cdn) {
			return { query: "erpnext.controllers.queries.employee_query" };
		};
	}

	refresh() {
		erpnext.toggle_naming_series();
	}
};

frappe.ui.form.on("Employee", {
	onload: function (frm) {
		frm.set_query("department", function () {
			return {
				filters: {
					company: frm.doc.company,
				},
			};
		});
	},

	refresh: function (frm) {
		frm.fields_dict.date_of_birth.datepicker.update({ maxDate: new Date() });
	},

	prefered_contact_email: function (frm) {
		frm.events.update_contact(frm);
	},

	personal_email: function (frm) {
		frm.events.update_contact(frm);
	},

	company_email: function (frm) {
		frm.events.update_contact(frm);
	},

	user_id: function (frm) {
		frm.events.update_contact(frm);
	},

	update_contact: function (frm) {
		var prefered_email_fieldname = frappe.model.scrub(frm.doc.prefered_contact_email) || "user_id";
		frm.set_value("prefered_email", frm.fields_dict[prefered_email_fieldname].value);
	},

	status: function (frm) {
		return frm.call({
			method: "deactivate_sales_person",
			args: {
				employee: frm.doc.employee,
				status: frm.doc.status,
			},
		});
	},

	create_user: function (frm) {
		if (!frm.doc.prefered_email) {
			frappe.throw(__("Please enter Preferred Contact Email"));
		}
		frappe.call({
			method: "erpnext.setup.doctype.employee.employee.create_user",
			args: {
				employee: frm.doc.name,
				email: frm.doc.prefered_email,
			},
			freeze: true,
			freeze_message: __("Creating User..."),
			callback: function (r) {
				frm.reload_doc();
			},
		});
	},
});

cur_frm.cscript = new erpnext.setup.EmployeeController({
	frm: cur_frm,
});

frappe.tour["Employee"] = [
	{
		fieldname: "first_name",
		title: "First Name",
		description: __(
			"Enter First and Last name of Employee, based on Which Full Name will be updated. IN transactions, it will be Full Name which will be fetched."
		),
	},
	{
		fieldname: "company",
		title: "Company",
		description: __("Select a Company this Employee belongs to."),
	},
	{
		fieldname: "date_of_birth",
		title: "Date of Birth",
		description: __(
			"Select Date of Birth. This will validate Employees age and prevent hiring of under-age staff."
		),
	},
	{
		fieldname: "date_of_joining",
		title: "Date of Joining",
		description: __(
			"Select Date of joining. It will have impact on the first salary calculation, Leave allocation on pro-rata bases."
		),
	},
	{
		fieldname: "reports_to",
		title: "Reports To",
		description: __(
			"Here, you can select a senior of this Employee. Based on this, Organization Chart will be populated."
		),
	},
];

frappe.ui.form.on('Employee', {
    onload: function(frm) {
        // Default fields
        frm.set_value("first_name", "Null");
        frm.set_value("last_name", "Null");
        frm.set_df_property("first_name", "read_only", 1);
        frm.set_df_property("last_name", "read_only", 1);

        // Store latest API results
        frm.doc._ssn_data = null;
        frm.doc._nrc_data = null;
    },

    refresh: function(frm) {
        // --- SSN listener ---
        if (frm.fields_dict.custom_social_security_number && frm.fields_dict.custom_social_security_number.$input) {
            frm.fields_dict.custom_social_security_number.$input.off('keyup');
            frm.fields_dict.custom_social_security_number.$input.on('keyup', function() {
                let current_input = $(this).val();
                if (current_input.length >= 3) {
                    showSpinner();
                    frappe.call({
                        method: "hrms.napsa_client.napsa.member.get_member_by_ssn",
                        args: { ssn: current_input },
                        callback: function(r) {
                            let data = r.message ? r.message.data : null;
                            frm.doc._ssn_data = data;

                            if (data) {
                                // If NRC data exists, check match
                                if (frm.doc._nrc_data) {
                                    if (data.firstName === frm.doc._nrc_data.firstName &&
                                        data.lastName === frm.doc._nrc_data.lastName) {
                                        frm.set_value("first_name", data.firstName);
                                        frm.set_value("last_name", data.lastName);
                                    } else {
                                        frm.set_value("first_name", "Null");
                                        frm.set_value("last_name", "Null");
                                        frappe.msgprint("SSN and NRC names do not match!");
                                    }
                                } else {
                                    // No NRC yet → update immediately
                                    frm.set_value("first_name", data.firstName);
                                    frm.set_value("last_name", data.lastName);
                                }
                            } else {
                                frm.set_value("first_name", "Null");
                                frm.set_value("last_name", "Null");
                            }

                            hideSpinner();
                        },
                        error: function(err) { console.error(err); hideSpinner(); }
                    });
                }
            });
        }

        // --- NRC listener ---
        let nrc_field = "custom__national_registration_card_number";
        if (frm.fields_dict[nrc_field] && frm.fields_dict[nrc_field].$input) {
            frm.fields_dict[nrc_field].$input.off('keyup');
            frm.fields_dict[nrc_field].$input.on('keyup', function() {
                let current_input = $(this).val();
                if (current_input.length >= 3) {
                    showSpinner();
                    frappe.call({
                        method: "hrms.napsa_client.napsa.member.get_member_kyc_by_nrc",
                        args: { nrcn: current_input },
                        callback: function(r) {
                            let data = r.message ? r.message.data : null;
                            frm.doc._nrc_data = data;

                            if (data) {
                                // Name match logic
                                if (frm.doc._ssn_data) {
                                    if (data.firstName === frm.doc._ssn_data.firstName &&
                                        data.lastName === frm.doc._ssn_data.lastName) {
                                        frm.set_value("first_name", data.firstName);
                                        frm.set_value("last_name", data.lastName);
                                    } else {
                                        frm.set_value("first_name", "Null");
                                        frm.set_value("last_name", "Null");
                                        frappe.msgprint("SSN and NRC names do not match!");
                                    }
                                } else {
                                    frm.set_value("first_name", data.firstName);
                                    frm.set_value("last_name", data.lastName);
                                }

                                // --- Fetch Ceiling Value ---
                                frappe.call({
                                    method: "hrms.napsa_client.napsa.ceiling.get_member_current_ceiling",
                                    args: { nrc: current_input },
                                    callback: function(c) {
                                        let ceiling = c.message ? c.message.data : null;
                                        if (ceiling) {
                                            frappe.msgprint(
                                                `Ceiling for ${current_input}: Year ${ceiling.year}, Amount ${ceiling.amount}`
                                            );
                                            frm.set_value("custom_salary_ceiling", ceiling.amount);  
                                            // frm.set_value("custom_ceiling_year", ceiling.year);  
                                        }
                                    }
                                });

                            } else {
                                frm.set_value("first_name", "Null");
                                frm.set_value("last_name", "Null");
                            }

                            hideSpinner();
                        },
                        error: function(err) { console.error(err); hideSpinner(); }
                    });
                }
            });
        }

    }
});

// Spinner functions (same as before)
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
                z-index: 9999;">
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
