from erpnext.zra_client.error.exceptions import  RequestException, ERRORS
from erpnext.zra_client.error.custom_exceptions import known_error_check
import threading
import time
from urllib.parse import quote
from frappe import throw, _
from datetime import datetime
import requests
import frappe
import json




ZRA_LOCAL_BASE_URL = "http://localhost:8080/sandboxvsdc1.0.8.0"
ZRA_GET_PRINCIPAL = "/trnsSales/selectPrincipals"
ZRA_CREATE_ITEM = "/items/saveItem"
ZRA_SAVE_STOCK_URL = "/stock/saveStockItems"
ZRA_UPDATE_ITEM = "/items/updateItem"
ZRA_SAVE_STOCK_MASTER = "/stockMaster/saveStockMaster"
ZRA_SAVE_PURCHASE = "/trnsPurchase/savePurchase"
ZRA_CREATE_CUSTOMER = "/branches/saveBrancheCustomers"
ZRA_SALE = "/trnsSales/saveSales"
UPDATE_IMPORT = "/imports/updateImportItems"
SAVE_ITEM_COMPOSITION = "/items/saveItemComposition"
INTERNAL_URL = "http://0.0.0.0:7000/"

BRANCH_CODE = "000"
TPIN = "2484778002"
ORIGIN_SCD_ID = "SDC0010002709"

class ZRAClient:
    def __init__(self):
        self.base_url = ZRA_LOCAL_BASE_URL
        self.internal_base_url = INTERNAL_URL 
        self.create_item_url  = f"{self.base_url}{ZRA_CREATE_ITEM}" 
        self.update_url = f"{self.base_url}{ZRA_UPDATE_ITEM}"
        self.save_stock_url = f"{self.base_url}{ZRA_SAVE_STOCK_URL}"
        self.save_stock_master_url = f"{self.base_url}{ZRA_SAVE_STOCK_MASTER}"
        self.save_purchase_url = f"{self.base_url}{ZRA_SAVE_PURCHASE}"
        self.sale_url = f"{self.base_url}{ZRA_SALE}"
        self.create_customer_url = f"{self.base_url}{ZRA_CREATE_CUSTOMER}"
        self.update_import_url = f"{self.base_url}{UPDATE_IMPORT}"
        self.save_item_composition_url = f"{self.base_url}{SAVE_ITEM_COMPOSITION}"
        self.get_principal_url = f"{self.base_url}{ZRA_GET_PRINCIPAL}"
        self.tpin = TPIN
        self.branch_code = BRANCH_CODE
        self.org_sdc_id = ORIGIN_SCD_ID

    def get_tpin(self):
        return self.tpin

    def get_branch_code(self):
        return self.branch_code
    



    def update_customer_status_by_tpin(self, tpin, status, delay=10):
        def worker():
            # Start a new Frappe request context
            frappe.local = frappe._dict()
            frappe.local.site = frappe.local.site or frappe.local.request_site
            frappe.connect()  # bind database connection

            try:
                if status == 0:
                    actual_status = "Pending"
                elif status == 1:
                    actual_status = "Approved"
                else:
                    actual_status = "Failed"

                print(f"Waiting {delay} seconds before updating TPIN '{tpin}'...")
                time.sleep(delay)

                customer_list = frappe.get_all("Customer", filters={"custom_tpin": tpin}, limit=1)
                if not customer_list:
                    print(f"No customer found with TPIN '{tpin}'.")
                    return

                customer_doc = frappe.get_doc("Customer", customer_list[0].name)
                customer_doc.custom_submission_status = actual_status
                customer_doc.save(ignore_permissions=True)
                frappe.db.commit()

                print(f"Customer with TPIN '{tpin}' status updated to '{actual_status}'.")

            except Exception as e:
                print(f"Error updating customer TPIN '{tpin}': {e}")
            finally:
                frappe.destroy()

        threading.Thread(target=worker, daemon=True).start()


    

    def validate_export(self, vatCd, export_destination_country, is_export):
        if vatCd == "C1":
            if not is_export:
                frappe.throw(
                    "VAT Code 'C1' signifies an export transaction, but the import flag has not been set. "
                    "Please make sure the 'Export' checkbox is checked."
                )

            else:
                pass

            if not export_destination_country:
                frappe.throw(
                    "Export transaction detected (VAT Code 'C1'), but no destination country provided. "
                    "Please select a destination country before continuing."
                )
            else:
                print("[OK] Destination country provided for VAT Code 'C1'.")
    
    def get_country_code_by_name(self, country_name):
        if not country_name or country_name.strip() == "":
            frappe.throw("Country name cannot be empty.")

        def api_call():
            url = f"{self.internal_base_url}/country/{quote(country_name)}/"
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            country_code = data.get("code")
            
            if not country_code:
                frappe.throw(f"Country code not found for '{country_name}' from external API.")
            
            return country_code
        return known_error_check(api_call)
    
    def get_packaging_unit(self, packaging_name):
        if not packaging_name or packaging_name.strip() == "":
            frappe.throw("Packaging name cannot be empty.")

        def api_call():
            url = f"{self.internal_base_url}/packaging-unit-code/{quote(packaging_name)}/"
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            packaging_unit_code = data.get("code")
            
            if not packaging_unit_code:
                frappe.throw(
                    f"Packaging unit code not found for '{packaging_name}' from external API response: {data}"
                )
            
            return packaging_unit_code

        return known_error_check(api_call)
    
    def get_classification_code(self, class_name):
        if not class_name or class_name.strip() == "":
            frappe.throw("Class name cannot be empty.")

        def api_call():
            encoded_class_code = quote(class_name)
            url = f"{self.internal_base_url}/api/get-item-class-by-name/{encoded_class_code}/"
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            itemClsCd = data.get("itemClsCd")

            if not itemClsCd:
                frappe.throw(f"itemClsCd not found for '{class_name}' from external API.")

            return itemClsCd

        return known_error_check(api_call)
    

    def get_units_of_measure(self, unit_name):
        if not unit_name or unit_name.strip() == "":
            frappe.throw("Unit name cannot be empty.")

        def api_call():
            encoded_unit_name = quote(unit_name)
            url = f"{self.internal_base_url}/unitofmeasure/{encoded_unit_name}/"
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            unit_code = data.get("code")

            if not unit_code:
                frappe.throw(f"Unit code not found for '{unit_name}' from external API.")

            return unit_code

        return known_error_check(api_call)

    def update_item_in_background(self, update_url, payload):
        def task():
            try:
                response = requests.post(update_url, json=payload, timeout=70)
                print("Response status:", response.status_code)
                response.raise_for_status()
                print(response.json())
            except requests.exceptions.RequestException as e:
                frappe.log_error(title="ZRA Update Error", message=str(e))
            except ValueError:
                frappe.log_error(title="ZRA Invalid JSON", message="Invalid JSON response from ZRA API during item update.")

        threading.Thread(target=task).start()
    
    def update_rcptNo_delayed(self, docname, rcpt_no, qrcode_url,delay=10):
        def worker():
            try:
                print(f"Received rcptNo: {rcpt_no}. Waiting {delay} seconds before updating...")
                time.sleep(delay)

                url = "http://0.0.0.0:7000/api/update_rcpt/" 
                payload = { 
                    "docname": docname,
                    "rcpt_no": rcpt_no,
                    "qrcode_url": qrcode_url
                }
                headers = {'Content-Type': 'application/json'}
                response = requests.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    print(f"rcptNo '{rcpt_no}' updated for {docname} via API")
                else:
                    print(f"Failed to update rcptNo via API: {response.text}")

            except Exception as e:
                print(f" Error calling API to update rcptNo: {e}")

        threading.Thread(target=worker, daemon=True).start()
    
    def run_stock_update_in_background(self, update_stock_payload, update_stock_master_items, created_by):
        def background_task():
            try:
                response = self.update_stock_zra_client(update_stock_payload)
                if response.get("resultCd") == "000":
                    print("Stock updated.")
                    response = self.save_stock_master_zra_client(update_stock_master_items)
                    if response.get("resultCd") == "000":
                        print("Stock master updated")
                    else:
                        print("Failed to update stock master:", response)
                else:
                    print(f"Failed to update stock: {response.get('resultMsg')}")
            except Exception as e:
                print(f"Exception in background stock update task: {e}")

        thread = threading.Thread(target=background_task)
        thread.daemon = True  
        thread.start()
    
    def get_current_item_stock_qty(self, item_code, warehouse):
        result = frappe.db.sql("""
            SELECT SUM(actual_qty)
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s
            AND warehouse = %s
            AND is_cancelled = 0
        """, (item_code, warehouse))

        return result[0][0] or 0

    def create_item_zra(self, payload):
        def call_create_item():    
                response = requests.post(url=self.create_item_url, json=payload, timeout=300)
                response.raise_for_status() 
                return response 
        return known_error_check(call_create_item)
        
    
    def create_customer(self, payload):
        def call_create_customer():
            response = requests.post(self.create_customer_url, json=payload, timeout=300)
            response.raise_for_status() 
            return response
        return known_error_check(call_create_customer)
    

    def create_purchase_zra_client(self, payload):
        def call_create_purchase():
            response = requests.post(self.save_purchase_url, json=payload, timeout=300)
            response.raise_for_status()
            return response
        return known_error_check(call_create_purchase)
    
    def create_sale_zra_client(self, payload):
        def create_sale():
            response = requests.post(self.sale_url, json=payload, timeout=300)
            response.raise_for_status()
            return response
        return known_error_check(create_sale)
    
    def update_item_zra_client(self, payload):
        def call_update_item():
            response = requests.post(self.update_url, json=payload, timeout=300)
            response.raise_for_status()
            return response
        return known_error_check(call_update_item)
    
    def zra_client_update_import(self, payload):
        def call_update_import_item():
            response = requests.post(self.update_import_url, json=payload, timeout=300)
            response.raise_for_status() 
            return response
        
        return known_error_check(call_update_import_item)

    def update_stock_zra_client(self, payload):
        response = requests.post(self.save_stock_url, json=payload, timeout=70)
        response.raise_for_status() 
        return response.json()  

    def save_stock_master_zra_client(self, payload):
        response = requests.post(self.save_stock_master_url, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()

   

    def get_principals_zra_client(self, payload):
        try:
            response = requests.post(self.get_principal_url, json=payload, timeout=300)
            content = response.text
            print("Raw response content:", content)

            response.raise_for_status()

            result = response.json()
            print("Parsed JSON result:", result)
            return result

        except requests.HTTPError as http_err:
            print("HTTP Error:", http_err)
            print("Response content:", response.text)
            raise Exception(f"Server Error\nException: Failed to save RVAT Sale\nResponse: {response.text}")

        except requests.RequestException as e:
            print("Request Exception:", e)
            raise Exception(f"Server Error\nException: Failed to save RVAT \nDetails: {str(e)}")
        









