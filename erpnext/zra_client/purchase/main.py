import frappe
import requests
from datetime import datetime
from erpnext.zra_client.main import ZRAClient


class zraPurchase(ZRAClient):
    def __init__(self):
        super().__init__()

    def get_tpin_number(self):
        return self.tpin

    def get_branch_code(self):
        return self.branch_code

    def purchase_item_local(self, purchase_invoice_name):
        url = "http://127.0.0.1:7000/api/supplier-invoices/"
        params = {"invoice_name": purchase_invoice_name}
        try:
            req = requests.get(url=url,  params=params, timeout=10)
            req.raise_for_status()  
            response = req.json()  
            return response 

        except requests.exceptions.HTTPError as http_err:
            frappe.throw("Error occurred. Try Again")

        except requests.exceptions.ConnectionError as conn_err:
            frappe.throw("Connection error occurred")

        except requests.exceptions.Timeout as timeout_err:
            frappe.throw("Request timed out")

        except requests.exceptions.RequestException as req_err:
            frappe.throw("Request error")

        except ValueError as json_err:
            frappe.throw("An unexpected error occurred")

        except Exception as e:
            frappe.throw("An unexpected error occurred")
          





    def create_purchase(self, purchase_data):
        print(purchase_data)
        name = purchase_data.get("name")
        modified_by = purchase_data.get("modified_by")
        purchase_api_data = self.purchase_item_local(name)

        if not purchase_api_data:
            frappe.throw("No data returned from local purchase API.")

        data = purchase_api_data[0]
        items = data.get("item_list", [])

        item_list = []
        for item in items:
            item_list.append({
                "itemSeq": item.get("item_seq"),
                "itemCd": item.get("item_cd"),
                "itemClsCd": item.get("item_cls_cd"),
                "itemNm": item.get("item_nm"),
                "pkgUnitCd": item.get("pkg_unit_cd"),
                "pkg": float(item.get("pkg", 0)),
                "qtyUnitCd": "KG",
                "qty": float(item.get("qty")),
                "prc": float(item.get("prc")),
                "splyAmt": float(item.get("sply_amt")),
                "dcRt": float(item.get("dc_rt")),
                "dcAmt": float(item.get("dc_amt")),
                "taxTyCd": "B", 
                "iplCatCd": item.get("ipl_cat_cd") or "",
                "tlCatCd": item.get("tl_cat_cd") or "",
                "exciseCatCd": item.get("excise_tx_cat_cd") or "",
                "taxblAmt": float(item.get("taxbl_amt")),
                "vatCatCd": item.get("vat_cat_cd"),
                "iplTaxblAmt": float(item.get("ipl_taxbl_amt")),
                "tlTaxblAmt": float(item.get("tl_taxbl_amt")),
                "exciseTaxblAmt": float(item.get("excise_taxbl_amt")),
                "taxAmt": float(item.get("vat_amt")),
                "iplAmt": float(item.get("ipl_amt")),
                "tlAmt": float(item.get("tl_amt")),
                "exciseTxAmt": float(item.get("excise_tx_amt")),
                "totAmt": float(item.get("tot_amt")),
            })

        payload = {
            "tpin": self.get_tpin_number(),
            "bhfId": self.get_branch_code(),
            "cisInvcNo": data.get("invoice_name", "N/A"),
            "regTyCd": "M",
            "pchsTyCd": "N",
            "rcptTyCd": "P",
            "pmtTyCd": data.get("pmt_ty_cd"),
            "pchsSttsCd": "02",
            "cfmDt": datetime.strptime(data.get("cfm_dt"), "%Y-%m-%dT%H:%M:%SZ").strftime("%Y%m%d%H%M%S"),
            "pchsDt": data.get("sales_dt"),
            "cnclReqDt": "",
            "cnclDt": "",
            "totItemCnt": data.get("tot_item_cnt"),
            "totTaxblAmt": float(data.get("tot_taxbl_amt")),
            "totTaxAmt": float(data.get("tot_tax_amt")),
            "totAmt": float(data.get("tot_amt")),
            "remark": data.get("remark") or "Purchase import",
            "regrNm": modified_by ,
            "regrId": modified_by ,
            "modrNm": modified_by ,
            "modrId": modified_by ,
            "itemList": item_list
        }
        print(payload)
        response_data = self.save_purchase_manually(payload)

        if response_data.get("resultCd") == "000":
            frappe.msgprint(f"Purchase saved successfully: {response_data.get('resultMsg')}")

            ocrnDt = datetime.now().strftime("%Y%m%d")
            stock_items = []
            stock_master_items = []

            for item in item_list:
                stock_items.append({
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
                    "pkg": item.get("pkg"),
                    "totDcAmt": item.get("dcAmt"),
                })

                stock_master_items.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": 12 
                })

            self.run_stock_update_in_background(
                {
                    "tpin": self.get_tpin_number(),
                    "bhfId": self.get_branch_code(),
                    "sarNo": 1,
                    "orgSarNo": 0,
                    "regTyCd": "M",
                    "sarTyCd": "02",
                    "ocrnDt": ocrnDt,
                    "totItemCnt": payload["totItemCnt"],
                    "totTaxblAmt": payload["totTaxblAmt"],
                    "totTaxAmt": payload["totTaxAmt"],
                    "totAmt": payload["totAmt"],
                    "regrId": modified_by ,
                    "regrNm": modified_by ,
                    "modrNm": modified_by ,
                    "modrId": modified_by ,
                    "itemList": stock_items
                },
                {
                    "tpin": self.get_tpin_number(),
                    "bhfId": self.get_branch_code(),
                    "regrId": modified_by ,
                    "regrNm": modified_by ,
                    "modrNm": modified_by ,
                    "modrId": modified_by ,
                    "stockItemList": stock_master_items
                },
                purchase_data.get("owner")
            )

        else:
            error_msg = response_data.get("resultMsg", "Unknown error")
            frappe.throw(f"Purchase save failed: {error_msg}")

        purchase_data["purchase_payload"] = frappe.as_json(payload)
