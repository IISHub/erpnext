import requests
import frappe

def internal_api_error_check(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    
    except requests.exceptions.Timeout:
        frappe.throw("Request timed out. Please try again later.")
    
    except requests.exceptions.HTTPError as http_err:
        status = http_err.response.status_code if http_err.response else "unknown"
        frappe.throw(f"HTTP error {status} occurred while processing your request.")
    
    except requests.exceptions.ConnectionError:
        frappe.throw("Failed to connect to the internal service. Please check your network.")
    
    except ValueError:
        frappe.throw("Received malformed response from external service.")
    
    except Exception as e:
        frappe.throw(f"Unexpected error: {str(e)}")
