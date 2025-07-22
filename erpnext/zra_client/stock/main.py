from erpnext.zra_client.main import ZRAClient

class Stock(ZRAClient):


    
    def create_stock(self):
        total_taxable = 0
        total_tax = 0
        total_amount = 0

        payload = {
            "tpin": zra_client.tpin,
            "bhfId": zra_client.branch_code,
            "sarNo": 1,
            "orgSarNo": 0,
            "regTyCd": "M",
            "custTpin": None,
            "custNm": None,
            "custBhfId": None,
            "sarTyCd": "02",
            "ocrnDt": stock_data.get("posting_date", "").replace("-", "") if stock_data.get("posting_date") else None,
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

        for idx, item in enumerate(items, start=1):
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

            # Try valuation_rate from Stock Entry item
            valuation_rate = flt(item.get("valuation_rate", 0))

            # Fallback to item default price
            if not valuation_rate:
                valuation_rate = flt(item_doc.get("custom_default_unit_price", 0))

            # If valuation rate is still zero or missing, log error or handle zero valuation allowance
            if valuation_rate == 0:
                allow_zero_val_rate = item.get("allow_zero_valuation_rate", False)
                if not allow_zero_val_rate:
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

            payload["itemList"].append({
                "itemSeq": idx,
                "itemCd": item_code,
                "itemClsCd": item_doc.get("item_class_code") or "NA",
                "itemNm": item_doc.item_name,
                "pkgUnitCd": item_doc.get("custom_packaging_unit_code") or "PKG",
                "qtyUnitCd": item_doc.get("custom_units_of_measure") or "EA",
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

        try:
            client = ZRAClient()
            response = client.save_stock(payload)

            if response.get("resultCd") == "000":
                create_by = stock_data.get("owner")
                print("✅ ZRA Response OK. Proceeding with stock update...")

                if not items:
                    print("⚠️ No items found to update in stock.")
                else:
                    stock_items = []
                    for item in items:
                        item_code = item.get("item_code")
                        qty = flt(item.get("qty", 0))

                        if not item_code:
                            print("⚠️ Skipping item with no item_code.")
                            continue

                        stock_items.append({
                            "itemCd": item_code,
                            "rsdQty": qty
                        })

                    try:
                        save_stock_master = client.save_stock_master(
                            created_by=create_by,
                            stock_items=stock_items
                        )
                        print(f"✅ Stock Master Update Response:", save_stock_master)

                    except Exception as e:
                        frappe.log_error(
                            title=f"❌ Failed to update stock master",
                            message=str(e)
                        )
            else:
                print("❌ ZRA Response Code NOT '000'. Skipping stock master update.")
                print("🧾 Full response:", response)
                frappe.throw(f"ZRA returned error: {response.get('resultMsg')}")

        except Exception as e:
            frappe.log_error(title="❌ ZRA Save Stock Failed", message=str(e))
            frappe.throw(f"ZRA Error: {e}")