#!/usr/bin/env bash

set -e

solcjs TestToken.sol --bin

echo 0x`cat TestToken_sol_TestToken.bin`