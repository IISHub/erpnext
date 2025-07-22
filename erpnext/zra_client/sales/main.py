import json
import random
import frappe
from frappe.utils import flt
from datetime import datetime
from erpnext.zra_client.main import ZRAClient

now = datetime.now()

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
    

    def update_stock_after_purchase(self, payload):
        self.update_stock_after_purchase_view(payload)

    def update_stock_master_after_purchase(self, payload):
        self.save_stock_master(payload)

    def cancel_sale(self, payload):
        self.sale_credit_note(payload)

    def create_sale_normal(self, sell_order):
        cisInvcNo = f'CIS{sell_order.get("name", "001")}-{random.randint(1000, 9999)}'
        created_by = sell_order.get("owner") or "system"
        currency = sell_order.get("currency") or "ZMW"
        totals = {'taxable': 0.0, 'vat': 0.0, 'discount': 0.0, 'gross': 0.0, 'net': 0.0}
        item_list = []

        for i, item in enumerate(sell_order.get("items", []), 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)
            qty = flt(item.get("qty", 1))
            price = flt(item_doc.get("custom_default_unit_price", 0))
            gross = flt(qty * price, 4)
            bins = frappe.db.get_all("Bin", filters={"item_code": item_code}, fields=["actual_qty"])
            available_qty = sum(flt(b.get("actual_qty", 0)) for b in bins)

            # if qty > available_qty:
            #     frappe.throw(
            #         f"Insufficient stock for item <b>{item_code}</b>: Ordered: {qty}, Available: {available_qty}"
            #     )

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
            "Customer": "Smart Customer",
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
        print("📦 Preparing sale data:", payload)
        response = self.call_create_normal_sale_client(payload)

        if response.get("resultCd") == "000":
            get_rcpt_no = response.get("rcptNo")
            sales_invoice_doc = frappe.get_doc("Sales Invoice", sell_order.get("name"))
            sales_invoice_doc.update({"rcptNo": get_rcpt_no})
            sales_invoice_doc.save(ignore_permissions=True)
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

            call_update_stock_after_purchase = self.update_stock_after_purchase(update_stock_payload)

            create_update_stock_master_payload = {
                            "tpin": self.tpin,
                            "bhfId": self.branch_code,
                            "regrId": created_by,
                            "regrNm": created_by,
                            "modrNm": created_by,
                            "modrId": created_by,
                            "stockItemList":update_stock_master_items 

                            }

            print("📦 Preparing stock master update data:", create_update_stock_master_payload)
            call_update_stock_master_after_purchase = self.update_stock_master_after_purchase(create_update_stock_master_payload)

            frappe.msgprint(f"✅ Sale made successfully: {response.get('resultMsg')}")
        else:
            frappe.throw(f"❌ Purchase save failed: {response.get('resultMsg')}")



    def create_credit_note_sale(self, cancel_data):
        print("sale cancelled", cancel_data)
        cisInvcNo = f'CIS{cancel_data.get("name", "001")}-{random.randint(1000, 9999)}'
        customer_name = cancel_data.get("customer") or cancel_data.get("customer_name") or ""
        created_by = cancel_data.get("owner") or "system"
        currency = cancel_data.get("currency") or "ZMW"

        cfmDt = datetime.now().strftime("%Y%m%d%H%M%S")
        salesDt = datetime.now().strftime('%Y%m%d')

        totals = {
            'taxable': 0.0,
            'vat': 0.0,
            'discount': 0.0,
            'gross': 0.0,
            'net': 0.0
        }

        item_list = []
        for i, item in enumerate(cancel_data.get("items", []), 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)

            qty = flt(item.get("qty", 1))
            price = flt(item_doc.get("custom_default_unit_price", 0))
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
                "prc": price,
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

        cash_discount_rate = 25.0
        cash_discount_amt = flt(totals['net'] * cash_discount_rate / 100, 4)
        final_amount = flt(totals['net'] - cash_discount_amt, 4)

        payload = {
                "tpin": self.get_tpin(),
                "bhfId": self.get_branch(),
                "orgSdcId": self.get_org_sdc_id(),
                "orgInvcNo": "86",
                "cisInvcNo":"CIS001-138060",
                "Customer": "Smart Customer",
                "custTpin": "1000000000",
                "salesTyCd": "N",
                "rcptTyCd": "R",
                "pmtTyCd": "01",
                "salesSttsCd": "02",
                "cfmDt": "20240508102010",
                "salesDt": "20250719",
                "rfdRsnCd": "01",
                "totItemCnt": 2,
                "taxblAmtA": 86.2069,
                "taxblAmtB": 0.0,
                "taxblAmtC1": 0.0,
                "taxblAmtC2": 0.0,
                "taxblAmtC3": 0.0,
                "taxblAmtD": 0.0,
                "taxblAmtRvat": 0.0,
                "taxblAmtE": 0.0,
                "taxblAmtF": 0.0,
                "taxblAmtIpl1": 0.0,
                "taxblAmtIpl2": 100,
                "taxblAmtTl": 0.0,
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
                "taxAmtA": 13.7931,
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
                "totTaxblAmt": 186.2069,
                "totTaxAmt": 13.7931,
                "cashDcRt": 25,
                "cashDcAmt": 50,
                "totAmt": 150,
                "prchrAcptcYn": "N",
                "remark": "",
                "regrId": "admin",
                "regrNm": "admin",
                "modrId": "admin",
                "modrNm": "admin",
                "saleCtyCd": "1",
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
                        "itemNm": "Bread",
                        "bcd": "",
                        "pkgUnitCd": "BA",
                        "pkg": 0.0,
                        "qtyUnitCd": "BE",
                        "qty": 1.0,
                        "prc": 125,
                        "splyAmt": 125,
                        "dcRt": 20,
                        "dcAmt": 25,
                        "isrccCd": "",
                        "isrccNm": "",
                        "isrcRt": 0.0,
                        "isrcAmt": 0.0,
                        "vatCatCd": "A",
                        "vatTaxblAmt": 86.2069,
                        "vatAmt": 13.7931,
                        "exciseTaxblAmt": 0,
                        "tlTaxblAmt": 0.0,
                        "iplTaxblAmt": 0.0,
                        "iplAmt": 0.0,
                        "tlAmt": 0.0,
                        "exciseTxAmt": 0,
                        "totAmt": 100
                    },
                    {
                        "itemSeq": 2,
                        "itemCd": "20056",
                        "itemClsCd": "50102518",
                        "itemNm": "Reinsurance",
                        "bcd": "",
                        "pkgUnitCd": "BA",
                        "pkg": 0.0,
                        "qtyUnitCd": "BE",
                        "qty": 1.0,
                        "prc": 100,
                        "splyAmt": 100,
                        "dcRt": 0.0,
                        "dcAmt": 0.0,
                        "isrccCd": "",
                        "isrccNm": "",
                        "isrcRt": 0.0,
                        "isrcAmt": 0.0,
                        "vatTaxblAmt": 0.0,
                        "exciseTaxblAmt": 0,
                        "tlTaxblAmt": 0.0,
                        "tlAmt": 0.0,
                        "iplCatCd": "IPL2",
                        "iplAmt": 0.0,
                        "iplTaxblAmt": 100,
                        "vatAmt": 0.0,
                        "exciseTxAmt": 0,
                        "totAmt": 100
                    }
                ]
            }
        
        self.cancel_sale(payload)


		