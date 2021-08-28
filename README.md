# Ethereum Playground

## Requirements

 * Solidity v0.8.6+ (https://docs.soliditylang.org/en/v0.8.6/installing-solidity.html)
 * Python 3+ (https://www.python.org/downloads/)
 * Docker (https://docs.docker.com/get-docker/)

## Running

1. Start the nodes with `docker-compose up --build`:

```bash
$ docker-compose up
Building openethereum
[...]
Successfully tagged solidityfun_openethereum:latest
Building geth
[...]
Successfully tagged solidityfun_geth:latest
Starting solidityfun_openethereum_1 ... done
Starting solidityfun_geth_1         ... done
[...]
```

2. Execute the tests:

```bash
$ python3 tests.py
 - 'test_extra_parameter' (OpenEth)... OK (0.18s)
 - 'test_extra_log_data' (OpenEth)... OK (0.25s)
 - 'test_extra_parameter' (Geth)... OK (4.31s)
 - 'test_extra_log_data' (Geth)... OK (10.68s)
```

Run with the `--verbose` flag to see a dump of requests (as cURL) and responses:

```bash
$ python3 tests.py --verbose
 - 'test_extra_parameter' (OpenEth)... >> curl -X POST --data '{"jsonrpc": "2.0", "method": "eth_accounts", "params": [], "id": 1}' --header 'Content-Type: application/json' http://localhost:8545
<< [
  "0x00a329c0648769a73afac7f9381e08fb43dbea72"
]
>> curl -X POST --data '{"jsonrpc": "2.0", "method": "personal_sendTransaction", "params": [{"from": "0x00a329c0648769a73afac7f9381e08fb43dbea72", "to": null, "gas": "0xf4240", "gasPrice": "0x2710",
[...]
```


