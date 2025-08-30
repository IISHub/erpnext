import time
import random
import frappe
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.mock.mock import mock_zra_response
from erpnext.zra_client.error.exceptions import RequestException, RETRYABLE_ERRORS


class ResponseRetry(ZRAClient):
    def __init__(self, payload=None, task_type=None, max_attempts=3):
        self.payload = payload
        self.task_type = task_type
        self.max_attempts = max_attempts

    def create_customer(self):
        create_customer_payload = self.payload
        customer_tpin = create_customer_payload["custTpin"]
        attempt = 0
        while attempt < self.max_attempts:
            attempt += 1
            data = mock_zra_response() 
            print(f"Attempt {attempt}: {data}")

            if data.get("resultCd") == "000":
                
                frappe.msgprint("Customer has been saved successfully.")
                self.update_customer_status_by_tpin(customer_tpin, 1)
                return data
            elif data.get("resultCd") in RETRYABLE_ERRORS:
                print(f"Retryable error: {data.get('resultMsg')}, retrying in 2s...")
                time.sleep(2) 
            else:
                RequestException(data.get("resultCd") or "CREATE_CUSTOMER_ERROR").throw()
        
        self.update_customer_status_by_tpin(customer_tpin, 0)
        RequestException("MAX_RETRIES_EXCEEDED").throw()


    def create_item(self):
        create_item_payload = self.payload
        item_code = create_item_payload["itemTyCd"]
        attempt = 0
        while attempt < self.max_attempts:
            attempt += 1
            data = mock_zra_response() 
            print(f"Attempt {attempt}: {data}")

            if data.get("resultCd") == "000":
                
                frappe.msgprint("Customer has been saved successfully.")
                self.update_item_status_by_item_code(item_code, 1)
                return data
            elif data.get("resultCd") in RETRYABLE_ERRORS:
                print(f"Retryable error: {data.get('resultMsg')}, retrying in 2s...")
                time.sleep(2) 
            else:
                RequestException(data.get("resultCd") or "CREATE_CUSTOMER_ERROR").throw()
        
        self.update_item_status_by_item_code(item_code, 0)
        RequestException("MAX_RETRIES_EXCEEDED").throw()


    def create_purchase_retry(self):
        create_purchase_payload = self.payload
        purchase_inv_no = create_purchase_payload["invNo"]
        attempt = 0
        while attempt < self.max_attempts:
            attempt += 1
            data = mock_zra_response() 
            print(f"Attempt {attempt}: {data}")

            if data.get("resultCd") == "000":
                
                frappe.msgprint("Customer has been saved successfully.")
                self.update_purchase_status_by_inv_no(purchase_inv_no, 1)
                return data
            elif data.get("resultCd") in RETRYABLE_ERRORS:
                print(f"Retryable error: {data.get('resultMsg')}, retrying in 2s...")
                time.sleep(2) 
            else:
                RequestException(data.get("resultCd") or "CREATE_CUSTOMER_ERROR").throw()
        
        self.update_purchase_status_by_inv_no(purchase_inv_no, 0)
        RequestException("MAX_RETRIES_EXCEEDED").throw()

        
    def determine_task_type(self):
        if self.task_type == 1:
            return self.create_customer()
        
        if self.task_type == 2:
            return self.create_item()

        if self.task_type == 3:
            return self.create_purchase_retry()
        
        else:
            RequestException("UNKNOWN_TASK_TYPE").throw()
