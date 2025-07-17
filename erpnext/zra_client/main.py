import json
import requests
import frappe


ZRA_LOCAL_BASE_URL = "http://localhost:8080/sandboxvsdc1.0.8.0"
ZRA_SAVE_STOCK_URL = "/stock/saveStockItems"
ZRA_UPDATE_ITEM = "/items/updateItem"
ZRA_SAVE_STOCK_MASTER = "/stockMaster/saveStockMaster"
ZRA_SAVE_PURCHASE = "/trnsPurchase/savePurchase"
ZRA_SALE = "/trnsSales/saveSales"

BRANCH_CODE = "000"
TPIN = "2484778002"

class ZRAClient:
    def __init__(self):
        self.base_url = ZRA_LOCAL_BASE_URL
        self.update_url = f"{self.base_url}{ZRA_UPDATE_ITEM}"
        self.save_stock_url = f"{self.base_url}{ZRA_SAVE_STOCK_URL}"
        self.save_stock_master_url = f"{self.base_url}{ZRA_SAVE_STOCK_URL}"
        self.save_purchase_url = f"{self.base_url}{ZRA_SAVE_PURCHASE}"
        self.sale_url = f"{self.base_url}{ZRA_SALE}"
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
        

    def save_stock_master(self, request):
        try:
            regrNm = "timeastw@gmail.com"
            regrId = "timeastw@gmail.com"
            modrNm = "timeastw@gmail.com"
            modrId = "timeastw@gmail.com"
            itemCd = "111111111111"
            rsdQty = 1

            payload = {
                "tpin": TPIN,
                "branchCode": BRANCH_CODE,
                "registrarName": regrNm,
                "registrarId": regrId,
                "modifierName": modrNm,
                "modifierId": modrId,
                "itemCode": itemCd,
                "residualQty": rsdQty
            }

            response = requests.post(self.save_stock_master_url, json=payload)
            frappe.logger().info(f"Stock Master Response [{response.status_code}]: {response.text}")
            response.raise_for_status()

        except requests.RequestException as e:
            frappe.log_error(title="❌ Failed to save stock master", message=str(e))
            raise Exception(f"❌ Failed to save stock master: {e}")
        
    def save_purchase_manually(self, payload):

        print("🌐 Saving to:", self.save_purchase_url)

        try:
            response = requests.post(self.save_purchase_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            print("📨 Purchase API Response:", data)

            if data.get("resultCd") != "000":
                frappe.throw(f"❌ Purchase save failed: {data.get('resultMsg')}")

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
            else:
                raise Exception(f"ZRA HTTP Error {response.status_code}: {response.text}")

        except requests.RequestException as e:
            frappe.log_error(title="❌ Failed to send normal sale", message=str(e))
            raise Exception(f"❌ Network or connection error: {e}")

    def sale_credit_note(self):
        try:
            response = requests.post(self.sale_url)

        except requests.RequestException as e:
            frappe.log_error(title="❌ Failed to sale credit note"
            , message=str(e))
            raise Exception(f"❌ Failed to normal sale: {e}")
        
    def sale_debit_note(self):
        try:
            response = requests.post(self.sale_url)

        except requests.RequestException as e:
            frappe.log_error(title="❌ Failed to sale debit note"
            , message=str(e))
            raise Exception(f"❌ Failed to normal sale: {e}")
        





