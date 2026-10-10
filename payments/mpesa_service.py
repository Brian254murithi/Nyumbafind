"""
Reusable Safaricom M-Pesa Daraja API service.

This module contains all Daraja HTTP communication so that
Django views stay thin. Credentials are read from settings
(environment variables) and never logged or returned to clients.

Environments:
  sandbox    -> https://sandbox.safaricom.co.ke
  production -> https://api.safaricom.co.ke

Official Daraja documentation:
  https://developer.safaricom.co.ke/docs
"""

import base64
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger("nyumbafind.payments")

# Daraja STK Push result codes we map to explicit statuses.
RESULT_CODE_SUCCESS = 0
RESULT_CODE_CANCELLED = 1032   # Request cancelled by user
RESULT_CODE_TIMEOUT = 1037     # No response from user (timeout)

HTTP_TIMEOUT_SECONDS = 15


class MpesaConfigurationError(Exception):
    """Daraja credentials are missing or incomplete."""


class MpesaApiError(Exception):
    """Daraja returned an error or was unreachable.

    ``sanitized_message`` is safe to display to users and never
    contains credentials or raw provider payloads.
    """

    def __init__(self, message, sanitized_message="Payment service temporarily unavailable. Please try again."):
        super().__init__(message)
        self.sanitized_message = sanitized_message


class MpesaService:
    """Thin wrapper around the Safaricom Daraja API."""

    def __init__(self):
        self.environment = (getattr(settings, "MPESA_ENVIRONMENT", "sandbox") or "sandbox").lower()
        self.consumer_key = getattr(settings, "MPESA_CONSUMER_KEY", "") or ""
        self.consumer_secret = getattr(settings, "MPESA_CONSUMER_SECRET", "") or ""
        self.shortcode = str(getattr(settings, "MPESA_SHORTCODE", "") or "")
        self.passkey = getattr(settings, "MPESA_PASSKEY", "") or ""
        self.callback_url = getattr(settings, "MPESA_CALLBACK_URL", "") or ""
        self.initiator = getattr(settings, "MPESA_INITIATOR", "") or ""
        self.security_credential = getattr(settings, "MPESA_SECURITY_CREDENTIAL", "") or ""

        if self.environment == "production":
            self.base_url = "https://api.safaricom.co.ke"
        else:
            self.base_url = "https://sandbox.safaricom.co.ke"

        self._token = None
        self._token_expiry = 0

    # ------------------------------------------------------------------
    # Configuration checks
    # ------------------------------------------------------------------
    def is_configured(self):
        """True when the credentials required for STK Push are present."""
        return bool(
            self.consumer_key
            and self.consumer_secret
            and self.shortcode
            and self.passkey
        )

    def _require_configured(self):
        if not self.is_configured():
            raise MpesaConfigurationError(
                "Daraja credentials are not configured "
                "(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET, "
                "MPESA_SHORTCODE, MPESA_PASSKEY)."
            )

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------
    def _request(self, method, path, payload=None, token=None):
        """Perform an authenticated request to Daraja.

        Returns (status_code, decoded_json). Raises MpesaApiError on
        network failure or non-2xx responses. Never logs credentials.
        """
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            url, data=data, headers=headers, method=method
        )

        try:
            with urllib.request.urlopen(
                request, timeout=HTTP_TIMEOUT_SECONDS
            ) as response:
                body = response.read().decode("utf-8")
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                body = exc.read().decode("utf-8")
            except Exception:  # noqa: BLE001 - best effort read
                body = ""
            logger.warning(
                "Daraja HTTP error %s for %s", status, path
            )
            raise MpesaApiError(
                f"Daraja returned HTTP {status} for {path}",
                "The payment service rejected the request. Please verify your details and try again.",
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("Daraja network error for %s: %s", path, type(exc).__name__)
            raise MpesaApiError(
                f"Daraja network error for {path}: {type(exc).__name__}",
                "Payment service is temporarily unreachable. Please try again in a few minutes.",
            )

        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:200]}

        return status, parsed

    # ------------------------------------------------------------------
    # OAuth access token
    # ------------------------------------------------------------------
    def get_access_token(self):
        """Retrieve and cache an OAuth access token (client credentials)."""
        self._require_configured()

        if self._token and time.time() < self._token_expiry:
            return self._token

        credentials = base64.b64encode(
            f"{self.consumer_key}:{self.consumer_secret}".encode("utf-8")
        ).decode("utf-8")

        request = urllib.request.Request(
            f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {credentials}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            logger.warning("Daraja token error: %s", type(exc).__name__)
            raise MpesaApiError(
                f"Daraja token request failed: {type(exc).__name__}",
                "Payment service is temporarily unreachable. Please try again in a few minutes.",
            )
        except json.JSONDecodeError:
            raise MpesaApiError(
                "Daraja returned an invalid token response",
                "Payment service returned an unexpected response. Please try again.",
            )

        token = payload.get("access_token")
        if not token:
            raise MpesaApiError(
                "Daraja did not return an access token",
                "Payment service is misconfigured. Please contact support.",
            )

        # Cache slightly less than the official 3600s lifetime.
        self._token = token
        self._token_expiry = time.time() + int(payload.get("expires_in", 3600)) - 60
        return token

    # ------------------------------------------------------------------
    # STK Push
    # ------------------------------------------------------------------
    def stk_push(self, amount, phone_number, account_reference, transaction_desc):
        """Initiate an M-Pesa STK Push (CustomerPayBillOnline).

        ``amount`` is in whole KSh. ``phone_number`` must already be
        normalized to the 254XXXXXXXXX format.

        Returns the parsed Daraja response. Raises MpesaApiError /
        MpesaConfigurationError.
        """
        self._require_configured()
        token = self.get_access_token()

        timestamp = time.strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{self.shortcode}{self.passkey}{timestamp}".encode("utf-8")
        ).decode("utf-8")

        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": self.shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference[:13] or "NyumbaFind",
            "TransactionDesc": transaction_desc[:13] or "Payment",
        }

        if not self.callback_url:
            # Daraja still accepts the request, but without a reachable
            # callback the payment can never be verified. Fail loudly.
            raise MpesaConfigurationError(
                "MPESA_CALLBACK_URL is not configured; payments cannot be verified."
            )

        status, data = self._request(
            "POST", "/mpesa/stkpush/v1/processrequest", payload, token
        )

        response_code = str(data.get("ResponseCode", ""))
        if status >= 400 or response_code not in ("0", ""):
            description = data.get("ResponseDescription", "Unknown Daraja error")
            raise MpesaApiError(
                f"STK push rejected: {response_code} {description}",
                "The payment was rejected by the mobile network. Please check your phone number and amount, then try again.",
            )

        return data

    # ------------------------------------------------------------------
    # Transaction status query (reconciliation support)
    # ------------------------------------------------------------------
    def query_transaction_status(self, checkout_request_id):
        """Query the status of an STK Push via the TransactionStatus API.

        Requires a registered Daraja initiator
        (MPESA_INITIATOR + MPESA_SECURITY_CREDENTIAL). Used for manual
        reconciliation only — never for automatic success marking.
        """
        self._require_configured()
        if not self.initiator or not self.security_credential:
            raise MpesaConfigurationError(
                "Daraja initiator credentials are not configured "
                "(MPESA_INITIATOR, MPESA_SECURITY_CREDENTIAL)."
            )

        token = self.get_access_token()
        payload = {
            "Initiator": self.initiator,
            "SecurityCredential": self.security_credential,
            "CommandID": "TransactionStatusQuery",
            "TransactionID": checkout_request_id,
            "PartyA": self.shortcode,
            "IdentifierType": "1",
            "ResultURL": self.callback_url,
            "QueueTimeOutURL": self.callback_url,
            "Remarks": "NyumbaFind reconciliation",
        }
        return self._request(
            "POST", "/mpesa/transactionstatus/v1/query", payload, token
        )

    # ------------------------------------------------------------------
    # Callback validation
    # ------------------------------------------------------------------
    @staticmethod
    def validate_callback(data):
        """Validate an incoming STK callback payload.

        Returns a normalized dict:
          {
            "checkout_request_id": str,
            "merchant_request_id": str,
            "result_code": int,
            "result_desc": str,
            "metadata": {name: value},
          }
        Raises ValueError when the structure is invalid.

        Note: Daraja callbacks do not include a signature that can be
        independently verified. We therefore correlate by the unique
        CheckoutRequestID, validate the payload structure and the
        expected amount server-side, and process callbacks
        idempotently. Production deployments should additionally
        restrict the callback endpoint to Safaricom's published IP
        ranges at the infrastructure level.
        """
        if not isinstance(data, dict):
            raise ValueError("Callback payload must be a JSON object.")

        body = data.get("Body")
        if not isinstance(body, dict):
            raise ValueError("Callback is missing the Body object.")

        callback = body.get("stkCallback")
        if not isinstance(callback, dict):
            raise ValueError("Callback is missing the stkCallback object.")

        checkout_request_id = callback.get("CheckoutRequestID")
        merchant_request_id = callback.get("MerchantRequestID")
        result_code = callback.get("ResultCode")
        result_desc = callback.get("ResultDesc", "")

        if not isinstance(checkout_request_id, str) or not checkout_request_id:
            raise ValueError("Callback is missing a valid CheckoutRequestID.")
        if not isinstance(merchant_request_id, str) or not merchant_request_id:
            raise ValueError("Callback is missing a valid MerchantRequestID.")
        if not isinstance(result_code, int) and not (
            isinstance(result_code, str) and result_code.isdigit()
        ):
            raise ValueError("Callback ResultCode must be an integer.")

        metadata = {}
        raw_metadata = callback.get("CallbackMetadata")
        if isinstance(raw_metadata, dict):
            for item in raw_metadata.get("Item", []):
                if isinstance(item, dict) and "Name" in item:
                    metadata[item["Name"]] = item.get("Value")

        return {
            "checkout_request_id": checkout_request_id,
            "merchant_request_id": merchant_request_id,
            "result_code": int(result_code),
            "result_desc": str(result_desc),
            "metadata": metadata,
        }

    @staticmethod
    def interpret_result(result_code, result_desc=""):
        """Map a Daraja result code to a transaction status."""
        if result_code == RESULT_CODE_SUCCESS:
            return PaymentResult.SUCCESS, ""
        if result_code == RESULT_CODE_CANCELLED:
            return PaymentResult.CANCELLED, "Payment cancelled on your phone."
        if result_code == RESULT_CODE_TIMEOUT:
            return PaymentResult.EXPIRED, "Payment timed out. Please try again."
        return (
            PaymentResult.FAILED,
            f"Payment failed: {result_desc or 'M-Pesa declined the transaction.'}",
        )


class PaymentResult:
    SUCCESS = "successful"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


def get_mpesa_service():
    """Return a configured MpesaService instance."""
    return MpesaService()
