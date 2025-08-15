from erpnext.zra_client.error.exceptions import  RequestException, ERRORS
from erpnext.zra_client.error.custom_exceptions import internal_api_error_check
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
        return internal_api_error_check(api_call)
    
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

        return internal_api_error_check(api_call)
    
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

        return internal_api_error_check(api_call)
    

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

        return internal_api_error_check(api_call)

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
    
    

    def create_item_zra(self, payload):
        if not payload:
            frappe.throw("Payload cannot be empty.")

        try:
            response = requests.post(url=self.create_item_url, json=payload, timeout=300)
            response.raise_for_status()

            try:
                data = response.json()
            except ValueError:
                raise RequestException("UNKNOWN_RESPONSE")

            if data.get("resultCd") == "000":
                frappe.msgprint("Item has been saved successfully.")
                return data
            else:
                full_msg = data.get("resultMsg", ERRORS["UNEXPECTED_ERROR"])
                if "[<principalId>] : provided is not found" in full_msg:
                    raise RequestException("INVALID_PRINCIPAL_ID")
                else:
                    raise RequestException("REQUEST_FAILED")

        except requests.exceptions.Timeout:
            raise RequestException("TIMEOUT").throw()
        except requests.exceptions.ConnectionError:
            raise RequestException("CONNECTION").throw()
        except requests.exceptions.HTTPError:
            raise RequestException("HTTP_ERROR").throw()
        except RequestException as e:
            e.throw()
        except Exception:
            raise RequestException("UNEXPECTED_ERROR").throw()

            
    
    def create_customer(self, payload):
        try:
            response = requests.post(self.create_customer_url, json=payload, timeout=300)
            response.raise_for_status()

            try:
                data = response.json()
                print(data)
            except ValueError:
                raise RequestException("UNKNOWN_RESPONSE")

            if data.get("resultCd") == "000":
                frappe.msgprint("Customer has been added successfully.")
                return data
            else:
                full_msg = data.get("resultMsg", "Unexpected error")
                if "[<principalId>] : provided is not found" in full_msg:
                    raise RequestException("INVALID_PRINCIPAL_ID")
                else:
                    raise RequestException("REQUEST_FAILED")

        except requests.exceptions.Timeout:
            RequestException("TIMEOUT").throw()
        except requests.exceptions.ConnectionError:
            raise RequestException("CONNECTION").throw()
        except requests.exceptions.HTTPError:
            raise RequestException("HTTP_ERROR").throw()
        except RequestException as e:
            e.throw()
        except Exception:
            raise RequestException("UNEXPECTED_ERROR").throw()

    
    def save_stock(self, payload=None):
        if payload is None:
            frappe.throw("Payload is required to save stock")

        for item in payload.get("itemList", []):
            packaging_unit = item.get("pkgUnitCd")
            qty_unit = item.get("qtyUnitCd")

            try:
                r = requests.get(f"http://0.0.0.0:7000/packaging-unit-code/{packaging_unit}/", timeout=5)
                r.raise_for_status()
                packaging_unit_code = r.json().get("code")
                if not packaging_unit_code:
                    raise ValueError("No code returned for packaging unit")
            except Exception as e:
                raise Exception(f"Packaging unit error ({packaging_unit}): {e}")

            try:
                r = requests.get(f"http://0.0.0.0:7000/unitofmeasure/{qty_unit}/", timeout=5)
                r.raise_for_status()
                qty_unit_code = r.json().get("code")
                if not qty_unit_code:
                    raise ValueError("No code returned for quantity unit")
            except Exception as e:
                raise Exception(f"Quantity unit error ({qty_unit}): {e}")

            item["pkgUnitCd"] = packaging_unit_code
            item["qtyUnitCd"] = qty_unit_code

        try:
            print("Saving stock payload: ", payload)
            response = requests.post(self.save_stock_url, json=payload, timeout=70)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to save stock in ZRA: {e}")

    def update_stock_zra_client(self, payload=None):
        if payload is None:
            frappe.throw("Payload is required to update stock after purchase")

        try:
            print("Updating stock after purchase payload: ", payload)
            response = requests.post(self.save_stock_url, json=payload, timeout=70)
            response.raise_for_status()
            print("Stock update response:", response.text)
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to update stock after purchase in ZRA: {e}")
        

    def save_stock_master_zra_client(self, payload):
        print("Now calling stock master")
        try:
            response = requests.post(self.save_stock_master_url, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.RequestException as e:
            error_msg = f"Request failed for stock master: {str(e)}"
            frappe.log_error(title="Stock Master Error", message=error_msg)
            return {"status": "error", "message": error_msg}





        
    def save_purchase_manually(self, payload):
        print(payload)
        try:
            response = requests.post(self.save_purchase_url, json=payload, timeout=300)

            try:
                data = response.json()
                print(data)
            except ValueError:
                RequestException("UNKNOWN_RESPONSE").throw()

            if response.status_code == 200:
                if data.get("resultCd") == "000":
                    frappe.msgprint("Purchase saved successfully")
                    return data
                else:
                    full_msg = data.get("resultMsg", ERRORS.get("PURCHASE_ERROR", "Purchase error"))
                    if "[<principalId>] : provided is not found" in full_msg:
                        RequestException("INVALID_PRINCIPAL_ID").throw()
                    RequestException("PURCHASE_ERROR").throw()

            # if result_cd == "999":
            #         frappe.throw("There is an unknown error. Please ask administrator")

            elif response.status_code == 400:
                error_message = data.get("error", ERRORS.get("PURCHASE_ERROR", "Purchase error"))
                frappe.throw(f"Could not save the purchase: {error_message}")

            elif response.status_code == 403:
                error_message = data.get("error", "Forbidden (403) access.")
                frappe.throw(f"Forbidden: {error_message}")

            elif response.status_code == 404:
                error_message = data.get("error", "Not Found (404).")
                frappe.throw(f"Not Found: {error_message}")

            else:
                RequestException("HTTP_ERROR").throw()

        except requests.exceptions.Timeout:
            RequestException("TIMEOUT").throw()

        except requests.exceptions.ConnectionError:
            RequestException("CONNECTION").throw()

        except requests.exceptions.HTTPError:
            RequestException("HTTP_ERROR").throw()

        except requests.exceptions.RequestException:
            RequestException("REQUEST_FAILED").throw()

        except Exception:
            RequestException("UNEXPECTED_ERROR").throw()




        
    def normal_sale(self, payload):
        try:
            response = requests.post(self.sale_url, json=payload, timeout=300)

            try:
                data = response.json()
                print(data)
            except ValueError:
                RequestException("UNKNOWN_RESPONSE").throw()

            if response.status_code == 200:
                result_cd = data.get("resultCd")
                result_msg = data.get("resultMsg", ERRORS.get("SALE_ERROR", "Sale error"))

                if result_cd == "000":
                    frappe.msgprint("Sale added successfully.")
                    return data
                
                if result_cd == "999":
                    frappe.throw("There is an unknown error. Please ask administrator")

                elif result_cd == "924":
                    frappe.throw(f"CIS Invoice number already exists.")
                
                else:
                    RequestException("SALE_ERROR").throw()

            elif response.status_code == 400:
                error_message = data.get("error", ERRORS.get("SALE_ERROR", "Sale error"))
                frappe.throw(f"Could not save the sale: {error_message}")

            else:
                RequestException("HTTP_ERROR").throw()
        except requests.exceptions.Timeout:
            RequestException("TIMEOUT").throw()
        except requests.exceptions.ConnectionError:
            RequestException("CONNECTION").throw()
        except requests.exceptions.HTTPError:
            RequestException("HTTP_ERROR").throw()
        except requests.exceptions.RequestException:
            RequestException("REQUEST_FAILED").throw()
        except Exception:
            RequestException("UNEXPECTED_ERROR").throw()



    
 
    def zra_client_update_import(self, payload):
        try:
            response = requests.post(self.update_import_url, json=payload, timeout=300)
            response.raise_for_status() 
            result = response.json()
            print(result)

            if result.get("resultCd") == "000":
                return response
            elif result.get("resultCd") == "001":
                frappe.throw("There is no search result")
                
            else:
                frappe.throw(_("ZRA Error: {0}").format(result.get('resultMsg', 'Unknown error')))
            return result

        except requests.exceptions.Timeout:
            frappe.throw(_("Request to ZRA timed out. Please try again later."))

        except requests.exceptions.HTTPError as http_err:
            frappe.throw(_("HTTP error occurred: {0}").format(str(http_err)))

        except requests.exceptions.RequestException as req_err:
            frappe.throw(_("An error occurred while connecting to ZRA: {0}").format(str(req_err)))

        except ValueError:
            frappe.throw(_("Invalid response received from ZRA (not JSON)."))
    
   
        

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








