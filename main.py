from prometheus_client import start_http_server, Histogram, Gauge, Info
import time
import requests
import config
import json

# Metrics to be tracked
REQUEST_TIME = Histogram('request_getStatus_seconds', 'Time spent processing getStatus request')
EPOCH = Gauge('parameter_epochNumber', 'Current epoch number')
TX_POOL = Gauge('parameter_pendingTx', 'Number of pending transactions in the pool')
INFO = Info('node_info', 'Node information')

#request parameters
headers = {'Content-Type': 'application/json'}

#get node status
@REQUEST_TIME.time()
def getStatus():
    data = {'jsonrpc':'2.0','method':'cfx_getStatus','id': "1"}
    r = requests.post(config.ENDPOINT, data =json.dumps(data), headers= headers)
    return r.json()["result"]

#get node client version
def getClientVersion():
    data = {'jsonrpc':'2.0','method':'cfx_clientVersion','id': "1"}
    r = requests.post(config.ENDPOINT, data =json.dumps(data), headers= headers)
    return r.json()["result"]

if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(config.PORT)
    print("Prometheus Metrics started at port "+str(config.PORT))

    # Metrics loop
    while True:
        data = getStatus()
        version = getClientVersion()

        # Set parameters
        EPOCH.set(int(data["epochNumber"], 0))
        TX_POOL.set(int(data["pendingTxNumber"], 0))
        INFO.info({'version': "test", 'chainId': str(int(data["chainId"], 0))})

        time.sleep(config.CYCLE)
