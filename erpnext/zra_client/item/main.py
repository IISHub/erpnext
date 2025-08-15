from datetime import datetime
import random
import requests
import json
import frappe
from urllib.parse import quote
from frappe.model.naming import make_autoname
from erpnext.zra_client.main import ZRAClient
from frappe.utils import strip


class zraItem(ZRAClient):

    def update_item_helper(self, payload):
        return self.update_item(payload)
    def get_tpin(self):
        return self.tpin

    def get_branch(self):
        return self.branch_code
    


    def create_item_helper(self, payload):
        self.create_item_zra(payload)

    def create_item(self, item_data):
        
        return item_data
    
    def update_item(self, update_data):

        item_class_code = update_data.get("custom_item_class_code")
        item_code = update_data.get("item_code")
        item_name = update_data.get("item_name")
        product_type = update_data.get("custom_product_type")
        origin_place = update_data.get("custom_origin_place_code")
        packaging_unit = update_data.get("custom_packaging_unit_code")
        qty_unit = update_data.get("custom_units_of_measure")
        vat_category = update_data.get("custom_vat")
        ipl_category = update_data.get("custom_ipl_category_code")
        excise_tax_category = update_data.get("custom_excise_tax_category_code")
        use_yn = update_data.get("use_yn", "Y")
        user = update_data.get("user", "ADMIN")
        price = update_data.get("standard_rate")

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


        
    
    

   