import requests
import frappe

# Centralized error messages



RETRYABLE_ERRORS = [
    "TIMEOUT", "CONNECTION", "REQUEST_FAILED", "UNKNOWN_RESPONSE",
    "HTTP_ERROR", "UNEXPECTED_ERROR", "838", "894", "801", "802"
]

ERRORS = {
    # General errors
    "TIMEOUT": "The request took too long to process. Please try again later.",
    "CONNECTION": "Network problem detected. Please check your internet connection and try again.",
    "INVALID_PRINCIPAL_ID": "The provided principal ID was not found. Please check and try again.",
    "UNKNOWN_RESPONSE": "Received an unexpected response from the system. Please try again later.",
    "SALE_ERROR": "There was a problem with your sale submission. Please try again.",
    "CREATE_CUSTOMER_ERROR": "There was a problem with your customer creation request. Please try again.",
    "PURCHASE_ERROR": "There was a problem saving your purchase. Please check your data and try again.",
    "HTTP_ERROR": "Unexpected system error occurred. Please try again later.",
    "REQUEST_FAILED": "There was an issue sending your request. Please try again.",
    "UNEXPECTED_ERROR": "An unexpected error occurred. Please try again or contact support.",
    "UPDATE_ITEM_ERROR": "There was a problem with your update item submission. Please try again.",
    "CREATE_ITEM_ERROR": "There was a problem with your create item submission. Please try again.",
    "MAX_RETRIES_EXCEEDED": "The request failed after multiple attempts. Please try again later.",
    "UNKNOWN_TASK_TYPE": "The requested task type is not recognized. Please contact support or check your request.",

    "000001": "It is succeeded. There is no search result.",
    "801": "There is no data to retransmit.",
    "802": "There is data that has not been transferred. After transfer is possible.",
    "803": "This is a report that transfer is complete.",
    "804": "There is no data to send for the report.",
    "805": "Corresponding retransmission data exists.",
    "834": "SalesType and ReceiptType must be NS-NR-ND-TS-TR-TD-CS-CR-CD-PS. Check your inputs. Your sequences have been altered, connect to ZRA API to get sequences.",
    "838": "Connection to API is not established: check connection.",
    "884": "Invalid customer TPIN was provided.",
    "891": "An error occurred while Request URL is created.",
    "892": "An error occurred while Request Header data is created.",
    "893": "An error occurred while Request Body data is created.",
    "894": "An error regarding server communication occurred.",
    "895": "An error regarding unallowed Request Method occurred.",
    "896": "An error regarding Request Status occurred.",
    "899900": "An error regarding Client occurred. There is no Header information.",
    "901": "It is not valid device.",
    "902": "This device is installed.",
    "903": "Only VSDC device can be verified.",
    "910": "Request parameter error.",
    "911": "There is no request full text.",
    "912": "There is a request Method error.",
    "913": "Code value error among request parameters.",
    "131921": "Sales or sales invoice data which is declared cannot be received.",
    "922": "Sales invoice data can be received after receiving the sales data.",
    "924": "CIS Invoice number already exists.",
    "930": "The specified invoice could not be found. Please verify [orgInvcNo] and try again.",
    "931": "The credit note amount exceeds the original invoice amount for item.",
    "932": "The item specified in the credit note does not exist on the original invoice. [itemCd]",
    "934": "The quantity specified in the credit note exceeds the quantity in the original invoice.",
    "935": "The credit note contains information that does not match the original invoice data.",
    "990": "The maximum number of views are exceeded.",
    "991": "There is an error during registration.",
    "992": "There is an error during modification.",
    "993": "There is an error during deletion.",
    "994": "There is an overlapped data.",
    "995": "There is no downloaded file.",
    "999": "There is an unknown error. Please ask the administrator.",
    "910": "Invalid Item Class Code",
    '001': "There is no search result",
}


class RequestException(Exception):
    """Custom exception for handling API errors with friendly messages."""

    def __init__(self, code):
        self.code = code
        self.message = ERRORS.get(code, "An unknown error occurred.")
        super().__init__(self.message)

    def throw(self):
        full_message = f"{self.message}"
        frappe.throw(full_message)
