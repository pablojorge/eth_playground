#!/usr/bin/env bash

set -x

docker build -t openethereum .
docker run -ti -p 8545:8545 openethereum
