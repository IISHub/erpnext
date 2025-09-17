import json
import random
import frappe
import requests
from datetime import datetime
from frappe.utils import strip
from urllib.parse import quote
from frappe.model.naming import make_autoname
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.purchase.main import ResponseRetry
from erpnext.zra_client.error.exceptions import RequestException
from erpnext.zra_client.error.exceptions import RequestException, RETRYABLE_ERRORS

class zraItem(ZRAClient):

    def update_item_helper(self, payload):
        return self.update_item(payload)
    def get_tpin(self):
        return self.tpin

    def get_branch(self):
        return self.branch_code
    


    def create_item_helper(self, payload):
        self.create_item_zra(payload)

    def create_item_composition_helper(self, payload):
        return self.create_item_composition_zra_client(payload)

    def create_item(self, item_data):
        
        return item_data
    
    def update_item(self, update_data):

        print("raw data: ", update_data)
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
        tourism_levy_category = update_data.get("custom_tourism_levy")
        use_yn = update_data.get("use_yn", "Y")
        user = update_data.get("modified_by")
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

        
        if ipl_category == "Insurance Premium Levy":
            iplCatCd = "IPL1" 
        elif ipl_category == "Re-Insurance":
            iplCatCd = "IPL2"
        else:
            iplCatCd = None

        if tourism_levy_category == "Tourism Levy":
            tlCatCd = "TL"
        elif tourism_levy_category == "Service Charge 10%":
            tlCatCd = "F"

        else:
            tlCatCd = None

        if excise_tax_category == "Excise on Coal":
            exciseTxCatCd = "ECM"
            
        elif excise_tax_category== "Excise Electricity":
            exciseTxCatCd = "EXEEG"

        else:
            exciseTxCatCd = None

        if use_yn not in ("Y", "N"):
            use_yn = "Y"

        logged_in_user = self.get_logged_in_details(user)
        username = logged_in_user.get("username", "system")


        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "itemCd": item_code,
            "itemClsCd": self.get_classification_code(item_class_code),
            "itemTyCd": itemTyCd,
            "itemNm": item_name,
            "itemStdNm": item_name,
            "orgnNatCd": self.get_country_code_by_name(origin_place),
            "pkgUnitCd": self.get_packaging_unit(packaging_unit),
            "qtyUnitCd": self.get_units_of_measure(qty_unit),
            "vatCatCd": vatCatCd_code,
            "iplCatCd": iplCatCd,
            "tlCatCd": tlCatCd,
            "exciseTxCatCd": exciseTxCatCd,
            "dftPrc": price, 
            "useYn": use_yn,
            "regrNm": username,
            "regrId": username,
            "modrNm": username,
            "modrId": username,
        }

        print("Sending payload:", json.dumps(payload, indent=2))

        response = self.update_item_zra_client(payload)
        return response

        # self.update_item_in_background(self.update_url, payload)

    def save_item_composition(self, composition_data):
        print("Composition Data Received:", composition_data)
        modified_by = composition_data.get("modified_by")
        itemCd = composition_data.get("item")
        name = composition_data.get("name")

        item_data = composition_data.get("items", [])
        itemQtyUsed = 0
        
        for item in item_data:
            quantity = item.get("qty", 0)
            
            try:
                quantity = float(quantity)
            except (TypeError, ValueError):
                quantity = 0
                
            itemQtyUsed += quantity 

        if itemQtyUsed <= 0:
            frappe.throw("Total quantity used must be greater than zero.")

        payload = {
            "tpin": self.tpin, 
            "bhfId": self.branch_code, 
            "itemCd": itemCd, 
            "cpstItemCd": name, 
            "cpstQty": itemQtyUsed, 
            "regrId": modified_by, 
            "regrNm": modified_by
        }

        print("Item Composition Payload:", json.dumps(payload, indent=2))
        response = self.create_item_composition_helper(payload)
        response = response.json()
        print(response)
        if response.get("resultCd") == "000":
            frappe.msgprint("Item composition saved successfully.")
        else:
            try:
                resultCd = response.get("resultCd")
                RequestException(resultCd or "UNKNOWN_RESPONSE").throw()
            except requests.exceptions.Timeout:
                RequestException("TIMEOUT").throw()
            except requests.exceptions.RequestException:
                RequestException("REQUEST_FAILED").throw()

    

    def create_item_zra_client_helper(self, item_data):

        get_item_class_code = str(item_data.get("custom_item_class_code", "")).strip()
        if not get_item_class_code:
            frappe.throw("Item Classification Code is required.")

        product_type = str(item_data.get("custom_product_type", "")).strip()
        itemTyCd = None
        if product_type == "Raw Material":
            itemTyCd = "1"
        elif product_type == "Finished Product":
            itemTyCd = "2"
        elif product_type == "Service":
            itemTyCd = "3"
        if not itemTyCd:
            frappe.throw("Missing or invalid ZRA Item Type Code. Must be 'Raw Material', 'Finished Product', or 'Service'.")

        unit_name = str(item_data.get("custom_units_of_measure", "")).strip()
        if not unit_name:
            frappe.throw("Missing ZRA Quantity Unit Code.")

        country_name = str(item_data.get("custom_origin_place_code", "")).strip()
        if not country_name:
            frappe.throw("Missing ZRA Country of Origin Code.")

        packaging_unit = str(item_data.get("custom_packaging_unit_code", "")).strip()
        if not packaging_unit:
            frappe.throw("Missing ZRA Packaging Unit Code.")
        try:
            country_code = self.get_country_code_by_name(country_name)
            packaging_unit_code = self.get_packaging_unit(packaging_unit)
            qtyUnitCd = self.get_units_of_measure(unit_name)
        except Exception as e:
            frappe.log_error(f"Error getting codes from ZRA client: {e}", "ZRA Item Save Error")
            frappe.throw("Failed to resolve required ZRA codes.")

        vat_raw = str(item_data.get("custom_vat", "")).replace(" ", "").strip()
        vat_map = {
            "StandardRated": "A",
            "MinimumTaxableValue": "B",
            "Exports": "C1",
            "ZeroRatingLocalPurchases": "C2",
            "ZeroRatedByNature": "C3",
            "Exempt": "D",
            "Disbursement": "E",
            "ServiceCharge10%": "F",
            "ReverseVAT": "RVAT"
        }
        vatCatCd = vat_map.get(vat_raw, "A")
        excise_name = str(item_data.get("custom_excise_tax_category_code", "")).strip()
        exciseTxCatCd = ""
        if excise_name == "Excise on Coal":
            exciseTxCatCd = "ECM"
        elif excise_name == "Excise Electricity":
            exciseTxCatCd = "EXEEG"


        ipl_name = str(item_data.get("custom_ipl_category_code", "")).strip()
        iplCatCd = None
        if ipl_name == "Insurance Premium Levy":
            iplCatCd = "IPL1"
        elif ipl_name == "Re-Insurance":
            iplCatCd = "IPL2"

        tl_name = str(item_data.get("custom_tourism_levy_category_code", "")).strip()
        tlCatCd = "TL" if tl_name == "Tourism Levy" else None

        rrp = None
        rrp_raw = item_data.get("custom_recommended_retail_price")
        if rrp_raw is not None and str(rrp_raw).strip() != "":
            try:
                rrp = float(rrp_raw)
            except (ValueError, TypeError):
                frappe.log_error(f"Invalid RRP value for item {item_data.get('item_name','<unknown>')}: {rrp_raw}", "ZRA Item Save Warning")
                rrp = None

        svcChargeYn = "Y" if item_data.get("custom_has_service_charge") else "N"
        rentalYn = "Y" if item_data.get("custom_has_rental_charge") else "N"

        add_info = str(item_data.get("custom_zra_additional_info", "")).strip() or None
        barcode = str(item_data.get("barcode", "")).strip() or None

        btchNo = None
        item_code = None
        for _ in range(5):
            if not all([country_code, itemTyCd, packaging_unit_code, qtyUnitCd]):
                frappe.throw("Missing required codes for item_code generation.")
            try:
                rand_num = random.randint(1, 9_999_999)
                formatted = f"{rand_num:07d}"
                candidate = f"{country_code}{itemTyCd}{packaging_unit_code}{qtyUnitCd}{formatted}"
                if not frappe.db.exists("Item", {"item_code": candidate}):
                    item_code = candidate
                    break
            except Exception as e:
                frappe.log_error(f"Random code generation failed: {e}", "ZRA Item Save Error")
        else:
            frappe.throw("Failed to generate a unique item code after 5 attempts.")

        opening_stock = 0.0
        try:
            raw_opening_stock = item_data.get("opening_stock")
            if raw_opening_stock is not None and str(raw_opening_stock).strip() != "":
                opening_stock = float(raw_opening_stock)
        except (ValueError, TypeError):
            frappe.throw("Invalid opening_stock value. Must be a number.")

        default_price = 0.0
        try:
            raw_default_price = item_data.get("standard_rate")
            if raw_default_price is not None and str(raw_default_price).strip() != "":
                default_price = float(raw_default_price)
        except (ValueError, TypeError):
            frappe.throw("Invalid standard_rate value. Must be a number.")

        created_by = item_data.get("owner", "System")
        try:
            logged_in_user = self.get_logged_in_details(created_by)
            username = logged_in_user.get("username", created_by)
        except Exception:
            username = created_by

        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_branch_code(),
            "itemCd": item_code,
            "itemClsCd": self.get_classification_code(get_item_class_code),
            "itemTyCd": itemTyCd,
            "itemNm": item_data.get("item_name"),
            "orgnNatCd": country_code,
            "pkgUnitCd": packaging_unit_code,
            "qtyUnitCd": qtyUnitCd,
            "vatCatCd": vatCatCd,
            "iplCatCd": iplCatCd,
            "tlCatCd": tlCatCd,
            "exciseTxCatCd": exciseTxCatCd,
            "btchNo": btchNo,
            "bcd": barcode,
            "dftPrc": default_price,
            "rrp": rrp,
            "svcChargeYn": svcChargeYn,
            "rentalYn": rentalYn,
            "addInfo": add_info,
            "sftyQty": opening_stock,
            "isrcAplcbYn": "N",
            "useYn": "Y",
            "regrNm": username,
            "regrId": username,
            "modrNm": username,
            "modrId": username
        }

        print("Payload being sent:", json.dumps(payload, indent=2))
        try:
            response = self.create_item_zra(payload)
            if isinstance(response, requests.Response):
                response.raise_for_status()
                data = response.json()
            else:
                data = response if isinstance(response, dict) else response.json()
        except requests.exceptions.Timeout:
            RequestException("TIMEOUT").throw()
        except requests.exceptions.RequestException:
            RequestException("REQUEST_FAILED").throw()
        except ValueError:
            RequestException("UNKNOWN_RESPONSE").throw()
        except Exception as e:
            frappe.log_error(f"Unexpected error calling ZRA: {e}", "ZRA Item Save Error")
            RequestException("REQUEST_FAILED").throw()
        result_cd = data.get("resultCd")
        if result_cd == "000":
            frappe.msgprint("Item has been saved successfully.")
            try:
                site = "erpnext.localhost"
                item_code = payload["itemCd"]
                self.update_item_status_by_item_code(item_code, 1, 10, site)

                return item_code, payload["itemNm"]
            except Exception as e:
                frappe.log_error(f"Failed to update item status: {e}", "ZRA Item Save Warning")
            return data
        else:
            if result_cd in RETRYABLE_ERRORS:
                try:
                    ResponseRetry(payload, task_type=2).determine_task_type()
                except Exception as e:
                    frappe.log_error(f"Failed to schedule retry: {e}", "ZRA Item Save Warning")
                RequestException(result_cd or "CREATE_ITEM_ERROR").throw()
            else:
                RequestException(result_cd or "CREATE_ITEM_ERROR").throw()

            
