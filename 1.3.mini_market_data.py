

import redis
import json
import time
import random
import threading

r = redis.Redis(host = 'localhost', port = 6379, decode_responses = True)

SYMBOLS = ['AAPL','GOOGL','TSLA',"MSFT"] # Naming: constants are all CAP

def simulate_exchange_feed():
    while True: #to create an infinite loop keep getting data from market
        for symbol in SYMBOLS:
            quote = {
                'ticker': symbol,
                'bid': round(random.uniform(100,500),2),
                'ask': round(random.uniform(100,500),2),
                'timestamp': time.time()
            }
            r.setex(f'quote:{symbol}', 1, json.dumps(quote)) #redis.SetWithExpiration(); for when new user login into the app, initial look
            r.publish(f'quote:{symbol}', json.dumps(quote)) #for constant price update jumps
        time.sleep(0.1) #100ms matches to the frequency real exchange sends out; put at the bottom instead of top so you dont break 100s before starting
    
#REST data pull: stateless request, when API first search to see the ticker quote    
def get_quote(symbol: str) -> dict: #-> = type hint for human readability
    data = r.get(f'quote:{symbol}')
    if data:
        return json.loads(data)
    return {'error': 'quote not found'}

#WebSockets: user keep seeing update
def subscribe_quotes(symbol: list): #same here, this is just a defined method, tho naming is symbol has nothing to do with the actual content in SYMBOL
    pubsub = r.pubsub() #its like initiating the call, r.pubsub needs to keep running to complete the following related steps
    for s in symbol:
        pubsub.subscribe(f'quote:{s}') #Stateless vs.stateful tool
    print(f'subscribe to {symbol}')
    for message in pubsub.listen(): #generate a value, and wait to yield another later
        if message['type'] == 'message': #redis sends diff kind of "envelop", theres "welcome", "data" etc, with data envelop it carries text 'message'
            quote = json.loads(message['data'])
            latency_ms = (time.time() - quote['timestamp']) * 1000
            print(f"{quote['ticker']}:{quote['bid']}/{quote['ask']} (latency: {latency_ms:.1f}ms)")


if __name__ == '__main__':
    publisher = threading.Thread(target = simulate_exchange_feed, daemon = True)
    publisher.start()
    time.sleep(0.5)
    print('--- REST Qeury ---')
    print(get_quote('AAPL'))
    print('\n --- Real-time Subscription --- (Press Ctrl+C to stop)')
    subscribe_quotes(['AAPL','TSLA'])

