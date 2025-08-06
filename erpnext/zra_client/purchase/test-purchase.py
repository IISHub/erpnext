import requests


url = "http://localhost:8080/sandboxvsdc1.0.8.0/trnsPurchase/savePurchase"

def call_purchase():
    payload ={
        "tpin": "2484778002",
        "bhfId": "000",
        "cisInvcNo": "CIS134",
        "regTyCd": "M",
        "pchsTyCd": "N",
        "rcptTyCd": "P",
        "pmtTyCd": "01",
        "pchsSttsCd": "02",
        "cfmDt": "20250716140000",
        "pchsDt": "20250716",
        "cnclReqDt": "",
        "cnclDt": "",
        "totItemCnt": 1,
        "totTaxblAmt": 86.21,
        "totTaxAmt": 13.79,
        "totAmt": 100.00,
        "remark": "Purchase test",
        "regrNm": "ADMIN",
        "regrId": "ADMIN",
        "modrNm": "ADMIN",
        "modrId": "ADMIN",
        "itemList": [
            {
            "itemSeq": 1,
            "itemCd": "ZM2BGKG0000001",
            "itemClsCd": "50102517",
            "itemNm": "Item Name 1",
            "pkgUnitCd": "BG",
            "pkg": 1,
            "qtyUnitCd": "KG",
            "qty": 1,
            "prc": 200.00,
            "splyAmt": 100.00,
            "dcRt": 0.00,
            "dcAmt": 0.00,
            "taxTyCd": "B",
            "iplCatCd": "",
            "tlCatCd": "",
            "exciseCatCd": "",
            "taxblAmt": 86.21,
            "vatCatCd": "A",
            "iplTaxblAmt": 0.00,
            "tlTaxblAmt": 0.00,
            "exciseTaxblAmt": 0.00,
            "taxAmt": 13.79,
            "iplAmt": 0.00,
            "tlAmt": 0.00,
            "exciseTxAmt": 0.00,
            "totAmt": 100.00
            }
        ]
        }

    try:
        response = requests.post(url=url, json=payload, timeout=10)
        response.raise_for_status() 
        json_result = response.json()
        print(json_result)

    except requests.exceptions.Timeout:
        print("Request timed out. Please try again later.")

    except requests.exceptions.ConnectionError:
        print("Failed to connect to the server. Check your internet or server status.")

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Status Code: {response.status_code}")

    except requests.exceptions.RequestException as req_err:
        print(f"Request failed: {req_err}")

    except ValueError as json_err:
        print(f"Failed to parse JSON response: {json_err}")
    
call_purchase()
