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

        for i, item in enumerate(sell_order.get("items", []), 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)
            print(f"\n=== ITEM DOC: {item_code} ===\n", item_doc.as_dict())

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

            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": "50102518",
                "itemNm": item.get("item_name"),
                "bcd": item_doc.get("custom_origin_place_code", ""),
                "pkgUnitCd": "WRAP",
                "pkg": 1,
                "qtyUnitCd": zra_qty_unit_code,
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

            print("📦 Preparing stock update data:", update_stock_payload)

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
            
            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": "50102518",
                "itemNm": item.get("item_name"),
                "bcd": item_doc.get("custom_origin_place_code", ""),
                "pkgUnitCd": "WRAP",
                "pkg": 1,
                "qtyUnitCd": zra_qty_unit_code,
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
            update_stock_master = []

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
                
                update_stock_master.append({
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
            
            item_list.append({
                "itemSeq": i,
                "itemCd": item_code,
                "itemClsCd": "50102518",
                "itemNm": item.get("item_name"),
                "bcd": item_doc.get("custom_origin_place_code", ""),
                "pkgUnitCd": "WRAP",
                "pkg": 1,
                "qtyUnitCd": zra_qty_unit_code,
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
            update_stock_master = []

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
                
                update_stock_master.append({
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
        




		