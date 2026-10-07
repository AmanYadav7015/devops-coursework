import json
import time
import urllib.request

NOW = time.time_ns()
TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
ROOT, INV, PAY = "00f067aa0ba902b7", "1a2b3c4d5e6f7081", "9f8e7d6c5b4a3920"
ENDPOINT = "http://localhost:4318/v1/traces"


def span(name, sid, parent, start_off_ms, dur_ms, attrs, err=False):
    out = {
        "traceId": TRACE,
        "spanId": sid,
        "name": name,
        "kind": 2,
        "startTimeUnixNano": str(NOW + start_off_ms * 1_000_000),
        "endTimeUnixNano": str(NOW + (start_off_ms + dur_ms) * 1_000_000),
        "attributes": [
            {"key": k, "value": {"stringValue": v} if isinstance(v, str) else {"intValue": str(v)}}
            for k, v in attrs.items()
        ],
        "status": {"code": 2, "message": "payment gateway timeout"} if err else {"code": 1},
    }
    if parent:
        out["parentSpanId"] = parent
    return out


def resource(service, spans):
    return {
        "resource": {
            "attributes": [
                {"key": "service.name", "value": {"stringValue": service}},
                {"key": "deployment.environment", "value": {"stringValue": "hw20"}},
            ]
        },
        "scopeSpans": [{"scope": {"name": "hw20.demo"}, "spans": spans}],
    }


payload = {
    "resourceSpans": [
        resource(
            "checkout-api",
            [
                span("POST /checkout", ROOT, None, 0, 3400,
                     {"http.method": "POST", "http.route": "/checkout", "http.status_code": 500, "order.id": 1007},
                     err=True),
                span("inventory.lookup", INV, ROOT, 20, 820,
                     {"db.system": "postgresql", "db.statement": "SELECT stock FROM items WHERE sku=$1"}),
            ],
        ),
        resource(
            "payment-gateway",
            [
                span("charge.card", PAY, ROOT, 900, 3200,
                     {"peer.service": "stripe-sandbox", "http.status_code": 504, "retry.count": 2},
                     err=True),
            ],
        ),
    ]
}

req = urllib.request.Request(
    ENDPOINT,
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=10) as resp:
    print("otlp status:", resp.status)
print("trace id:", TRACE)
