from datetime import datetime
import random
import requests
import json
import frappe
from urllib.parse import quote
from frappe.model.naming import make_autoname
from erpnext.zra_client.main import ZRAClient
from frappe.utils import strip


@frappe.whitelist()
def get_item_classes(q=None):
    if not q:
        q = ""
    url = f"http://127.0.0.1:7000/get-item-classes/?q={q}&page=1&page_size=50"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        frappe.log_error(f"Failed to fetch item classes: {e}")
        return []

    return [item['itemClsNm'] for item in data.get('results', [])]


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

        iplCatCd = "IPL1" if ipl_category == "Insurance Premium Levy" else "IPL2"
        tlCatCd = "TL"
        exciseTxCatCd = "ECM" if excise_tax_category == "Excise on Coal" else "EXEEG"

        if use_yn not in ("Y", "N"):
            use_yn = "Y"


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

        response = self.update_item_zra_client(payload)
        return response

        # self.update_item_in_background(self.update_url, payload)


        
    
    

   