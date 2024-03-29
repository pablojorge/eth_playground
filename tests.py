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

# See https://eth.wiki/json-rpc/API
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
            print("<<", dumps(res))
        return res

    def _call(self, method, params):
        return self.__call(method, params)

    def eth_accounts(self):
        return self.__call("eth_accounts", [])

    def personal_sendTransaction(self, from_, to_, value_, nonce, gas, gasPrice, data):
        req = {
            "from": from_,
            "to": to_,
            "value": hex(value_),
            "nonce": hex(nonce),
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

    def eth_blockNumber(self):
        return self.__call("eth_blockNumber", [])

    def eth_getTransactionCount(self, address, block="pending"):
        return self.__call("eth_getTransactionCount", [address, block])

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
        raise NotImplemented()

class OpenEthereumClient(Client):
    desc = "OpenEth"

    @classmethod
    def normalize(cls, trace):
        return {
          "type": trace["action"]["callType"] if trace["type"] == "call" else trace["type"],
          "from": trace["action"]["from"],
          "to": trace["action"]["to"],
          "value": trace["action"]["value"],
          "gas": trace["action"]["gas"],
          "gasUsed": trace.get("result", {}).get("gasUsed"),
          "input": trace["action"]["input"],
          "output": trace.get("result", {}).get("output"),
          "error": trace.get("error")
        }

    # https://openethereum.github.io/JSONRPC-trace-module
    def trace_transaction(self, txhash):
        traces = self._call("trace_transaction", [txhash])
        return list(map(self.normalize, traces))


class GethClient(Client):
    desc = "Geth"

    @classmethod
    def flatten(cls, trace):
        parent = {
          "type": trace["type"].lower(),
          "from": trace["from"],
          "to": trace["to"],
          "value": trace.get("value", "0x0"), # Not present on delegate calls
          "gas": trace["gas"],
          "gasUsed": trace["gasUsed"],
          "input": trace["input"],
          "output": trace.get("output"),
          "error": trace.get("error")
        }
        return [parent] + sum(list(map(cls.flatten, trace.get('calls',[]))), [])

    # https://geth.ethereum.org/docs/dapp/tracing
    # https://geth.ethereum.org/docs/rpc/ns-debug#debug_tracetransaction
    def trace_transaction(self, txhash):
        trace = self._call("debug_traceTransaction", [txhash, {"tracer": "callTracer"}])
        return self.flatten(trace)


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

def wait_condition(action, condition, max_retries, on_retry=lambda: time.sleep(1)):
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
                on_retry()

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
    nonce = int(client.eth_getTransactionCount(sender), 16)
    txhash = client.personal_sendTransaction(sender, None, 0, nonce, 1000000, 10**9, code)
    wait_confirmation(client, txhash)
    receipt = wait_receipt(client, txhash)
    if receipt["status"] != "0x1":
        raise Exception("Deployment failed")
    return receipt["contractAddress"]

def contract_send_tx(client, sender, contractAddress, data):
    nonce = int(client.eth_getTransactionCount(sender), 16)
    txhash = client.personal_sendTransaction(sender, contractAddress, 0, nonce, 4000000, 10**9, data)
    wait_confirmation(client, txhash)
    receipt = wait_receipt(client, txhash)
    if receipt["status"] != "0x1":
        raise Exception("Sending TX to contract failed")
    return receipt

def contract_call(client, contractAddress, data):
    return client.eth_call(contractAddress, data, "latest")

def erc20_balanceOf(client, token, address):
    data = "0x70a08231" + zeropad(remove_0x(address), 64)
    return contract_call(client, token, data)


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

def test_bad_balance_check(client):
    code = compile("src/UnsafeToken.sol")
    sender = client.eth_accounts()[0]
    contractAddress = deploy_contract(client, sender, code)

    # Call transfer() with a big amount, to make the check fail:
    receipt = contract_send_tx(client, sender, contractAddress, 
        "0xa9059cbb" 
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee"
          "0000000000000000000000000000000000000000000000000000000010000010")

    # Transaction seems to be OK:
    assert receipt["status"] == "0x1"

    # Capture and validate traces
    traces = client.trace_transaction(receipt["transactionHash"])
    assert len(traces) == 1, f"Unexpected number of traces {len(traces)}"

    assert traces[0]["type"] == "call"
    assert traces[0]["from"] == sender
    assert traces[0]["to"] == contractAddress
    assert traces[0]["value"] == "0x0"
    assert traces[0]["output"] == prepend_0x(zeropad("00", 64)) # Return value is false
    assert traces[0]["error"] is None

    # Fetch the token balance of the destination
    balance = contract_call(client, contractAddress, 
        "0x70a08231"
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee")

    # It should be still zero:
    assert balance == prepend_0x(zeropad('00', 64)), f"Balance is {balance}"

def test_impersonate(client):
    sender = client.eth_accounts()[0]

    token = compile("src/TestToken.sol")
    tokenAddress = deploy_contract(client, sender, token)

    impersonator = compile("src/Impersonator.sol")
    impAddress = deploy_contract(client, sender, impersonator)

    # Call setTarget():
    contract_send_tx(client, sender, impAddress, 
        "0x776d1a01" +
          zeropad(remove_0x(tokenAddress), 64))

    # Call transfer() to the impersonator, with a big value that would make
    # the check fail in the target contract:
    receipt = contract_send_tx(client, sender, impAddress, 
        "0xa9059cbb" 
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee"
          "0000000000000000000000000000000000000000000000000000000000100000")

    # Transaction seems to be OK:
    assert receipt["status"] == "0x1"

    logs = receipt["logs"]
    assert len(logs) == 1, f"Unexpected number of logs {len(logs)}"

    # Transfer(from=sender, to=victim, value=0x100000)
    # We have a log with the address of the impersonator, so filtering logs by address is safe:
    # (this address will always match in which 'context' -which storage- the code executed)
    assert len(logs[0]['topics']) == 3
    assert logs[0]['address'] == impAddress
    assert logs[0]['logIndex'] == "0x0"
    assert logs[0]['topics'][0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    assert logs[0]['topics'][1] == prepend_0x(zeropad(remove_0x(sender), 64))
    assert logs[0]['topics'][2] == prepend_0x(zeropad("aabbccddeeff112233445566778899aabbccddee", 64))
    assert logs[0]['data'] == prepend_0x(zeropad("100000", 64))

    # Capture and validate traces
    traces = client.trace_transaction(receipt["transactionHash"])
    assert len(traces) == 2, f"Unexpected number of traces {len(traces)}"

    # Original call to the impersonator:
    assert traces[0]["type"] == "call"
    assert traces[0]["from"] == sender
    assert traces[0]["to"] == impAddress
    assert traces[0]["value"] == "0x0"
    assert traces[0]["output"] == prepend_0x(zeropad("01", 64))
    assert traces[0]["error"] is None

    # If we treat delegate calls as normal calls, this will look like a successful call
    # to transfer X amount of the underlying token in the context of the target/victim contract
    assert traces[1]["type"] == "delegatecall"
    assert traces[1]["from"] == impAddress
    assert traces[1]["to"] == tokenAddress
    assert traces[1]["value"] == "0x0"
    assert traces[1]["output"] in (prepend_0x(zeropad("01", 64)), '0x') # Success
    assert traces[1]["error"] is None

    # Fetch the token balance of the destination
    balance = contract_call(client, impAddress, 
        "0x70a08231"
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee")

    # It should have the big value, because the target code modified the storage of
    # the impersonator
    assert balance == prepend_0x(zeropad('100000', 64)), f"Balance is {balance}"

def test_extra_log_data(client):
    token_code = compile("src/TestToken.sol")
    runner_code = compile("src/Runner.sol")
    sender = client.eth_accounts()[0]
    token_address = deploy_contract(client, sender, token_code)
    runner_address = deploy_contract(client, sender, runner_code)

    # Fund runner contract with some tokens
    contract_send_tx(client, sender, token_address, 
        "0xa9059cbb" +
          zeropad(remove_0x(runner_address), 64) +
          "0000000000000000000000000000000000000000000000000000000000002000")

    # Submit tx to send from runner to dummy address
    submit_receipt = contract_send_tx(client, sender, runner_address, 
        "0xc6427474" +
          zeropad(remove_0x(token_address), 64) +
          "0000000000000000000000000000000000000000000000000000000000000000"
          "0000000000000000000000000000000000000000000000000000000000000060"
            "0000000000000000000000000000000000000000000000000000000000000044"
            "a9059cbb"
            "000000000000000000000000aabbccddeeff112233445566778899aabbccddee"
            "0000000000000000000000000000000000000000000000000000000000000ead")

    # The data in the logs has 28 extra bytes:
    logs = submit_receipt['logs']
    assert len(logs) == 1, f"Unexpected number of logs {len(logs)}"

    data = remove_0x(logs[0]['data'])
    expected = (
        "0000000000000000000000000000000000000000000000000000000000000020"
        "0000000000000000000000000000000000000000000000000000000000000044"
            "a9059cbb"
            "000000000000000000000000aabbccddeeff112233445566778899aabbccddee"
            "0000000000000000000000000000000000000000000000000000000000000ead"
            "00000000000000000000000000000000000000000000000000000000" # Extra bytes
    )
    assert data == expected

    # Exec tx in runner:
    exec_receipt = contract_send_tx(client, sender, runner_address, "0x069549bc")

    # Capture and validate traces
    traces = client.trace_transaction(exec_receipt["transactionHash"])
    assert len(traces) == 2, f"Unexpected number of traces {len(traces)}"

    assert traces[0]["type"] == "call"
    assert traces[0]["from"] == sender
    assert traces[0]["to"] == runner_address
    assert traces[0]["value"] == "0x0"
    assert traces[0]["input"] == "0x069549bc"
    assert traces[0]["output"] == prepend_0x(zeropad("01", 64))
    assert traces[0]["error"] is None

    assert traces[1]["type"] == "call"
    assert traces[1]["from"] == runner_address
    assert traces[1]["to"] == token_address
    assert traces[1]["value"] == "0x0"
    assert traces[1]["input"] == "0xa9059cbb000000000000000000000000aabbccddeeff112233445566778899aabbccddee0000000000000000000000000000000000000000000000000000000000000ead"
    # assert traces[1]["output"] == prepend_0x(zeropad("01", 64)) # Geth returns "0x0"
    assert traces[1]["error"] is None

    # Check final address token balance:
    balance = contract_call(client, token_address, 
        "0x70a08231"
          "000000000000000000000000aabbccddeeff112233445566778899aabbccddee")

    assert balance == prepend_0x(zeropad('ead', 64)), f"Balance is {balance}"

def test_partial_revert(client):
    token_code = compile("src/TestToken.sol")
    runner_code = compile("src/Runner.sol")
    sender = client.eth_accounts()[0]
    token_address = deploy_contract(client, sender, token_code)
    runner_address = deploy_contract(client, sender, runner_code)

    # Fund runner contract with some tokens
    contract_send_tx(client, sender, token_address, 
        "0xa9059cbb" +
          zeropad(remove_0x(runner_address), 64) +
          "0000000000000000000000000000000000000000000000000000000000002000")

    # Submit valid tx to send some tokens:
    contract_send_tx(client, sender, runner_address, 
        "0xc6427474" +
          zeropad(remove_0x(token_address), 64) +
          "0000000000000000000000000000000000000000000000000000000000000000"
          "0000000000000000000000000000000000000000000000000000000000000060"
            "0000000000000000000000000000000000000000000000000000000000000044"
            "a9059cbb"
            "000000000000000000000000aabbccddeeff112233445566778899aabbccddee"
            "0000000000000000000000000000000000000000000000000000000000001000")

    # Submit invalid tx to send more tokens than available:
    contract_send_tx(client, sender, runner_address, 
        "0xc6427474" +
          zeropad(remove_0x(token_address), 64) +
          "0000000000000000000000000000000000000000000000000000000000000000"
          "0000000000000000000000000000000000000000000000000000000000000060"
            "0000000000000000000000000000000000000000000000000000000000000044"
            "a9059cbb"
            "000000000000000000000000aabbccddeeff112233445566778899aabbccddee"
            "0000000000000000000000000000000000000000000000000000000000004000")

    # Exec txs in runner:
    exec_receipt = contract_send_tx(client, sender, runner_address, "0x069549bc")

    # Capture and validate logs
    logs = exec_receipt['logs']
    assert len(logs) == 3, f"Unexpected number of logs {len(logs)}"

    # Transfer(from=runner, to=dummy, value=0x1000)
    assert len(logs[0]['topics']) == 3
    assert logs[0]['address'] == token_address
    assert logs[0]['logIndex'] == "0x0"
    assert logs[0]['topics'][0] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    assert logs[0]['topics'][1] == prepend_0x(zeropad(remove_0x(runner_address), 64))
    assert logs[0]['topics'][2] == prepend_0x(zeropad("aabbccddeeff112233445566778899aabbccddee", 64))
    assert logs[0]['data'] == prepend_0x(zeropad("1000", 64))

    # 1st Execution(destination=token_address, result=1)
    assert len(logs[1]['topics']) == 2
    assert logs[1]['address'] == runner_address
    assert logs[1]['logIndex'] == "0x1"
    assert logs[1]['topics'][0] == "0x3fe9a337a26945194ec5a3dbeefaf9fb06a2a9b91825681dc24772f1575124d4"
    assert logs[1]['topics'][1] == prepend_0x(zeropad(remove_0x(token_address), 64))
    assert logs[1]['data'] == prepend_0x(zeropad("01", 64))

    # 2nd Execution(destination=token_address, result=1)
    assert len(logs[2]['topics']) == 2
    assert logs[2]['address'] == runner_address
    assert logs[2]['logIndex'] == "0x2"
    assert logs[2]['topics'][0] == "0x3fe9a337a26945194ec5a3dbeefaf9fb06a2a9b91825681dc24772f1575124d4"
    assert logs[2]['topics'][1] == prepend_0x(zeropad(remove_0x(token_address), 64))
    assert logs[2]['data'] == prepend_0x(zeropad("00", 64))

    # Capture and validate traces
    traces = client.trace_transaction(exec_receipt["transactionHash"])
    assert len(traces) == 3, f"Unexpected number of traces {len(traces)}"

    assert traces[0]["type"] == "call"
    assert traces[0]["from"] == sender
    assert traces[0]["to"] == runner_address
    assert traces[0]["value"] == "0x0"
    assert traces[0]["input"] == "0x069549bc"
    assert traces[0]["output"] == prepend_0x(zeropad("00", 64)) # Failure (one tx failed)
    assert traces[0]["error"] is None

    assert traces[1]["type"] == "call"
    assert traces[1]["from"] == runner_address
    assert traces[1]["to"] == token_address
    assert traces[1]["value"] == "0x0"
    assert traces[1]["input"] == "0xa9059cbb000000000000000000000000aabbccddeeff112233445566778899aabbccddee0000000000000000000000000000000000000000000000000000000000001000"
    assert traces[1]["output"] in (prepend_0x(zeropad("01", 64)), '0x') # Success
    assert traces[1]["error"] is None

    assert traces[2]["type"] == "call"
    assert traces[2]["from"] == runner_address
    assert traces[2]["to"] == token_address
    assert traces[2]["value"] == "0x0"
    assert traces[2]["input"] == "0xa9059cbb000000000000000000000000aabbccddeeff112233445566778899aabbccddee0000000000000000000000000000000000000000000000000000000000004000"
    assert traces[2]["output"] is None # reverted
    assert traces[2]["error"] is not None # reverted

    # Check final address token balance:
    balance = erc20_balanceOf(client, token_address, runner_address)
    assert balance == prepend_0x(zeropad('1000', 64)), f"Balance is {balance}"

    balance = erc20_balanceOf(client, token_address, "aabbccddeeff112233445566778899aabbccddee")
    assert balance == prepend_0x(zeropad('1000', 64)), f"Balance is {balance}"

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

    openeth_client = OpenEthereumClient("localhost", "8545", args.verbose)
    geth_client = GethClient("localhost", "8546", args.verbose)

    run_tests([
        (test_extra_parameter, openeth_client),
        (test_extra_log_data, openeth_client),
        (test_extra_parameter, geth_client),
        (test_extra_log_data, geth_client),
        (test_partial_revert, openeth_client),
        (test_partial_revert, geth_client),
        (test_bad_balance_check, openeth_client),
        (test_bad_balance_check, geth_client),
        (test_impersonate, openeth_client),
        (test_impersonate, geth_client),
    ])

if __name__ == '__main__':
    main()

