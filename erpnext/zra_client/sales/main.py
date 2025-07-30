import time
import json
import random
import asyncio
import frappe
import requests
import threading
from frappe.utils import flt
from datetime import datetime
import frappe
from frappe import get_doc
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.principals.main import Principals

now = datetime.now()

principals_obj = Principals()
class zraSales(ZRAClient):
    def __init__(self):
        super().__init__()

    def get_tpin(self):
        return self.tpin

    def get_branch(self):
        return self.branch_code


    def get_org_sdc_id(self):
        return self.org_sdc_id
    
    def call_create_normal_sale_client(self, payload):
        return self.normal_sale(payload)
    
    def call_create_credit_note_sale_client(self, payload):
        return self.credit_sale(payload)

    def update_stock_after_purchase(self, payload):
        return self.update_stock_after_purchase_view(payload)

    def update_stock_master_after_purchase(self, payload):
        return self.save_stock_master(payload)
    
    def call_debit_sale_client(self, payload):
        return self.sale_debit_note(payload)
    
    def call_export_sale_client(self, payload):
        return self.create_export_sale_zra_client(payload)

    def call_lpo_sale_client(self, payload):
        return self.create_export_sale_zra_client(payload)

    def update_rcptNo_delayed(self, docname, rcpt_no, delay=10):
        def worker():
            try:
                print(f"⏳ Received rcptNo: {rcpt_no}. Waiting {delay} seconds before updating...")
                time.sleep(delay)

                url = "http://0.0.0.0:7000/api/update_rcpt/" 
                payload = {
                    "docname": docname,
                    "rcpt_no": rcpt_no
                }
                headers = {'Content-Type': 'application/json'}
                response = requests.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    print(f"rcptNo '{rcpt_no}' updated for {docname} via API")
                else:
                    print(f"Failed to update rcptNo via API: {response.text}")

            except Exception as e:
                print(f" Error calling API to update rcptNo: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def create_sale_normal(self, sell_order):
        print("Creating sale for order:", sell_order)
        customer_name = sell_order.get("customer") or sell_order.get("customer_name") or ""
        customer_doc = frappe.get_doc("Customer", customer_name)
        customer_tpin = customer_doc.get("custom_customer_tpin")
        cisInvcNo = f'CIS{sell_order.get("name", "001")}-{random.randint(1000, 9999)}'
        created_by = sell_order.get("owner") or "system"
        currency = sell_order.get("currency") or "ZMW"
        totals = {'taxable': 0.0, 'vat': 0.0, 'discount': 0.0, 'gross': 0.0, 'net': 0.0}
        item_list = []

        for i, item in enumerate(sell_order.get("items", []), 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)
            qty = flt(item.get("qty", 1))
            price = flt(item_doc.get("standard_rate", 0))
            gross = flt(qty * price, 4)
            bins = frappe.db.get_all("Bin", filters={"item_code": item_code}, fields=["actual_qty"])
            available_qty = sum(flt(b.get("actual_qty", 0)) for b in bins)

            discount_pct = flt(item.get("discount_percentage", 0))
            discount_amt = flt(gross * discount_pct / 100, 4)
            net = flt(gross - discount_amt, 4)
            taxable = flt(net / 1.16, 4)
            vat = flt(taxable * 0.16, 4)

            totals['gross'] += gross
            totals['discount'] += discount_amt
            totals['net'] += net
            totals['taxable'] += taxable
            totals['vat'] += vat

            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": "50102518",
                "itemNm": item.get("item_name"),
                "bcd": item_doc.get("custom_origin_place_code", ""),
                "pkgUnitCd": "WRAP",
                "pkg": 1,
                "qtyUnitCd": "EA",
                "qty": qty,
                "prc": flt(price, 4),
                "splyAmt": gross,
                "dcRt": discount_pct,
                "dcAmt": discount_amt,
                "vatCatCd": "A",
                "vatTaxblAmt": taxable,
                "vatAmt": vat,
                "totAmt": flt(taxable + vat, 4),
                "exciseTxCatCd": "",
                "tlCatCd": "",
                "iplCatCd": "",
                "exciseTaxblAmt": 0.0,
                "tlTaxblAmt": 0.0,
                "iplTaxblAmt": 0.0,
                "iplAmt": 0.0,
                "tlAmt": 0.0,
                "exciseTxAmt": 0.0
            })

        cash_discount_rate = flt(25.0, 4)
        cash_discount_amt = flt(totals['net'] * cash_discount_rate / 100, 4)
        final_amount = flt(totals['net'] - cash_discount_amt, 4)

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "orgSdcId": "SDC0010002709",
            "cisInvcNo": cisInvcNo,
            "orgInvcNo": 0,
            "Customer":  customer_name,
            "custTpin":  customer_tpin ,
            "salesTyCd": "N",
            "rcptTyCd": "S",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "totItemCnt": len(item_list),
            "taxblAmtA": totals['taxable'],
            "taxblAmtB": 0.0,
            "taxblAmtC1": 0.0,
            "taxblAmtC2": 0.0,
            "taxblAmtC3": 0.0,
            "taxblAmtD": 0.0,
            "taxblAmtRvat": 0.0,
            "taxblAmtE": 0.0,
            "taxblAmtF": 0.0,
            "taxblAmtIpl1": 0.0,
            "taxblAmtIpl2": 0.0,
            "taxblAmtTl": 0.0,
            "taxblAmtEcm": 0.0,
            "taxblAmtExeeg": 0.0,
            "taxblAmtTot": 0.0,
            "taxRtA": 16,
            "taxRtB": 16,
            "taxRtC1": 0,
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "tlAmt": 0.0,
            "taxRtRvat": 16,
            "taxRtE": 0,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtIpl2": 0,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            "taxAmtA": totals['vat'],
            "taxAmtB": 0.0,
            "taxAmtC1": 0.0,
            "taxAmtC2": 0.0,
            "taxAmtC3": 0.0,
            "taxAmtD": 0.0,
            "taxAmtRvat": 0.0,
            "taxAmtE": 0.0,
            "taxAmtF": 0.0,
            "taxAmtIpl1": 0.0,
            "taxAmtIpl2": 0.0,
            "taxAmtTl": 0.0,
            "taxAmtEcm": 0.0,
            "taxAmtExeeg": 0.0,
            "taxAmtTot": 0.0,
            "totTaxblAmt": totals['taxable'],
            "totTaxAmt": totals['vat'],
            "totAmt": final_amount,
            "cashDcRt": cash_discount_rate,
            "cashDcAmt": cash_discount_amt,
            "prchrAcptcYn": "N",
            "remark": "",
            "regrId": created_by,
            "regrNm": created_by,
            "modrId": created_by,
            "modrNm": created_by,
            "saleCtyCd": "1",
            "currencyTyCd": currency,
            "exchangeRt": "1",
            "destnCountryCd": "",
            "dbtRsnCd": "",
            "invcAdjustReason": "",
            "itemList": item_list
        }
        toUseData = payload
        print(" Preparing sale data:", payload)
        response = self.call_create_normal_sale_client(payload)

        if response.get("resultCd") == "000":
            get_rcpt_no = response.get("data", {}).get("rcptNo")
            print(" Stock master updated successfully after sale.")
            doc_name = sell_order.get("name")
            self.update_rcptNo_delayed(docname=doc_name, rcpt_no=get_rcpt_no)

            print("This prints immediately, before delayed print")
            ocrnDt = datetime.now().strftime("%Y%m%d")
            itemsListInToUseData = toUseData.get("itemList", [])

            update_stock_items = []
            update_stock_master_items = []

            for item in itemsListInToUseData:
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
                    "pkg": 1,
                    "totDcAmt": 0,
                })
                update_stock_master_items.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": 12 
                })

            update_stock_payload = {
                "tpin": self.tpin,
                "bhfId": self.branch_code,
                "sarNo": 1,
                "orgSarNo": 0,
                "regTyCd": "M",
                "sarTyCd": "02",
                "ocrnDt": ocrnDt,
                "totItemCnt": toUseData['totItemCnt'],
                "totTaxblAmt": toUseData['totTaxblAmt'],
                "totTaxAmt": toUseData['totTaxAmt'],
                "totAmt": toUseData['totAmt'],
                "regrId": created_by,
                "regrNm": created_by,
                "modrNm": created_by,
                "modrId": created_by,
                "itemList": update_stock_items
            }

            print("📦 Preparing stock update data:", update_stock_payload)

            response = call_update_stock_after_purchase = self.update_stock_after_purchase(update_stock_payload)
            if response.get("resultCd") == "000":
                print("Stock updated successfully after sale.")

                create_update_stock_master_payload = {
                                "tpin": self.tpin,
                                "bhfId": self.branch_code,
                                "regrId": created_by,
                                "regrNm": created_by,
                                "modrNm": created_by,
                                "modrId": created_by,
                                "stockItemList":update_stock_master_items 

                                }

                print(" Preparing stock master update data:", create_update_stock_master_payload)
                response = call_update_stock_master_after_purchase = self.update_stock_master_after_purchase(create_update_stock_master_payload)
         
            frappe.msgprint(f" Sale made successfully: {response.get('resultMsg')}")
        else:
            frappe.throw(f"Purchase save failed: {response.get('resultMsg')}")



    def create_credit_note_payload(self, credit_note_doc):
        now = datetime.now()

        customer_name = credit_note_doc.get("customer") or credit_note_doc.get("customer_name") or ""
        customer_doc = frappe.get_doc("Customer", customer_name) if customer_name else None
        customer_tpin = customer_doc.get("custom_customer_tpin") if customer_doc else ""
        
        cisInvcNo = credit_note_doc.get("name", f"CN-{random.randint(1000,9999)}")
        original_invoice_no = credit_note_doc.get("return_against")

        try:
            original_invoice = frappe.get_doc("Sales Invoice", original_invoice_no)
            orgInvcNo = original_invoice.custom_rcpt_no if hasattr(original_invoice, 'custom_rcpt_no') else None
            if not orgInvcNo:
                frappe.throw("Original invoice receipt number not found")
        except Exception as e:
            frappe.throw(f"Failed to get original invoice: {str(e)}")

        created_by = credit_note_doc.get("owner") or "system"
        currency = credit_note_doc.get("currency") or "ZMW"

        debit_type_map = {
        "01": "Wrong product(s)",
        "02": "Wrong price",
        "03": "Damaged Goods",
        "04": "Wrong Customer Invoiced",
        "05": "Duplicated invoice",
        "06": "Excess supplies",
        "07": "Other (Provide other reason in brief)"
        }

        credit_type_reverse_map = {v: k for k, v in debit_type_map.items()}

        custom_reason_text = credit_note_doc.get("custom_reason", "Other (Provide other reason in brief)")
        custom_reason_code = credit_type_reverse_map.get(custom_reason_text, "07")


        totals = {
            'gross': 0.0,
            'discount': 0.0,
            'net': 0.0,
            'taxable': 0.0,
            'vat': 0.0
        }

        item_list = []
        items = credit_note_doc.get("items", [])
        for i, item in enumerate(items, 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)
            qty = abs(flt(item.get("qty", 1))) 
            price = flt(item.get("rate") or item_doc.get("standard_rate", 0))
            gross = flt(qty * price, 4)

            discount_pct = flt(item.get("discount_percentage", 0))
            discount_amt = flt(gross * discount_pct / 100, 4)
            net = flt(gross - discount_amt, 4)
            taxable = flt(net / 1.16, 4)
            vat = flt(taxable * 0.16, 4)

            totals['gross'] += gross
            totals['discount'] += discount_amt
            totals['net'] += net
            totals['taxable'] += taxable
            totals['vat'] += vat

            original_item = next((x for x in original_invoice.items if x.item_code == item_code), None)
            
            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": "50102518",
                "itemNm": item.get("item_name"),
                "bcd": item_doc.get("custom_origin_place_code", ""),
                "pkgUnitCd": "WRAP",
                "pkg": 1,
                "qtyUnitCd": "EA",
                "qty": qty,
                "prc": flt(price, 4),
                "splyAmt": gross,
                "dcRt": discount_pct,
                "dcAmt": discount_amt,
                "vatCatCd": "A",  # Standard VAT rate
                "vatTaxblAmt": taxable,
                "vatAmt": vat,
                "totAmt": flt(taxable + vat, 4),
                "exciseTxCatCd": "",
                "tlCatCd": "",
                "iplCatCd": "",
                "exciseTaxblAmt": 0.0,
                "tlTaxblAmt": 0.0,
                "iplTaxblAmt": 0.0,
                "iplAmt": 0.0,
                "tlAmt": 0.0,
                "exciseTxAmt": 0.0
            })

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "orgSdcId": "SDC0010002709",
            "cisInvcNo": cisInvcNo,
            "orgInvcNo": orgInvcNo,
            "Customer": customer_name,
            "custTpin": customer_tpin,
            "salesTyCd": "N",
            "rcptTyCd": "R",  
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "rfdRsnCd": custom_reason_text, 
            "totItemCnt": len(item_list),
            
            # Taxable amounts - only populate category A (16%) and zero others
            "taxblAmtA": round(totals['taxable'], 2),
            "taxblAmtB": 0.0,
            "taxblAmtC1": 0.0,
            "taxblAmtC2": 0.0,
            "taxblAmtC3": 0.0,
            "taxblAmtD": 0.0,
            "taxblAmtRvat": 0.0,
            "taxblAmtE": 0.0,
            "taxblAmtF": 0.0,
            "taxblAmtIpl1": 0.0,
            "taxblAmtIpl2": 0.0,
            "taxblAmtTl": 0.0,
            "taxblAmtEcm": 0.0,
            "taxblAmtExeeg": 0.0,
            "taxblAmtTot": 0.0,  # Must be zero when using specific categories
            
            # Tax rates - only populate category A (16%) and zero others
            "taxRtA": 16,
            "taxRtB": 0,
            "taxRtC1": 0,
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "tlAmt": 0.0,
            "taxRtRvat": 0,
            "taxRtE": 0,
            "taxRtF": 0,
            "taxRtIpl1": 0,
            "taxRtIpl2": 0,
            "taxRtTl": 0,
            "taxRtEcm": 0,
            "taxRtExeeg": 0,
            "taxRtTot": 0,  # Must be zero when using specific rates
            
            # Tax amounts - only populate category A (16%) and zero others
            "taxAmtA": round(totals['vat'], 2),
            "taxAmtB": 0.0,
            "taxAmtC1": 0.0,
            "taxAmtC2": 0.0,
            "taxAmtC3": 0.0,
            "taxAmtD": 0.0,
            "taxAmtRvat": 0.0,
            "taxAmtE": 0.0,
            "taxAmtF": 0.0,
            "taxAmtIpl1": 0.0,
            "taxAmtIpl2": 0.0,
            "taxAmtTl": 0.0,
            "taxAmtEcm": 0.0,
            "taxAmtExeeg": 0.0,
            "taxAmtTot": 0.0,  # Must be zero when using specific categories
            
            # Totals
            "totTaxblAmt": round(totals['taxable'], 2),
            "totTaxAmt": round(totals['vat'], 2),
            "totAmt": round(abs(totals['net']), 2),
            
            # Other fields
            "cashDcRt": 0.0,
            "cashDcAmt": 0.0,
            "prchrAcptcYn": "N",
            "remark": credit_note_doc.get("remarks") or "",
            "regrId": created_by,
            "regrNm": created_by,
            "modrId": created_by,
            "modrNm": created_by,
            "saleCtyCd": "1",
            "currencyTyCd": currency,
            "exchangeRt": "1",
            "destnCountryCd": "",
            "dbtRsnCd": "",
            "invcAdjustReason": "",
            "itemList": item_list
        }
        if not abs(payload["totAmt"] - (payload["totTaxblAmt"] + payload["totTaxAmt"])) < 0.01:
            frappe.throw("Amount validation failed: Total amount must equal taxable amount plus tax amount")

        print(payload)
        response = self.call_create_credit_note_sale_client(payload)

        if response.get("resultCd") == "000":
            if response.get("data") and response["data"].get("rcptNo"):
                rcpt_no = response["data"]["rcptNo"]
                doc_name = credit_note_doc.get("name")
                self.update_rcptNo_delayed(docname=doc_name, rcpt_no=rcpt_no)
                frappe.msgprint(f"Credit Note created successfully. Receipt No: {rcpt_no}")
            else:
                frappe.msgprint("Credit Note created successfully but no receipt number was returned")

            ocrnDt = datetime.now().strftime("%Y%m%d")
            update_stock_item = []
            update_stock_master = []

            toUseItem = item_list
            for item in toUseItem:
                update_stock_item.append({
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
                    "pkg": 1,
                    "totDcAmt": 0,
                })
                update_stock_master.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": 12 
                })

            update_stock_payload = {
                "tpin": self.get_tpin(),
                "bhfId": self.get_branch(),
                "sarNo": 1,
                "orgSarNo": 0,
                "regTyCd": "M",
                "sarTyCd": "02",
                "ocrnDt": ocrnDt,
                "totItemCnt": payload["totItemCnt"],
                "totTaxblAmt": payload["totTaxblAmt"],
                "totTaxAmt": payload["totTaxAmt"],
                "totAmt": payload["totAmt"],
                "regrId": created_by,
                "regrNm": created_by,
                "modrNm": created_by,
                "modrId": created_by,
                "itemList": update_stock_item
            }

            call_update_stock_after_purchase = self.update_stock_after_purchase(update_stock_payload)
            print("update stock response", response)
            if call_update_stock_after_purchase.get("resultCd") == "000":
                update_stock_master_payload = {
                    "tpin": self.tpin,
                    "bhfId": self.branch_code,
                    "regrId": created_by,
                    "regrNm": created_by,
                    "modrNm": created_by,
                    "modrId": created_by,
                    "stockItemList": update_stock_master
                }

                call_update_stock_master_after_purchase = self.update_stock_master_after_purchase(update_stock_master_payload)
                print("update stock master response")
                print(call_update_stock_master_after_purchase)
                
            
        else:
            error_msg = response.get("resultMsg", "Unknown error occurred")
            frappe.throw(f"Failed to create Credit Note: {error_msg}")




    def debit_sale(self, debit_data):
        created_by = debit_data.get("owner") or "system"
        name = (debit_data.get("name") or "") + str(random.randint(1000, 9999))
        get_original_rcpt_no = debit_data.get("return_against")

        if not get_original_rcpt_no:
            frappe.throw("Sale cancellation failed: 'name' field is required in credit note.")

        try:
            response = requests.get(
                "http://0.0.0.0:7000/api/get-rcpt-no/",
                params={"docname": get_original_rcpt_no}
            )
            response.raise_for_status()
            data = response.json()
            orgInvcNo = data.get("custom_rcpt_no")
            if not orgInvcNo:
                frappe.throw("Sale cancellation failed: 'custom_rcpt_no' not found in API response.")
        except requests.RequestException as e:
            frappe.throw(f"Sale cancellation failed: Request error - {str(e)}")
        except Exception as e:
            frappe.throw(f"Sale cancellation failed: {str(e)}")

        current_dt_full = datetime.now().strftime("%Y%m%d%H%M%S")

        total_taxable_amt = 0.0
        total_vat_amt = 0.0
        total_excise_taxable_amt = 0.0
        total_excise_tax_amt = 0.0
        total_tot_amt = 0.0

        debit_type_map = {
        "01": "Wrong product(s)",
        "02": "Wrong price",
        "03": "Damaged Goods",
        "04": "Wrong Customer Invoiced",
        "05": "Duplicated invoice",
        "06": "Excess supplies",
        "07": "Other (Provide other reason in brief)"
    }

        credit_type_reverse_map = {v: k for k, v in debit_type_map.items()}

        custom_reason_text = debit_data.get("custom_reason", "Other (Provide other reason in brief)")
        custom_reason_code = credit_type_reverse_map.get(custom_reason_text, "07")

        item_list = []
        for idx, item in enumerate(debit_data.get("items", []), start=1):
            qty = item.get("qty", 1)
            price = item.get("price", 0)
            dcAmt = item.get("dcAmt", 0)
            isrccAmt = item.get("isrcAmt", 0)
            exciseTaxblAmt = item.get("exciseTaxblAmt", 0)
            exciseTxAmt = item.get("exciseTxAmt", 0)

            vat_rate = item.get("vatRate", 16)
            splyAmt = round(qty * price, 3)

            vatTaxblAmt = round(item.get("vatTaxblAmt", splyAmt), 3)
            vatAmt = round(item.get("vatAmt", vatTaxblAmt * vat_rate / 100), 3)

            totAmt = round(splyAmt + vatAmt + exciseTxAmt - dcAmt - isrccAmt, 3)

            total_taxable_amt += vatTaxblAmt
            total_vat_amt += vatAmt
            total_excise_taxable_amt += exciseTaxblAmt
            total_excise_tax_amt += exciseTxAmt
            total_tot_amt += totAmt

            item_list.append({
                "itemSeq": idx,
                "itemCd": item.get("item_code", ""),
                "itemClsCd": item.get("itemClsCd", "A"),
                "itemNm": item.get("item_name", ""),
                "bcd": item.get("barcode", ""),
                "pkgUnitCd": item.get("pkgUnitCd", "P/KG"),
                "pkg": item.get("pkg", 0),
                "qtyUnitCd": item.get("qtyUnitCd", "U"),
                "qty": qty,
                "prc": price,
                "splyAmt": splyAmt,
                "dcRt": item.get("dcRt", 0),
                "dcAmt": dcAmt,
                "isrccCd": item.get("isrccCd", ""),
                "isrccNm": item.get("isrccNm", ""),
                "isrcRt": item.get("isrcRt", 0),
                "isrcAmt": isrccAmt,
                "vatCatCd": item.get("vatCatCd", "A"),
                "exciseTxCatCd": item.get("exciseTxCatCd", ""),
                "vatTaxblAmt": vatTaxblAmt,
                "exciseTaxblAmt": exciseTaxblAmt,
                "vatAmt": vatAmt,
                "exciseTxAmt": exciseTxAmt,
                "totAmt": totAmt
            })

        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_branch(),
            "orgInvcNo": orgInvcNo,
            "cisInvcNo":  name,
            "custTpin": "1000724543",
            "custNm": "Customer Name\n1",
            "salesTyCd": "N",
            "rcptTyCd": "D",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": current_dt_full,
            "salesDt": current_dt_full[:8],
            "stockRlsDt": current_dt_full,
            "cnclReqDt": current_dt_full,
            "cnclDt": current_dt_full,
            "rfdDt": current_dt_full,
            "totItemCnt": len(item_list),
            "taxblAmtA": round(total_taxable_amt, 3),
            "taxAmtA": round(total_vat_amt, 3),
            "totTaxblAmt": round(total_taxable_amt, 3),
            "totTaxAmt": round(total_vat_amt, 3),
            "totAmt": round(total_tot_amt, 3),
            "cashDcRt": 0,
            "cashDcAmt": 0,
            "taxRtA": 16,
            "taxRtRvat": 16,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            "taxAmtTot": 0,
            "prchrAcptcYn": "N",
            "remark": "",
            "regrId": created_by,
            "regrNm": created_by,
            "modrId": created_by,
            "modrNm": created_by,
            "saleCtyCd": "1",
            "currencyTyCd": "ZMW",
            "exchangeRt": "1",
            "destnCountryCd": "",
            "dbtRsnCd":  custom_reason_code,
            "invcAdjustReason":  custom_reason_text,
            "itemList": item_list
        }

        print(payload)

        response = self.call_debit_sale_client(payload)
        if response.get("resultCd") == "000":
            if response.get("data") and response["data"].get("rcptNo"):
                rcpt_no = response["data"]["rcptNo"]
                doc_name = debit_data.get("name")
                self.update_rcptNo_delayed(docname=doc_name, rcpt_no=rcpt_no)
                frappe.msgprint(f"Credit Note created successfully. Receipt No: {rcpt_no}")
            else:
                frappe.msgprint("Credit Note created successfully but no receipt number was returned")

            ocrnDt = datetime.now().strftime("%Y%m%d")
            update_stock_item = []
            update_stock_master = []

            toUseItem = item_list
            for item in toUseItem:
                update_stock_item.append({
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
                    "pkg": 1,
                    "totDcAmt": 0,
                })
                update_stock_master.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": 12 
                })

            update_stock_payload = {
                "tpin": self.get_tpin(),
                "bhfId": self.get_branch(),
                "sarNo": 1,
                "orgSarNo": 0,
                "regTyCd": "M",
                "sarTyCd": "02",
                "ocrnDt": ocrnDt,
                "totItemCnt": payload["totItemCnt"],
                "totTaxblAmt": payload["totTaxblAmt"],
                "totTaxAmt": payload["totTaxAmt"],
                "totAmt": payload["totAmt"],
                "regrId": created_by,
                "regrNm": created_by,
                "modrNm": created_by,
                "modrId": created_by,
                "itemList": update_stock_item
            }

            call_update_stock_after_purchase = self.update_stock_after_purchase(update_stock_payload)
            print("update stock response", response)
            if call_update_stock_after_purchase.get("resultCd") == "000":
                update_stock_master_payload = {
                    "tpin": self.tpin,
                    "bhfId": self.branch_code,
                    "regrId": created_by,
                    "regrNm": created_by,
                    "modrNm": created_by,
                    "modrId": created_by,
                    "stockItemList": update_stock_master
                }

                call_update_stock_master_after_purchase = self.update_stock_master_after_purchase(update_stock_master_payload)
                print("update stock master response")
                print(call_update_stock_master_after_purchase)

        else:
            error_msg = response.get("resultMsg", "Unknown error occurred")
            frappe.throw(f"Failed to create Debit Note: {error_msg}")
    
    def create_export_sale_invoice(self, import_data):
        print("Creating import sale:", import_data)
        customer_name = import_data.get("customer") or import_data.get("customer_name") or ""
        customer_doc = frappe.get_doc("Customer", customer_name)
        customer_tpin = customer_doc.get("custom_customer_tpin")
        cisInvcNo = f'CIS{import_data.get("name", "001")}-{random.randint(1000, 9999)}'
        created_by = import_data.get("owner") or "system"
        currency = import_data.get("currency") or "ZMW"
        totals = {'taxable': 0.0, 'vat': 0.0, 'discount': 0.0, 'gross': 0.0, 'net': 0.0}
        item_list = []

        for i, item in enumerate(import_data.get("items", []), 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)
            qty = flt(item.get("qty", 1))
            price = flt(item_doc.get("standard_rate", 0))
            gross = flt(qty * price, 4)
            bins = frappe.db.get_all("Bin", filters={"item_code": item_code}, fields=["actual_qty"])
            available_qty = sum(flt(b.get("actual_qty", 0)) for b in bins)

            discount_pct = flt(item.get("discount_percentage", 0))
            discount_amt = flt(gross * discount_pct / 100, 4)
            net = flt(gross - discount_amt, 4)
            taxable = flt(net, 4)  # For exports, taxable amount is full net (0% VAT)
            vat = 0.0  # VAT is 0% for exports

            totals['gross'] += gross
            totals['discount'] += discount_amt
            totals['net'] += net
            totals['taxable'] += taxable
            totals['vat'] += vat

            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": "50102518",
                "itemNm": item.get("item_name"),
                "bcd": item_doc.get("custom_origin_place_code", ""),
                "pkgUnitCd": "WRAP",
                "pkg": 1,
                "qtyUnitCd": "EA",
                "qty": qty,
                "prc": flt(price, 4),
                "splyAmt": gross,
                "dcRt": discount_pct,
                "dcAmt": discount_amt,
                "vatCatCd": "C1",  # Changed from "A" to "C1" (Exports)
                "vatTaxblAmt": taxable,
                "vatAmt": vat,
                "totAmt": flt(taxable + vat, 4),
                "exciseTxCatCd": "",
                "tlCatCd": "",
                "iplCatCd": "",
                "exciseTaxblAmt": 0.0,
                "tlTaxblAmt": 0.0,
                "iplTaxblAmt": 0.0,
                "iplAmt": 0.0,
                "tlAmt": 0.0,
                "exciseTxAmt": 0.0
            })

        cash_discount_rate = flt(25.0, 4)
        cash_discount_amt = flt(totals['net'] * cash_discount_rate / 100, 4)
        final_amount = flt(totals['net'] - cash_discount_amt, 4)

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "orgSdcId": "SDC0010002709",
            "cisInvcNo": cisInvcNo,
            "orgInvcNo": 0,
            "custTpin": customer_tpin,
            "custNm": customer_name,
            "salesTyCd": "N",
            "rcptTyCd": "S",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "totItemCnt": len(item_list),
            "taxblAmtA": 0.0, 
            "taxblAmtB": 0.0,
            "taxblAmtC1": totals['taxable'], 
            "taxblAmtC2": 0.0,
            "taxblAmtC3": 0.0,
            "taxblAmtD": 0.0,
            "taxblAmtRvat": 0.0,
            "taxblAmtE": 0.0,
            "taxblAmtF": 0.0,
            "taxblAmtIpl1": 0.0,
            "taxblAmtIpl2": 0.0,
            "taxblAmtTl": 0.0,
            "taxblAmtEcm": 0.0,
            "taxblAmtExeeg": 0.0,
            "taxblAmtTot": 0.0,
            "taxRtA": 16,
            "taxRtB": 16,
            "taxRtC1": 0, 
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "tlAmt": 0.0,
            "taxRtRvat": 16,
            "taxRtE": 0,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtIpl2": 0,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            "taxAmtA": 0.0,  # No VAT for exports
            "taxAmtB": 0.0,
            "taxAmtC1": 0.0,  # VAT is 0 for exports
            "taxAmtC2": 0.0,
            "taxAmtC3": 0.0,
            "taxAmtD": 0.0,
            "taxAmtRvat": 0.0,
            "taxAmtE": 0.0,
            "taxAmtF": 0.0,
            "taxAmtIpl1": 0.0,
            "taxAmtIpl2": 0.0,
            "taxAmtTl": 0.0,
            "taxAmtEcm": 0.0,
            "taxAmtExeeg": 0.0,
            "taxAmtTot": 0.0,
            "totTaxblAmt": totals['taxable'],
            "totTaxAmt": 0.0,  
            "totAmt": final_amount,
            "cashDcRt": cash_discount_rate,
            "cashDcAmt": cash_discount_amt,
            "prchrAcptcYn": "N",
            "remark": "",
            "regrId": created_by,
            "regrNm": created_by,
            "modrId": created_by,
            "modrNm": created_by,
            "saleCtyCd": "1",
            "currencyTyCd": currency,
            "exchangeRt": "1",
            "destnCountryCd": "ZM", 
            "dbtRsnCd": "",
            "invcAdjustReason": "",
            "itemList": item_list
        }

        self.call_export_sale_client(payload)

    def create_lop_sale(self, lpo_data):
        cnclReqDt = datetime.now().strftime("%Y%m%d%H%M%S")
        cfmDt = datetime.now().strftime("%Y%m%d%I%M%S")
        salesDt = datetime.now().strftime("%Y%m%d")
        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_branch(),
            "orgInvcNo": 0,
            "cisInvcNo": "CIS001-22",
            "custTpin": "2000000000",
            "custNm": "LPO CUSTOMER",
            "salesTyCd": "N",
            "rcptTyCd": "S",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": cfmDt,
            "salesDt": salesDt,
            "totItemCnt": 1,
            "taxblAmtA": 0.0,
            "taxblAmtB": 0.0,
            "taxblAmtC1": 0.0,
            "taxblAmtC2": 86.2069,
            "taxblAmtC3": 0.0,
            "taxblAmtD": 0.0,
            "taxblAmtRvat": 0.0,
            "taxblAmtE": 0.0,
            "taxblAmtF": 0.0,
            "taxblAmtIpl1": 0,
            "taxblAmtIpl2": 0,
            "taxblAmtTl": 0,
            "taxblAmtEcm": 0,
            "taxblAmtExeeg": 0.0,
            "taxblAmtTot": 0.0,
            "taxRtA": 16,
            "taxRtB": 16,
            "taxRtC1": 0,
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "tlAmt": 0.0,
            "taxRtRvat": 16,
            "taxRtE": 0,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtIpl2": 0,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            "taxAmtA": 0.0,
            "taxAmtB": 0.0,
            "taxAmtC1": 0.0,
            "taxAmtC2": 0.0,
            "taxAmtC3": 0.0,
            "taxAmtD": 0.0,
            "taxAmtRvat": 0.0,
            "taxAmtE": 0.0,
            "taxAmtF": 0.0,
            "taxAmtIpl1": 0.0,
            "taxAmtIpl2": 0.0,
            "taxAmtTl": 0.0,
            "taxAmtEcm": 0.0,
            "taxAmtExeeg": 0.0,
            "taxAmtTot": 0.0,
            "totTaxblAmt": 86.2069,
            "totTaxAmt": 0,
            "cashDcRt": 0,
            "cashDcAmt": 0,
            "totAmt": 86.2069,
            "prchrAcptcYn": "N",
            "remark": "",
            "regrId": "admin",
            "regrNm": "admin",
            "modrId": "admin",
            "modrNm": "admin",
            "saleCtyCd": "1",
            "lpoNumber": "109506957",
            "currencyTyCd": "ZMW",
            "exchangeRt": "1",
            "destnCountryCd": "",
            "dbtRsnCd": "",
            "invcAdjustReason": "",
            "itemList": [
                {
                "itemSeq": 1,
                "itemCd": "20056",
                "itemClsCd": "50102518",
                "itemNm": "Item One",
                "bcd": "",
                "pkgUnitCd": "BA",
                "pkg": 0.0,
                "qtyUnitCd": "BE",
                "qty": 1.0,
                "prc": 86.2069,
                "splyAmt": 86.2069,
                "dcRt": 0,
                "dcAmt": 0.0,
                "vatCatCd": "C2",
                "vatTaxblAmt": 86.2069,
                "vatAmt": 0,
                "totAmt": 86.2069
                }
            ]
            }
        self.call_lpo_sale_client(payload)

    def create_rvat_with_agent(self, sell_data):
        response = principals_obj.get_principal()
        print(response)
        




		