import requests
import json
import time
from typing import Dict, List, Any, Optional

class ICAREClient:
    def __init__(self, base_url: str, client_id: str, username: str, password: str, 
                 grant_type: str = "client_credentials", scope: str = "*"):
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.username = username
        self.password = password
        self.grant_type = grant_type
        self.scope = scope
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
    
    def _make_request(self, endpoint: str, method: str = "GET", 
                     data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
        """Generic method to make API requests with authentication handling"""
    
        if self.token_expiry and time.time() > self.token_expiry:
            self.refresh_access_token()
        
        # Set up headers
        request_headers = {
            'Content-Type': 'application/json',
            **(headers or {})
        }
        
        # Add authorization header if we have a token
        if self.access_token and endpoint != "/auth/authenticate":
            request_headers['Authorization'] = f"Bearer {self.access_token}"
        
        # Add authentication headers for auth endpoint
        if endpoint == "/auth/authenticate":
            request_headers.update({
                'clientId': self.client_id,
                'grantType': self.grant_type,
                'scope': self.scope
            })
        
        # Make the request
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=request_headers, params=data)
            elif method.upper() == "POST":
                response = requests.post(url, headers=request_headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse and return JSON response
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            raise
    
    def authenticate(self) -> Dict:
        """Authenticate and get access token"""
        endpoint = "/central-authentication-integrations/auth/authenticate"
        
        auth_data = {
            "username": self.username,
            "password": self.password
        }
        
        result = self._make_request(endpoint, "POST", auth_data)
        
        if result.get("success"):
            self.access_token = result["data"]["accessToken"]
            self.refresh_token = result["data"]["refreshToken"]
            self.token_expiry = time.time() + result["data"]["expiresIn"]
            print("Authentication successful!")
        
        return result
    
    def refresh_access_token(self) -> Dict:
        """Refresh access token using refresh token"""
        if not self.refresh_token:
            raise ValueError("No refresh token available. Please authenticate first.")
        
        endpoint = "/central-authentication-integrations/auth/refreshToken"
        
        refresh_data = {
            "refreshToken": self.refresh_token
        }
        
        result = self._make_request(endpoint, "POST", refresh_data)
        
        if result.get("success"):
            self.access_token = result["data"]["accessToken"]
            self.refresh_token = result["data"]["refreshToken"]
            self.token_expiry = time.time() + result["data"]["expiresIn"]
            print("Token refreshed successfully!")
        
        return result
    
    def get_member_kyc(self, ssn: str) -> Dict:
        """Get member KYC details by SSN"""
        endpoint = f"/icare-thirdparty/memberKyc/{ssn}"
        return self._make_request(endpoint, "GET")
    
    def get_current_year_ceiling(self) -> Dict:
        """Get current year ceiling value"""
        endpoint = "/icare-thirdparty/cellingValue"
        return self._make_request(endpoint, "GET")
    
    def submit_bulk_returns(self, return_reference: str, request_callback_url: str, 
                           returns: List[Dict]) -> Dict:
        """Submit bulk returns"""
        endpoint = "/icare-thirdparty/bulkEmployerReturns"
        
        bulk_data = {
            "returnReference": return_reference,
            "requestCallBackUrl": request_callback_url,
            "returns": returns
        }
        
        return self._make_request(endpoint, "POST", bulk_data)
    
    def submit_single_return(self, return_data: Dict) -> Dict:
        """Submit single return"""
        endpoint = "/icare-thirdparty/employerReturn"
        return self._make_request(endpoint, "POST", return_data)
    
    def query_return_status(self, return_reference: str) -> Dict:
        """Query return status by reference"""
        endpoint = f"/icare-thirdparty/queryReturnStatus/{return_reference}"
        return self._make_request(endpoint, "GET")
    
    def generic_api_call(self, endpoint: str, method: str = "GET", 
                        data: Optional[Dict] = None) -> Dict:
        """Generic method to call any ICARE API endpoint"""
        return self._make_request(endpoint, method, data)