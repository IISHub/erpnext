import frappe
import requests
from datetime import datetime
from frappe.utils import flt
from erpnext.zra_client.main import ZRAClient


class zraPurchase(ZRAClient):
    def __init__(self):
        super().__init__()

    def get_tpin_number(self):
        return self.tpin

    def get_branch_code(self):
        return self.branch_code

    def update_stock_after_purchase(self, payload):
        self.update_stock_after_purchase_view(payload)

    def update_stock_master_after_purchase(self, payload):
        self.save_stock_master(payload)

    def create_purchase(self, purchase_data):
        created_by = purchase_data.get("owner")
        try:
            payload ={
                "tpin": "2484778002",
                "bhfId": "000",
                "cisInvcNo": "CIS134",
                "regTyCd": "M",
                "pchsTyCd": "N",
                "rcptTyCd": "P",
                "pmtTyCd": "01",
                "pchsSttsCd": "02",
                "cfmDt": "20250716140000",
                "pchsDt": "20250716",
                "cnclReqDt": "",
                "cnclDt": "",
                "totItemCnt": 1,
                "totTaxblAmt": 86.21,
                "totTaxAmt": 13.79,
                "totAmt": 100.00,
                "remark": "Purchase test",
                "regrNm": "ADMIN",
                "regrId": "ADMIN",
                "modrNm": "ADMIN",
                "modrId": "ADMIN",
                "itemList": [
                    {
                    "itemSeq": 1,
                    "itemCd": "ZM2BGKG0000001",
                    "itemClsCd": "50102517",
                    "itemNm": "Item Name 1",
                    "pkgUnitCd": "BG",
                    "pkg": 1,
                    "qtyUnitCd": "KG",
                    "qty": 1,
                    "prc": 200.00,
                    "splyAmt": 100.00,
                    "dcRt": 0.00,
                    "dcAmt": 0.00,
                    "taxTyCd": "B",
                    "iplCatCd": "",
                    "tlCatCd": "",
                    "exciseCatCd": "",
                    "taxblAmt": 86.21,
                    "vatCatCd": "A",
                    "iplTaxblAmt": 0.00,
                    "tlTaxblAmt": 0.00,
                    "exciseTaxblAmt": 0.00,
                    "taxAmt": 13.79,
                    "iplAmt": 0.00,
                    "tlAmt": 0.00,
                    "exciseTxAmt": 0.00,
                    "totAmt": 100.00
                    }
                ]
                }

            # Call API to save purchase
            response_data = self.save_purchase_manually(payload)

            if response_data.get("resultCd") == "000":
                frappe.msgprint(f"Purchase saved successfully: {response_data.get('resultMsg')}")

                ocrnDt = datetime.now().strftime("%Y%m%d")

                update_stock_master_items = []
                update_stock_items = []

                for item in payload.get("itemList", []):
                    update_stock_items.append({
                        "itemSeq": item.get("itemSeq"),
                        "itemCd": item.get("itemCd"),
                        "itemClsCd": item.get("itemClsCd"),
                        "itemNm": item.get("itemNm"),
                        "pkgUnitCd": item.get("pkgUnitCd"),
                        "qtyUnitCd": item.get("qtyUnitCd"),
                        "qty": item.get("qty"),
                        "prc": item.get("prc"),
                        "splyAmt": item.get("splyAmt"),
                        "taxblAmt": item.get("taxblAmt"),
                        "vatCatCd": item.get("vatCatCd"),
                        "taxAmt": item.get("taxAmt"),
                        "totAmt": item.get("totAmt"),
                        "pkg": 1,
                        "totDcAmt": 0,
                    })
                    update_stock_master_items.append({
                        "itemCd": item.get("itemCd"),
                        "rsdQty": 12  # Adjust accordingly if you have real stock qty
                    })

                create_update_stock_payload = {
                    "tpin": self.get_tpin_number(),
                    "bhfId": self.get_branch_code(),
                    "sarNo": 1,
                    "orgSarNo": 0,
                    "regTyCd": "M",
                    "sarTyCd": "02",
                    "ocrnDt": ocrnDt,
                    "totItemCnt": payload['totItemCnt'],
                    "totTaxblAmt": payload['totTaxblAmt'],
                    "totTaxAmt": payload['totTaxAmt'],
                    "totAmt": payload['totAmt'],
                    "regrId": purchase_data.get("owner"),
                    "regrNm": purchase_data.get("owner"),
                    "modrNm": purchase_data.get("owner"),
                    "modrId": purchase_data.get("owner"),
                    "itemList": update_stock_items
                }

                create_update_stock_master_payload = {
                    "tpin": self.get_tpin_number(),
                    "bhfId": self.get_branch_code(),
                    "regrId": purchase_data.get("owner"),
                    "regrNm": purchase_data.get("owner"),
                    "modrNm": purchase_data.get("owner"),
                    "modrId": purchase_data.get("owner"),
                    "stockItemList": update_stock_master_items
                }

                self.run_stock_update_in_background(create_update_stock_payload, create_update_stock_master_payload, created_by)
            else:
                print("Purchase save failed. Response:", response_data)
                error_message = response_data.get("resultMsg", "Unknown error from ZRA API")
                frappe.throw(f"❌ Purchase save failed: {error_message}")

            purchase_data["purchase_payload"] = frappe.as_json(payload)

        except requests.RequestException as e:
            error_msg = response_data.get("resultMsg", "Unknown error")
            print("Failed Purchase Response:", response_data)
            frappe.throw(f"❌ Purchase save failed: {error_msg}")
