from erpnext.zra_client.receipt.generate import InvoicePDF
class BuildPdf:
    def build_invoice(self, company_info, customer_info, invoice, items):
        # Extract values from the lists/tuples
        company_name, company_phone, company_email = company_info[0]
        cust_tpin, cust_name = customer_info[0]
        invoice_number, invoice_date = invoice[0]

        # Prepare invoice_data dict dynamically
        invoice_data = {
            "company": {
                "name": company_name,
                "phone": company_phone,
                "email": company_email,
                # optional TPIN, add if you have a method for it
                "tpin": getattr(self, "get_company_tpin", lambda: "")()
            },
            "customer": {
                "name": cust_name,
                "tpin": cust_tpin
            },
            "invoice": {
                "number": invoice_number,
                "date": invoice_date
            },
            "items": [
                {
                    "name": item["itemNm"],
                    "qty": item["qty"],
                    "price": item["prc"],
                    "total": item["totAmt"],
                    "tax_type": item.get("vatCatCd", "")
                }
                for item in items
            ],
            "totals": {
                "standard_rated": sum(i.get("vatTaxblAmt", 0) for i in items),
                "mtv": sum(i.get("mtv", 0) for i in items),
                "reverse_vat": sum(i.get("tlAmt", 0) for i in items),
                "subtotal": sum(i.get("splyAmt", 0) for i in items),
                "tax": sum(i.get("vatAmt", 0) for i in items),
                "grand_total": sum(i.get("totAmt", 0) for i in items),
                "currency": "ZMW",
                "exchange_rate": "1 ZMW = 1.0000 ZMW"
            },
            # Optional sections
            "sdc_info": {},
            "payment": {"type": "Cash"},
            "internal_data": {}
        }

        # Save PDF
        file_doc = InvoicePDF(invoice_data).build_pdf()
        print("PDF saved with file ID:", file_doc)

