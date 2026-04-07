import requests
import uuid
import os

# =============================================
# ORANGE MONEY MADAGASCAR
# =============================================
ORANGE_API_URL = "https://api.orange.com/orange-money-webpay/mg/v1"
ORANGE_CLIENT_ID = os.environ.get("ORANGE_CLIENT_ID", "VOTRE_CLIENT_ID")
ORANGE_CLIENT_SECRET = os.environ.get("ORANGE_CLIENT_SECRET", "VOTRE_CLIENT_SECRET")
ORANGE_MERCHANT_KEY = os.environ.get("ORANGE_MERCHANT_KEY", "VOTRE_MERCHANT_KEY")

# =============================================
# MVOLA (TELMA)
# =============================================
MVOLA_API_URL = "https://devapi.mvola.mg"
MVOLA_CONSUMER_KEY = os.environ.get("MVOLA_CONSUMER_KEY", "VOTRE_CONSUMER_KEY")
MVOLA_CONSUMER_SECRET = os.environ.get("MVOLA_CONSUMER_SECRET", "VOTRE_CONSUMER_SECRET")
MVOLA_MERCHANT_NUMBER = os.environ.get("MVOLA_MERCHANT_NUMBER", "034XXXXXXX")


def get_orange_token():
    """Mahazo access token Orange Money"""
    try:
        resp = requests.post(
            "https://api.orange.com/oauth/v3/token",
            data={
                "grant_type": "client_credentials",
                "client_id": ORANGE_CLIENT_ID,
                "client_secret": ORANGE_CLIENT_SECRET,
            },
            timeout=10
        )
        return resp.json().get("access_token")
    except Exception as e:
        print(f"Orange token error: {e}")
        return None


def initiate_orange_money(phone, amount, order_id):
    """
    Manomboka payment Orange Money
    phone   : ex "0341234567"
    amount  : ariary
    order_id: ID ny commande
    """
    # ---- MODE SIMULATION (raha mbola tsy manana API key) ----
    if ORANGE_CLIENT_ID == "VOTRE_CLIENT_ID":
        print(f"[SIMULATION] Orange Money: {phone} → {amount} Ar (order #{order_id})")
        return {
            "success": True,
            "transaction_ref": f"OM-SIM-{uuid.uuid4().hex[:8].upper()}",
            "message": "Simulation mode"
        }

    # ---- MODE REEL ----
    token = get_orange_token()
    if not token:
        return {"success": False, "message": "Tsy afaka mahazo token"}
    try:
        resp = requests.post(
            f"{ORANGE_API_URL}/webpayment",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "merchant_key": ORANGE_MERCHANT_KEY,
                "currency": "Ar",
                "order_id": str(order_id),
                "amount": int(amount),
                "return_url": "https://votre-site.com/payment/callback",
                "cancel_url": "https://votre-site.com/payment/cancel",
                "notif_url": "https://votre-site.com/payment/notify",
                "lang": "fr",
                "reference": f"ORDER-{order_id}"
            },
            timeout=15
        )
        data = resp.json()
        if resp.status_code == 200:
            return {
                "success": True,
                "transaction_ref": data.get("pay_token"),
                "payment_url": data.get("payment_url")
            }
        return {"success": False, "message": data.get("message", "Nisy olana")}
    except Exception as e:
        return {"success": False, "message": str(e)}


def get_mvola_token():
    """Mahazo access token Mvola"""
    try:
        resp = requests.post(
            f"{MVOLA_API_URL}/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": MVOLA_CONSUMER_KEY,
                "client_secret": MVOLA_CONSUMER_SECRET,
                "scope": "EXT_INT_MVOLA_SCOPE"
            },
            timeout=10
        )
        return resp.json().get("access_token")
    except Exception as e:
        print(f"Mvola token error: {e}")
        return None


def initiate_mvola(phone, amount, order_id):
    """
    Manomboka payment Mvola
    phone   : ex "0341234567"
    amount  : ariary
    order_id: ID ny commande
    """
    # ---- MODE SIMULATION ----
    if MVOLA_CONSUMER_KEY == "VOTRE_CONSUMER_KEY":
        print(f"[SIMULATION] Mvola: {phone} → {amount} Ar (order #{order_id})")
        return {
            "success": True,
            "transaction_ref": f"MV-SIM-{uuid.uuid4().hex[:8].upper()}",
            "message": "Simulation mode"
        }

    # ---- MODE REEL ----
    token = get_mvola_token()
    if not token:
        return {"success": False, "message": "Tsy afaka mahazo token Mvola"}
    try:
        correlation_id = str(uuid.uuid4())
        resp = requests.post(
            f"{MVOLA_API_URL}/mvola/mm/transactions/type/merchantpay/1.0.0/",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Version": "1.0",
                "X-CorrelationID": correlation_id,
                "UserLanguage": "MG",
                "UserAccountIdentifier": f"msisdn;{phone}",
                "partnerName": "VotreOrinasa",
                "Cache-Control": "no-cache"
            },
            json={
                "amount": str(int(amount)),
                "currency": "Ar",
                "descriptionText": f"Achat logiciel #{order_id}",
                "requestingOrganisationTransactionReference": f"ORDER-{order_id}",
                "requestDate": "2024-01-01T00:00:00.000Z",
                "originalTransactionReference": correlation_id,
                "debitParty": [{"key": "msisdn", "value": phone}],
                "creditParty": [{"key": "msisdn", "value": MVOLA_MERCHANT_NUMBER}],
                "metadata": [{"key": "partnerName", "value": "VotreOrinasa"}]
            },
            timeout=15
        )
        data = resp.json()
        if resp.status_code in [200, 201, 202]:
            return {
                "success": True,
                "transaction_ref": data.get("serverCorrelationId", correlation_id)
            }
        return {"success": False, "message": data.get("errorDescription", "Nisy olana Mvola")}
    except Exception as e:
        return {"success": False, "message": str(e)}


def check_payment_status(transaction_ref, payment_method):
    """
    Manamarina ny status ny payment
    Miverina: 'completed', 'pending', na 'failed'
    """
    if not transaction_ref:
        return 'pending'

    # Simulation mode
    if transaction_ref.startswith("OM-SIM-") or transaction_ref.startswith("MV-SIM-"):
        return 'completed'  # Simulation: eken'ny payment foana

    try:
        if payment_method == 'orange_money':
            token = get_orange_token()
            if not token:
                return 'pending'
            resp = requests.get(
                f"{ORANGE_API_URL}/paymentstatus",
                headers={"Authorization": f"Bearer {token}"},
                params={"pay_token": transaction_ref},
                timeout=10
            )
            data = resp.json()
            status = data.get("status", "")
            if status == "SUCCESS":
                return 'completed'
            elif status in ["FAILED", "CANCELLED"]:
                return 'failed'

        elif payment_method == 'mvola':
            token = get_mvola_token()
            if not token:
                return 'pending'
            resp = requests.get(
                f"{MVOLA_API_URL}/mvola/mm/transactions/type/merchantpay/1.0.0/status/{transaction_ref}",
                headers={"Authorization": f"Bearer {token}", "Version": "1.0"},
                timeout=10
            )
            data = resp.json()
            status = data.get("status", "")
            if status == "completed":
                return 'completed'
            elif status in ["failed", "cancelled"]:
                return 'failed'

    except Exception as e:
        print(f"Check status error: {e}")

    return 'pending'
