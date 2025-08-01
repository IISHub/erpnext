import requests
from erpnext.zra_client.main import ZRAClient
import frappe
from frappe.utils import flt
from datetime import datetime

# Get today's date
today = datetime.today()

# Format it as YYYYMMDD
ocrnDt = today.strftime("%Y%m%d")
class Stock(ZRAClient):
    def __init__(self):
        super().__init__()

    def get_tpin(self):
        return self.tpin

    def get_branch_code(self):
        return self.branch_code

    def create_stock(self, stock_data):
        created_by = stock_data.get("owner")
        print("Creating stock with data:", stock_data)
        if not isinstance(stock_data, dict):
            frappe.throw("Invalid input: stock_data must be a dictionary")

        total_taxable = 0
        total_tax = 0
        total_amount = 0
        ocrnDt = datetime.now().strftime("%Y%m%d")


        items = stock_data.get("items", [])
        if not items:
            frappe.throw("No items found in stock_data")

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "sarNo": 1,
            "orgSarNo": 0,
            "regTyCd": "M",
            "custTpin": None,
            "custNm": None,
            "custBhfId": None,
            "sarTyCd": "02",
            "ocrnDt": ocrnDt,
            "totItemCnt": len(items),
            "remark": stock_data.get("remarks"),
            "regrId": stock_data.get("owner"),
            "regrNm": stock_data.get("owner"),
            "modrNm": stock_data.get("owner"),
            "modrId": stock_data.get("owner"),
            "itemList": []
        }

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
        
        print("looping items")
        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                frappe.log_error(f"Invalid item format. Expected dict, got {type(item)}")
                continue

            item_code = item.get("item_code")
            if not item_code:
                frappe.log_error("Missing item_code in Stock Entry items")
                continue

            try:
                item_doc = frappe.get_doc("Item", item_code)
            except frappe.DoesNotExistError:
                frappe.log_error(f"Item not found: {item_code}")
                continue

            qty = flt(item.get("qty", 0))
            valuation_rate = flt(item.get("valuation_rate", 0))

            if not valuation_rate:
                valuation_rate = flt(item_doc.get("custom_default_unit_price", 0))

            if valuation_rate == 0:
                if not item.get("allow_zero_valuation_rate", False):
                    frappe.throw(f"Valuation Rate missing for item: {item_code}. "
                                 "Set valuation rate or enable 'Allow Zero Valuation Rate'.")
                else:
                    frappe.log_error(f"Zero valuation rate allowed for item: {item_code}")

            custom_vat = (item_doc.get("custom_vat") or "").replace(" ", "").strip()
            vatCatCd = vat_code_map.get(custom_vat, "A")
            vat_rate = 0.16 if vatCatCd == "A" else 0

            supply_amount = round(qty * valuation_rate, 2)
            taxable_amount = supply_amount if vatCatCd == "A" else 0
            tax_amount = round(taxable_amount * vat_rate, 2)
            total_item_amount = supply_amount + tax_amount

            total_taxable += taxable_amount
            total_tax += tax_amount
            total_amount += total_item_amount
            packaging_unit_name = item_doc.get("custom_packaging_unit_code") or "PKG"
            unit_of_measure_name = item_doc.get("custom_units_of_measure") or "EA"
            print(packaging_unit_name, unit_of_measure_name)

            payload["itemList"].append({
                "itemSeq": idx,
                "itemCd": item_code,
                "itemClsCd": item_doc.get("item_class_code") or "NA",
                "itemNm": item_doc.item_name,
                "pkgUnitCd": self.get_packaging_unit(packaging_unit_name),
                "qtyUnitCd": self.get_units_of_measure(unit_of_measure_name),
                "vatCatCd": vatCatCd,
                "qty": qty,
                "prc": valuation_rate,
                "splyAmt": supply_amount,
                "taxblAmt": taxable_amount,
                "taxAmt": tax_amount,
                "totAmt": total_item_amount,
                "totDcAmt": 0,
                "pkg": 1
            })

            payload.update({
                "totTaxblAmt": total_taxable,
                "totTaxAmt": total_tax,
                "totAmt": total_amount
            })

            update_stock_master_payload = {
                "tpin": payload.get("tpin"),
                "regrId": payload.get("regrId"),
                "regrNm": payload.get("regrNm"),
                "bhfId": payload.get("bhfId"),
                "modrId": payload.get("modrId"),
                "modrNm": payload.get("modrNm"),
                "stockItemList": [
                    {
                        "itemCd": payload["itemList"][0]["itemCd"],
                        "rsdQty": 12
                    }
                ]
            }

            print("update stock: ", payload, "stock master payload: ", update_stock_master_payload)
            self.run_stock_update_in_background(payload, update_stock_master_payload, created_by)
            # frappe.throw(f"Error")

