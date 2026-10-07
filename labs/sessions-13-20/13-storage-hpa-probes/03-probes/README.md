# Probes — readiness, liveness, startup

`STATUS: Running` only means the container process exists. It says nothing about whether the
application inside it can serve a request. Probes are how the kubelet asks.

All output below is real, captured in namespace `hw13` on minikube (Kubernetes v1.37.0).

---

## The three probes in one table

| Probe | The question it asks | Who reacts | What happens on failure |
| :--- | :--- | :--- | :--- |
| **startupProbe** | "Have you finished booting?" | kubelet | Container is killed and restarted. While it is running, liveness and readiness are **suspended**. |
| **readinessProbe** | "Can I send you user traffic?" | endpoints controller / kube-proxy | Pod IP is removed from the Service's EndpointSlice. The container is **not** restarted. |
| **livenessProbe** | "Are you still alive?" | kubelet | Container is killed and restarted. The Pod object stays, the Pod IP stays. |

The single most important distinction: **a readiness failure never restarts anything.** A liveness
failure always does. Proven below with real restart counters.

Four probe mechanisms exist: `httpGet` (2xx/3xx is a pass), `tcpSocket` (connection opens), `exec`
(exit code 0) and `grpc`. The examples here use `httpGet` because the failure mode is visible in the
events.

Shared tuning fields:

| Field | Default | Meaning |
| :--- | :--- | :--- |
| `initialDelaySeconds` | 0 | Wait this long after the container starts before the first check |
| `periodSeconds` | 10 | How often to check |
| `timeoutSeconds` | 1 | How long to wait for a response before counting a failure |
| `failureThreshold` | 3 | Consecutive failures before the probe is declared failed |
| `successThreshold` | 1 | Consecutive successes before a failed probe is healthy again (must be 1 for liveness/startup) |

---

## 1. Readiness — pulling a Pod out of the Service

### The trick that makes this demonstrable

A probe is immutable on a running Pod, so "break the probe" cannot mean "edit the YAML". Instead the
probe points at a file the container serves, and the file is deleted at runtime:

```yaml
          lifecycle:
            postStart:
              exec:
                command:
                  - sh
                  - -c
                  - "echo ok > /usr/share/nginx/html/healthz"
          readinessProbe:
            httpGet:
              path: /healthz
              port: 80
            initialDelaySeconds: 2
            periodSeconds: 3
            timeoutSeconds: 1
            failureThreshold: 2
```

`postStart` writes `/healthz` when the container starts, so the Pod comes up healthy. Deleting that
one file turns the probe into a 404 while nginx itself keeps running perfectly — exactly the
"process is up, application is broken" case probes exist for.

### Healthy state: two Pods, two endpoints

```bash
kubectl apply -f 01-readiness-deployment.yaml -f 02-readiness-service.yaml
kubectl rollout status deploy/readiness-demo -n hw13 --timeout=120s
kubectl get pods -n hw13 -o wide
kubectl get endpoints readiness-service -n hw13
```

```text
deployment.apps/readiness-demo created
service/readiness-service created
Waiting for deployment "readiness-demo" rollout to finish: 0 of 2 updated replicas are available...
Waiting for deployment "readiness-demo" rollout to finish: 1 of 2 updated replicas are available...
deployment "readiness-demo" successfully rolled out
NAME                             READY   STATUS    RESTARTS   AGE   IP             NODE       NOMINATED NODE   READINESS GATES
readiness-demo-676789996-gqthr   1/1     Running   0          4s    10.244.0.118   minikube   <none>           <none>
readiness-demo-676789996-t6kkn   1/1     Running   0          4s    10.244.0.117   minikube   <none>           <none>
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME                ENDPOINTS                         AGE
readiness-service   10.244.0.117:80,10.244.0.118:80   12s
```

Both Pod IPs are in the Service. `READY 1/1` on both.

### Break readiness on exactly one Pod

```bash
kubectl exec -n hw13 readiness-demo-676789996-gqthr -- rm /usr/share/nginx/html/healthz
sleep 12
kubectl get pods -n hw13 -o wide
kubectl get endpoints readiness-service -n hw13
```

```text
=== breaking readiness on readiness-demo-676789996-gqthr at 13:08:18 UTC ===
NAME                             READY   STATUS    RESTARTS   AGE   IP             NODE       NOMINATED NODE   READINESS GATES
readiness-demo-676789996-gqthr   0/1     Running   0          24s   10.244.0.118   minikube   <none>           <none>
readiness-demo-676789996-t6kkn   1/1     Running   0          24s   10.244.0.117   minikube   <none>           <none>
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME                ENDPOINTS         AGE
readiness-service   10.244.0.117:80   24s
```

Three things to read off that output at once:

1. `STATUS` is still `Running` — Kubernetes did not consider this a crash.
2. `READY` went `1/1 -> 0/1`.
3. `RESTARTS` is still `0`. **Readiness did not restart anything.**
4. `10.244.0.118` is gone from the Service endpoints. Traffic now goes only to the healthy Pod.

The EndpointSlice shows the same thing with more detail — the address is still listed, but marked
not ready, which is how kube-proxy knows to skip it:

```bash
kubectl get endpointslices -n hw13 -l kubernetes.io/service-name=readiness-service \
  -o custom-columns='NAME:.metadata.name,ADDRESSES:.endpoints[*].addresses,READY:.endpoints[*].conditions.ready'
```

```text
NAME                      ADDRESSES                       READY
readiness-service-8hf7s   [10.244.0.118],[10.244.0.117]   false,true
```

The Pod's own condition list:

```bash
kubectl get pod readiness-demo-676789996-gqthr -n hw13 \
  -o jsonpath='{range .status.conditions[*]}{.type}={.status}{"\n"}{end}'
```

```text
PodReadyToStartContainers=True
Initialized=True
Ready=False
ContainersReady=False
PodScheduled=True
```

And the event that caused it:

```bash
kubectl describe pod readiness-demo-676789996-gqthr -n hw13 | tail -8
```

```text
Events:
  Type     Reason     Age               From               Message
  ----     ------     ----              ----               -------
  Normal   Scheduled  24s               default-scheduler  Successfully assigned hw13/readiness-demo-676789996-gqthr to minikube
  Normal   Pulled     23s               kubelet            spec.containers{web}: Container image "nginx:1.27" already present on machine and can be accessed by the pod
  Normal   Created    23s               kubelet            spec.containers{web}: Container created
  Normal   Started    23s               kubelet            spec.containers{web}: Container started
  Warning  Unhealthy  2s (x5 over 11s)  kubelet            spec.containers{web}: Readiness probe failed: HTTP probe failed with statuscode: 404
```

### Readiness recovers on its own

```bash
kubectl exec -n hw13 readiness-demo-676789996-gqthr -- sh -c 'echo ok > /usr/share/nginx/html/healthz'
sleep 10
kubectl get pods -n hw13 -o wide
kubectl get endpoints readiness-service -n hw13
```

```text
=== restoring /healthz at 13:08:39 UTC ===
NAME                             READY   STATUS    RESTARTS   AGE   IP             NODE       NOMINATED NODE   READINESS GATES
readiness-demo-676789996-gqthr   1/1     Running   0          43s   10.244.0.118   minikube   <none>           <none>
readiness-demo-676789996-t6kkn   1/1     Running   0          43s   10.244.0.117   minikube   <none>           <none>
NAME                ENDPOINTS                         AGE
readiness-service   10.244.0.117:80,10.244.0.118:80   43s
```

Back in the Service within one probe period, and `RESTARTS` is **still 0** across the whole episode.
That is the entire point: readiness is a reversible traffic gate, not a kill switch. Use it for a
dependency that is temporarily unavailable, a cache that is still warming, or a Pod that is draining
before shutdown.

---

## 2. Liveness — restarting a stuck container

Same mechanism, different probe field:

```yaml
      livenessProbe:
        httpGet:
          path: /healthz
          port: 80
        initialDelaySeconds: 5
        periodSeconds: 5
        timeoutSeconds: 2
        failureThreshold: 3
```

`periodSeconds: 5 × failureThreshold: 3` means the container is killed roughly 15 seconds after the
application stops answering.

```bash
kubectl apply -f 03-liveness-pod.yaml
kubectl wait --for=condition=Ready pod/liveness-demo -n hw13 --timeout=90s
kubectl exec -n hw13 liveness-demo -- rm /usr/share/nginx/html/healthz
for i in $(seq 1 8); do printf '%s  ' "$(date -u +%H:%M:%S)"; kubectl get pod liveness-demo -n hw13 --no-headers; sleep 10; done
```

```text
pod/liveness-demo created
pod/liveness-demo condition met
=== breaking liveness at 13:08:54 UTC ===
13:08:54  liveness-demo   1/1   Running   0     0s
13:09:04  liveness-demo   1/1   Running   0     10s
13:09:15  liveness-demo   1/1   Running   1 (6s ago)   21s
13:09:25  liveness-demo   1/1   Running   1 (16s ago)   31s
13:09:35  liveness-demo   1/1   Running   1 (26s ago)   41s
13:09:45  liveness-demo   1/1   Running   1 (36s ago)   51s
13:09:55  liveness-demo   1/1   Running   1 (46s ago)   61s
13:10:05  liveness-demo   1/1   Running   1 (56s ago)   71s
```

`RESTARTS 0 -> 1` at 13:09:15, roughly 15 seconds after the file was removed at 13:08:54 — exactly
`periodSeconds × failureThreshold`. Compare with the readiness run, where the counter never moved.

The container state confirms a real kill and restart:

```bash
kubectl describe pod liveness-demo -n hw13 | sed -n '/Containers:/,/Conditions:/p'
```

```text
Containers:
  web:
    Container ID:   containerd://7e3debaf04a8d09d6cf84c8a4d4e89d919191d9ff56b34332a92feda54eec25f
    Image:          nginx:1.27
    Image ID:       docker.io/library/nginx@sha256:6784fb0834aa7dbbe12e3d7471e69c290df3e6ba810dc38b34ae33d3c1c05f7d
    Port:           80/TCP
    Host Port:      0/TCP
    State:          Running
      Started:      Wed, 07 Oct 2026 18:39:09 +0530
    Last State:     Terminated
      Reason:       Completed
      Exit Code:    0
      Started:      Wed, 07 Oct 2026 18:38:54 +0530
      Finished:     Wed, 07 Oct 2026 18:39:09 +0530
    Ready:          True
    Restart Count:  1
    Liveness:       http-get http://:80/healthz delay=5s timeout=2s period=5s successThreshold=1 failureThreshold=3
```

`Last State: Terminated` with `Started 18:38:54 / Finished 18:39:09` — the first container lived 15
seconds after the probe started failing. The new `Container ID` is a different container entirely.

```bash
kubectl describe pod liveness-demo -n hw13 | sed -n '/^Events:/,$p'
```

```text
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  84s                default-scheduler  Successfully assigned hw13/liveness-demo to minikube
  Normal   Pulled     69s (x2 over 84s)  kubelet            spec.containers{web}: Container image "nginx:1.27" already present on machine and can be accessed by the pod
  Normal   Created    69s (x2 over 84s)  kubelet            spec.containers{web}: Container created
  Normal   Started    69s (x2 over 84s)  kubelet            spec.containers{web}: Container started
  Warning  Unhealthy  69s (x3 over 79s)  kubelet            spec.containers{web}: Liveness probe failed: HTTP probe failed with statuscode: 404
  Normal   Killing    69s                kubelet            spec.containers{web}: Container web failed liveness probe, will be restarted
```

`Unhealthy ... (x3 ...)` then `Killing ... failed liveness probe, will be restarted` is the exact
audit trail. `(x2 over 84s)` on `Created`/`Started` shows the container was built twice.

The restart counter stopped at 1 because `postStart` recreates `/healthz` on every container start —
the restart genuinely repaired the fault. A real stuck process would keep failing and the Pod would
go to `CrashLoopBackOff` with the backoff doubling 10s, 20s, 40s … up to 5 minutes.

### Why liveness probes are dangerous

A liveness probe that calls a database, or shares a thread pool with request handling, will fail
under load — and then Kubernetes restarts every replica at exactly the moment the system is busiest,
turning a slowdown into an outage. Rules worth following:

- Liveness should test only "is this process wedged", never "are my dependencies up". Dependencies
  belong in **readiness**.
- Give it a generous `failureThreshold` and `timeoutSeconds`.
- If you are not sure you need one, do not add one. A missing liveness probe costs you an automatic
  restart; a bad one costs you an outage.

---

## 3. Startup — protecting a slow boot

The problem: an application that needs 40 seconds to start, behind a liveness probe tuned for a
healthy application (`periodSeconds: 5`, `failureThreshold: 3` = a 15-second patience). The liveness
probe kills it before it can ever finish booting.

`04-slow-app-no-startup-probe.yaml` reproduces that exactly:

```yaml
      command:
        - sh
        - -c
        - "mkdir -p /www && echo ok > /www/index.html && sleep 40 && httpd -f -p 8080 -h /www"
      livenessProbe:
        httpGet:
          path: /
          port: 8080
        initialDelaySeconds: 5
        periodSeconds: 5
        timeoutSeconds: 2
        failureThreshold: 3
```

`05-slow-app-with-startup-probe.yaml` is byte-for-byte the same container, plus:

```yaml
      startupProbe:
        httpGet:
          path: /
          port: 8080
        periodSeconds: 3
        failureThreshold: 30
```

`3s × 30 = 90 seconds` of boot time allowed. Both were applied at the same moment:

```bash
kubectl apply -f 04-slow-app-no-startup-probe.yaml -f 05-slow-app-with-startup-probe.yaml
for i in $(seq 1 10); do printf '%s  ' "$(date -u +%H:%M:%S)"; kubectl get pods -n hw13 --no-headers | grep slow | tr '\n' '|'; echo; sleep 15; done
```

```text
pod/slow-no-startup created
pod/slow-with-startup created
13:10:24  slow-no-startup                  0/1   ContainerCreating   0             0s|slow-with-startup                0/1   ContainerCreating   0             0s|
13:10:39  slow-no-startup                  1/1   Running   0             15s|slow-with-startup                0/1   Running   0             15s|
13:10:54  slow-no-startup                  1/1   Running   0              30s|slow-with-startup                0/1   Running   0              30s|
13:11:09  slow-no-startup                  1/1   Running   1 (0s ago)   45s|slow-with-startup                1/1   Running   0            45s|
13:11:24  slow-no-startup                  1/1   Running   1 (16s ago)     61s|slow-with-startup                1/1   Running   0               61s|
13:11:40  slow-no-startup                  1/1   Running   1 (31s ago)     76s|slow-with-startup                1/1   Running   0               76s|
13:11:55  slow-no-startup                  1/1   Running   2 (1s ago)      91s|slow-with-startup                1/1   Running   0               91s|
13:12:10  slow-no-startup                  1/1   Running   2 (16s ago)    106s|slow-with-startup                1/1   Running   0              106s|
13:12:25  slow-no-startup                  1/1   Running   2 (31s ago)     2m1s|slow-with-startup                1/1   Running   0               2m1s|
13:12:40  slow-no-startup                  1/1   Running   3 (1s ago)      2m16s|slow-with-startup                1/1   Running   0               2m16s|
```

Two different fates from one difference in the manifest:

- **`slow-no-startup`** restarts every ~45 seconds — 3 restarts in 2m16s — and never gets past the
  `sleep 40`. It is in an infinite boot loop caused entirely by its own health check.
- **`slow-with-startup`** goes `0/1 -> 1/1` at 13:11:09 (45 seconds, matching the 40-second sleep)
  with **0 restarts**, and stays there.

```bash
kubectl describe pod slow-no-startup -n hw13 | sed -n '/^Events:/,$p'
```

```text
Events:
  Type     Reason     Age                  From               Message
  ----     ------     ----                 ----               -------
  Normal   Scheduled  2m39s                default-scheduler  Successfully assigned hw13/slow-no-startup to minikube
  Normal   Pulled     24s (x4 over 2m39s)  kubelet            spec.containers{slow}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Normal   Created    24s (x4 over 2m39s)  kubelet            spec.containers{slow}: Container created
  Normal   Started    24s (x4 over 2m39s)  kubelet            spec.containers{slow}: Container started
  Warning  Unhealthy  9s (x12 over 2m34s)  kubelet            spec.containers{slow}: Liveness probe failed: Get "http://10.244.0.120:8080/": dial tcp 10.244.0.120:8080: connect: connection refused
  Normal   Killing    9s (x4 over 2m24s)   kubelet            spec.containers{slow}: Container slow failed liveness probe, will be restarted
```

```bash
kubectl describe pod slow-with-startup -n hw13 | sed -n '/^Events:/,$p'
```

```text
Events:
  Type     Reason     Age                  From               Message
  ----     ------     ----                 ----               -------
  Normal   Scheduled  2m39s                default-scheduler  Successfully assigned hw13/slow-with-startup to minikube
  Normal   Pulled     2m39s                kubelet            spec.containers{slow}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Normal   Created    2m39s                kubelet            spec.containers{slow}: Container created
  Normal   Started    2m39s                kubelet            spec.containers{slow}: Container started
  Warning  Unhealthy  2m (x13 over 2m36s)  kubelet            spec.containers{slow}: Startup probe failed: Get "http://10.244.0.121:8080/": dial tcp 10.244.0.121:8080: connect: connection refused
```

The second Pod also logged 13 failures — but as `Startup probe failed`, not `Liveness probe failed`,
and there is no `Killing` event. 13 of its 30 allowed attempts were used, then the startup probe
passed and the kubelet handed control to liveness and readiness.

```bash
kubectl describe pod slow-with-startup -n hw13 | grep -E 'Liveness|Readiness|Startup'
```

```text
    Liveness:       http-get http://:8080/ delay=0s timeout=2s period=5s successThreshold=1 failureThreshold=3
    Readiness:      http-get http://:8080/ delay=0s timeout=1s period=5s successThreshold=1 failureThreshold=3
    Startup:        http-get http://:8080/ delay=0s timeout=1s period=3s successThreshold=1 failureThreshold=30
```

### Why `startupProbe` beats a large `initialDelaySeconds`

`initialDelaySeconds: 90` on the liveness probe would also stop the restart loop, but it is a worse
answer: it is a fixed delay applied to **every** restart for the life of the Pod, so a container that
wedges in minute two is left broken for 90 seconds before anyone notices. A startup probe adapts —
it hands over the moment the application answers, and from then on liveness runs at its tight
5-second cadence.

Side note visible in the table above: `slow-no-startup` reports `READY 1/1` while its application is
not even listening. It has no readiness probe, so Kubernetes has nothing to judge it on. A container
with no readiness probe is Ready the instant it starts.

---

## 4. Putting the three together

```text
container starts
      │
      ├── startupProbe running ──────────> readiness and liveness are SUSPENDED
      │        │
      │        ├── fails failureThreshold times ──> container killed and restarted
      │        └── passes once ──────────────────┐
      │                                          │
      ▼                                          ▼
   (no startupProbe: both start immediately)   handover
                                                 │
            ┌────────────────────────────────────┴───────────────────────────────┐
            ▼                                                                    ▼
      readinessProbe                                                       livenessProbe
      fail -> Pod removed from Service EndpointSlice, container untouched   fail -> container killed and restarted
      pass -> Pod back in the Service                                       pass -> nothing happens
```

A sane default for an HTTP service:

```yaml
startupProbe:
  httpGet: { path: /healthz, port: 8080 }
  periodSeconds: 5
  failureThreshold: 30          # 150s of boot time, then give up
readinessProbe:
  httpGet: { path: /ready, port: 8080 }    # checks dependencies too
  periodSeconds: 5
  failureThreshold: 2           # leave the Service quickly
livenessProbe:
  httpGet: { path: /healthz, port: 8080 }  # process health ONLY
  periodSeconds: 10
  failureThreshold: 3           # be slow to kill
```

Two different endpoints matter: `/healthz` answers "my process is not wedged" and must never touch a
database; `/ready` answers "I can serve a real request" and may.

---

## Manifests in this folder

| File | Purpose |
| :--- | :--- |
| `01-readiness-deployment.yaml` | 2 nginx replicas, readiness `httpGet /healthz`, `postStart` creates the file |
| `02-readiness-service.yaml` | ClusterIP Service used to observe endpoint removal |
| `03-liveness-pod.yaml` | Same pattern with a liveness probe — deleting the file causes a restart |
| `04-slow-app-no-startup-probe.yaml` | 40-second boot behind a tight liveness probe: permanent restart loop |
| `05-slow-app-with-startup-probe.yaml` | Identical container plus a startup probe: starts cleanly, 0 restarts |

## References

- Probes — https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-probes
- Configure probes — https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
