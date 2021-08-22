import sys
import json
import time
import requests
import subprocess
import traceback

import argparse

## Client

class RPCRequest:
    def __init__(self, host, port, method, params):
        self.host = host
        self.port = port
        self.method = method
        self.params = params

    def get_data(self):
        return {
            "jsonrpc" : "2.0",
            "method" : self.method,
            "params" : self.params,
            "id": 1
        }

    def execute(self):
        resp = requests.post(
            "http://%s:%s" % (self.host, self.port),
            headers={"Content-Type": "application/json"},
            data=json.dumps(self.get_data()),
        )

        if resp.status_code != 200:
            raise Exception(resp.text)

        body = json.loads(resp.text)

        if body.get("error"):
            raise Exception(body['error'])

        if body["result"] is None:
            raise Exception("null result")

        return body["result"]

    def as_curl(self):
        return (f"curl -X POST " + 
                f"--data '{json.dumps(self.get_data())}' " +
                f"--header 'Content-Type: application/json' " +
                f"http://{self.host}:{self.port}")

class Client:
    def __init__(self, desc, host, port, verbose):
        self.desc = desc
        self.host = host
        self.port = port
        self.verbose = verbose

    def __call(self, method, params):
        req = RPCRequest(self.host, self.port, method, params)
        if self.verbose:
            print(">>", req.as_curl())
        res = req.execute()
        if self.verbose:
            print("<<", dumps(res))
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

    def eth_getTransactionByHash(self, txhash):
        return self.__call("eth_getTransactionByHash", [txhash])

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

## Utils

def dumps(obj):
    return json.dumps(obj, indent="  ")

def remove_0x(string_):
    if string_.startswith("0x"):
        return string_[2:]
    return string_

def prepend_0x(string_):
    if not string_.startswith("0x"):
        return "0x" + string_
    return string_

def zeropad(str_, size):
    return "0" * (size - len(str_)) + str_

def compile(filename):
    cmd = ["solc", filename, "--bin"]

    proc = subprocess.run(cmd, capture_output=True, encoding='utf8')

    if proc.returncode:
        sys.stderr.write(proc.stderr)
        proc.check_returncode()

    return prepend_0x([x for x in proc.stdout.split('\n') if x][-1])

def wait_condition(action, condition, max_retries):
    attempts = 0
    success = False

    while True:
        try:
            ret = action()
            if condition(ret):
                success = True
                return ret
        finally:
            if not success:
                attempts += 1
                if attempts == max_retries + 1:
                    raise Exception("Max number of retries reached")
                time.sleep(1)

def wait_confirmation(client, txhash):
    return wait_condition(
        lambda: client.eth_getTransactionByHash(txhash), 
        lambda tx: tx["blockHash"] is not None,
        10
    )

def wait_receipt(client, txhash):
    return wait_condition(
        lambda: client.eth_getTransactionReceipt(txhash), 
        lambda _: True,
        10
    )

def deploy_contract(client, sender, code):
    txhash = client.personal_sendTransaction(sender, None, 1000000, 10000, code)
    wait_confirmation(client, txhash)
    receipt = wait_receipt(client, txhash)
    if receipt["status"] != "0x1":
        raise Exception("Deployment failed")
    return receipt["contractAddress"]

def contract_send_tx(client, sender, contractAddress, data):
    txhash = client.personal_sendTransaction(sender, contractAddress, 4000000, 10000, data)
    wait_confirmation(client, txhash)
    receipt = wait_receipt(client, txhash)
    if receipt["status"] != "0x1":
        raise Exception("Sending TX to contract failed")
    return receipt

def contract_call(client, contractAddress, data):
    return client.eth_call(contractAddress, data, "latest")

## Tests

def test_extra_parameter(client):
    code = compile("src/TestToken.sol")
    sender = client.eth_accounts()[0]
    contractAddress = deploy_contract(client, sender, code)

    # Call transfer() including an extra parameter, with a different value:
    receipt = contract_send_tx(client, sender, contractAddress, 
        "0xa9059cbb" 
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee"
          "0000000000000000000000000000000000000000000000000000000000000010"
          "0000000000000000000000000000000000000000000000000000000000000021")

    # Fetch the token balance of the destination
    balance = contract_call(client, contractAddress, 
        "0x70a08231"
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee")

    # It should be the value sent in the extra param:
    assert balance == prepend_0x(zeropad('21', 64)), f"Balance is {balance}"

def test_extra_log_data(client):
    token_code = compile("src/TestToken.sol")
    proxy_code = compile("src/ProxyContract.sol")
    sender = client.eth_accounts()[0]
    token_address = deploy_contract(client, sender, token_code)
    proxy_address = deploy_contract(client, sender, proxy_code)

    # Fund proxy contract with some tokens
    contract_send_tx(client, sender, token_address, 
        "0xa9059cbb" +
          zeropad(remove_0x(proxy_address), 64) +
          "0000000000000000000000000000000000000000000000000000000000002000")

    # Submit tx to send from proxy to dummy address
    submit_receipt = contract_send_tx(client, sender, proxy_address, 
        "0xc6427474" +
          zeropad(remove_0x(token_address), 64) +
          "0000000000000000000000000000000000000000000000000000000000000000"
          "0000000000000000000000000000000000000000000000000000000000000060"
            "0000000000000000000000000000000000000000000000000000000000000044"
            "a9059cbb"
            "000000000000000000000000aabbccddeeff112233445566778899aabbccddee"
            "0000000000000000000000000000000000000000000000000000000000000ead")

    # Exec tx in proxy:
    exec_receipt = contract_send_tx(client, sender, proxy_address, "0x0eb288f1")

    # Check final address token balance:
    balance = contract_call(client, token_address, 
        "0x70a08231"
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee")

    assert balance == prepend_0x(zeropad('ead', 64)), f"Balance is {balance}"

def elapsed_since(start):
    return "%.2fs" % (time.time() - start)

def run_tests(tests):
    errors = []

    for test, client in tests:
        try:
            sys.stdout.write(f" - '{test.__name__}' ({client.desc})... ")
            sys.stdout.flush()
            start = time.time()
            test(client)
            sys.stdout.write(f"OK ({elapsed_since(start)})\n")
        except Exception as e:
            _, _, tb = sys.exc_info()
            errors.append((test, client, e, tb))
            sys.stdout.write(f"ERROR ({elapsed_since(start)})\n")

    for (test, client, exc, tb) in errors:
        print(f"\nError in '{test.__name__}' ({client.desc}): {exc}\n")
        traceback.print_tb(tb)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", default=False)
    args = parser.parse_args()

    openeth_client = Client("OpenEth", "localhost", "8545", args.verbose)
    geth_client = Client("Geth", "localhost", "8546", args.verbose)

    run_tests([
        (test_extra_parameter, openeth_client),
        (test_extra_log_data, openeth_client),
        (test_extra_parameter, geth_client),
        (test_extra_log_data, geth_client),
    ])

if __name__ == '__main__':
    main()

