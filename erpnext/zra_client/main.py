from datetime import datetime
import requests
import frappe
import json




ZRA_LOCAL_BASE_URL = "http://localhost:8080/sandboxvsdc1.0.8.0"
ZRA_CREATE_ITEM = "/items/saveItem"
ZRA_SAVE_STOCK_URL = "/stock/saveStockItems"
ZRA_UPDATE_ITEM = "/items/updateItem"
ZRA_SAVE_STOCK_MASTER = "/stockMaster/saveStockMaster"
ZRA_SAVE_PURCHASE = "/trnsPurchase/savePurchase"
ZRA_CREATE_CUSTOMER = "/branches/saveBrancheCustomers"
ZRA_SALE = "/trnsSales/saveSales"
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
        self.tpin = TPIN
        self.branch_code = BRANCH_CODE
        self.org_sdc_id = ORIGIN_SCD_ID

    

    def create_item_zra(self, payload):
        try:       
            response = requests.post(url=self.create_item_url, json=payload, timeout=10)
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
        item_class_code = kwargs.get("item_class_code")
        item_code = kwargs.get("item_code")
        item_name = kwargs.get("item_name")
        product_type = kwargs.get("product_type")
        origin_place = kwargs.get("origin_place")
        packaging_unit = kwargs.get("packaging_unit")
        qty_unit = kwargs.get("qty_unit")
        vat_category = kwargs.get("vat_category")
        ipl_category = kwargs.get("ipl_category")
        tl_category = kwargs.get("tl_category")
        excise_tax_category = kwargs.get("excise_tax_category")
        use_yn = kwargs.get("use_yn", "Y")
        user = kwargs.get("user", "ADMIN")

        if not all([item_class_code, item_code, item_name, product_type, origin_place,
                    packaging_unit, qty_unit, vat_category, ipl_category,
                    tl_category, excise_tax_category]):
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
        tlCatCd = "TL" if tl_category == "Tourism Levy" else "F"
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
            "dftPrc": 15, 
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

        try:
            response = requests.post(self.update_url, json=payload, timeout=10)
            print("Response status:", response.status_code)
            response.raise_for_status() 
            return response.json()
        except requests.exceptions.RequestException as e:
            frappe.throw(f"Failed to update item in ZRA due to network or API error: {e}")
        except ValueError:
            frappe.throw(f"Invalid JSON response from ZRA API during item update.")


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
            response = requests.post(self.save_stock_url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to save stock in ZRA: {e}")

    def update_stock_after_purchase_view(self, payload=None):
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
        

    def save_stock_master(self, payload):
        try:
        

            response = requests.post(
                self.save_stock_master_url,
                json=payload,
                timeout=50
            )


            frappe.logger().info(
                f"Stock Master Request: {payload}\n"
                f"Response [{response.status_code}]: {response.text}"
            )

            response.raise_for_status()
            print("Stock master response:", response.text)
            return response.json()
        
           

        except requests.RequestException as e:
            error_msg = f"Request failed for stock master: {str(e)}"
            frappe.log_error(
                title="❌ Failed to save stock master",
                message=f"{error_msg}\nPayload: {payload}"
            )
            raise Exception(error_msg)

        except ValueError as e:
            error_msg = f"Invalid response for stock master: {str(e)}"
            frappe.log_error(
                title="❌ Stock Master Response Error",
                message=error_msg
            )
            raise Exception(error_msg)


        
    def save_purchase_manually(self, payload):

        try:
            response = requests.post(self.save_purchase_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data

        except requests.RequestException as e:
            frappe.log_error(title="❌ Failed to save purchase", message=str(e))
            raise Exception(f"❌ Failed to save purchase: {e}")


        
    def normal_sale(self, payload):
        try:
            response = requests.post(self.sale_url, json=payload)
            print("🔄 Raw response object:", response)
            print("📦 Response Status Code:", response.status_code)

            if response.status_code == 200:
                try:
                    data = response.json()
                    print("✅ ZRA Response JSON:", data)

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
            frappe.log_error(title="❌ Failed to send normal sale", message=str(e))
            raise Exception(f"❌ Network or connection error: {e}")
        

    def sale_credit_note(self, payload):
        print(payload)
        try:
            response = requests.post(self.sale_url, json=payload)
            print("✅ Credit note response status:", response.status_code)
            if response.headers.get('Content-Type') == 'application/json':
                print("📦 Response content:", response.json())
            else:
                print("📦 Response content:", response.text)
            return response

        except requests.RequestException as e:
            frappe.log_error(
                title="❌ Failed to sale credit note",
                message=str(e)
            )
            raise Exception(f"❌ Failed to post credit note sale: {e}")

    def sale_debit_note(self):
        try:
            response = requests.post(self.sale_url)

        except requests.RequestException as e:
            frappe.log_error(title="❌ Failed to sale debit note"
            , message=str(e))
            raise Exception(f"❌ Failed to normal sale: {e}")
        





