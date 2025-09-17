from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.error.exceptions import RequestException, RETRYABLE_ERRORS
from erpnext.zra_client.purchase.main import ResponseRetry
import frappe
import requests
from frappe import _

zra_instance = ZRAClient()

class ZRACustomerClient:
    def create_customer_helper(self, customer_data: dict):
        print(customer_data)
        tpin = customer_data.get("custom_tpin")
        customer_name = customer_data.get("customer_name") or ""
        email_id = customer_data.get("custom_customer_email") or ""
        mobile_no = customer_data.get("custom_customer_number") or ""
        created_by = customer_data.get("modified_by")

        self._validate_customer_inputs(tpin, mobile_no)
        if frappe.db.exists("Customer", {"custom_tpin": tpin}):
            frappe.throw(
                _("A customer with TPIN {0} already exists.").format(frappe.bold(tpin))
            )
        zra_client = ZRAClient()
        logged_in_user = zra_client.get_logged_in_details(created_by)
        username = logged_in_user.get("username", "system")

        payload = {
            "tpin": zra_client.get_tpin(),
            "bhfId": zra_client.get_branch_code(),
            "custNo": mobile_no,
            "custTpin": tpin,
            "custNm": customer_name,
            "adrs": None,
            "email": email_id,
            "faxNo": None,
            "useYn": "Y",
            "remark": None,
            "regrNm": username,
            "regrId": username,
            "modrNm": username,
            "modrId": username,
        }
        try:
            result = zra_client.create_customer(payload)
            return self._handle_zra_response(result, payload)

        except requests.exceptions.Timeout:
            RequestException("TIMEOUT").throw()

        except requests.exceptions.RequestException:
            RequestException("REQUEST_FAILED").throw()

        except Exception as e:
            frappe.log_error(message=str(e), title="ZRA Customer Creation Error")
            RequestException("UNKNOWN_ERROR").throw()

    def _validate_customer_inputs(self, tpin: str, mobile_no: str):
        if not tpin:
            frappe.throw(
                _("Customer TPIN ({0}) is required.").format(frappe.bold("custom_tpin"))
            )

        if len(tpin) < 10:
            frappe.throw(_("Invalid TPIN: must be at least 10 characters long."))

        if not mobile_no:
            frappe.throw(_("Customer mobile number is required."))

        if len(mobile_no) < 10:
            frappe.throw(_("Invalid Mobile Number: must be at least 10 digits."))

    def _handle_zra_response(self, result, payload: dict):
        try:
            data = result.json()
        except ValueError:
            RequestException("UNKNOWN_RESPONSE").throw()

        result_cd = data.get("resultCd")

        if result_cd == "000":
            frappe.msgprint(_("Customer has been saved successfully."))

            site = frappe.local.site if hasattr(frappe.local, "site") else "erpnext.localhost"
            customer_tpin = payload["custTpin"]
            if "zra_instance" in globals():
                zra_instance.update_customer_status_by_tpin(customer_tpin, 1, 10, site)

            return data
        if result_cd in RETRYABLE_ERRORS:
            return ResponseRetry(payload, task_type=1).determine_task_type()
        RequestException(result_cd or "CREATE_CUSTOMER_ERROR").throw()
