from erpnext.zra_client.main import ZRAClient
import os
import frappe
import json
import random
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import requests

class NormaSale(ZRAClient):
    def __init__(self):
        self.taxbl_totals = {key: 0.0 for key in self.TAX_RATES}
        self.tax_amt_totals = {key: 0.0 for key in self.TAX_RATES}
        super().__init__()



    def create_normal_sale_helper(self, payload):
        return self.normal_sale(payload)

    TAX_RATES = {
        "A": 16, "B": 16, "C1": 0, "C2": 0, "C3": 0,
        "D": 0, "E": 0, "F": 10,
        "Ipl1": 5, "Ipl2": 0,
        "Tl": 1.5,
        "ECM": 5,
        "EXEEG": 3,
        "RVAT": 16
    }


    @staticmethod
    def format_tax_amount(value):
        return float(Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))

    def generate_cis_invc_no(self):
        no = f"CIS{random.randint(1, 999):03d}-{random.randint(1000, 9999)}"
        print(f"[INFO] Generated invoice no: {no}")
        return no

    def calculate_tax_for_item(self, item):
        qty = float(item.get("qty", 0))
        price_tax_inclusive = float(item.get("prc", 0))
        discount_rate = 0.0

        vat_cat = item.get("vatCatCd")
        ipl_cat = item.get("iplCatCd")
        tl_cat = item.get("tlCatCd")
        excise_cat = item.get("exciseTxCatCd")

        print(f"\n[CALCULATE TAX] {item['itemNm']} (qty={qty}, price={price_tax_inclusive}, "
              f"vatCatCd={vat_cat}, iplCatCd={ipl_cat}, tlCatCd={tl_cat}, exciseTxCatCd={excise_cat})")

        supply_amount = round(qty * price_tax_inclusive, 2)
        discount_amount = round(supply_amount * (discount_rate / 100), 2)

        vat_rate = self.TAX_RATES.get(vat_cat, 0) / 100 if vat_cat else 0
        ipl_rate = self.TAX_RATES["Ipl1"] / 100 if ipl_cat == "IPL1" else self.TAX_RATES["Ipl2"] / 100 if ipl_cat == "IPL2" else 0
        tl_rate = self.TAX_RATES["Tl"] / 100 if tl_cat == "TL" else 0
        ecm_rate = self.TAX_RATES["ECM"] / 100 if excise_cat == "ECM" else 0

        combined_rate_excl_ecm = vat_rate + ipl_rate + tl_rate
        base_amount = round(supply_amount / (1 + combined_rate_excl_ecm), 2) if combined_rate_excl_ecm > 0 else supply_amount

        vat_tax = round(base_amount * vat_rate, 2)
        ipl_tax = round(base_amount * ipl_rate, 2)
        tl_tax = round(base_amount * tl_rate, 2)

        ecm_taxable_amount = 0.0
        ecm_tax = 0.0

        ipl_taxable_amt = base_amount if ipl_rate > 0 else (supply_amount if ipl_cat == "IPL2" else 0.0)

        return {
            "splyAmt": supply_amount,
            "dcRt": discount_rate,
            "dcAmt": discount_amount,
            "vatTaxblAmt": base_amount if vat_cat else 0.0,
            "vatAmt": vat_tax,
            "iplTaxblAmt": ipl_taxable_amt,
            "iplAmt": ipl_tax,
            "tlTaxblAmt": base_amount if tl_rate > 0 else 0.0,
            "tlAmt": tl_tax,
            "ecmTaxblAmt": ecm_taxable_amount,
            "ecmAmt": ecm_tax,
            "totAmt": supply_amount
        }

    def build_payload(self, items, base_data):
        print("\n[BUILD PAYLOAD] Processing items...")
        processed_items = []

        for idx, item in enumerate(items):
            tax_result = self.calculate_tax_for_item(item)

            vat_cat = item.get("vatCatCd")
            ipl_cat = item.get("iplCatCd")
            tl_cat = item.get("tlCatCd")
            excise_cat = item.get("exciseTxCatCd")

            if vat_cat in self.TAX_RATES:
                self.taxbl_totals[vat_cat] += tax_result["vatTaxblAmt"]
                self.tax_amt_totals[vat_cat] += tax_result["vatAmt"]

            if ipl_cat == "IPL1":
                self.taxbl_totals["Ipl1"] += tax_result["iplTaxblAmt"]
                self.tax_amt_totals["Ipl1"] += tax_result["iplAmt"]
            elif ipl_cat == "IPL2":
                self.taxbl_totals["Ipl2"] += tax_result["iplTaxblAmt"]

            if tl_cat == "TL":
                self.taxbl_totals["Tl"] += tax_result["tlTaxblAmt"]
                self.tax_amt_totals["Tl"] += tax_result["tlAmt"]

            if excise_cat == "ECM":
                ecm_taxbl_amt = 150.0
                ecm_tax_amt = round(ecm_taxbl_amt * (self.TAX_RATES["ECM"] / 100), 2)
                self.taxbl_totals["ECM"] += ecm_taxbl_amt
                self.tax_amt_totals["ECM"] += ecm_tax_amt
            else:
                ecm_taxbl_amt = 0.0
                ecm_tax_amt = 0.0

            processed_item = {
                "itemSeq": idx + 1,
                "itemCd": item["itemCd"],
                "itemClsCd": item["itemClsCd"],
                "itemNm": item["itemNm"],
                "qty": float(item.get("qty", 0)),
                "prc": float(item.get("prc", 0)),
                "rrp": round(float(item.get("prc", 0)), 2),
                **tax_result,
                "vatCatCd": vat_cat or "",
                "iplCatCd": ipl_cat or "",
                "tlCatCd": tl_cat or "",
                "pkgUnitCd": item.get("pkgUnitCd", "BA"),
                "pkg": float(item.get("pkg", 1.0)),
                "qtyUnitCd": item.get("qtyUnitCd", "BE"),
                "bcd": item.get("bcd", ""),
                "isrccCd": item.get("isrccCd", ""),
                "isrccNm": item.get("isrccNm", ""),
                "isrcRt": float(item.get("isrcRt", 0.0)),
                "isrcAmt": float(item.get("isrcAmt", 0.0)),
                "ecmTaxblAmt": ecm_taxbl_amt,
                "ecmAmt": ecm_tax_amt,
                "totAmt": round(tax_result["splyAmt"] + ecm_tax_amt, 2)
            }

            processed_items.append(processed_item)

        total_taxable_amount = round(sum(item["vatTaxblAmt"] for item in processed_items), 2)
        total_tax_amount = round(sum(
            item["vatAmt"] + item["iplAmt"] + item["tlAmt"] + item["ecmAmt"]
            for item in processed_items
        ), 2)
        total_amount = round(sum(item["totAmt"] for item in processed_items), 2)

        export_destination_country_code = base_data.get("export_destination_code")
        if export_destination_country_code is not None:
            destnCountryCd = export_destination_country_code
        else:
            destnCountryCd = None
        
        get_lpoNumber = base_data.get("lpoNumber")
        get_principal_id = base_data.get("principalId")


        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_branch_code(),
            "orgInvcNo": 0,
            "cisInvcNo":  base_data["name"],
            "custTpin": base_data["cust_tpin"],
            "custNm": base_data["cust_name"],
            "salesTyCd": "N",
            "rcptTyCd": "S",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": datetime.now().strftime("%Y%m%d%H%M%S"),
            "salesDt": datetime.now().strftime("%Y%m%d"),
            "totItemCnt": len(items),
            **self.generate_tax_fields(),
            "totTaxblAmt": total_taxable_amount,
            "totTaxAmt": self.format_tax_amount(total_tax_amount),
            "cashDcRt": 0,
            "cashDcAmt": 0.0,
            "totAmt": total_amount,
            "prchrAcptcYn": "N",
            "remark": "",
            "regrId": "admin",
            "regrNm": "admin",
            "modrId": "admin",
            "modrNm": "admin",
            "saleCtyCd": "1",
            "currencyTyCd": "ZMW",
            "exchangeRt": "1",
            "dbtRsnCd": "",
            "invcAdjustReason": "",
            "itemList": processed_items
        }
        if destnCountryCd:
            payload["destnCountryCd"] = destnCountryCd

        if get_lpoNumber:
            payload["lpoNumber"] = get_lpoNumber

        if get_principal_id:
            payload["principalId"] = get_principal_id

        self.to_use_data = payload

        print(json.dumps(payload, indent=4))
        return payload

    def generate_tax_fields(self):
        return {
            f"taxblAmt{k}": round(self.taxbl_totals.get(k, 0.0), 2)
            for k in self.TAX_RATES
        } | {
            f"taxRt{k}": self.TAX_RATES.get(k, 0)
            for k in self.TAX_RATES
        } | {
            f"taxAmt{k}": round(self.tax_amt_totals.get(k, 0.0), 2)
            for k in self.TAX_RATES
        }
    
    def send_sale_data(self, sell_data):
        customer_name = sell_data.get("customer") or sell_data.get("customer_name") or ""
        name = sell_data.get("name")
        customer_doc = frappe.get_doc("Customer", customer_name)
        customer_tpin = customer_doc.get("custom_tpin") or ""
        export_destination_country = sell_data.get("custom_destination_country")
        lpo_number = sell_data.get("custom_lpo_number")
        is_lpo_transactions = sell_data.get("custom__lpo_transaction")
        is_export = sell_data.get("custom_export")
        is_rvat_agent = sell_data.get("custom_rvat")
        principal_id = sell_data.get("custom_principal_id")
        if export_destination_country == "ASCENSION ISLAND":
            export_destination_country = " "
        


        sell_data_item = sell_data.get("items")
        items = []
        for item in sell_data_item:

            itemCd = item.get("item_code")
            item_doc = frappe.get_doc("Item", itemCd)
            formatted_items = item_doc.as_dict()
            package_unit_code = formatted_items.get("custom_packaging_unit_code")
            unit_of_measure = formatted_items.get("custom_units_of_measure")
            get_ipl_name = item.get("custom_ipl")
            get_tl_name = item.get("custom_tl")
            get_excise_name = item.get("custom_excise")
            get_turn_over_tax = item.get("custom_tot")
            get_vat_name = item.get("custom_test")

            tlCat = {
                "TL":"Tourism Levy",
                "F": "Service Charge 10%"
            }

            
            iplCat = {

                "IPL1":"Insurance Premium Levy",
                "IPL2": "Re-Insurance"
            }

            
    
            vat_tax_types = {
                "A": "Standard Rated 16%",
                "B": "Minimum Taxable Value (MTV)",
                "C1": "Exports 0%",               
                "RVAT": "RVAT Reverse VAT",           
                "C2": "Local Purchases Order",
                "C3": "Zero-rated by nature",
                "D": "Exempt No tax charge",
                "E": "Disbursement",
            }
            vatCd = next((key for key, value in vat_tax_types.items() if value == get_vat_name), None)
            iplCd = next((key for key, value in iplCat.items() if value == get_ipl_name), None)
            tlCd = next((key for key, value in tlCat.items() if value == get_tl_name), None)

            present_codes = [code for code in [vatCd, iplCd, tlCd] if code is not None]
            if len(present_codes) != 1:
                frappe.throw("Exactly one of vatCd, iplCd, or tlCd must be present. Found: {}".format(len(present_codes)))

            print(package_unit_code, unit_of_measure, get_vat_name, vatCd)
            itemName = item.get("item_name")

            qty = item.get("qty")

            items.append({
                "itemCd": itemCd,
                "itemClsCd": "50101101",         
                "itemNm": itemName,
                "qty": qty,
                "prc": 100.00,
                "pkgUnitCd": self.get_packaging_unit(package_unit_code),
                "qtyUnitCd": self.get_units_of_measure(unit_of_measure),                
                "vatCatCd": vatCd,                
                "iplCatCd": iplCd,
                "tlCatCd": tlCd,
                "exciseTxCatCd": None
            })

        base_data = {
            "cust_name": customer_name,
            "cust_tpin": customer_tpin,
            "name": name,
            
        }
        if is_export == 1 or vatCd == "C1":
                self.validate_export(vatCd, export_destination_country, is_export)

                if export_destination_country == "N / A":
                    frappe.throw("Destination country is required. Please select a valid country.")

                destination_country_code = self.get_country_code_by_name(export_destination_country)
                base_data["export_destination_code"] = destination_country_code 


        if iplCd is not None and (vatCd is not None or tlCd is not None):
            frappe.throw(
                f"[ZRA Error] IPL transactions (iplCd) must not be combined with VAT or TL. Found: vatCd={vatCd}, tlCd={tlCd}"
            )
        
        if is_lpo_transactions == 1:
            if vatCd != "C2":
                frappe.throw("Only VAT Code 'C2' is allowed for LPO transactions.")
            if not lpo_number:
                frappe.throw("LPO Number is required when VAT Code is 'C2' for LPO transactions.")
            if len(lpo_number) < 9 or len(lpo_number) > 20:
                frappe.throw("LPO Number length must be between 9 and 20 characters.")
            base_data["lpoNumber"] = lpo_number

        if vatCd == "C2" and not is_lpo_transactions:
            frappe.throw("For VAT Code 'C2', LPO transaction must be checked.")

        if is_rvat_agent:
            if not principal_id:
                frappe.throw("For RVAT Agent Sales, Principal ID is required.")
            base_data["principalId"] = principal_id





        print("\n[START] Sending sale data...")
        payload = self.build_payload(items, base_data)
        response = self.create_normal_sale_helper(payload)
        
        if response.get("resultCd") == "000":
            get_rcpt_no = response.get("data", {}).get("rcptNo")
            get_qrcode_url = response.get("data", {}).get("qrCodeUrl") 
            print("Stock master updated successfully after sale.")
            doc_name = sell_data.get("name")
            self.update_rcptNo_delayed(docname=doc_name, rcpt_no=get_rcpt_no, qrcode_url=get_qrcode_url)
            created_by = sell_data.get("owner")

            print("This prints immediately, before delayed print")
            ocrnDt = datetime.now().strftime("%Y%m%d")
            print(self.to_use_data)

            update_stock_items = []
            update_stock_master_items = []

                
                
            for item in self.to_use_data.get("itemList", []):
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
                    "pkg": item.get("pkg", 1),
                    "totDcAmt": item.get("dcAmt", 0),
                })

                remaining_qty = 12  
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
                "totItemCnt": self.to_use_data['totItemCnt'],
                "totTaxblAmt": self.to_use_data['totTaxblAmt'],
                "totTaxAmt": self.to_use_data['totTaxAmt'],
                "totAmt": self.to_use_data['totAmt'],
                "regrId": created_by,
                "regrNm": created_by,
                "modrNm": created_by,
                "modrId": created_by,
                "itemList": update_stock_items
            }

            print(update_stock_payload, update_stock_master_items)
            self.run_stock_update_in_background(update_stock_payload, update_stock_master_items, created_by)


            frappe.msgprint(f"Sale made successfully: {response.get('resultMsg')}")
        else:
            frappe.throw(f"Sale save failed: {response.get('resultMsg')}")



class CreditNote(ZRAClient):
        def __init__(self):
            self.taxbl_totals = {key: 0.0 for key in self.TAX_RATES}
            self.tax_amt_totals = {key: 0.0 for key in self.TAX_RATES}
            super().__init__()

        def create_normal_sale_helper(self, payload):
            return self.normal_sale(payload)

        TAX_RATES = {
            "A": 16, "B": 16, "C1": 0, "C2": 0, "C3": 0,
            "D": 0, "E": 0, "F": 10,
            "Ipl1": 5, "Ipl2": 0,
            "Tl": 1.5,
            "ECM": 5,
            "EXEEG": 3,
            "RVAT": 16
        }


        @staticmethod
        def format_tax_amount(value):
            return float(Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))

        def generate_cis_invc_no(self):
            no = f"CIS{random.randint(1, 999):03d}-{random.randint(1000, 9999)}"
            print(f"[INFO] Generated invoice no: {no}")
            return no

        def calculate_tax_for_item(self, item):
            qty = float(item.get("qty", 0))
            price_tax_inclusive = float(item.get("prc", 0))
            discount_rate = 0.0

            vat_cat = item.get("vatCatCd")
            ipl_cat = item.get("iplCatCd")
            tl_cat = item.get("tlCatCd")
            excise_cat = item.get("exciseTxCatCd")

            print(f"\n[CALCULATE TAX] {item['itemNm']} (qty={qty}, price={price_tax_inclusive}, "
                f"vatCatCd={vat_cat}, iplCatCd={ipl_cat}, tlCatCd={tl_cat}, exciseTxCatCd={excise_cat})")

            supply_amount = round(qty * price_tax_inclusive, 2)
            discount_amount = round(supply_amount * (discount_rate / 100), 2)

            vat_rate = self.TAX_RATES.get(vat_cat, 0) / 100 if vat_cat else 0
            ipl_rate = self.TAX_RATES["Ipl1"] / 100 if ipl_cat == "IPL1" else self.TAX_RATES["Ipl2"] / 100 if ipl_cat == "IPL2" else 0
            tl_rate = self.TAX_RATES["Tl"] / 100 if tl_cat == "TL" else 0
            ecm_rate = self.TAX_RATES["ECM"] / 100 if excise_cat == "ECM" else 0

            combined_rate_excl_ecm = vat_rate + ipl_rate + tl_rate
            base_amount = round(supply_amount / (1 + combined_rate_excl_ecm), 2) if combined_rate_excl_ecm > 0 else supply_amount

            vat_tax = round(base_amount * vat_rate, 2)
            ipl_tax = round(base_amount * ipl_rate, 2)
            tl_tax = round(base_amount * tl_rate, 2)

            ecm_taxable_amount = 0.0
            ecm_tax = 0.0

            ipl_taxable_amt = base_amount if ipl_rate > 0 else (supply_amount if ipl_cat == "IPL2" else 0.0)

            return {
                "splyAmt": supply_amount,
                "dcRt": discount_rate,
                "dcAmt": discount_amount,
                "vatTaxblAmt": base_amount if vat_cat else 0.0,
                "vatAmt": vat_tax,
                "iplTaxblAmt": ipl_taxable_amt,
                "iplAmt": ipl_tax,
                "tlTaxblAmt": base_amount if tl_rate > 0 else 0.0,
                "tlAmt": tl_tax,
                "ecmTaxblAmt": ecm_taxable_amount,
                "ecmAmt": ecm_tax,
                "totAmt": supply_amount
            }

        def build_payload(self, items, base_data):
            print("\n[BUILD PAYLOAD] Processing items...")
            processed_items = []

            for idx, item in enumerate(items):
                tax_result = self.calculate_tax_for_item(item)

                vat_cat = item.get("vatCatCd")
                ipl_cat = item.get("iplCatCd")
                tl_cat = item.get("tlCatCd")
                excise_cat = item.get("exciseTxCatCd")

                if vat_cat in self.TAX_RATES:
                    self.taxbl_totals[vat_cat] += tax_result["vatTaxblAmt"]
                    self.tax_amt_totals[vat_cat] += tax_result["vatAmt"]

                if ipl_cat == "IPL1":
                    self.taxbl_totals["Ipl1"] += tax_result["iplTaxblAmt"]
                    self.tax_amt_totals["Ipl1"] += tax_result["iplAmt"]
                elif ipl_cat == "IPL2":
                    self.taxbl_totals["Ipl2"] += tax_result["iplTaxblAmt"]

                if tl_cat == "TL":
                    self.taxbl_totals["Tl"] += tax_result["tlTaxblAmt"]
                    self.tax_amt_totals["Tl"] += tax_result["tlAmt"]

                if excise_cat == "ECM":
                    ecm_taxbl_amt = 150.0
                    ecm_tax_amt = round(ecm_taxbl_amt * (self.TAX_RATES["ECM"] / 100), 2)
                    self.taxbl_totals["ECM"] += ecm_taxbl_amt
                    self.tax_amt_totals["ECM"] += ecm_tax_amt
                else:
                    ecm_taxbl_amt = 0.0
                    ecm_tax_amt = 0.0

                processed_item = {
                    "itemSeq": idx + 1,
                    "itemCd": item["itemCd"],
                    "itemClsCd": item["itemClsCd"],
                    "itemNm": item["itemNm"],
                    "qty": float(item.get("qty", 0)),
                    "prc": float(item.get("prc", 0)),
                    "rrp": round(float(item.get("prc", 0)), 2),
                    **tax_result,
                    "vatCatCd": vat_cat or "",
                    "iplCatCd": ipl_cat or "",
                    "tlCatCd": tl_cat or "",
                    "pkgUnitCd": item.get("pkgUnitCd", "BA"),
                    "pkg": float(item.get("pkg", 1.0)),
                    "qtyUnitCd": item.get("qtyUnitCd", "BE"),
                    "bcd": item.get("bcd", ""),
                    "isrccCd": item.get("isrccCd", ""),
                    "isrccNm": item.get("isrccNm", ""),
                    "isrcRt": float(item.get("isrcRt", 0.0)),
                    "isrcAmt": float(item.get("isrcAmt", 0.0)),
                    "ecmTaxblAmt": ecm_taxbl_amt,
                    "ecmAmt": ecm_tax_amt,
                    "totAmt": round(tax_result["splyAmt"] + ecm_tax_amt, 2)
                }

                processed_items.append(processed_item)

            total_taxable_amount = sum(self.taxbl_totals.values())
            total_tax_amount = sum(self.tax_amt_totals.values())
            total_amount = round(total_taxable_amount + total_tax_amount, 2)
            original_invoice_no = base_data["original_sell"]
            try:
                original_invoice = frappe.get_doc("Sales Invoice", original_invoice_no)
                orgInvcNo = original_invoice.custom_rcpt_no if hasattr(original_invoice, 'custom_rcpt_no') else None
                if not orgInvcNo:
                    frappe.throw("Original invoice receipt number not found")
            except Exception as e:
                frappe.throw(f"Failed to get original invoice: {str(e)}")

            export_destination_country_code = base_data.get("export_destination_code")
            if export_destination_country_code is not None:
                destnCountryCd = export_destination_country_code
            else:
                destnCountryCd = None
            
            get_lpoNumber = base_data.get("lpoNumber")

            payload = {
                "tpin": self.get_tpin(),
                "bhfId": self.get_branch_code(),
                "orgInvcNo":  orgInvcNo,
                "orgSdcId": "SDC0010002709",
                "cisInvcNo": self.generate_cis_invc_no(),
                "custTpin": base_data["cust_tpin"],
                "custNm": base_data["cust_name"],
                "salesTyCd": "N",
                "rcptTyCd": "R",
                "pmtTyCd": "01",
                "salesSttsCd": "02",
                "cfmDt": datetime.now().strftime("%Y%m%d%H%M%S"),
                "salesDt": datetime.now().strftime("%Y%m%d"),
                "totItemCnt": len(items),
                **self.generate_tax_fields(),
                "totTaxblAmt": total_taxable_amount,
                "totTaxAmt": self.format_tax_amount(total_tax_amount),
                "cashDcRt": 0,
                "cashDcAmt": 0.0,
                "totAmt": total_amount,
                "prchrAcptcYn": "N",
                "remark": "",
                "regrId": "admin",
                "regrNm": "admin",
                "modrId": "admin",
                "modrNm": "admin",
                "saleCtyCd": "1",
                "lpoNumber": None,
                "currencyTyCd": "ZMW",
                "exchangeRt": "1",
                "dbtRsnCd": "",
                "rfdRsnCd": "01",
                "invcAdjustReason": "",
                "itemList": processed_items
            }
            if destnCountryCd:
                payload["destnCountryCd"] = destnCountryCd

            print("Checkin for LOP: ", get_lpoNumber)
            if get_lpoNumber:
                payload["lpoNumber"] = get_lpoNumber
            self.to_use_data = payload

            print(json.dumps(payload, indent=4))
            return payload

        def generate_tax_fields(self):
            return {
                f"taxblAmt{k}": round(self.taxbl_totals.get(k, 0.0), 2)
                for k in self.TAX_RATES
            } | {
                f"taxRt{k}": self.TAX_RATES.get(k, 0)
                for k in self.TAX_RATES
            } | {
                f"taxAmt{k}": round(self.tax_amt_totals.get(k, 0.0), 2)
                for k in self.TAX_RATES
            }
        
        def send_credit_sale_data(self, sell_data):
            print(sell_data)
            customer_name = sell_data.get("customer") or sell_data.get("customer_name") or ""
            customer_doc = frappe.get_doc("Customer", customer_name)
            customer_tpin = customer_doc.get("custom_tpin") or ""
            original_sell = sell_data.get("return_against")
            export_destination_country = sell_data.get("custom_destination_country")
            lpo_number = sell_data.get("custom_lpo_number")
            is_lpo_transactions = sell_data.get("custom__lpo_transaction")
            is_export = sell_data.get("custom_export")
            

            if export_destination_country == "ASCENSION ISLAND":
                export_destination_country = " "


            sell_data_item = sell_data.get("items")
            items = []
            for item in sell_data_item:

                itemCd = item.get("item_code")
                item_doc = frappe.get_doc("Item", itemCd)
                formatted_items = item_doc.as_dict()
                package_unit_code = formatted_items.get("custom_packaging_unit_code")
                unit_of_measure = formatted_items.get("custom_units_of_measure")
                get_ipl_name = item.get("custom_ipl")
                get_tl_name = item.get("custom_tl")
                get_excise_name = item.get("custom_excise")
                get_turn_over_tax = item.get("custom_tot")
                get_vat_name = item.get("custom_test")
                
           
        
                tlCat = {
                "TL":"Tourism Levy",
                "F": "Service Charge 10%"
                }

                
                iplCat = {

                    "IPL1":"Insurance Premium Levy",
                    "IPL2": "Re-Insurance"
                }

                
        
                vat_tax_types = {
                    "A": "Standard Rated 16%",
                    "B": "Minimum Taxable Value (MTV)",
                    "C1": "Exports 0%",               
                    "RVAT": "RVAT Reverse VAT",           
                    "C2": "Local Purchases Order",
                    "C3": "Zero-rated by nature",
                    "D": "Exempt No tax charge",
                    "E": "Disbursement",
                }
                vatCd = next((key for key, value in vat_tax_types.items() if value == get_vat_name), None)
                iplCd = next((key for key, value in iplCat.items() if value == get_ipl_name), None)
                tlCd = next((key for key, value in tlCat.items() if value == get_tl_name), None)

                present_codes = [code for code in [vatCd, iplCd, tlCd] if code is not None]
                if len(present_codes) != 1:
                    frappe.throw("Exactly one of vatCd, iplCd, or tlCd must be present. Found: {}".format(len(present_codes)))


                print(package_unit_code, unit_of_measure, get_vat_name, vatCd)
                itemName = item.get("item_name")

                
            
                qty = abs((item.get("qty", 0)))

                items.append({
                    "itemCd": itemCd,
                    "itemClsCd": "50101101",         
                    "itemNm": itemName,
                    "qty": qty,
                    "prc": 100.00,
                    "pkgUnitCd": self.get_packaging_unit(package_unit_code),
                    "qtyUnitCd": self.get_units_of_measure(unit_of_measure),                
                    "vatCatCd": vatCd,                
                    "iplCatCd": iplCd ,
                    "tlCatCd": tlCd,
                    "exciseTxCatCd": None
                })

            base_data = {
                "cust_name": customer_name,
                "cust_tpin": customer_tpin,
                "original_sell": original_sell,
            }
            if is_export == 1 or vatCd == "C1":
                self.validate_export(vatCd, export_destination_country, is_export)

                if export_destination_country == "N / A":
                    frappe.throw("Destination country is required. Please select a valid country.")

                destination_country_code = self.get_country_code_by_name(export_destination_country)
                base_data["export_destination_code"] = destination_country_code 


            if iplCd is not None and (vatCd is not None or tlCd is not None):
                frappe.throw(
                    f"[ZRA Error] IPL transactions (iplCd) must not be combined with VAT or TL. Found: vatCd={vatCd}, tlCd={tlCd}"
                )
            
            if is_lpo_transactions == 1:
                if vatCd != "C2":
                    frappe.throw("Only VAT Code 'C2' is allowed for LPO transactions.")
                if not lpo_number:
                    frappe.throw("LPO Number is required when VAT Code is 'C2' for LPO transactions.")
                if len(lpo_number) < 9 or len(lpo_number) > 20:
                    frappe.throw("LPO Number length must be between 9 and 20 characters.")
                base_data["lpoNumber"] = lpo_number

            if vatCd == "C2" and not is_lpo_transactions:
                frappe.throw("For VAT Code 'C2', LPO transaction must be checked.")

            print("\n[START] Sending sale data...")
            payload = self.build_payload(items, base_data)
            response = self.create_normal_sale_helper(payload)
            
            if response.get("resultCd") == "000":
                get_rcpt_no = response.get("data", {}).get("rcptNo")
                get_qrcode_url = response.get("data", {}).get("qrCodeUrl") 
                print("Stock master updated successfully after sale.")
                doc_name = sell_data.get("name")
                self.update_rcptNo_delayed(docname=doc_name, rcpt_no=get_rcpt_no, qrcode_url=get_qrcode_url)
                created_by = sell_data.get("owner")

                print("This prints immediately, before delayed print")
                ocrnDt = datetime.now().strftime("%Y%m%d")
                print(self.to_use_data)

                update_stock_items = []
                update_stock_master_items = []

                    
                    
                for item in self.to_use_data.get("itemList", []):
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
                        "pkg": item.get("pkg", 1),
                        "totDcAmt": item.get("dcAmt", 0),
                    })

                    remaining_qty = 12  
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
                    "totItemCnt": self.to_use_data['totItemCnt'],
                    "totTaxblAmt": self.to_use_data['totTaxblAmt'],
                    "totTaxAmt": self.to_use_data['totTaxAmt'],
                    "totAmt": self.to_use_data['totAmt'],
                    "regrId": created_by,
                    "regrNm": created_by,
                    "modrNm": created_by,
                    "modrId": created_by,
                    "itemList": update_stock_items
                }

                print(update_stock_payload, update_stock_master_items)
                self.run_stock_update_in_background(update_stock_payload, update_stock_master_items, created_by)


                frappe.msgprint(f"Sale made successfully: {response.get('resultMsg')}")
            else:
                frappe.throw(f"Sale save failed: {response.get('resultMsg')}")


class DebitNote(ZRAClient):
            def __init__(self):
                self.taxbl_totals = {key: 0.0 for key in self.TAX_RATES}
                self.tax_amt_totals = {key: 0.0 for key in self.TAX_RATES}
                super().__init__()

            def create_normal_sale_helper(self, payload):
                return self.normal_sale(payload)

            TAX_RATES = {
                "A": 16, "B": 16, "C1": 0, "C2": 0, "C3": 0,
                "D": 0, "E": 0, "F": 10,
                "Ipl1": 5, "Ipl2": 0,
                "Tl": 1.5,
                "ECM": 5,
                "EXEEG": 3,
                "RVAT": 16
            }


            @staticmethod
            def format_tax_amount(value):
                return float(Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))

            def generate_cis_invc_no(self):
                no = f"CIS{random.randint(1, 999):03d}-{random.randint(1000, 9999)}"
                print(f"[INFO] Generated invoice no: {no}")
                return no

            def calculate_tax_for_item(self, item):
                qty = float(item.get("qty", 0))
                price_tax_inclusive = float(item.get("prc", 0))
                discount_rate = 0.0

                vat_cat = item.get("vatCatCd")
                ipl_cat = item.get("iplCatCd")
                tl_cat = item.get("tlCatCd")
                excise_cat = item.get("exciseTxCatCd")

                print(f"\n[CALCULATE TAX] {item['itemNm']} (qty={qty}, price={price_tax_inclusive}, "
                    f"vatCatCd={vat_cat}, iplCatCd={ipl_cat}, tlCatCd={tl_cat}, exciseTxCatCd={excise_cat})")

                supply_amount = round(qty * price_tax_inclusive, 2)
                discount_amount = round(supply_amount * (discount_rate / 100), 2)

                vat_rate = self.TAX_RATES.get(vat_cat, 0) / 100 if vat_cat else 0
                ipl_rate = self.TAX_RATES["Ipl1"] / 100 if ipl_cat == "IPL1" else self.TAX_RATES["Ipl2"] / 100 if ipl_cat == "IPL2" else 0
                tl_rate = self.TAX_RATES["Tl"] / 100 if tl_cat == "TL" else 0
                ecm_rate = self.TAX_RATES["ECM"] / 100 if excise_cat == "ECM" else 0

                combined_rate_excl_ecm = vat_rate + ipl_rate + tl_rate
                base_amount = round(supply_amount / (1 + combined_rate_excl_ecm), 2) if combined_rate_excl_ecm > 0 else supply_amount

                vat_tax = round(base_amount * vat_rate, 2)
                ipl_tax = round(base_amount * ipl_rate, 2)
                tl_tax = round(base_amount * tl_rate, 2)

                ecm_taxable_amount = 0.0
                ecm_tax = 0.0

                ipl_taxable_amt = base_amount if ipl_rate > 0 else (supply_amount if ipl_cat == "IPL2" else 0.0)

                return {
                    "splyAmt": supply_amount,
                    "dcRt": discount_rate,
                    "dcAmt": discount_amount,
                    "vatTaxblAmt": base_amount if vat_cat else 0.0,
                    "vatAmt": vat_tax,
                    "iplTaxblAmt": ipl_taxable_amt,
                    "iplAmt": ipl_tax,
                    "tlTaxblAmt": base_amount if tl_rate > 0 else 0.0,
                    "tlAmt": tl_tax,
                    "ecmTaxblAmt": ecm_taxable_amount,
                    "ecmAmt": ecm_tax,
                    "totAmt": supply_amount
                }

            def build_payload(self, items, base_data):
                print("\n[BUILD PAYLOAD] Processing items...")
                processed_items = []

                for idx, item in enumerate(items):
                    tax_result = self.calculate_tax_for_item(item)

                    vat_cat = item.get("vatCatCd")
                    ipl_cat = item.get("iplCatCd")
                    tl_cat = item.get("tlCatCd")
                    excise_cat = item.get("exciseTxCatCd")

                    if vat_cat in self.TAX_RATES:
                        self.taxbl_totals[vat_cat] += tax_result["vatTaxblAmt"]
                        self.tax_amt_totals[vat_cat] += tax_result["vatAmt"]

                    if ipl_cat == "IPL1":
                        self.taxbl_totals["Ipl1"] += tax_result["iplTaxblAmt"]
                        self.tax_amt_totals["Ipl1"] += tax_result["iplAmt"]
                    elif ipl_cat == "IPL2":
                        self.taxbl_totals["Ipl2"] += tax_result["iplTaxblAmt"]

                    if tl_cat == "TL":
                        self.taxbl_totals["Tl"] += tax_result["tlTaxblAmt"]
                        self.tax_amt_totals["Tl"] += tax_result["tlAmt"]

                    if excise_cat == "ECM":
                        ecm_taxbl_amt = 150.0
                        ecm_tax_amt = round(ecm_taxbl_amt * (self.TAX_RATES["ECM"] / 100), 2)
                        self.taxbl_totals["ECM"] += ecm_taxbl_amt
                        self.tax_amt_totals["ECM"] += ecm_tax_amt
                    else:
                        ecm_taxbl_amt = 0.0
                        ecm_tax_amt = 0.0

                    processed_item = {
                        "itemSeq": idx + 1,
                        "itemCd": item["itemCd"],
                        "itemClsCd": item["itemClsCd"],
                        "itemNm": item["itemNm"],
                        "qty": float(item.get("qty", 0)),
                        "prc": float(item.get("prc", 0)),
                        "rrp": round(float(item.get("prc", 0)), 2),
                        **tax_result,
                        "vatCatCd": vat_cat or "",
                        "iplCatCd": ipl_cat or "",
                        "tlCatCd": tl_cat or "",
                        "pkgUnitCd": item.get("pkgUnitCd", "BA"),
                        "pkg": float(item.get("pkg", 1.0)),
                        "qtyUnitCd": item.get("qtyUnitCd", "BE"),
                        "bcd": item.get("bcd", ""),
                        "isrccCd": item.get("isrccCd", ""),
                        "isrccNm": item.get("isrccNm", ""),
                        "isrcRt": float(item.get("isrcRt", 0.0)),
                        "isrcAmt": float(item.get("isrcAmt", 0.0)),
                        "ecmTaxblAmt": ecm_taxbl_amt,
                        "ecmAmt": ecm_tax_amt,
                        "totAmt": round(tax_result["splyAmt"] + ecm_tax_amt, 2)
                    }

                    processed_items.append(processed_item)

                total_taxable_amount = sum(self.taxbl_totals.values())
                total_tax_amount = sum(self.tax_amt_totals.values())
                total_amount = round(total_taxable_amount + total_tax_amount, 2)
                original_invoice_no = base_data["original_sell"]
                try:
                    original_invoice = frappe.get_doc("Sales Invoice", original_invoice_no)
                    orgInvcNo = original_invoice.custom_rcpt_no if hasattr(original_invoice, 'custom_rcpt_no') else None
                    if not orgInvcNo:
                        frappe.throw("Original invoice receipt number not found")
                except Exception as e:
                    frappe.throw(f"Failed to get original invoice: {str(e)}")

                export_destination_country_code = base_data.get("export_destination_code")
                if export_destination_country_code is not None:
                    destnCountryCd = export_destination_country_code
                else:
                    destnCountryCd = None
                
                get_lpoNumber = base_data.get("lpoNumber")

                payload = {
                    "tpin": self.get_tpin(),
                    "bhfId": self.get_branch_code(),
                    "orgInvcNo":  orgInvcNo,
                    "orgSdcId": "SDC0010002709",
                    "cisInvcNo": self.generate_cis_invc_no(),
                    "custTpin": base_data["cust_tpin"],
                    "custNm": base_data["cust_name"],
                    "salesTyCd": "N",
                    "rcptTyCd": "D",
                    "pmtTyCd": "01",
                    "salesSttsCd": "02",
                    "cfmDt": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "salesDt": datetime.now().strftime("%Y%m%d"),
                    "totItemCnt": len(items),
                    **self.generate_tax_fields(),
                    "totTaxblAmt": total_taxable_amount,
                    "totTaxAmt": self.format_tax_amount(total_tax_amount),
                    "cashDcRt": 0,
                    "cashDcAmt": 0.0,
                    "totAmt": total_amount,
                    "prchrAcptcYn": "N",
                    "remark": "",
                    "regrId": "admin",
                    "regrNm": "admin",
                    "modrId": "admin",
                    "modrNm": "admin",
                    "saleCtyCd": "1",
                    "lpoNumber": None,
                    "currencyTyCd": "ZMW",
                    "exchangeRt": "1",
                    "dbtRsnCd": "03",
                    "invcAdjustReason": "",
                    "itemList": processed_items
                }
                if destnCountryCd:
                    payload["destnCountryCd"] = destnCountryCd

                print("Checkin for LOP: ", get_lpoNumber)
                if get_lpoNumber:
                    payload["lpoNumber"] = get_lpoNumber
                self.to_use_data = payload

                print(json.dumps(payload, indent=4))
                return payload

            def generate_tax_fields(self):
                return {
                    f"taxblAmt{k}": round(self.taxbl_totals.get(k, 0.0), 2)
                    for k in self.TAX_RATES
                } | {
                    f"taxRt{k}": self.TAX_RATES.get(k, 0)
                    for k in self.TAX_RATES
                } | {
                    f"taxAmt{k}": round(self.tax_amt_totals.get(k, 0.0), 2)
                    for k in self.TAX_RATES
                }
            
            def send_debit_sale_data(self, sell_data):
                customer_name = sell_data.get("customer") or sell_data.get("customer_name") or ""
                customer_doc = frappe.get_doc("Customer", customer_name)
                customer_tpin = customer_doc.get("custom_tpin") or ""
                original_sell = sell_data.get("return_against")
                export_destination_country = sell_data.get("custom_destination_country")
                lpo_number = sell_data.get("custom_lpo_number")
                is_lpo_transactions = sell_data.get("custom__lpo_transaction")
                is_export = sell_data.get("custom_export")
                if export_destination_country == "ASCENSION ISLAND":
                    export_destination_country = " "


                sell_data_item = sell_data.get("items")
                items = []
                for item in sell_data_item:

                    itemCd = item.get("item_code")
                    item_doc = frappe.get_doc("Item", itemCd)
                    formatted_items = item_doc.as_dict()
                    package_unit_code = formatted_items.get("custom_packaging_unit_code")
                    unit_of_measure = formatted_items.get("custom_units_of_measure")
                    get_ipl_name = item.get("custom_ipl")
                    get_tl_name = item.get("custom_tl")
                    get_excise_name = item.get("custom_excise")
                    get_turn_over_tax = item.get("custom_tot")
                    get_vat_name = item.get("custom_test")

            
                    tlCat = {
                    "TL":"Tourism Levy",
                    "F": "Service Charge 10%"
                    }

                    
                    iplCat = {

                        "IPL1":"Insurance Premium Levy",
                        "IPL2": "Re-Insurance"
                    }

                    
            
                    vat_tax_types = {
                        "A": "Standard Rated 16%",
                        "B": "Minimum Taxable Value (MTV)",
                        "C1": "Exports 0%",               
                        "RVAT": "RVAT Reverse VAT",           
                        "C2": "Local Purchases Order",
                        "C3": "Zero-rated by nature",
                        "D": "Exempt No tax charge",
                        "E": "Disbursement",
                    }
                    vatCd = next((key for key, value in vat_tax_types.items() if value == get_vat_name), None)
                    iplCd = next((key for key, value in iplCat.items() if value == get_ipl_name), None)
                    tlCd = next((key for key, value in tlCat.items() if value == get_tl_name), None)

                    present_codes = [code for code in [vatCd, iplCd, tlCd] if code is not None]
                    if len(present_codes) != 1:
                        frappe.throw("Exactly one of vatCd, iplCd, or tlCd must be present. Found: {}".format(len(present_codes)))

                    print(package_unit_code, unit_of_measure, get_vat_name, vatCd)
                    itemName = item.get("item_name")

                    
                
                    qty = abs((item.get("qty", 0)))

                    items.append({
                        "itemCd": itemCd,
                        "itemClsCd": "50101101",         
                        "itemNm": itemName,
                        "qty": qty,
                        "prc": 100.00,
                        "pkgUnitCd": self.get_packaging_unit(package_unit_code),
                        "qtyUnitCd": self.get_units_of_measure(unit_of_measure),                
                        "vatCatCd": vatCd,                
                        "iplCatCd": iplCd,
                        "tlCatCd": tlCd,
                        "exciseTxCatCd": None
                    })

                base_data = {
                    "cust_name": customer_name,
                    "cust_tpin": customer_tpin,
                    "original_sell": original_sell,
                }

                if is_export == 1 or vatCd == "C1":
                    self.validate_export(vatCd, export_destination_country, is_export)

                    if export_destination_country == "N / A":
                        frappe.throw("Destination country is required. Please select a valid country.")

                    destination_country_code = self.get_country_code_by_name(export_destination_country)
                    base_data["export_destination_code"] = destination_country_code 


                if iplCd is not None and (vatCd is not None or tlCd is not None):
                    frappe.throw(
                        f"[ZRA Error] IPL transactions (iplCd) must not be combined with VAT or TL. Found: vatCd={vatCd}, tlCd={tlCd}"
                    )
                
                if is_lpo_transactions == 1:
                    if vatCd != "C2":
                        frappe.throw("Only VAT Code 'C2' is allowed for LPO transactions.")
                    if not lpo_number:
                        frappe.throw("LPO Number is required when VAT Code is 'C2' for LPO transactions.")
                    if len(lpo_number) < 9 or len(lpo_number) > 20:
                        frappe.throw("LPO Number length must be between 9 and 20 characters.")
                    base_data["lpoNumber"] = lpo_number

                if vatCd == "C2" and not is_lpo_transactions:
                    frappe.throw("For VAT Code 'C2', LPO transaction must be checked.")

                print("\n[START] Sending sale data...")
                payload = self.build_payload(items, base_data)
                response = self.create_normal_sale_helper(payload)
                
                if response.get("resultCd") == "000":
                    get_rcpt_no = response.get("data", {}).get("rcptNo")
                    get_qrcode_url = response.get("data", {}).get("qrCodeUrl") 
                    print("Stock master updated successfully after sale.")
                    doc_name = sell_data.get("name")
                    self.update_rcptNo_delayed(docname=doc_name, rcpt_no=get_rcpt_no, qrcode_url=get_qrcode_url)
                    created_by = sell_data.get("owner")

                    print("This prints immediately, before delayed print")
                    ocrnDt = datetime.now().strftime("%Y%m%d")
                    print(self.to_use_data)

                    update_stock_items = []
                    update_stock_master_items = []

                        
                        
                    for item in self.to_use_data.get("itemList", []):
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
                            "pkg": item.get("pkg", 1),
                            "totDcAmt": item.get("dcAmt", 0),
                        })

                        remaining_qty = 12  
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
                        "totItemCnt": self.to_use_data['totItemCnt'],
                        "totTaxblAmt": self.to_use_data['totTaxblAmt'],
                        "totTaxAmt": self.to_use_data['totTaxAmt'],
                        "totAmt": self.to_use_data['totAmt'],
                        "regrId": created_by,
                        "regrNm": created_by,
                        "modrNm": created_by,
                        "modrId": created_by,
                        "itemList": update_stock_items
                    }

                    print(update_stock_payload, update_stock_master_items)
                    self.run_stock_update_in_background(update_stock_payload, update_stock_master_items, created_by)


                    frappe.msgprint(f"Sale made successfully: {response.get('resultMsg')}")
                else:
                    frappe.throw(f"Sale save failed: {response.get('resultMsg')}")




