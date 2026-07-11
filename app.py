from flask import Flask, request, jsonify
import requests
import time
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor
import json

app = Flask(name)

# Headers common to all requests - UPDATED WITH NEW TOKENS
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'sec-ch-ua-platform': '"Android"',
    'Authorization': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJleHAiOjE3NzM5MzAwNjcsInN1YiI6IjMxNDgzMzE0IiwidW5pcXVlX2lkIjoicEZjc1ZMck5YeElOeElpcWtLYUZQR3hmcFpFZUVzQ0ZRdGdiaFpSZlZVcHZXVVhYUEJvUkpkTEhMd1pLeFh6dyIsImh0dHBzOi8vcGFya3doZWVscy5jby5pbi8iOnsidXNlcl9pZCI6MzE0ODMzMTQsIm5hbWUiOiIgIiwiZW1haWwiOiIiLCJwaG9uZV9udW1iZXIiOiI5MzM2Nzc3NjgyIiwicm9sZSI6ImNsaWVudCIsImRldmljZV9pZCI6bnVsbCwidmVyc2lvbiI6NCwidGVzdF91c2VyIjpmYWxzZX19.yjCvjdVKklUgWaAA3hXVyF_wgxZO6GR5wGimH1y2GZ70pNbogPSk4RrVO5u3Py57NcKqbQGCM_WRJygmTFY2Kg',
    'app-name': 'Park+ PWA',
    'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
    'new-device-id': 'f90b15bcf402b5a2162173ff8301b03f',
    'package-name': 'web.pwa',
    'sec-ch-ua-mobile': '?1',
    'client-id': '8186c1be-660f-428c-93a7-6480c2d8af66',
    'client-secret': 'hjjh0uw8c3j7vw5jgba8',
    'device-id': 'f90b15bcf402b5a2162173ff8301b03f',
    'Content-Type': 'application/json;charset=UTF-8',
    'platform': 'web',
    'Origin': 'https://parkplus.io',
    'Sec-Fetch-Site': 'same-site',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'Referer': 'https://parkplus.io/',
    'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6',
    'Connection': 'keep-alive'
}

BASE_URL = 'https://fastag-issuance.parkplus.io/fastag-recharge'

# ============= SIMPLE CACHE =============
class SimpleCache:
    def init(self, ttl_seconds=300):
        self.cache = {}
        self.timestamps = {}
        self.ttl = ttl_seconds
        self.lock = Lock()
    
    def get(self, key):
        with self.lock:
            if key in self.cache:
                if time.time() - self.timestamps[key] < self.ttl:
                    return self.cache[key]
                else:
                    del self.cache[key]
                    del self.timestamps[key]
            return None
    
    def set(self, key, value):
        with self.lock:
            self.cache[key] = value
            self.timestamps[key] = time.time()

# Create caches
vehicle_cache = SimpleCache(ttl_seconds=300)  # 5 minutes

# Connection pooling - headers already updated above
session = requests.Session()
session.headers.update(COMMON_HEADERS)

# Thread pool
executor = ThreadPoolExecutor(max_workers=5)

# ============= VEHICLE DETAILS =============
def get_vehicle_details(vehicle_number):
    """Get vehicle details"""
    cache_key = f"vrn_{vehicle_number}"
    cached = vehicle_cache.get(cache_key)
    if cached:
        return cached
    
    url = f'{BASE_URL}/tag/v2/vrn-detail'
    payload = {
        'vehicle_number': vehicle_number,
        'source': 'recharge'
    }
    
    try:
        response = session.post(url, json=payload, timeout=10)
        data = response.json()
        
        if data.get('status') == 0 and data.get('data'):
            bank_detail = data['data'].get('bank_detail', {})
            biller_id = bank_detail.get('biller_id')
            is_chasis = data['data'].get('is_chasis', False)
            owner_name = data['data'].get('owner_name', '')
            fastag_status = data['data'].get('fastag_status', '')
            
            result = {
                'found': True,
                'biller_id': biller_id,
                'is_chasis': is_chasis,

'owner_name': owner_name,
                'fastag_status': fastag_status,
                'bank_name': bank_detail.get('bank_name', '')
            }
            
            vehicle_cache.set(cache_key, result)
            return result
        else:
            return {'found': False, 'message': 'Vehicle not found'}
            
    except Exception as e:
        return {'found': False, 'message': f'Error: {str(e)}'}

# ============= FIXED: BALANCE WITH AUTO POLLING =============
def get_balance_with_polling(vehicle_number, biller_id, is_chasis, max_attempts=5):
    """
    Automatically poll until balance is available
    Returns balance or pending status
    """
    url = f'{BASE_URL}/balance/v1.1/fetch'
    
    # Step 1: Initiate balance fetch
    payload = {
        'vehicle_number': vehicle_number,
        'biller_id': biller_id,
        'is_chasis': is_chasis
    }
    
    try:
        print(f"Initiating balance fetch for {vehicle_number}...")
        response = session.post(url, json=payload, timeout=10)
        data = response.json()
        
        if data.get('status') != 0:
            return {'success': False, 'message': 'Failed to initiate'}
        
        init_data = data.get('data', {})
        request_id = init_data.get('request_id')
        
        if not request_id:
            return {'success': False, 'message': 'No request_id received'}
        
        # Step 2: Poll for balance
        print(f"Polling for balance with request_id: {request_id}")
        
        for attempt in range(max_attempts):
            # Wait before polling (increasing wait time)
            wait_time = 2 if attempt == 0 else 3
            print(f"Attempt {attempt + 1}/{max_attempts} - waiting {wait_time}s...")
            time.sleep(wait_time)
            
            # Check balance with request_id
            payload_with_id = {
                'vehicle_number': vehicle_number,
                'biller_id': biller_id,
                'is_chasis': is_chasis,
                'request_id': request_id
            }
            
            response2 = session.post(url, json=payload_with_id, timeout=10)
            data2 = response2.json()
            
            if data2.get('status') == 0:
                result_data = data2.get('data', {})
                
                # Check if balance fetch is complete
                if not result_data.get('is_balance_fetch_pending', True):
                    # Try to extract balance from different locations
                    balance_info = result_data.get('balance_fetch_data', {})
                    bottom_info = result_data.get('bottom_list_info', {})
                    
                    # Check multiple places for balance
                    balance = (balance_info.get('balance') or 
                              bottom_info.get('balance_amount') or
                              result_data.get('balance_amount'))
                    
                    if balance:
                        return {
                            'success': True,
                            'balance': balance,
                            'balance_updated_at': (balance_info.get('balance_updated_at') or 
                                                 bottom_info.get('balance_updated_at')),
                            'request_id': request_id
                        }
                    
                    # If balance_fetch_data exists but no balance yet
                    if balance_info:
                        return {
                            'success': False,
                            'pending': True,
                            'request_id': request_id,
                            'message': 'Balance fetch still processing',
                            'partial_data': balance_info

}
                
                # If still pending, continue polling
                print(f"Still pending on attempt {attempt + 1}")
        
        # If we reach here, polling timed out
        return {
            'success': False,
            'pending': True,
            'request_id': request_id,
            'message': 'Balance fetch taking longer than expected. Use /fastag/status to check later.'
        }
        
    except Exception as e:
        print(f"Balance polling error: {str(e)}")
        return {'success': False, 'message': f'Error: {str(e)}'}

# ============= MAIN ENDPOINT - WITH AUTO POLLING =============
@app.route('/fastag', methods=['GET'])
def get_fastag():
    """
    Main endpoint - automatically polls for balance
    URL: http://127.0.0.1:5000/fastag?vnum=HR26EV0001
    """
    vehicle_number = request.args.get('vnum')
    
    if not vehicle_number:
        return jsonify({
            'status': 'error',
            'message': 'Vehicle number required',
            'data': None
        })
    
    start_time = time.time()
    
    # Get vehicle details
    vehicle_data = get_vehicle_details(vehicle_number)
    
    if not vehicle_data.get('found', False):
        return jsonify({
            'status': 'error',
            'message': vehicle_data.get('message', 'Vehicle not found'),
            'data': {'vehicle_number': vehicle_number}
        })
    
    # Prepare base response
    response_data = {
        'status': 'success',
        'message': 'Vehicle found',
        'data': {
            'vehicle_number': vehicle_number,
            'owner_name': vehicle_data.get('owner_name', ''),
            'bank_name': vehicle_data.get('bank_name', ''),
            'fastag_status': vehicle_data.get('fastag_status', ''),
            'biller_id': vehicle_data.get('biller_id')
        }
    }
    
    # Get balance with auto-polling
    biller_id = vehicle_data.get('biller_id')
    if biller_id:
        balance_result = get_balance_with_polling(
            vehicle_number, 
            biller_id, 
            vehicle_data.get('is_chasis', False),
            max_attempts=5  # Will try 5 times with increasing waits
        )
        
        if balance_result.get('success'):
            # Balance found!
            response_data['data']['balance'] = balance_result.get('balance')
            response_data['data']['balance_updated_at'] = balance_result.get('balance_updated_at')
            response_data['data']['balance_status'] = 'available'
            response_data['message'] = 'Balance fetched successfully'
        elif balance_result.get('pending'):
            # Still pending after polling
            response_data['data']['request_id'] = balance_result.get('request_id')
            response_data['data']['balance_status'] = 'pending'
            response_data['data']['message'] = balance_result.get('message', 'Balance fetch in progress')
            response_data['message'] = 'Balance pending - check status with request_id'
        else:
            # Failed
            response_data['data']['balance_status'] = 'unavailable'
            response_data['data']['message'] = balance_result.get('message', 'Could not fetch balance')
    
    # Add performance
    response_time = int((time.time() - start_time) * 1000)
    response_data['performance'] = {
        'response_time_ms': response_time
    }
    
    return jsonify(response_data)

# ============= STATUS CHECK ENDPOINT =============
@app.route('/fastag/status', methods=['GET'])
def check_status():
    """Check balance status with request_id"""
    vehicle_number = request.args.get('vnum')
    request_id = request.args.get('request_id')
    
    if not vehicle_number or not request_id:
        return jsonify({
            'status': 'error',

'message': 'Vehicle number and request_id required'
        })
    
    # Get vehicle details
    vehicle_data = get_vehicle_details(vehicle_number)
    
    if not vehicle_data.get('found', False):
        return jsonify({
            'status': 'error',
            'message': 'Vehicle not found',
            'data': {'vehicle_number': vehicle_number}
        })
    
    # Check balance
    url = f'{BASE_URL}/balance/v1.1/fetch'
    payload = {
        'vehicle_number': vehicle_number,
        'biller_id': vehicle_data.get('biller_id'),
        'is_chasis': vehicle_data.get('is_chasis', False),
        'request_id': request_id
    }
    
    try:
        response = session.post(url, json=payload, timeout=10)
        data = response.json()
        
        if data.get('status') == 0:
            result_data = data.get('data', {})
            
            # Try to extract balance
            balance_info = result_data.get('balance_fetch_data', {})
            bottom_info = result_data.get('bottom_list_info', {})
            
            balance = (balance_info.get('balance') or 
                      bottom_info.get('balance_amount'))
            
            if balance:
                return jsonify({
                    'status': 'success',
                    'message': 'Balance available',
                    'data': {
                        'vehicle_number': vehicle_number,
                        'balance': balance,
                        'balance_updated_at': (balance_info.get('balance_updated_at') or 
                                             bottom_info.get('balance_updated_at')),
                        'request_id': request_id
                    }
                })
            elif result_data.get('is_balance_fetch_pending'):
                return jsonify({
                    'status': 'pending',
                    'message': 'Balance fetch still in progress',
                    'data': {
                        'vehicle_number': vehicle_number,
                        'request_id': request_id,
                        'polling_interval': result_data.get('polling_interval', 5)
                    }
                })
        
        return jsonify({
            'status': 'error',
            'message': 'Failed to get balance',
            'data': {'request_id': request_id}
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}',
            'data': {'request_id': request_id}
        })

# ============= FORCE BALANCE ENDPOINT =============
@app.route('/fastag/force-balance', methods=['GET'])
def force_balance():
    """Force balance fetch with longer polling"""
    vehicle_number = request.args.get('vnum')
    
    if not vehicle_number:
        return jsonify({'error': 'Vehicle number required'})
    
    vehicle_data = get_vehicle_details(vehicle_number)
    
    if not vehicle_data.get('found'):
        return jsonify({'error': 'Vehicle not found'})
    
    # Try with more attempts
    result = get_balance_with_polling(
        vehicle_number,
        vehicle_data.get('biller_id'),
        vehicle_data.get('is_chasis', False),
        max_attempts=8  # More attempts
    )
    
    return jsonify(result)

# ============= HEALTH CHECK =============
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'message': 'FASTag API - Auto Polling Enabled',
        'cached_vehicles': len(vehicle_cache.cache)
    })

if name == 'main':
    print("="*60)
    print("✅ FASTag API - AUTO POLLING VERSION (NEW TOKENS UPDATED)")
    print("="*60)
    print("📍 Main URL: http://127.0.0.1:5000/fastag?vnum=HR26EV0001")
    print("📊 Status URL: http://127.0.0.1:5000/fastag/status?vnum=HR26EV0001&request_id=4fada53e-0bf8-11f1-aa86-e2eb61a2af93")

print("⚡ Force URL: http://127.0.0.1:5000/fastag/force-balance?vnum=HR26EV0001")
    print("="*60)
    print("🔄 Auto-polling: 5 attempts with increasing waits")
    print("="*60)
    
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True,
        threaded=True
    )
