# webhook-lab-stripe

Herramienta de línea de comandos para practicar con webhooks de Stripe sin necesitar una cuenta ni claves de Stripe. **Es un proyecto de práctica**: implementa el esquema de firma `Stripe-Signature` (HMAC-SHA256) a mano para entender cómo funciona; no usa el SDK oficial ni se conecta a Stripe.

## Qué hace

Un solo archivo (`webhook_lab.py`), solo librería estándar de Python 3.10+:

- `sample`: genera un evento de ejemplo (`payment_intent.succeeded`, `charge.refunded`, etc.).
- `sign`: calcula el header `Stripe-Signature` (`t=...,v1=...`) para un payload.
- `verify`: valida payload + header (firma y tolerancia de 5 minutos, como Stripe).
- `serve`: receptor HTTP en `POST /webhook` que verifica la firma, guarda los eventos en un archivo JSONL y responde 200 a los reintentos duplicados sin guardarlos dos veces.
- `summary`: resume el log (eventos por tipo, cobrado, reembolsado y neto por moneda).

Los eventos son simplificados (solo `id`, `type`, `data.object.amount` y `currency`); no replican el payload completo de Stripe.

## Cómo correrlo

```bash
# demo completa (levanta el servidor, manda 4 requests y muestra el resumen)
./demo.sh

# tests
python3 -m unittest discover tests

# uso manual
python3 webhook_lab.py sample --amount 4200 --currency eur > evento.json
python3 webhook_lab.py sign evento.json --secret whsec_xxx
python3 webhook_lab.py serve --secret whsec_xxx --port 8080 --log events.jsonl
python3 webhook_lab.py summary --log events.jsonl
```

El receptor también acepta webhooks reales de Stripe si usás el `whsec_...` de tu endpoint (por ejemplo con `stripe listen --forward-to localhost:8080/webhook`), aunque no lo probé contra Stripe real.

## Salida de la demo

```
evt_1 payment_intent.succeeded -> {"message": "ok"} [HTTP 200]
evt_1 payment_intent.succeeded -> {"message": "duplicado ignorado"} [HTTP 200]
evt_2 charge.refunded -> {"message": "ok"} [HTTP 200]
evt_3 payment_intent.succeeded -> {"message": "firma no coincide"} [HTTP 400]
```

## Limitaciones

- Solo firma `v1`, sin soporte para rotación de secretos más allá de aceptar varias `v1` en el header.
- Los eventos se guardan en un archivo local, sin base de datos ni concurrencia pensada.
- Escucha solo en `127.0.0.1`.
