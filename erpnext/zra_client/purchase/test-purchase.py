import json
import random
from datetime import datetime
import requests

# Constants for tax rates (%)
TAX_RATES = {
    "A": 16,         # VAT
    "B": 16,
    "C1": 0,
    "C2": 0,
    "C3": 0,
    "D": 0,
    "E": 0,
    "F": 10,         # Service Charge
    "IPL1": 5,       # Insurance Premium Levy 1
    "IPL2": 0,       # Insurance Premium Levy 2 (exempt)
    "Tl": 1.5,       # Tourism Levy
    "ECM": 5,        # Excise Tax
    "EXEEG": 3,
    "RVAT": 16
}

API_URL = "http://localhost:8080/sandboxvsdc1.0.8.0/trnsSales/saveSales"

def generate_cis_invc_no():
    no = f"CIS{random.randint(1, 999):03d}-{random.randint(1000, 9999)}"
    print(f"[INFO] Generated invoice no: {no}")
    return no

def calculate_tax_for_item(item):
    qty = float(item.get("qty", 0))
    price_tax_inclusive = float(item.get("prc", 0))
    discount_rate = 0.0  # Assuming no discount

    vat_cat = item.get("vatCatCd")
    ipl_cat = item.get("iplCatCd")
    tl_cat = item.get("tlCatCd")
    excise_cat = item.get("exciseTxCatCd")

    print(f"\n[CALCULATE TAX] {item['itemNm']} (qty={qty}, price={price_tax_inclusive}, "
          f"vatCatCd={vat_cat}, iplCatCd={ipl_cat}, tlCatCd={tl_cat}, exciseTxCatCd={excise_cat})")

    supply_amount = round(qty * price_tax_inclusive, 2)
    discount_amount = round(supply_amount * (discount_rate / 100), 2)

    # Initialize tax rates to zero
    vat_rate = TAX_RATES.get(vat_cat, 0) / 100 if vat_cat else 0
    tl_rate = TAX_RATES["Tl"] / 100 if tl_cat == "TL" else 0
    ecm_rate = TAX_RATES["ECM"] / 100 if excise_cat == "ECM" else 0
    ipl_rate = 0

    if ipl_cat == "IPL1":
        ipl_rate = TAX_RATES["IPL1"] / 100
        vat_rate = 0
        tl_rate = 0
        ecm_rate = 0
    elif ipl_cat == "IPL2":
        ipl_rate = TAX_RATES["IPL2"] / 100
        vat_rate = 0
        tl_rate = 0
        ecm_rate = 0

    combined_rate_excl_ecm = vat_rate + ipl_rate + tl_rate

    if combined_rate_excl_ecm > 0:
        base_amount = round(supply_amount / (1 + combined_rate_excl_ecm), 2)
    else:
        base_amount = supply_amount

    vat_tax = round(base_amount * vat_rate, 2)
    ipl_tax = round(base_amount * ipl_rate, 2)
    tl_tax = round(base_amount * tl_rate, 2)

    ecm_taxable_amount = 150.0 if excise_cat == "ECM" and ipl_cat not in ["IPL1", "IPL2"] else 0.0
    ecm_tax = round(ecm_taxable_amount * ecm_rate, 2)

    ipl_taxable_amt = base_amount if ipl_rate > 0 else (supply_amount if ipl_cat == "IPL2" else 0.0)

    total_amount = round(base_amount + vat_tax + ipl_tax + tl_tax + ecm_tax, 2)

    return {
        "splyAmt": supply_amount,
        "dcRt": discount_rate,
        "dcAmt": discount_amount,
        "vatTaxblAmt": base_amount if vat_rate > 0 else 0.0,
        "vatAmt": vat_tax,
        "iplTaxblAmt": ipl_taxable_amt,
        "iplAmt": ipl_tax,
        "tlTaxblAmt": base_amount if tl_rate > 0 else 0.0,
        "tlAmt": tl_tax,
        "ecmTaxblAmt": ecm_taxable_amount,
        "ecmAmt": ecm_tax,
        "totAmt": total_amount
        
    }

def build_payload(items):
    processed_items = []
    taxbl_totals = {key: 0.0 for key in TAX_RATES}
    tax_amt_totals = {key: 0.0 for key in TAX_RATES}

    print("\n[BUILD PAYLOAD] Processing items...")

    for idx, item in enumerate(items):
        tax_result = calculate_tax_for_item(item)

        vat_cat = item.get("vatCatCd")
        ipl_cat = item.get("iplCatCd")
        tl_cat = item.get("tlCatCd")
        excise_cat = item.get("exciseTxCatCd")

        if vat_cat in TAX_RATES:
            taxbl_totals[vat_cat] += tax_result["vatTaxblAmt"]
            tax_amt_totals[vat_cat] += tax_result["vatAmt"]

        if ipl_cat:
            ipl_key = ipl_cat.upper()
            if ipl_key in taxbl_totals:
                taxbl_totals[ipl_key] += tax_result["iplTaxblAmt"]
                tax_amt_totals[ipl_key] += tax_result["iplAmt"]

        if tl_cat == "TL":
            taxbl_totals["Tl"] += tax_result["tlTaxblAmt"]
            tax_amt_totals["Tl"] += tax_result["tlAmt"]

        if excise_cat == "ECM":
            taxbl_totals["ECM"] += tax_result["ecmTaxblAmt"]
            tax_amt_totals["ECM"] += tax_result["ecmAmt"]

        processed_items.append({
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
        })

    total_taxable_amount = round(sum(item["vatTaxblAmt"] for item in processed_items), 2)


    total_tax_amount = round(sum(
        item["vatAmt"] + item["iplAmt"] + item["tlAmt"] + item["ecmAmt"]
        for item in processed_items
    ), 2)
    total_amount = round(sum(item["totAmt"] for item in processed_items), 2)

    payload = {
        "tpin": "2484778002",
        "bhfId": "000",
        "orgInvcNo": 0,
        "cisInvcNo": generate_cis_invc_no(),
        "custTpin": "2000000000",
        "custNm": "Smart Customer",
        "salesTyCd": "N",
        "rcptTyCd": "S",
        "pmtTyCd": "01",
        "salesSttsCd": "02",
        "cfmDt": datetime.now().strftime("%Y%m%d%H%M%S"),
        "salesDt": datetime.now().strftime("%Y%m%d"),
        "totItemCnt": len(items),
        "taxblAmtA": taxbl_totals.get("A", 0.0),
        "taxRtA": TAX_RATES.get("A", 0),
        "taxAmtA": tax_amt_totals.get("A", 0.0),
        "taxblAmtB": taxbl_totals.get("B", 0.0),
        "taxRtB": TAX_RATES.get("B", 0),
        "taxAmtB": tax_amt_totals.get("B", 0.0),
        "taxblAmtC1": taxbl_totals.get("C1", 0.0),
        "taxRtC1": TAX_RATES.get("C1", 0),
        "taxAmtC1": tax_amt_totals.get("C1", 0.0),
        "taxblAmtC2": taxbl_totals.get("C2", 0.0),
        "taxRtC2": TAX_RATES.get("C2", 0),
        "taxAmtC2": tax_amt_totals.get("C2", 0.0),
        "taxblAmtC3": taxbl_totals.get("C3", 0.0),
        "taxRtC3": TAX_RATES.get("C3", 0),
        "taxAmtC3": tax_amt_totals.get("C3", 0.0),
        "taxblAmtE": taxbl_totals.get("E", 0.0),
        "taxRtE": TAX_RATES.get("E", 0),
        "taxAmtE": tax_amt_totals.get("E", 0.0),
        "taxblAmtRvat": taxbl_totals.get("RVAT", 0.0),
        "taxRtRvat": TAX_RATES.get("RVAT", 0),
        "taxAmtRvat": tax_amt_totals.get("RVAT", 0.0),
        "taxblAmtIpl1": taxbl_totals.get("IPL1", 0.0),
        "taxRtIpl1": TAX_RATES.get("IPL1", 0),
        "taxAmtIpl1": tax_amt_totals.get("IPL1", 0.0),
        "taxblAmtIpl2": taxbl_totals.get("IPL2", 0.0),
        "taxRtIpl2": TAX_RATES.get("IPL2", 0),
        "taxAmtIpl2": tax_amt_totals.get("IPL2", 0.0),
        "taxblAmtTl": taxbl_totals.get("Tl", 0.0),
        "taxRtTl": TAX_RATES.get("Tl", 0),
        "taxAmtTl": tax_amt_totals.get("Tl", 0.0),
        "taxblAmtEcm": taxbl_totals.get("ECM", 0.0),
        "taxRtEcm": TAX_RATES.get("ECM", 0),
        "taxAmtEcm": tax_amt_totals.get("ECM", 0.0),
        "taxblAmtExeeg": taxbl_totals.get("EXEEG", 0.0),
        "taxRtExeeg": TAX_RATES.get("EXEEG", 0),
        "taxAmtExeeg": tax_amt_totals.get("EXEEG", 0.0),
        "totTaxblAmt": total_taxable_amount,
        "totTaxAmt": total_tax_amount,
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
        "currencyTyCd": "USD",
        "exchangeRt": "23",
        "dbtRsnCd": "",
        "invcAdjustReason": "",
        "itemList": processed_items
    }

    print(json.dumps(payload, indent=4))
    return payload

def send_sale_data():
    items = [
        {
            "itemCd": "40021",
            "itemClsCd": "50101101",
            "itemNm": "Test Item C1",
            "qty": 1.0,
            "prc": 100.00,
            "vatCatCd": "A",
            "iplCatCd": None,
            "tlCatCd": "TL",
            "exciseTxCatCd": None
        }
    ]
    print("\n[START] Sending sale data...")
    payload = build_payload(items)

    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        print(f"\n[RESPONSE] Status: {response.status_code}")
        print(f"[RESPONSE] Body: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed: {e}")

    print("\n[END] Sale data processing complete.")

if __name__ == "__main__":
    send_sale_data()
