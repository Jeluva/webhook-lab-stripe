#!/usr/bin/env bash
# Demo de punta a punta: levanta el receptor, manda eventos firmados y resume.
set -u
cd "$(dirname "$0")"
SECRET=whsec_demo
LOG=demo-events.jsonl
PORT=8099
rm -f "$LOG"
python3 webhook_lab.py serve --secret "$SECRET" --port "$PORT" --log "$LOG" 2>/dev/null &
PID=$!
trap 'kill $PID 2>/dev/null; rm -f demo-payload.json' EXIT
sleep 1

send() { # id tipo monto secreto
  python3 webhook_lab.py sample --id "$1" --type "$2" --amount "$3" > demo-payload.json
  local hdr; hdr=$(python3 webhook_lab.py sign demo-payload.json --secret "$4")
  printf '%s %s -> ' "$1" "$2"
  curl -s -w ' [HTTP %{http_code}]\n' -X POST "http://127.0.0.1:$PORT/webhook" \
    -H "Stripe-Signature: $hdr" --data-binary @demo-payload.json
}

send evt_1 payment_intent.succeeded 2500 "$SECRET"
send evt_1 payment_intent.succeeded 2500 "$SECRET"   # reintento: duplicado
send evt_2 charge.refunded 500 "$SECRET"
send evt_3 payment_intent.succeeded 999 secreto_malo  # firma invalida
python3 webhook_lab.py summary --log "$LOG"
