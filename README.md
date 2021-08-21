# Solidity playground

## Requirements

 * Solidity v0.8.6+ (https://docs.soliditylang.org/en/v0.8.6/installing-solidity.html)
 * Python 3+ (https://www.python.org/downloads/)
 * Docker (https://docs.docker.com/get-docker/)

## Running

1. Execute `run-node.sh`; it will build an OpenEthereum Docker image and run it, ready for connections on `localhost:8545`

```bash
$ bash run-node.sh
+ docker build -t openethereum .
[...]
Successfully tagged openethereum:latest
+ docker run -ti -p 8545:8545 openethereum
2021-08-16 09:44:11 UTC Starting OpenEthereum/v3.3.0-rc.4-stable/x86_64-linux-musl/rustc1.47.0
[...]
```

2. Execute the tests:

```bash
$ python3 tests.py localhost 8545
Running 'test_extra_parameter'... OK
Running 'test_extra_log_data'... OK
```

To see a dump of requests (in curl format), and results, run the script with the `--verbose` flag:

```bash
$ python3 tests.py localhost 8545 --verbose
Running 'test_extra_parameter'... >> curl -X POST --data '{"jsonrpc": "2.0", "method": "eth_accounts", "params": [], "id": 1}' --header 'Content-Type: application/json' http://localhost:8545
<< [
  "0x00a329c0648769a73afac7f9381e08fb43dbea72"
]
[...]
```


