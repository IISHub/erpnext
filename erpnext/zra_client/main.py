import json
import requests
import frappe


ZRA_LOCAL_BASE_URL = "http://localhost:8080/sandboxvsdc1.0.8.0"
ZRA_SAVE_STOCK_URL = "/stock/saveStockItems"
ZRA_UPDATE_ITEM = "/items/updateItem"

BRANCH_CODE = "000"
TPIN = "2484778002"

class ZRAClient:
    def __init__(self):
        self.base_url = ZRA_LOCAL_BASE_URL
        self.update_url = f"{self.base_url}{ZRA_UPDATE_ITEM}"
        self.save_stock_url = f"{self.base_url}{ZRA_SAVE_STOCK_URL}"
        self.tpin = TPIN
        self.branch_code = BRANCH_CODE

    def update_item(self, **kwargs):
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
        useYn = kwargs.get("useYn", "Y")
        user = kwargs.get("user", "ADMIN")



        # Country code API
        try:
            r = requests.get(f"http://0.0.0.0:7000/country/{origin_place}/", timeout=5)
            r.raise_for_status()
            country_code = r.json().get("code")
        except Exception as e:
            frappe.throw(f"Failed to get country code: {e}")

        # Packaging unit code API
        try:
            r = requests.get(f"http://0.0.0.0:7000/packaging-unit-code/{packaging_unit}/", timeout=5)
            r.raise_for_status()
            packaging_unit_code = r.json().get("code")
        except Exception as e:
            frappe.throw(f"Failed to get packaging unit code: {e}")

        # Quantity unit code API
        try:
            r = requests.get(f"http://0.0.0.0:7000/unitofmeasure/{qty_unit}/", timeout=5)
            r.raise_for_status()
            qty_unit_code = r.json().get("code")
        except Exception as e:
            frappe.throw(f"Failed to get quantity unit code: {e}")

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
            frappe.throw(f"Invalid VAT category: {vat_category}")

        # IPL, TL, Excise categories
        iplCatCd = "IPL1" if ipl_category == "Insurance Premium Levy" else "IPL2"
        tlCatCd = "TL" if tl_category == "Tourism Levy" else "F"
        exciseTxCatCd = "ECM" if excise_tax_category == "Excise on Coal" else "EXEEG"

        if useYn not in ("Y", "N"):
            useYn = "Y"

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "itemCd": item_code,
            "itemClsCd": "50425610", 
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
            "useYn": useYn,
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
        except requests.RequestException as e:
            frappe.throw(f"Failed to update item in ZRA: {e}")

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
            response = requests.post(self.save_stock_url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to save stock in ZRA: {e}")
