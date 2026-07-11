import requests

def get_vehicle_token(reg_no):
    url = "https://www.royalsundaram.in/car-insurance/proxy/apiproxy/eappspolicyservices/getTokenForVehicleDetails"

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "registrationno": reg_no,
        "origin": "https://www.royalsundaram.in",
        "referer": "https://www.royalsundaram.in/car-insurance/",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "x-datadog-origin": "rum",
        "x-datadog-sampling-priority": "1",
        "traceparent": "00-00000000000000003cfa05d2f8541d44-08676fe52f6b26dc-01",
    }

    # remove cookies fully (they break mobile requests)
    response = requests.post(url, headers=headers, json={})

    try:
        return response.json()
    except:
        return {"raw": response.text, "error": "NON_JSON_RESPONSE"}


def fetch_vehicle_details(token, reg_no):
    url = "https://www.royalsundaram.in/car-insurance/proxy/apiproxy/eappspolicyservices/getVehicleDetails"

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "origin": "https://www.royalsundaram.in",
        "referer": "https://www.royalsundaram.in/car-insurance/",
        "registrationno": reg_no,
        "token": token
    }

    data = {
        "registrationNo": reg_no,
        "token": token
    }

    response = requests.post(url, headers=headers, json=data)

    try:
        return response.json()
    except:
        return {"raw": response.text, "error": "NON_JSON_RESPONSE"}


if __name__ == "__main__":
    reg = input("Enter Registration No: ")

    print("\nGetting Token...\n")
    token_data = get_vehicle_token(reg)
    print("Token API Response:", token_data)

    if "token" not in token_data:
        print("\n❌ Token missing! API error.")
        exit()

    token = token_data["token"]

    print("\nFetching Vehicle Details...\n")
    details = fetch_vehicle_details(token, reg)
    print(details)
