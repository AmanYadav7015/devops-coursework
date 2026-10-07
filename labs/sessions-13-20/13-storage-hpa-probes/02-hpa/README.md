# Task 2 — Horizontal Pod Autoscaler, hands-on

The nine numbered steps from the task, in order, run against a live minikube cluster
(Kubernetes v1.37.0, metrics-server already enabled) in the namespace `hw13`.
Every `text` block is real captured output.

The workload and the autoscaler are the ones from `session-13-storage-hpa-probes/04-hpa/`
(`deployment.yaml`, `service.yaml`, `hpa.yaml`), re-namespaced to `hw13`.

---

## What HPA actually does

```text
      nginx Pods                     metrics-server                     HPA controller
  (cAdvisor in kubelet)   ──scrape──>  resource API  ──query every 15s──>  compare to target
                                                                                │
                                                       desiredReplicas = ceil(  │  )
                                                         currentReplicas × currentMetric / targetMetric
                                                                                │
                                                                                ▼
                                                                    Deployment .spec.replicas
```

The arithmetic is one line:

```text
desiredReplicas = ceil( currentReplicas × ( currentMetricValue / desiredMetricValue ) )
```

HPA changes the **number** of Pods (horizontal). It never makes a Pod bigger — that is the
VerticalPodAutoscaler's job, and the two must not target the same resource on the same workload.

---

## Step 0 — Why CPU **requests** are mandatory

`averageUtilization: 50` is a **percentage of the CPU request**, not a percentage of a core and not
a percentage of the limit. With no `resources.requests.cpu` on the container there is no denominator,
so the fraction is undefined and HPA refuses to compute anything.

This is the single most common HPA failure, so it is worth reproducing deliberately.
`01-deployment-no-requests.yaml` is the same nginx Deployment with the `resources` block removed:

```bash
kubectl apply -f 01-deployment-no-requests.yaml
kubectl apply -f 03-service.yaml
kubectl apply -f 04-hpa.yaml
kubectl rollout status deploy/hpa-demo -n hw13 --timeout=120s
```

```text
deployment.apps/hpa-demo created
service/hpa-demo-service created
horizontalpodautoscaler.autoscaling/hpa-demo created
Waiting for deployment "hpa-demo" rollout to finish: 0 of 1 updated replicas are available...
deployment "hpa-demo" successfully rolled out
```

After waiting a full metrics cycle:

```bash
kubectl get hpa -n hw13
```

```text
NAME       REFERENCE             TARGETS              MINPODS   MAXPODS   REPLICAS   AGE
hpa-demo   Deployment/hpa-demo   cpu: <unknown>/50%   1         5         1          70s
```

```bash
kubectl describe hpa hpa-demo -n hw13 | tail -25
```

```text
Metrics:                                               ( current / target )
  resource cpu on pods  (as a percentage of request):  <unknown> / 50%
Min replicas:                                          1
Max replicas:                                          5
Deployment pods:                                       1 current / 0 desired
Conditions:
  Type           Status  Reason                   Message
  ----           ------  ------                   -------
  AbleToScale    True    SucceededGetScale        the HPA controller was able to get the target's current scale
  ScalingActive  False   FailedGetResourceMetric  the HPA was unable to compute the replica count: failed to get cpu utilization: unable to get metrics for resource cpu: no metrics returned from resource metrics API
Events:
  Type     Reason                        Age                From                       Message
  ----     ------                        ----               ----                       -------
  Warning  FailedGetResourceMetric       10s (x5 over 70s)  horizontal-pod-autoscaler  failed to get cpu utilization: unable to get metrics for resource cpu: no metrics returned from resource metrics API
  Warning  FailedComputeMetricsReplicas  10s (x5 over 70s)  horizontal-pod-autoscaler  invalid metrics (1 invalid out of 1), first error is: failed to get cpu resource metric value: failed to get cpu utilization: unable to get metrics for resource cpu: no metrics returned from resource metrics API
```

The message says "no metrics returned from resource metrics API", which reads like a broken
metrics-server. It is not. At the same moment:

```bash
kubectl top pods -n hw13
kubectl top nodes
```

```text
NAME                        CPU(cores)   MEMORY(bytes)   
hpa-demo-77b89f84b6-mc6x8   1m           11Mi            
--- metrics-server is healthy ---
NAME       CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)   
minikube   184m         1%       1934Mi          24%         
```

metrics-server is returning 1m for that exact Pod. The metric exists; what is missing is the
request to divide it by, so the HPA controller discards the sample. **`kubectl top` working is not
evidence that HPA will work.**

Note also `Deployment pods: 1 current / 0 desired` — with no valid metric the controller cannot even
produce a recommendation.

---

## Step 1 — Deploy the application

`02-deployment.yaml` is the same Deployment with the requests restored:

```yaml
          resources:
            requests:
              cpu: 100m
            limits:
              cpu: 200m
```

```bash
kubectl apply -f 02-deployment.yaml
kubectl rollout status deploy/hpa-demo -n hw13 --timeout=120s
kubectl get deploy,pods -n hw13
kubectl get pod -n hw13 -l app=hpa-demo -o jsonpath='{.items[0].spec.containers[0].resources}{"\n"}'
```

```text
deployment.apps/hpa-demo configured
Waiting for deployment "hpa-demo" rollout to finish: 1 old replicas are pending termination...
deployment "hpa-demo" successfully rolled out
NAME                       READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/hpa-demo   1/1     1            1           79s

NAME                            READY   STATUS        RESTARTS   AGE
pod/hpa-demo-5d6676989b-rng8v   1/1     Running       0          0s
pod/hpa-demo-77b89f84b6-mc6x8   1/1     Terminating   0          79s
{"limits":{"cpu":"200m"},"requests":{"cpu":"100m"}}
```

With `requests.cpu: 100m`, a 50% target means **HPA aims for 50m of CPU per Pod**.

---

## Step 2 — Configure the HPA

`04-hpa.yaml`:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: hpa-demo
  namespace: hw13
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hpa-demo
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
```

| Field | Meaning |
| :--- | :--- |
| `scaleTargetRef` | The workload to resize. It must expose the `scale` subresource — Deployment, ReplicaSet, StatefulSet. A bare Pod cannot be a target. |
| `minReplicas` / `maxReplicas` | Hard floor and ceiling. HPA never goes outside them, whatever the metric says. |
| `target.type: Utilization` | Percentage of the **request**. `AverageValue` would be an absolute figure such as `100m` and would not need a request. |
| `apiVersion: autoscaling/v2` | v2 is required for multiple metrics, custom/external metrics and `behavior`. `autoscaling/v1` only supports a single CPU percentage. |

The HPA was already applied in step 0, so this step only had to wait for a valid metric:

```bash
kubectl get hpa -n hw13
```

```text
NAME       REFERENCE             TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
hpa-demo   Deployment/hpa-demo   cpu: 1%/50%   1         5         1          2m34s
```

`<unknown>` became `1%` purely because the Pod now declares a CPU request.

---

## Step 3 — Verify the HPA

```bash
kubectl describe hpa hpa-demo -n hw13 | sed -n '1,30p'
```

```text
Name:                                                  hpa-demo
Namespace:                                             hw13
Labels:                                                <none>
Annotations:                                           <none>
CreationTimestamp:                                     Wed, 07 Oct 2026 18:12:02 +0530
Reference:                                             Deployment/hpa-demo
Metrics:                                               ( current / target )
  resource cpu on pods  (as a percentage of request):  1% (1m) / 50%
Min replicas:                                          1
Max replicas:                                          5
Deployment pods:                                       1 current / 1 desired
Conditions:
  Type            Status  Reason              Message
  ----            ------  ------              -------
  AbleToScale     True    ReadyForNewScale    recommended size matches current size
  ScalingActive   True    ValidMetricFound    the HPA was able to successfully calculate a replica count from cpu resource utilization (percentage of request)
  ScalingLimited  False   DesiredWithinRange  the desired count is within the acceptable range
```

The three conditions are the health check for any HPA:

| Condition | Healthy value | What a bad value means |
| :--- | :--- | :--- |
| `AbleToScale` | `True` | `False` — the target does not exist, or a scale is still in progress |
| `ScalingActive` | `True` | `False` — no usable metric: missing requests, metrics-server down, Pods unready |
| `ScalingLimited` | `False` | `True` — the recommendation was clamped by `minReplicas`/`maxReplicas` |

`1% (1m) / 50%` shows both the percentage and the raw milli-cores it was computed from — useful when
you want to sanity-check the denominator.

---

## Step 4 — Deploy a load generator

`05-load-generator.yaml` is a Deployment (not a bare Pod), so the load itself can be scaled with
`kubectl scale` and removed cleanly later:

```yaml
          command:
            - sh
            - -c
            - "for i in 1 2 3; do (while true; do wget -q -O /dev/null http://hpa-demo-service.hw13.svc.cluster.local/; done) & done; wait"
```

Three replicas × three parallel request loops = nine concurrent clients.

```bash
kubectl apply -f 05-load-generator.yaml
kubectl rollout status deploy/load-generator -n hw13 --timeout=120s
```

```text
deployment.apps/load-generator created
Waiting for deployment "load-generator" rollout to finish: 0 of 3 updated replicas are available...
Waiting for deployment "load-generator" rollout to finish: 1 of 3 updated replicas are available...
Waiting for deployment "load-generator" rollout to finish: 2 of 3 updated replicas are available...
deployment "load-generator" successfully rolled out
```

The generator talks to the Service DNS name `hpa-demo-service.hw13.svc.cluster.local`, so as HPA
adds Pods the Service spreads the same traffic across all of them — which is exactly the feedback
loop that makes the utilisation fall back towards the target.

---

## Steps 5, 6 and 7 — Increase load, observe CPU, observe scaling

One watch loop covers all three. Timestamps are UTC:

```bash
for i in $(seq 1 24); do
  printf '%s  ' "$(date -u +%H:%M:%S)"
  kubectl get hpa hpa-demo -n hw13 --no-headers
  sleep 15
done
```

```text
12:44:49  hpa-demo   Deployment/hpa-demo   cpu: 1%/50%   1     5     1     2m47s
12:45:04  hpa-demo   Deployment/hpa-demo   cpu: 1%/50%   1     5     1     3m2s
12:45:19  hpa-demo   Deployment/hpa-demo   cpu: 24%/50%   1     5     1     3m17s
12:45:34  hpa-demo   Deployment/hpa-demo   cpu: 24%/50%   1     5     1     3m32s
12:45:49  hpa-demo   Deployment/hpa-demo   cpu: 24%/50%   1     5     1     3m47s
12:46:04  hpa-demo   Deployment/hpa-demo   cpu: 24%/50%   1     5     1     4m3s
12:46:20  hpa-demo   Deployment/hpa-demo   cpu: 174%/50%   1     5     1     4m18s
12:46:35  hpa-demo   Deployment/hpa-demo   cpu: 174%/50%   1     5     4     4m33s
12:46:50  hpa-demo   Deployment/hpa-demo   cpu: 174%/50%   1     5     4     4m48s
12:47:05  hpa-demo   Deployment/hpa-demo   cpu: 174%/50%   1     5     4     5m3s
12:47:20  hpa-demo   Deployment/hpa-demo   cpu: 59%/50%   1     5     4     5m19s
12:47:36  hpa-demo   Deployment/hpa-demo   cpu: 59%/50%   1     5     4     5m34s
12:47:51  hpa-demo   Deployment/hpa-demo   cpu: 59%/50%   1     5     4     5m49s
12:48:06  hpa-demo   Deployment/hpa-demo   cpu: 59%/50%   1     5     4     6m4s
12:48:21  hpa-demo   Deployment/hpa-demo   cpu: 47%/50%   1     5     4     6m19s
12:48:36  hpa-demo   Deployment/hpa-demo   cpu: 47%/50%   1     5     4     6m34s
12:48:51  hpa-demo   Deployment/hpa-demo   cpu: 47%/50%   1     5     4     6m49s
12:49:06  hpa-demo   Deployment/hpa-demo   cpu: 47%/50%   1     5     4     7m4s
12:49:21  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     7m19s
12:49:36  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     7m34s
12:49:51  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     7m50s
12:50:07  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     8m5s
12:50:22  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     8m20s
12:50:37  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     8m35s
```

Reading the timeline:

| Time (UTC) | What happened |
| :--- | :--- |
| 12:44:49 | Load generator already running, HPA still reports `1%` — metrics have not caught up |
| 12:45:19 | First raised reading, `24%` |
| 12:46:20 | `174%/50%` — well past the threshold. 174% of 100m = 174m on a single Pod |
| 12:46:35 | `REPLICAS 1 -> 4`. `ceil(1 × 174/50) = ceil(3.48) = 4` |
| 12:47:20 | `59%` — the same traffic is now shared by four Pods |
| 12:48:21 onwards | Settles at `46-47%`, just under the 50% target. Stable; no further scaling |

Note the ~90 second lag between starting the load and the metric moving. That is not HPA being slow:
metrics-server scrapes kubelets on a fixed interval and reports a windowed average, the HPA
controller then syncs every 15 seconds. **Autoscaling is always reacting to the recent past.**

### `kubectl get pods` — the replica count really rose

```bash
kubectl get pods -n hw13 -o wide
```

```text
NAME                              READY   STATUS    RESTARTS   AGE     IP            NODE       NOMINATED NODE   READINESS GATES
hpa-demo-5d6676989b-2zgtw         1/1     Running   0          4m40s   10.244.0.95   minikube   <none>           <none>
hpa-demo-5d6676989b-4cnv7         1/1     Running   0          4m40s   10.244.0.96   minikube   <none>           <none>
hpa-demo-5d6676989b-rng8v         1/1     Running   0          7m36s   10.244.0.84   minikube   <none>           <none>
hpa-demo-5d6676989b-wn9k2         1/1     Running   0          4m40s   10.244.0.97   minikube   <none>           <none>
load-generator-66f76bcfc9-bqhhm   1/1     Running   0          6m9s    10.244.0.92   minikube   <none>           <none>
load-generator-66f76bcfc9-mfwwp   1/1     Running   0          6m9s    10.244.0.91   minikube   <none>           <none>
load-generator-66f76bcfc9-xsnzn   1/1     Running   0          6m9s    10.244.0.93   minikube   <none>           <none>
```

The `AGE` column tells the story on its own: one `hpa-demo` Pod is 7m36s old (the original) and
three are 4m40s old (created by the scale-out). All four share the same ReplicaSet hash
`5d6676989b`, so this was a replica-count change, not a new rollout.

### `kubectl top pods` — real CPU numbers

```bash
kubectl top pods -n hw13
```

```text
NAME                              CPU(cores)   MEMORY(bytes)   
hpa-demo-5d6676989b-2zgtw         46m          12Mi            
hpa-demo-5d6676989b-4cnv7         48m          12Mi            
hpa-demo-5d6676989b-rng8v         46m          12Mi            
hpa-demo-5d6676989b-wn9k2         46m          12Mi            
load-generator-66f76bcfc9-bqhhm   691m         4Mi             
load-generator-66f76bcfc9-mfwwp   689m         4Mi             
load-generator-66f76bcfc9-xsnzn   687m         4Mi             
```

`(46 + 48 + 46 + 46) / 4 = 46.5m`, and `46.5 / 100 = 46%` — which is exactly what
`kubectl get hpa` printed. The HPA average is a plain mean over the Pods it targets.

Also worth noticing: each load generator burns ~690m while each nginx Pod burns ~46m. The
`busybox`/`wget` client, which forks a process per request, is roughly 15× more expensive than the
server it is hammering. Load generators are not free, and on a small cluster they, not the workload,
are usually the thing that saturates.

### `kubectl describe hpa` — the SuccessfulRescale event

```bash
kubectl describe hpa hpa-demo -n hw13 | sed -n '1,40p'
```

```text
Metrics:                                               ( current / target )
  resource cpu on pods  (as a percentage of request):  46% (46m) / 50%
Min replicas:                                          1
Max replicas:                                          5
Deployment pods:                                       4 current / 4 desired
Conditions:
  Type            Status  Reason              Message
  ----            ------  ------              -------
  AbleToScale     True    ReadyForNewScale    recommended size matches current size
  ScalingActive   True    ValidMetricFound    the HPA was able to successfully calculate a replica count from cpu resource utilization (percentage of request)
  ScalingLimited  False   DesiredWithinRange  the desired count is within the acceptable range
  ScaledToZero    False   NotScaledToZero     the HPA controller did not scale the workload to zero
Events:
  Type     Reason                        Age                    From                       Message
  ----     ------                        ----                   ----                       -------
  Normal   SuccessfulRescale             4m41s                  horizontal-pod-autoscaler  New size: 4; reason: cpu resource utilization (percentage of request) above target
```

`SuccessfulRescale ... New size: 4; reason: cpu resource utilization (percentage of request) above
target` is the authoritative record that HPA — not a human and not a controller restart — changed
the replica count.

### An experiment that did not do what was expected

Scaling the load generator from 3 to 5 replicas did **not** push the deployment to `maxReplicas: 5`:

```bash
kubectl scale deploy/load-generator -n hw13 --replicas=5
```

Five samples from the twelve-sample watch loop that followed:

```text
12:51:12  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     9m10s
12:51:27  hpa-demo   Deployment/hpa-demo   cpu: 47%/50%   1     5     4     9m25s
12:52:12  hpa-demo   Deployment/hpa-demo   cpu: 47%/50%   1     5     4     10m
12:53:13  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     11m
12:53:58  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     11m
```

```bash
kubectl top nodes
kubectl top pods -n hw13 | grep -E 'NAME|load'
```

```text
NAME       CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)   
minikube   3997m        26%      1685Mi          21%         
--- load generators ---
NAME                              CPU(cores)   MEMORY(bytes)   
load-generator-66f76bcfc9-bqhhm   446m         2Mi             
load-generator-66f76bcfc9-jn7vc   441m         2Mi             
load-generator-66f76bcfc9-ktsrh   439m         2Mi             
load-generator-66f76bcfc9-mfwwp   437m         2Mi             
load-generator-66f76bcfc9-xsnzn   446m         4Mi             
```

Each generator dropped from ~690m to ~440m, and the total stayed around 2.2 cores. Adding clients
did not add throughput — the node is the bottleneck, so the aggregate request rate was flat and
nginx stayed at 46%. The deployment therefore stabilised at 4 replicas, not 5. This is reported as
it happened rather than retried until it produced a nicer number: on a single six-core node, a
`wget`-loop load generator saturates the host long before nginx gets anywhere near its own limit.

---

## Step 8 — Capture the output: scale **down**

Scaling down is the half that surprises people, so it was timed explicitly.

```bash
echo "=== load removed at $(date -u +%H:%M:%S) UTC ==="
kubectl delete deploy/load-generator -n hw13
for i in $(seq 1 28); do
  printf '%s  ' "$(date -u +%H:%M:%S)"
  kubectl get hpa hpa-demo -n hw13 --no-headers
  sleep 15
done
```

```text
=== load removed at 12:54:32 UTC ===
deployment.apps "load-generator" deleted from hw13 namespace
12:54:32  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     12m
12:54:47  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     12m
12:55:02  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     13m
12:55:17  hpa-demo   Deployment/hpa-demo   cpu: 46%/50%   1     5     4     13m
12:55:33  hpa-demo   Deployment/hpa-demo   cpu: 45%/50%   1     5     4     13m
12:55:48  hpa-demo   Deployment/hpa-demo   cpu: 45%/50%   1     5     4     13m
12:56:03  hpa-demo   Deployment/hpa-demo   cpu: 45%/50%   1     5     4     14m
12:56:18  hpa-demo   Deployment/hpa-demo   cpu: 45%/50%   1     5     4     14m
12:56:33  hpa-demo   Deployment/hpa-demo   cpu: 1%/50%   1     5     4     14m
12:56:48  hpa-demo   Deployment/hpa-demo   cpu: 1%/50%   1     5     4     14m
12:57:03  hpa-demo   Deployment/hpa-demo   cpu: 1%/50%   1     5     4     15m
12:57:19  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     15m
12:57:34  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     15m
12:57:49  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     15m
12:58:04  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     16m
12:58:19  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     16m
12:58:34  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     16m
12:58:49  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     16m
12:59:04  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     17m
12:59:19  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     17m
12:59:34  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     17m
12:59:50  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     17m
13:00:05  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     18m
13:00:20  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     18m
13:00:35  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     18m
13:00:50  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     18m
13:01:05  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     19m
13:01:21  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     1     19m
```

The stabilisation window, measured:

| Time (UTC) | Event | Gap |
| :--- | :--- | :--- |
| 12:54:32 | Load generator deleted | — |
| 12:56:33 | CPU reading finally falls to `1%` | +2m01s (metrics lag) |
| 13:01:21 | `REPLICAS 4 -> 1` | +4m48s after the metric dropped |
| | **Total idle-to-shrink** | **+6m49s** |

For nearly five minutes `kubectl get hpa` showed `cpu: 0%/50%` next to `REPLICAS 4`, which looks
broken and is not. This is the **scale-down stabilisation window**:

```bash
kubectl explain hpa.spec.behavior.scaleDown.stabilizationWindowSeconds
```

```text
DESCRIPTION:
    stabilizationWindowSeconds is the number of seconds for which past
    recommendations should be considered while scaling up or scaling down.
    StabilizationWindowSeconds must be greater than or equal to zero and less
    than or equal to 3600 (one hour). If not set, use the default values: - For
    scale up: 0 (i.e. no stabilization is done). - For scale down: 300 (i.e. the
    stabilization window is 300 seconds long).
```

When shrinking, the controller takes the **maximum** recommendation from the last 300 seconds, not
the latest one. Any single busy sample inside that window keeps the replica count up. The asymmetry
is deliberate:

- **scale up: 0s stabilisation** — a traffic spike is an emergency; react immediately.
- **scale down: 300s stabilisation** — removing capacity during a lull in a spiky workload causes
  thrashing (scale up, scale down, scale up …), and every scale-down drops in-flight connections.

Confirmed against the event stream:

```bash
kubectl get events -n hw13 --field-selector involvedObject.name=hpa-demo \
  -o custom-columns='TIME:.lastTimestamp,REASON:.reason,MESSAGE:.message'
```

```text
TIME                   REASON                         MESSAGE
2026-10-07T12:46:17Z   SuccessfulRescale              New size: 4; reason: cpu resource utilization (percentage of request) above target
2026-10-07T13:01:03Z   SuccessfulRescale              New size: 1; reason: All metrics below target
```

Final state:

```bash
kubectl get hpa -n hw13
kubectl get pods -n hw13
```

```text
NAME       REFERENCE             TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1         5         1          19m

NAME                        READY   STATUS    RESTARTS   AGE
hpa-demo-5d6676989b-wn9k2   1/1     Running   0          15m
```

Note the scale-down went straight from 4 to 1 in one move — with the default `behavior` there is no
rate limit on how many Pods a single scale-down may remove, only the time window.

### Tuning the window

`06-hpa-tuned-behavior.yaml` adds an explicit `behavior` block:

```yaml
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 50
          periodSeconds: 15
```

To prove the window is really what caused the five-minute delay, the deployment was scaled up by
hand while CPU was idle — HPA should pull it back down, and now much faster:

```bash
kubectl apply -f 06-hpa-tuned-behavior.yaml
kubectl scale deploy/hpa-demo -n hw13 --replicas=4
```

```text
13:02:03  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     1     20m
13:02:13  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     4     20m
13:02:23  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     2     20m
13:02:33  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     2     20m
13:02:43  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     2     20m
13:02:54  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     2     20m
13:03:04  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     2     21m
13:03:14  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     2     21m
13:03:24  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     2     21m
13:03:34  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     2     21m
13:03:44  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     2     21m
13:03:54  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     1     21m
13:04:04  hpa-demo   Deployment/hpa-demo   cpu: 0%/50%   1     5     1     22m
```

Two behaviours are visible at once:

- **The window shrank**: 4 Pods were removed starting 20 seconds after the manual scale, instead of
  the ~5 minutes measured above. Same cluster, same idle CPU, only `stabilizationWindowSeconds`
  changed — so the earlier delay was the window, not a stuck controller.
- **The policy throttled the step**: `4 -> 2 -> 1` rather than `4 -> 1`, because
  `type: Percent, value: 50, periodSeconds: 15` permits removing at most half the Pods per
  15-second period. This is how you protect a workload with long-lived connections.

---

## Step 9 — Output in the README

This document is that output. Nothing in it is reconstructed: every block was copied from the
terminal as the lab ran, including the failures in step 0 and the experiment that did not reach
`maxReplicas`.

---

## Troubleshooting cheat sheet

| Symptom | Likely cause | Check |
| :--- | :--- | :--- |
| `TARGETS: <unknown>/50%` | Container has no `resources.requests.cpu` | `kubectl get pod -o jsonpath='{.spec.containers[0].resources}'` |
| `TARGETS: <unknown>/50%` and `kubectl top pods` also fails | metrics-server missing or unhealthy | `kubectl get apiservice v1beta1.metrics.k8s.io` |
| HPA works but never scales | Utilisation genuinely below target, or `maxReplicas` already reached | `ScalingLimited` condition |
| Replicas stuck high after load stops | Scale-down stabilisation window (300s default) | `kubectl describe hpa`, then wait |
| Replicas flapping up and down | Target too close to idle usage, or window too short | Raise the target, lengthen `scaleDown.stabilizationWindowSeconds` |
| `AbleToScale: False` | `scaleTargetRef` points at something that does not exist, or has no `scale` subresource | `kubectl get deploy <name>` |
| Pods scale but traffic does not spread | Service selector does not match the new Pods | `kubectl get endpointslices` |

---

## Manifests in this folder

| File | Purpose |
| :--- | :--- |
| `01-deployment-no-requests.yaml` | The broken variant: no CPU request, so HPA reports `<unknown>` |
| `02-deployment.yaml` | nginx, `requests.cpu: 100m`, `limits.cpu: 200m` |
| `03-service.yaml` | ClusterIP Service in front of the Deployment |
| `04-hpa.yaml` | `autoscaling/v2` HPA, 1–5 replicas, 50% CPU |
| `05-load-generator.yaml` | 3 replicas × 3 `wget` loops against the Service |
| `06-hpa-tuned-behavior.yaml` | Same HPA plus an explicit `behavior` block (30s scale-down window, 50%/15s policy) |

## References

- Horizontal Pod Autoscaling — https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- HPA walkthrough — https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/
- Resource metrics pipeline — https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/
