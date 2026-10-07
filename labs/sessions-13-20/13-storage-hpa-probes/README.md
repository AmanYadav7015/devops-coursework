# Session 13 — Kubernetes Storage, HPA & Probes

Homework for Session 13, completed against a live cluster. Nothing here is theoretical: every
command was executed, every `text` block is real terminal output, and the failures that happened
along the way are documented rather than edited out.

**Environment:** minikube v1.39.0 (docker driver, 6 CPU / 7000 MB), Kubernetes v1.37.0, containerd
2.3.4, single node `minikube`. Addons: `storage-provisioner`, `default-storageclass`, `ingress`,
`metrics-server`. All work confined to namespace `hw13`; cluster-scoped objects prefixed `hw13-`.

---

## Contents

| Folder | Task | What it proves |
| :--- | :--- | :--- |
| [`01-kubernetes-volumes/`](01-kubernetes-volumes/README.md) | Task 1 — Volumes | emptyDir, hostPath, PV, PVC, StorageClass, dynamic provisioning, reclaim policies, access modes — each applied and verified |
| [`02-hpa/`](02-hpa/README.md) | Task 2 — HPA | All nine numbered steps: 1 -> 4 replicas under load, scale back to 1, with the 5-minute stabilisation window measured |
| [`03-probes/`](03-probes/README.md) | Probes | A real readiness failure removing a Pod from a Service, a real liveness failure restarting a container, a startup probe rescuing a slow boot |
| [`04-mini-project/`](04-mini-project/README.md) | Task 3 — Mini project | PVC + HPA + all three probes in one workload, end to end, plus all three bonus challenges |

---

## The one-paragraph version

Containers are disposable, so anything that must survive one goes in a **volume**; which volume
depends on how long "survive" means — `emptyDir` lives as long as the Pod, `hostPath` as long as the
node's directory, a **PersistentVolume** as long as its reclaim policy allows. A Pod never names a PV
directly; it names a **PersistentVolumeClaim**, and a **StorageClass** lets the cluster create the PV
on demand instead of an administrator pre-making them. Separately, **HPA** keeps the replica count
proportional to load — but only if the container declares a CPU **request**, because the target is a
percentage of that request. And **probes** are how the kubelet learns the difference between "the
process is running" and "the application works": readiness gates traffic, liveness restarts
containers, startup buys a slow application time to boot.

---

## Headline results

### Task 1 — Volumes

| Experiment | Result |
| :--- | :--- |
| emptyDir, container restarted (`RESTARTS 1`) | File still present |
| emptyDir, Pod deleted and recreated | `cat: can't open '/data/message.txt': No such file or directory` |
| hostPath, Pod deleted and recreated | File still present; also visible via `minikube ssh` |
| PVC, Pod deleted and recreated | Timestamped file read back identically |
| PVC with no `storageClassName` | Captured by the **default** class, did **not** bind to the hand-made PV |
| Dynamic provisioning | `kubectl get pv` went from 1 PV to 2 with no PV manifest written |
| `reclaimPolicy: Delete` on PVC delete | PV gone, data gone |
| `reclaimPolicy: Retain` on PVC delete | PV survives as `Released`, admin must clean it up |
| RWOP claim in two Pods | Second Pod `Pending`: `PersistentVolumeClaim with ReadWriteOncePod access mode already in-use by another pod` |
| ROX claim, write attempted | **Write succeeded** — minikube does not enforce ROX |

### Task 2 — HPA

| Capture | Result |
| :--- | :--- |
| No CPU request | `TARGETS: cpu: <unknown>/50%`, `ScalingActive: False / FailedGetResourceMetric` — while `kubectl top pods` returned `1m` for the same Pod |
| Under load | `cpu: 174%/50%`, replicas `1 -> 4` (`ceil(1 × 174/50) = 4`) |
| `kubectl top pods` at steady state | 46m, 48m, 46m, 46m -> mean 46.5m = the 46% the HPA reported |
| `kubectl describe hpa` | `SuccessfulRescale  New size: 4; reason: cpu resource utilization (percentage of request) above target` |
| Load stopped | CPU hit 0% at 12:57, replicas dropped at 13:01:21 — a 4m48s wait, the default 300s scale-down stabilisation window |
| Window shortened to 30s | Same idle CPU, shrink started 20 seconds later, stepping `4 -> 2 -> 1` under a 50%-per-15s policy |

### Probes

| Capture | Result |
| :--- | :--- |
| Readiness broken on one Pod | `STATUS Running`, `READY 0/1`, **`RESTARTS 0`**, Pod IP removed from the Service endpoints |
| Readiness restored | Back in endpoints within one probe period, restart count never moved |
| Liveness broken | `RESTARTS 0 -> 1` after exactly 15s (`periodSeconds 5 × failureThreshold 3`), `Killing ... failed liveness probe, will be restarted` |
| Slow app, no startup probe | Infinite restart loop — 3 restarts in 2m16s, never finished booting |
| Same app with a startup probe | Ready at 45s, **0 restarts**, 13 of 30 allowed startup failures used |

### Task 3 — Mini project

| Capture | Result |
| :--- | :--- |
| PVC persistence | File written at `13:17:14Z` read back identically from a Pod created minutes later |
| Service | `HTTP 200` through NodePort 30130, both Pod IPs in endpoints |
| HPA scale out | `cpu: 83%/50%`, replicas `2 -> 4` |
| HPA scale in | `SuccessfulRescale  New size: 2; reason: All metrics below target`, floored at `minReplicas` |
| Bonus 1 — target 30% | Same load produced **5** replicas and `ScalingLimited: True / TooManyReplicas` |
| Bonus 2 — readiness `/does-not-exist` | Endpoints list empty, `curl` exit 7, `kubectl rollout status` exit code 1 |
| Bonus 3 — liveness `/crash` | `CrashLoopBackOff`, 5 restarts, back-off growing 5s -> 81s |

---

## What did not work, reported as it happened

1. **`volumeBindingMode: WaitForFirstConsumer` is unusable on stock minikube.** The PVC stays
   `Pending` forever with:

   ```text
   Warning  ProvisioningFailed  k8s.io/minikube-hostpath_minikube_...  failed to get target node: nodes "minikube" is forbidden: User "system:serviceaccount:kube-system:storage-provisioner" cannot get resource "nodes" in API group "" at the cluster scope
   ```

   Delayed binding requires the provisioner to read the node the Pod was scheduled to, and
   minikube's `storage-provisioner` ServiceAccount has no `get nodes` permission. Fixing it means
   editing a ClusterRole in `kube-system`, which was out of scope, so the StorageClass was recreated
   with `Immediate`. Details in [`01-kubernetes-volumes/README.md` §7.2](01-kubernetes-volumes/README.md).

2. **Task 2 never reached `maxReplicas: 5`.** Scaling the load generator from 3 to 5 replicas did not
   raise nginx's CPU: each generator's own usage dropped from ~690m to ~440m and the total stayed at
   ~2.2 cores. The single node, not nginx, was the bottleneck, so the deployment stabilised at 4. The
   `TooManyReplicas` condition was captured later in the mini project instead, by lowering the target
   to 30%.

3. **Access modes mean nothing on minikube's hostpath provisioner.** ROX, RWX and RWOP claims all
   bind successfully, and a write into a `ReadOnlyMany` volume succeeded. Only RWOP is actually
   enforced, because the kube-scheduler enforces it rather than the storage driver. A successful
   bind is not evidence that the storage supports what you asked for.

---

## Interview questions

### Storage

**1. A Pod is deleted and its data is gone. The Pod had a volume. What kind?**
`emptyDir`. Its lifetime is tied to the Pod, not the container — it survives container restarts
(proved: `RESTARTS 1`, file intact) but is deleted with the Pod (proved: `No such file or
directory`). If the data must outlive the Pod, use a PVC.

**2. What is the difference between a PV and a PVC, and why does the indirection exist?**
A PV is a cluster-scoped piece of real storage; a PVC is a namespaced *request* for storage. Pods
reference only the PVC. The indirection means the same Deployment manifest works on minikube, EKS
and AKS — the PVC says "500Mi, ReadWriteOnce" and the cluster supplies whatever that means locally.
It is also the permission boundary: developers create PVCs, administrators or a CSI driver create
PVs.

**3. A PVC asks for 500Mi and binds to a 1Gi PV. How much space does the application get?**
1Gi. Binding is not partitioning — a PVC binds to a single PV that is *at least* as big as the
request, one-to-one and exclusively, and the surplus is wasted.

**4. A PVC with no `storageClassName` is created while an `Available` PV sits unclaimed. Which does it bind to?**
Neither, usually. The `DefaultStorageClass` admission plugin stamps the default class onto the
claim, which triggers dynamic provisioning of a brand-new PV. The hand-made PV stays `Available`.
To bind to a pre-made PV you must set `storageClassName: ""` or name the class the PV carries.

**5. What is the difference between `Retain` and `Delete` reclaim policies, and what is the `Released` state?**
`Delete` destroys the PV and its backing disk when the PVC is deleted. `Retain` keeps both, moving
the PV to `Released`. A `Released` PV cannot be reused as-is: it still holds a `claimRef` to the
deleted PVC, so an administrator must delete it or clear `spec.claimRef` to return it to
`Available`. That manual step is the safety.

**6. Explain the four access modes. Which is enforced by Kubernetes itself?**
RWO = read-write by one *node* (several Pods on that node may share it). ROX = read-only by many
nodes. RWX = read-write by many nodes, needs a shared filesystem. RWOP = read-write by exactly one
*Pod*. Only RWOP is enforced by Kubernetes — the kube-scheduler refuses to place a second Pod. The
other three are matching metadata and depend entirely on the storage driver; on minikube a write
into a ROX volume succeeds.

**7. Why would a Deployment with 3 replicas and one RWO PVC work on minikube and break on EKS?**
On minikube every Pod lands on the same node, and RWO permits multiple Pods on one node. On EKS the
scheduler spreads replicas across nodes, and the second node's Pod gets stuck in
`ContainerCreating` with `FailedAttachVolume`. The correct patterns are a StatefulSet with
`volumeClaimTemplates` (one volume per replica) or an RWX class such as EFS.

**8. What is `volumeBindingMode: WaitForFirstConsumer` for?**
It delays provisioning until a Pod that uses the PVC is scheduled, so the volume is created in the
zone/node the scheduler actually chose. With `Immediate` on a multi-zone cloud cluster the volume
can be created in `us-east-1a` while the Pod needs `us-east-1c`, and the Pod never starts.

**9. Why is `hostPath` discouraged in production?**
Data is tied to one node, so a rescheduled Pod silently gets an empty directory; and it breaks
container isolation — mounting `/` or a container runtime socket effectively gives the Pod the
node. Pod Security Standards `baseline` and `restricted` forbid it. Legitimate uses are node-level
agents that are supposed to read the node.

### HPA

**10. An HPA shows `TARGETS: <unknown>/50%` but `kubectl top pods` works. What is wrong?**
The container has no `resources.requests.cpu`. `averageUtilization` is a percentage *of the
request*, so with no request there is no denominator and the controller discards the sample. The
misleading part is the event text — "no metrics returned from resource metrics API" — which sounds
like a broken metrics-server. It is not; `kubectl top` working proves the metric exists.

**11. Write the HPA replica formula.**
`desiredReplicas = ceil( currentReplicas × ( currentMetricValue / desiredMetricValue ) )`.
With 1 replica at 174% against a 50% target: `ceil(1 × 3.48) = 4`, which is what was observed.

**12. Load stops and CPU reads 0%, but replicas stay at 4 for five minutes. Is something broken?**
No. That is the scale-down stabilisation window, default 300 seconds. When shrinking, the controller
uses the *maximum* recommendation from the last 300 seconds, so one busy sample keeps replicas up.
Scale-up has a 0-second window by default. The asymmetry is deliberate: adding capacity late causes
an outage, removing it early causes thrashing and dropped connections.

**13. How do you make an HPA scale down faster, and what is the risk?**
`spec.behavior.scaleDown.stabilizationWindowSeconds`, plus `policies` to cap how many Pods or what
percentage may be removed per period. Shortening it was measured here: the same workload shrank
20 seconds after going idle instead of ~5 minutes, stepping `4 -> 2 -> 1` under a 50%-per-15s
policy. The risk is flapping on spiky traffic and killing in-flight requests.

**14. What does `ScalingLimited: True` mean and why should you alert on it?**
The recommendation was clamped by `minReplicas` or `maxReplicas`. With reason `TooManyReplicas` it
means the autoscaler wants more capacity than you allowed and the service is now degrading — in the
mini project, 38% actual against a 30% target with no replicas left to add. It is the difference
between "autoscaling is working" and "autoscaling has given up".

**15. Can HPA and VPA both target the same Deployment?**
Not on the same resource. VPA rewrites `resources.requests`, which is HPA's denominator, so the two
fight and oscillate. The supported combination is HPA on a custom or external metric (requests per
second, queue depth) with VPA on CPU/memory.

**16. Why does HPA need a Deployment and not a bare Pod?**
`scaleTargetRef` must point at something exposing the `scale` subresource — Deployment, ReplicaSet,
StatefulSet. A Pod has no replica count to change.

**17. `autoscaling/v1` vs `autoscaling/v2`?**
v1 supports a single CPU utilisation target only. v2 adds multiple metrics (the highest
recommendation wins), memory, custom and external metrics, `AverageValue` targets, and the
`behavior` block for stabilisation windows and rate policies.

### Probes

**18. What is the single most important difference between readiness and liveness?**
A readiness failure removes the Pod from the Service's endpoints and **never restarts anything**; a
liveness failure kills and restarts the container. Measured here: the readiness experiment kept
`RESTARTS 0` throughout, the liveness experiment went to `RESTARTS 1` in 15 seconds.

**19. A Pod is `Running`, `READY 0/1`, `RESTARTS 0`, and the Service returns connection refused. Diagnose it.**
Readiness is failing. The container is alive, Kubernetes has not touched it, but the Pod IP has been
pulled from the EndpointSlice — and if every replica fails, the Service has zero endpoints and
`curl` exits 7. Check `kubectl describe pod` for `Readiness probe failed` and
`kubectl get endpoints`.

**20. An application takes 90 seconds to start and keeps restarting. Fix it, and say why your fix beats the obvious one.**
Add a `startupProbe` with `periodSeconds × failureThreshold` greater than the boot time; while it
runs, readiness and liveness are suspended. The obvious fix — a large `initialDelaySeconds` on
liveness — also stops the loop, but it applies that delay to *every* restart forever, so a container
that wedges on day two goes undetected for 90 seconds. A startup probe hands over the moment the app
answers and liveness then runs at its tight cadence.

**21. Why can a liveness probe turn a slowdown into an outage?**
If the probe shares a thread pool with request handling, or checks a database, it fails under load —
and Kubernetes then restarts every replica at the worst possible moment. Liveness should test only
"is this process wedged", never dependencies; dependencies belong in readiness.

**22. How long does it take for a failing liveness probe to restart a container?**
Roughly `periodSeconds × failureThreshold` after the first failure (plus `initialDelaySeconds` on
startup). With `periodSeconds: 5, failureThreshold: 3` the measured gap was 15 seconds.

**23. A container with no readiness probe — when is it Ready?**
The moment it starts. Kubernetes has nothing to judge it on. This was visible in the startup-probe
test: a Pod reported `READY 1/1` while its application was not even listening on its port.

**24. What probe mechanisms exist, and when would you use `exec` over `httpGet`?**
`httpGet`, `tcpSocket`, `exec` and `grpc`. `exec` for workloads with no network endpoint — a batch
worker, a queue consumer — where health means "this file exists" or "this CLI returns 0". It is the
most expensive option, since it forks a process on every check.

### Integration

**25. Design a stateful web service that autoscales. What breaks naively, and what do you change?**
Naively: one Deployment, one RWO PVC, an HPA to 5. It works on one node and deadlocks the moment the
scheduler spreads Pods across nodes — `FailedAttachVolume`. Change it to a StatefulSet with
`volumeClaimTemplates` so each replica gets its own volume, or move shared state to an RWX class or
out of the filesystem entirely (object storage, a database). Keep `Recreate` only if a single shared
RWO volume is genuinely required, and know it costs you the rolling-update safety net.

**26. Why does this project use `strategy: Recreate` instead of `RollingUpdate`?**
With a single `ReadWriteOnce` PVC, a rolling update would start a new Pod that must attach the same
volume while the old Pod still holds it. `Recreate` terminates the old Pods first. The cost is
visible in bonus challenge 2: a broken readiness probe took the Service to zero endpoints, because
there were no old Pods left to serve traffic.

**27. How does a broken readiness probe interact with a deployment rollout?**
It stops it. `kubectl rollout status` waits on readiness and returned exit code 1 after the timeout,
with the new Pods at `0/1`. That is the intended behaviour — readiness is the gate that prevents a
bad build from silently replacing a good one, and it is why CI should check that exit code.

---

## Full command reference used in this homework

```bash
# storage
kubectl get pv
kubectl get pvc -n hw13
kubectl get sc
kubectl describe pv <name>
kubectl describe pvc <name> -n hw13
kubectl describe sc standard
minikube ssh -- "sudo ls /tmp/hostpath-provisioner/hw13/<pvc>"

# autoscaling
kubectl get hpa -n hw13
kubectl get hpa -n hw13 -w
kubectl describe hpa <name> -n hw13
kubectl top pods -n hw13
kubectl top nodes
kubectl explain hpa.spec.behavior.scaleDown.stabilizationWindowSeconds
kubectl get events -n hw13 --field-selector involvedObject.name=<hpa>

# probes and health
kubectl get pods -n hw13 -o wide
kubectl describe pod <name> -n hw13
kubectl get endpoints <svc> -n hw13
kubectl get endpointslices -n hw13 -l kubernetes.io/service-name=<svc>
kubectl rollout status deploy/<name> -n hw13
kubectl logs <pod> -n hw13
```

---

## Cleanup

See [CLEANUP.md](CLEANUP.md) for the teardown and its verification.

## References

- Volumes — https://kubernetes.io/docs/concepts/storage/volumes/
- Persistent Volumes — https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- Storage Classes — https://kubernetes.io/docs/concepts/storage/storage-classes/
- Horizontal Pod Autoscaling — https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- Probes — https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-probes
