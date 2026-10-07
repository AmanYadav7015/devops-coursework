# Task 3 — Mini project: production-ready web app

The mini project supplied with the session (`session-13-storage-hpa-probes/mini-project/`),
implemented and verified end to end. It combines all three pillars of the session in one workload:

1. **State persistence** — a PVC mounted at `/data`, so data outlives Pod deletion.
2. **Elastic scaling** — an HPA on CPU, 2 to 5 replicas.
3. **Health diagnostics** — startup, readiness and liveness probes.

### Deviations from the supplied manifests, and why

| Supplied | Used here | Reason |
| :--- | :--- | :--- |
| `namespace: production-webapp` | `namespace: hw13` | The cluster is shared with other concurrent work; everything in this homework is confined to one namespace. |
| `Service type: ClusterIP` | `type: NodePort`, `nodePort: 30130` | Lets the Service be verified from outside the Pod network without holding a `port-forward` open. |
| Probes on `path: /` | Probes on `path: /healthz`, created by a `postStart` hook | Probing `/` means "nginx serves its default page". A dedicated health file can be removed at runtime, which is what makes a *real* probe failure demonstrable instead of only describable. |
| `kubectl run load-generator` (one `wget` loop) | A `load-generator` Deployment, 3 replicas × 3 loops | One loop does not generate enough CPU to cross a 50% target against two Pods. It is also easier to scale and delete. |

Everything below is real captured output.

---

## Architecture

```text
                 NodePort 30130  ──>  Service: web-service (ClusterIP 10.105.120.147)
                                               │ selector app=web-app
                     ┌─────────────────────────┼─────────────────────────┐
                     ▼                         ▼                         ▼
            [ Pod: web-app-1 ]        [ Pod: web-app-2 ]        [ Pod: web-app-N ]
            ├─ startupProbe           ├─ startupProbe           ├─ startupProbe
            ├─ readinessProbe         ├─ readinessProbe         ├─ readinessProbe
            ├─ livenessProbe          ├─ livenessProbe          ├─ livenessProbe
            ├─ requests cpu 100m      ├─ requests cpu 100m      ├─ requests cpu 100m
            └──────────┬──────────────┴────────────┬────────────┴──────────┘
                       │  mount /data                           ▲
                       ▼                                        │ sets .spec.replicas
            PVC: web-data (500Mi, RWO)             HPA: web-app-hpa (2-5, 50% CPU)
                       │                                        ▲
                       ▼                                        │ resource metrics API
            PV pvc-6c679b7b-... (StorageClass standard)      metrics-server
                       │
                       ▼
            /tmp/hostpath-provisioner/hw13/web-data on the node
```

---

## Deployment

### Namespace

```bash
kubectl apply -f 01-namespace.yaml
```

```text
namespace/hw13 configured
```

### PersistentVolumeClaim

```bash
kubectl apply -f 02-pvc.yaml
kubectl get pvc -n hw13
```

```text
persistentvolumeclaim/web-data created
NAME       STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
web-data   Bound    pvc-6c679b7b-61a0-4d1c-97dc-d10c2d9fd376   500Mi      RWO            standard       <unset>                 5s
```

`Bound` with a `pvc-<uid>` volume name — dynamically provisioned by the `standard` StorageClass.

### Deployment and Service

```bash
kubectl apply -f 03-deployment.yaml -f 04-service.yaml
kubectl rollout status deploy/web-app -n hw13 --timeout=180s
kubectl get pods -n hw13 -o wide
kubectl get svc -n hw13
```

```text
deployment.apps/web-app created
service/web-service created
Waiting for deployment "web-app" rollout to finish: 0 of 2 updated replicas are available...
Waiting for deployment "web-app" rollout to finish: 1 of 2 updated replicas are available...
deployment "web-app" successfully rolled out
NAME                      READY   STATUS    RESTARTS   AGE   IP             NODE       NOMINATED NODE   READINESS GATES
web-app-97bc5bcf6-bhvpt   1/1     Running   0          9s    10.244.0.135   minikube   <none>           <none>
web-app-97bc5bcf6-tn6lv   1/1     Running   0          9s    10.244.0.134   minikube   <none>           <none>
NAME          TYPE       CLUSTER-IP       EXTERNAL-IP   PORT(S)        AGE
web-service   NodePort   10.105.120.147   <none>        80:30130/TCP   9s
```

`strategy: type: Recreate` is required here, not cosmetic: with `RollingUpdate` the new Pod would
try to attach the same `ReadWriteOnce` volume while the old one still holds it. On a multi-node
cluster that deadlocks the rollout.

### HorizontalPodAutoscaler

```bash
kubectl apply -f 05-hpa.yaml
kubectl get hpa -n hw13
kubectl top pods -n hw13
```

```text
horizontalpodautoscaler.autoscaling/web-app-hpa created
NAME          REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
web-app-hpa   Deployment/web-app   cpu: 1%/50%   2         5         2          2m2s
NAME                      CPU(cores)   MEMORY(bytes)   
web-app-97bc5bcf6-bhvpt   1m           12Mi            
web-app-97bc5bcf6-tn6lv   1m           12Mi            
```

```bash
kubectl describe hpa web-app-hpa -n hw13 | sed -n '1,20p'
```

```text
Reference:                                             Deployment/web-app
Metrics:                                               ( current / target )
  resource cpu on pods  (as a percentage of request):  1% (1m) / 50%
Min replicas:                                          2
Max replicas:                                          5
Deployment pods:                                       2 current / 2 desired
Conditions:
  Type            Status  Reason               Message
  ----            ------  ------               -------
  AbleToScale     True    ScaleDownStabilized  recent recommendations were higher than current one, applying the highest recent recommendation
  ScalingActive   True    ValidMetricFound     the HPA was able to successfully calculate a replica count from cpu resource utilization (percentage of request)
  ScalingLimited  False   DesiredWithinRange   the desired count is within the acceptable range
```

Immediately after creation the HPA reported `cpu: <unknown>/50%` for about a minute. That is the
metrics-server scrape interval, not a misconfiguration — the container does declare
`requests.cpu: 100m`, and the value resolved to `1%` on its own.

---

## Verification 1 — storage persistence

```bash
POD_NAME=$(kubectl get pods -n hw13 -l app=web-app -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n hw13 "$POD_NAME" -- sh -c 'echo "Student: Aman Yadav, written $(date -u +%Y-%m-%dT%H:%M:%SZ)" > /data/student.txt'
kubectl exec -n hw13 "$POD_NAME" -- cat /data/student.txt
```

```text
pod: web-app-97bc5bcf6-bhvpt
Student: Aman Yadav, written 2026-10-07T13:17:14Z
```

The other replica sees the same file, because both Pods mount the same PVC:

```bash
OTHER=$(kubectl get pods -n hw13 -l app=web-app -o jsonpath='{.items[1].metadata.name}')
kubectl exec -n hw13 "$OTHER" -- cat /data/student.txt
```

```text
other pod: web-app-97bc5bcf6-tn6lv
Student: Aman Yadav, written 2026-10-07T13:17:14Z
```

### Delete a Pod and read the file back

```bash
kubectl delete pod -n hw13 web-app-97bc5bcf6-bhvpt
kubectl wait --for=condition=Ready pod -l app=web-app -n hw13 --timeout=120s
kubectl get pods -n hw13
NEW_POD=$(kubectl get pods -n hw13 -l app=web-app --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
kubectl exec -n hw13 "$NEW_POD" -- cat /data/student.txt
```

```text
pod "web-app-97bc5bcf6-bhvpt" deleted from hw13 namespace
pod/web-app-97bc5bcf6-mhlg4 condition met
pod/web-app-97bc5bcf6-tn6lv condition met
NAME                      READY   STATUS    RESTARTS   AGE
web-app-97bc5bcf6-mhlg4   1/1     Running   0          9s
web-app-97bc5bcf6-tn6lv   1/1     Running   0          2m31s
new pod: web-app-97bc5bcf6-mhlg4
Student: Aman Yadav, written 2026-10-07T13:17:14Z
```

The embedded timestamp `13:17:14Z` is the proof. It was generated before the Pod was destroyed, and
a Pod that did not exist at that time read it back byte for byte.

---

## Verification 2 — the Service

### From inside the cluster, by DNS name

```bash
kubectl run hw13-curl -n hw13 --image=busybox:1.36 --restart=Never --rm -i --quiet -- \
  wget -q -O- http://web-service.hw13.svc.cluster.local/
```

```text
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
html { color-scheme: light dark; }
body { width: 35em; margin: 0 auto;
font-family: Tahoma, Verdana, Arial, sans-serif; }
</style>
</head>
<body>
<h1>Welcome to nginx!</h1>
```

### From outside the Pod network, via the NodePort

The minikube node IP is not routable from the host when the docker driver is used, so the request is
issued from the node itself:

```bash
minikube ssh -- "curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://192.168.49.2:30130/ && curl -s http://192.168.49.2:30130/healthz"
kubectl get endpoints web-service -n hw13
```

```text
HTTP 200
ok

NAME          ENDPOINTS                         AGE
web-service   10.244.0.134:80,10.244.0.137:80   2m39s
```

`HTTP 200` through the NodePort, `ok` from the health file, and both Pod IPs listed as endpoints.

---

## Verification 3 — HPA elastic scaling

### Scale out

```bash
kubectl apply -f 06-load-generator.yaml
kubectl rollout status deploy/load-generator -n hw13 --timeout=120s
for i in $(seq 1 20); do printf '%s  ' "$(date -u +%H:%M:%S)"; kubectl get hpa web-app-hpa -n hw13 --no-headers; sleep 15; done
```

```text
=== load started at 13:18:44 UTC ===
13:18:44  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     2     2m30s
13:18:59  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     2     2m45s
13:19:14  web-app-hpa   Deployment/web-app   cpu: 19%/50%   2     5     2     3m
13:19:29  web-app-hpa   Deployment/web-app   cpu: 19%/50%   2     5     2     3m16s
13:19:45  web-app-hpa   Deployment/web-app   cpu: 19%/50%   2     5     2     3m31s
13:20:00  web-app-hpa   Deployment/web-app   cpu: 19%/50%   2     5     2     3m46s
13:20:15  web-app-hpa   Deployment/web-app   cpu: 83%/50%   2     5     2     4m1s
13:20:30  web-app-hpa   Deployment/web-app   cpu: 83%/50%   2     5     4     4m16s
13:20:45  web-app-hpa   Deployment/web-app   cpu: 83%/50%   2     5     4     4m31s
13:21:00  web-app-hpa   Deployment/web-app   cpu: 83%/50%   2     5     4     4m46s
13:21:15  web-app-hpa   Deployment/web-app   cpu: 59%/50%   2     5     4     5m1s
13:21:30  web-app-hpa   Deployment/web-app   cpu: 59%/50%   2     5     4     5m17s
13:21:46  web-app-hpa   Deployment/web-app   cpu: 59%/50%   2     5     4     5m32s
13:22:01  web-app-hpa   Deployment/web-app   cpu: 59%/50%   2     5     4     5m47s
13:22:16  web-app-hpa   Deployment/web-app   cpu: 43%/50%   2     5     4     6m2s
13:22:31  web-app-hpa   Deployment/web-app   cpu: 43%/50%   2     5     4     6m17s
13:22:46  web-app-hpa   Deployment/web-app   cpu: 43%/50%   2     5     4     6m32s
13:23:01  web-app-hpa   Deployment/web-app   cpu: 43%/50%   2     5     4     6m47s
13:23:16  web-app-hpa   Deployment/web-app   cpu: 44%/50%   2     5     4     7m3s
13:23:32  web-app-hpa   Deployment/web-app   cpu: 44%/50%   2     5     4     7m18s
```

`ceil(2 × 83/50) = ceil(3.32) = 4`, which is exactly the replica count the HPA chose at 13:20:30.

```bash
kubectl get pods -n hw13
kubectl top pods -n hw13
```

```text
NAME                              READY   STATUS      RESTARTS   AGE
hw13-curl                         0/1     Completed   0          5m13s
load-generator-867d84d4c8-snvd4   1/1     Running     0          5m7s
load-generator-867d84d4c8-sscm8   1/1     Running     0          5m7s
load-generator-867d84d4c8-x4skh   1/1     Running     0          5m7s
web-app-97bc5bcf6-jd7q6           1/1     Running     0          3m37s
web-app-97bc5bcf6-mhlg4           1/1     Running     0          5m29s
web-app-97bc5bcf6-tn6lv           1/1     Running     0          7m51s
web-app-97bc5bcf6-xjrf8           1/1     Running     0          3m37s

NAME                              CPU(cores)   MEMORY(bytes)   
load-generator-867d84d4c8-snvd4   654m         3Mi             
load-generator-867d84d4c8-sscm8   656m         4Mi             
load-generator-867d84d4c8-x4skh   656m         4Mi             
web-app-97bc5bcf6-jd7q6           44m          12Mi            
web-app-97bc5bcf6-mhlg4           44m          12Mi            
web-app-97bc5bcf6-tn6lv           44m          12Mi            
web-app-97bc5bcf6-xjrf8           44m          12Mi            
```

```bash
kubectl describe hpa web-app-hpa -n hw13 | sed -n '/Conditions:/,$p'
```

```text
Conditions:
  Type            Status  Reason              Message
  ----            ------  ------              -------
  AbleToScale     True    ReadyForNewScale    recommended size matches current size
  ScalingActive   True    ValidMetricFound    the HPA was able to successfully calculate a replica count from cpu resource utilization (percentage of request)
  ScalingLimited  False   DesiredWithinRange  the desired count is within the acceptable range
  ScaledToZero    False   NotScaledToZero     the HPA controller did not scale the workload to zero
Events:
  Normal   SuccessfulRescale             3m38s                  horizontal-pod-autoscaler  New size: 4; reason: cpu resource utilization (percentage of request) above target
```

### All four replicas really do share one volume

```bash
for p in $(kubectl get pods -n hw13 -l app=web-app -o jsonpath='{.items[*].metadata.name}'); do
  printf '%-26s ' "$p"; kubectl exec -n hw13 $p -- cat /data/student.txt
done
```

```text
web-app-97bc5bcf6-jd7q6    Student: Aman Yadav, written 2026-10-07T13:17:14Z
web-app-97bc5bcf6-mhlg4    Student: Aman Yadav, written 2026-10-07T13:17:14Z
web-app-97bc5bcf6-tn6lv    Student: Aman Yadav, written 2026-10-07T13:17:14Z
web-app-97bc5bcf6-xjrf8    Student: Aman Yadav, written 2026-10-07T13:17:14Z
```

Two Pods that never existed when the file was written mount the same RWO volume and read the same
content. This works only because all five Pods land on the same node — `ReadWriteOnce` is a *node*
guarantee. The identical manifest on a multi-node cluster would leave Pods on other nodes stuck in
`ContainerCreating` with a `FailedAttachVolume` event. A Deployment whose replicas all share one RWO
PVC is a single-node pattern; the production answer is a StatefulSet with `volumeClaimTemplates` (a
volume each) or an RWX class such as EFS/Azure Files.

### Scale in

```bash
kubectl delete deploy load-generator -n hw13
for i in $(seq 1 30); do printf '%s  ' "$(date -u +%H:%M:%S)"; kubectl get hpa web-app-hpa -n hw13 --no-headers; sleep 15; done
```

```text
=== load removed at 13:23:58 UTC ===
13:23:58  web-app-hpa   Deployment/web-app   cpu: 44%/50%   2     5     4     7m44s
13:24:13  web-app-hpa   Deployment/web-app   cpu: 44%/50%   2     5     4     7m59s
13:24:28  web-app-hpa   Deployment/web-app   cpu: 44%/50%   2     5     4     8m14s
13:24:43  web-app-hpa   Deployment/web-app   cpu: 44%/50%   2     5     4     8m29s
13:24:58  web-app-hpa   Deployment/web-app   cpu: 44%/50%   2     5     4     8m44s
13:25:13  web-app-hpa   Deployment/web-app   cpu: 44%/50%   2     5     4     8m59s
13:25:28  web-app-hpa   Deployment/web-app   cpu: 22%/50%   2     5     4     9m15s
13:25:44  web-app-hpa   Deployment/web-app   cpu: 22%/50%   2     5     4     9m30s
13:25:59  web-app-hpa   Deployment/web-app   cpu: 22%/50%   2     5     4     9m45s
13:26:14  web-app-hpa   Deployment/web-app   cpu: 22%/50%   2     5     4     10m
13:26:29  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     10m
13:26:44  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     10m
13:26:59  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     10m
13:27:14  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     11m
13:27:29  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     11m
13:27:44  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     11m
13:28:00  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     11m
13:28:15  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     12m
13:28:30  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     12m
13:28:45  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     12m
13:29:00  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     12m
13:29:15  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     13m
13:29:30  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     13m
13:29:46  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     13m
13:30:01  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     4     13m
13:30:16  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     2     14m
13:30:31  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     2     14m
13:30:46  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     2     14m
13:31:01  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     2     14m
13:31:16  web-app-hpa   Deployment/web-app   cpu: 1%/50%   2     5     2     15m
```

```bash
kubectl get events -n hw13 --field-selector involvedObject.name=web-app-hpa \
  -o custom-columns='TIME:.lastTimestamp,REASON:.reason,MESSAGE:.message'
```

```text
TIME                   REASON                         MESSAGE
2026-10-07T13:20:14Z   SuccessfulRescale              New size: 4; reason: cpu resource utilization (percentage of request) above target
2026-10-07T13:30:00Z   SuccessfulRescale              New size: 2; reason: All metrics below target
```

| Time (UTC) | Event |
| :--- | :--- |
| 13:23:58 | Load generator deleted |
| 13:25:28 | First reduced reading, `22%` — the recommendation becomes `ceil(4 × 22/50) = 2` |
| 13:30:00 | `SuccessfulRescale ... New size: 2` — just under 5 minutes after the recommendation dropped |

Scale-in stopped at 2, not 1 or 0, because `minReplicas: 2` is a hard floor. The ~4m30s delay is the
default 300-second scale-down stabilisation window, measured in detail in
[`../02-hpa/README.md`](../02-hpa/README.md).

---

## Bonus challenge 1 — lower the threshold from 50% to 30%

`07-hpa-threshold-30.yaml` is `05-hpa.yaml` with `averageUtilization: 30`. With identical load:

```bash
kubectl apply -f 07-hpa-threshold-30.yaml
kubectl apply -f 06-load-generator.yaml
```

```text
=== load restarted at 13:31:55 UTC, target now 30% ===
13:31:55  web-app-hpa   Deployment/web-app   cpu: 1%/30%   2     5     2     15m
13:32:25  web-app-hpa   Deployment/web-app   cpu: 3%/30%   2     5     2     16m
13:33:11  web-app-hpa   Deployment/web-app   cpu: 3%/30%   2     5     2     16m
13:33:26  web-app-hpa   Deployment/web-app   cpu: 92%/30%   2     5     2     17m
13:33:41  web-app-hpa   Deployment/web-app   cpu: 92%/30%   2     5     4     17m
13:33:56  web-app-hpa   Deployment/web-app   cpu: 92%/30%   2     5     5     17m
13:34:11  web-app-hpa   Deployment/web-app   cpu: 92%/30%   2     5     5     17m
13:34:26  web-app-hpa   Deployment/web-app   cpu: 69%/30%   2     5     5     18m
13:35:11  web-app-hpa   Deployment/web-app   cpu: 69%/30%   2     5     5     18m
13:35:27  web-app-hpa   Deployment/web-app   cpu: 39%/30%   2     5     5     19m
13:36:12  web-app-hpa   Deployment/web-app   cpu: 39%/30%   2     5     5     19m
13:36:27  web-app-hpa   Deployment/web-app   cpu: 38%/30%   2     5     5     20m
13:36:42  web-app-hpa   Deployment/web-app   cpu: 38%/30%   2     5     5     20m
```

(abridged — every line shown is a real sample from the 20-sample watch loop)

The same traffic that produced 4 replicas at a 50% target produced **5** at 30%, and it got there in
two steps 15 seconds apart (`2 -> 4 -> 5`). More importantly, the deployment is now pinned at the
ceiling:

```bash
kubectl describe hpa web-app-hpa -n hw13 | sed -n '/Conditions:/,$p' | head -20
kubectl top pods -n hw13 | grep -E 'NAME|web-app'
```

```text
Conditions:
  Type            Status  Reason            Message
  ----            ------  ------            -------
  AbleToScale     True    ReadyForNewScale  recommended size matches current size
  ScalingActive   True    ValidMetricFound  the HPA was able to successfully calculate a replica count from cpu resource utilization (percentage of request)
  ScalingLimited  True    TooManyReplicas   the desired replica count is more than the maximum replica count
  ScaledToZero    False   NotScaledToZero   the HPA controller did not scale the workload to zero
Events:
  Normal   SuccessfulRescale             7m1s                 horizontal-pod-autoscaler  New size: 2; reason: All metrics below target
  Normal   SuccessfulRescale             3m46s (x2 over 16m)  horizontal-pod-autoscaler  New size: 4; reason: cpu resource utilization (percentage of request) above target
  Normal   SuccessfulRescale             3m31s                horizontal-pod-autoscaler  New size: 5; reason: cpu resource utilization (percentage of request) above target

NAME                              CPU(cores)   MEMORY(bytes)   
web-app-97bc5bcf6-bjfvv           39m          12Mi            
web-app-97bc5bcf6-bwpnl           38m          12Mi            
web-app-97bc5bcf6-cvwrg           39m          12Mi            
web-app-97bc5bcf6-tn6lv           39m          12Mi            
web-app-97bc5bcf6-xjrf8           39m          12Mi            
```

`ScalingLimited: True / TooManyReplicas` is the condition to alert on in production — it means the
autoscaler wants more capacity than you allowed it and is now letting the service degrade. `38%`
against a `30%` target is the visible symptom: the HPA cannot bring utilisation back down because it
has run out of replicas.

Lesson: a lower threshold does not make an application faster. It makes the autoscaler react sooner
and hold more headroom, at the cost of more Pods — and it reaches `maxReplicas` sooner.

---

## Bonus challenge 2 — break the readiness probe

`08-deployment-broken-readiness.yaml` is `03-deployment.yaml` with one field changed:

```yaml
          readinessProbe:
            httpGet:
              path: /does-not-exist
```

```bash
kubectl get endpoints web-service -n hw13          # before
kubectl apply -f 08-deployment-broken-readiness.yaml
kubectl rollout status deploy/web-app -n hw13 --timeout=60s; echo "rollout exit code: $?"
kubectl get pods -n hw13 -l app=web-app
kubectl get endpoints web-service -n hw13          # after
```

```text
=== BEFORE ===
NAME          ENDPOINTS                         AGE
web-service   10.244.0.134:80,10.244.0.143:80   21m
=== challenge 2: readiness -> /does-not-exist at 13:37:24 UTC ===
deployment.apps/web-app configured
Waiting for deployment "web-app" rollout to finish: 0 out of 2 new replicas have been updated...
Waiting for deployment "web-app" rollout to finish: 0 of 2 updated replicas are available...
error: timed out waiting for the condition
rollout exit code: 1
NAME                       READY   STATUS    RESTARTS   AGE
web-app-55db44c68f-7jjzs   0/1     Running   0          60s
web-app-55db44c68f-r624z   0/1     Running   0          60s
--- endpoints ---
NAME          ENDPOINTS   AGE
web-service               22m
```

Exactly as predicted: `STATUS Running`, `READY 0/1`, `RESTARTS 0`, and the `ENDPOINTS` column is
**empty**. The Service object still exists and still has a ClusterIP, but it has nothing to forward
to:

```bash
minikube ssh -- "curl -s -m 5 -o /dev/null -w 'HTTP %{http_code}\n' http://192.168.49.2:30130/ ; echo curl exit: \$?"
```

```text
HTTP 000
curl exit: 7
```

`curl` exit code 7 is "failed to connect" — a complete outage, caused by a one-word change to a
probe path, with every container still running happily.

Two further things this demonstrates:

- **`kubectl rollout status` returned exit code 1.** Readiness is what a rollout waits on, so a
  broken readiness probe makes a bad deploy *fail loudly* instead of silently replacing good Pods
  with broken ones. That is a feature, not a bug.
- With `maxUnavailable` defaults and a `RollingUpdate` strategy, the old Pods would have been kept
  and the outage avoided. This project uses `Recreate` (required by the RWO volume), which removes
  that safety net — the old Pods are gone before the new ones are checked.

Reverting restores service within one rollout:

```bash
kubectl apply -f 03-deployment.yaml
kubectl rollout status deploy/web-app -n hw13 --timeout=180s
kubectl get endpoints web-service -n hw13
minikube ssh -- "curl -s -m 5 -o /dev/null -w 'HTTP %{http_code}\n' http://192.168.49.2:30130/"
```

```text
deployment.apps/web-app configured
deployment "web-app" successfully rolled out
NAME          ENDPOINTS                         AGE
web-service   10.244.0.152:80,10.244.0.153:80   22m
HTTP 200
```

---

## Bonus challenge 3 — break the liveness probe

`09-deployment-broken-liveness.yaml` changes `livenessProbe.httpGet.path` to `/crash`:

```bash
kubectl apply -f 09-deployment-broken-liveness.yaml
for i in $(seq 1 14); do printf '%s  ' "$(date -u +%H:%M:%S)"; kubectl get pods -n hw13 -l app=web-app --no-headers | tr '\n' '|'; echo; sleep 15; done
```

```text
=== challenge 3: liveness -> /crash at 13:38:46 UTC ===
deployment.apps/web-app configured
13:38:46  web-app-97bc5bcf6-dbzgj   1/1   Terminating   0     14s|web-app-97bc5bcf6-r4m2t   1/1   Terminating   0     14s|
13:39:02  web-app-5654d6b4d9-j7lgj   1/1   Running   0     15s|web-app-5654d6b4d9-jh5sv   1/1   Running   0     15s|
13:39:17  web-app-5654d6b4d9-j7lgj   1/1   Running   1 (15s ago)   30s|web-app-5654d6b4d9-jh5sv   1/1   Running   1 (15s ago)   30s|
13:39:32  web-app-5654d6b4d9-j7lgj   1/1   Running   2 (15s ago)   45s|web-app-5654d6b4d9-jh5sv   1/1   Running   2 (15s ago)   45s|
13:39:47  web-app-5654d6b4d9-j7lgj   1/1   Running   3 (15s ago)   60s|web-app-5654d6b4d9-jh5sv   1/1   Running   3 (15s ago)   60s|
13:40:02  web-app-5654d6b4d9-j7lgj   0/1   CrashLoopBackOff   3 (15s ago)   75s|web-app-5654d6b4d9-jh5sv   0/1   CrashLoopBackOff   3 (15s ago)   75s|
13:40:17  web-app-5654d6b4d9-j7lgj   1/1   Running   4 (30s ago)   90s|web-app-5654d6b4d9-jh5sv   0/1   Running   4 (30s ago)   90s|
13:40:32  web-app-5654d6b4d9-j7lgj   0/1   Running   5 (5s ago)   105s|web-app-5654d6b4d9-jh5sv   0/1   Running   5 (0s ago)   105s|
13:40:47  web-app-5654d6b4d9-j7lgj   0/1   CrashLoopBackOff   5 (5s ago)    2m|web-app-5654d6b4d9-jh5sv   1/1   Running            5 (15s ago)   2m|
13:41:02  web-app-5654d6b4d9-j7lgj   0/1   CrashLoopBackOff   5 (20s ago)   2m15s|web-app-5654d6b4d9-jh5sv   0/1   CrashLoopBackOff   5 (15s ago)   2m15s|
13:41:17  web-app-5654d6b4d9-j7lgj   0/1   CrashLoopBackOff   5 (36s ago)   2m31s|web-app-5654d6b4d9-jh5sv   0/1   CrashLoopBackOff   5 (31s ago)   2m31s|
13:41:33  web-app-5654d6b4d9-j7lgj   0/1   CrashLoopBackOff   5 (51s ago)   2m46s|web-app-5654d6b4d9-jh5sv   0/1   CrashLoopBackOff   5 (46s ago)   2m46s|
13:41:48  web-app-5654d6b4d9-j7lgj   0/1   CrashLoopBackOff   5 (66s ago)   3m1s|web-app-5654d6b4d9-jh5sv   0/1   CrashLoopBackOff   5 (61s ago)   3m1s|
13:42:03  web-app-5654d6b4d9-j7lgj   0/1   CrashLoopBackOff   5 (81s ago)   3m16s|web-app-5654d6b4d9-jh5sv   0/1   CrashLoopBackOff   5 (76s ago)   3m16s|
```

The restart counter climbs every 15 seconds (`periodSeconds: 5 × failureThreshold: 3`), and after
the fifth restart the kubelet gives up restarting immediately and the Pods settle into
`CrashLoopBackOff` with a growing back-off (5s, 15s, 20s, 36s, 51s, 66s, 81s in the `(N ago)`
column).

```bash
kubectl describe pod web-app-5654d6b4d9-j7lgj -n hw13 | sed -n '/^Events:/,$p'
```

```text
Events:
  Type     Reason     Age                   From               Message
  ----     ------     ----                  ----               -------
  Normal   Scheduled  3m37s                 default-scheduler  Successfully assigned hw13/web-app-5654d6b4d9-j7lgj to minikube
  Normal   Created    117s (x6 over 3m37s)  kubelet            spec.containers{nginx}: Container created
  Normal   Started    117s (x6 over 3m37s)  kubelet            spec.containers{nginx}: Container started
  Normal   Killing    102s (x6 over 3m22s)  kubelet            spec.containers{nginx}: Container nginx failed liveness probe, will be restarted
  Warning  BackOff    98s (x6 over 2m37s)   kubelet            spec.containers{nginx}: Back-off restarting failed container nginx in pod web-app-5654d6b4d9-j7lgj_hw13(640b9404-f73d-4d21-8864-fdbc7a8414f0)
  Warning  Unhealthy  7s (x19 over 3m32s)   kubelet            spec.containers{nginx}: Liveness probe failed: HTTP probe failed with statuscode: 404
```

`Killing ... failed liveness probe, will be restarted (x6)` plus `BackOff` is the signature of a
liveness-induced crash loop. Compare with challenge 2, where `RESTARTS` never left 0.

Interestingly the Service was not completely dead during this — the two Pods crash-looped out of
phase, so at 13:40:47 one was `1/1` while the other was in back-off:

```bash
kubectl get endpoints web-service -n hw13
```

```text
NAME          ENDPOINTS         AGE
web-service   10.244.0.155:80   26m
```

One surviving endpoint. The readiness probe is doing its job of routing around the broken replica
even while liveness destroys them both in turn.

### Recovery, and the data is still intact

```bash
kubectl apply -f 03-deployment.yaml
kubectl rollout status deploy/web-app -n hw13 --timeout=180s
kubectl get pods -n hw13
kubectl get endpoints web-service -n hw13
kubectl exec -n hw13 $(kubectl get pods -n hw13 -l app=web-app -o jsonpath='{.items[0].metadata.name}') -- cat /data/student.txt
```

```text
deployment.apps/web-app configured
deployment "web-app" successfully rolled out
NAME                      READY   STATUS    RESTARTS   AGE
web-app-97bc5bcf6-dwx2q   1/1     Running   0          9s
web-app-97bc5bcf6-rzp9s   1/1     Running   0          9s
NAME          ENDPOINTS                         AGE
web-service   10.244.0.156:80,10.244.0.157:80   26m
Student: Aman Yadav, written 2026-10-07T13:17:14Z
```

The closing line is the whole mini project in one output: across four scale-outs, three scale-ins,
two deliberately broken rollouts, a dozen container restarts and several complete Pod replacements,
the file written at 13:17:14Z is still exactly where it was put. That is what a PVC buys you.

---

## Troubleshooting guide

| Issue | Check | Root cause | Fix |
| :--- | :--- | :--- | :--- |
| PVC stuck `Pending` | `kubectl describe pvc web-data -n hw13` | No default StorageClass, or the provisioner cannot serve the requested `volumeBindingMode` / access mode | `kubectl get sc`; name a class explicitly |
| HPA shows `<unknown>/50%` | `kubectl get pod -o jsonpath='{.spec.containers[0].resources}'` | Container has no `resources.requests.cpu` | Add the request. `kubectl top` working does not rule this out |
| HPA shows `<unknown>` *and* `kubectl top` fails | `kubectl get apiservice v1beta1.metrics.k8s.io` | metrics-server not installed or unhealthy | `minikube addons enable metrics-server` |
| Pods `Running` but `READY 0/1` | `kubectl describe pod` -> `Readiness probe failed` | Probe path/port wrong, or a dependency is down | Fix the path; check `kubectl get endpoints` |
| `CrashLoopBackOff`, restart count climbing | `kubectl describe pod` -> `Killing ... failed liveness probe` | Liveness path wrong, or too aggressive for the app's start time | Fix the path, or add a `startupProbe` |
| Second Pod stuck `ContainerCreating` on a multi-node cluster | `kubectl describe pod` -> `FailedAttachVolume` | RWO volume already attached to another node | StatefulSet with `volumeClaimTemplates`, or an RWX StorageClass |
| Rollout hangs forever | `kubectl rollout status` exit code | New Pods never become Ready | Readiness probe is the gate — look there first |

---

## Manifests in this folder

| File | Purpose |
| :--- | :--- |
| `01-namespace.yaml` | Namespace `hw13` with environment labels |
| `02-pvc.yaml` | `web-data`, 500Mi, RWO, class `standard` |
| `03-deployment.yaml` | 2 replicas, `Recreate`, requests/limits, PVC mount, all three probes |
| `04-service.yaml` | NodePort Service on 30130 |
| `05-hpa.yaml` | HPA 2–5 replicas, 50% CPU |
| `06-load-generator.yaml` | 3 replicas × 3 `wget` loops |
| `07-hpa-threshold-30.yaml` | Bonus 1 — same HPA at a 30% target |
| `08-deployment-broken-readiness.yaml` | Bonus 2 — readiness on `/does-not-exist` |
| `09-deployment-broken-liveness.yaml` | Bonus 3 — liveness on `/crash` |
