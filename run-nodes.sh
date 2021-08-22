#!/usr/bin/env bash

set -x

docker run -d -p 8545:8545 openethereum
docker run -d -p 8546:8545 geth
