import requests
import frappe
from frappe import throw, _
from erpnext.zra_client.main import ZRAClient
from datetime import datetime


class Imports(ZRAClient):
    def __init__(self):
        super().__init__()
        self.to_use_data = {}

    def get_tpin(self):
        return self.tpin

    def get_bhf_id(self):
        return self.branch_code

    def call_update_import(self, payload):
        return self.zra_client_update_import(payload)

    def update_import(self, import_data):
        # Extract required fields
        taskCd = import_data.get("custom_task_cd")
        modified_by = import_data.get("modified_by")
        get_class_code = import_data.get("custom_item_class_code")
        item_code = import_data.get("name")
        hscd = import_data.get("custom_hscd")
        remarks = import_data.get("custom_remark")
        created_by = import_data.get("owner")
        get_status = import_data.get("custom_status")

        status = 3 if get_status == "Approved" else 4

        # Validate required fields
        if not all([taskCd, get_class_code, item_code]):
            throw(_("Missing required fields: 'custom_task_cd', 'custom_item_class_code', or 'name'."))

        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_bhf_id(),
            "taskCd": taskCd,
            "dclDe": datetime.now().strftime("%Y%m%d"),
            "importItemList": [
                {
                    "itemSeq": 1,
                    "hsCd": hscd,
                    "itemClsCd": self.get_classification_code(get_class_code),
                    "itemCd": item_code,
                    "imptItemSttsCd": status,
                    "remark": remarks,
                    "modrNm": modified_by,
                    "modrId": modified_by,
                }
            ]
        }

        print("Payload to send to ZRA:", payload)

        # Call the ZRA API
        try:
            response = self.call_update_import(payload)
            if response.status_code == 200:
                return response
            update_stock_items = []
            update_stock_master_items = []

            for item in self.to_use_data.get("itemList", []):
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
                    "taxblAmt": item.get("vatTaxblAmt"),
                    "vatCatCd": item.get("vatCatCd"),
                    "taxAmt": item.get("vatAmt"),
                    "totAmt": item.get("totAmt"),
                    "pkg": item.get("pkg", 1),
                    "totDcAmt": item.get("dcAmt", 0),
                })

                remaining_qty = 12  # adjust as needed
                update_stock_master_items.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": max(0, remaining_qty)
                })

            ocrnDt = datetime.now().strftime("%Y%m%d")

            update_stock_payload = {
                "tpin": self.tpin,
                "bhfId": self.branch_code,
                "sarNo": 1,
                "orgSarNo": 0,
                "regTyCd": "M",
                "sarTyCd": "06",
                "ocrnDt": ocrnDt,
                "totItemCnt": self.to_use_data.get('totItemCnt', 0),
                "totTaxblAmt": self.to_use_data.get('totTaxblAmt', 0),
                "totTaxAmt": self.to_use_data.get('totTaxAmt', 0),
                "totAmt": self.to_use_data.get('totAmt', 0),
                "regrId": created_by,
                "regrNm": created_by,
                "modrNm": created_by,
                "modrId": created_by,
                "itemList": update_stock_items
            }

            update_stock_master_payload = {
                "tpin": self.tpin,
                "bhfId": self.get_bhf_id(),
                "regrId": created_by,
                "regrNm": created_by,
                "modrNm": created_by,
                "modrId": created_by,
                "stockItemList": update_stock_master_items
            }

            print("Update stock payload:", update_stock_payload)
            print("Update stock master payload:", update_stock_master_payload)

            # Run background stock update
            self.run_stock_update_in_background(update_stock_payload, update_stock_master_payload, created_by)

        except requests.exceptions.Timeout:
            throw(_("ZRA request timed out."))
        except requests.exceptions.RequestException as e:
            throw(_("ZRA request failed: {0}").format(e))
