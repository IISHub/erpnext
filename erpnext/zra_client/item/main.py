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

    def get_tpin(self):
        return self.tpin

    def get_branch(self):
        return self.branch_code

    def create_item_helper(self, payload):
        self.create_item_zra(payload)

    def create_item(self, item_data):
        
        return item_data
    
    def update_item(self):
        return 
    
    

   
