import frappe

class UpdateRecieptUrl:
    def __init__(self):
        self.new_url = "http://41.60.191.7:8081/files/uploads/f5533349-1826-487e-aea7-909656d61cac.pdf"

    def update_invoice(self, invoice_name):
        doc = frappe.get_doc("Sales Invoice", invoice_name)
        doc.custom_slip = self.new_url
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return f"Updated invoice {invoice_name} with new receipt URL."
