import time
import frappe
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.mock.mock import mock_zra_response
from erpnext.zra_client.error.exceptions import RequestException, RETRYABLE_ERRORS


class ResponseRetry(ZRAClient):
    def __init__(self, payload=None, task_type=None, max_attempts=3, site_url=None):
        super().__init__()  # Initialize ZRAClient attributes
        self.payload = payload
        self.task_type = task_type
        self.max_attempts = max_attempts
        if site_url:
            self.site_url = site_url

    def create_customer_retry(self):
        customer_tpin = self.payload.get("custTpin")
        attempt = 0

        while attempt < self.max_attempts:
            attempt += 1
            data = self.create_customer(self.payload)
            print(f"Attempt {attempt}: {data}")

            if data.get("resultCd") == "000":
                frappe.msgprint("Customer has been saved successfully.")
                self.update_customer_status_by_tpin(customer_tpin, 1, 10, self.get_site_url())
                return data
            elif data.get("resultCd") in RETRYABLE_ERRORS:
                print(f"Retryable error: {data.get('resultMsg')}, retrying in 2s...")
                time.sleep(2)
            else:
                RequestException(data.get("resultCd") or "CREATE_CUSTOMER_ERROR").throw()

        self.update_customer_status_by_tpin(customer_tpin, 0, 10, self.get_site_url())
        frappe.msgprint("The request failed after multiple attempts. It will be retried when ZRA is back online.")
        return None

    def create_item(self):
        item_code = self.payload.get("itemCd")
        attempt = 0

        while attempt < self.max_attempts:
            attempt += 1
            data = self.create_item_zra(self.payload)
            print(f"Attempt {attempt}: {data}")

            if data.get("resultCd") == "000":
                frappe.msgprint("Item has been saved successfully.")
                self.update_item_status_by_item_code(item_code, 1,  10, self.get_site_url())
                return data
            elif data.get("resultCd") in RETRYABLE_ERRORS:
                print(f"Retryable error: {data.get('resultMsg')}, retrying in 2s...")
                time.sleep(2)
            else:
                RequestException(data.get("resultCd") or "CREATE_ITEM_ERROR").throw()

        self.update_item_status_by_item_code(item_code, 0,  10, self.get_site_url())
        frappe.msgprint("The request failed after multiple attempts. It will be retried when ZRA is back online.")
        return None

    def create_purchase_retry(self):
        purchase_inv_no = self.payload.get("cisInvcNo")
        attempt = 0

        while attempt < self.max_attempts:
            attempt += 1
            data = self.create_purchase_zra_client(self.payload)
            print(f"Attempt {attempt}: {data}")

            if data.get("resultCd") == "000":
                frappe.msgprint("Purchase has been saved successfully.")
                self.update_purchase_status_by_inv_no(purchase_inv_no, 1, 10, self.get_site_url())
                return data
            elif data.get("resultCd") in RETRYABLE_ERRORS:
                print(f"Retryable error: {data.get('resultMsg')}, retrying in 2s...")
                time.sleep(2)
            else:
                RequestException(data.get("resultCd") or "CREATE_PURCHASE_ERROR").throw()

        self.update_purchase_status_by_inv_no(purchase_inv_no, 0, 10, self.get_site_url())
        frappe.msgprint("The request failed after multiple attempts. It will be retried when ZRA is back online.")

    def determine_task_type(self):
        if self.task_type == 1:
            return self.create_customer_retry()
        elif self.task_type == 2:
            return self.create_item()
        elif self.task_type == 3:
            return self.create_purchase_retry()
        else:
            RequestException("UNKNOWN_TASK_TYPE").throw()

