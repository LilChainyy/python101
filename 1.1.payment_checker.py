
import requests
import logging
from datetime import datetime


#Audit logging

logging.basicConfig( #setting menu for where/how/what to store
    filename = 'payment_audit.log', #keyword argument, pre-fixed
    level = logging.INFO,
    format = '%(asctime)s, %(message)s'
)

BASE_URL = "http://localhost:5001/v1"


def check_payment_status(payment_id: str) -> dict: #-> = result in
    endpoint = f'{BASE_URL}/payments/{payment_id}' #once the function gets the input (payment_id), it create "endpoint"

    #when connection works, can proceed to look for ans
    try:
        response = requests.get(endpoint, timeout = 5)

        logging.info(f'query, payment_id = {payment_id} | status_code = {response.status_code}')

        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'payment_id': payment_id,
                'status': data['status'],
                'amount': data['amount'],
                'detail': data
            }
        elif response.status_code == 404:
            return {
                'success': False,
                'payment_id': payment_id,
                'error': 'not found'
            }
        else:
            return {
                'success': False,
                'payment_id': payment_id,
                'error': f'Unexpected: {response.status_code}'
            }

    #cant connect/system failure
    except requests.exceptions.Timeout:
        logging.error(f'timeout, payment_id = {payment_id}') #f' = formatting; just a sentence builder
        return {'success': False, 'error': 'Gateway timeout'}
    except requests.exceptions.RequestException as e:
        logging.error(f'error, payment_id = {payment_id},{str(e)}') #str(e) is a smart human-readable text extraction
        return {'success': False, 'error': str(e)} #we create a dict here, to standardize so PC can easily read and compare. Also dict creates label, simple () tuples dont
        # all error are RequestException, but Timtout is a specific one thats insightful: "server is slow, lets up the bandwidth"


if __name__ == '__main__':
    testUse_ids = ['txn_01','txn_02','txn_03','txn_99']
    for txn_id in testUse_ids:
        result = check_payment_status(txn_id)
        print(f'{txn_id}: {result['status'] if result['success'] else result['error']}')





