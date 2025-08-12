import requests
import frappe

ERRORS = {
    "TIMEOUT": "The request took too long to process. Please try again later.",
    "CONNECTION": "Network problem detected. Please check your internet connection and try again.",
    "INVALID_PRINCIPAL_ID": "The provided principal ID was not found. Please check and try again.",
    "UNKNOWN_RESPONSE": "Received an unexpected response from the system. Please try again later.",
    "SALE_ERROR": "There was a problem with your sale submission. Please try again.",
    "CREATE_CUSTOMER_ERROR": "There was a problem with your customer creation request. Please try again.",
    "PURCHASE_ERROR": "There was a problem saving your purchase. Please check your data and try again.",
    "HTTP_ERROR": "Unexpected system error occurred. Please try again later.",
    "REQUEST_FAILED": "There was an issue sending your request. Please try again.",
    "UNEXPECTED_ERROR": "An unexpected error occurred. Please try again or contact support."
}

class RequestException(Exception):
    def __init__(self, code):
        self.code = code
        self.message = ERRORS.get(code, "An unknown error occurred.")
        super().__init__(self.message)

    def throw(self):
        frappe.throw(self.message)