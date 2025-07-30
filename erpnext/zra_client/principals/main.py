from erpnext.zra_client.main import ZRAClient

class Principals(ZRAClient):
    def __init__(self):
        super().__init__()

    def get_tpin(self):
        return self.tpin 

    def get_branch_code(self):
        return self.branch_code 
    
    def call_get_principals_helper(self, payload):
        return self.get_principals_zra_client(payload)


    def get_principal(self):
        payload = {
                "tpin": self.get_tpin(),
                "bhfId": self.get_branch_code(),
                "lastReqDt":"20250730135021"
                }
        
        self.call_get_principals_helper(payload)




