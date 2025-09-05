import os
import uuid
from frappe import get_doc, _  # frappe functions
from frappe.utils.file_manager import save_file
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF


class InvoicePDF:
    def __init__(self, invoice_data):
        self.invoice_data = invoice_data

    def draw_nav(self, c, width, height):
        logo_path = "logo.png"
        logo_width, logo_height = 2*inch, 1*inch
        top_y = height - 1*inch

        try:
            logo = ImageReader(logo_path)
            c.drawImage(logo, width - logo_width - 1*inch,
                        top_y - logo_height + 0.2*inch,
                        width=logo_width, height=logo_height,
                        preserveAspectRatio=True, mask="auto")
        except:
            pass

        text_y = top_y
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.black)
        c.drawString(1*inch, text_y, self.invoice_data["company"]["name"])

        c.setFont("Helvetica", 10)
        text_y -= 0.2*inch
        c.drawString(1*inch, text_y, f"TPIN: {self.invoice_data['company']['tpin']}")
        text_y -= 0.2*inch
        c.drawString(1*inch, text_y, f"Phone: {self.invoice_data['company']['phone']}")
        text_y -= 0.2*inch
        c.drawString(1*inch, text_y, f"Email: {self.invoice_data['company']['email']}")

        c.setStrokeColor(colors.grey)
        c.setLineWidth(1)
        c.line(1*inch, text_y - 0.2*inch, width - 1*inch, text_y - 0.2*inch)

        return text_y - 0.6*inch

    def draw_hero(self, c, width, start_y):
        c.setFont("Helvetica-Bold", 12)
        c.drawString(1*inch, start_y, "Bill To:")
        c.setFont("Helvetica", 10)
        c.drawString(1*inch, start_y - 0.2*inch, self.invoice_data["customer"]["name"])
        c.drawString(1*inch, start_y - 0.4*inch, f"TPIN: {self.invoice_data['customer']['tpin']}")

        c.drawRightString(width - 1*inch, start_y, f"Invoice No: {self.invoice_data['invoice']['number']}")
        c.drawRightString(width - 1*inch, start_y - 0.3*inch, f"Date: {self.invoice_data['invoice']['date']}")
        return start_y - 0.8*inch

    def draw_invoice_title(self, c, width, start_y):
        c.setFont("Helvetica-Bold", 18)
        c.setFillColor(colors.HexColor("#2c3e50"))
        c.drawCentredString(width / 2, start_y, "TAX INVOICE")
        return start_y - 0.4*inch

    def draw_items_table(self, c, width, start_y):
        currency = self.invoice_data.get("totals", {}).get("currency", "ZMW")
        data = [["#", "Name", "Qty", "Unit Price", "Total ("+currency+")", "Tax Cat"]]

        for idx, item in enumerate(self.invoice_data["items"], start=1):
            total_value = item.get('total', item['qty']*item['price'])
            data.append([
                str(idx),
                item["name"],
                str(item["qty"]),
                f"{item['price']:.2f}",
                f"{total_value:.2f} {currency}",
                item.get("tax_type","Standard Rated")
            ])

        table = Table(data, colWidths=[0.5*inch, 2.5*inch, 0.7*inch, 1*inch, 1.2*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2c3e50")),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,0),10),
            ('BOTTOMPADDING',(0,0),(-1,0),8),
            ('BACKGROUND',(0,1),(-1,-1),colors.whitesmoke),
            ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ]))

        table.wrapOn(c, width, start_y)
        table.drawOn(c, 1*inch, start_y - len(data)*0.28*inch)
        return start_y - (len(data)+1)*0.28*inch

    def draw_totals(self, c, width, start_y):
        totals = self.invoice_data.get("totals", {})
        currency = totals.get("currency", "ZMW")
        c.setFont("Helvetica-Bold", 10)
        y = start_y
        lines = [
            ("Taxable Standard Rated - A (16%)", totals.get("standard_rated",0)),
            ("Taxable MTV - B (16%)", totals.get("mtv",0)),
            ("Taxable Reverse VAT - RVAT (16%)", totals.get("reverse_vat",0)),
            ("", ""),
            ("Sub-total", totals.get("subtotal",0)),
            ("VAT (16%)", totals.get("tax",0)),
            ("Total Amount", totals.get("grand_total",0)),
        ]
        start_x, value_x = width/2, width - 0.5*inch
        for label, value in lines:
            if label and isinstance(value,(int,float)):
                c.drawString(start_x, y, label)
                c.drawRightString(value_x, y, f"{value:,.2f} {currency}")
            elif label:
                c.setFont("Helvetica-Oblique",7)
                c.drawString(start_x, y, label)
                c.setFont("Helvetica", 6)
            y -= 0.25*inch
        return y - 0.2*inch

    def draw_sdc_info(self, c, width, start_y):
        sdc = self.invoice_data.get("sdc_info", {})
        payment = self.invoice_data.get("payment", {})

        left_x, right_x = 1*inch, width/2 + 0.5*inch
        y = start_y

        # SDC Information Section
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#2c3e50"))
        c.drawString(left_x, y, "SDC INFORMATION")
        c.setFont("Helvetica", 9)
        
        y_offset = 0.25*inch
        y_curr = y - y_offset
        
        # SDC Details
        sdc_details = [
            ("SDC ID:", sdc.get('sdc_id', 'N/A')),
            ("Invoice Date:", sdc.get('invoice_date', 'N/A')),
            ("Current Date:", sdc.get('current_date', 'N/A')),
            ("Invoice Number:", sdc.get('invoice_number', 'N/A')),
            ("Invoice Type:", sdc.get('invoice_type', 'Normal invoice')),
            ("Payment Type:", payment.get('type', 'Cash'))
        ]
        
        for label, value in sdc_details:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(left_x, y_curr, label)
            c.setFont("Helvetica", 9)
            c.drawString(left_x + 1.2*inch, y_curr, str(value))
            y_curr -= y_offset

        # Right column - ZRA Compliance Information
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#2c3e50"))
        c.drawString(right_x, y, "ZRA COMPLIANCE")
        c.setFont("Helvetica", 9)
        
        y_curr_right = y - y_offset
        
        compliance_info = [
            ("Tax Authority:", "Zambia Revenue Authority"),
            ("Compliance Status:", "Valid"),
            ("SDC Status:", "Active"),
            ("Tax Category:", "VAT Registered"),
            ("Fiscal Device:", "Certified SDC")
        ]
        
        for label, value in compliance_info:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(right_x, y_curr_right, label)
            c.setFont("Helvetica", 9)
            c.drawString(right_x + 1.5*inch, y_curr_right, value)
            y_curr_right -= y_offset

        return min(y_curr, y_curr_right) - 0.6*inch

    def draw_qrcode_below_sdc(self, c, width, y_start, gap=0.7*inch):
        qr_data = f"Invoice: {self.invoice_data['invoice']['number']}\nCustomer: {self.invoice_data['customer']['name']}\nTotal: {self.invoice_data['totals']['grand_total']} {self.invoice_data['totals']['currency']}"
        qr_code = qr.QrCodeWidget(qr_data)
        bounds = qr_code.getBounds()
        size = 1*inch
        scale_x = size / (bounds[2]-bounds[0])
        scale_y = size / (bounds[3]-bounds[1])
        d = Drawing(size, size, transform=[scale_x,0,0,scale_y,0,0])
        d.add(qr_code)
        x = (width - size)/2
        y = y_start - gap
        renderPDF.draw(d, c, x, y)

    def draw_footer(self, c, width):
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.grey)
        c.drawCentredString(width/2, 0.9*inch, "Powered by ZRA Smart Invoice!")
        c.drawCentredString(width/2, 0.7*inch, f"Created By: {self.invoice_data.get('created_by','Timothy Simwawa')}")

    def add_watermark(self, c, width, height):
        try:
            logo = ImageReader("logo.png")
            wm_width, wm_height = width*0.9, height*0.9
            x, y = (width - wm_width)/2, (height - wm_height)/2
            c.saveState()
            c.setFillAlpha(0.05)
            c.drawImage(logo, x, y, width=wm_width, height=wm_height, preserveAspectRatio=True, mask='auto')
            c.restoreState()
        except:
            pass

    def build_pdf(self, site_folder=None, site_name="erpnext.localhost"):
        if site_folder is None:
            site_folder = os.path.join(os.getcwd(), "erpnext.localhost")
        output_folder = os.path.join(site_folder, "public", "files", "uploads")
        os.makedirs(output_folder, exist_ok=True)

        filename = str(uuid.uuid4()) + ".pdf"
        file_path = os.path.join(output_folder, filename)
        c = canvas.Canvas(file_path, pagesize=A4)
        width, height = A4
        self.add_watermark(c, width, height)
        hero_start_y = self.draw_nav(c, width, height)
        items_start_y = self.draw_hero(c, width, hero_start_y)
        items_start_y = self.draw_invoice_title(c, width, items_start_y)
        totals_start_y = self.draw_items_table(c, width, items_start_y)
        sdc_start_y = self.draw_totals(c, width, totals_start_y)
        footer_start_y = self.draw_sdc_info(c, width, sdc_start_y)
        self.draw_qrcode_below_sdc(c, width, footer_start_y, gap=0.7*inch)
        self.draw_footer(c, width)
        c.showPage()
        c.save()

        public_url = f"http://{site_name}/files/uploads/{filename}"
        print(f"PDF saved at: {file_path}")
        print(f"Accessible URL: {public_url}")
        return public_url

