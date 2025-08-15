# customer_tasks.py
import frappe
from erpnext.zra_client.main import ZRAClient
from frappe.utils.background_jobs import get_jobs

zra_obj = ZRAClient()

def get_pending_customers():
    """Fetch all customers with Pending submission status"""
    frappe.logger().info("get_pending_customers started")
    customers = frappe.get_all(
        "Customer",
        filters={"custom_submission_status": "Pending"},
        fields=[
            "name",
            "customer_name",
            "customer_type",
            "custom_submission_status",
            "custom_customer_number",
            "custom_tpin",
            "custom_customer_email"
        ]
    )
    frappe.logger().info(f"Found {len(customers)} pending customers")
    return customers

def process_pending_customers(**kwargs):
    """Process pending customers and log payloads"""
    user = kwargs.get("user", "Administrator")
    frappe.logger().info(f"process_pending_customers started by {user}")

    customer_data = get_pending_customers()
    if not customer_data:
        frappe.logger().info("No pending customers found")
        return

    for customer in customer_data:
        payload = {
            "tpin": zra_obj.get_tpin(),
            "bhfId": zra_obj.get_branch_code(),
            "custNo": customer.get("custom_customer_number"),
            "custTpin": customer.get("custom_tpin"),
            "custNm": customer.get("customer_name"),
            "adrs": None,
            "email": customer.get("custom_customer_email"),
            "faxNo": None,
            "useYn": "Y",
            "remark": None,
            "regrNm": user,
            "regrId": user,
            "modrNm": user,
            "modrId": user
        }
        frappe.logger().info(f"Payload for customer {customer.get('name')}: {payload}")

def enqueue_process_pending_customers(user="Administrator"):
    running_jobs = get_jobs(queue="short", key="process_pending_customers")
    if running_jobs:
        frappe.logger().info("process_pending_customers job already running. Skipping enqueue.")
        return

    frappe.logger().info(f"Enqueueing process_pending_customers job by user: {user}")
    frappe.enqueue(
        process_pending_customers,
        queue="short",
        timeout=600,
        kwargs={"user": user}
    )

if __name__ == "__main__":
    enqueue_process_pending_customers()
