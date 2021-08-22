#!/usr/bin/env bash

set -x

docker build -t openethereum nodes/openethereum
docker build -t geth nodes/geth
