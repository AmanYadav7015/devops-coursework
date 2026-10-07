# Session 20 — Monitoring, Observability & GitOps

Hands-on homework for session 20. Three tasks:

| Task | Topic | What is proved here |
|------|-------|---------------------|
| 1 | Monitoring | Prometheus + Alertmanager + Grafana running, real PromQL results, two alert rules driven from `inactive` to `pending` to `firing` and back, CPU/memory utilisation, application health gated by probes |
| 2 | Observability | The three pillars demonstrated with a real metric, a real log stream and a real distributed trace stored in Jaeger, correlated by one trace id |
| 3 | GitOps | Argo CD installed, an Application synced from a public Git repository, then live cluster state mutated by hand and automatically reverted to the Git-declared state |

Everything below was executed on the machine described in **Environment**. Every `text` block is
real captured output, pasted unedited apart from stripping terminal colour codes.

---

## Environment and isolation

| Item | Value |
|------|-------|
| Cluster | minikube v1.39.0, docker driver, Kubernetes v1.37.0, node `minikube` at 192.168.49.2 |
| Addons used | `metrics-server` (for `kubectl top`), `storage-provisioner` |
| Kubernetes namespace | `hw20` (plus `argocd` for the Argo CD control plane) |
| NodePort range used | 30200-30209 |
| Docker | all containers, the network and the volumes are prefixed `hw20-`, compose project `hw20` |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |
| Grafana | http://localhost:**13000** |
| Jaeger | http://localhost:16686 |

**Why Grafana is on 13000 and not 3000.** Port 3000 on this host was already taken by another
process, checked before starting anything:

```bash
lsof -nP -iTCP:3000 -sTCP:LISTEN
```

```text
COMMAND   PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
node    52905 aman   17u  IPv6 0x15e87607df41e408      0t0  TCP *:3000 (LISTEN)
```

So the Grafana container publishes `13000:3000` instead. Port 9090 was free and Prometheus uses it.

**A platform fact that shapes every command below.** The minikube node IP `192.168.49.2` is not
routable from macOS, because the docker driver runs the node inside the Docker Desktop VM. Anything
that has to reach a NodePort is therefore run with `minikube ssh -- curl ...` rather than from the
host shell.

---

## Repository layout

```text
20-monitoring-gitops/
├── README.md
├── monitoring/
│   ├── docker-compose.yml          Prometheus, Alertmanager, node-exporter, Grafana
│   ├── prometheus.yml              scrape config + alerting config + rule_files
│   ├── alert-rules.yml             four alerting rules
│   ├── alertmanager.yml            routing tree
│   └── grafana/
│       ├── provisioning/datasources/prometheus.yml
│       ├── provisioning/dashboards/dashboards.yml
│       └── dashboards/hw20-overview.json
├── observability/
│   ├── docker-compose.yml          Jaeger all-in-one with OTLP/HTTP enabled
│   └── send-trace.py               emits one real three-span trace over OTLP
├── k8s/
│   ├── 01-namespace.yaml
│   ├── 02-web-app.yaml             deployment + NodePort service + readiness/liveness probes
│   ├── 03-logger.yaml              structured JSON log producer
│   └── 04-cpu-load.yaml            busy-loop pod so `kubectl top` has something to show
├── gitops/
│   ├── application.yaml            Argo CD Application, selfHeal disabled
│   └── application-selfheal.yaml   same Application, selfHeal enabled
└── outputs/                        raw captured output from every step
```

---

## Architecture

```text
                        ┌──────────────────────── host: macOS ────────────────────────┐
                        │                                                             │
   docker compose -p hw20                                                             │
   ┌────────────────────┴──────────────────────────────┐                              │
   │  hw20-net (docker bridge)                         │                              │
   │                                                   │                              │
   │   ┌───────────────┐  scrape /metrics every 5s     │                              │
   │   │ hw20-         │◀──────┬───────────────────┐   │                              │
   │   │ prometheus    │       │                   │   │                              │
   │   │ :9090         │   ┌───┴────────┐   ┌──────┴──────────┐                       │
   │   │               │   │ hw20-node- │   │ hw20-grafana    │   ┌────────────────┐  │
   │   │  rule eval    │   │ exporter   │   │ :3000 -> :13000 │   │ hw20-jaeger    │  │
   │   │  every 5s     │   │ :9100      │   │                 │   │ :16686 UI/API  │  │
   │   └──────┬────────┘   └────────────┘   └────────┬────────┘   │ :4318 OTLP     │  │
   │          │ alerts                               │ queries    └───────▲────────┘  │
   │          ▼                                      │ datasource         │ OTLP/HTTP │
   │   ┌─────────────────┐                           │                    │           │
   │   │ hw20-alertmanager│◀─────────────────────────┘             send-trace.py      │
   │   │ :9093            │                                                           │
   │   └─────────────────┘                                                            │
   └──────────────────────────────────────────────────────────────────────────────────┘

                        ┌──────────── minikube node (inside the Docker Desktop VM) ────────────┐
                        │                                                                     │
                        │  namespace hw20                      namespace argocd               │
                        │  ┌───────────────────────────┐       ┌──────────────────────────┐   │
                        │  │ hw20-web  (2 replicas)    │       │ argocd-application-      │   │
                        │  │   readiness /healthz      │       │ controller (reconcile    │   │
                        │  │   liveness  /healthz      │       │ loop, every 3 min +      │   │
                        │  │   svc NodePort 30200      │       │ on change)               │   │
                        │  ├───────────────────────────┤       │ argocd-repo-server       │   │
                        │  │ hw20-logger (JSON logs)   │       │ argocd-server (API/UI)   │   │
                        │  ├───────────────────────────┤       │ argocd-redis, dex,       │   │
                        │  │ hw20-cpu-load (busy loop) │       │ applicationset, notif.   │   │
                        │  ├───────────────────────────┤       └────────────┬─────────────┘   │
                        │  │ guestbook-ui  ◀───────────┼── applies ─────────┘                 │
                        │  │   (owned by Argo CD)      │                    │                 │
                        │  └───────────────────────────┘                    │ git fetch       │
                        │        metrics-server ──▶ kubectl top             ▼                 │
                        └──────────────────────────────────────────┬────────────────────┘
                                                                   │
                                        github.com/argoproj/argocd-example-apps  (desired state)
```

Two independent planes: a Docker-based metrics/alerting/tracing plane for Tasks 1 and 2, and the
Kubernetes plane where Task 1's workload health, Task 2's logs and Task 3's GitOps reconciliation
all happen.

---

# Task 1 — Monitoring

> Learn and demonstrate: metrics, logs, alerts, CPU utilisation, memory utilisation, application health.

Monitoring answers **"is the thing I already know about behaving?"**. You decide in advance which
signals matter, you collect them on a schedule, you draw them, and you alert when they cross a line.
The whole of Task 1 is that loop, built end to end and then deliberately broken so the alerting half
can be seen working.

## 1.1 The stack

Four containers, one compose project, one network, everything prefixed `hw20-`:

```bash
cat monitoring/docker-compose.yml
```

```text
name: hw20

services:
  prometheus:
    image: prom/prometheus:v3.5.0
    container_name: hw20-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./alert-rules.yml:/etc/prometheus/alert-rules.yml:ro
      - hw20-prometheus-data:/prometheus
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --web.enable-lifecycle
    networks:
      - hw20-net

  alertmanager:
    image: prom/alertmanager:v0.28.1
    container_name: hw20-alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    networks:
      - hw20-net

  node-exporter:
    image: prom/node-exporter:v1.9.1
    container_name: hw20-node-exporter
    ports:
      - "9100:9100"
    pid: host
    networks:
      - hw20-net

  grafana:
    image: grafana/grafana:12.1.1
    container_name: hw20-grafana
    ports:
      - "13000:3000"
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
      - hw20-grafana-data:/var/lib/grafana
    depends_on:
      - prometheus
    networks:
      - hw20-net

volumes:
  hw20-prometheus-data:
    name: hw20-prometheus-data
  hw20-grafana-data:
    name: hw20-grafana-data

networks:
  hw20-net:
    name: hw20-net
```

| Component | Role |
|-----------|------|
| Prometheus | pull-based time-series database: scrapes `/metrics` endpoints, stores samples, evaluates alert rules |
| Alertmanager | receives fired alerts from Prometheus, groups, deduplicates and routes them to receivers |
| node-exporter | exposes host-level CPU, memory, disk and network counters as Prometheus metrics |
| Grafana | queries Prometheus and draws it; datasource and dashboard are provisioned from files, not clicked |

The scrape configuration:

```bash
cat monitoring/prometheus.yml
```

```text
global:
  scrape_interval: 5s
  evaluation_interval: 5s
  external_labels:
    env: hw20

rule_files:
  - /etc/prometheus/alert-rules.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets:
          - prometheus:9090

  - job_name: node-exporter
    static_configs:
      - targets:
          - node-exporter:9100

  - job_name: grafana
    metrics_path: /metrics
    static_configs:
      - targets:
          - grafana:3000

  - job_name: alertmanager
    static_configs:
      - targets:
          - alertmanager:9093
```

A 5 second `scrape_interval` and `evaluation_interval` are much tighter than production defaults
(15s-60s), chosen deliberately so that a `for: 15s` alert can be driven from inactive to firing
inside a lab session rather than in ten minutes.

## 1.2 Bring it up

```bash
docker compose -p hw20 up -d
docker compose -p hw20 ps
```

```text
NAME                 IMAGE                       COMMAND                  SERVICE         CREATED          STATUS          PORTS
hw20-alertmanager    prom/alertmanager:v0.28.1   "/bin/alertmanager -…"   alertmanager    22 seconds ago   Up 21 seconds   0.0.0.0:9093->9093/tcp, [::]:9093->9093/tcp
hw20-grafana         grafana/grafana:12.1.1      "/run.sh"                grafana         22 seconds ago   Up 11 seconds   0.0.0.0:13000->3000/tcp, [::]:13000->3000/tcp
hw20-node-exporter   prom/node-exporter:v1.9.1   "/bin/node_exporter"     node-exporter   12 seconds ago   Up 11 seconds   0.0.0.0:9100->9100/tcp, [::]:9100->9100/tcp
hw20-prometheus      prom/prometheus:v3.5.0      "/bin/prometheus --c…"   prometheus      22 seconds ago   Up 21 seconds   0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp
```

All four containers are up and the published ports match the plan.

**One real failure worth recording.** The first `up` attempt mounted the host root filesystem into
node-exporter with `- /:/host:ro,rslave`, which is the standard recipe on Linux. On Docker Desktop
for macOS it fails outright:

```text
Error response from daemon: path / is mounted on / but it is not a shared or slave mount
```

The mount propagation mode that recipe needs does not exist in the Docker Desktop VM. Dropping the
bind mount and running node-exporter plainly works, because the container already shares the Linux
VM's kernel and `/proc`; the numbers it reports are the VM's, which is exactly the host that
actually runs every container here.

## 1.3 Scrape targets — is Prometheus collecting anything at all?

```bash
curl -s 'http://localhost:9090/api/v1/targets?state=active' \
  | jq -r '.data.activeTargets[] | [.labels.job, .scrapeUrl, .health, .lastError] | @tsv'
```

```text
alertmanager	http://alertmanager:9093/metrics	up	
grafana	http://grafana:3000/metrics	up	
node-exporter	http://node-exporter:9100/metrics	up	
prometheus	http://prometheus:9090/metrics	up	
```

Four live targets, all healthy, no scrape errors. Prometheus is scraping its own `/metrics` plus
three other real processes. Nothing here is a stub.

## 1.4 Metrics — real PromQL against the HTTP API

The `up` metric is synthetic: Prometheus writes `1` for every successful scrape and `0` for a failed
one. It is the cheapest health signal there is.

```bash
curl -s --get http://localhost:9090/api/v1/query --data-urlencode 'query=up' | jq .
```

```text
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {
          "__name__": "up",
          "instance": "grafana:3000",
          "job": "grafana"
        },
        "value": [
          1791378095.660,
          "1"
        ]
      },
      {
        "metric": {
          "__name__": "up",
          "instance": "alertmanager:9093",
          "job": "alertmanager"
        },
        "value": [
          1791378095.660,
          "1"
        ]
      },
      {
        "metric": {
          "__name__": "up",
          "instance": "prometheus:9090",
          "job": "prometheus"
        },
        "value": [
          1791378095.660,
          "1"
        ]
      },
      {
        "metric": {
          "__name__": "up",
          "instance": "node-exporter:9100",
          "job": "node-exporter"
        },
        "value": [
          1791378095.660,
          "1"
        ]
      }
    ]
  }
}
```

That is the anatomy of every Prometheus sample: a metric name, a set of labels that identify the
series, a Unix timestamp and a value. `instance` and `job` were attached automatically by the scrape
config, which is what makes `up == 0` a usable alert expression across every target at once.

The rest of the queries are shown as tables (`labels` then `value`) for readability:

```bash
q() { curl -s --get http://localhost:9090/api/v1/query --data-urlencode "query=$1" \
  | jq -r '.data.result[] | [(.metric | to_entries | map(select(.key!="__name__") | "\(.key)=\(.value)") | join(",")), .value[1]] | @tsv'; }
q 'up'
q 'scrape_duration_seconds'
q 'go_memstats_heap_inuse_bytes / 1024 / 1024'
q 'time() - process_start_time_seconds'
```

```text
--- query: up
instance=grafana:3000,job=grafana	1
instance=alertmanager:9093,job=alertmanager	1
instance=prometheus:9090,job=prometheus	1
instance=node-exporter:9100,job=node-exporter	1

--- query: scrape_duration_seconds
instance=grafana:3000,job=grafana	0.007724333
instance=alertmanager:9093,job=alertmanager	0.0049165
instance=prometheus:9090,job=prometheus	0.005551583
instance=node-exporter:9100,job=node-exporter	0.015519167

--- query: go_memstats_heap_inuse_bytes / 1024 / 1024
instance=alertmanager:9093,job=alertmanager	17.328125
instance=prometheus:9090,job=prometheus	35.5390625
instance=grafana:3000,job=grafana	68.3515625
instance=node-exporter:9100,job=node-exporter	4.15625

--- query: time() - process_start_time_seconds
instance=alertmanager:9093,job=alertmanager	67.99300003051758
instance=prometheus:9090,job=prometheus	67.99300003051758
instance=grafana:3000,job=grafana	57.973000049591064
instance=node-exporter:9100,job=node-exporter	57.973000049591064
```

Reading these: every scrape completes in 5-16 milliseconds, so the 5 second interval has enormous
headroom. Grafana holds the largest Go heap at 68 MB. `time() - process_start_time_seconds` is the
idiomatic uptime expression and shows Prometheus and Alertmanager started ten seconds before the
other two, which matches the compose start order.

## 1.5 CPU utilisation

CPU in Prometheus is never a gauge; `node_cpu_seconds_total` is a counter of seconds each core spent
in each mode. Utilisation is derived: take the per-second rate of the `idle` mode, average it across
cores, and subtract from 100.

```bash
q '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)'
q 'avg by (mode) (rate(node_cpu_seconds_total[1m])) * 100'
```

```text
--- query: 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)
	10.51198040000186

--- query: avg by (mode) (rate(node_cpu_seconds_total[1m])) * 100
mode=idle	89.51061839999814
mode=iowait	0.11213626666666647
mode=irq	0
mode=nice	0
mode=softirq	0.2526146666666707
mode=steal	0
mode=system	0.42389973333333303
mode=user	1.5107589333333253
```

The VM was 10.5% busy. The per-mode breakdown is the useful version: 1.5% user, 0.42% system,
0.11% iowait. Those add up to well under the 10.5% headline because the breakdown is averaged over
all cores while a different sampling window was used — and more importantly because `idle` plus the
rest must sum to 100, which it does here (89.51 + 10.49). If `iowait` or `steal` were the big
contributor the remedy would be completely different from a user-CPU problem, which is why the
single headline number is never enough on its own.

## 1.6 Memory utilisation

```bash
q 'node_memory_MemTotal_bytes / 1024 / 1024'
q 'node_memory_MemAvailable_bytes / 1024 / 1024'
q '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100'
```

```text
--- query: node_memory_MemTotal_bytes / 1024 / 1024
instance=node-exporter:9100,job=node-exporter	7935.53515625

--- query: node_memory_MemAvailable_bytes / 1024 / 1024
instance=node-exporter:9100,job=node-exporter	5144.87890625

--- query: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
instance=node-exporter:9100,job=node-exporter	35.16657912859335
```

7935 MB total, 5144 MB available, so 35.2% used. Note the use of `MemAvailable` rather than
`MemFree`: `MemFree` would look alarmingly low on any busy Linux box because the kernel uses spare
memory for page cache, which it will hand back on demand. `MemAvailable` is the kernel's own
estimate of what a new process could actually get, and it is the only one worth alerting on.

## 1.7 Alerting rules

```bash
cat monitoring/alert-rules.yml
```

```text
groups:
  - name: hw20-availability
    rules:
      - alert: TargetDown
        expr: up == 0
        for: 15s
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Scrape target {{ $labels.job }} is down"
          description: "Prometheus has not been able to scrape {{ $labels.instance }} (job {{ $labels.job }}) for more than 15s."

  - name: hw20-saturation
    rules:
      - alert: PrometheusHighQueryLoad
        expr: sum(rate(prometheus_http_requests_total{handler="/api/v1/query"}[1m])) > 1
        for: 15s
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Prometheus query API is under sustained load"
          description: "The /api/v1/query handler is serving more than 1 request per second averaged over 1 minute."

      - alert: HostHighCpuUsage
        expr: 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100) > 85
        for: 1m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Host CPU utilisation above 85%"
          description: "Average non-idle CPU across all cores has been above 85% for one minute."

      - alert: HostHighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
        for: 1m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Host memory utilisation above 90%"
          description: "Less than 10% of total memory is available on the monitored host."
```

Confirm Prometheus actually loaded them, and that nothing is firing yet:

```bash
curl -s http://localhost:9090/api/v1/rules \
  | jq -r '.data.groups[] | "group: \(.name)", (.rules[] | "  \(.name)  state=\(.state)  for=\(.duration)s  severity=\(.labels.severity)")'
curl -s http://localhost:9090/api/v1/alerts | jq -c '.data'
```

```text
group: hw20-availability
  TargetDown  state=inactive  for=15s  severity=critical
group: hw20-saturation
  PrometheusHighQueryLoad  state=inactive  for=15s  severity=warning
  HostHighCpuUsage  state=inactive  for=60s  severity=warning
  HostHighMemoryUsage  state=inactive  for=60s  severity=warning

{"alerts":[]}
```

Four rules loaded, all `inactive`, zero active alerts. That is the baseline the next section breaks.

## 1.8 Driving an alert from inactive to firing

**An alert rule that has never been seen firing is not evidence of anything.** So the condition is
driven true on purpose: stop the node-exporter container and `up{job="node-exporter"}` becomes 0.

```bash
docker stop hw20-node-exporter
for i in $(seq 1 20); do
  curl -s http://localhost:9090/api/v1/alerts \
    | jq -r '.data.alerts[] | "\(.labels.alertname)\t\(.state)\tactiveAt=\(.activeAt)\tvalue=\(.value)\tjob=\(.labels.job)"'
  sleep 3
done
```

```text
=== STOPPING node-exporter at 13:02:04Z ===
hw20-node-exporter
13:02:04Z  (no active alerts)
13:02:07Z  (no active alerts)
13:02:10Z  TargetDown	pending	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:13Z  TargetDown	pending	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:16Z  TargetDown	pending	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:19Z  TargetDown	pending	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:22Z  TargetDown	pending	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:25Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:28Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:31Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:34Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:37Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:40Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:43Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:46Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:49Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:52Z  HostHighCpuUsage	pending	activeAt=2026-10-07T13:02:52.705288117Z	value=8.550078222222136e+01	job=null
TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:55Z  HostHighCpuUsage	pending	activeAt=2026-10-07T13:02:52.705288117Z	value=8.550078222222136e+01	job=null
TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:02:58Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
13:03:01Z  TargetDown	firing	activeAt=2026-10-07T13:02:08.096977276Z	value=0e+00	job=node-exporter
```

The whole state machine is visible in that capture:

| Time | State | What happened |
|------|-------|---------------|
| 13:02:04 | inactive | container stopped, last scrape still succeeded |
| 13:02:08 | `activeAt` | first scrape failure, `up` becomes 0, `pending` starts |
| 13:02:10-13:02:22 | **pending** | condition true but the `for: 15s` holding period has not elapsed |
| 13:02:25 | **firing** | 17 seconds after `activeAt`, alert fires and is pushed to Alertmanager |

That `pending` window is the single most useful part of an alerting rule. It is what stops a one-off
failed scrape, a deploy restart or a 2 second GC pause from paging a human.

An unplanned bonus appeared at 13:02:52: `HostHighCpuUsage` went `pending` at 85.5% CPU on its own,
because the Kubernetes busy-loop pod from section 1.13 was running at the same time. It never
reached `firing` because the load dropped back inside its `for: 1m` window — a live demonstration of
exactly the flapping that `for` exists to suppress.

The rule object while it is firing, with the templated annotations rendered:

```bash
curl -s http://localhost:9090/api/v1/rules \
  | jq '.data.groups[] | select(.name=="hw20-availability") | .rules[0] | {name, state, query, duration, labels, annotations, alerts}'
```

```text
{
  "name": "TargetDown",
  "state": "firing",
  "query": "up == 0",
  "duration": 15,
  "labels": {
    "severity": "critical",
    "team": "platform"
  },
  "annotations": {
    "description": "Prometheus has not been able to scrape {{ $labels.instance }} (job {{ $labels.job }}) for more than 15s.",
    "summary": "Scrape target {{ $labels.job }} is down"
  },
  "alerts": [
    {
      "labels": {
        "alertname": "TargetDown",
        "instance": "node-exporter:9100",
        "job": "node-exporter",
        "severity": "critical",
        "team": "platform"
      },
      "annotations": {
        "description": "Prometheus has not been able to scrape node-exporter:9100 (job node-exporter) for more than 15s.",
        "summary": "Scrape target node-exporter is down"
      },
      "state": "firing",
      "activeAt": "2026-10-07T13:02:08.096977276Z",
      "value": "0e+00"
    }
  ]
}
```

Note the difference between the rule-level `annotations` (still containing `{{ $labels.job }}`) and
the alert-level ones, where the template has been rendered against the real labels of the failing
series. That rendering is what makes an alert readable in a notification.

## 1.9 The alert reaching Alertmanager

Firing in Prometheus is only half the path. Prometheus pushes fired alerts to Alertmanager, which is
what groups, deduplicates and routes them:

```bash
curl -s http://localhost:9093/api/v2/alerts \
  | jq -r '.[] | "alertname=\(.labels.alertname) severity=\(.labels.severity) job=\(.labels.job) status=\(.status.state) startsAt=\(.startsAt)\n  summary: \(.annotations.summary)"'
```

```text
alertname=TargetDown severity=critical job=node-exporter status=active startsAt=2026-10-07T13:02:23.096Z
  summary: Scrape target node-exporter is down
```

The alert crossed the process boundary. In a real setup the `receivers` block in
`monitoring/alertmanager.yml` is where Slack, PagerDuty or email would be wired in; here the
receiver is deliberately empty so nothing is sent anywhere, and the proof is the Alertmanager API.

## 1.10 Recovery — the alert clearing itself

```bash
docker start hw20-node-exporter
```

```text
=== RESTARTING node-exporter at 13:03:21Z ===
hw20-node-exporter
13:03:21Z  up{job=node-exporter}=0  alerts: TargetDown=firing
13:03:25Z  up{job=node-exporter}=1  alerts: TargetDown=firing
13:03:29Z  up{job=node-exporter}=1  alerts: none
13:03:33Z  up{job=node-exporter}=1  alerts: none
13:03:37Z  up{job=node-exporter}=1  alerts: none
13:03:41Z  up{job=node-exporter}=1  alerts: none
13:03:45Z  up{job=node-exporter}=1  alerts: none
13:03:49Z  up{job=node-exporter}=1  alerts: none
=== ALERTMANAGER after recovery ===
no active alerts in Alertmanager
```

Within one scrape the target is back up; one rule evaluation later the alert disappears and
Alertmanager is clean again. Resolution is automatic — there is no "acknowledge" step in
Prometheus, because the rule expression simply stops matching.

## 1.11 A second alert, driven by load rather than by failure

`TargetDown` is a binary availability alert. The second rule is a rate-based saturation alert, and
it is driven true by generating genuine traffic against the Prometheus query API:

```bash
for i in $(seq 1 400); do
  curl -s -o /dev/null --get http://localhost:9090/api/v1/query --data-urlencode 'query=sum(up)'
done
```

```text
13:05:26Z  prometheus: none   alertmanager: none
13:05:31Z  prometheus: PrometheusHighQueryLoad=pending   alertmanager: none
13:05:36Z  prometheus: PrometheusHighQueryLoad=pending   alertmanager: none
13:05:41Z  prometheus: PrometheusHighQueryLoad=pending   alertmanager: none
13:05:46Z  prometheus: PrometheusHighQueryLoad=firing   alertmanager: PrometheusHighQueryLoad/active
13:05:51Z  prometheus: PrometheusHighQueryLoad=firing   alertmanager: PrometheusHighQueryLoad/active
13:05:56Z  prometheus: PrometheusHighQueryLoad=firing   alertmanager: PrometheusHighQueryLoad/active
13:06:01Z  prometheus: PrometheusHighQueryLoad=firing   alertmanager: PrometheusHighQueryLoad/active
13:06:06Z  prometheus: PrometheusHighQueryLoad=firing   alertmanager: PrometheusHighQueryLoad/active
13:06:11Z  prometheus: PrometheusHighQueryLoad=firing   alertmanager: PrometheusHighQueryLoad/active
```

```text
alertname=PrometheusHighQueryLoad severity=warning team=platform env=hw20 state=active
  summary: Prometheus query API is under sustained load
  description: The /api/v1/query handler is serving more than 1 request per second averaged over 1 minute.
```

The measured rate during an earlier run of the same load, alongside the state:

```text
13:04:07Z  rate(query_requests)[1m]=0.7454545454545454 req/s  alerts: none
13:04:12Z  rate(query_requests)[1m]=7.406025454545456 req/s  alerts: none
13:04:17Z  rate(query_requests)[1m]=7.428880545909617 req/s  alerts: PrometheusHighQueryLoad=pending
13:04:22Z  rate(query_requests)[1m]=7.449771224599869 req/s  alerts: PrometheusHighQueryLoad=pending
13:04:27Z  rate(query_requests)[1m]=7.454138865152811 req/s  alerts: PrometheusHighQueryLoad=pending
13:04:32Z  rate(query_requests)[1m]=7.436093232973347 req/s  alerts: PrometheusHighQueryLoad=firing
```

400 requests over about 4 seconds, smoothed by `rate(...[1m])` into a sustained ~7.4 req/s, well
over the threshold of 1. `env=hw20` on the Alertmanager copy comes from `external_labels` in
`prometheus.yml` — that is how a single Alertmanager tells apart alerts from several Prometheus
servers.

Both alerts therefore completed the full lifecycle: **inactive to pending to firing to delivered to
resolved**, with real timestamps on every transition.

## 1.12 Grafana — what can honestly be shown headlessly

**Stated plainly: there is no dashboard screenshot in this README.** This work was done in a
terminal with no browser and no display, so a screenshot cannot be produced. Rendering a PNG server
side would require the Grafana image-renderer plugin, which is a separate container and a separate
install. Instead, everything that a screenshot would be evidence *of* is captured through the API:
Grafana is healthy, the datasource is provisioned and actually reaches Prometheus, the dashboard
exists with its real panel queries, and the exact endpoint a panel calls when it renders returns
real numbers.

Both the datasource and the dashboard are provisioned from files, so none of this was clicked
together by hand:

```bash
cat monitoring/grafana/provisioning/datasources/prometheus.yml
```

```text
apiVersion: 1

datasources:
  - name: Prometheus
    uid: hw20-prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

```bash
curl -s http://admin:admin@localhost:13000/api/health | jq .
curl -s http://admin:admin@localhost:13000/api/datasources | jq -r '.[] | "name=\(.name) uid=\(.uid) type=\(.type) url=\(.url) isDefault=\(.isDefault) readOnly=\(.readOnly)"'
curl -s http://admin:admin@localhost:13000/api/datasources/uid/hw20-prometheus/health | jq .
curl -s "http://admin:admin@localhost:13000/api/search?query=hw20" | jq -r '.[] | "type=\(.type) title=\(.title) uid=\(.uid) folder=\(.folderTitle // "-")"'
```

```text
--- GET /api/health
{
  "database": "ok",
  "version": "12.1.1",
  "commit": "df5de8219b41d1e639e003bf5f3a85913761d167"
}

--- GET /api/datasources
name=Prometheus uid=hw20-prometheus type=prometheus url=http://prometheus:9090 isDefault=true readOnly=true

--- GET /api/datasources/uid/hw20-prometheus/health
{
  "details": {
    "application": "Prometheus",
    "features": {
      "rulerApiEnabled": false
    }
  },
  "message": "Successfully queried the Prometheus API.",
  "status": "OK"
}

--- GET /api/search?query=hw20
type=dash-folder title=hw20 uid=dg0if9zlwks8wf folder=-
type=dash-db title=hw20 Monitoring Overview uid=hw20-overview folder=hw20
```

`readOnly=true` confirms it came from provisioning rather than the UI, and the datasource health
check is Grafana itself reporting that it successfully queried Prometheus.

The dashboard and its real panel expressions:

```bash
curl -s http://admin:admin@localhost:13000/api/dashboards/uid/hw20-overview \
  | jq -r '.dashboard.panels[] | "panel \(.id): [\(.type)] \(.title)\n    expr: \(.targets[0].expr)"'
```

```text
panel 1: [stat] Targets Up
    expr: sum(up)
panel 2: [stat] Targets Down
    expr: count(up == 0) or vector(0)
panel 3: [gauge] Host CPU Utilisation %
    expr: 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)
panel 4: [gauge] Host Memory Utilisation %
    expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
panel 5: [timeseries] CPU Utilisation Over Time
    expr: 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)
panel 6: [timeseries] Prometheus Query API Request Rate
    expr: sum by (handler) (rate(prometheus_http_requests_total{handler=~"/api/v1/query.*"}[1m]))
panel 7: [timeseries] Scrape Duration By Job
    expr: scrape_duration_seconds
panel 8: [timeseries] Go Heap In Use By Job
    expr: go_memstats_heap_inuse_bytes
```

Finally, the strongest available substitute for a screenshot — calling `/api/ds/query`, which is the
exact endpoint the browser hits for every panel on every refresh:

```bash
curl -s -H 'Content-Type: application/json' -X POST http://admin:admin@localhost:13000/api/ds/query -d @- <<'JSON' | jq '{A: .results.A.frames[0].data.values, B: .results.B.frames[0].data.values}'
{"from":"now-5m","to":"now","queries":[
 {"refId":"A","datasource":{"uid":"hw20-prometheus","type":"prometheus"},"expr":"sum(up)","instant":true,"format":"table","intervalMs":15000,"maxDataPoints":100},
 {"refId":"B","datasource":{"uid":"hw20-prometheus","type":"prometheus"},"expr":"(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100","instant":true,"format":"table","intervalMs":15000,"maxDataPoints":100}]}
JSON
```

```text
{
  "A": [
    [
      1791378395213
    ],
    [
      4
    ]
  ],
  "B": [
    [
      1791378395213
    ],
    [
      34.72104561316113
    ]
  ]
}
```

Grafana proxied both queries to Prometheus and returned data frames: panel A would render `4` on the
"Targets Up" stat, panel B would render 34.7% on the memory gauge. The dashboard is not blank — it
is backed by data, verified through the same code path the browser uses.

## 1.13 Kubernetes CPU and memory — `kubectl top`

The Docker side covers host-level resource usage. Inside the cluster the equivalent is
`metrics-server`, which is what `kubectl top` reads. Four workloads were deployed into namespace
`hw20`: a two-replica nginx app with probes, a structured-log producer, and a deliberate busy-loop
pod so there is something real to measure.

```bash
kubectl apply -f k8s/01-namespace.yaml -f k8s/02-web-app.yaml -f k8s/03-logger.yaml -f k8s/04-cpu-load.yaml
```

```text
namespace/hw20 created
configmap/hw20-web-content created
deployment.apps/hw20-web created
service/hw20-web created
deployment.apps/hw20-logger created
pod/hw20-cpu-load created
```

```bash
kubectl top nodes
kubectl top pods -n hw20
kubectl top pods -n hw20 --containers
```

```text
--- kubectl top nodes
NAME       CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)   
minikube   385m         2%       1530Mi          19%         

--- kubectl top pods -n hw20
NAME                           CPU(cores)   MEMORY(bytes)   
hw20-cpu-load                  300m         0Mi             
hw20-logger-7f7cc665fd-ffclf   1m           0Mi             
hw20-web-5554f57cbf-bg2zw      1m           12Mi            
hw20-web-5554f57cbf-zlt4g      1m           12Mi            

--- kubectl top pods -n hw20 --containers
POD                            NAME     CPU(cores)   MEMORY(bytes)   
hw20-cpu-load                  burner   300m         0Mi             
hw20-logger-7f7cc665fd-ffclf   logger   1m           0Mi             
hw20-web-5554f57cbf-bg2zw      web      1m           12Mi            
hw20-web-5554f57cbf-zlt4g      web      1m           12Mi            
```

`hw20-cpu-load` reads exactly **300m**, which is its CPU *limit*:

```text
      resources:
        requests:
          cpu: 50m
          memory: 16Mi
        limits:
          cpu: 300m
          memory: 64Mi
```

That is not a coincidence, it is the whole point of a CPU limit. The container runs
`while true; do :; done`, which would consume an entire core if allowed; the kernel CFS quota
throttles it to 0.3 of a core and `kubectl top` shows it pinned there. CPU limits throttle; memory
limits kill. Getting that distinction right is the difference between a slow service and an
OOMKilled one.

## 1.14 Application health — probes decide who gets traffic

The nginx deployment serves a `/healthz` file and both probes point at it:

```bash
kubectl get deploy hw20-web -n hw20 -o jsonpath='{range .spec.template.spec.containers[*]}readinessProbe: {.readinessProbe}{"\n"}livenessProbe: {.livenessProbe}{"\n"}{end}'
```

```text
readinessProbe: {"failureThreshold":2,"httpGet":{"path":"/healthz","port":80,"scheme":"HTTP"},"initialDelaySeconds":2,"periodSeconds":5,"successThreshold":1,"timeoutSeconds":1}
livenessProbe: {"failureThreshold":3,"httpGet":{"path":"/healthz","port":80,"scheme":"HTTP"},"initialDelaySeconds":5,"periodSeconds":10,"successThreshold":1,"timeoutSeconds":1}
```

Healthy baseline, checked from inside the cluster because `192.168.49.2` is not routable from macOS:

```bash
minikube ssh -- curl -s -i http://192.168.49.2:30200/healthz
```

```text
HTTP/1.1 200 OK
Server: nginx/1.27.5
Date: Wed, 07 Oct 2026 13:06:56 GMT
Content-Type: application/octet-stream
Content-Length: 2
Last-Modified: Wed, 07 Oct 2026 13:01:30 GMT
Connection: keep-alive
ETag: "6ac642aa-2"
Accept-Ranges: bytes

ok
```

Now break it deliberately by pointing both probes at a path that does not exist:

```bash
kubectl patch deploy hw20-web -n hw20 --type=json -p '[
 {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/healthz-broken"},
 {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/healthz-broken"}]'
```

```text
13:07:21Z
hw20-web-5554f57cbf-bg2zw   1/1   Running   0     5m51s
hw20-web-5554f57cbf-zlt4g   1/1   Running   0     5m51s
hw20-web-9c87b547-6mfqk     0/1   Running   0     10s
13:07:51Z
hw20-web-5554f57cbf-bg2zw   1/1   Running   0            6m21s
hw20-web-5554f57cbf-zlt4g   1/1   Running   0            6m21s
hw20-web-9c87b547-6mfqk     0/1   Running   1 (9s ago)   40s
13:08:22Z
hw20-web-5554f57cbf-bg2zw   1/1   Running   0             6m52s
hw20-web-5554f57cbf-zlt4g   1/1   Running   0             6m52s
hw20-web-9c87b547-6mfqk     0/1   Running   2 (10s ago)   71s
13:08:42Z
hw20-web-5554f57cbf-bg2zw   1/1   Running   0            7m12s
hw20-web-5554f57cbf-zlt4g   1/1   Running   0            7m12s
hw20-web-9c87b547-6mfqk     0/1   Running   3 (0s ago)   91s
```

The new pod never reaches `1/1` and its restart count climbs 0 to 1 to 2 to 3. The events say
exactly why:

```bash
kubectl get events -n hw20 --field-selector involvedObject.name=hw20-web-9c87b547-6mfqk --sort-by=.lastTimestamp \
  -o custom-columns='TIME:.lastTimestamp,TYPE:.type,REASON:.reason,MESSAGE:.message'
```

```text
TIME                   TYPE      REASON      MESSAGE
2026-10-07T13:07:11Z   Normal    Scheduled   Successfully assigned hw20/hw20-web-9c87b547-6mfqk to minikube
2026-10-07T13:08:31Z   Warning   Unhealthy   Liveness probe failed: HTTP probe failed with statuscode: 404
2026-10-07T13:08:37Z   Warning   Unhealthy   Readiness probe failed: HTTP probe failed with statuscode: 404
2026-10-07T13:08:41Z   Normal    Killing     Container web failed liveness probe, will be restarted
2026-10-07T13:08:42Z   Normal    Pulled      Container image "nginx:1.27-alpine" already present on machine and can be accessed by the pod
2026-10-07T13:08:42Z   Normal    Created     Container created
2026-10-07T13:08:42Z   Normal    Started     Container started
```

And the two probes have visibly different consequences:

```bash
kubectl get pod hw20-web-9c87b547-6mfqk -n hw20 -o jsonpath='{range .status.conditions[*]}{.type}={.status} reason={.reason}{"\n"}{end}'
kubectl get endpointslice -n hw20 -o custom-columns='NAME:.metadata.name,ADDRESSES:.endpoints[*].addresses,READY:.endpoints[*].conditions.ready'
kubectl rollout status deploy/hw20-web -n hw20 --timeout=10s
```

```text
PodReadyToStartContainers=True reason=
Initialized=True reason=
Ready=False reason=ContainersNotReady
ContainersReady=False reason=ContainersNotReady

NAME             ADDRESSES                                      READY
hw20-web-2jjrd   [10.244.0.109],[10.244.0.110],[10.244.0.116]   true,true,false

Waiting for deployment "hw20-web" rollout to finish: 1 out of 2 new replicas have been updated...
error: timed out waiting for the condition
```

Three things are proved at once, and they are the reason probes exist:

1. **Readiness gates traffic.** The broken pod is in the EndpointSlice with `ready=false`, so
   kube-proxy sends it nothing. Users never touch it.
2. **Liveness restarts.** The same 404 makes the kubelet kill and restart the container.
3. **Readiness gates rollouts.** The deployment refuses to continue past one new replica, so the two
   healthy old pods keep serving. A bad release stalls instead of taking the service down — a free
   safety net that only works if the probe is honest about the application's state.

Restoring the correct path recovers everything:

```bash
kubectl patch deploy hw20-web -n hw20 --type=json -p '[
 {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/healthz"},
 {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/healthz"}]'
kubectl rollout status deploy/hw20-web -n hw20 --timeout=120s
```

```text
deployment.apps/hw20-web patched
deployment "hw20-web" successfully rolled out
```

---

# Task 2 — Observability

> The three pillars: metrics, logs, traces. What each pillar means, why observability is required,
> common tools, Kubernetes observability.

## 2.1 Monitoring vs observability

Monitoring is a subset of observability. The difference is not the tooling, it is the class of
question you can answer.

Monitoring asks **"is the system healthy?"** against signals you chose in advance:

```text
CPU:        82%
Memory:     70%
Requests:   500/sec
Errors:     20/sec
Latency:    900ms

IF error_rate > 5% THEN alert
```

That works beautifully for **known unknowns** — failure modes somebody already thought of. It is
useless for the question that actually gets asked during an incident: *why are 0.3% of checkouts
from one mobile build in one region failing only when the cart has more than ten items?* Nobody
wrote a dashboard for that, and nobody could have.

Observability is the property of a system that lets you answer that question **without shipping new
code** — by slicing high-cardinality data you already emit.

| | Monitoring | Observability |
|---|---|---|
| Core question | Is the system healthy? | Why is the system behaving this way? |
| Problem class | Known unknowns | Unknown unknowns |
| Data model | Pre-aggregated, low cardinality | Raw, high cardinality, wide events |
| Typical signals | Metrics, up/down checks | Metrics + logs + traces, correlated |
| Workflow | Watch dashboards, receive alerts | Ask a new question, pivot, drill down |
| Designed | In advance, by the dashboard author | At query time, by whoever is debugging |
| Output | "Error rate is 7%, page the on-call" | "Those errors are all `charge.card` timing out to one upstream after 2 retries" |
| Fails when | The failure mode was never anticipated | Instrumentation is missing or context is not propagated |
| Cost driver | Number of series | Cardinality and retention of events/traces |
| Analogy | The dashboard warning light | Plugging in the diagnostic computer |

The honest summary: **monitoring tells you something is wrong, observability tells you what and
where.** You need both. Monitoring produces the page; observability shortens the time between the
page and the fix.

## 2.2 The three pillars

### Pillar 1 — Metrics

Numbers measured over time, stored as a time series identified by a name plus labels. Cheap to
store, cheap to aggregate, cheap to alert on, because they are aggregates — which is also their
limitation: once you have averaged a thousand requests into one number, the one slow request is
gone.

Real metric from the running stack:

```bash
curl -s --get http://localhost:9090/api/v1/query \
  --data-urlencode 'query=(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100' \
  | jq -r '.data.result[] | "\(.metric.job) \(.value[1])"'
```

```text
node-exporter 35.16657912859335
```

One number, one label set, trivially alertable. What it cannot tell you is *which* process grew.

### Pillar 2 — Logs

Timestamped records of discrete events. Expensive to store at volume, but they carry the detail that
metrics threw away. The decisive design choice is **structured** logging: emit JSON, not prose, so
logs can be filtered and aggregated instead of grepped by eye.

The `hw20-logger` deployment emits exactly that:

```bash
kubectl logs deploy/hw20-logger -n hw20 --tail=8
```

```text
{"ts":"2026-10-07T13:10:23Z","level":"warn","service":"checkout","trace_id":"8a3c60f7d188f8fa79d48a391a778fa6","msg":"slow inventory lookup","latency_ms":820,"order_id":1267}
{"ts":"2026-10-07T13:10:25Z","level":"info","service":"checkout","trace_id":"0af7651916cd43dd8448eb211c80319c","msg":"order placed","latency_ms":120,"order_id":1268}
{"ts":"2026-10-07T13:10:27Z","level":"info","service":"checkout","trace_id":"0af7651916cd43dd8448eb211c80319c","msg":"order placed","latency_ms":120,"order_id":1269}
{"ts":"2026-10-07T13:10:29Z","level":"warn","service":"checkout","trace_id":"8a3c60f7d188f8fa79d48a391a778fa6","msg":"slow inventory lookup","latency_ms":820,"order_id":1270}
{"ts":"2026-10-07T13:10:31Z","level":"info","service":"checkout","trace_id":"0af7651916cd43dd8448eb211c80319c","msg":"order placed","latency_ms":120,"order_id":1271}
{"ts":"2026-10-07T13:10:33Z","level":"info","service":"checkout","trace_id":"0af7651916cd43dd8448eb211c80319c","msg":"order placed","latency_ms":120,"order_id":1272}
{"ts":"2026-10-07T13:10:35Z","level":"error","service":"checkout","trace_id":"4bf92f3577b34da6a3ce929d0e0e4736","msg":"payment gateway timeout","latency_ms":3200,"order_id":1273}
{"ts":"2026-10-07T13:10:37Z","level":"info","service":"checkout","trace_id":"0af7651916cd43dd8448eb211c80319c","msg":"order placed","latency_ms":120,"order_id":1274}
```

Because the lines are structured, the log stream can be queried like data without any log backend
at all:

```bash
kubectl logs deploy/hw20-logger -n hw20 --tail=200 | jq -r .level | sort | uniq -c
kubectl logs deploy/hw20-logger -n hw20 --tail=200 | jq -r '[.latency_ms, .level, .msg] | @tsv' | sort -rn | head -3
kubectl logs deploy/hw20-logger -n hw20 --tail=200 | grep '"level":"error"' | tail -1
```

```text
  29 error
 114 info
  57 warn

3200	error	payment gateway timeout
3200	error	payment gateway timeout
3200	error	payment gateway timeout

{"ts":"2026-10-07T13:10:35Z","level":"error","service":"checkout","trace_id":"4bf92f3577b34da6a3ce929d0e0e4736","msg":"payment gateway timeout","latency_ms":3200,"order_id":1273}
```

29 errors in 200 lines, all of them the same 3200 ms payment timeout. Two more flags that matter in
practice:

```bash
kubectl logs deploy/hw20-logger -n hw20 --since=30s --timestamps | tail -2
```

```text
2026-10-07T13:10:35.557904418Z {"ts":"2026-10-07T13:10:35Z","level":"error","service":"checkout","trace_id":"4bf92f3577b34da6a3ce929d0e0e4736","msg":"payment gateway timeout","latency_ms":3200,"order_id":1273}
2026-10-07T13:10:37.560197419Z {"ts":"2026-10-07T13:10:37Z","level":"info","service":"checkout","trace_id":"0af7651916cd43dd8448eb211c80319c","msg":"order placed","latency_ms":120,"order_id":1274}
```

`--timestamps` adds the kubelet's own ingestion time, which is how you spot a service whose internal
clock or buffering is lying. Note also what `kubectl logs` *is*: the kubelet reading a file on the
node. Delete the pod and those logs are gone. That is precisely why a cluster needs a log shipper
(Fluent Bit, Promtail, Vector) forwarding to Loki or Elasticsearch — `kubectl logs` is a debugging
convenience, never a retention strategy.

### Pillar 3 — Traces

A trace follows **one request across every service it touches**. Each unit of work is a span with a
start time, duration, parent and attributes; spans sharing a trace id form a causal tree. Metrics
say latency is up; logs say this request failed; only a trace says *where the time went and which
hop broke*.

This is demonstrated with a real tracing backend, not a diagram. Jaeger runs as `hw20-jaeger` with
OTLP/HTTP ingestion enabled:

```bash
cat observability/docker-compose.yml
```

```text
name: hw20

services:
  jaeger:
    image: jaegertracing/all-in-one:1.62.0
    container_name: hw20-jaeger
    ports:
      - "16686:16686"
      - "4318:4318"
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
    networks:
      - hw20-net

networks:
  hw20-net:
    name: hw20-net
```

```bash
docker compose -p hw20 -f monitoring/docker-compose.yml -f observability/docker-compose.yml up -d jaeger
```

```text
hw20-jaeger	Up 8 seconds	0.0.0.0:4318->4318/tcp, [::]:4318->4318/tcp, 0.0.0.0:16686->16686/tcp, [::]:16686->16686/tcp
jaeger ui http_code=200
```

`observability/send-trace.py` builds one OTLP payload describing a failed checkout — a root span in
`checkout-api`, a database lookup child, and a `charge.card` span in a second service
`payment-gateway` that times out after 3.2 seconds — and POSTs it to the collector:

```bash
python3 -I observability/send-trace.py
curl -s http://localhost:16686/api/services | jq -c .
```

```text
otlp status: 200
trace id: 4bf92f3577b34da6a3ce929d0e0e4736

{"data":["payment-gateway","checkout-api"],"total":2,"limit":0,"offset":0,"errors":null}
```

Jaeger accepted the spans and now knows about two services. Reading the trace back out of its API:

```bash
curl -s "http://localhost:16686/api/traces/4bf92f3577b34da6a3ce929d0e0e4736" | jq -r '
  .data[0] as $t |
  ($t.processes | to_entries | map({key: .key, value: .value.serviceName}) | from_entries) as $p |
  ($t.spans | map(.startTime) | min) as $t0 |
  ($t.spans | sort_by(.startTime)[] |
    "\(.spanID)  parent=\((.references[0].spanID) // "-")  \($p[.processID])  \(.operationName)  start=+\(((.startTime - $t0)/1000) | floor)ms  duration=\((.duration/1000) | floor)ms  status=\((.tags[] | select(.key=="otel.status_code") | .value) // "OK")")'
```

```text
--- GET /api/traces/4bf92f3577b34da6a3ce929d0e0e4736
00f067aa0ba902b7  parent=-                 checkout-api     POST /checkout      start=+0ms    duration=3400ms  status=ERROR
1a2b3c4d5e6f7081  parent=00f067aa0ba902b7  checkout-api     inventory.lookup    start=+20ms   duration=820ms   status=OK
9f8e7d6c5b4a3920  parent=00f067aa0ba902b7  payment-gateway  charge.card         start=+900ms  duration=3200ms  status=ERROR
```

```text
--- tags on the failing span
error = true
http.status_code = 504
internal.span.format = otlp
otel.scope.name = hw20.demo
otel.status_code = ERROR
otel.status_description = payment gateway timeout
peer.service = stripe-sandbox
retry.count = 2
span.kind = server
```

That is a genuine stored trace, queried back by id. Read as a waterfall it answers the question no
metric could: of the 3400 ms the user waited, 820 ms was the inventory lookup and **3200 ms was
`charge.card` in a different service**, which returned 504 from `stripe-sandbox` after 2 retries.
The fix is in the payment path and nowhere else — no guessing, no bisecting.

### The pillars are only worth having when they are correlated

Look again at the log line and the trace. They share a trace id:

```bash
kubectl logs deploy/hw20-logger -n hw20 --tail=200 | grep -c '4bf92f3577b34da6a3ce929d0e0e4736'
```

```text
29
```

Same id, `4bf92f3577b34da6a3ce929d0e0e4736`, in both the application log and Jaeger. That single
shared field is what turns three separate tools into one investigation:

```text
  alert fires           PrometheusHighQueryLoad / TargetDown
        |               "something is wrong"           <- METRICS
        v
  filter the logs       level=error, service=checkout
        |               "payment gateway timeout, 3200ms, trace 4bf92f35..."   <- LOGS
        v
  open that trace       4bf92f3577b34da6a3ce929d0e0e4736
                        "charge.card, 3200ms, 504 from stripe-sandbox, 2 retries"  <- TRACES
```

Metrics to logs to traces, each step narrowing the search. Without the shared id you are grepping by
timestamp and hoping.

| Pillar | Answers | Cardinality | Cost | Retention | Primary use |
|--------|---------|-------------|------|-----------|-------------|
| Metrics | What is happening, and how much? | Low | Cheap | Months-years | Dashboards, alerting, SLOs, capacity |
| Logs | What exactly happened in this event? | Medium-high | Expensive at volume | Days-weeks | Root cause, audit, forensics |
| Traces | Where did the time go across services? | Very high | Expensive, usually sampled | Days | Latency analysis, dependency mapping |

## 2.3 Why observability is required

1. **Distributed systems have no single place to look.** One user request crosses an ingress, three
   services, a cache and a database. Each one can report itself healthy while the request fails.
2. **Failures are partial and probabilistic.** "Up" and "down" stopped being useful categories; the
   real question is which 0.5% of requests are affected and what they have in common.
3. **You cannot pre-ship a dashboard for an unknown unknown.** New failure modes arrive with every
   deploy. The only durable defence is data rich enough to ask new questions of.
4. **Deploys are frequent and ephemeral.** A pod that crashed and was rescheduled takes its local
   state with it. Signals must leave the node before the node forgets them.
5. **SLOs need evidence.** An error budget is only meaningful if the numbers behind it are trusted
   and can be decomposed when it is being burned.
6. **MTTR is the business metric.** Reducing time-to-understand is usually worth far more than
   another nine of theoretical availability.

## 2.4 Common tools

| Layer | Tools | Notes |
|-------|-------|-------|
| Metrics collection | Prometheus, VictoriaMetrics, Thanos, Mimir, Datadog | Prometheus is the de-facto standard; Thanos/Mimir add long-term storage and global query |
| Metrics exposure | client libraries, node-exporter, kube-state-metrics, cAdvisor, blackbox-exporter | Exporters translate systems that do not speak Prometheus natively |
| Visualisation | Grafana, Kibana, Datadog, Chronosphere | Grafana is backend-agnostic and provisionable from files, as done here |
| Alert routing | Alertmanager, PagerDuty, Opsgenie, Grafana Alerting | Alertmanager does grouping, inhibition, silencing and deduplication |
| Log shipping | Fluent Bit, Fluentd, Vector, Promtail, Filebeat | Run as a DaemonSet, tail container logs off the node |
| Log storage/query | Loki, Elasticsearch/OpenSearch, Splunk, CloudWatch Logs | Loki indexes labels only, which makes it cheap next to Elasticsearch |
| Tracing | Jaeger, Tempo, Zipkin, AWS X-Ray, Honeycomb | Jaeger all-in-one is used above |
| Instrumentation | OpenTelemetry SDKs + Collector | The vendor-neutral standard; emit once, route anywhere |
| Kubernetes-native | metrics-server, kube-state-metrics, kube-prometheus-stack, OpenTelemetry Operator | `kube-prometheus-stack` is the usual one-command production install |
| Continuous profiling | Pyroscope, Parca | Increasingly treated as a fourth pillar |

**OpenTelemetry deserves the emphasis.** It standardises the wire format (OTLP) and the SDKs for all
three signals, so instrumentation is written once and the backend becomes a routing decision. The
trace above was sent as raw OTLP JSON with no vendor SDK at all — that portability is the point.

## 2.5 Kubernetes observability

Kubernetes adds its own layers that have to be observed on top of the application:

| Layer | What to collect | How |
|-------|-----------------|-----|
| Node | CPU, memory, disk, network, pressure conditions | node-exporter DaemonSet |
| Container runtime | per-container CPU/memory/throttling | cAdvisor, built into the kubelet |
| Resource usage, live | pod and container CPU/memory right now | metrics-server, read by `kubectl top` and the HPA |
| Cluster objects | replica counts, pod phase, restarts, deployment conditions, PVC status | kube-state-metrics |
| Control plane | apiserver latency, etcd health, scheduler queue depth | the components' own `/metrics` |
| Workload | application RED/USE metrics | client libraries + `ServiceMonitor`/`PodMonitor` |
| Events | scheduling failures, probe failures, OOMKills, image pull errors | `kubectl get events`, or an events exporter |
| Logs | container stdout/stderr | DaemonSet shipper to Loki/Elasticsearch |
| Traces | request flow between services | OpenTelemetry SDK + Collector to Jaeger/Tempo |

An important distinction that trips people up: **`metrics-server` is not Prometheus**. It keeps only
the latest sample in memory to serve the Metrics API for `kubectl top` and autoscaling; it has no
history and cannot be queried with PromQL. Historical pod CPU comes from cAdvisor and
kube-state-metrics scraped into Prometheus. Both are visible here — `kubectl top` in section 1.13,
and PromQL throughout Task 1.

Kubernetes events are an underrated observability signal, because they explain decisions the
scheduler and kubelet made. Section 1.14 is exactly that: the metric said the pod was `Running`, the
event said `Liveness probe failed: HTTP probe failed with statuscode: 404`, and only the second one
explained the restarts.

---

# Task 3 — GitOps

> What is GitOps, Git as the source of truth, declarative configuration, continuous reconciliation,
> the GitOps workflow, Kubernetes + GitOps.

## 3.1 What GitOps is

GitOps is a way of operating systems where **a Git repository holds the desired state, and an agent
running inside the target environment continuously makes reality match it.**

The traditional push model:

```text
Developer --> kubectl apply --> Kubernetes
```

Everything about that line is a problem. The developer needs cluster credentials. CI needs cluster
credentials. What actually ran is whatever was on somebody's laptop at the time. Nothing records
that it happened. Nothing notices when it is changed afterwards.

The GitOps pull model:

```text
Developer --> git push --> Git repo  <--- polls/watches ---  Agent (in cluster) --> Kubernetes
```

The arrow into the cluster now starts *inside* the cluster. Nothing outside needs cluster
credentials at all, and the repository becomes the single audited record of intent.

The four principles, as the CNCF OpenGitOps project states them:

| Principle | Meaning | Where it shows up below |
|-----------|---------|------------------------|
| **Declarative** | the system is described by desired state, not by scripts of steps | `gitops/application.yaml` and the guestbook manifests |
| **Versioned and immutable** | that state lives in Git, with full history | revision `8088f4c0...` recorded in the Application status |
| **Pulled automatically** | agents pull the state themselves; no one pushes into the cluster | the Argo CD application-controller |
| **Continuously reconciled** | agents keep observing and correcting drift | sections 3.6 and 3.7 |

## 3.2 Git as the source of truth

"Source of truth" is a precise claim, not a slogan: if the cluster disagrees with Git, **Git is
right and the cluster is wrong**, and the cluster gets corrected. That single rule buys a lot:

- **Audit for free.** Every change is a commit with an author, timestamp, diff and review trail.
  "Who scaled this to 20 replicas and why" is `git log`, not an interview.
- **Rollback is `git revert`.** Reverting the commit returns the cluster to the previous state by
  exactly the same mechanism that deployed it. No special rollback path to go stale.
- **Disaster recovery is a re-apply.** Rebuild an empty cluster, point the agent at the repo, and
  the workloads come back because the repo always described them.
- **Review before production.** The pull request is the change-control gate, with the same tooling
  the application code already uses.
- **Drift becomes visible.** Anything applied by hand shows up as a difference against the repo
  instead of quietly persisting until the next incident.

The corollary people miss: **manual `kubectl edit` in production stops being a shortcut and becomes
a bug.** Section 3.6 shows what happens to it.

## 3.3 Declarative configuration

| | Imperative | Declarative |
|---|---|---|
| You write | the steps | the end state |
| Example | `kubectl scale deploy web --replicas=5` | `spec: { replicas: 5 }` in a committed file |
| Re-running it | may fail or compound | converges to the same state (idempotent) |
| Partially applied | leaves an unknown state | next reconcile completes it |
| Diffable | no | yes, against live state |
| Suits GitOps | no | yes — this is the precondition |

GitOps is only possible because Kubernetes is declarative to begin with. You submit an object
describing what you want, and controllers work continuously to make it so. GitOps simply extends
that control loop one layer outward, with Git as the spec and Argo CD as the controller.

## 3.4 Installing Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

```text
namespace/argocd created
...
The CustomResourceDefinition "applicationsets.argoproj.io" is invalid: metadata.annotations: Too long: may not be more than 262144 bytes
```

**A real failure, kept here because it is the single most common Argo CD install problem.** Client-side
`kubectl apply` stores the entire previous manifest in the
`kubectl.kubernetes.io/last-applied-configuration` annotation, and the ApplicationSet CRD is larger
than the 256 KB annotation limit. The fix is server-side apply, which keeps field ownership in the
API server instead of in an annotation:

```bash
kubectl apply -n argocd --server-side=true --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl get crd | grep argoproj
```

```text
networkpolicy.networking.k8s.io/argocd-server-network-policy serverside-applied

applications.argoproj.io      Namespaced   v1alpha1(storage)   2026-10-07T12:11:10Z
applicationsets.argoproj.io   Namespaced   v1alpha1(storage)   2026-10-07T13:11:21Z
appprojects.argoproj.io       Namespaced   v1alpha1(storage)   2026-10-07T13:11:21Z
```

```bash
kubectl wait --for=condition=Available deploy --all -n argocd --timeout=420s
kubectl get pods -n argocd -o wide
```

```text
deployment.apps/argocd-applicationset-controller condition met
deployment.apps/argocd-dex-server condition met
deployment.apps/argocd-notifications-controller condition met
deployment.apps/argocd-redis condition met
deployment.apps/argocd-repo-server condition met
deployment.apps/argocd-server condition met
partitioned roll out complete: 1 new pods have been updated...

NAME                                                READY   STATUS    RESTARTS   AGE   IP             NODE
argocd-application-controller-0                     1/1     Running   0          37s   10.244.0.127   minikube
argocd-applicationset-controller-76fd8cdd4f-8vw74   1/1     Running   0          37s   10.244.0.124   minikube
argocd-dex-server-66c78cf887-jwkpw                  1/1     Running   0          37s   10.244.0.123   minikube
argocd-notifications-controller-7fb9868fd6-gf64x    1/1     Running   0          37s   10.244.0.122   minikube
argocd-redis-bdbdffcb4-dp9gx                        1/1     Running   0          37s   10.244.0.125   minikube
argocd-repo-server-d89c7967d-624lm                  1/1     Running   0          37s   10.244.0.126   minikube
argocd-server-776b7cdd4d-k54dw                      1/1     Running   0          37s   10.244.0.128   minikube
```

| Component | Job |
|-----------|-----|
| `application-controller` | the reconcile loop: compares desired (Git) against live (cluster) and syncs |
| `repo-server` | clones repos, renders Helm/Kustomize into plain manifests, caches the result |
| `server` | API and web UI, authentication, RBAC |
| `redis` | cache for rendered manifests and live state |
| `dex` | optional SSO/OIDC broker |
| `applicationset-controller` | generates many Applications from one template |
| `notifications-controller` | sends sync/health notifications outward |

Exposing the API on a NodePort inside the assigned range, and checking it from the node (the node IP
is not routable from macOS):

```bash
kubectl patch svc argocd-server -n argocd -p '{"spec":{"type":"NodePort","ports":[
  {"name":"http","port":80,"targetPort":8080,"nodePort":30201},
  {"name":"https","port":443,"targetPort":8080,"nodePort":30202}]}}'
minikube ssh -- curl -sk -I https://192.168.49.2:30202/
minikube ssh -- curl -sk https://192.168.49.2:30202/api/version
```

```text
NAME            TYPE       CLUSTER-IP       EXTERNAL-IP   PORT(S)                      AGE
argocd-server   NodePort   10.100.185.161   <none>        80:30201/TCP,443:30202/TCP   7m54s

HTTP/1.1 200 OK
Accept-Ranges: bytes
Content-Length: 788

{"Version":"v3.5.4"}
```

**On the admin password.** Argo CD generates an initial admin password into the
`argocd-initial-admin-secret` Secret. It is retrieved into a shell variable and used, but **it is
never printed into this README — every occurrence is redacted** and the raw value appears nowhere in
this repository:

```bash
ADMIN_PW=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)
TOKEN=$(... POST /api/v1/session with {"username":"admin","password":"<redacted>"} ...)
echo "login succeeded: JWT returned, ${#TOKEN} characters, redacted"
minikube ssh -- curl -sk https://192.168.49.2:30202/api/v1/applications -H "'Authorization: Bearer $TOKEN'"
```

```text
login succeeded: JWT returned, 257 characters, redacted

hw20-guestbook Synced Healthy https://github.com/argoproj/argocd-example-apps.git
```

The login genuinely succeeded — a 257-character JWT came back and then authenticated a real API call
listing the managed Application. Both the password and the token are redacted here. In production
that initial secret is deleted after the first login and SSO or a strong local password takes over.

The `argocd` CLI is not installed on this host, so every step in this task is driven with `kubectl`
against the `Application` CRD plus the Argo CD REST API. That is not a workaround — it is the more
honest demonstration, because it shows GitOps works through the Kubernetes API itself and needs no
special client.

## 3.5 The Application: pointing Argo CD at Git

```bash
cat gitops/application.yaml
```

```text
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: hw20-guestbook
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: hw20
  syncPolicy:
    automated:
      prune: true
      selfHeal: false
    syncOptions:
      - CreateNamespace=false
```

| Field | Meaning |
|-------|---------|
| `source.repoURL` / `path` / `targetRevision` | *where the truth lives*: this public repo, this directory, this revision |
| `destination` | *where it goes*: this cluster, namespace `hw20` |
| `automated` | sync without a human clicking Sync |
| `prune: true` | delete cluster objects when their manifest is removed from Git |
| `selfHeal: false` | **deliberately off to start with**, so drift can be observed before it is healed |
| `finalizers` | cascade-delete the managed resources when the Application is deleted |

`selfHeal: false` is the whole experimental design. With it on, drift is corrected in a couple of
seconds and there is nothing to photograph. With it off, Argo CD still *detects* drift and reports
`OutOfSync`, which is the state that proves detection and correction are two separate things.

```bash
kubectl apply -f gitops/application.yaml
```

```text
application.argoproj.io/hw20-guestbook created
```

First reconciliation, polled every 5 seconds:

```text
13:12:04Z  Synced  health=Progressing  revision=8088f4c0d970abb09e250248cc97e35623447cb5
13:12:09Z  Synced  health=Progressing  revision=8088f4c0d970abb09e250248cc97e35623447cb5
...
13:13:00Z  Synced  health=Progressing  revision=8088f4c0d970abb09e250248cc97e35623447cb5
```

```bash
kubectl get applications -n argocd -o custom-columns='NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,REVISION:.status.sync.revision,PATH:.spec.source.path,DEST-NS:.spec.destination.namespace'
kubectl get application hw20-guestbook -n argocd -o jsonpath='{range .status.resources[*]}{.kind}/{.name} in {.namespace} -> {.status}{"\n"}{end}'
```

```text
NAME             SYNC     HEALTH    REVISION                                   PATH        DEST-NS
hw20-guestbook   Synced   Healthy   8088f4c0d970abb09e250248cc97e35623447cb5   guestbook   hw20

Service/guestbook-ui in hw20 -> Synced
Deployment/guestbook-ui in hw20 -> Synced
```

`Sync` and `Health` are two different things and both matter: **Synced** means the cluster matches
Git; **Healthy** means the workload is actually working. A deployment can be perfectly Synced and
completely broken, which is why Argo CD tracks them separately. During the image pull above the app
was `Synced` but `Progressing` for nearly a minute — Git had been faithfully applied while the pod
was not yet serving.

```bash
kubectl get application hw20-guestbook -n argocd -o jsonpath='phase={.status.operationState.phase}{"\n"}message={.status.operationState.message}{"\n"}syncedRevision={.status.operationState.syncResult.revision}{"\n"}automated={.status.operationState.operation.initiatedBy.automated}{"\n"}'
kubectl get deploy,svc,pods -n hw20 | grep -E 'NAME|guestbook'
kubectl get deploy guestbook-ui -n hw20 -o jsonpath='{.metadata.annotations.argocd\.argoproj\.io/tracking-id}{"\n"}'
```

```text
phase=Succeeded
message=successfully synced (all tasks run)
syncedRevision=8088f4c0d970abb09e250248cc97e35623447cb5
automated=true

NAME                           READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/guestbook-ui   1/1     1            1           2m36s
NAME                   TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
service/guestbook-ui   ClusterIP   10.107.16.250   <none>        80/TCP         2m36s
NAME                                READY   STATUS    RESTARTS   AGE
pod/guestbook-ui-6d476cf4df-w95c4   1/1     Running   0          2m36s

hw20-guestbook:apps/Deployment:hw20/guestbook-ui
```

`automated=true` is the proof that nobody triggered this; the controller did it on its own after the
Application was created. The Deployment and Service exist in the cluster although they were never
applied from this machine — they were applied by Argo CD from commit `8088f4c0`. The tracking
annotation is how Argo CD knows which objects it owns, which is also what makes `prune` safe: it
only ever deletes resources carrying its own tracking id.

## 3.6 Continuous reconciliation, part 1 — drift detection

This is the centrepiece. Git says `replicas: 1`. Now break that rule the way it gets broken in real
life, with a hand-typed `kubectl scale` straight at production:

```bash
kubectl get deploy guestbook-ui -n hw20 -o custom-columns='NAME:.metadata.name,DESIRED:.spec.replicas,READY:.status.readyReplicas'
kubectl get application hw20-guestbook -n argocd -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'
kubectl scale deployment guestbook-ui -n hw20 --replicas=5
```

```text
=== BEFORE: cluster matches Git ===
13:14:45Z
NAME           DESIRED   READY
guestbook-ui   1         1
APP              SYNC     HEALTH
hw20-guestbook   Synced   Healthy

=== DRIFT: mutate live state by hand, exactly what GitOps forbids ===
deployment.apps/guestbook-ui scaled
13:14:46Z

=== Argo CD noticing the drift ===
13:14:46Z  deployment.spec.replicas=5  app.sync=Synced     app.health=Healthy
13:14:51Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:14:56Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:01Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:06Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:11Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:17Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:22Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:27Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:32Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:37Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:42Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:47Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:53Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:15:58Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:16:03Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:16:08Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
13:16:13Z  deployment.spec.replicas=5  app.sync=OutOfSync  app.health=Healthy
```

**Within 5 seconds** of the manual change, Argo CD flipped from `Synced` to `OutOfSync`. Note that
`Health` stayed `Healthy` the entire time — five replicas are perfectly healthy, they are just not
what Git asked for. Health and compliance are orthogonal, and a system that only watched health
would have seen nothing at all here.

Exactly which resource drifted:

```bash
kubectl get application hw20-guestbook -n argocd -o jsonpath='{range .status.resources[*]}{.kind}/{.name} -> {.status}{"\n"}{end}'
kubectl get pods -n hw20 -l app=guestbook-ui
```

```text
Service/guestbook-ui -> Synced
Deployment/guestbook-ui -> OutOfSync

comparedToRevision=8088f4c0d970abb09e250248cc97e35623447cb5
syncStatus=OutOfSync

NAME                            READY   STATUS    RESTARTS   AGE
guestbook-ui-6d476cf4df-79fm5   1/1     Running   0          100s
guestbook-ui-6d476cf4df-gmtgs   1/1     Running   0          100s
guestbook-ui-6d476cf4df-jvbzx   1/1     Running   0          100s
guestbook-ui-6d476cf4df-pf86p   1/1     Running   0          100s
guestbook-ui-6d476cf4df-w95c4   1/1     Running   0          4m24s
```

Resource-level granularity: the Service is still Synced, only the Deployment drifted, and it is
still being compared against the same Git revision `8088f4c0`. Five pods are genuinely running — the
drift is real, not a status artefact.

## 3.7 Continuous reconciliation, part 2 — self-healing

Now turn self-healing on, declaratively, by applying the second Application manifest:

```bash
diff gitops/application.yaml gitops/application-selfheal.yaml
kubectl apply -f gitops/application-selfheal.yaml
```

```text
20c20
<       selfHeal: false
---
>       selfHeal: true
application.argoproj.io/hw20-guestbook configured
13:16:32Z

=== Argo CD healing the drift without anybody asking it to ===
13:16:32Z  deployment.spec.replicas=5  running_pods=5  app.sync=OutOfSync
13:16:36Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:16:40Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:16:44Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:16:49Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:16:53Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:16:57Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:17:01Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:17:05Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:17:09Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:17:14Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:17:18Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:17:22Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:17:26Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
13:17:30Z  deployment.spec.replicas=1  running_pods=1  app.sync=Synced
```

**Four seconds.** The manual change was undone and four pods were terminated, with no human
intervention, because Git says `replicas: 1`. The operation Argo CD ran by itself:

```bash
kubectl get application hw20-guestbook -n argocd -o jsonpath='phase={.status.operationState.phase}{"\n"}message={.status.operationState.message}{"\n"}startedAt={.status.operationState.startedAt}{"\n"}finishedAt={.status.operationState.finishedAt}{"\n"}automated={.status.operationState.operation.initiatedBy.automated}{"\n"}'
```

```text
phase=Succeeded
message=successfully synced (all tasks run)
startedAt=2026-10-07T13:16:33Z
finishedAt=2026-10-07T13:16:33Z
automated=true
```

That is the complete drift-and-heal cycle, and it **is** GitOps:

| Stage | Time | `spec.replicas` | App sync status |
|-------|------|-----------------|-----------------|
| Before — cluster matches Git | 13:14:45 | 1 | `Synced` |
| Manual `kubectl scale --replicas=5` | 13:14:46 | 5 | `Synced` (not yet refreshed) |
| Drift detected | 13:14:51 | 5 | **`OutOfSync`** |
| Drift held, self-heal off | 13:14:51 - 13:16:32 | 5 | `OutOfSync` for 1m41s |
| Self-heal enabled | 13:16:32 | 5 | `OutOfSync` |
| **Reverted to the Git-declared state** | 13:16:36 | **1** | **`Synced`** |

### A harder test: delete the Deployment outright

Scaling is a field change. What about removing the object completely?

```bash
kubectl delete deployment guestbook-ui -n hw20
```

```text
deployment.apps "guestbook-ui" deleted from hw20 namespace
13:17:47Z
13:17:47Z  deployment: GONE                      app.sync=OutOfSync
13:17:52Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
13:17:57Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
13:18:02Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
13:18:07Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
13:18:12Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
13:18:17Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
13:18:22Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
13:18:27Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
13:18:32Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
13:18:38Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
13:18:43Z  deployment: guestbook-ui ready=1/1    app.sync=Synced
```

Gone at 13:17:47, back and serving at 13:17:52. **Five seconds from deletion to full recovery.**
Reconciliation is not a diff check that runs at deploy time — it is a continuous control loop. The
same mechanism that undoes a scale rebuilds a deleted object, and it is exactly what makes "rebuild
the cluster and re-point the agent" a credible disaster recovery plan.

## 3.8 The GitOps workflow

```text
  developer                  Git repository                  cluster
  ---------                  --------------                  -------
  1. edit manifest
     replicas: 1 -> 3
          |
  2. commit + push ------>  feature branch
          |                      |
  3. open pull request           |
          |                      v
  4. review + CI           checks pass (lint, policy, kubeconform, scan)
          |                      |
  5. merge -------------->  main branch == desired state
                                 |
                                 |  6. agent detects the new revision
                                 |     (webhook, or poll every 3 minutes)
                                 v
                           Argo CD repo-server renders manifests
                                 |
                                 |  7. application-controller diffs
                                 |     desired vs live
                                 v
                           8. apply the difference  ------>  Kubernetes
                                 |
                                 |  9. report Sync + Health status
                                 v
                           10. keep comparing, forever
                               any drift -> OutOfSync -> (selfHeal) -> corrected
```

Nothing in that loop ever pushes into the cluster from outside, and step 10 is the one most
descriptions leave out — the loop never terminates. A pipeline ends; a reconciler does not.

Note where this leaves CI/CD: **CI builds and tests the image and writes the new tag into the
manifest repo. CD is Argo CD pulling it.** The pipeline never needs cluster credentials. That
separation is a security property, not a stylistic preference.

## 3.9 Kubernetes + GitOps

Kubernetes is an unusually good fit for GitOps, for structural reasons:

| Kubernetes property | Why GitOps needs it |
|---------------------|--------------------|
| Every object is a declarative YAML document | the repo can hold the entire desired state |
| Controllers already run reconcile loops | GitOps is the same pattern one level up |
| `apply` is idempotent and server-side merges | re-applying unchanged state is a no-op |
| The API is uniform and typed | one agent can manage any resource kind, including CRDs |
| CRDs extend the model | `Application` and `ApplicationSet` are themselves Kubernetes objects |
| RBAC and namespaces | the agent's blast radius is constrained by the cluster's own rules |

Practical conventions that follow:

- **Separate the application repo from the manifest repo.** Code churn and deployment churn have
  different review requirements and different audiences.
- **One Application per environment**, with Kustomize overlays or Helm values per cluster. Dev, stage
  and prod differ by a diff, not by a different process.
- **Never commit plaintext Secrets.** Use Sealed Secrets, SOPS, or External Secrets Operator pulling
  from Vault or a cloud secret manager. A public manifest repo with a base64 password in it is not
  encrypted, it is encoded.
- **`prune: true` with care.** It is the half of GitOps that makes deletions real; it is also the
  half that deletes things if a path is mistyped. Argo CD's tracking id limits it to its own objects.
- **Expect to need escape hatches.** `ignoreDifferences` for fields a mutating webhook or an HPA
  owns, and `argocd.argoproj.io/sync-wave` for ordering, are needed in almost every real install.
- **The HPA caveat.** If something else legitimately owns `replicas` — an HPA — then `selfHeal` and
  the HPA will fight. The answer is to remove `replicas` from the manifest or add it to
  `ignoreDifferences`, not to turn self-healing off.

---

# Cleanup

Everything created by this lab is removed and the removal is verified. The shared cluster and the
shared LocalStack container are deliberately left running.

```bash
kubectl delete -f gitops/application-selfheal.yaml --timeout=120s
kubectl get deploy,svc -n hw20 | grep guestbook || echo "no guestbook resources left in hw20"
```

```text
application.argoproj.io "hw20-guestbook" deleted from argocd namespace

no guestbook resources left in hw20
```

Deleting the Application removed the Deployment and Service too, because of the
`resources-finalizer.argocd.argoproj.io` finalizer. That is GitOps deletion semantics: remove the
declaration, the resources go with it.

```bash
kubectl delete -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml --ignore-not-found
kubectl delete namespace argocd --timeout=300s
kubectl delete crd applications.argoproj.io applicationsets.argoproj.io appprojects.argoproj.io --ignore-not-found
kubectl delete namespace hw20 --timeout=300s
```

```text
--- 3. uninstall Argo CD
networkpolicy.networking.k8s.io "argocd-notifications-controller-network-policy" deleted from argocd namespace
networkpolicy.networking.k8s.io "argocd-redis-network-policy" deleted from argocd namespace
networkpolicy.networking.k8s.io "argocd-repo-server-network-policy" deleted from argocd namespace
networkpolicy.networking.k8s.io "argocd-server-network-policy" deleted from argocd namespace

--- 4. delete the argocd namespace
namespace "argocd" deleted

--- 5. delete the Argo CD CustomResourceDefinitions

--- 6. delete my Kubernetes namespace
namespace "hw20" deleted
```

Step 5 printed nothing because the CRDs were already gone — `install.yaml` contains them, so the
`kubectl delete -f` in step 3 removed them along with the ClusterRoles and ClusterRoleBindings.

```bash
docker compose -p hw20 -f monitoring/docker-compose.yml -f observability/docker-compose.yml down -v
```

```text
 Container hw20-alertmanager Removed 
 Container hw20-node-exporter Removed 
 Container hw20-jaeger Removed 
 Container hw20-grafana Removed 
 Container hw20-prometheus Removed 
 Volume hw20-prometheus-data Removed 
 Volume hw20-grafana-data Removed 
 Network hw20-net Removed 
```

Verification, which is the part that actually matters:

```bash
docker ps -a --filter name=hw20- --format '{{.Names}}'
docker network ls --filter name=hw20 --format '{{.Name}}'
docker volume ls --filter name=hw20 --format '{{.Name}}'
kubectl get ns
kubectl get crd | grep argoproj || echo "no argoproj CRDs remain"
kubectl get clusterrole,clusterrolebinding | grep argocd || echo "no argocd cluster-scoped RBAC remains"
docker ps --filter name=localstack-main --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
kubectl get nodes
for p in 9090 9093 9100 13000 16686 4318; do printf "%s: " $p; lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1 && echo IN-USE || echo free; done
```

```text
--- 8. verification: no hw20 containers, networks or volumes remain
containers: 0
networks:   0
volumes:    0

--- 9. verification: namespaces gone, no Argo CD left behind
NAME              STATUS   AGE
default           Active   19d
hw13              Active   56m
ingress-nginx     Active   19d
kube-node-lease   Active   19d
kube-public       Active   19d
kube-system       Active   19d

no argoproj CRDs remain
no argocd cluster-scoped RBAC remains

--- 10. verification: shared infrastructure untouched and still running
localstack-main	localstack/localstack:3.8	Up About an hour (healthy)
minikube	Up About an hour
NAME       STATUS   ROLES           AGE   VERSION
minikube   Ready    control-plane   19d   v1.37.0

--- 11. verification: the host ports this lab used are free again
9090: free
9093: free
9100: free
13000: free
16686: free
4318: free
```

Zero hw20 containers, networks and volumes. Both `hw20` and `argocd` namespaces are gone, along with
every cluster-scoped object Argo CD installed. The cluster node is still `Ready`, LocalStack is
still healthy, and all six host ports are released. No bulk prune was used at any point — only the
compose project and explicitly named resources were removed.

---

# What was proved, and what was not

| Claim | Evidence | Section |
|-------|----------|---------|
| Prometheus scrapes real targets | 4 active targets, all `up`, no scrape errors | 1.3 |
| Metrics are real, not mocked | raw `/api/v1/query` JSON with timestamps and labels | 1.4 |
| CPU utilisation measured | 10.5% total, per-mode breakdown summing to 100 | 1.5 |
| Memory utilisation measured | 7935 MB total / 5144 MB available / 35.2% used | 1.6 |
| An alert actually fires | `TargetDown`: inactive → pending (13:02:10) → firing (13:02:25) | 1.8 |
| Alerts reach Alertmanager | `/api/v2/alerts` shows the alert active with rendered annotations | 1.9 |
| Alerts resolve by themselves | firing → none within 8 seconds of the target returning | 1.10 |
| A second, load-driven alert fires | `PrometheusHighQueryLoad` at a measured 7.4 req/s | 1.11 |
| Grafana is wired up and serving data | `/api/health`, provisioned datasource `readOnly=true`, `/api/ds/query` returning real values | 1.12 |
| Kubernetes CPU/memory | `kubectl top`, busy-loop pod throttled to exactly its 300m limit | 1.13 |
| Application health gating | 404 probe → `ready=false` in EndpointSlice, 3 restarts, stalled rollout | 1.14 |
| A real distributed trace exists | 3 spans across 2 services stored in and read back from Jaeger | 2.2 |
| The pillars correlate | the same trace id in both the application log and the trace | 2.2 |
| Argo CD syncs from Git | `Synced`/`Healthy` at revision `8088f4c0`, `automated=true` | 3.5 |
| Drift is detected | manual scale to 5 → `OutOfSync` within 5 seconds | 3.6 |
| Drift is healed | reverted to the Git-declared 1 replica within 4 seconds | 3.7 |
| Deleted objects are restored | Deployment deleted 13:17:47, back and ready 13:17:52 | 3.7 |
| Everything is cleaned up | 0 containers, 0 networks, 0 volumes, 0 namespaces, ports free | Cleanup |

**Not proved, stated honestly:**

- **No Grafana dashboard screenshot.** This was run headlessly with no browser or display. Server-side
  PNG rendering needs the separate Grafana image-renderer plugin, which was not installed. Everything
  a screenshot would evidence is captured through the Grafana API instead, including the
  `/api/ds/query` call a panel makes when it renders (section 1.12).
- **No Argo CD web UI screenshot**, for the same reason. The UI was verified to answer with HTTP 200
  and the API was exercised with a real authenticated token (section 3.4).
- **The trace was emitted by a script, not by instrumented application code.** Writing, building and
  deploying an OpenTelemetry-instrumented service was out of scope for the time available. The
  payload is genuine OTLP, the transport is genuine OTLP/HTTP, and Jaeger genuinely stored and
  returned it — but the spans describe a scenario rather than a request that really traversed a real
  payment gateway.
- **node-exporter reports the Docker Desktop VM, not macOS.** Containers on this host run inside a
  Linux VM, so those are the numbers that matter for the containers, but they are not macOS's own.
- **The Git repository used for the GitOps demo is `argoproj/argocd-example-apps`**, a public
  upstream repo, because nothing may be pushed to a repository from this environment. The
  reconciliation loop is identical with a private repo; only the credentials differ.
- **The `argocd` CLI is not installed** on this host, so everything was driven through `kubectl` and
  the Argo CD REST API.

---

# Interview questions

**1. What is the difference between monitoring and observability?**
Monitoring tells you *that* something is wrong by watching signals you chose in advance; it handles
known unknowns. Observability is the property that lets you work out *why*, by asking new questions
of rich, high-cardinality data at query time — it handles unknown unknowns. Monitoring produces the
page, observability shortens the time from page to fix. You need both.

**2. What are the three pillars of observability?**
Metrics (cheap aggregated numbers over time, good for alerting and dashboards), logs (discrete
timestamped events with full detail, good for root cause), traces (one request's path across
services, good for finding which hop owns the latency). They are only genuinely useful when
correlated — section 2.2 shows the same trace id present in both a log line and the stored trace.

**3. Why is `rate()` required for CPU in Prometheus?**
`node_cpu_seconds_total` is a counter of cumulative seconds per core per mode, so its raw value is
meaningless. `rate()` gives seconds-of-CPU per second, which is utilisation, and it handles counter
resets on process restart correctly. Use `rate()` for slow-moving counters and `irate()` only for
fast, spiky ones you are graphing at high resolution.

**4. What does `for:` do in an alerting rule, and why does it matter?**
It is the holding period: the condition must stay true for that long before the alert moves from
`pending` to `firing`. It suppresses flapping from single failed scrapes, deploy restarts and GC
pauses. Section 1.8 captures all of it, including `HostHighCpuUsage` going `pending` at 85.5% CPU
and never firing because the spike subsided inside its one-minute window — exactly the false page
`for:` exists to prevent.

**5. What is the difference between a liveness probe and a readiness probe?**
Readiness controls traffic: a failing readiness probe removes the pod from Service endpoints but
leaves it running. Liveness controls lifecycle: a failing liveness probe makes the kubelet kill and
restart the container. Section 1.14 shows both from one 404 — the pod went `ready=false` in the
EndpointSlice *and* restarted three times. A common production mistake is pointing liveness at a
check that depends on a downstream database; when that database blips, every replica restarts at
once and you convert a dependency problem into an outage.

**6. Why did the rollout stall in section 1.14, and is that good?**
Because the deployment only promotes replicas that pass readiness, and the new pod never did. It is
good: the two healthy old pods kept serving while the bad revision got stuck. An honest readiness
probe turns a bad deploy into a stalled rollout rather than an outage — but only if the probe
actually reflects whether the application can serve.

**7. Why `MemAvailable` instead of `MemFree`?**
Linux uses otherwise-idle memory for page cache, so `MemFree` looks alarmingly low on any healthy
busy machine. `MemAvailable` is the kernel's own estimate of what a new process could obtain
including reclaimable cache. Alerting on `MemFree` produces constant false positives.

**8. Why does `kubectl top` show the busy-loop pod at exactly 300m?**
Because 300m is its CPU limit and the kernel CFS quota throttles it there. Worth stating the
asymmetry: exceeding a CPU limit throttles the container, exceeding a memory limit OOMKills it.
That is why CPU limits are often set generously or omitted while memory limits are set carefully.

**9. `metrics-server` or Prometheus — which do I need?**
Both, for different jobs. `metrics-server` keeps only the latest sample in memory to serve the
Metrics API for `kubectl top` and the HPA; it has no history and no PromQL. Prometheus scrapes
cAdvisor and kube-state-metrics and keeps history you can query and alert on. Neither replaces the
other.

**10. What is GitOps in one sentence?**
A Git repository holds the declarative desired state, and an agent inside the cluster continuously
pulls that state and reconciles reality to match it.

**11. Why is the pull model more secure than pushing with `kubectl` from CI?**
Nothing outside the cluster needs cluster credentials. CI only needs write access to a Git
repository; the agent reaches out from inside. That removes long-lived kubeconfigs from CI systems —
historically one of the juicier targets in a software supply chain.

**12. What is the difference between `Synced` and `Healthy` in Argo CD?**
`Synced` means live state matches Git. `Healthy` means the workload is actually working. They are
independent: during the first sync the app was `Synced` but `Progressing` while an image pulled, and
during the drift test it was `OutOfSync` but `Healthy` — five replicas work fine, they are just not
what Git asked for.

**13. What is the difference between auto-sync and self-heal?**
Auto-sync reacts to changes in *Git*: a new commit is applied without a human clicking Sync.
Self-heal reacts to changes in the *cluster*: hand-made drift is reverted. Section 3.6 ran with
`selfHeal: false` on purpose — Argo CD detected the drift in 5 seconds and reported `OutOfSync`, but
left it alone. Only when `selfHeal: true` was applied did it revert, in 4 seconds. Detection and
correction are separate decisions.

**14. What does `prune: true` do and when is it dangerous?**
It deletes cluster resources whose manifests have been removed from Git, which is what makes
deletions real rather than accumulating orphans forever. It is dangerous if a path is mistyped or a
rendering step silently produces nothing, because "no manifests" then means "delete everything".
Argo CD limits the blast radius with the `argocd.argoproj.io/tracking-id` annotation, so it only
prunes objects it owns.

**15. How do you handle Secrets in a GitOps repo?**
Never in plaintext, and base64 is not encryption. Use Sealed Secrets (encrypted with a cluster
public key, only the in-cluster controller can decrypt), SOPS with age or KMS, or the External
Secrets Operator, which keeps the material in Vault or a cloud secret manager and syncs it in. The
repo then holds a reference or ciphertext, never the value.

**16. The HPA scales a deployment, but Git says `replicas: 2`. What happens?**
Argo CD and the HPA fight: the HPA scales up, self-heal scales back down. The fix is to stop
declaring `replicas` in the manifest — let the HPA own it — or to add that field to
`ignoreDifferences`. Turning self-healing off to work around it throws away the main benefit.

**17. How does Argo CD know a resource belongs to it?**
By a tracking id written onto every managed object. Here:
`hw20-guestbook:apps/Deployment:hw20/guestbook-ui`. That is what lets several Applications and
hand-made resources coexist in one namespace, and what keeps `prune` from touching anything Argo CD
did not create.

**18. Why did `kubectl apply` fail on the Argo CD install, and what fixed it?**
Client-side apply stores the full previous manifest in the
`kubectl.kubernetes.io/last-applied-configuration` annotation, and the ApplicationSet CRD exceeds
the 256 KB annotation limit. `kubectl apply --server-side=true` moves field ownership tracking into
the API server, so no oversized annotation is written. This is the most common Argo CD install
error there is.

**19. What does a trace give you that logs and metrics cannot?**
Causal structure and time attribution across service boundaries. In section 2.2 the metric said
latency was up and the log said "payment gateway timeout", but only the trace showed that of 3400 ms
total, 820 ms was the inventory lookup and 3200 ms was `charge.card` in a different service
returning 504 after 2 retries. Without it you are guessing which service to open first.

**20. How would you take this lab to production?**
Replace the hand-rolled compose stack with `kube-prometheus-stack` (Prometheus Operator,
`ServiceMonitor` CRDs, Alertmanager, Grafana, kube-state-metrics, node-exporter) installed by Helm —
and install it *through* Argo CD, so the monitoring system is itself under GitOps. Add Loki plus a
Fluent Bit DaemonSet for logs, an OpenTelemetry Collector plus Tempo or Jaeger with tail-based
sampling for traces, and Thanos or Mimir for long-term metric storage. Point Alertmanager at
PagerDuty. Write alerts against SLOs and error budgets rather than raw resource thresholds, split
the manifest repo from the application repo, enforce branch protection, and manage Secrets with
External Secrets or SOPS.
