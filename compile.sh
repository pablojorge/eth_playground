#!/usr/bin/env bash

set -e

function compile() {
	solcjs $1 --bin
	echo 0x`cat ${1//.sol/}_sol_${1//.sol/.bin}`
}

compile $1