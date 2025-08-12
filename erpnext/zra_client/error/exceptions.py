# exceptions.py
from frappe import frappe
from error.error_codes import ERRORS

class SaleException(Exception):
    def __init__(self, code):
        self.code = code
        self.message = ERRORS.get(code, "An unknown error occurred.")
        super().__init__(self.message)

    def throw(self):
        frappe.throw(self.message)
