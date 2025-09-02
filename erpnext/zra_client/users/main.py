from erpnext.zra_client.main import ZRAClient
import frappe
class ZRAUsers(ZRAClient):
    def __init__(self):
        super().__init__()

    def format_data(self, data):
        print(f"ZRA User Data: {data}")
        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.branch_code(),
            "userId": "SMART USER",
            "userNm": "SMART USER",
            "adrs": "Smart Invoice Street 1234",
            "useYn": "Y",
            "regrNm": "Admin",
            "regrId": "Admin",
            "modrNm": "Admin",
            "modrId": "Admin"
            }

        print(f"ZRA User Payload: {payload}")
        frappe.throw("ZRA User Creation is not allowed at the moment.")
        return payload
