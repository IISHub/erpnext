import time
import json
import random
import asyncio
from urllib.parse import quote
import frappe
import requests
import threading
from frappe.utils import flt
from datetime import datetime
import frappe
import threading
from frappe import get_doc
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.principals.main import Principals

now = datetime.now()

principals_obj = Principals()
class zraSales(ZRAClient):
    def __init__(self):
        super().__init__()

    def run_stock_update_in_background(self, update_stock_payload, update_stock_master_items, created_by):
        def background_task():
            try:
                response = self.update_stock_after_purchase(update_stock_payload)
                if response.get("resultCd") == "000":
                    print("Stock updated successfully after sale.")

                    create_update_stock_master_payload = {
                        "tpin": self.tpin,
                        "bhfId": self.branch_code,
                        "regrId": created_by,
                        "regrNm": created_by,
                        "modrNm": created_by,
                        "modrId": created_by,
                        "stockItemList": update_stock_master_items
                    }

                    print("Preparing stock master update data:", create_update_stock_master_payload)
                    response = self.update_stock_master_after_purchase(create_update_stock_master_payload)
                    if response.get("resultCd") == "000":
                        print("Stock master updated successfully after sale.")
                    else:
                        print(f"Failed to update stock master: {response.get('resultMsg')}")
                else:
                    print(f"Failed to update stock: {response.get('resultMsg')}")
            except Exception as e:
                print(f"Exception in background stock update task: {e}")

        thread = threading.Thread(target=background_task)
        thread.daemon = True  
        thread.start()

    def get_tpin(self):
        return self.tpin
    

    def get_branch(self):
        return self.branch_code

    def call_get_principal(self, payload):
        return self.get_principals_zra_client(payload)


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
        return self.create_lpo_sale_zra_client(payload)

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
        
        # Initialize category totals based on ZRA structure
        category_totals = {
            'A': {'taxable': 0.0, 'tax': 0.0},
            'B': {'taxable': 0.0, 'tax': 0.0},
            'C1': {'taxable': 0.0, 'tax': 0.0},
            'C2': {'taxable': 0.0, 'tax': 0.0},
            'C3': {'taxable': 0.0, 'tax': 0.0},
            'D': {'taxable': 0.0, 'tax': 0.0},
            'RVAT': {'taxable': 0.0, 'tax': 0.0},
            'E': {'taxable': 0.0, 'tax': 0.0},
            'F': {'taxable': 0.0, 'tax': 0.0}
        }
        
        special_tax_totals = {
            'ipl1': {'taxable': 0.0, 'tax': 0.0},
            'ipl2': {'taxable': 0.0, 'tax': 0.0},
            'tl': {'taxable': 0.0, 'tax': 0.0},
            'ecm': {'taxable': 0.0, 'tax': 0.0},
            'exeeg': {'taxable': 0.0, 'tax': 0.0}
        }
        
        totals = {'gross': 0.0, 'discount': 0.0, 'net': 0.0}
        item_list = []

        for i, item in enumerate(sell_order.get("items", []), 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)
            packaging_unit = item_doc.get("custom_packaging_unit_code", "").strip()
            qty = flt(item.get("qty", 1))
            price = flt(item_doc.get("standard_rate", 0))
            gross = flt(qty * price, 4)

            # Retrieve custom fields from item_doc
            ipl_doc_cat = item_doc.get("custom_ipl_category_code", "").strip()
            excise_doc_cat = item_doc.get("custom_excise_tax_category_code", "").strip()
            tl_doc_cat = item_doc.get("custom_tourism_levy", "").strip()
            vat_doc_cat = item_doc.get("custom_vat", "").strip()

            # VAT Mapping
            vat_map = {
                "StandardRated": "A", "MinimumTaxableValue": "B", "Exports": "C1",
                "ZeroRatingLocalPurchases": "C2", "ZeroRatedByNature": "C3",
                "Exempt": "D", "Disbursement": "E", "ServiceCharge10%": "F", "ReverseVAT": "RVAT"
            }
            vatCatCd = vat_map.get(vat_doc_cat, "D")


            # Excise Tax Mapping
            exciseTxCatCd = ""
            if excise_doc_cat == "Excise on Coal":
                exciseTxCatCd = "ECM"
            elif excise_doc_cat == "Excise Electricity":
                exciseTxCatCd = "EXEEG"

            # IPL Mapping
            iplCatCd = ""
            if ipl_doc_cat == "Insurance Premium Levy":
                iplCatCd = "IPL1"
            elif ipl_doc_cat == "Re-Insurance":
                iplCatCd = "IPL2"

            # Tourism Levy Mapping
            tlCatCd = "TL" if tl_doc_cat == "Tourism Levy" else ""

            zra_qty_unit_code = item_doc.get("custom_zra_qty_unit_code", "EA")

            print(f"Categories: IPL: {ipl_doc_cat}, Excise: {excise_doc_cat}, TL: {tl_doc_cat}, VAT: {vat_doc_cat}")

            discount_pct = flt(item.get("discount_percentage", 0))
            discount_amt = flt(gross * discount_pct / 100, 4)
            net = flt(gross - discount_amt, 4)

            # Calculate VAT based on category
            if vatCatCd == "A":  # Standard Rated 16%
                taxable = flt(net / 1.16, 4)
                vat = flt(taxable * 0.16, 4)
            elif vatCatCd == "B":  # Minimum Taxable Value 16%
                taxable = flt(net / 1.16, 4)
                vat = flt(taxable * 0.16, 4)
            elif vatCatCd == "F":  # Service Charge 10%
                taxable = flt(net / 1.10, 4)
                vat = flt(taxable * 0.10, 4)
            elif vatCatCd == "RVAT":  # Reverse VAT 16%
                taxable = flt(net / 1.16, 4)
                vat = flt(taxable * 0.16, 4)
            else:  # C1, C2, C3, D, E (Zero rated or Exempt)
                taxable = net
                vat = 0.0

            # Calculate special taxes (simplified - you may need more complex logic)
            excise_taxable = 0.0
            excise_tax = 0.0
            if exciseTxCatCd == "ECM":  # 5%
                excise_taxable = taxable
                excise_tax = flt(excise_taxable * 0.05, 4)
            elif exciseTxCatCd == "EXEEG":  # 3%
                excise_taxable = taxable
                excise_tax = flt(excise_taxable * 0.03, 4)

            ipl_taxable = 0.0
            ipl_tax = 0.0
            if iplCatCd == "IPL1":  # 5%
                ipl_taxable = taxable
                ipl_tax = flt(ipl_taxable * 0.05, 4)
            elif iplCatCd == "IPL2":  # 0%
                ipl_taxable = taxable
                ipl_tax = 0.0

            tl_taxable = 0.0
            tl_tax = 0.0
            if tlCatCd == "TL":  # 1.5%
                tl_taxable = taxable
                tl_tax = flt(tl_taxable * 0.015, 4)

            # Total amount for this item
            total_item_amount = flt(taxable + vat + excise_tax + ipl_tax + tl_tax, 4)

            # Update category totals
            if vatCatCd in category_totals:
                category_totals[vatCatCd]['taxable'] += taxable
                category_totals[vatCatCd]['tax'] += vat

            # Update special tax totals
            if exciseTxCatCd == "ECM":
                special_tax_totals['ecm']['taxable'] += excise_taxable
                special_tax_totals['ecm']['tax'] += excise_tax
            elif exciseTxCatCd == "EXEEG":
                special_tax_totals['exeeg']['taxable'] += excise_taxable
                special_tax_totals['exeeg']['tax'] += excise_tax

            if iplCatCd == "IPL1":
                special_tax_totals['ipl1']['taxable'] += ipl_taxable
                special_tax_totals['ipl1']['tax'] += ipl_tax
            elif iplCatCd == "IPL2":
                special_tax_totals['ipl2']['taxable'] += ipl_taxable
                special_tax_totals['ipl2']['tax'] += ipl_tax

            if tlCatCd == "TL":
                special_tax_totals['tl']['taxable'] += tl_taxable
                special_tax_totals['tl']['tax'] += tl_tax

            totals['gross'] += gross
            totals['discount'] += discount_amt
            totals['net'] += net

            # Get RRP (Recommended Retail Price) for MTV items
            rrp = 0.0
            if vatCatCd == "B":  # Minimum Taxable Value requires RRP
                rrp = flt(item_doc.get("custom_rrp") or item_doc.get("custom_recommended_retail_price") or price, 4)

            country_name = item_doc.get("custom_origin_place_code", "")
            print(country_name)
            try:
                res = requests.get(f"http://0.0.0.0:7000/country/{quote(country_name)}/", timeout=10)
                res.raise_for_status()
                country_code = res.json().get("code")
                if not country_code:
                    frappe.throw(f"Country code not found for '{country_name}' from external API.")
            except requests.exceptions.Timeout:
                frappe.throw(f"Timeout fetching country code for '{country_name}'.")
            except requests.RequestException as e:
                frappe.throw(f"Error fetching country code for '{country_name}' from external API: {e}")

            if vatCatCd == "C2":
                lpo_number = sell_order.get('lpoNumber')

                frappe.throw(
                    "VAT Category 'C2' (Zero-rating LPO) detected: 'lpoNumber' is mandatory and cannot be empty or null. "
                    "Please check the 'LPO Transaction' box to select the LPO transaction.",
                )

            elif vatCatCd == "C1":
                destn_country_code = sell_order.get('destnCountryCd')

                if not destn_country_code:
                    frappe.throw(
                        "VAT Category 'C1' (Exports) detected: 'Destination Country Code' (destnCountryCd) is mandatory and cannot be empty. "
                        "Please select the export sale type for this sale.",
                    )

                        

            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": "50102518",
                "itemNm": item.get("item_name"),
                "bcd": country_code,
                "pkgUnitCd": "WRAP",
                "pkg": 1,
                "qtyUnitCd": "U",
                "qty": qty,
                "prc": flt(price, 4),
                "splyAmt": gross,
                "dcRt": discount_pct,
                "dcAmt": discount_amt,
                "vatCatCd": vatCatCd,
                "vatTaxblAmt": taxable,
                "vatAmt": vat,
                "totAmt": total_item_amount,
                "exciseTxCatCd": exciseTxCatCd,
                "tlCatCd": tlCatCd,
                "iplCatCd": iplCatCd,
                "exciseTaxblAmt": excise_taxable,
                "tlTaxblAmt": tl_taxable,
                "iplTaxblAmt": ipl_taxable,
                "iplAmt": ipl_tax,
                "tlAmt": tl_tax,
                "exciseTxAmt": excise_tax,
                "rrp": rrp  
            })

        # Calculate total taxable and tax amounts
        total_taxable_amount = sum(cat['taxable'] for cat in category_totals.values()) + \
                            sum(cat['taxable'] for cat in special_tax_totals.values())
        
        total_tax_amount = sum(cat['tax'] for cat in category_totals.values()) + \
                        sum(cat['tax'] for cat in special_tax_totals.values())

        cash_discount_rate = flt(25.0, 4)
        cash_discount_amt = flt(totals['net'] * cash_discount_rate / 100, 4)
        final_amount = flt(totals['net'] - cash_discount_amt, 4)

        # Build payload with exact field names from ZRA API documentation
        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "orgSdcId": "SDC0010002709",
            "cisInvcNo": cisInvcNo,
            "orgInvcNo": 0,
            "Customer": customer_name,
            "custTpin": customer_tpin,
            "salesTyCd": "N",
            "rcptTyCd": "S",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "totItemCnt": len(item_list),
            
            # Individual tax category amounts (as per ZRA API spec)
            "taxblAmtA": flt(category_totals['A']['taxable'], 4),
            "taxblAmtB": flt(category_totals['B']['taxable'], 4),
            "taxblAmtC1": flt(category_totals['C1']['taxable'], 4),
            "taxblAmtC2": flt(category_totals['C2']['taxable'], 4),
            "taxblAmtC3": flt(category_totals['C3']['taxable'], 4),
            "taxblAmtD": flt(category_totals['D']['taxable'], 4),
            "taxblAmtRvat": flt(category_totals['RVAT']['taxable'], 4),
            "taxblAmtE": flt(category_totals['E']['taxable'], 4),
            "taxblAmtF": flt(category_totals['F']['taxable'], 4),
            "taxblAmtIpl1": flt(special_tax_totals['ipl1']['taxable'], 4),
            "taxblAmtIpl2": flt(special_tax_totals['ipl2']['taxable'], 4),
            "taxblAmtTl": flt(special_tax_totals['tl']['taxable'], 4),
            "taxblAmtEcm": flt(special_tax_totals['ecm']['taxable'], 4),
            "taxblAmtExeeg": flt(special_tax_totals['exeeg']['taxable'], 4),
            
            # Tax rates
            "taxRtA": 16,
            "taxRtB": 16,
            "taxRtC1": 0,
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "taxRtRvat": 16,
            "taxRtE": 0,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtIpl2": 0,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            
            # Tax amounts
            "taxAmtA": flt(category_totals['A']['tax'], 4),
            "taxAmtB": flt(category_totals['B']['tax'], 4),
            "taxAmtC1": flt(category_totals['C1']['tax'], 4),
            "taxAmtC2": flt(category_totals['C2']['tax'], 4),
            "taxAmtC3": flt(category_totals['C3']['tax'], 4),
            "taxAmtD": flt(category_totals['D']['tax'], 4),
            "taxAmtRvat": flt(category_totals['RVAT']['tax'], 4),
            "taxAmtE": flt(category_totals['E']['tax'], 4),
            "taxAmtF": flt(category_totals['F']['tax'], 4),
            "iplAmt1": flt(special_tax_totals['ipl1']['tax'], 4),
            "iplAmt2": flt(special_tax_totals['ipl2']['tax'], 4),
            "tlAmt": flt(special_tax_totals['tl']['tax'], 4),
            "exciseTxAmtEcm": flt(special_tax_totals['ecm']['tax'], 4),
            "exciseTxAmtExeeg": flt(special_tax_totals['exeeg']['tax'], 4),
            
            "totTaxblAmt": flt(total_taxable_amount, 4),
            "totTaxAmt": flt(total_tax_amount, 4),
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
        print("Preparing sale data:", payload)

        response = self.call_create_normal_sale_client(payload)

        if response.get("resultCd") == "000":
            get_rcpt_no = response.get("data", {}).get("rcptNo")
            print("Stock master updated successfully after sale.")
            doc_name = sell_order.get("name")
            self.update_rcptNo_delayed(docname=doc_name, rcpt_no=get_rcpt_no)

            print("This prints immediately, before delayed print")
            ocrnDt = datetime.now().strftime("%Y%m%d")
            itemsListInToUseData = toUseData.get("itemList", [])

            update_stock_items = []
            update_stock_master_items = []

            for item in itemsListInToUseData:
                # Calculate total taxable and tax amounts for this item
                item_total_taxable = item.get("vatTaxblAmt", 0) + item.get("exciseTaxblAmt", 0) + \
                                item.get("tlTaxblAmt", 0) + item.get("iplTaxblAmt", 0)
                item_total_tax = item.get("vatAmt", 0) + item.get("exciseTxAmt", 0) + \
                            item.get("tlAmt", 0) + item.get("iplAmt", 0)

                
                
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
                    "taxblAmt": flt(item_total_taxable, 4),
                    "vatCatCd": item.get("vatCatCd"),
                    "taxAmt": flt(item_total_tax, 4),
                    "totAmt": item.get("totAmt"),
                    "pkg": 1,
                    "totDcAmt": item.get("dcAmt", 0),
                })
                
                # Get actual remaining quantity from bins
                bins = frappe.db.get_all("Bin", filters={"item_code": item.get("itemCd")}, fields=["actual_qty"])
                remaining_qty = sum(flt(b.get("actual_qty", 0)) for b in bins) - item.get("qty", 0)
                
                update_stock_master_items.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": max(0, remaining_qty)
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

            self.run_stock_update_in_background(update_stock_payload, update_stock_master_items, created_by)


            frappe.msgprint(f"Sale made successfully: {response.get('resultMsg')}")
        else:
            frappe.throw(f"Sale save failed: {response.get('resultMsg')}")



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

        # Initialize category totals based on ZRA API structure
        category_totals = {
            'A': {'taxable': 0.0, 'tax': 0.0},
            'B': {'taxable': 0.0, 'tax': 0.0},
            'C1': {'taxable': 0.0, 'tax': 0.0},
            'C2': {'taxable': 0.0, 'tax': 0.0},
            'C3': {'taxable': 0.0, 'tax': 0.0},
            'D': {'taxable': 0.0, 'tax': 0.0},
            'RVAT': {'taxable': 0.0, 'tax': 0.0},
            'E': {'taxable': 0.0, 'tax': 0.0},
            'F': {'taxable': 0.0, 'tax': 0.0}
        }
        
        special_tax_totals = {
            'ipl1': {'taxable': 0.0, 'tax': 0.0},
            'ipl2': {'taxable': 0.0, 'tax': 0.0},
            'tl': {'taxable': 0.0, 'tax': 0.0},
            'ecm': {'taxable': 0.0, 'tax': 0.0},
            'exeeg': {'taxable': 0.0, 'tax': 0.0}
        }

        totals = {'gross': 0.0, 'discount': 0.0, 'net': 0.0}
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

            # Retrieve custom fields from item_doc (same as sales)
            ipl_doc_cat = item_doc.get("custom_ipl_category_code", "").strip()
            excise_doc_cat = item_doc.get("custom_excise_tax_category_code", "").strip()
            tl_doc_cat = item_doc.get("custom_tourism_levy", "").strip()
            vat_doc_cat = item_doc.get("custom_vat", "").strip()

            # VAT Mapping (same as sales)
            vat_map = {
                "StandardRated": "A", "MinimumTaxableValue": "B", "Exports": "C1",
                "ZeroRatingLocalPurchases": "C2", "ZeroRatedByNature": "C3",
                "Exempt": "D", "Disbursement": "E", "ServiceCharge10%": "F", "ReverseVAT": "RVAT"
            }
            vatCatCd = vat_map.get(vat_doc_cat, "A")  # Default to A for credit notes

            # Excise Tax Mapping
            exciseTxCatCd = ""
            if excise_doc_cat == "Excise on Coal":
                exciseTxCatCd = "ECM"
            elif excise_doc_cat == "Excise Electricity":
                exciseTxCatCd = "EXEEG"

            # IPL Mapping
            iplCatCd = ""
            if ipl_doc_cat == "Insurance Premium Levy":
                iplCatCd = "IPL1"
            elif ipl_doc_cat == "Re-Insurance":
                iplCatCd = "IPL2"

            # Tourism Levy Mapping
            tlCatCd = "TL" if tl_doc_cat == "Tourism Levy" else ""

            zra_qty_unit_code = item_doc.get("custom_zra_qty_unit_code", "EA")

            # Calculate VAT based on category (same logic as sales)
            if vatCatCd == "A":  # Standard Rated 16%
                taxable = flt(net / 1.16, 4)
                vat = flt(taxable * 0.16, 4)
            elif vatCatCd == "B":  # Minimum Taxable Value 16%
                taxable = flt(net / 1.16, 4)
                vat = flt(taxable * 0.16, 4)
            elif vatCatCd == "F":  # Service Charge 10%
                taxable = flt(net / 1.10, 4)
                vat = flt(taxable * 0.10, 4)
            elif vatCatCd == "RVAT":  # Reverse VAT 16%
                taxable = flt(net / 1.16, 4)
                vat = flt(taxable * 0.16, 4)
            else:  # C1, C2, C3, D, E (Zero rated or Exempt)
                taxable = net
                vat = 0.0

            # Calculate special taxes
            excise_taxable = 0.0
            excise_tax = 0.0
            if exciseTxCatCd == "ECM":  # 5%
                excise_taxable = taxable
                excise_tax = flt(excise_taxable * 0.05, 4)
            elif exciseTxCatCd == "EXEEG":  # 3%
                excise_taxable = taxable
                excise_tax = flt(excise_taxable * 0.03, 4)

            ipl_taxable = 0.0
            ipl_tax = 0.0
            if iplCatCd == "IPL1":  # 5%
                ipl_taxable = taxable
                ipl_tax = flt(ipl_taxable * 0.05, 4)
            elif iplCatCd == "IPL2":  # 0%
                ipl_taxable = taxable
                ipl_tax = 0.0

            tl_taxable = 0.0
            tl_tax = 0.0
            if tlCatCd == "TL":  # 1.5%
                tl_taxable = taxable
                tl_tax = flt(tl_taxable * 0.015, 4)

            # Total amount for this item
            total_item_amount = flt(taxable + vat + excise_tax + ipl_tax + tl_tax, 4)

            # Update category totals
            if vatCatCd in category_totals:
                category_totals[vatCatCd]['taxable'] += taxable
                category_totals[vatCatCd]['tax'] += vat

            # Update special tax totals
            if exciseTxCatCd == "ECM":
                special_tax_totals['ecm']['taxable'] += excise_taxable
                special_tax_totals['ecm']['tax'] += excise_tax
            elif exciseTxCatCd == "EXEEG":
                special_tax_totals['exeeg']['taxable'] += excise_taxable
                special_tax_totals['exeeg']['tax'] += excise_tax

            if iplCatCd == "IPL1":
                special_tax_totals['ipl1']['taxable'] += ipl_taxable
                special_tax_totals['ipl1']['tax'] += ipl_tax
            elif iplCatCd == "IPL2":
                special_tax_totals['ipl2']['taxable'] += ipl_taxable
                special_tax_totals['ipl2']['tax'] += ipl_tax

            if tlCatCd == "TL":
                special_tax_totals['tl']['taxable'] += tl_taxable
                special_tax_totals['tl']['tax'] += tl_tax

            totals['gross'] += gross
            totals['discount'] += discount_amt
            totals['net'] += net

            # Get RRP (Recommended Retail Price) for MTV items
            rrp = 0.0
            if vatCatCd == "B":  # Minimum Taxable Value requires RRP
                rrp = flt(item_doc.get("custom_rrp") or item_doc.get("custom_recommended_retail_price") or price, 4)

            original_item = next((x for x in original_invoice.items if x.item_code == item_code), None)
            country_name = item_doc.get("custom_origin_place_code", "")
            print(country_name)
            try:
                res = requests.get(f"http://0.0.0.0:7000/country/{quote(country_name)}/", timeout=10)
                res.raise_for_status()
                country_code = res.json().get("code")
                if not country_code:
                    frappe.throw(f"Country code not found for '{country_name}' from external API.")
            except requests.exceptions.Timeout:
                frappe.throw(f"Timeout fetching country code for '{country_name}'.")
            except requests.RequestException as e:
                frappe.throw(f"Error fetching country code for '{country_name}' from external API: {e}")
            
            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": "50102518",
                "itemNm": item.get("item_name"),
                "bcd": country_code,
                "pkgUnitCd": "WRAP",
                "pkg": 1,
                "qtyUnitCd": "U",
                "qty": qty,
                "prc": flt(price, 4),
                "splyAmt": gross,
                "dcRt": discount_pct,
                "dcAmt": discount_amt,
                "vatCatCd": vatCatCd,
                "vatTaxblAmt": taxable,
                "vatAmt": vat,
                "totAmt": total_item_amount,
                "exciseTxCatCd": exciseTxCatCd,
                "tlCatCd": tlCatCd,
                "iplCatCd": iplCatCd,
                "exciseTaxblAmt": excise_taxable,
                "tlTaxblAmt": tl_taxable,
                "iplTaxblAmt": ipl_taxable,
                "iplAmt": ipl_tax,
                "tlAmt": tl_tax,
                "exciseTxAmt": excise_tax,
                "rrp": rrp  # Required for MTV (Category B) items
            })

        # Calculate total taxable and tax amounts
        total_taxable_amount = sum(cat['taxable'] for cat in category_totals.values()) + \
                            sum(cat['taxable'] for cat in special_tax_totals.values())
        
        total_tax_amount = sum(cat['tax'] for cat in category_totals.values()) + \
                        sum(cat['tax'] for cat in special_tax_totals.values())

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "orgSdcId": "SDC0010002709",
            "cisInvcNo": cisInvcNo,
            "orgInvcNo": orgInvcNo,
            "Customer": customer_name,
            "custTpin": customer_tpin,
            "salesTyCd": "N",
            "rcptTyCd": "R",  # Refund
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "rfdRsnCd": custom_reason_code,  # Use the mapped code, not text
            "totItemCnt": len(item_list),
            
            # Individual tax category amounts (as per ZRA API spec)
            "taxblAmtA": flt(category_totals['A']['taxable'], 4),
            "taxblAmtB": flt(category_totals['B']['taxable'], 4),
            "taxblAmtC1": flt(category_totals['C1']['taxable'], 4),
            "taxblAmtC2": flt(category_totals['C2']['taxable'], 4),
            "taxblAmtC3": flt(category_totals['C3']['taxable'], 4),
            "taxblAmtD": flt(category_totals['D']['taxable'], 4),
            "taxblAmtRvat": flt(category_totals['RVAT']['taxable'], 4),
            "taxblAmtE": flt(category_totals['E']['taxable'], 4),
            "taxblAmtF": flt(category_totals['F']['taxable'], 4),
            "taxblAmtIpl1": flt(special_tax_totals['ipl1']['taxable'], 4),
            "taxblAmtIpl2": flt(special_tax_totals['ipl2']['taxable'], 4),
            "taxblAmtTl": flt(special_tax_totals['tl']['taxable'], 4),
            "taxblAmtEcm": flt(special_tax_totals['ecm']['taxable'], 4),
            "taxblAmtExeeg": flt(special_tax_totals['exeeg']['taxable'], 4),
            
            # Tax rates
            "taxRtA": 16,
            "taxRtB": 16,
            "taxRtC1": 0,
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "taxRtRvat": 16,
            "taxRtE": 0,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtIpl2": 0,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            
            # Tax amounts
            "taxAmtA": flt(category_totals['A']['tax'], 4),
            "taxAmtB": flt(category_totals['B']['tax'], 4),
            "taxAmtC1": flt(category_totals['C1']['tax'], 4),
            "taxAmtC2": flt(category_totals['C2']['tax'], 4),
            "taxAmtC3": flt(category_totals['C3']['tax'], 4),
            "taxAmtD": flt(category_totals['D']['tax'], 4),
            "taxAmtRvat": flt(category_totals['RVAT']['tax'], 4),
            "taxAmtE": flt(category_totals['E']['tax'], 4),
            "taxAmtF": flt(category_totals['F']['tax'], 4),
            "iplAmt1": flt(special_tax_totals['ipl1']['tax'], 4),
            "iplAmt2": flt(special_tax_totals['ipl2']['tax'], 4),
            "tlAmt": flt(special_tax_totals['tl']['tax'], 4),
            "exciseTxAmtEcm": flt(special_tax_totals['ecm']['tax'], 4),
            "exciseTxAmtExeeg": flt(special_tax_totals['exeeg']['tax'], 4),
            
            # Totals
            "totTaxblAmt": flt(total_taxable_amount, 4),
            "totTaxAmt": flt(total_tax_amount, 4),
            "totAmt": flt(abs(totals['net']), 4),
            
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

        print("Credit Note payload:", payload)
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
            update_stock_master_items = []

            for item in item_list:
                # Calculate total taxable and tax amounts for this item
                item_total_taxable = item.get("vatTaxblAmt", 0) + item.get("exciseTaxblAmt", 0) + \
                                item.get("tlTaxblAmt", 0) + item.get("iplTaxblAmt", 0)
                item_total_tax = item.get("vatAmt", 0) + item.get("exciseTxAmt", 0) + \
                            item.get("tlAmt", 0) + item.get("iplAmt", 0)
                
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
                    "taxblAmt": flt(item_total_taxable, 4),
                    "vatCatCd": item.get("vatCatCd"),
                    "taxAmt": flt(item_total_tax, 4),
                    "totAmt": item.get("totAmt"),
                    "pkg": 1,
                    "totDcAmt": item.get("dcAmt", 0),
                })
                
                # Get actual remaining quantity from bins (add back the returned qty)
                bins = frappe.db.get_all("Bin", filters={"item_code": item.get("itemCd")}, fields=["actual_qty"])
                remaining_qty = sum(flt(b.get("actual_qty", 0)) for b in bins) + item.get("qty", 0)
                
                update_stock_master_items.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": max(0, remaining_qty)
                })

            update_stock_payload = {
                "tpin": self.tpin,
                "bhfId": self.branch_code,
                "sarNo": 1,
                "orgSarNo": 0,
                "regTyCd": "M",
                "sarTyCd": "03",  # Return/Refund type
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

            self.run_stock_update_in_background(update_stock_payload, update_stock_master_items, created_by)
                
        else:
            error_msg = response.get("resultMsg", "Unknown error occurred")
            frappe.throw(f"Failed to create Credit Note: {error_msg}")




    def create_debit_note_payload(self, debit_note_doc):
        now = datetime.now()

        customer_name = debit_note_doc.get("customer") or debit_note_doc.get("customer_name") or ""
        customer_doc = frappe.get_doc("Customer", customer_name) if customer_name else None
        customer_tpin = customer_doc.get("custom_customer_tpin") if customer_doc else ""
        
        cisInvcNo = debit_note_doc.get("name", f"DN-{random.randint(1000,9999)}")
        original_invoice_no = debit_note_doc.get("return_against")

        try:
            original_invoice = frappe.get_doc("Sales Invoice", original_invoice_no)
            orgInvcNo = original_invoice.custom_rcpt_no if hasattr(original_invoice, 'custom_rcpt_no') else None
            if not orgInvcNo:
                frappe.throw("Original invoice receipt number not found")
        except Exception as e:
            frappe.throw(f"Failed to get original invoice: {str(e)}")

        created_by = debit_note_doc.get("owner") or "system"
        currency = debit_note_doc.get("currency") or "ZMW"

        debit_type_map = {
            "01": "Wrong product(s)",
            "02": "Wrong price",
            "03": "Damaged Goods",
            "04": "Wrong Customer Invoiced",
            "05": "Duplicated invoice",
            "06": "Excess supplies",
            "07": "Other (Provide other reason in brief)"
        }

        debit_type_reverse_map = {v: k for k, v in debit_type_map.items()}
        custom_reason_text = debit_note_doc.get("custom_reason", "Other (Provide other reason in brief)")
        custom_reason_code = debit_type_reverse_map.get(custom_reason_text, "07")

        # Initialize category totals based on ZRA API structure
        category_totals = {
            'A': {'taxable': 0.0, 'tax': 0.0},
            'B': {'taxable': 0.0, 'tax': 0.0},
            'C1': {'taxable': 0.0, 'tax': 0.0},
            'C2': {'taxable': 0.0, 'tax': 0.0},
            'C3': {'taxable': 0.0, 'tax': 0.0},
            'D': {'taxable': 0.0, 'tax': 0.0},
            'RVAT': {'taxable': 0.0, 'tax': 0.0},
            'E': {'taxable': 0.0, 'tax': 0.0},
            'F': {'taxable': 0.0, 'tax': 0.0}
        }
        
        special_tax_totals = {
            'ipl1': {'taxable': 0.0, 'tax': 0.0},
            'ipl2': {'taxable': 0.0, 'tax': 0.0},
            'tl': {'taxable': 0.0, 'tax': 0.0},
            'ecm': {'taxable': 0.0, 'tax': 0.0},
            'exeeg': {'taxable': 0.0, 'tax': 0.0}
        }

        totals = {'gross': 0.0, 'discount': 0.0, 'net': 0.0}
        item_list = []
        items = debit_note_doc.get("items", [])
        
        for i, item in enumerate(items, 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)
            
            qty = abs(flt(item.get("qty", 1))) 
            price = flt(item.get("rate") or item_doc.get("standard_rate", 0))
            gross = flt(qty * price, 4)

            discount_pct = flt(item.get("discount_percentage", 0))
            discount_amt = flt(gross * discount_pct / 100, 4)
            net = flt(gross - discount_amt, 4)

            # Retrieve custom fields from item_doc (same as sales)
            ipl_doc_cat = item_doc.get("custom_ipl_category_code", "").strip()
            excise_doc_cat = item_doc.get("custom_excise_tax_category_code", "").strip()
            tl_doc_cat = item_doc.get("custom_tourism_levy", "").strip()
            vat_doc_cat = item_doc.get("custom_vat", "").strip()

            # VAT Mapping (same as sales)
            vat_map = {
                "StandardRated": "A", "MinimumTaxableValue": "B", "Exports": "C1",
                "ZeroRatingLocalPurchases": "C2", "ZeroRatedByNature": "C3",
                "Exempt": "D", "Disbursement": "E", "ServiceCharge10%": "F", "ReverseVAT": "RVAT"
            }
            vatCatCd = vat_map.get(vat_doc_cat, "A")  # Default to A for debit notes

            # Excise Tax Mapping
            exciseTxCatCd = ""
            if excise_doc_cat == "Excise on Coal":
                exciseTxCatCd = "ECM"
            elif excise_doc_cat == "Excise Electricity":
                exciseTxCatCd = "EXEEG"

            # IPL Mapping
            iplCatCd = ""
            if ipl_doc_cat == "Insurance Premium Levy":
                iplCatCd = "IPL1"
            elif ipl_doc_cat == "Re-Insurance":
                iplCatCd = "IPL2"

            # Tourism Levy Mapping
            tlCatCd = "TL" if tl_doc_cat == "Tourism Levy" else ""

            zra_qty_unit_code = item_doc.get("custom_zra_qty_unit_code", "EA")

            # Calculate VAT based on category (same logic as sales)
            if vatCatCd == "A":  # Standard Rated 16%
                taxable = flt(net / 1.16, 4)
                vat = flt(taxable * 0.16, 4)
            elif vatCatCd == "B":  # Minimum Taxable Value 16%
                taxable = flt(net / 1.16, 4)
                vat = flt(taxable * 0.16, 4)
            elif vatCatCd == "F":  # Service Charge 10%
                taxable = flt(net / 1.10, 4)
                vat = flt(taxable * 0.10, 4)
            elif vatCatCd == "RVAT":  # Reverse VAT 16%
                taxable = flt(net / 1.16, 4)
                vat = flt(taxable * 0.16, 4)
            else:  # C1, C2, C3, D, E (Zero rated or Exempt)
                taxable = net
                vat = 0.0

            # Calculate special taxes
            excise_taxable = 0.0
            excise_tax = 0.0
            if exciseTxCatCd == "ECM":  # 5%
                excise_taxable = taxable
                excise_tax = flt(excise_taxable * 0.05, 4)
            elif exciseTxCatCd == "EXEEG":  # 3%
                excise_taxable = taxable
                excise_tax = flt(excise_taxable * 0.03, 4)

            ipl_taxable = 0.0
            ipl_tax = 0.0
            if iplCatCd == "IPL1":  # 5%
                ipl_taxable = taxable
                ipl_tax = flt(ipl_taxable * 0.05, 4)
            elif iplCatCd == "IPL2":  # 0%
                ipl_taxable = taxable
                ipl_tax = 0.0

            tl_taxable = 0.0
            tl_tax = 0.0
            if tlCatCd == "TL":  # 1.5%
                tl_taxable = taxable
                tl_tax = flt(tl_taxable * 0.015, 4)

            # Total amount for this item
            total_item_amount = flt(taxable + vat + excise_tax + ipl_tax + tl_tax, 4)

            # Update category totals
            if vatCatCd in category_totals:
                category_totals[vatCatCd]['taxable'] += taxable
                category_totals[vatCatCd]['tax'] += vat

            # Update special tax totals
            if exciseTxCatCd == "ECM":
                special_tax_totals['ecm']['taxable'] += excise_taxable
                special_tax_totals['ecm']['tax'] += excise_tax
            elif exciseTxCatCd == "EXEEG":
                special_tax_totals['exeeg']['taxable'] += excise_taxable
                special_tax_totals['exeeg']['tax'] += excise_tax

            if iplCatCd == "IPL1":
                special_tax_totals['ipl1']['taxable'] += ipl_taxable
                special_tax_totals['ipl1']['tax'] += ipl_tax
            elif iplCatCd == "IPL2":
                special_tax_totals['ipl2']['taxable'] += ipl_taxable
                special_tax_totals['ipl2']['tax'] += ipl_tax

            if tlCatCd == "TL":
                special_tax_totals['tl']['taxable'] += tl_taxable
                special_tax_totals['tl']['tax'] += tl_tax

            totals['gross'] += gross
            totals['discount'] += discount_amt
            totals['net'] += net

            # Get RRP (Recommended Retail Price) for MTV items
            rrp = 0.0
            if vatCatCd == "B":  # Minimum Taxable Value requires RRP
                rrp = flt(item_doc.get("custom_rrp") or item_doc.get("custom_recommended_retail_price") or price, 4)

            original_item = next((x for x in original_invoice.items if x.item_code == item_code), None)
            country_name = item_doc.get("custom_origin_place_code", "")
            print(country_name)
            try:
                res = requests.get(f"http://0.0.0.0:7000/country/{quote(country_name)}/", timeout=10)
                res.raise_for_status()
                country_code = res.json().get("code")
                if not country_code:
                    frappe.throw(f"Country code not found for '{country_name}' from external API.")
            except requests.exceptions.Timeout:
                frappe.throw(f"Timeout fetching country code for '{country_name}'.")
            except requests.RequestException as e:
                frappe.throw(f"Error fetching country code for '{country_name}' from external API: {e}")

            
            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": "50102518",
                "itemNm": item.get("item_name"),
                "bcd": country_code,
                "pkgUnitCd": "WRAP",
                "pkg": 1,
                "qtyUnitCd": "U",
                "qty": qty,
                "prc": flt(price, 4),
                "splyAmt": gross,
                "dcRt": discount_pct,
                "dcAmt": discount_amt,
                "vatCatCd": vatCatCd,
                "vatTaxblAmt": taxable,
                "vatAmt": vat,
                "totAmt": total_item_amount,
                "exciseTxCatCd": exciseTxCatCd,
                "tlCatCd": tlCatCd,
                "iplCatCd": iplCatCd,
                "exciseTaxblAmt": excise_taxable,
                "tlTaxblAmt": tl_taxable,
                "iplTaxblAmt": ipl_taxable,
                "iplAmt": ipl_tax,
                "tlAmt": tl_tax,
                "exciseTxAmt": excise_tax,
                "rrp": rrp  # Required for MTV (Category B) items
            })

        # Calculate total taxable and tax amounts
        total_taxable_amount = sum(cat['taxable'] for cat in category_totals.values()) + \
                            sum(cat['taxable'] for cat in special_tax_totals.values())
        
        total_tax_amount = sum(cat['tax'] for cat in category_totals.values()) + \
                        sum(cat['tax'] for cat in special_tax_totals.values())

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "orgSdcId": "SDC0010002709",
            "cisInvcNo": cisInvcNo,
            "orgInvcNo": orgInvcNo,
            "Customer": customer_name,
            "custTpin": customer_tpin,
            "salesTyCd": "N",
            "rcptTyCd": "D",  # Debit
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "dbtRsnCd": custom_reason_code,  # Use the mapped code, not text
            "totItemCnt": len(item_list),
            
            # Individual tax category amounts (as per ZRA API spec)
            "taxblAmtA": flt(category_totals['A']['taxable'], 4),
            "taxblAmtB": flt(category_totals['B']['taxable'], 4),
            "taxblAmtC1": flt(category_totals['C1']['taxable'], 4),
            "taxblAmtC2": flt(category_totals['C2']['taxable'], 4),
            "taxblAmtC3": flt(category_totals['C3']['taxable'], 4),
            "taxblAmtD": flt(category_totals['D']['taxable'], 4),
            "taxblAmtRvat": flt(category_totals['RVAT']['taxable'], 4),
            "taxblAmtE": flt(category_totals['E']['taxable'], 4),
            "taxblAmtF": flt(category_totals['F']['taxable'], 4),
            "taxblAmtIpl1": flt(special_tax_totals['ipl1']['taxable'], 4),
            "taxblAmtIpl2": flt(special_tax_totals['ipl2']['taxable'], 4),
            "taxblAmtTl": flt(special_tax_totals['tl']['taxable'], 4),
            "taxblAmtEcm": flt(special_tax_totals['ecm']['taxable'], 4),
            "taxblAmtExeeg": flt(special_tax_totals['exeeg']['taxable'], 4),
            
            # Tax rates
            "taxRtA": 16,
            "taxRtB": 16,
            "taxRtC1": 0,
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "taxRtRvat": 16,
            "taxRtE": 0,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtIpl2": 0,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            
            # Tax amounts
            "taxAmtA": flt(category_totals['A']['tax'], 4),
            "taxAmtB": flt(category_totals['B']['tax'], 4),
            "taxAmtC1": flt(category_totals['C1']['tax'], 4),
            "taxAmtC2": flt(category_totals['C2']['tax'], 4),
            "taxAmtC3": flt(category_totals['C3']['tax'], 4),
            "taxAmtD": flt(category_totals['D']['tax'], 4),
            "taxAmtRvat": flt(category_totals['RVAT']['tax'], 4),
            "taxAmtE": flt(category_totals['E']['tax'], 4),
            "taxAmtF": flt(category_totals['F']['tax'], 4),
            "iplAmt1": flt(special_tax_totals['ipl1']['tax'], 4),
            "iplAmt2": flt(special_tax_totals['ipl2']['tax'], 4),
            "tlAmt": flt(special_tax_totals['tl']['tax'], 4),
            "exciseTxAmtEcm": flt(special_tax_totals['ecm']['tax'], 4),
            "exciseTxAmtExeeg": flt(special_tax_totals['exeeg']['tax'], 4),
            
            # Totals
            "totTaxblAmt": flt(total_taxable_amount, 4),
            "totTaxAmt": flt(total_tax_amount, 4),
            "totAmt": flt(abs(totals['net']), 4),
            
            # Other fields
            "cashDcRt": 0.0,
            "cashDcAmt": 0.0,
            "prchrAcptcYn": "N",
            "remark": debit_note_doc.get("remarks") or "",
            "regrId": created_by,
            "regrNm": created_by,
            "modrId": created_by,
            "modrNm": created_by,
            "saleCtyCd": "1",
            "currencyTyCd": currency,
            "exchangeRt": "1",
            "destnCountryCd": "",
            "rfdRsnCd": "",  # Empty for debit notes
            "invcAdjustReason": custom_reason_text,
            "itemList": item_list
        }

        print("Debit Note payload:", payload)
        response = self.call_debit_sale_client(payload)

        if response.get("resultCd") == "000":
            if response.get("data") and response["data"].get("rcptNo"):
                rcpt_no = response["data"]["rcptNo"]
                doc_name = debit_note_doc.get("name")
                self.update_rcptNo_delayed(docname=doc_name, rcpt_no=rcpt_no)
                frappe.msgprint(f"Debit Note created successfully. Receipt No: {rcpt_no}")
            else:
                frappe.msgprint("Debit Note created successfully but no receipt number was returned")

            ocrnDt = datetime.now().strftime("%Y%m%d")
            update_stock_item = []
            update_stock_master_items = []

            for item in item_list:
                # Calculate total taxable and tax amounts for this item
                item_total_taxable = item.get("vatTaxblAmt", 0) + item.get("exciseTaxblAmt", 0) + \
                                item.get("tlTaxblAmt", 0) + item.get("iplTaxblAmt", 0)
                item_total_tax = item.get("vatAmt", 0) + item.get("exciseTxAmt", 0) + \
                            item.get("tlAmt", 0) + item.get("iplAmt", 0)
                
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
                    "taxblAmt": flt(item_total_taxable, 4),
                    "vatCatCd": item.get("vatCatCd"),
                    "taxAmt": flt(item_total_tax, 4),
                    "totAmt": item.get("totAmt"),
                    "pkg": 1,
                    "totDcAmt": item.get("dcAmt", 0),
                })
                
                # Get actual remaining quantity from bins (subtract the debited qty)
                bins = frappe.db.get_all("Bin", filters={"item_code": item.get("itemCd")}, fields=["actual_qty"])
                remaining_qty = sum(flt(b.get("actual_qty", 0)) for b in bins) - item.get("qty", 0)
                
                update_stock_master_items.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": max(0, remaining_qty)
                })

            update_stock_payload = {
                "tpin": self.tpin,
                "bhfId": self.branch_code,
                "sarNo": 1,
                "orgSarNo": 0,
                "regTyCd": "M",
                "sarTyCd": "02",  # Sale type for debit notes
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

            self.run_stock_update_in_background(update_stock_payload, update_stock_master_items, created_by)
                
        else:
            error_msg = response.get("resultMsg", "Unknown error occurred")
            frappe.throw(f"Failed to create Debit Note: {error_msg}")
    
    def create_export_sale_payload(self, export_sale_data):
        now = datetime.now()

        customer_name = export_sale_data.get("customer") or export_sale_data.get("customer_name") or ""
        customer_doc = frappe.get_doc("Customer", customer_name) if customer_name else None
        customer_tpin = customer_doc.get("custom_customer_tpin") if customer_doc else ""
        
        
        # For export sales, cisInvcNo should be the system's generated invoice number
        cisInvcNo = export_sale_data.get("name", f"EXP-{random.randint(1000,9999)}")
        
        # orgInvcNo should only be present for credit/debit notes. For a new export sale, it should be null or 0.
        # Assuming for a 'Save Sales Request - Exports' this is a new sale, not a linked one.
 

        created_by = export_sale_data.get("owner") or "system"
        currency = export_sale_data.get("currency") or "ZMW"
        
        # Destination Country Code (Required for Exports)
        destn_country = export_sale_data.get("custom_destination_country")
        destnCountryCd = ""
        if destn_country:
            try:
                # Assuming an external service to get country code from country name
                res = requests.get(f"http://0.0.0.0:7000/country/{quote(destn_country)}/", timeout=10)
                res.raise_for_status()
                country_data = res.json()
                destnCountryCd = country_data.get("code")
                if not destnCountryCd:
                    frappe.throw(f"Country code not found for '{destn_country}' from external API response: {country_data}")
            except requests.exceptions.Timeout:
                frappe.throw(f"Timeout fetching country code for '{destn_country}'.")
            except requests.RequestException as e:
                frappe.throw(f"Error fetching country code for '{destn_country}' from external API: {e}")
        else:
            frappe.throw("Destination Country is required for Export Sales.")

        # Special check: If destination country is ZM (Zambia's code, assuming your system recognizes it),
        # then it's not a true export, even if custom_destination_country was set.
        # This prevents the `destnCountryCd` error from the API if ZM is mistakenly set for an export.
        if destnCountryCd == "ZM":
            frappe.throw(f"For an Export Sale, the destination country '{destn_country}' cannot be Zambia ({destnCountryCd}). Please select a foreign country.")


        category_totals = {
            'A': {'taxable': 0.0, 'tax': 0.0},
            'B': {'taxable': 0.0, 'tax': 0.0},
            'C1': {'taxable': 0.0, 'tax': 0.0}, # Exports
            'C2': {'taxable': 0.0, 'tax': 0.0},
            'C3': {'taxable': 0.0, 'tax': 0.0},
            'D': {'taxable': 0.0, 'tax': 0.0},
            'RVAT': {'taxable': 0.0, 'tax': 0.0},
            'E': {'taxable': 0.0, 'tax': 0.0},
            'F': {'taxable': 0.0, 'tax': 0.0}
        }
        
        special_tax_totals = {
            'ipl1': {'taxable': 0.0, 'tax': 0.0},
            'ipl2': {'taxable': 0.0, 'tax': 0.0},
            'tl': {'taxable': 0.0, 'tax': 0.0},
            'ecm': {'taxable': 0.0, 'tax': 0.0},
            'exeeg': {'taxable': 0.0, 'tax': 0.0}
        }

        totals = {'gross': 0.0, 'discount': 0.0, 'net': 0.0, 'total_tax_inclusive_amount': 0.0}
        item_list = []
        items = export_sale_data.get("items", [])
        
        for i, item in enumerate(items, 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)

            
            qty = abs(flt(item.get("qty", 1))) 
            price = flt(item.get("rate") or item_doc.get("standard_rate", 0)) 
            packaging_unit = item_doc.get("custom_packaging_unit_code", "").strip()
            unit_name = item_doc.get("custom_units_of_measure", "").strip()
            print("Unit name: ", unit_name)
            
            # This is the tax-inclusive amount for the line item
            gross_line_amount = flt(qty * price, 4) 

            discount_pct = flt(item.get("discount_percentage", 0))
            discount_amt = flt(gross_line_amount * discount_pct / 100, 4)
            
            # Net amount after discount, still tax-inclusive for now
            net_line_amount = flt(gross_line_amount - discount_amt, 4)

            # Retrieve custom fields from item_doc
            ipl_doc_cat = item_doc.get("custom_ipl_category_code", "").strip()
            excise_doc_cat = item_doc.get("custom_excise_tax_category_code", "").strip()
            tl_doc_cat = item_doc.get("custom_tourism_levy", "").strip()
            vat_doc_cat = item_doc.get("custom_vat", "").strip()

            # VAT Mapping (based on documentation)
            vat_map = {
                "StandardRated": "A", "MinimumTaxableValue": "B", "Exports": "C1",
                "ZeroRatingLocalPurchases": "C2", "ZeroRatedByNature": "C3",
                "Exempt": "D", "Disbursement": "E", "ServiceCharge10%": "F", "ReverseVAT": "RVAT"
            }
            
            # --- VAT Category Validation ---
            vatCatCd = "C1"
         

            # Excise Tax Mapping
            exciseTxCatCd = ""
            if excise_doc_cat == "Excise on Coal":
                exciseTxCatCd = "ECM"
            elif excise_doc_cat == "Excise Electricity":
                exciseTxCatCd = "EXEEG"

            # IPL Mapping
            iplCatCd = ""
            if ipl_doc_cat == "Insurance Premium Levy":
                iplCatCd = "IPL1"
            elif ipl_doc_cat == "Re-Insurance":
                iplCatCd = "IPL2"

            # Tourism Levy Mapping
            tlCatCd = "TL" if tl_doc_cat == "Tourism Levy" else ""

            zra_qty_unit_code = item_doc.get("custom_zra_qty_unit_code", "EA")
            
            # --- Tax Calculation Logic (Revised for clarity and consistency) ---
            # Assume net_line_amount is the tax-inclusive amount after discount for a particular line item.
            # We need to extract the taxable base and the tax amount for each category.

            vat_taxable = 0.0
            vat_amount = 0.0
            excise_taxable = 0.0
            excise_amount = 0.0
            ipl_taxable = 0.0
            ipl_amount = 0.0
            tl_taxable = 0.0
            tl_amount = 0.0
            
            # This 'taxable_base_for_other_taxes' will be the tax-exclusive amount from VAT calculation.
            taxable_base_for_other_taxes = net_line_amount 

            # Since we are enforcing vatCatCd == "C1" for export sales in the validation step above,
            # this section can be simplified for export sales, but keeping the full structure
            # allows this function to potentially be adapted or ensures robustness.
            if vatCatCd == "A":  # Standard Rated 16%
                vat_taxable = flt(net_line_amount / 1.16, 4)
                vat_amount = flt(vat_taxable * 0.16, 4)
                taxable_base_for_other_taxes = vat_taxable
            elif vatCatCd == "B":  # Minimum Taxable Value 16%
                vat_taxable = flt(net_line_amount / 1.16, 4)
                vat_amount = flt(vat_taxable * 0.16, 4)
                taxable_base_for_other_taxes = vat_taxable
            elif vatCatCd == "F":  # Service Charge 10%
                vat_taxable = flt(net_line_amount / 1.10, 4)
                vat_amount = flt(vat_taxable * 0.10, 4)
                taxable_base_for_other_taxes = vat_taxable
            elif vatCatCd == "RVAT":  # Reverse VAT 16%
                vat_taxable = flt(net_line_amount / 1.16, 4)
                vat_amount = flt(vat_taxable * 0.16, 4)
                taxable_base_for_other_taxes = vat_taxable
            # For C1, C2, C3, D, E (Zero rated or Exempt for VAT)
            else:  
                vat_taxable = net_line_amount # For zero-rated/exempt, the whole amount is taxable base
                vat_amount = 0.0 # This will be the case for C1
                taxable_base_for_other_taxes = vat_taxable # Still use this for other tax calculations


            # Calculate special taxes based on the determined taxable_base_for_other_taxes
            if exciseTxCatCd == "ECM":  # 5%
                excise_taxable = taxable_base_for_other_taxes
                excise_amount = flt(excise_taxable * 0.05, 4)
            elif exciseTxCatCd == "EXEEG":  # 3%
                excise_taxable = taxable_base_for_other_taxes
                excise_amount = flt(excise_taxable * 0.03, 4)

            if iplCatCd == "IPL1":  # 5%
                ipl_taxable = taxable_base_for_other_taxes
                ipl_amount = flt(ipl_taxable * 0.05, 4)
            elif iplCatCd == "IPL2":  # 0%
                ipl_taxable = taxable_base_for_other_taxes
                ipl_amount = 0.0 # Re-Insurance is 0%

            if tlCatCd == "TL":  # 1.5%
                tl_taxable = taxable_base_for_other_taxes
                tl_amount = flt(tl_taxable * 0.015, 4)

            # Recalculate `totAmt` to be just `net_line_amount` (after discount, before splitting taxes)
            total_amount_line_item = net_line_amount

            # Update category totals for the main payload
            if vatCatCd in category_totals:
                category_totals[vatCatCd]['taxable'] += vat_taxable
                category_totals[vatCatCd]['tax'] += vat_amount

            if exciseTxCatCd == "ECM":
                special_tax_totals['ecm']['taxable'] += excise_taxable
                special_tax_totals['ecm']['tax'] += excise_amount
            elif exciseTxCatCd == "EXEEG":
                special_tax_totals['exeeg']['taxable'] += excise_taxable
                special_tax_totals['exeeg']['tax'] += excise_amount

            if iplCatCd == "IPL1":
                special_tax_totals['ipl1']['taxable'] += ipl_taxable
                special_tax_totals['ipl1']['tax'] += ipl_amount
            elif iplCatCd == "IPL2":
                special_tax_totals['ipl2']['taxable'] += ipl_taxable
                special_tax_totals['ipl2']['tax'] += ipl_amount

            if tlCatCd == "TL":
                special_tax_totals['tl']['taxable'] += tl_taxable
                special_tax_totals['tl']['tax'] += tl_amount

            totals['gross'] += gross_line_amount
            totals['discount'] += discount_amt
            totals['net'] += net_line_amount # This is the net tax-inclusive amount per line item
            totals['total_tax_inclusive_amount'] += total_amount_line_item

            # Get RRP (Recommended Retail Price) for MTV items
            rrp = 0.0
            if vatCatCd == "B": # Minimum Taxable Value requires RRP
                rrp = flt(item_doc.get("custom_rrp") or item_doc.get("custom_recommended_retail_price") or price, 4)
            
            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": item_doc.get("custom_item_classification_code", "50102518"), # Assuming a default if not set
                "itemNm": item.get("item_name"),
                "bcd": item_doc.get("barcode", ""),
                "pkgUnitCd": "WRAP",
                "pkg": item.get("pkg", 1),
                "qtyUnitCd": "U",
                "qty": qty,
                "prc": flt(price, 4),
                "splyAmt": flt(gross_line_amount, 4), # Total supply amount for the line (qty * price)
                "dcRt": flt(discount_pct, 2),
                "dcAmt": flt(discount_amt, 2),
                "isrccCd": item.get("insurance_company_code", ""),
                "isrccNm": item.get("insurance_company_name", ""),
                "isrcAmt": flt(item.get("insurance_amount", 0.0), 4), # Assuming this comes from item data
                "vatCatCd": vatCatCd,
                "exciseTxCatCd": exciseTxCatCd if exciseTxCatCd else None, # Null if not applicable
                "vatTaxblAmt": flt(vat_taxable, 4),
                "exciseTaxblAmt": flt(excise_taxable, 4),
                "tlTaxblAmt": flt(tl_taxable, 4),
                "iplTaxblAmt": flt(ipl_taxable, 4),
                "iplAmt": flt(ipl_amount, 4),
                "tlAmt": flt(tl_amount, 4),
                "vatAmt": flt(vat_amount, 4),
                "exciseTxAmt": flt(excise_amount, 4),
                "totAmt": flt(total_amount_line_item, 2), # Total tax inclusive amount of the line item
                "rrp": flt(rrp, 4) # Only required for MTV items, otherwise 0.0 or null
            })

        # Calculate total taxable and total tax amounts for the entire invoice
        # Sum of all individual taxable amounts for each tax type
        total_taxable_amount = sum(cat['taxable'] for cat in category_totals.values()) + \
                            sum(cat['taxable'] for cat in special_tax_totals.values())
        
        # Sum of all individual tax amounts for each tax type
        total_tax_amount = sum(cat['tax'] for cat in category_totals.values()) + \
                        sum(cat['tax'] for cat in special_tax_totals.values())

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "orgSdcId": "SDC0010002709", # Verify this value or make it configurable
            "cisInvcNo": cisInvcNo,
            "orgInvcNo": 0, # Will be None for a new export sale
            "custTpin": customer_tpin,
            "custNm": customer_name,
            "salesTyCd": "N", # Normal sales
            "rcptTyCd": "S",  
            "pmtTyCd": export_sale_data.get("payment_type_code", "01"), # Default to "01" (Cash) if not provided
            "salesSttsCd": "02", # Assuming 'Approved' for a sales request
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "stockRlsDt": export_sale_data.get("stock_release_date") or None, # Optional
            "cnclReqDt": export_sale_data.get("cancellation_request_date") or None, # Optional
            "cnclDt": export_sale_data.get("cancellation_date") or None, # Optional
            "rfdDt": export_sale_data.get("refund_date") or None, # Optional
            "rfdRsnCd": export_sale_data.get("refund_reason_code", ""), # Optional
            "totItemCnt": len(item_list),
            
            # Individual tax category taxable amounts
            "taxblAmtA": flt(category_totals['A']['taxable'], 4),
            "taxblAmtB": flt(category_totals['B']['taxable'], 4),
            "taxblAmtC1": flt(category_totals['C1']['taxable'], 4),
            "taxblAmtC2": flt(category_totals['C2']['taxable'], 4),
            "taxblAmtC3": flt(category_totals['C3']['taxable'], 4),
            "taxblAmtD": flt(category_totals['D']['taxable'], 4),
            "taxblAmtRvat": flt(category_totals['RVAT']['taxable'], 4),
            "taxblAmtE": flt(category_totals['E']['taxable'], 4),
            "taxblAmtF": flt(category_totals['F']['taxable'], 4),
            "taxblAmtIpl1": flt(special_tax_totals['ipl1']['taxable'], 4),
            "taxblAmtIpl2": flt(special_tax_totals['ipl2']['taxable'], 4),
            "taxblAmtTl": flt(special_tax_totals['tl']['taxable'], 4),
            "taxblAmtEcm": flt(special_tax_totals['ecm']['taxable'], 4),
            "taxblAmtExeeg": flt(special_tax_totals['exeeg']['taxable'], 4),
            "taxblAmtTot": 0.0, # Check documentation, often for TOT (Turnover Tax) if applicable
            
            # Tax rates (fixed as per documentation)
            "taxRtA": 16,
            "taxRtB": 16,
            "taxRtC1": 0,
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "taxRtRvat": 16,
            "taxRtE": 0,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtIpl2": 0,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            
            # Individual tax category amounts (corrected names)
            "taxAmtA": flt(category_totals['A']['tax'], 4),
            "taxAmtB": flt(category_totals['B']['tax'], 4),
            "taxAmtC1": flt(category_totals['C1']['tax'], 4),
            "taxAmtC2": flt(category_totals['C2']['tax'], 4),
            "taxAmtC3": flt(category_totals['C3']['tax'], 4),
            "taxAmtD": flt(category_totals['D']['tax'], 4),
            "taxAmtRvat": flt(category_totals['RVAT']['tax'], 4),
            "taxAmtE": flt(category_totals['E']['tax'], 4),
            "taxAmtF": flt(category_totals['F']['tax'], 4),
            "taxAmtIpl1": flt(special_tax_totals['ipl1']['tax'], 4), # Corrected name
            "taxAmtIpl2": flt(special_tax_totals['ipl2']['tax'], 4), # Corrected name
            "taxAmtTl": flt(special_tax_totals['tl']['tax'], 4), # Corrected name
            "taxAmtEcm": flt(special_tax_totals['ecm']['tax'], 4), # Corrected name
            "taxAmtExeeg": flt(special_tax_totals['exeeg']['tax'], 4), # Corrected name
            "taxAmtTot": 0.0, # For Turnover Tax, if applicable
            
            # Totals
            "totTaxblAmt": flt(total_taxable_amount, 2), # As per doc (18,2)
            "totTaxAmt": flt(total_tax_amount, 2), # As per doc (18,2)
            "totAmt": flt(totals['total_tax_inclusive_amount'], 2), # Total tax-inclusive invoice amount
            
            # Other fields
            "cashDcRt": flt(export_sale_data.get("cash_discount_rate", 0.0), 4),
            "cashDcAmt": flt(export_sale_data.get("cash_discount_amount", 0.0), 4),
            "prchrAcptcYn": "Y", # Assuming "Y" for a new export sale, as per doc "Yes or No"
            "remark": export_sale_data.get("remarks") or "",
            "regrId": created_by,
            "regrNm": created_by,
            "modrId": created_by,
            "modrNm": created_by,
            "saleCtyCd": "1", # As per doc (pass 1)
            "lpoNumber": export_sale_data.get("lpo_number") or None,
            "currencyTyCd": currency,
            "exchangeRt": flt(export_sale_data.get("exchange_rate", 1.0), 4), # Ensure this is a float
            "destnCountryCd": destnCountryCd, 
            "dbtRsnCd": "",  # Empty for sales, only for debit notes
            "invcAdjustReason": "", # Empty for sales, only for debit notes
            "itemList": item_list
        }

        print("\n--- Export Sale Payload Constructed ---", destnCountryCd)
        print(payload)

        response = self.call_export_sale_client(payload)
        
        # Fix: Parse the JSON response first, then use .get() on the parsed data
        try:
            if hasattr(response, "json"):
                response_data = response.json()
            else:
                # If response doesn't have .json(), it might be a direct dict from mock
                response_data = response 
        except Exception as e:
            frappe.throw(f"Failed to parse response JSON: {e}")

        # Use response_data instead of response for dictionary operations
        if response_data.get("resultCd") == "000":
            if response_data.get("data") and response_data["data"].get("rcptNo"):
                rcpt_no = response_data["data"]["rcptNo"]
                doc_name = export_sale_data.get("name")
                self.update_rcptNo_delayed(docname=doc_name, rcpt_no=rcpt_no)
                frappe.msgprint(f"Export Sale created successfully. Receipt No: {rcpt_no}")
            else:
                frappe.msgprint("Export Sale created successfully but no receipt number was returned.")

            ocrnDt = datetime.now().strftime("%Y%m%d")
            update_stock_item = []
            update_stock_master_items = []

            for item in item_list:
                # Calculate total taxable and tax amounts for this item based on the line item's individual taxable/tax amounts
                item_total_taxable = item.get("vatTaxblAmt", 0) + item.get("exciseTaxblAmt", 0) + \
                                    item.get("tlTaxblAmt", 0) + item.get("iplTaxblAmt", 0)
                item_total_tax = item.get("vatAmt", 0) + item.get("exciseTxAmt", 0) + \
                                item.get("tlAmt", 0) + item.get("iplAmt", 0)
                
                update_stock_item.append({
                    "itemSeq": item.get("itemSeq"),
                    "itemCd": item.get("itemCd"),
                    "itemClsCd": item.get("itemClsCd"),
                    "itemNm": item.get("itemNm"),
                    "pkgUnitCd": item.get("pkgUnitCd"),
                    "qtyUnitCd": item.get("qtyUnitCd"),
                    "qty": item.get("qty"),
                    "prc": item.get("prc"),
                    "splyAmt": item.get("splyAmt"), # This is the gross supply amount from the sales payload
                    "taxblAmt": flt(item_total_taxable, 4), # Total taxable amount for this line item across all taxes
                    "vatCatCd": item.get("vatCatCd"),
                    "taxAmt": flt(item_total_tax, 4), # Total tax amount for this line item across all taxes
                    "totAmt": item.get("totAmt"), # Total tax-inclusive amount for this line item
                    "pkg": item.get("pkg"),
                    "totDcAmt": item.get("dcAmt", 0),
                })
                
                # Get actual remaining quantity from bins (subtract the sold qty for an export sale)
                # This assumes 'actual_qty' refers to available stock that needs to be reduced.
                bins = frappe.db.get_all("Bin", filters={"item_code": item.get("itemCd")}, fields=["actual_qty"])
                remaining_qty = sum(flt(b.get("actual_qty", 0)) for b in bins) - item.get("qty", 0)
                
                update_stock_master_items.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": max(0, remaining_qty) # Ensure quantity doesn't go negative
                })

            # Payload for updating stock after sales (sarTyCd "02" for "Sale")
            update_stock_payload = {
                "tpin": self.tpin,
                "bhfId": self.branch_code,
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

            self.run_stock_update_in_background(update_stock_payload, update_stock_master_items, created_by)
        else:
            frappe.throw(f"Failed to create Export Sale: {response_data.get('resultMsg', 'Unknown error')}")

    def create_lpo_sale_transaction_payload(self, lpo_data):
        now = datetime.now()

        customer_name = lpo_data.get("customer") or lpo_data.get("customer_name") or ""
        customer_doc = frappe.get_doc("Customer", customer_name) if customer_name else None
        customer_tpin = customer_doc.get("custom_customer_tpin") if customer_doc else ""
        lpo_number = lpo_data.get("custom_lpo_number")
        if lpo_number is None or not (9 <= len(lpo_number) <= 20):
            frappe.throw("The LPO Number must be between 9 and 20 characters long.")
        
        # For export sales, cisInvcNo should be the system's generated invoice number
        cisInvcNo = lpo_data.get("name", f"EXP-{random.randint(1000,9999)}")
        
        # orgInvcNo should only be present for credit/debit notes. For a new export sale, it should be null or 0.
        # Assuming for a 'Save Sales Request - Exports' this is a new sale, not a linked one.
 

        created_by = lpo_data.get("owner") or "system"
        currency = lpo_data.get("currency") or "ZMW"
        
        # Destination Country Code (Required for Exports)
        destn_country = lpo_data.get("custom_destination_country")
        destnCountryCd = ""
        if destn_country:
            try:
                # Assuming an external service to get country code from country name
                res = requests.get(f"http://0.0.0.0:7000/country/{quote(destn_country)}/", timeout=10)
                res.raise_for_status()
                country_data = res.json()
                destnCountryCd = country_data.get("code")
                if not destnCountryCd:
                    frappe.throw(f"Country code not found for '{destn_country}' from external API response: {country_data}")
            except requests.exceptions.Timeout:
                frappe.throw(f"Timeout fetching country code for '{destn_country}'.")
            except requests.RequestException as e:
                frappe.throw(f"Error fetching country code for '{destn_country}' from external API: {e}")
        else:
            frappe.throw("Destination Country is required for Export Sales.")

        # Special check: If destination country is ZM (Zambia's code, assuming your system recognizes it),
        # then it's not a true export, even if custom_destination_country was set.
        # This prevents the `destnCountryCd` error from the API if ZM is mistakenly set for an export.
        if destnCountryCd == "ZM":
            frappe.throw(f"For an Export Sale, the destination country '{destn_country}' cannot be Zambia ({destnCountryCd}). Please select a foreign country.")


        category_totals = {
            'A': {'taxable': 0.0, 'tax': 0.0},
            'B': {'taxable': 0.0, 'tax': 0.0},
            'C1': {'taxable': 0.0, 'tax': 0.0}, # Exports
            'C2': {'taxable': 0.0, 'tax': 0.0},
            'C3': {'taxable': 0.0, 'tax': 0.0},
            'D': {'taxable': 0.0, 'tax': 0.0},
            'RVAT': {'taxable': 0.0, 'tax': 0.0},
            'E': {'taxable': 0.0, 'tax': 0.0},
            'F': {'taxable': 0.0, 'tax': 0.0}
        }
        
        special_tax_totals = {
            'ipl1': {'taxable': 0.0, 'tax': 0.0},
            'ipl2': {'taxable': 0.0, 'tax': 0.0},
            'tl': {'taxable': 0.0, 'tax': 0.0},
            'ecm': {'taxable': 0.0, 'tax': 0.0},
            'exeeg': {'taxable': 0.0, 'tax': 0.0}
        }

        totals = {'gross': 0.0, 'discount': 0.0, 'net': 0.0, 'total_tax_inclusive_amount': 0.0}
        item_list = []
        items = lpo_data.get("items", [])
        
        for i, item in enumerate(items, 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)

            
            qty = abs(flt(item.get("qty", 1))) 
            price = flt(item.get("rate") or item_doc.get("standard_rate", 0)) 
            packaging_unit = item_doc.get("custom_packaging_unit_code", "").strip()
            unit_name = item_doc.get("custom_units_of_measure", "").strip()
            print("Unit name: ", unit_name)
            
            # This is the tax-inclusive amount for the line item
            gross_line_amount = flt(qty * price, 4) 

            discount_pct = flt(item.get("discount_percentage", 0))
            discount_amt = flt(gross_line_amount * discount_pct / 100, 4)
            
            # Net amount after discount, still tax-inclusive for now
            net_line_amount = flt(gross_line_amount - discount_amt, 4)

            # Retrieve custom fields from item_doc
            ipl_doc_cat = (item_doc.get("custom_ipl_category_code") or "").strip()
            excise_doc_cat = (item_doc.get("custom_excise_tax_category_code") or "").strip()
            tl_doc_cat = (item_doc.get("custom_tourism_levy") or "").strip()
            vat_doc_cat = (item_doc.get("custom_vat") or "").strip()
            print(ipl_doc_cat, excise_doc_cat, tl_doc_cat, vat_doc_cat)


            # VAT Mapping (based on documentation)
            vat_map = {
                "StandardRated": "A", "MinimumTaxableValue": "B", "Exports": "C1",
                "ZeroRatingLocalPurchases": "C2", "ZeroRatedByNature": "C3",
                "Exempt": "D", "Disbursement": "E", "ServiceCharge10%": "F", "ReverseVAT": "RVAT"
            }
            
            # --- VAT Category Validation ---
            vatCatCd = "C2"
            
            if not vatCatCd:
                frappe.throw(f"Invalid or missing VAT category '{vat_doc_cat}' configured for item '{item_code}'. Please ensure it is one of the recognized types (e.g., 'Exports', 'StandardRated').")
            
            # Second, if it's an export sale, strongly recommend C1
            # Assuming that if this function `create_export_sale_payload` is called, it IS an export sale.
            if vatCatCd not in ["A1", "A", "C2"]:
                print(vatCatCd)
                frappe.throw(
                    f"For LPO transactions, the item '{item_code}' has a VAT category of '{vat_doc_cat}' (mapped to '{vatCatCd}'). "
                    f"Items in LPO transactions should be categorized under 'StandardRated' (A1) or 'Exports' (C2). Please correct the VAT category for this item."
                )


            # --- End VAT Category Validation ---

            # Excise Tax Mapping
            exciseTxCatCd = ""
            if excise_doc_cat == "Excise on Coal":
                exciseTxCatCd = "ECM"
            elif excise_doc_cat == "Excise Electricity":
                exciseTxCatCd = "EXEEG"

            # IPL Mapping
            iplCatCd = ""
            if ipl_doc_cat == "Insurance Premium Levy":
                iplCatCd = "IPL1"
            elif ipl_doc_cat == "Re-Insurance":
                iplCatCd = "IPL2"

            # Tourism Levy Mapping
            tlCatCd = "TL" if tl_doc_cat == "Tourism Levy" else ""

            zra_qty_unit_code = item_doc.get("custom_zra_qty_unit_code", "EA")
            
            # --- Tax Calculation Logic (Revised for clarity and consistency) ---
            # Assume net_line_amount is the tax-inclusive amount after discount for a particular line item.
            # We need to extract the taxable base and the tax amount for each category.

            vat_taxable = 0.0
            vat_amount = 0.0
            excise_taxable = 0.0
            excise_amount = 0.0
            ipl_taxable = 0.0
            ipl_amount = 0.0
            tl_taxable = 0.0
            tl_amount = 0.0
            
            # This 'taxable_base_for_other_taxes' will be the tax-exclusive amount from VAT calculation.
            taxable_base_for_other_taxes = net_line_amount 

            # Since we are enforcing vatCatCd == "C1" for export sales in the validation step above,
            # this section can be simplified for export sales, but keeping the full structure
            # allows this function to potentially be adapted or ensures robustness.
            if vatCatCd == "A":  # Standard Rated 16%
                vat_taxable = flt(net_line_amount / 1.16, 4)
                vat_amount = flt(vat_taxable * 0.16, 4)
                taxable_base_for_other_taxes = vat_taxable
            elif vatCatCd == "B":  # Minimum Taxable Value 16%
                vat_taxable = flt(net_line_amount / 1.16, 4)
                vat_amount = flt(vat_taxable * 0.16, 4)
                taxable_base_for_other_taxes = vat_taxable
            elif vatCatCd == "F":  # Service Charge 10%
                vat_taxable = flt(net_line_amount / 1.10, 4)
                vat_amount = flt(vat_taxable * 0.10, 4)
                taxable_base_for_other_taxes = vat_taxable
            elif vatCatCd == "RVAT":  # Reverse VAT 16%
                vat_taxable = flt(net_line_amount / 1.16, 4)
                vat_amount = flt(vat_taxable * 0.16, 4)
                taxable_base_for_other_taxes = vat_taxable
            # For C1, C2, C3, D, E (Zero rated or Exempt for VAT)
            else:  
                vat_taxable = net_line_amount # For zero-rated/exempt, the whole amount is taxable base
                vat_amount = 0.0 # This will be the case for C1
                taxable_base_for_other_taxes = vat_taxable # Still use this for other tax calculations


            # Calculate special taxes based on the determined taxable_base_for_other_taxes
            if exciseTxCatCd == "ECM":  # 5%
                excise_taxable = taxable_base_for_other_taxes
                excise_amount = flt(excise_taxable * 0.05, 4)
            elif exciseTxCatCd == "EXEEG":  # 3%
                excise_taxable = taxable_base_for_other_taxes
                excise_amount = flt(excise_taxable * 0.03, 4)

            if iplCatCd == "IPL1":  # 5%
                ipl_taxable = taxable_base_for_other_taxes
                ipl_amount = flt(ipl_taxable * 0.05, 4)
            elif iplCatCd == "IPL2":  # 0%
                ipl_taxable = taxable_base_for_other_taxes
                ipl_amount = 0.0 # Re-Insurance is 0%

            if tlCatCd == "TL":  # 1.5%
                tl_taxable = taxable_base_for_other_taxes
                tl_amount = flt(tl_taxable * 0.015, 4)

            # Recalculate `totAmt` to be just `net_line_amount` (after discount, before splitting taxes)
            total_amount_line_item = net_line_amount

            # Update category totals for the main payload
            if vatCatCd in category_totals:
                category_totals[vatCatCd]['taxable'] += vat_taxable
                category_totals[vatCatCd]['tax'] += vat_amount

            if exciseTxCatCd == "ECM":
                special_tax_totals['ecm']['taxable'] += excise_taxable
                special_tax_totals['ecm']['tax'] += excise_amount
            elif exciseTxCatCd == "EXEEG":
                special_tax_totals['exeeg']['taxable'] += excise_taxable
                special_tax_totals['exeeg']['tax'] += excise_amount

            if iplCatCd == "IPL1":
                special_tax_totals['ipl1']['taxable'] += ipl_taxable
                special_tax_totals['ipl1']['tax'] += ipl_amount
            elif iplCatCd == "IPL2":
                special_tax_totals['ipl2']['taxable'] += ipl_taxable
                special_tax_totals['ipl2']['tax'] += ipl_amount

            if tlCatCd == "TL":
                special_tax_totals['tl']['taxable'] += tl_taxable
                special_tax_totals['tl']['tax'] += tl_amount

            totals['gross'] += gross_line_amount
            totals['discount'] += discount_amt
            totals['net'] += net_line_amount # This is the net tax-inclusive amount per line item
            totals['total_tax_inclusive_amount'] += total_amount_line_item

            # Get RRP (Recommended Retail Price) for MTV items
            rrp = 0.0
            if vatCatCd == "B": # Minimum Taxable Value requires RRP
                rrp = flt(item_doc.get("custom_rrp") or item_doc.get("custom_recommended_retail_price") or price, 4)
            
            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": item_doc.get("custom_item_classification_code", "50102518"), # Assuming a default if not set
                "itemNm": item.get("item_name"),
                "bcd": item_doc.get("barcode", ""),
                "pkgUnitCd": "WRAP",
                "pkg": item.get("pkg", 1),
                "qtyUnitCd": "EA",
                "qty": qty,
                "prc": flt(price, 4),
                "splyAmt": flt(gross_line_amount, 4), # Total supply amount for the line (qty * price)
                "dcRt": flt(discount_pct, 2),
                "dcAmt": flt(discount_amt, 2),
                "isrccCd": item.get("insurance_company_code", ""),
                "isrccNm": item.get("insurance_company_name", ""),
                "isrcAmt": flt(item.get("insurance_amount", 0.0), 4), # Assuming this comes from item data
                "vatCatCd": vatCatCd,
                "exciseTxCatCd": exciseTxCatCd if exciseTxCatCd else None, # Null if not applicable
                "vatTaxblAmt": flt(vat_taxable, 4),
                "exciseTaxblAmt": flt(excise_taxable, 4),
                "tlTaxblAmt": flt(tl_taxable, 4),
                "iplTaxblAmt": flt(ipl_taxable, 4),
                "iplAmt": flt(ipl_amount, 4),
                "tlAmt": flt(tl_amount, 4),
                "vatAmt": flt(vat_amount, 4),
                "exciseTxAmt": flt(excise_amount, 4),
                "totAmt": flt(total_amount_line_item, 2), # Total tax inclusive amount of the line item
                "rrp": flt(rrp, 4) # Only required for MTV items, otherwise 0.0 or null
            })

        # Calculate total taxable and total tax amounts for the entire invoice
        # Sum of all individual taxable amounts for each tax type
        total_taxable_amount = sum(cat['taxable'] for cat in category_totals.values()) + \
                            sum(cat['taxable'] for cat in special_tax_totals.values())
        
        # Sum of all individual tax amounts for each tax type
        total_tax_amount = sum(cat['tax'] for cat in category_totals.values()) + \
                        sum(cat['tax'] for cat in special_tax_totals.values())

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "orgSdcId": "SDC0010002709",
            "cisInvcNo": cisInvcNo,
            "orgInvcNo": 0, 
            "custTpin": "1002328764",
            "salesTyCd": "N", 
            "rcptTyCd": "S",  
            "pmtTyCd": lpo_data.get("payment_type_code", "01"), 
            "salesSttsCd": "02", # Assuming 'Approved' for a sales request
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "stockRlsDt": lpo_data.get("stock_release_date") or None, # Optional
            "cnclReqDt": lpo_data.get("cancellation_request_date") or None, # Optional
            "cnclDt": lpo_data.get("cancellation_date") or None, # Optional
            "rfdDt": lpo_data.get("refund_date") or None, # Optional
            "rfdRsnCd": lpo_data.get("refund_reason_code", ""), # Optional
            "totItemCnt": len(item_list),
            
            # Individual tax category taxable amounts
            "taxblAmtA": flt(category_totals['A']['taxable'], 4),
            "taxblAmtB": flt(category_totals['B']['taxable'], 4),
            "taxblAmtC1": flt(category_totals['C1']['taxable'], 4),
            "taxblAmtC2": flt(category_totals['C2']['taxable'], 4),
            "taxblAmtC3": flt(category_totals['C3']['taxable'], 4),
            "taxblAmtD": flt(category_totals['D']['taxable'], 4),
            "taxblAmtRvat": flt(category_totals['RVAT']['taxable'], 4),
            "taxblAmtE": flt(category_totals['E']['taxable'], 4),
            "taxblAmtF": flt(category_totals['F']['taxable'], 4),
            "taxblAmtIpl1": flt(special_tax_totals['ipl1']['taxable'], 4),
            "taxblAmtIpl2": flt(special_tax_totals['ipl2']['taxable'], 4),
            "taxblAmtTl": flt(special_tax_totals['tl']['taxable'], 4),
            "taxblAmtEcm": flt(special_tax_totals['ecm']['taxable'], 4),
            "taxblAmtExeeg": flt(special_tax_totals['exeeg']['taxable'], 4),
            "taxblAmtTot": 0.0, # Check documentation, often for TOT (Turnover Tax) if applicable
            
            # Tax rates (fixed as per documentation)
            "taxRtA": 16,
            "taxRtB": 16,
            "taxRtC1": 0,
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "taxRtRvat": 16,
            "taxRtE": 0,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtIpl2": 0,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            
            # Individual tax category amounts (corrected names)
            "taxAmtA": flt(category_totals['A']['tax'], 4),
            "taxAmtB": flt(category_totals['B']['tax'], 4),
            "taxAmtC1": flt(category_totals['C1']['tax'], 4),
            "taxAmtC2": flt(category_totals['C2']['tax'], 4),
            "taxAmtC3": flt(category_totals['C3']['tax'], 4),
            "taxAmtD": flt(category_totals['D']['tax'], 4),
            "taxAmtRvat": flt(category_totals['RVAT']['tax'], 4),
            "taxAmtE": flt(category_totals['E']['tax'], 4),
            "taxAmtF": flt(category_totals['F']['tax'], 4),
            "taxAmtIpl1": flt(special_tax_totals['ipl1']['tax'], 4), # Corrected name
            "taxAmtIpl2": flt(special_tax_totals['ipl2']['tax'], 4), # Corrected name
            "taxAmtTl": flt(special_tax_totals['tl']['tax'], 4), # Corrected name
            "taxAmtEcm": flt(special_tax_totals['ecm']['tax'], 4), # Corrected name
            "taxAmtExeeg": flt(special_tax_totals['exeeg']['tax'], 4), # Corrected name
            "taxAmtTot": 0.0, # For Turnover Tax, if applicable
            
            # Totals
            "totTaxblAmt": flt(total_taxable_amount, 2), # As per doc (18,2)
            "totTaxAmt": flt(total_tax_amount, 2), # As per doc (18,2)
            "totAmt": flt(totals['total_tax_inclusive_amount'], 2), # Total tax-inclusive invoice amount
            
            # Other fields
            "cashDcRt": flt(lpo_data.get("cash_discount_rate", 0.0), 4),
            "cashDcAmt": flt(lpo_data.get("cash_discount_amount", 0.0), 4),
            "prchrAcptcYn": "Y", # Assuming "Y" for a new export sale, as per doc "Yes or No"
            "remark": lpo_data.get("remarks") or "",
            "regrId": created_by,
            "regrNm": created_by,
            "modrId": created_by,
            "modrNm": created_by,
            "saleCtyCd": "1", 
            "lpoNumber": lpo_number,
            "currencyTyCd": currency,
            "exchangeRt": flt(lpo_data.get("exchange_rate", 1.0), 4),
            "dbtRsnCd": "", 
            "invcAdjustReason": "", 
            "itemList": item_list
        }

        print("\n--- LPO Sale Payload Constructed ---", destnCountryCd)
        print(payload)

        response = self.call_lpo_sale_client(payload)
        
        # Fix: Parse the JSON response first, then use .get() on the parsed data
        try:
            if hasattr(response, "json"):
                response_data = response.json()
            else:
                # If response doesn't have .json(), it might be a direct dict from mock
                response_data = response 
        except Exception as e:
            frappe.throw(f"Failed to parse response JSON: {e}")

        # Use response_data instead of response for dictionary operations
        if response_data.get("resultCd") == "000":
            if response_data.get("data") and response_data["data"].get("rcptNo"):
                rcpt_no = response_data["data"]["rcptNo"]
                doc_name = lpo_data.get("name")
                self.update_rcptNo_delayed(docname=doc_name, rcpt_no=rcpt_no)
                frappe.msgprint(f"Export Sale created successfully. Receipt No: {rcpt_no}")
            else:
                frappe.msgprint("Export Sale created successfully but no receipt number was returned.")

            ocrnDt = datetime.now().strftime("%Y%m%d")
            update_stock_item = []
            update_stock_master = []

            for item in item_list:
                # Calculate total taxable and tax amounts for this item based on the line item's individual taxable/tax amounts
                item_total_taxable = item.get("vatTaxblAmt", 0) + item.get("exciseTaxblAmt", 0) + \
                                    item.get("tlTaxblAmt", 0) + item.get("iplTaxblAmt", 0)
                item_total_tax = item.get("vatAmt", 0) + item.get("exciseTxAmt", 0) + \
                                item.get("tlAmt", 0) + item.get("iplAmt", 0)
                
                update_stock_item.append({
                    "itemSeq": item.get("itemSeq"),
                    "itemCd": item.get("itemCd"),
                    "itemClsCd": item.get("itemClsCd"),
                    "itemNm": item.get("itemNm"),
                    "pkgUnitCd": item.get("pkgUnitCd"),
                    "qtyUnitCd": item.get("qtyUnitCd"),
                    "qty": item.get("qty"),
                    "prc": item.get("prc"),
                    "splyAmt": item.get("splyAmt"), # This is the gross supply amount from the sales payload
                    "taxblAmt": flt(item_total_taxable, 4), # Total taxable amount for this line item across all taxes
                    "vatCatCd": item.get("vatCatCd"),
                    "taxAmt": flt(item_total_tax, 4), # Total tax amount for this line item across all taxes
                    "totAmt": item.get("totAmt"), # Total tax-inclusive amount for this line item
                    "pkg": item.get("pkg"),
                    "totDcAmt": item.get("dcAmt", 0),
                })
                
                # Get actual remaining quantity from bins (subtract the sold qty for an export sale)
                # This assumes 'actual_qty' refers to available stock that needs to be reduced.
                bins = frappe.db.get_all("Bin", filters={"item_code": item.get("itemCd")}, fields=["actual_qty"])
                remaining_qty = sum(flt(b.get("actual_qty", 0)) for b in bins) - item.get("qty", 0)
                
                update_stock_master.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": max(0, remaining_qty) # Ensure quantity doesn't go negative
                })

            # Payload for updating stock after sales (sarTyCd "02" for "Sale")
            update_stock_payload = {
                "tpin": self.tpin,
                "bhfId": self.branch_code,
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
            print("Update stock response:", call_update_stock_after_purchase)
            
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
                print("Update stock master response:", call_update_stock_master_after_purchase)
                
            else:
                frappe.throw(f"Failed to update detailed stock: {call_update_stock_after_purchase.get('resultMsg', 'Unknown error')}")
        else:
            frappe.throw(f"{response_data.get('resultMsg', 'Unknown error').replace('Request parameter error: ', '')}")

    def get_principal(self):

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "lastReqDt":"20240123121449"
        }
        self.call_get_principal(payload)

        

    def create_rvat_with_agent_sale(self, rvat_data):
        data = self.get_principal()
        print(data)
        now = datetime.now()

        customer_name = rvat_data.get("customer") or rvat_data.get("customer_name") or ""
        customer_doc = frappe.get_doc("Customer", customer_name) if customer_name else None
        customer_tpin = customer_doc.get("custom_customer_tpin") if customer_doc else ""
        
        cisInvcNo = rvat_data.get("name", f"EXP-{random.randint(1000,9999)}")
        

 

        created_by = rvat_data.get("owner") or "system"
        currency = rvat_data.get("currency") or "ZMW"
        
        # Destination Country Code (Required for Exports)
        destn_country = rvat_data.get("custom_destination_country")
        destnCountryCd = ""
        if destn_country:
            try:
                # Assuming an external service to get country code from country name
                res = requests.get(f"http://0.0.0.0:7000/country/{quote(destn_country)}/", timeout=10)
                res.raise_for_status()
                country_data = res.json()
                destnCountryCd = country_data.get("code")
                if not destnCountryCd:
                    frappe.throw(f"Country code not found for '{destn_country}' from external API response: {country_data}")
            except requests.exceptions.Timeout:
                frappe.throw(f"Timeout fetching country code for '{destn_country}'.")
            except requests.RequestException as e:
                frappe.throw(f"Error fetching country code for '{destn_country}' from external API: {e}")
        else:
            frappe.throw("Destination Country is required for Export Sales.")

        # Special check: If destination country is ZM (Zambia's code, assuming your system recognizes it),
        # then it's not a true export, even if custom_destination_country was set.
        # This prevents the `destnCountryCd` error from the API if ZM is mistakenly set for an export.
        if destnCountryCd == "ZM":
            frappe.throw(f"For an Export Sale, the destination country '{destn_country}' cannot be Zambia ({destnCountryCd}). Please select a foreign country.")


        category_totals = {
            'A': {'taxable': 0.0, 'tax': 0.0},
            'B': {'taxable': 0.0, 'tax': 0.0},
            'C1': {'taxable': 0.0, 'tax': 0.0}, # Exports
            'C2': {'taxable': 0.0, 'tax': 0.0},
            'C3': {'taxable': 0.0, 'tax': 0.0},
            'D': {'taxable': 0.0, 'tax': 0.0},
            'RVAT': {'taxable': 0.0, 'tax': 0.0},
            'E': {'taxable': 0.0, 'tax': 0.0},
            'F': {'taxable': 0.0, 'tax': 0.0}
        }
        
        special_tax_totals = {
            'ipl1': {'taxable': 0.0, 'tax': 0.0},
            'ipl2': {'taxable': 0.0, 'tax': 0.0},
            'tl': {'taxable': 0.0, 'tax': 0.0},
            'ecm': {'taxable': 0.0, 'tax': 0.0},
            'exeeg': {'taxable': 0.0, 'tax': 0.0}
        }

        totals = {'gross': 0.0, 'discount': 0.0, 'net': 0.0, 'total_tax_inclusive_amount': 0.0}
        item_list = []
        items = rvat_data.get("items", [])
        
        for i, item in enumerate(items, 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)

            
            qty = abs(flt(item.get("qty", 1))) 
            price = flt(item.get("rate") or item_doc.get("standard_rate", 0)) 
            packaging_unit = item_doc.get("custom_packaging_unit_code", "").strip()
            unit_name = item_doc.get("custom_units_of_measure", "").strip()
            print("Unit name: ", unit_name)
            
            # This is the tax-inclusive amount for the line item
            gross_line_amount = flt(qty * price, 4) 

            discount_pct = flt(item.get("discount_percentage", 0))
            discount_amt = flt(gross_line_amount * discount_pct / 100, 4)
            
            # Net amount after discount, still tax-inclusive for now
            net_line_amount = flt(gross_line_amount - discount_amt, 4)

            # Retrieve custom fields from item_doc
            ipl_doc_cat = (item_doc.get("custom_ipl_category_code") or "").strip()
            excise_doc_cat = (item_doc.get("custom_excise_tax_category_code") or "").strip()
            tl_doc_cat = (item_doc.get("custom_tourism_levy") or "").strip()
            vat_doc_cat = (item_doc.get("custom_vat") or "").strip()
            print(ipl_doc_cat, excise_doc_cat, tl_doc_cat, vat_doc_cat)


            # VAT Mapping (based on documentation)
            vat_map = {
                "StandardRated": "A", "MinimumTaxableValue": "B", "Exports": "C1",
                "ZeroRatingLocalPurchases": "C2", "ZeroRatedByNature": "C3",
                "Exempt": "D", "Disbursement": "E", "ServiceCharge10%": "F", "ReverseVAT": "RVAT"
            }
            
            # --- VAT Category Validation ---
            vatCatCd = vat_map.get(vat_doc_cat) 
            
            if not vatCatCd:
                frappe.throw(f"Invalid or missing VAT category '{vat_doc_cat}' configured for item '{item_code}'. Please ensure it is one of the recognized types (e.g., 'Exports', 'StandardRated').")
            
            # Second, if it's an export sale, strongly recommend C1
            # The original comment was incorrect, the logic was for LPO transactions.
            # Assuming that if this function `create_rvat_with_agent_sale` is called, it IS an agent sale.
            if vatCatCd != "RVAT":
                print(vatCatCd)
                frappe.throw(
                    f"For agent sales, the item '{item_code}' has a VAT category of '{vat_doc_cat}' (mapped to '{vatCatCd}'). "
                    f"Items in agent sales transactions should be categorized under 'ReverseVAT' (RVAT). Please correct the VAT category for this item."
                )

            # --- End VAT Category Validation ---

            # Excise Tax Mapping
            exciseTxCatCd = ""
            if excise_doc_cat == "Excise on Coal":
                exciseTxCatCd = "ECM"
            elif excise_doc_cat == "Excise Electricity":
                exciseTxCatCd = "EXEEG"

            # IPL Mapping
            iplCatCd = ""
            if ipl_doc_cat == "Insurance Premium Levy":
                iplCatCd = "IPL1"
            elif ipl_doc_cat == "Re-Insurance":
                iplCatCd = "IPL2"

            # Tourism Levy Mapping
            tlCatCd = "TL" if tl_doc_cat == "Tourism Levy" else ""

            zra_qty_unit_code = item_doc.get("custom_zra_qty_unit_code", "EA")
            
            # --- Tax Calculation Logic (Revised for clarity and consistency) ---
            # Assume net_line_amount is the tax-inclusive amount after discount for a particular line item.
            # We need to extract the taxable base and the tax amount for each category.

            vat_taxable = 0.0
            vat_amount = 0.0
            excise_taxable = 0.0
            excise_amount = 0.0
            ipl_taxable = 0.0
            ipl_amount = 0.0
            tl_taxable = 0.0
            tl_amount = 0.0
            
            # This 'taxable_base_for_other_taxes' will be the tax-exclusive amount from VAT calculation.
            taxable_base_for_other_taxes = net_line_amount 

            # Since we are enforcing vatCatCd == "RVAT" for agent sales in the validation step above,
            # this section can be simplified for agent sales, but keeping the full structure
            # allows this function to potentially be adapted or ensures robustness.
            if vatCatCd == "A":  # Standard Rated 16%
                vat_taxable = flt(net_line_amount / 1.16, 4)
                vat_amount = flt(vat_taxable * 0.16, 4)
                taxable_base_for_other_taxes = vat_taxable
            elif vatCatCd == "B":  # Minimum Taxable Value 16%
                vat_taxable = flt(net_line_amount / 1.16, 4)
                vat_amount = flt(vat_taxable * 0.16, 4)
                taxable_base_for_other_taxes = vat_taxable
            elif vatCatCd == "F":  # Service Charge 10%
                vat_taxable = flt(net_line_amount / 1.10, 4)
                vat_amount = flt(vat_taxable * 0.10, 4)
                taxable_base_for_other_taxes = vat_taxable
            elif vatCatCd == "RVAT":  # Reverse VAT 16%
                vat_taxable = flt(net_line_amount / 1.16, 4)
                vat_amount = flt(vat_taxable * 0.16, 4)
                taxable_base_for_other_taxes = vat_taxable
            # For C1, C2, C3, D, E (Zero rated or Exempt for VAT)
            else:  
                vat_taxable = net_line_amount # For zero-rated/exempt, the whole amount is taxable base
                vat_amount = 0.0 # This will be the case for C1
                taxable_base_for_other_taxes = vat_taxable # Still use this for other tax calculations


            # Calculate special taxes based on the determined taxable_base_for_other_taxes
            if exciseTxCatCd == "ECM":  # 5%
                excise_taxable = taxable_base_for_other_taxes
                excise_amount = flt(excise_taxable * 0.05, 4)
            elif exciseTxCatCd == "EXEEG":  # 3%
                excise_taxable = taxable_base_for_other_taxes
                excise_amount = flt(excise_taxable * 0.03, 4)

            if iplCatCd == "IPL1":  # 5%
                ipl_taxable = taxable_base_for_other_taxes
                ipl_amount = flt(ipl_taxable * 0.05, 4)
            elif iplCatCd == "IPL2":  # 0%
                ipl_taxable = taxable_base_for_other_taxes
                ipl_amount = 0.0 # Re-Insurance is 0%

            if tlCatCd == "TL":  # 1.5%
                tl_taxable = taxable_base_for_other_taxes
                tl_amount = flt(tl_taxable * 0.015, 4)

            # Recalculate `totAmt` to be just `net_line_amount` (after discount, before splitting taxes)
            total_amount_line_item = net_line_amount

            # Update category totals for the main payload
            if vatCatCd in category_totals:
                category_totals[vatCatCd]['taxable'] += vat_taxable
                category_totals[vatCatCd]['tax'] += vat_amount

            if exciseTxCatCd == "ECM":
                special_tax_totals['ecm']['taxable'] += excise_taxable
                special_tax_totals['ecm']['tax'] += excise_amount
            elif exciseTxCatCd == "EXEEG":
                special_tax_totals['exeeg']['taxable'] += excise_taxable
                special_tax_totals['exeeg']['tax'] += excise_amount

            if iplCatCd == "IPL1":
                special_tax_totals['ipl1']['taxable'] += ipl_taxable
                special_tax_totals['ipl1']['tax'] += ipl_amount
            elif iplCatCd == "IPL2":
                special_tax_totals['ipl2']['taxable'] += ipl_taxable
                special_tax_totals['ipl2']['tax'] += ipl_amount

            if tlCatCd == "TL":
                special_tax_totals['tl']['taxable'] += tl_taxable
                special_tax_totals['tl']['tax'] += tl_amount

            totals['gross'] += gross_line_amount
            totals['discount'] += discount_amt
            totals['net'] += net_line_amount # This is the net tax-inclusive amount per line item
            totals['total_tax_inclusive_amount'] += total_amount_line_item

            # Get RRP (Recommended Retail Price) for MTV items
            rrp = 0.0
            if vatCatCd == "B": # Minimum Taxable Value requires RRP
                rrp = flt(item_doc.get("custom_rrp") or item_doc.get("custom_recommended_retail_price") or price, 4)
            
            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": item_doc.get("custom_item_classification_code", "50102518"), # Assuming a default if not set
                "itemNm": item.get("item_name"),
                "bcd": item_doc.get("barcode", ""),
                "pkgUnitCd": "WRAP",
                "pkg": item.get("pkg", 1),
                "qtyUnitCd": "EA",
                "qty": qty,
                "prc": flt(price, 4),
                "splyAmt": flt(gross_line_amount, 4), # Total supply amount for the line (qty * price)
                "dcRt": flt(discount_pct, 2),
                "dcAmt": flt(discount_amt, 2),
                "isrccCd": item.get("insurance_company_code", ""),
                "isrccNm": item.get("insurance_company_name", ""),
                "isrcAmt": flt(item.get("insurance_amount", 0.0), 4), # Assuming this comes from item data
                "vatCatCd": vatCatCd,
                "exciseTxCatCd": exciseTxCatCd if exciseTxCatCd else None, # Null if not applicable
                "vatTaxblAmt": flt(vat_taxable, 4),
                "exciseTaxblAmt": flt(excise_taxable, 4),
                "tlTaxblAmt": flt(tl_taxable, 4),
                "iplTaxblAmt": flt(ipl_taxable, 4),
                "iplAmt": flt(ipl_amount, 4),
                "tlAmt": flt(tl_amount, 4),
                "vatAmt": flt(vat_amount, 4),
                "exciseTxAmt": flt(excise_amount, 4),
                "totAmt": flt(total_amount_line_item, 2), # Total tax inclusive amount of the line item
                "rrp": flt(rrp, 4) # Only required for MTV items, otherwise 0.0 or null
            })

        # Calculate total taxable and total tax amounts for the entire invoice
        # Sum of all individual taxable amounts for each tax type
        total_taxable_amount = sum(cat['taxable'] for cat in category_totals.values()) + \
                            sum(cat['taxable'] for cat in special_tax_totals.values())
        
        # Sum of all individual tax amounts for each tax type
        total_tax_amount = sum(cat['tax'] for cat in category_totals.values()) + \
                        sum(cat['tax'] for cat in special_tax_totals.values())

        payload = {
            "tpin": self.tpin,
            "bhfId": self.branch_code,
            "orgSdcId": "SDC0010002709", # Verify this value or make it configurable
            "cisInvcNo": cisInvcNo,
            "orgInvcNo": 0, # Will be None for a new agent sale
            "custTpin": "1002328764",
            "custNm": customer_name,
            "salesTyCd": "N", 
            "rcptTyCd": "S",  
            "pmtTyCd": rvat_data.get("payment_type_code", "01"), 
            "salesSttsCd": "02", # Assuming 'Approved' for a sales request
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "stockRlsDt": rvat_data.get("stock_release_date") or None, # Optional
            "cnclReqDt": rvat_data.get("cancellation_request_date") or None, # Optional
            "cnclDt": rvat_data.get("cancellation_date") or None, # Optional
            "rfdDt": rvat_data.get("refund_date") or None, # Optional
            "rfdRsnCd": rvat_data.get("refund_reason_code", ""), # Optional
            "totItemCnt": len(item_list),
            
            # Individual tax category taxable amounts
            "taxblAmtA": flt(category_totals['A']['taxable'], 4),
            "taxblAmtB": flt(category_totals['B']['taxable'], 4),
            "taxblAmtC1": flt(category_totals['C1']['taxable'], 4),
            "taxblAmtC2": flt(category_totals['C2']['taxable'], 4),
            "taxblAmtC3": flt(category_totals['C3']['taxable'], 4),
            "taxblAmtD": flt(category_totals['D']['taxable'], 4),
            "taxblAmtRvat": flt(category_totals['RVAT']['taxable'], 4),
            "taxblAmtE": flt(category_totals['E']['taxable'], 4),
            "taxblAmtF": flt(category_totals['F']['taxable'], 4),
            "taxblAmtIpl1": flt(special_tax_totals['ipl1']['taxable'], 4),
            "taxblAmtIpl2": flt(special_tax_totals['ipl2']['taxable'], 4),
            "taxblAmtTl": flt(special_tax_totals['tl']['taxable'], 4),
            "taxblAmtEcm": flt(special_tax_totals['ecm']['taxable'], 4),
            "taxblAmtExeeg": flt(special_tax_totals['exeeg']['taxable'], 4),
            "taxblAmtTot": 0.0, # Check documentation, often for TOT (Turnover Tax) if applicable
            
            # Tax rates (fixed as per documentation)
            "taxRtA": 16,
            "taxRtB": 16,
            "taxRtC1": 0,
            "taxRtC2": 0,
            "taxRtC3": 0,
            "taxRtD": 0,
            "taxRtRvat": 16,
            "taxRtE": 0,
            "taxRtF": 10,
            "taxRtIpl1": 5,
            "taxRtIpl2": 0,
            "taxRtTl": 1.5,
            "taxRtEcm": 5,
            "taxRtExeeg": 3,
            "taxRtTot": 0,
            
            # Individual tax category amounts (corrected names)
            "taxAmtA": flt(category_totals['A']['tax'], 4),
            "taxAmtB": flt(category_totals['B']['tax'], 4),
            "taxAmtC1": flt(category_totals['C1']['tax'], 4),
            "taxAmtC2": flt(category_totals['C2']['tax'], 4),
            "taxAmtC3": flt(category_totals['C3']['tax'], 4),
            "taxAmtD": flt(category_totals['D']['tax'], 4),
            "taxAmtRvat": flt(category_totals['RVAT']['tax'], 4),
            "taxAmtE": flt(category_totals['E']['tax'], 4),
            "taxAmtF": flt(category_totals['F']['tax'], 4),
            "taxAmtIpl1": flt(special_tax_totals['ipl1']['tax'], 4), # Corrected name
            "taxAmtIpl2": flt(special_tax_totals['ipl2']['tax'], 4), # Corrected name
            "taxAmtTl": flt(special_tax_totals['tl']['tax'], 4), # Corrected name
            "taxAmtEcm": flt(special_tax_totals['ecm']['tax'], 4), # Corrected name
            "taxAmtExeeg": flt(special_tax_totals['exeeg']['tax'], 4), # Corrected name
            "taxAmtTot": 0.0, # For Turnover Tax, if applicable
            
            # Totals
            "totTaxblAmt": flt(total_taxable_amount, 2), # As per doc (18,2)
            "totTaxAmt": flt(total_tax_amount, 2), # As per doc (18,2)
            "totAmt": flt(totals['total_tax_inclusive_amount'], 2), # Total tax-inclusive invoice amount
            
            # Other fields
            "cashDcRt": flt(rvat_data.get("cash_discount_rate", 0.0), 4),
            "cashDcAmt": flt(rvat_data.get("cash_discount_amount", 0.0), 4),
            "prchrAcptcYn": "Y", # Assuming "Y" for a new agent sale, as per doc "Yes or No"
            "remark": rvat_data.get("remarks") or "",
            "regrId": created_by,
            "regrNm": created_by,
            "modrId": created_by,
            "modrNm": created_by,
            "saleCtyCd": "1", # As per doc (pass 1)
            "principalId": "3676521678",
            "currencyTyCd": currency,
            "exchangeRt": flt(rvat_data.get("exchange_rate", 1.0), 4),
            "dbtRsnCd": "", 
            "invcAdjustReason": "", 
            "itemList": item_list
        }

        print("\n--- RVAT Payload Constructed ---", destnCountryCd)
        print(payload)

        response = self.call_lpo_sale_client(payload)
        
        # Fix: Parse the JSON response first, then use .get() on the parsed data
        try:
            if hasattr(response, "json"):
                response_data = response.json()
            else:
                # If response doesn't have .json(), it might be a direct dict from mock
                response_data = response 
        except Exception as e:
            frappe.throw(f"Failed to parse response JSON: {e}")

        # Use response_data instead of response for dictionary operations
        if response_data.get("resultCd") == "000":
            if response_data.get("data") and response_data["data"].get("rcptNo"):
                rcpt_no = response_data["data"]["rcptNo"]
                doc_name = rvat_data.get("name")
                self.update_rcptNo_delayed(docname=doc_name, rcpt_no=rcpt_no)
                frappe.msgprint(f"Agent Sale created successfully. Receipt No: {rcpt_no}")
            else:
                frappe.msgprint("Agent Sale created successfully but no receipt number was returned.")

            ocrnDt = datetime.now().strftime("%Y%m%d")
            update_stock_item = []
            update_stock_master = []

            for item in item_list:
                # Calculate total taxable and tax amounts for this item based on the line item's individual taxable/tax amounts
                item_total_taxable = item.get("vatTaxblAmt", 0) + item.get("exciseTaxblAmt", 0) + \
                                    item.get("tlTaxblAmt", 0) + item.get("iplTaxblAmt", 0)
                item_total_tax = item.get("vatAmt", 0) + item.get("exciseTxAmt", 0) + \
                                item.get("tlAmt", 0) + item.get("iplAmt", 0)
                
                update_stock_item.append({
                    "itemSeq": item.get("itemSeq"),
                    "itemCd": item.get("itemCd"),
                    "itemClsCd": item.get("itemClsCd"),
                    "itemNm": item.get("itemNm"),
                    "pkgUnitCd": item.get("pkgUnitCd"),
                    "qtyUnitCd": item.get("qtyUnitCd"),
                    "qty": item.get("qty"),
                    "prc": item.get("prc"),
                    "splyAmt": item.get("splyAmt"), # This is the gross supply amount from the sales payload
                    "taxblAmt": flt(item_total_taxable, 4), # Total taxable amount for this line item across all taxes
                    "vatCatCd": item.get("vatCatCd"),
                    "taxAmt": flt(item_total_tax, 4), # Total tax amount for this line item across all taxes
                    "totAmt": item.get("totAmt"), # Total tax-inclusive amount for this line item
                    "pkg": item.get("pkg"),
                    "totDcAmt": item.get("dcAmt", 0),
                })
                
                # Get actual remaining quantity from bins (subtract the sold qty for an agent sale)
                # This assumes 'actual_qty' refers to available stock that needs to be reduced.
                bins = frappe.db.get_all("Bin", filters={"item_code": item.get("itemCd")}, fields=["actual_qty"])
                remaining_qty = sum(flt(b.get("actual_qty", 0)) for b in bins) - item.get("qty", 0)
                
                update_stock_master.append({
                    "itemCd": item.get("itemCd"),
                    "rsdQty": max(0, remaining_qty) # Ensure quantity doesn't go negative
                })

            # Payload for updating stock after sales (sarTyCd "02" for "Sale")
            update_stock_payload = {
                "tpin": self.tpin,
                "bhfId": self.branch_code,
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
            print("Update stock response:", call_update_stock_after_purchase)
            
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
                print("Update stock master response:", call_update_stock_master_after_purchase)
                
            else:
                frappe.throw(f"Failed to update detailed stock: {call_update_stock_after_purchase.get('resultMsg', 'Unknown error')}")
        else:
            frappe.throw(f"Failed to create Agent Sale: {response_data.get('resultMsg', 'Unknown error')}")