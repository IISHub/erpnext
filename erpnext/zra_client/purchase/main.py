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
            print("Creating purchase with data:", purchase_data)

            vat_map = {
                "StandardRated": "A",
                "MinimumTaxableValue": "B",
                "Exports": "C1",
                "ZeroRatingLocalPurchases": "C2",
                "ZeroRatedByNature": "C3",
                "Exempt": "D",
                "Disbursement": "E",
                "ServiceCharge10%": "F",
                "ReverseVAT": "RVAT"
            }

            # Prepare totals
            total_taxable_amount = 0.0
            total_tax_amount = 0.0
            total_amount = 0.0

            payload = {
                "tpin": self.get_tpin_number(),
                "bhfId": self.get_branch_code(),
                "cisInvcNo": purchase_data.get("name"),
                "regTyCd": "M",
                "pchsTyCd": "N",
                "rcptTyCd": "P",
                "pmtTyCd": "01",
                "pchsSttsCd": "02",
                "cfmDt": frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S"),
                "pchsDt": frappe.utils.now_datetime().strftime("%Y%m%d"),
                "cnclReqDt": "",
                "cnclDt": "",
                "totItemCnt": len(purchase_data.get("items", [])),
                "totTaxblAmt": 0.0,  # to be updated later
                "totTaxAmt": 0.0,    # to be updated later
                "totAmt": 0.0,       # to be updated later
                "remark": "Auto from ERP",
                "regrNm": purchase_data.get("owner"),
                "regrId": purchase_data.get("owner"),
                "modrNm": purchase_data.get("owner"),
                "modrId": purchase_data.get("owner"),
                "itemList": []
            }

            for idx, item in enumerate(purchase_data.get("items", [])):
                print(f"\nProcessing item #{idx + 1}")
                item_code = item.get("item_code")
                item_name = item.get("item_name")
                item_qty = flt(item.get("qty") or 0)
                item_rate = flt(item.get("rate") or 0)
                item_amount = flt(item.get("amount") or 0)

                item_doc = frappe.get_doc("Item", item_code)

                # Get VAT tax type from item custom field, map it, default to A
                vat_doc_cat = item_doc.get("custom_vat", "").strip()
                taxTyCd = vat_map.get(vat_doc_cat, "A")

                # # Throw exception if taxTyCd is not "A"
                # if taxTyCd != "A":
                #     frappe.throw(
                #         f"Invalid tax type for item {item_code} ({item_name}). "
                #         f"Only tax type 'A' is allowed for URCAS purchases, but got '{taxTyCd}'."
                #     )

                # Get packaging unit code via API
                get_packaging_unit = item_doc.custom_packaging_unit_code or "PCS"
                r = requests.get(f"http://0.0.0.0:7000/packaging-unit-code/{get_packaging_unit}/", timeout=5)
                r.raise_for_status()
                packaging_unit_code = r.json().get("code")

                # Get quantity unit code via API
                get_qty_unit = item_doc.custom_units_of_measure or "PCS"
                r = requests.get(f"http://0.0.0.0:7000/unitofmeasure/{get_qty_unit}/", timeout=5)
                r.raise_for_status()
                qty_unit_code = r.json().get("code")

                item_cls_cd = item_doc.get("unspsc_code") or "50102517"

                # Calculate tax amounts
                # Assuming VAT rate 16% as example (replace with actual rate if available)
                vat_rate = 0.16
                taxbl_amt = round(item_amount / (1 + vat_rate), 2)  # Taxable amount (price before VAT)
                tax_amt = round(item_amount - taxbl_amt, 2)         # VAT amount

                # Update totals
                total_taxable_amount += taxbl_amt
                total_tax_amount += tax_amt
                total_amount += item_amount

                payload["itemList"].append({
                    "itemSeq": idx + 1,
                    "itemCd": item_code,
                    "itemClsCd": item_cls_cd,
                    "itemNm": item_name,
                    "bcd": "",
                    "pkgUnitCd": packaging_unit_code,
                    "pkg": 1,
                    "qtyUnitCd": qty_unit_code,
                    "qty": item_qty,
                    "prc": round(item_rate, 2),
                    "splyAmt": round(item_amount, 2),
                    "dcRt": 0.0,
                    "dcAmt": 0.0,
                    "taxTyCd": taxTyCd,
                    "iplCatCd": "",
                    "tlCatCd": "",
                    "exciseCatCd": "",
                    "taxblAmt": taxbl_amt,
                    "vatCatCd": taxTyCd,
                    "iplTaxblAmt": 0.0,
                    "tlTaxblAmt": 0.0,
                    "exciseTaxblAmt": 0.0,
                    "taxAmt": tax_amt,
                    "iplAmt": 0.0,
                    "tlAmt": 0.0,
                    "exciseTxAmt": 0.0,
                    "totAmt": round(item_amount, 2)
                })

            # Update totals in payload
            payload["totTaxblAmt"] = round(total_taxable_amount, 2)
            payload["totTaxAmt"] = round(total_tax_amount, 2)
            payload["totAmt"] = round(total_amount, 2)

            print("Prepared purchase payload:", payload)

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
