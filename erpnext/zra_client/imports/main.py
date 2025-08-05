import requests
from frappe import throw, _
import frappe
from erpnext.zra_client.main import ZRAClient

class Imports(ZRAClient):
    def __init__(self):
        super().__init__()

    def get_tpin(self):
        return self.tpin

    def get_bhf_id(self):
        return self.branch_code

    def call_update_import(self, payload):
        return self.zra_client_update_import(payload)

    def update_import(self, import_data):
        print("Import data received:", import_data)

    
        taskCd = import_data.get("custom_task_cd")
        created_by = import_data.get("owner", "System")
        get_class_code = import_data.get("custom_item_class_code")
        item_code = import_data.get("name")
        hscd = import_data.get("custom_hscd")

        if not all([taskCd, get_class_code, item_code]):
            throw(_("Missing required fields: 'custom_task_cd', 'custom_item_class_code', or 'name'."))

        try:
            res = requests.get(
                f"http://0.0.0.0:7000/api/get-item-class-by-name/{get_class_code}/",
                timeout=5
            )
            res.raise_for_status()
            data = res.json()
            itemClsCd = data.get("itemClsCd")

            if not itemClsCd:
                throw(_(f"itemClsCd not found for '{get_class_code}'"))

        except requests.RequestException as e:
            throw(_(f"Error fetching item class code: {e}"))

        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_bhf_id(),
            "taskCd": taskCd,
            "dclDe": "20240426",  
            "importItemList": [
                {
                    "itemSeq": 1,
                    "hsCd": hscd,
                    "itemClsCd": itemClsCd,
                    "itemCd": item_code,
                    "imptItemSttsCd":3,
                    "remark": "remark",
                    "modrNm": "Tim",
                    "modrId": "Tim",
                }
            ]
        }

        print("Payload to send to ZRA:", payload)

        response = self.call_update_import(payload)


        if response.get("resultCd") not in ["000", "001"]:
            frappe.throw(_(f"ZRA Error: {response.get('resultMsg', 'Unknown error')}"))

    
        self.update_stock_master()

    def update_stock(self):
        print("Updating stock...")

    def update_stock_master(self):
        print("Updating stock master...")
