from prometheus_client import start_http_server, Histogram, Gauge, Info, Enum
import time
import requests
import config
import json
import subprocess
import sys


# Metrics to be tracked
REQUEST_TIME = Histogram('request_getStatus_seconds', 'Time spent processing getStatus request')
EPOCH = Gauge('parameter_epochNumber', 'Current epoch number')
TX_POOL = Gauge('parameter_pendingTx', 'Number of pending transactions in the pool')
INFO = Info('node_info', 'Node information')
R_BASE = Gauge('reward_base', "Average base block reward for epoch")
R_TOTAL = Gauge('reward_total', "Average total block reward for epoch")
R_TX = Gauge('reward_tx', "Average transaction fees for epoch")
NODE_SYNC = Enum('node_sync_state', 'Sync process of a local node',
        states=["CatchUpCheckpointPhase", "CatchUpRecoverBlockFromDbPhase",
        "CatchUpRecoverBlockHeaderFromDbPhase", "CatchUpSyncBlockHeaderPhase",
        "CatchUpSyncBlockPhase", "NormalSyncPhase", "SyncPhaseType",
        "SynchronizationPhaseManager", "SynchronizationPhaseTrait"])
TX_DEFE = Gauge('txpool_deferred', 'Local node transaction pool - deferred')
TX_READY = Gauge('txpool_ready', 'Local node transaction pool - ready')
TX_RECE = Gauge('txpool_received', 'Local node transaction pool - received')
TX_UNEX = Gauge('txpool_unexecuted', 'Local node transaction pool - unexecuted')

#request parameters
headers = {'Content-Type': 'application/json'}

# construct JSON RPC data
def pack(method, params=[]):
    data = {'jsonrpc':'2.0','id': "1"}
    data['method'] = method
    data['params'] = params
    return json.dumps(data)

# get direct JSON RPC method
def get(method, params=[]):
    r = requests.post(config.ENDPOINT, data =pack(method, params), headers= headers)
    return r.json()["result"]

# calculate block reward info (averaged)
def blockReward():
    r = get("cfx_getBlockRewardInfo", ["latest_confirmed"])

    sum = {"baseReward": 0, "totalReward": 0, "txFee": 0}

    # sum
    for obj in r:
        for key in sum.keys():
            sum[key] += int(obj[key], 0)

    # average
    for key in sum.keys():
        sum[key] = round(sum[key]/len(r))

    return sum

#get node status
@REQUEST_TIME.time()
def getStatus():
    return get('cfx_getStatus')

# check OS
def checkSystem():
    if sys.platform.startswith('linux'):
        return checkNode()
    else:
        print("System is not Linux, running metrics with only RPC calls")
        return False

# check functioning node
def checkNode():
    output = subprocess.check_output(['ls'])
    if "\\nconflux\\n" in str(output): #checking for conflux executable
        try: #check if the node is active
            output = subprocess.check_output(['./conflux', 'rpc', 'epoch'])
            print("Local Conflux node is active")
            return True
        except:
            print("Local Conflux node did not respond, running metrics with only RPC calls")
            return False
    else:
        print("No local Conflux node, running metrics with only RPC calls")
        return False

# get parameters from local node
def checkLocal(params):
    calls = ["./conflux", "rpc", "local"]
    calls.extend(params)
    return subprocess.check_output(calls)

if __name__ == '__main__':
    local = checkSystem() #check local configuration

    # Start up the server to expose the metrics.
    start_http_server(config.PORT)
    print("Prometheus Metrics started at port "+str(config.PORT))

    # Metrics loop
    while True:
        data = getStatus() #get node status (wrapped with REQUEST_TIME measurement)
        version = get('cfx_clientVersion') #get node client version
        rewards = blockReward()

        # Set parameters
        EPOCH.set(int(data["epochNumber"], 0))
        TX_POOL.set(int(data["pendingTxNumber"], 0))
        INFO.info({'version': "test", 'chainId': str(int(data["chainId"], 0))})
        R_BASE.set(rewards["baseReward"])
        R_TOTAL.set(rewards["totalReward"])
        R_TX.set(rewards["txFee"])

        if local is True:
            #get node synchronization
            sync = checkLocal(["sync-phase"])
            NODE_SYNC.state(sync.decode().strip().replace('"',"")) #removes /n and extra quotation marks

            #transaction pool summary
            txpool = checkLocal(["txpool", "status"])
            txpool = json.loads(txpool.decode().replace("\n","").replace(" ",""))
            TX_DEFE.set(txpool["deferred"])
            TX_READY.set(txpool["ready"])
            TX_RECE.set(txpool["received"])
            TX_UNEX.set(txpool["unexecuted"])


        time.sleep(config.CYCLE)
