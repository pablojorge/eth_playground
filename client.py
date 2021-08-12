import sys
import json
import requests
import subprocess
import tempfile
import glob

import argparse
from urllib.parse import urljoin

class RPCRequest:
    def __init__(self, host, port, method, params):
        self.host = host
        self.port = port
        self.data = {
            "jsonrpc" : "2.0",
            "method" : method,
            "params" : params,
            "id": 1
        }

    def execute(self):
        resp = requests.post(
            "http://%s:%s" % (self.host, self.port),
            headers={"Content-Type": "application/json"},
            data=json.dumps(self.data),
        )

        if resp.status_code != 200:
            raise Exception(resp.text)

        body = json.loads(resp.text)

        if body.get("error"):
            raise Exception(body['error'])

        return body["result"]

    def as_curl(self):
        return (f"curl -X POST " + 
                f"--data '{json.dumps(self.data)}' " +
                f"--header 'Content-Type: application/json' " +
                f"http://{self.host}:{self.port}")

class Client:
    def __init__(self, host, port, verbose):
        self.host = host
        self.port = port
        self.verbose = verbose

    def __call(self, method, params):
        req = RPCRequest(self.host, self.port, method, params)
        if self.verbose:
            print(">>", req.as_curl())
        res = req.execute()
        if self.verbose:
            print("<<", res)
        return res

    def eth_accounts(self):
        return self.__call("eth_accounts", [])

    def personal_sendTransaction(self, from_, to_, gas, gasPrice, data):
        req = {
            "from": from_,
            "to": to_,
            "gas": hex(gas),
            "gasPrice": hex(gasPrice),
            "data": data
        }
        return self.__call("personal_sendTransaction", [req, ""])

    def eth_call(self, to_, data, at_):
        req = {
            "to": to_,
            "data": data
        }
        return self.__call("eth_call", [req, at_])

    def eth_getTransactionReceipt(self, txhash):
        return self.__call("eth_getTransactionReceipt", [txhash])

    def eth_getLogs(self, address, fromBlock, toBlock, topics):
        req = {
            "address": address,
            "fromBlock": fromBlock,
            "toBlock": toBlock,
            "topics": topics
        }
        return self.__call("eth_getLogs", [req])

    def trace_transaction(self, txhash):
        return self.__call("trace_transaction", [txhash])

def dumps(obj):
    return json.dumps(obj, indent="  ")

def compile(filename):
    with tempfile.TemporaryDirectory() as tempdir:
        cmd = ["solcjs", filename, "--bin", "-o", tempdir]
        print(f"Running: '{' '.join(cmd)}'")
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode:
            sys.stderr.write(proc.stderr.decode('utf8'))
            proc.check_returncode()

        binary = glob.glob(f"{tempdir}/*.bin")[0]
        with open(binary) as output:
            return "0x" + output.read()

def deploy_contract(client, sender, code):
    txhash = client.personal_sendTransaction(sender, None, 1000000, 10000, code)
    receipt = client.eth_getTransactionReceipt(txhash)
    if receipt["status"] != "0x1":
        raise Exception("Deployment failed")
    return receipt["contractAddress"]

def contract_send_tx(client, sender, contractAddress, data):
    txhash = client.personal_sendTransaction(sender, contractAddress, 4000000, 10000, data)
    receipt = client.eth_getTransactionReceipt(txhash)
    if receipt["status"] != "0x1":
        raise Exception("Sending TX to contract failed")
    return receipt

def contract_call(client, contractAddress, data):
    return client.eth_call(contractAddress, data, "latest")

def test_token_transfer(client):
    code = compile("TestToken.sol")
    sender = client.eth_accounts()[0]
    contractAddress = deploy_contract(client, sender, code)
    receipt = contract_send_tx(client, sender, contractAddress, 
        "0xa9059cbb" + 
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee" +
          "0000000000000000000000000000000000000000000000000000000000000010" +
          "0000000000000000000000000000000000000000000000000000000000000021")
    balance = contract_call(client, contractAddress, 
        "0x70a08231" + 
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee")
    print("Balance:", balance)

    # print(dumps(receipt))
    # print(dumps(client.trace_transaction(receipt['transactionHash'])))
    # topics = ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef']
    # print(dumps(client.eth_getLogs(contractAddress, "earliest", "latest", topics)))

def test_proxy_contract(client):
    token_code = compile("TestToken.sol")
    proxy_code = compile("ProxyContract.sol")
    sender = client.eth_accounts()[0]
    token_address = deploy_contract(client, sender, token_code)
    proxy_address = deploy_contract(client, sender, proxy_code)
    submit_receipt = contract_send_tx(client, sender, proxy_address, 
        "0xc6427474" + 
          "0"*24 + token_address[2:] +
          "0000000000000000000000000000000000000000000000000000000000000000" + 
          "0000000000000000000000000000000000000000000000000000000000000060" + 
            "0000000000000000000000000000000000000000000000000000000000000044" + 
            "a9059cbb" + 
            "000000000000000000000000aabbccddeeff112233445566778899aabbccddee" +
            "0000000000000000000000000000000000000000000000000000000000000010" + 
            "00000000000000000000000000000000000000000000000000000000")
    print(dumps(submit_receipt))
    exec_receipt = contract_send_tx(client, sender, proxy_address, "0x0eb288f1")
    print(dumps(exec_receipt))
    print(dumps(client.trace_transaction(exec_receipt['transactionHash'])))
    balance = contract_call(client, token_address, 
        "0x70a08231" + 
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee")
    print("Balance:", balance)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("port", type=int)
    parser.add_argument("--verbose", action="store_true", default=False)
    args = parser.parse_args()

    client = Client(args.host, args.port, args.verbose)

    # test_token_transfer(client)
    test_proxy_contract(client)


if __name__ == '__main__':
    main()

