from flask import Flask, jsonify

app = Flask(__name__) #universal starting line for web app server

payments = {
    'txn_01': {'status': 'completed','amount':150,'currency':'usd', "created_at": "2025-01-06T10:30:00Z"},
    'txn_02': {'status': 'pending','amount':2500,'currency':'usd', "created_at": "2025-01-06T11:00:00Z"},
    'txn_03': {'status': 'failed','amount':75,'currency':'usd', 'error_code': "insufficient_funds"},
}

@app.route("/v1/payments/<payment_id>", methods=["GET"]) #decorator # to web server, "GET" is an action

def get_payment(payment_id): #define theTask(code A1 typed into vending machine)
    if payment_id in payments: #if A1/B2.., (payments) has food exists 
        return jsonify({"id": payment_id, **payments[payment_id]}), 200
    return jsonify({"error": "payment_not_found", "message": f"No payment with id {payment_id}"}), 404 
        #same as else: return...

    #as things are added to payments, payment_id method just checks if what is queried exists in payments, if so, package it as json and send out 200

if __name__ == "__main__":
    app.run(port=5001)

