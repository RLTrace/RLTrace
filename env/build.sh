#!/usr/bin/env bash
GOPATH=$PWD

mkdir -p ./bin/linux_amd64
gcc -o ./bin/linux_amd64/syz-executor $GOPATH/src/executor/executor.cc \
	-O2 -pthread -Wall -Werror -Wparentheses -Wunused-const-variable -Wframe-larger-than=8192 -m64 -static \
    -DGOOS_linux=1 -DGOARCH_amd64=1 \
	-DHOSTGOOS_linux=1

GOOS=linux GOARCH=amd64 go build "-ldflags=-s -w" -o ./bin/rl-manager rl-manager

GOOS=linux GOARCH=amd64 go build "-ldflags=-s -w" "-tags=syz_target syz_os_linux syz_arch_amd64 " -o ./bin/linux_amd64/syz-fuzzer rl-fuzzer
GOOS=linux GOARCH=amd64 go build "-ldflags=-s -w" "-tags=syz_target syz_os_linux syz_arch_amd64 " -o ./bin/linux_amd64/syz-execprog tools/execprog

