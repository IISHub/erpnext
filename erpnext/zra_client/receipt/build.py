from erpnext.zra_client.receipt.generate import InvoicePDF

class BuildPdf:
    def build_invoice(self, company_info, customer_info, invoice, items, sdc_data):
        company_name, company_phone, company_email = company_info[0]
        cust_tpin, cust_name = customer_info[0]
        invoice_number, invoice_date, invoice_type = invoice[0]
        current_date, sdc_id = sdc_data[0]

        invoice_data = {
            "company": {
                "name": company_name,
                "phone": company_phone,
                "email": company_email,
                "tpin": getattr(self, "get_company_tpin", lambda: "")()
            },
            "customer": {
                "name": cust_name,
                "tpin": cust_tpin
            },
            "invoice": {
                "number": invoice_number,
                "date": invoice_date,
                "type": invoice_type  
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
            "sdc_info": {
                "invoice_date": invoice_date,
                "sdc_id": sdc_id,
                "invoice_number": invoice_number,
                "invoice_type": "Normal invoice",
                "current_date": current_date
            },
            "payment": {"type": "Cash"},
            "internal_data": {}
        }

        builder = InvoicePDF(invoice_data)
        result = builder.build_pdf(invoice_number)

        print("PDF saved with file ID:", result)
