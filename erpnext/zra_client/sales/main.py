import json
import random
import frappe
from frappe.utils import flt
from datetime import datetime
from datetime import datetime
now = datetime.now()
from erpnext.zra_client.main import ZRAClient


class zraSales(ZRAClient):
    def __init__(self):
        super().__init__()

    def get_tpin(self):
        return self.tpin

    def get_branch(self):
        return self.branch_code
    
    def call_create_normal_sale_client(self, payload):
        self.normal_sale(payload)

    def create_sale_normal(self, sell_order):
        cisInvcNo = f'CIS{sell_order.get("name", "001")}-{random.randint(1000, 9999)}'
        created_by = sell_order.get("owner") or "system"
        currency = sell_order.get("currency") or "ZMW"
        totals = {
            'taxable': 0.0,
            'vat': 0.0,
            'discount': 0.0,
            'gross': 0.0,
            'net': 0.0
        }

        item_list = []
        for i, item in enumerate(sell_order.get("items", []), 1):
            item_code = item.get("item_code")
            item_doc = frappe.get_doc("Item", item_code)

            qty = flt(item.get("qty", 1))
            price = flt(item_doc.get("custom_default_unit_price", 0))
            gross = flt(qty * price, 4)

            bins = frappe.db.get_all("Bin", filters={"item_code": item_code}, fields=["actual_qty"])
            available_qty = sum(flt(b.get("actual_qty", 0)) for b in bins)

            if qty > available_qty:
                frappe.throw(
                    f"Insufficient stock for item <b>{item_code}</b>: "
                    f"Ordered: {qty}, Available: {available_qty}"
                )

            discount_pct = flt(item.get("discount_percentage", 0))
            discount_amt = flt(gross * discount_pct / 100, 4)
            net = flt(gross - discount_amt, 4)

            # VAT calculations (using standard VAT category A)
            taxable = flt(net / 1.16, 4)
            vat = flt(taxable * 0.16, 4)

            # Update totals
            totals['gross'] = flt(totals['gross'] + gross, 4)
            totals['discount'] = flt(totals['discount'] + discount_amt, 4)
            totals['net'] = flt(totals['net'] + net, 4)
            totals['taxable'] = flt(totals['taxable'] + taxable, 4)
            totals['vat'] = flt(totals['vat'] + vat, 4)


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
                "splyAmt": flt(gross, 4),
                "dcRt": flt(discount_pct, 4),
                "dcAmt": flt(discount_amt, 4),
                "vatCatCd": "A",
                "vatTaxblAmt": flt(taxable, 4),
                "vatAmt": flt(vat, 4),
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
            "cisInvcNo": cisInvcNo,
            "orgInvcNo":  0,
            "Customer": "Smart Customer",
            "salesTyCd": "N",
            "rcptTyCd": "S",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": now.strftime("%Y%m%d%H%M%S"),
            "salesDt": now.strftime("%Y%m%d"),
            "totItemCnt": len(item_list),
            "taxblAmtA": flt(totals['taxable'], 4),
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
            "taxAmtA": flt(totals['vat'], 4),
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
            "totTaxblAmt": flt(totals['taxable'], 4),
            "totTaxAmt": flt(totals['vat'], 4),
            "totAmt": flt(final_amount, 4),
            "cashDcRt": flt(cash_discount_rate, 4),
            "cashDcAmt": flt(cash_discount_amt, 4),
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
        call_create_normal_sale_client = self.call_create_normal_sale_client(payload)
