from erpnext.zra_client.receipt.generate import InvoicePDF

class BuildPdf:
    def build_invoice(self):
        invoice_data = {
            "company": {
                "name": "IZYANE INOVSOLUTIONS LIMITED",
                "tpin": "100200300",
                "phone": "+260 777 123456",
                "email": "info@izyane.com"
            },
            "customer": {"name": "First National Bank Zambia", "tpin": "200300400"},
            "invoice": {"number": "INV-001", "date": "2025-09-04"},
            "items": [
                {"name": "Laptop", "qty": 2, "price": 1200.00, "total": 2400.00, "tax_type": "A"},
                {"name": "Mouse", "qty": 3, "price": 15.00, "total": 45.00, "tax_type": "B"}
            ],
            "totals": {
                "standard_rated": 862.07,
                "mtv": 0,
                "reverse_vat": 0,
                "subtotal": 862.07,
                "tax": 137.93,
                "grand_total": 1000.00,
                "currency": "ZMW",
                "exchange_rate": "1 ZMW = 1.0000 ZMW"
            },
            "sdc_info": {
                "invoice_date": "04/09/2025 09:06:53",
                "sdc_id": "SDC0010002709",
                "invoice_number": "INV0010002709/856",
                "invoice_type": "Normal invoice"
            },
            "payment": {"type": "Cash"},
            "internal_data": {
                "value": "USQH-NSZE-GE3P-HDYM-UHFG-BTYR-AE",
                "receipt_signature": "NB3B-75ZE-KIYU-PSSQ"
            }
        }

        # Save PDF without attaching to any document
        file_doc = InvoicePDF(invoice_data).build_pdf()
        print("PDF saved with file ID:")
