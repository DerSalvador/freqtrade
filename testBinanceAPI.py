
import requests
import hashlib
import hmac
import time

api_key = 'HrLllzlPhN2BAAChE7iQdewMvawTuEwLGkWPYU1ZqlnxJ1uN1IdUernLvk6rU5cF'
api_secret = 'HSeKgVJP2XpL7AJWENZ54p2QexsWZq25jT3i8ywHpSLA7zKijo8yoKvFFTweTIYF'

def generate_signature(query_string):
    return hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def get_account_info():
    timestamp = int(time.time() * 1000)
    query_string = f'timestamp={timestamp}'
    signature = generate_signature(query_string)
    print (timestamp)
    print (signature)
    url = f'https://api.binance.com/api/v3/account?{query_string}&signature={signature}'
    """ 
    response = requests.get(url, headers={'X-MBX-APIKEY': api_key})
    return response.json() 
    curl -X 'POST' \
  'https://api.binance.com/sapi/v1/asset/transfer?type=MAIN_C2C&asset=AERGO&amount=100&recvWindow=5000&timestamp=1701206427036&signature=ca7ba4ac7b6a95757ae953cc1632cf24cf128b0bdf5e6a266082543d86a4069b' \
  -H 'accept: application/json' \
  -H 'X-MBX-APIKEY: ZJ8HMz2H5G1HMqcZh5yIJmoCVcWrYZLp9ZUqMhhSlb6mdJnzjUkNrdN8rJ4Zw7ro' \
  -d ''
    """
    wallet =  f'https://api.binance.com/sapi/v1/asset/transfer?type=MAIN_C2C&asset=AERGO&amount=100&recvWindow=10000&timestamp={timestamp}&signature={signature}'
    response = requests.get(wallet, headers={'X-MBX-APIKEY': api_key})
    return response.json()

account_info = get_account_info()
print(account_info)

    
