from flask import Flask, request, jsonify
import base64
import json
import requests
import time
import re
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

app = Flask(__name__)

# Constants
KEY = b'ZNJU64rUm5kU2pM@XPePYdK2lXxjn4th'
IV = b'N8YQ0Psgs44hM$2y'
BLOCK_SIZE = 16

URL = "https://digital.cholainsurance.com/api/v1/masterdata/vcv_prepopup_and_class_validation"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin": "https://digital.cholainsurance.com",
    "referer": "https://digital.cholainsurance.com/pc/",
    "in-auth-token": "pOpQfZ0E0kWm3hX1fWvqN1bJkbhMVzLxJ0ZAhstewIjcIGRUpXZJk6goo4kSr0Oy20gY1oZ4Zlwz3xPp0lXwwPsMtCX96AVkKVCB88vBR612R307ZRCkphB7Rwk+iYGCxdx3dOQtGiLt",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

COOKIES = {
    "_ga": "GA1.1.1012350830.1754117438",
    "_fbp": "fb.1.1754117471790.825338324930276170"
}

def validate_vehicle(vehicle_no):
    vehicle_no = vehicle_no.upper().strip()
    if re.match(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{1,4}$', vehicle_no):
        return vehicle_no
    return None

def encrypt_payload(data):
    json_bytes = json.dumps(data).encode("utf-8")
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    encrypted_bytes = cipher.encrypt(pad(json_bytes, BLOCK_SIZE))
    return base64.b64encode(encrypted_bytes).decode("utf-8")

def extract_vehicle_info(raw_data):
    """Extract relevant vehicle information from response"""
    result = {
        "vehicle_number": None,
        "make": None,
        "model": None,
        "fuel_type": None,
        "registration_date": None,
        "owner_name": None,
        "engine_number": None,
        "chassis_number": None,
        "status": None
    }
    
    if isinstance(raw_data, dict):
        if "data" in raw_data:
            data = raw_data["data"]
            result["vehicle_number"] = data.get("vehicle_number")
            result["make"] = data.get("make_name") or data.get("make")
            result["model"] = data.get("model_name") or data.get("model")
            result["fuel_type"] = data.get("fuel_type")
            result["registration_date"] = data.get("registration_date")
            result["owner_name"] = data.get("owner_name")
            result["engine_number"] = data.get("engine_number")
            result["chassis_number"] = data.get("chassis_number")
            result["status"] = data.get("status")
        elif "vehicle" in raw_data:
            data = raw_data["vehicle"]
            result["vehicle_number"] = data.get("registration_number")
            result["make"] = data.get("make")
            result["model"] = data.get("model")
            result["fuel_type"] = data.get("fuel")
    
    return {k: v for k, v in result.items() if v}

@app.route("/api/vehicle/insurance", methods=["GET"])
def vehicle_lookup():
    vehicle_no = request.args.get("vehicle", "").strip()
    
    if not vehicle_no:
        return jsonify({
            "success": False,
            "error": "Missing 'vehicle' parameter",
            "usage": "/api/vehicle/insurance?vehicle=MH02AB1234"
        }), 400
    
    validated_vehicle = validate_vehicle(vehicle_no)
    if not validated_vehicle:
        return jsonify({
            "success": False,
            "error": "Invalid vehicle number format",
            "example": "MH02AB1234"
        }), 400
    
    start_time = time.time()
    
    try:
        payload = {
            "vehicle_number": validated_vehicle,
            "journey_channel": "D2C",
            "product_name": "Private Car",
            "signzySelPolicytype": "Comp",
            "client_ip": "152.58.130.46",
            "mobile_no": "9876543210",
            "utm_source": "Direct",
            "utm_medium": "Direct",
            "utm_campaign": "Direct",
            "utm_content": "Direct",
            "utm_term": "Direct"
        }
        
        enc_token = encrypt_payload(payload)
        
        response = requests.post(
            URL,
            headers=HEADERS,
            cookies=COOKIES,
            json={"enc_token": enc_token},
            timeout=15
        )
        
        response_time = round((time.time() - start_time) * 1000, 2)
        
        try:
            data = response.json()
        except:
            data = {"raw": response.text[:500]}
        
        if response.status_code == 200:
            vehicle_info = extract_vehicle_info(data)
            
            if vehicle_info:
                return jsonify({
                    "success": True,
                    "vehicle_number": validated_vehicle,
                    "data": vehicle_info,
                    "meta": {
                        "response_time_ms": response_time,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "Chola Insurance"
                    }
                }), 200
            else:
                return jsonify({
                    "success": True,
                    "vehicle_number": validated_vehicle,
                    "message": "Vehicle found but no additional details available",
                    "raw_response": data.get("message", "No details"),
                    "meta": {
                        "response_time_ms": response_time
                    }
                }), 200
        else:
            return jsonify({
                "success": False,
                "error": f"API returned status {response.status_code}",
                "message": data.get("message", response.text[:200]) if isinstance(data, dict) else response.text[:200],
                "meta": {
                    "response_time_ms": response_time
                }
            }), response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({
            "success": False,
            "error": "Request timeout"
        }), 504
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/vehicle/insurance/check", methods=["GET"])
def vehicle_check():
    """Simple check if vehicle exists in database"""
    vehicle_no = request.args.get("vehicle", "").strip()
    
    if not vehicle_no:
        return jsonify({"success": False, "error": "Missing vehicle number"}), 400
    
    validated_vehicle = validate_vehicle(vehicle_no)
    if not validated_vehicle:
        return jsonify({"success": False, "error": "Invalid format"}), 400
    
    start_time = time.time()
    
    try:
        payload = {
            "vehicle_number": validated_vehicle,
            "journey_channel": "D2C",
            "product_name": "Private Car",
            "signzySelPolicytype": "Comp",
            "client_ip": "152.58.130.46",
            "mobile_no": "9876543210",
            "utm_source": "Direct",
            "utm_medium": "Direct",
            "utm_campaign": "Direct",
            "utm_content": "Direct",
            "utm_term": "Direct"
        }
        
        enc_token = encrypt_payload(payload)
        
        response = requests.post(
            URL,
            headers=HEADERS,
            cookies=COOKIES,
            json={"enc_token": enc_token},
            timeout=15
        )
        
        response_time = round((time.time() - start_time) * 1000, 2)
        
        if response.status_code == 200:
            return jsonify({
                "success": True,
                "vehicle_number": validated_vehicle,
                "exists": True,
                "meta": {
                    "response_time_ms": response_time,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }), 200
        else:
            return jsonify({
                "success": False,
                "vehicle_number": validated_vehicle,
                "exists": False,
                "meta": {"response_time_ms": response_time}
            }), 404
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "Chola Insurance Vehicle API",
        "endpoints": {
            "/api/vehicle/insurance?vehicle=MH02AB1234": "Get vehicle insurance details",
            "/api/vehicle/insurance/check?vehicle=MH02AB1234": "Check if vehicle exists",
            "/api/health": "Health check"
        },
        "api_by": "@ftgamer2"
    })

if __name__ == "__main__":
    print("=" * 50)
    print("Chola Insurance Vehicle API by @ftgamer2")
    print("=" * 50)
    print("Test URL: http://localhost:5000/api/vehicle/insurance?vehicle=MH02AB1234")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)
