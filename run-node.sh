#!/usr/bin/env bash

docker build -t parity .
docker run -ti -p 8545:8545 parity
