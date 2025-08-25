import time
import random
import frappe
from erpnext.zra_client.mock.mock import mock_zra_response
from erpnext.zra_client.error.exceptions import RequestException, RETRYABLE_ERRORS


class ResponseRetry:
    def __init__(self, payload=None, task_type=None, max_attempts=3):
        self.payload = payload
        self.task_type = task_type
        self.max_attempts = max_attempts

    def create_customer(self):
        attempt = 0
        while attempt < self.max_attempts:
            attempt += 1
            data = mock_zra_response() 
            print(f"Attempt {attempt}: {data}")

            if data.get("resultCd") == "000":
                frappe.msgprint("Customer has been saved successfully.")
                return data
            elif data.get("resultCd") in RETRYABLE_ERRORS:
                print(f"Retryable error: {data.get('resultMsg')}, retrying in 2s...")
                time.sleep(2) 
            else:
                RequestException(data.get("resultCd") or "CREATE_CUSTOMER_ERROR").throw()
        
        frappe.msgprint("Customer saved with status 'Pending'. Will retry sending when network is back.")

    def determine_task_type(self):
        if self.task_type == 1:
            return self.create_customer()
        else:
            RequestException("UNKNOWN_TASK_TYPE").throw()
