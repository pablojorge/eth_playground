FROM openethereum/openethereum:v3.3.0-rc.4

CMD ["--chain", "dev", \
     "--jsonrpc-interface", "all", \
     "--jsonrpc-hosts", "all", \
     "--jsonrpc-apis", "all", \
     "--tracing", "on"]
