#!/usr/bin/env python3
"""webhook-lab: firmar, verificar, recibir y resumir webhooks de Stripe (solo stdlib)."""
import argparse
import hashlib
import hmac
import json
import sys
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer

TOLERANCE = 300  # segundos, igual que el default de Stripe


def sign(payload: str, secret: str, timestamp: int | None = None) -> str:
    """Devuelve el valor del header Stripe-Signature: t=...,v1=..."""
    ts = int(time.time()) if timestamp is None else timestamp
    mac = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256)
    return f"t={ts},v1={mac.hexdigest()}"


def verify(payload: str, header: str, secret: str, tolerance: int = TOLERANCE, now: float | None = None) -> None:
    """Lanza ValueError si la firma es invalida o el timestamp esta fuera de tolerancia."""
    try:
        parts = [p.split("=", 1) for p in header.split(",")]
        ts = int(next(v for k, v in parts if k == "t"))
        sigs = [v for k, v in parts if k == "v1"]
    except (ValueError, StopIteration):
        raise ValueError("header Stripe-Signature mal formado")
    if not sigs:
        raise ValueError("falta firma v1")
    expected = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in sigs):
        raise ValueError("firma no coincide")
    if abs((time.time() if now is None else now) - ts) > tolerance:
        raise ValueError("timestamp fuera de tolerancia")


def sample_event(kind: str, amount: int, currency: str, event_id: str | None = None) -> dict:
    return {
        "id": event_id or f"evt_{int(time.time() * 1000)}",
        "object": "event",
        "type": kind,
        "data": {"object": {"amount": amount, "currency": currency}},
    }


def load_events(path: str) -> list[dict]:
    try:
        with open(path) as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def summarize(events: list[dict]) -> dict:
    """Cuenta eventos por tipo y suma montos (en unidades menores) por moneda."""
    by_type: dict[str, int] = defaultdict(int)
    paid: dict[str, int] = defaultdict(int)
    refunded: dict[str, int] = defaultdict(int)
    for e in events:
        by_type[e["type"]] += 1
        obj = e.get("data", {}).get("object", {})
        cur, amt = obj.get("currency", "?").upper(), obj.get("amount", 0)
        if e["type"] == "payment_intent.succeeded":
            paid[cur] += amt
        elif e["type"] == "charge.refunded":
            refunded[cur] += amt
    return {"events": len(events), "by_type": dict(by_type), "paid": dict(paid),
            "refunded": dict(refunded), "net": {c: paid[c] - refunded.get(c, 0) for c in paid}}


def make_handler(secret: str, log_path: str):
    seen = {e["id"] for e in load_events(log_path)}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/webhook":
                return self._reply(404, "not found")
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            try:
                verify(body, self.headers.get("Stripe-Signature", ""), secret)
                event = json.loads(body)
                event["id"], event["type"]
            except (ValueError, KeyError) as exc:
                return self._reply(400, str(exc))
            if event["id"] in seen:  # Stripe reintenta: responder 200 sin duplicar
                return self._reply(200, "duplicado ignorado")
            seen.add(event["id"])
            with open(log_path, "a") as f:
                f.write(json.dumps(event) + "\n")
            self._reply(200, "ok")

        def _reply(self, code, msg):
            data = json.dumps({"message": msg}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            sys.stderr.write("[webhook] " + fmt % args + "\n")

    return Handler


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sign", help="firma un payload JSON (archivo o '-' para stdin)")
    s.add_argument("file")
    s.add_argument("--secret", required=True)
    v = sub.add_parser("verify", help="verifica payload + header")
    v.add_argument("file")
    v.add_argument("--header", required=True)
    v.add_argument("--secret", required=True)
    e = sub.add_parser("sample", help="imprime un evento de ejemplo")
    e.add_argument("--type", default="payment_intent.succeeded")
    e.add_argument("--amount", type=int, default=2500)
    e.add_argument("--currency", default="usd")
    e.add_argument("--id")
    r = sub.add_parser("serve", help="receptor HTTP en POST /webhook")
    r.add_argument("--secret", required=True)
    r.add_argument("--port", type=int, default=8080)
    r.add_argument("--log", default="events.jsonl")
    m = sub.add_parser("summary", help="resume el log de eventos")
    m.add_argument("--log", default="events.jsonl")
    a = p.parse_args(argv)

    def read(f):
        return sys.stdin.read() if f == "-" else open(f).read()

    if a.cmd == "sample":
        print(json.dumps(sample_event(a.type, a.amount, a.currency, a.id)))
    elif a.cmd == "sign":
        print(sign(read(a.file), a.secret))
    elif a.cmd == "verify":
        try:
            verify(read(a.file), a.header, a.secret)
        except ValueError as exc:
            print(f"INVALIDO: {exc}")
            return 1
        print("VALIDO")
    elif a.cmd == "summary":
        print(json.dumps(summarize(load_events(a.log)), indent=2))
    elif a.cmd == "serve":
        print(f"Escuchando en http://127.0.0.1:{a.port}/webhook (log: {a.log})", flush=True)
        HTTPServer(("127.0.0.1", a.port), make_handler(a.secret, a.log)).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
