"""Payment watcher for the storefront.

Polls public RPCs for the store's EVM + Solana addresses. Logs balance
changes to store/payments.csv and alerts on inbound payments. Read-only —
signs nothing, sends nothing.
"""
from __future__ import annotations

import csv
import os
import sys
import time
import urllib.request

CSV_PATH = os.path.expanduser("~/autonomous-agent/sims/payments.csv")

EVM_ADDR = "0x2343406488D26387E467107076C6D6711502786A"
SOL_ADDR = "5KfuH2oCPHoSmW6dG9aiJwRw5LtWqyd3Gyn6jLWcNiUe"

USDC_ETH = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
USDT_ETH = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
BALANCE_SELECTOR = "0x70a08231000000000000000000000000" + EVM_ADDR[2:].lower()

EVM_RPCS = ["https://mainnet.gateway.tenderly.co", "https://rpc.flashbots.net"]
SOL_RPC = "https://api.mainnet-beta.solana.com"


def rpc_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=__import__("json").dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) store-watcher/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return __import__("json").loads(r.read().decode())


def evm_balances() -> dict:
    for rpc in EVM_RPCS:
        try:
            eth = int(
                rpc_json(rpc, {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance",
                               "params": [EVM_ADDR, "latest"]})["result"],
                16,
            ) / 1e18
            usdc = int(
                rpc_json(rpc, {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                               "params": [{"to": USDC_ETH, "data": BALANCE_SELECTOR}, "latest"]})["result"] or "0x0",
                16,
            ) / 1e6
            usdt = int(
                rpc_json(rpc, {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                               "params": [{"to": USDT_ETH, "data": BALANCE_SELECTOR}, "latest"]})["result"] or "0x0",
                16,
            ) / 1e6
            return {"eth": eth, "usdc": usdc, "usdt": usdt}
        except Exception:
            continue
    raise RuntimeError("all EVM RPCs failed")


def sol_balance() -> float:
    r = rpc_json(SOL_RPC, {"jsonrpc": "2.0", "id": 1, "method": "getBalance",
                           "params": [SOL_ADDR]})
    return r["result"]["value"] / 1e9


def main() -> int:
    prev = None
    header = "ts,eth,usdc,usdt,sol"
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w") as f:
            f.write(header + "\n")
    else:
        with open(CSV_PATH) as f:
            rows = list(csv.DictReader(f))
        if rows:
            prev = {k: float(v) for k, v in rows[-1].items() if k != "ts"}

    evm = evm_balances()
    sol = sol_balance()
    cur = {**evm, "sol": sol}
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(CSV_PATH, "a") as f:
        f.write(f"{ts},{evm['eth']},{evm['usdc']},{evm['usdt']},{sol}\n")

    if prev:
        for k, v in cur.items():
            if v > prev[k] + 1e-9:
                print(f"PAYMENT: {k} +{v - prev[k]:.6f} (now {v:.6f}) at {ts}")
    else:
        print(f"baseline: {cur}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
