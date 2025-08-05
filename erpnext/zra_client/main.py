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
                    print("Stock updated successfully after sale.")

                    create_update_stock_master_payload = {
                        "tpin": self.tpin,
                        "bhfId": self.branch_code,
                        "regrId": created_by,
                        "regrNm": created_by,
                        "modrNm": created_by,
                        "modrId": created_by,
                        "stockItemList": update_stock_master_items
                    }
                    print(create_update_stock_master_payload)
                    response = self.save_stock_master_zra_client(create_update_stock_master_payload)
                    print("Response :", response)
                    if response.get("resultCd") == "000":
                        
                        print("Stock master updated successfully after sale.")
                    else:
                        print("Failed to update stock master:", response)
                else:
                    print(f"Failed to update stock: {response.get('resultMsg')}")
            except Exception as e:
                print(f"Exception in background stock update task: {e}")

        thread = threading.Thread(target=background_task)
        thread.daemon = True  
        thread.start()

    def get_packaging_unit(self, packaging_name):

        if not packaging_name:
            return None
            
        packaging_unit_code = None
        try:
            res = requests.get(f"http://0.0.0.0:7000/packaging-unit-code/{quote(packaging_name)}/", timeout=10)
            res.raise_for_status()
            response_data = res.json()
            packaging_unit_code = response_data.get("code")
            print(res)
            
            if not packaging_unit_code:
                frappe.throw(f"Packaging unit code not found for '{packaging_name}' from external API response: {response_data}")
                
        except requests.exceptions.Timeout:
            frappe.throw(f"Timeout fetching packaging unit code for '{packaging_name}'.")
        except requests.exceptions.RequestException as e:
            frappe.throw(f"Error fetching packaging unit code for '{packaging_name}' from external API: {e}")
        except ValueError as e:
        
            frappe.throw(f"Invalid JSON response when fetching packaging unit code for '{packaging_name}': {e}")

    
    
        return packaging_unit_code

    def get_units_of_measure(self, unit_name):
        if not unit_name:
            frappe.throw("Unit name cannot be empty.")
        
        qtyUnitCd = None
        
        try:
            
            encoded_unit_name = quote(unit_name)
            url = f"http://0.0.0.0:7000/unitofmeasure/{encoded_unit_name}/"
            
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            
            response_data = res.json()
            qtyUnitCd = response_data.get("code")
            
            if not qtyUnitCd:
                frappe.throw(f"Unit code not found for '{unit_name}' from external API.")
                
        except requests.exceptions.Timeout:
            frappe.throw(f"Timeout fetching unit code for '{unit_name}'. Please try again.")
            
        except requests.exceptions.HTTPError as e:
            if res.status_code == 404:
                frappe.throw(f"Unit '{unit_name}' not found in external API.")
            else:
                frappe.throw(f"HTTP error {res.status_code} fetching unit code for '{unit_name}': {e}")
                
        except requests.exceptions.ConnectionError:
            frappe.throw(f"Connection error fetching unit code for '{unit_name}'. Please check your network connection.")
            
        except requests.exceptions.JSONDecodeError:
            frappe.throw(f"Invalid JSON response received for unit '{unit_name}' from external API.")
            
        except requests.RequestException as e:
            frappe.throw(f"Error fetching unit code for '{unit_name}' from external API: {e}")
            
        except Exception as e:
            frappe.throw(f"Unexpected error fetching unit code for '{unit_name}': {e}")
        
        return qtyUnitCd

    def create_item_zra(self, payload):
        try:       
            response = requests.post(url=self.create_item_url, json=payload, timeout=70)
            response.raise_for_status() 
            print(response)
            return response.json()
        
        except requests.exceptions.RequestException as e:
            frappe.throw(f"Failed to add item in ZRA due to network or API error: {e}")
        except ValueError:
            frappe.throw(f"Invalid JSON response from ZRA API during adding item.")

    
    def create_customer(self, tpin, customer_name, email_id, mobile_no, created_by):
        if not self.tpin:
            raise ValueError("TPIN is required.")
        print("Creating customer with data:", tpin, customer_name, email_id, mobile_no, created_by)

        payload = {
            "tpin": TPIN,
            "bhfId": BRANCH_CODE,
            "custNo": mobile_no,      
            "custTpin": tpin,      
            "custNm": customer_name,              
            "adrs": None,
            "email":  email_id,
            "faxNo": None,
            "useYn": "Y",
            "remark": None,
            "regrNm": created_by,
            "regrId": created_by,
            "modrNm": created_by,
            "modrId": created_by
        }
        print(payload)

        try:
            response = requests.post(self.create_customer_url, json=payload)
            print("Status Code:", response.status_code)
            print("Response:", response.text)
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")

    def update_item(self, **kwargs):
        item_class_code = kwargs.get("custom_item_class_code")
        item_code = kwargs.get("item_code")
        item_name = kwargs.get("item_name")
        product_type = kwargs.get("custom_product_type")
        origin_place = kwargs.get("custom_origin_place_code")
        packaging_unit = kwargs.get("custom_packaging_unit_code")
        qty_unit = kwargs.get("custom_units_of_measure")
        vat_category = kwargs.get("custom_vat")
        ipl_category = kwargs.get("custom_ipl_category_code")
        # tl_category = kwargs.get("tl_category")
        excise_tax_category = kwargs.get("custom_excise_tax_category_code")
        use_yn = kwargs.get("use_yn", "Y")
        user = kwargs.get("user", "ADMIN")
        price = kwargs.get("standard_rate")

        required_fields = {
        "item_class_code": item_class_code,
        "item_code": item_code,
        "item_name": item_name,
        "product_type": product_type,
        "origin_place": origin_place,
        "packaging_unit": packaging_unit,
        "qty_unit": qty_unit,
        "vat_category": vat_category,
        "ipl_category": ipl_category,
        # "tl_category": tl_category,
        "excise_tax_category": excise_tax_category
    }
        print("Received values:")
        for key, value in required_fields.items():
            print(f"  {key}: {value}")


        if not all([item_class_code, item_code, item_name, product_type, origin_place,
                    packaging_unit, qty_unit, vat_category, ipl_category,
                    excise_tax_category]):
            frappe.throw("Missing required item details for ZRA update.")



        # Get Classification code
        item_class_code_stripped = item_class_code.strip()
        try:
            req = requests.get(f"{self.internal_base_url}/api/get-item-class-by-name/{item_class_code_stripped}/", timeout=5)
            req.raise_for_status()
            data = req.json()
            itemClsCd = data.get("itemClsCd")
            if not itemClsCd:
                frappe.throw(f"Item classification code '{item_class_code_stripped}' not found in API response.")
        except requests.exceptions.RequestException as e:
            frappe.throw(f"Failed to get item classification code for '{item_class_code_stripped}': {e}")
        except ValueError: # Catches JSON decoding errors
            frappe.throw(f"Invalid JSON response for item classification code '{item_class_code_stripped}'.")

        # Country code API
        try:
            r = requests.get(f"{self.internal_base_url}/country/{origin_place}/", timeout=5)
            r.raise_for_status()
            country_code = r.json().get("code")
            if not country_code:
                frappe.throw(f"Country code for '{origin_place}' not found in API response.")
        except requests.exceptions.RequestException as e:
            frappe.throw(f"Failed to get country code for '{origin_place}': {e}")
        except ValueError:
            frappe.throw(f"Invalid JSON response for country code '{origin_place}'.")

        # Packaging unit code API
        try:
            r = requests.get(f"{self.internal_base_url}/packaging-unit-code/{packaging_unit}/", timeout=5)
            r.raise_for_status()
            packaging_unit_code = r.json().get("code")
            if not packaging_unit_code:
                frappe.throw(f"Packaging unit code for '{packaging_unit}' not found in API response.")
        except requests.exceptions.RequestException as e:
            frappe.throw(f"Failed to get packaging unit code for '{packaging_unit}': {e}")
        except ValueError:
            frappe.throw(f"Invalid JSON response for packaging unit code '{packaging_unit}'.")

        # Quantity unit code API
        try:
            r = requests.get(f"{self.internal_base_url}/unitofmeasure/{qty_unit}/", timeout=5)
            r.raise_for_status()
            qty_unit_code = r.json().get("code")
            if not qty_unit_code:
                frappe.throw(f"Quantity unit code for '{qty_unit}' not found in API response.")
        except requests.exceptions.RequestException as e:
            frappe.throw(f"Failed to get quantity unit code for '{qty_unit}': {e}")
        except ValueError:
            frappe.throw(f"Invalid JSON response for quantity unit code '{qty_unit}'.")


        # Map product type
        itemTyCd = {"Raw Material": "1", "Finished Product": "2"}.get(product_type, "3")

        # VAT category map
        vat_code_map = {
            "StandardRated": "A",
            "MinimumTaxableValue": "B",
            "Exports": "C1",
            "ZeroRatingLocalPurchases": "C2",
            "ZeroRatedByNature": "C3",
            "Exempt": "D",
            "Disbursement": "E",
            "ReverseVAT": "RVAT"
        }
        vatCatCd_code = vat_code_map.get(vat_category)
        if not vatCatCd_code:
            frappe.throw(f"Invalid VAT category: '{vat_category}'. Please provide a valid VAT category.")

        # IPL, TL, Excise categories (assuming these are fixed mappings based on the original code)
        iplCatCd = "IPL1" if ipl_category == "Insurance Premium Levy" else "IPL2"
        tlCatCd = "TL"
        exciseTxCatCd = "ECM" if excise_tax_category == "Excise on Coal" else "EXEEG"

        if use_yn not in ("Y", "N"):
            use_yn = "Y"


        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "itemCd": item_code,
            "itemClsCd": itemClsCd,
            "itemTyCd": itemTyCd,
            "itemNm": item_name,
            "itemStdNm": item_name,
            "orgnNatCd": country_code,
            "pkgUnitCd": packaging_unit_code,
            "qtyUnitCd": qty_unit_code,
            "vatCatCd": vatCatCd_code,
            "iplCatCd": iplCatCd,
            "tlCatCd": tlCatCd,
            "exciseTxCatCd": exciseTxCatCd,
            "dftPrc": price, 
            "manufacturerTpin": self.tpin, 
            "manufacturerItemCd": "1234",
            "rrp": "1000",
            "svcChargeYn": "Y",
            "rentalYn": "N",
            "addInfo": None,
            "sftyQty": 5, 
            "isrcAplcbYn": "N", 
            "useYn": use_yn,
            "regrNm": user,
            "regrId": user,
            "modrNm": user,
            "modrId": user,
        }

        print("Sending payload:", payload)

        self.update_item_in_background(self.update_url, payload)



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
            response = requests.post(self.save_stock_url, json=payload, timeout=60)
            response.raise_for_status()
            print("Stock update response:", response.text)
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to update stock after purchase in ZRA: {e}")
        

    def save_stock_master_zra_client(self, payload):
        print("Now calling stock master")
        try:
            response = requests.post(self.save_stock_master_url, json=payload, timeout=50)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.RequestException as e:
            error_msg = f"Request failed for stock master: {str(e)}"
            frappe.log_error(title="Stock Master Error", message=error_msg)
            return {"status": "error", "message": error_msg}





        
    def save_purchase_manually(self, payload):
        try:
            response = requests.post(self.save_purchase_url, json=payload, timeout=80)
            response.raise_for_status()
            data = response.json()
            print("✅ Success Response:", data)
            return data

        except requests.Timeout:
            error_msg = "The request timed out. The server may be down or too slow to respond."
            print("Timeout Error:", error_msg)
            frappe.throw(f"Purchase save failed: {error_msg}")

        except requests.ConnectionError as e:
            error_msg = f"Connection error: {e}"
            print("Connection Error:", error_msg)
            frappe.throw(f"Purchase save failed: {error_msg}")

        except requests.HTTPError as e:
            try:
                response_data = e.response.json()
                error_msg = response_data.get("resultMsg", str(e))
            except Exception:
                error_msg = f"HTTP error occurred: {e}"
            print("HTTP Error Response:", error_msg)
            frappe.throw(f"Purchase save failed: {error_msg}")

        except requests.RequestException as e:
            error_msg = f"Unexpected error: {str(e)}"
            print("RequestException:", error_msg)
            frappe.throw(f"Purchase save failed: {error_msg}")


        
    def normal_sale(self, payload):
        print("**** calling sale ***")
        try:
            response = requests.post(self.sale_url, json=payload)
            print(" Raw response object:", response)


            if response.status_code == 200:
                try:
                    data = response.json()
                    print("ZRA Response JSON:", data)

                    if data.get("resultCd") != "000":
                        raise Exception(f"ZRA Error {data.get('resultCd')}: {data.get('resultMsg')}")
                    return data
                except ValueError:
                    raise Exception(f"ZRA Response is not valid JSON. Raw text: {response.text}")
                

            elif response.status_code == 400:
                try:
                    data = response.json()
                    error_message = data.get("error", "Unknown error")
                    raise Exception(f"Error saving normal sale")   

                except ValueError:
                    raise Exception(f"ZRA Response is not valid JSON. Raw text: {response.text}")
            else:
                raise Exception(f"ZRA HTTP Error {response.status_code}: {response.text}")

        except requests.RequestException as e:
            frappe.log_error(title="Failed to send normal sale", message=str(e))
            raise Exception(f"Network or connection error: {e}")
        

    def credit_sale(self, payload):
        print("**** calling credit sale ***")
        try:
            response = requests.post(self.sale_url, json=payload)
            print("Raw response object:", response)
            print("Response Status Code:", response.status_code)

            if response.status_code == 200:
                try:
                    data = response.json()
                    print("ZRA Response JSON:", data)

                    if data.get("resultCd") != "000":
                        raise Exception(f"ZRA Error {data.get('resultCd')}: {data.get('resultMsg')}")
                    return data
                except ValueError:
                    raise Exception(f"ZRA Response is not valid JSON. Raw text: {response.text}")
                

            elif response.status_code == 400:
                try:
                    data = response.json()
                    print(data)
                    error_message = data.get("error", "Unknown error")
                    raise Exception(f"Error saving credit sale")   

                except ValueError:
                    raise Exception(f"ZRA Response is not valid JSON. Raw text: {response.text}")
            else:
                raise Exception(f"ZRA HTTP Error {response.status_code}: {response.text}")

        except requests.RequestException as e:
            frappe.log_error(title="Failed to send credit sale", message=str(e))
            raise Exception(f"Network or connection error: {e}")
        
        
        
    def sale_debit_note(self, payload):
        try:
            response = requests.post(self.sale_url, json=payload)
            print("Debit note response status:", response.status_code)

            if response.headers.get('Content-Type', '').startswith('application/json'):
                resp_json = response.json()
                print("📦 Response content:", resp_json)
                return resp_json
            else:
                frappe.log_error(title="Debit note response not JSON",
                                message=f"Content-Type: {response.headers.get('Content-Type')}")
                return None

        except requests.RequestException as e:
            frappe.log_error(title="Failed to sale debit note", message=str(e))
            raise Exception(f"Failed to normal sale: {e}")

    
    def zra_client_update_import(self, payload):
        
        response = requests.post(self.update_import_url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        print(result)

        if result.get("resultCd") in ["000", "001"]:
            print("Import update successful.")
        else:
            frappe.throw(_("ZRA Error: {0}").format(result.get('resultMsg', 'Unknown error')))

        return result
    
    def save_item_composition_zra_client(self, payload):
        try:
            response = requests.post(self.save_item_composition_url, payload)
            response.raise_for_status()
            results = 1

        except requests.RequestException as e:
            raise Exception("Failed to save item composition")
    


    def create_export_sale_zra_client(self, payload):
        print("create export sale payload: ", payload)
        try:
            response = requests.post(self.sale_url, json=payload)
            response.raise_for_status()
            result = response.json()
            print("Results for the response: ", result)
            return response

        except requests.HTTPError as http_err:
            error_content = ""
            if http_err.response is not None:
                try:
                    error_content = http_err.response.text
                except Exception:
                    error_content = "Could not read error response text."
            
            print("HTTP Error:", http_err)
            print("Response content:", error_content)
            raise Exception(f"Server Error\nException: Failed to save import sale\nResponse: {error_content}")

        except requests.RequestException as e:

            print("Request Exception:", e)
            raise Exception(f"Server Error\nException: Failed to save import sale\nDetails: {str(e)}")
        

    def create_lpo_sale_zra_client(self, payload):
        print("Creating LPO sale payload:", payload)
        try:
            response = requests.post(self.sale_url, json=payload)
            response.raise_for_status()
            result = response.json()
            print("Results for the response:", result)
            return response

        except requests.HTTPError as http_err:
            error_content = ""
            if http_err.response is not None:
                try:
                    error_content = http_err.response.text
                except Exception:
                    error_content = "Could not read error response text."
            
            print("HTTP Error:", http_err)
            print("Response content:", error_content)
            raise Exception(f"Server Error\nException: Failed to save LPO sale\nResponse: {error_content}")

        except requests.RequestException as e:
            print("Request Exception:", e)
            raise Exception(f"Server Error\nException: Failed to save LPO sale\nDetails: {str(e)}")

        

    def get_principals_zra_client(self, payload):
        try:
            response = requests.post(self.get_principal_url, json=payload)
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








