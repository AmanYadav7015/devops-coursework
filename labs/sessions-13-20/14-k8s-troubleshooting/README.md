# Session 14 — Kubernetes Troubleshooting

Homework submission. Everything below was run against a live cluster and every `text` block is
copy-pasted real output. Nothing is illustrative.

All work is isolated in the namespace `hw14`, which is deleted at the end.

---

## Environment

```bash
kubectl get nodes -o wide
kubectl get storageclass
```

```text
NAME       STATUS   ROLES           AGE   VERSION   INTERNAL-IP    EXTERNAL-IP   OS-IMAGE                         KERNEL-VERSION             CONTAINER-RUNTIME
minikube   Ready    control-plane   19d   v1.37.0   192.168.49.2   <none>        Debian GNU/Linux 12 (bookworm)   6.12.76-linuxkit (arm64)   containerd://2.3.4

NAME                 PROVISIONER                RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION   AGE
standard (default)   k8s.io/minikube-hostpath   Delete          Immediate           false                  19d
```

Single-node minikube, Kubernetes v1.37.0, containerd runtime, metrics-server enabled so `kubectl top`
works. One storage class, `standard`, with `Immediate` volume binding — that detail matters for the
unbound-PVC scenario later.

```bash
kubectl create namespace hw14
kubectl get ns hw14
```

```text
namespace/hw14 created
NAME   STATUS   AGE
hw14   Active   0s
```

---

## Folder layout

```text
14-k8s-troubleshooting/
├── README.md
├── 01-commands/            Task 1 — a healthy pod and a crashing pod to practise commands on
│   ├── healthy-pod.yaml
│   └── crasher-pod.yaml
├── 02-scenarios/           Task 2 — one folder per failure mode, broken.yaml + fixed.yaml
│   ├── 01-crashloopbackoff/
│   ├── 02-imagepullbackoff/
│   ├── 03-errimagepull/
│   ├── 04-pending-resources/
│   ├── 05-pending-nodeselector/
│   ├── 06-pending-unbound-pvc/
│   ├── 07-containercreating/
│   ├── 08-service-connectivity/
│   ├── 09-dns/
│   ├── 10-pod-networking/
│   ├── 11-configuration/
│   └── 12-oomkilled/
└── 03-mini-project/        Task 3 — the provided troubleshooting challenge
    ├── deployment.yaml
    ├── service.yaml
    ├── service-broken.yaml
    ├── broken-pod.yaml
    └── fixed-pod.yaml
```

Every scenario ships a broken manifest and a fixed one so the failure is reproducible from a clean
cluster, not just described. Most are `broken.yaml` / `fixed.yaml`; the Service scenario splits into
`deployment.yaml` plus three Service variants (wrong selector, wrong `targetPort`, correct), and the
DNS scenario needs no broken manifest at all — the failures there are wrong *names*, demonstrated
against correctly-deployed Services from the `netshoot` debug pod.

---

## Task 1 — The troubleshooting command set

Two pods carry this section: `demo-web` (healthy nginx) and `demo-crasher` (a busybox container that
prints a startup banner, sleeps 15s and then exits 3).

```bash
kubectl apply -f 01-commands/
```

```text
pod/demo-crasher created
pod/demo-web created
```

### 1.1 `kubectl get` — what is the state right now?

```bash
kubectl get pods -n hw14
```

```text
NAME           READY   STATUS    RESTARTS      AGE
demo-crasher   0/1     Error     2 (19s ago)   20s
demo-web       1/1     Running   0             20s
```

This is always the first command. Four columns answer four questions: `READY` says how many
containers passed their readiness check out of how many exist, `STATUS` is the one-word verdict,
`RESTARTS` with a timestamp in brackets tells you whether the problem is happening *now* or happened
once an hour ago, and `AGE` tells you whether this is a fresh rollout or something long-running that
just broke. `demo-crasher` showing `0/1 Error 2 (19s ago)` already says: it starts, it dies, and it
died 19 seconds ago, so it is still dying.

(Two restarts in twenty seconds: this capture is from the first version of `crasher-pod.yaml`, which
exited immediately. The manifest on disk now sleeps 15 seconds before exiting — section 1.5 explains
why that change was necessary and what it cost.)

### 1.2 `kubectl get -o wide` — where is it and what IP does it have?

```bash
kubectl get pods -n hw14 -o wide
```

```text
NAME           READY   STATUS    RESTARTS      AGE   IP            NODE       NOMINATED NODE   READINESS GATES
demo-crasher   0/1     Error     2 (24s ago)   25s   10.244.0.27   minikube   <none>           <none>
demo-web       1/1     Running   0             25s   10.244.0.28   minikube   <none>           <none>
```

`-o wide` adds the pod IP and the node. Reach for it when the symptom is network-shaped ("service
returns nothing") because the pod IP is what you compare against the Service's endpoint list, or when
the symptom is node-shaped ("only some replicas are broken") because `NODE` tells you whether all the
sick pods landed on one machine. `NOMINATED NODE` is populated only when preemption is in flight.

Adding `--show-labels` is the fastest way to answer "why doesn't my Service select this pod":

```bash
kubectl get pod demo-web -n hw14 -o wide --show-labels
```

```text
NAME       READY   STATUS    RESTARTS   AGE     IP            NODE       NOMINATED NODE   READINESS GATES   LABELS
demo-web   1/1     Running   0          5m27s   10.244.0.28   minikube   <none>           <none>            app=demo-web,tier=frontend
```

### 1.3 `kubectl describe` — what did Kubernetes try to do?

```bash
kubectl describe pod demo-crasher -n hw14
```

```text
Name:             demo-crasher
Namespace:        hw14
Priority:         0
Service Account:  default
Node:             minikube/192.168.49.2
Start Time:       Wed, 07 Oct 2026 18:01:31 +0530
Labels:           app=demo-crasher
Annotations:      <none>
Status:           Running
IP:               10.244.0.37
IPs:
  IP:  10.244.0.37
Containers:
  crasher:
    Container ID:  containerd://d1c1d874e1bcdf32b97fa45cd255735ddcd95647a8d3eb0d0dcdf5e3d657da0c
    Image:         busybox:1.36
    Image ID:      docker.io/library/busybox@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662
    Port:          <none>
    Host Port:     <none>
    Command:
      sh
      -c
      echo "boot: starting payment-worker v1.4.2"
      echo "boot: reading config from /etc/app"
      sleep 15
      echo "FATAL: cannot open /etc/app/app.conf: No such file or directory" >&2
      exit 3

    State:          Terminated
      Reason:       Error
      Exit Code:    3
      Started:      Wed, 07 Oct 2026 18:04:06 +0530
      Finished:     Wed, 07 Oct 2026 18:04:21 +0530
    Last State:     Terminated
      Reason:       Error
      Exit Code:    3
      Started:      Wed, 07 Oct 2026 18:03:01 +0530
      Finished:     Wed, 07 Oct 2026 18:03:16 +0530
    Ready:          False
    Restart Count:  4
    Environment:    <none>
    Mounts:
      /var/run/secrets/kubernetes.io/serviceaccount from kube-api-access-4tpht (ro)
Conditions:
  Type                        Status
  PodReadyToStartContainers   True
  Initialized                 True
  Ready                       False
  ContainersReady             False
  PodScheduled                True
Volumes:
  kube-api-access-4tpht:
    Type:                    Projected (a volume that contains injected data from multiple sources)
    TokenExpirationSeconds:  3607
    ConfigMapName:           kube-root-ca.crt
    Optional:                false
    DownwardAPI:             true
QoS Class:                   BestEffort
Node-Selectors:              <none>
Tolerations:                 node.kubernetes.io/not-ready:NoExecute op=Exists for 300s
                             node.kubernetes.io/unreachable:NoExecute op=Exists for 300s
Events:
  Type     Reason     Age                  From               Message
  ----     ------     ----                 ----               -------
  Normal   Scheduled  3m33s                default-scheduler  Successfully assigned hw14/demo-crasher to minikube
  Normal   Pulled     58s (x5 over 3m32s)  kubelet            spec.containers{crasher}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Normal   Created    58s (x5 over 3m32s)  kubelet            spec.containers{crasher}: Container created
  Normal   Started    58s (x5 over 3m32s)  kubelet            spec.containers{crasher}: Container started
  Warning  BackOff    42s (x4 over 3m1s)   kubelet            spec.containers{crasher}: Back-off restarting failed container crasher in pod demo-crasher_hw14(f07a20bb-33a7-428f-baa7-f2f1a73c2006)
```

`describe` is `get` plus everything the control plane knows. The four blocks that earn their keep:

- **`State` / `Last State`** — `Exit Code: 3` and the `Started`/`Finished` pair 15 seconds apart. The
  container is not failing to start; it starts fine and then quits. That rules out image and config
  problems and points straight at the application.
- **`Restart Count: 4`** — confirms a loop rather than a one-off.
- **`QoS Class: BestEffort`** — no requests or limits set. Useful to know before blaming the scheduler.
- **`Events`** — the kubelet's narrative. `Pulled → Created → Started → BackOff`, repeating `x5`.

Note that `describe` only keeps events for about an hour (the default event TTL), so on an old
incident the `Events` block can be empty and you fall back on `State`/`Last State`.

### 1.4 `kubectl logs` — what did the application say?

```bash
kubectl logs demo-crasher -n hw14
```

```text
FATAL: cannot open /etc/app/app.conf: No such file or directory
boot: starting payment-worker v1.4.2
boot: reading config from /etc/app
```

`describe` told us the container exits 3; only `logs` tells us *why*. Here the application states its
own root cause: a missing config file. (stdout and stderr are separate streams and the kubelet
interleaves them by arrival, which is why the FATAL line appears out of order — not a bug.)

### 1.5 `kubectl logs --previous` — the single most useful move in a crash loop

When a container is in `CrashLoopBackOff`, the container you can see is either dead or freshly
restarted. Plain `logs` shows the *current* attempt, which is often empty or just the banner. The
evidence you want is in the attempt that died.

```bash
kubectl logs demo-crasher -n hw14 --previous
```

```text
boot: starting payment-worker v1.4.2
boot: reading config from /etc/app
FATAL: cannot open /etc/app/app.conf: No such file or directory
```

That is the complete story of the failed run, in order, including the last line before `exit 3`.

One real caveat discovered while building this lab. The first version of `demo-crasher` crashed in
under a second. Against that pod, `--previous` failed:

```bash
kubectl logs demo-crasher -n hw14 --previous
```

```text
unable to retrieve container logs for containerd://f48d3cea8312e2b2846d264898e882aa51ad0b1fb3a70ef80429cdb11d45c8ac
```

The dead container had already been garbage-collected by the kubelet, taking its log file with it.
The lesson is operational: in a fast crash loop you have a short window to grab `--previous`, so run
it early. If it is already gone, the fallbacks are the `Last State` block in `describe` (which
survives, and at least gives you the exit code) or a log shipper that got the lines off the node.

Exit codes worth memorising when reading `Last State`:

| Exit code | Meaning |
| :--- | :--- |
| 0 | Clean exit — with `restartPolicy: Always` this still restarts |
| 1 | Generic application error — read the logs |
| 2 | Shell misuse / bad command-line argument |
| 126 | Command found but not executable (permissions, wrong architecture) |
| 127 | Command not found — usually a typo in `command:` or a missing binary in a distroless image |
| 137 | SIGKILL (128+9) — almost always OOMKilled, or a failed liveness probe plus a hung shutdown |
| 139 | SIGSEGV (128+11) — segfault |
| 143 | SIGTERM (128+15) — normal graceful shutdown |

### 1.6 `kubectl exec` — what does the world look like from inside?

```bash
kubectl exec demo-web -n hw14 -- sh -c 'hostname; id; nginx -v 2>&1; cat /etc/resolv.conf'
```

```text
demo-web
uid=0(root) gid=0(root) groups=0(root),1(bin),2(daemon),3(sys),4(adm),6(disk),10(wheel),11(floppy),20(dialout),26(tape),27(video)
nginx version: nginx/1.27.5
search hw14.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5
```

`exec` is for questions the control plane cannot answer: is the file actually mounted, is the binary
the version I think it is, what user am I, what does DNS resolution look like from here. That
`/etc/resolv.conf` is the foundation of every DNS scenario below — `nameserver 10.96.0.10` is the
CoreDNS Service, and the `search` list is why a bare `shop-api-svc` resolves inside `hw14` but not
from another namespace.

The second thing `exec` is for is proving the app works locally, which splits "the app is broken"
from "the routing to the app is broken":

```bash
kubectl exec demo-web -n hw14 -- wget -qO- -S http://localhost 2>&1 | head -9
```

```text
  HTTP/1.1 200 OK
  Server: nginx/1.27.5
  Date: Wed, 07 Oct 2026 12:35:07 GMT
  Content-Type: text/html
  Content-Length: 615
  Last-Modified: Wed, 16 Apr 2025 12:55:34 GMT
  Connection: close
  ETag: "67ffa8c6-267"
  Accept-Ranges: bytes
```

`exec` only works on a *running* container. In `CrashLoopBackOff` there is nothing to exec into —
that is exactly when you use `logs --previous` instead, or `kubectl debug` with an ephemeral container.

### 1.7 `kubectl events` — the cluster's timeline

Scoped to a single object, which is what you almost always want:

```bash
kubectl events -n hw14 --for pod/demo-crasher
```

```text
LAST SEEN               TYPE      REASON      OBJECT             MESSAGE
5m20s                   Normal    Scheduled   Pod/demo-crasher   Successfully assigned hw14/demo-crasher to minikube
4m35s (x4 over 5m20s)   Normal    Pulled      Pod/demo-crasher   Container image "busybox:1.36" already present on machine and can be accessed by the pod
4m35s (x4 over 5m20s)   Normal    Created     Pod/demo-crasher   Container created
4m35s (x4 over 5m19s)   Normal    Started     Pod/demo-crasher   Container started
4m34s (x3 over 5m18s)   Warning   BackOff     Pod/demo-crasher   Back-off restarting failed container crasher in pod demo-crasher_hw14(5e350494-e7ea-4a0e-8aa5-d983d4eaf992)
3m39s                   Normal    Scheduled   Pod/demo-crasher   Successfully assigned hw14/demo-crasher to minikube
64s (x5 over 3m38s)     Normal    Pulled      Pod/demo-crasher   Container image "busybox:1.36" already present on machine and can be accessed by the pod
64s (x5 over 3m38s)     Normal    Created     Pod/demo-crasher   Container created
64s (x5 over 3m38s)     Normal    Started     Pod/demo-crasher   Container started
48s (x4 over 3m7s)      Warning   BackOff     Pod/demo-crasher   Back-off restarting failed container crasher in pod demo-crasher_hw14(f07a20bb-33a7-428f-baa7-f2f1a73c2006)
```

`--for pod/demo-crasher` filters by `involvedObject`, so one noisy pod does not drown in a busy
namespace. The two `Scheduled` lines and two different pod UIDs in the `BackOff` messages are a real
artefact: this pod was deleted and recreated during the lab, and events from the old UID are still
within their TTL. That is a genuinely useful signal in production too — it tells you the pod you are
looking at is not the pod that logged the earlier failure.

Namespace-wide and time-ordered, for "something broke in the last five minutes but I don't know what":

```bash
kubectl get events -n hw14 --sort-by=.lastTimestamp | tail -15
```

```text
4m35s       Normal    Pulled      pod/demo-crasher          Container image "busybox:1.36" already present on machine and can be accessed by the pod
4m35s       Normal    Created     pod/demo-crasher          Container created
4m35s       Normal    Started     pod/demo-crasher          Container started
4m34s       Warning   BackOff     pod/demo-crasher          Back-off restarting failed container crasher in pod demo-crasher_hw14(5e350494-e7ea-4a0e-8aa5-d983d4eaf992)
3m39s       Normal    Scheduled   pod/demo-crasher          Successfully assigned hw14/demo-crasher to minikube
69s         Normal    Scheduled   pod/errimagepull-broken   Successfully assigned hw14/errimagepull-broken to minikube
64s         Normal    Started     pod/demo-crasher          Container started
64s         Normal    Created     pod/demo-crasher          Container created
64s         Normal    Pulled      pod/demo-crasher          Container image "busybox:1.36" already present on machine and can be accessed by the pod
48s         Warning   BackOff     pod/demo-crasher          Back-off restarting failed container crasher in pod demo-crasher_hw14(f07a20bb-33a7-428f-baa7-f2f1a73c2006)
25s         Normal    Pulling     pod/errimagepull-broken   Pulling image "nginx:1.27-alpine-typo"
24s         Warning   Failed      pod/errimagepull-broken   Failed to pull image "nginx:1.27-alpine-typo": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:1.27-alpine-typo": failed to resolve reference "docker.io/library/nginx:1.27-alpine-typo": docker.io/library/nginx:1.27-alpine-typo: not found
24s         Warning   Failed      pod/errimagepull-broken   Error: ErrImagePull
8s          Normal    BackOff     pod/errimagepull-broken   Back-off pulling image "nginx:1.27-alpine-typo"
8s          Warning   Failed      pod/errimagepull-broken   Error: ImagePullBackOff
```

`kubectl get events` is unsorted by default, which makes it near-useless; `--sort-by=.lastTimestamp`
is what makes it a timeline. `kubectl events` (the newer verb) sorts for you.

### 1.8 `kubectl explain` — the schema, offline

```bash
kubectl explain pod.spec.containers.livenessProbe
```

```text
KIND:       Pod
VERSION:    v1

FIELD: livenessProbe <Probe>


DESCRIPTION:
    Periodic probe of container liveness. Container will be restarted if the
    probe fails. Cannot be updated. More info:
    https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle#container-probes
    Probe describes a health check to be performed against a container to
    determine whether it is alive or ready to receive traffic.

FIELDS:
  exec	<ExecAction>
    Exec specifies a command to execute in the container.

  failureThreshold	<integer>
    Minimum consecutive failures for the probe to be considered failed after
    having succeeded. Defaults to 3. Minimum value is 1.

  grpc	<GRPCAction>
    GRPC specifies a GRPC HealthCheckRequest.

  httpGet	<HTTPGetAction>
    HTTPGet specifies an HTTP GET request to perform.

  initialDelaySeconds	<integer>
    Number of seconds after the container has started before liveness probes are
    initiated. More info:
    https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle#container-probes

  periodSeconds	<integer>
    How often (in seconds) to perform the probe. Default to 10 seconds. Minimum
    value is 1.

  successThreshold	<integer>
    Minimum consecutive successes for the probe to be considered successful
    after having failed. Defaults to 1. Must be 1 for liveness and startup.
    Minimum value is 1.
```

This is served by the API server you are actually talking to, so it reflects *this* cluster's
version and includes CRDs. That makes it more trustworthy than a web search when you are debugging
"why is this field being ignored" — if `explain` does not list the field, the API server is silently
dropping it.

`--recursive` flattens the whole subtree with no prose, which is the form you want when you are
checking a field path rather than reading documentation:

```bash
kubectl explain pod.spec.containers.resources --recursive
```

```text
KIND:       Pod
VERSION:    v1

FIELD: resources <ResourceRequirements>


DESCRIPTION:
    Compute Resources required by this container. Cannot be updated. More info:
    https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
    ResourceRequirements describes the compute resource requirements.

FIELDS:
  claims	<[]ResourceClaim>
    name	<string> -required-
    request	<string>
  limits	<map[string]Quantity>
  requests	<map[string]Quantity>
```

Three lines confirm the thing people get wrong constantly: it is `resources.requests` and
`resources.limits`, both maps of quantity, and there is no `resources.cpu`. A typo'd field name here
is the usual reason a pod that "has limits set" still gets OOMKilled.

### 1.9 `kubectl top` — actual consumption, not what you asked for

```bash
kubectl top nodes
kubectl top pods -n hw14 --containers
```

```text
NAME       CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)
minikube   146m         0%       1809Mi          22%

POD        NAME   CPU(cores)   MEMORY(bytes)
demo-web   web    0m           11Mi
```

`describe` shows requests and limits — what you *declared*. `top` shows what is being *used*. The gap
between them is where capacity incidents live: a pod requesting 1Gi and using 40Mi is why the
scheduler says `Insufficient memory` on a node that looks idle.

Note `demo-crasher` is missing from `top pods`. metrics-server only reports on running containers,
so a crash-looping pod has no metrics — another reason `top` is a capacity tool, not a triage tool.
It needs metrics-server installed; without it the command returns
`error: Metrics API not available`.

---

## Task 2 — Nine failure modes, reproduced and fixed

Every scenario below follows the same six steps: **identify → investigate → root cause → fix →
verify → document**. Each ships a `broken.yaml` and a `fixed.yaml`, so the failure can be recreated
on any cluster rather than taken on trust.

A note on naming: the broken and fixed pods run side by side with different names (`crashloop-broken`
and `crashloop-fixed`), so both states are visible in a single `kubectl get pods` at any point.

---

### Scenario 1 — CrashLoopBackOff

Files: `02-scenarios/01-crashloopbackoff/{broken,fixed}.yaml`

**1. Identify.** A worker that needs `DATABASE_URL` is deployed without it.

```bash
kubectl apply -f 02-scenarios/01-crashloopbackoff/broken.yaml
kubectl get pod crashloop-broken -n hw14
```

```text
pod/crashloop-broken created
NAME               READY   STATUS             RESTARTS      AGE
crashloop-broken   0/1     CrashLoopBackOff   4 (76s ago)   2m53s
```

`CrashLoopBackOff` is not an error in itself — it is the kubelet saying "this container has died
enough times that I am now deliberately waiting before I try again". The backoff doubles: 10s, 20s,
40s, 80s, 160s, capped at 5 minutes. A rising `RESTARTS` count with a recent timestamp is the tell.

**2. Investigate.**

```bash
kubectl describe pod crashloop-broken -n hw14
```

```text
Events:
  Type     Reason     Age                  From               Message
  ----     ------     ----                 ----               -------
  Normal   Scheduled  2m35s                default-scheduler  Successfully assigned hw14/crashloop-broken to minikube
  Normal   Pulled     58s (x5 over 2m34s)  kubelet            spec.containers{worker}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Normal   Created    58s (x5 over 2m34s)  kubelet            spec.containers{worker}: Container created
  Normal   Started    58s (x5 over 2m34s)  kubelet            spec.containers{worker}: Container started
  Warning  BackOff    58s (x4 over 2m32s)  kubelet            spec.containers{worker}: Back-off restarting failed container worker in pod crashloop-broken_hw14(4c4c0e10-354e-46e9-9ba3-7089c4964635)
```

The events say the image pulled fine and the container *started* five times. So this is not an image
problem and not a scheduling problem — Kubernetes did its job and the process chose to exit. The
events give no application detail, which is exactly the point: for CrashLoopBackOff, `describe` tells
you *where* the fault is, not *what* it is.

```bash
kubectl get pod crashloop-broken -n hw14 \
  -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}{" exitCode="}{.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}'
```

```text
Error exitCode=1
```

Exit 1, not 137 — so it is an application error, not an OOM kill.

```bash
kubectl logs crashloop-broken -n hw14 --previous
```

```text
[FATAL] DATABASE_URL environment variable is MISSING
payment-worker: starting
```

**3. Root cause.** The container's entrypoint checks for `DATABASE_URL` and calls `exit 1` when it is
unset. The manifest has no `env:` block at all, so the variable is never injected. The application is
behaving correctly; the manifest is incomplete.

**4. Fix.** Add the environment variable (`02-scenarios/01-crashloopbackoff/fixed.yaml`):

```yaml
env:
  - name: DATABASE_URL
    value: postgres://payments-db.hw14.svc.cluster.local:5432/payments
```

```bash
kubectl apply -f 02-scenarios/01-crashloopbackoff/fixed.yaml
```

**5. Verify.**

```bash
kubectl get pod crashloop-fixed -n hw14
kubectl logs crashloop-fixed -n hw14
```

```text
NAME              READY   STATUS    RESTARTS   AGE
crashloop-fixed   1/1     Running   0          4s

payment-worker: starting
payment-worker: connected to postgres://payments-db.hw14.svc.cluster.local:5432/payments
```

`1/1 Running` with `RESTARTS 0` and the application's own success line. Note that a pod spec is
largely immutable — you cannot `kubectl edit` an env var into a running pod. In production this is
why you fix the Deployment and let it roll a new ReplicaSet.

**6. Document.** CrashLoopBackOff = the container starts and then exits. The decision tree is: read
the exit code from `Last State` first (137 → memory, 127 → bad command, 1 → application), then read
`logs --previous` for the message. Never restart it hoping it sticks; the backoff is a symptom, not
the disease.

---

### Scenario 2 — ImagePullBackOff

Files: `02-scenarios/02-imagepullbackoff/{broken,fixed}.yaml`

**1. Identify.** An image reference that does not exist in any registry we can reach.

```bash
kubectl apply -f 02-scenarios/02-imagepullbackoff/broken.yaml
kubectl get pod imagepullbackoff-broken -n hw14
```

```text
pod/imagepullbackoff-broken created
NAME                      READY   STATUS             RESTARTS   AGE
imagepullbackoff-broken   0/1     ImagePullBackOff   0          2m35s
```

`RESTARTS 0` is the distinguishing feature against CrashLoopBackOff. The container has never run, so
there is nothing to restart. `kubectl logs` on this pod returns nothing useful for the same reason.

**2. Investigate.**

```bash
kubectl describe pod imagepullbackoff-broken -n hw14
```

```text
Events:
  Type     Reason     Age                  From               Message
  ----     ------     ----                 ----               -------
  Normal   Scheduled  2m35s                default-scheduler  Successfully assigned hw14/imagepullbackoff-broken to minikube
  Normal   Pulling    58s (x4 over 2m34s)  kubelet            spec.containers{api}: Pulling image "yatri-api-service:v999-invalid"
  Warning  Failed     57s (x4 over 2m33s)  kubelet            spec.containers{api}: Failed to pull image "yatri-api-service:v999-invalid": failed to pull and unpack image "docker.io/library/yatri-api-service:v999-invalid": failed to resolve reference "docker.io/library/yatri-api-service:v999-invalid": pull access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed
  Warning  Failed     57s (x4 over 2m33s)  kubelet            spec.containers{api}: Error: ErrImagePull
  Normal   BackOff    13s (x8 over 2m32s)  kubelet            spec.containers{api}: Back-off pulling image "yatri-api-service:v999-invalid"
  Warning  Failed     13s (x8 over 2m32s)  kubelet            spec.containers{api}: Error: ImagePullBackOff
```

**3. Root cause.** Two things are visible in that one message and both matter.

First, `docker.io/library/yatri-api-service` — the kubelet expanded the bare name `yatri-api-service`
into Docker Hub's *official images* namespace, because an image reference with no registry and no
org defaults to `docker.io/library/`. A private image almost always needs the full path
(`ghcr.io/org/yatri-api-service:1.2.3`).

Second, `pull access denied, repository does not exist or may require authorization`. The registry
deliberately refuses to distinguish "does not exist" from "exists but you are not allowed to see it",
to avoid leaking the names of private repositories. So this single message covers three different
real-world root causes:

| Real cause | How to tell them apart |
| :--- | :--- |
| Typo in image name or org | `docker manifest inspect <image>` from your laptop also fails |
| Private registry, no `imagePullSecrets` | `kubectl get pod -o yaml \| grep imagePullSecrets` is empty |
| `imagePullSecrets` present but wrong/expired | Secret exists; `kubectl get secret <name> -o jsonpath='{.data.\.dockerconfigjson}' \| base64 -d` shows stale credentials |

**4. Fix.** Point at an image that exists and is reachable (`fixed.yaml` uses `nginx:1.27-alpine`).
In a real incident the fix is one of: correct the name, add `imagePullSecrets`, or push the tag.

**5. Verify.**

```bash
kubectl get pods -n hw14 -l scenario=imagepullbackoff
```

```text
imagepullbackoff-broken   0/1   ImagePullBackOff   0     5m49s
imagepullbackoff-fixed    1/1   Running            0     3m
```

**6. Document.** ImagePullBackOff never produces logs and never increments `RESTARTS`. The whole
answer is in `describe`'s events, and specifically in the fully-expanded image path the kubelet
prints back at you — that expanded path is frequently not the path the author thought they wrote.

---

### Scenario 3 — ErrImagePull, and how it differs from ImagePullBackOff

Files: `02-scenarios/03-errimagepull/{broken,fixed}.yaml`

These two are not different problems. They are two states of the same problem, and the difference is
purely *when you looked*. The manifest here uses a valid repository with an invalid tag
(`nginx:1.27-alpine-typo`), which produces a cleaner `NotFound` than the previous scenario.

**1. Identify — catching the transition.** Applying the pod and polling every two seconds:

```bash
kubectl apply -f 02-scenarios/03-errimagepull/broken.yaml
for i in $(seq 1 25); do printf "t+%02ds  " $((i*2)); kubectl get pod errimagepull-broken -n hw14 --no-headers; sleep 2; done
```

```text
pod/errimagepull-broken created
t+02s  errimagepull-broken   0/1   ContainerCreating   0     0s
t+04s  errimagepull-broken   0/1   ContainerCreating   0     2s
t+06s  errimagepull-broken   0/1   ErrImagePull   0     4s
t+08s  errimagepull-broken   0/1   ErrImagePull   0     6s
t+10s  errimagepull-broken   0/1   ErrImagePull   0     8s
t+12s  errimagepull-broken   0/1   ErrImagePull   0     10s
t+14s  errimagepull-broken   0/1   ErrImagePull   0     12s
t+16s  errimagepull-broken   0/1   ErrImagePull   0     15s
t+18s  errimagepull-broken   0/1   ErrImagePull   0     17s
t+20s  errimagepull-broken   0/1   ImagePullBackOff   0     19s
t+22s  errimagepull-broken   0/1   ImagePullBackOff   0     21s
t+24s  errimagepull-broken   0/1   ImagePullBackOff   0     23s
t+26s  errimagepull-broken   0/1   ImagePullBackOff   0     25s
t+28s  errimagepull-broken   0/1   ImagePullBackOff   0     27s
t+30s  errimagepull-broken   0/1   ImagePullBackOff   0     29s
t+32s  errimagepull-broken   0/1   ErrImagePull   0     31s
t+34s  errimagepull-broken   0/1   ErrImagePull   0     33s
t+36s  errimagepull-broken   0/1   ErrImagePull   0     35s
t+38s  errimagepull-broken   0/1   ErrImagePull   0     37s
t+40s  errimagepull-broken   0/1   ErrImagePull   0     39s
t+42s  errimagepull-broken   0/1   ErrImagePull   0     41s
t+44s  errimagepull-broken   0/1   ErrImagePull   0     43s
t+46s  errimagepull-broken   0/1   ImagePullBackOff   0     45s
t+48s  errimagepull-broken   0/1   ImagePullBackOff   0     47s
t+50s  errimagepull-broken   0/1   ImagePullBackOff   0     50s
```

This is the whole distinction, in real timestamps:

```text
ContainerCreating  (0-4s)    kubelet is trying the pull for the first time
       │
       ▼
ErrImagePull       (4-19s)   the pull just failed. This is the LIVE error.
       │
       ▼
ImagePullBackOff   (19-31s)  kubelet is sleeping before retrying. This is the WAIT.
       │
       ▼
ErrImagePull       (31-45s)  it woke up, retried, failed again
       │
       ▼
ImagePullBackOff   (45s+)    sleeping longer this time
```

`ErrImagePull` means **a pull attempt just failed**. `ImagePullBackOff` means **the kubelet is
waiting before the next attempt**. The pod oscillates between the two forever, with the backoff
interval growing each round until it caps. If a colleague reports `ErrImagePull` and you see
`ImagePullBackOff` thirty seconds later, nothing changed — you just caught a different phase.

**2. Investigate.** Both phases carry the same underlying message; `describe` shows both reasons
side by side because it keeps the whole event history:

```bash
kubectl describe pod errimagepull-broken -n hw14
```

```text
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  57s                default-scheduler  Successfully assigned hw14/errimagepull-broken to minikube
  Normal   BackOff    26s (x2 over 54s)  kubelet            spec.containers{web}: Back-off pulling image "nginx:1.27-alpine-typo"
  Warning  Failed     26s (x2 over 54s)  kubelet            spec.containers{web}: Error: ImagePullBackOff
  Normal   Pulling    13s (x3 over 57s)  kubelet            spec.containers{web}: Pulling image "nginx:1.27-alpine-typo"
  Warning  Failed     12s (x3 over 55s)  kubelet            spec.containers{web}: Failed to pull image "nginx:1.27-alpine-typo": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:1.27-alpine-typo": failed to resolve reference "docker.io/library/nginx:1.27-alpine-typo": docker.io/library/nginx:1.27-alpine-typo: not found
  Warning  Failed     12s (x3 over 55s)  kubelet            spec.containers{web}: Error: ErrImagePull
```

Reading the counters: `Pulling x3`, `ErrImagePull x3`, `ImagePullBackOff x2`. Three attempts, two
naps. The `BackOff` reason is `Normal`, not `Warning`, because backing off is correct kubelet
behaviour.

The pod's own status field merges both into one string, which is where the clearest summary lives:

```bash
kubectl get pod errimagepull-broken -n hw14 \
  -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}{"  |  "}{.status.containerStatuses[0].state.waiting.message}{"\n"}'
```

```text
ImagePullBackOff  |  Back-off pulling image "nginx:1.27-alpine-typo": ErrImagePull: rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:1.27-alpine-typo": failed to resolve reference "docker.io/library/nginx:1.27-alpine-typo": docker.io/library/nginx:1.27-alpine-typo: not found
```

**3. Root cause.** The tag `1.27-alpine-typo` does not exist. The repository resolves fine
(`docker.io/library/nginx`), only the reference fails — hence `code = NotFound` here versus
`pull access denied` in scenario 2. That difference is diagnostic: `NotFound` on a public repo means
a bad tag; `access denied` means a bad repo name or missing credentials.

**4. Fix.** Correct the tag to `nginx:1.27-alpine`.

**5. Verify.**

```bash
kubectl get pods -n hw14 -l scenario=errimagepull
```

```text
errimagepull-broken   0/1   ImagePullBackOff   0     9m15s
errimagepull-fixed    1/1   Running            0     2m59s
```

**6. Document.** Treat `ErrImagePull` and `ImagePullBackOff` as one diagnosis with two display
states. Read the error *text*, not the status word: `NotFound` → bad tag; `access denied` /
`insufficient_scope` → bad repo path or missing pull secret; `dial tcp ... i/o timeout` → the node
cannot reach the registry at all, which is a network or proxy problem, not an image problem.

---

### Scenario 4 — Pending, way one: unsatisfiable resource requests

Files: `02-scenarios/04-pending-resources/{broken,fixed}.yaml`

**1. Identify.** A pod requesting 500 CPU cores and 1000Gi of memory.

```bash
kubectl apply -f 02-scenarios/04-pending-resources/broken.yaml
kubectl get pod pending-resources-broken -n hw14 -o wide
```

```text
pod/pending-resources-broken created
NAME                       READY   STATUS    RESTARTS   AGE     IP       NODE     NOMINATED NODE   READINESS GATES
pending-resources-broken   0/1     Pending   0          5m49s   <none>   <none>   <none>           <none>
```

`NODE` is `<none>` and `IP` is `<none>`. That is the signature of `Pending`: the scheduler has not
placed the pod anywhere, so no kubelet has ever seen it. There is nothing to get logs from and
nothing to exec into — for a Pending pod, `describe` is the only tool.

**2. Investigate.**

```bash
kubectl describe pod pending-resources-broken -n hw14
```

```text
Events:
  Type     Reason            Age                 From               Message
  ----     ------            ----                ----               -------
  Warning  FailedScheduling  4s (x4 over 2m35s)  default-scheduler  0/1 nodes are available: 1 Insufficient cpu, 1 Insufficient memory. preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.
```

Note the reporter is `default-scheduler`, not `kubelet` — further confirmation that this never
reached a node. `0/1 nodes are available` reads as "of the 1 node in the cluster, 0 passed the
filters", and the reasons are tallied per node: `1 Insufficient cpu, 1 Insufficient memory`.
`Preemption is not helpful` means evicting lower-priority pods would still not free enough.

Compare the request against what the node actually has:

```bash
kubectl describe node minikube | sed -n '/^Allocatable:/,/^System Info/p'
```

```text
Allocatable:
  cpu:                15
  ephemeral-storage:  977850466304
  hugepages-1Gi:      0
  hugepages-2Mi:      0
  hugepages-32Mi:     0
  hugepages-64Ki:     0
  memory:             8125988Ki
  pods:               110
```

15 cores and roughly 7.7Gi allocatable, against a request for 500 cores and 1000Gi. Scheduling is
impossible on any node in this cluster.

**3. Root cause.** `resources.requests` exceeds every node's allocatable capacity. The scheduler
filters on **requests**, never on limits and never on current usage — so a node sitting at 2% CPU
will still reject a pod whose request does not fit in its *unreserved* capacity.

**4. Fix.** Right-size the request to something the node can satisfy (`cpu: 100m`, `memory: 64Mi`) and
add limits.

**5. Verify.**

```bash
kubectl get pods -n hw14 -l scenario=pending-resources -o wide --no-headers
```

```text
pending-resources-broken   0/1   Pending   0     5m49s   <none>        <none>     <none>   <none>
pending-resources-fixed    1/1   Running   0     2m59s   10.244.0.72   minikube   <none>   <none>
```

The fixed pod now has a `NODE` and an `IP`.

**6. Document.** `Pending` + `Insufficient cpu/memory` is a capacity arithmetic problem. Check
`kubectl describe node` for `Allocatable` and the `Allocated resources` summary at the bottom. The
trap is that `kubectl top node` can show the node nearly idle while the scheduler still refuses —
because requests are reservations, not measurements.

---

### Scenario 5 — Pending, way two: a `nodeSelector` nothing matches

Files: `02-scenarios/05-pending-nodeselector/{broken,fixed}.yaml`

**1. Identify.** The pod asks for `disktype: nvme-ssd`.

```bash
kubectl apply -f 02-scenarios/05-pending-nodeselector/broken.yaml
kubectl get pod pending-nodeselector-broken -n hw14 -o wide
```

```text
pod/pending-nodeselector-broken created
NAME                          READY   STATUS    RESTARTS   AGE     IP       NODE     NOMINATED NODE   READINESS GATES
pending-nodeselector-broken   0/1     Pending   0          5m49s   <none>   <none>   <none>           <none>
```

Identical outward symptom to scenario 4 — same status, same empty `NODE`. Only the events separate
them, which is why `describe` is non-optional for a Pending pod.

**2. Investigate.**

```bash
kubectl describe pod pending-nodeselector-broken -n hw14
```

```text
Events:
  Type     Reason            Age    From               Message
  ----     ------            ----   ----               -------
  Warning  FailedScheduling  2m35s  default-scheduler  0/1 nodes are available: 1 node(s) didn't match Pod's node affinity/selector. preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.
```

A completely different reason: `didn't match Pod's node affinity/selector`. Also note this fired
**once** and has not repeated, where the resources one shows `x4`. A label requirement is static, so
the scheduler stops re-reporting; capacity changes constantly, so it keeps retrying.

```bash
kubectl get node minikube --show-labels --no-headers | tr ',' '\n' | grep -E 'kubernetes.io/os|kubernetes.io/arch|disktype'
```

```text
minikube   Ready   control-plane   19d   v1.37.0   beta.kubernetes.io/arch=arm64
beta.kubernetes.io/os=linux
kubernetes.io/arch=arm64
kubernetes.io/os=linux
```

No `disktype` label exists on the only node.

**3. Root cause.** `nodeSelector: {disktype: nvme-ssd}` is a hard requirement and no node carries that
label. `nodeSelector` is exact-match and all-must-match; there is no partial credit and no fallback.

**4. Fix.** Two legitimate options. Either label the node (`kubectl label node minikube
disktype=nvme-ssd`) — which is the right move when the requirement is real and the labelling was
simply missed — or correct the selector to something that exists. The `fixed.yaml` uses
`kubernetes.io/os: linux` because labelling a shared node would affect other users of this cluster.
In production, preferring `nodeAffinity` with `preferredDuringSchedulingIgnoredDuringExecution` makes
this failure mode degrade to "scheduled somewhere suboptimal" instead of "never scheduled".

**5. Verify.**

```bash
kubectl get pods -n hw14 -l scenario=pending-nodeselector -o wide --no-headers
```

```text
pending-nodeselector-broken   0/1   Pending   0     5m49s   <none>        <none>     <none>   <none>
pending-nodeselector-fixed    1/1   Running   0     2m59s   10.244.0.69   minikube   <none>   <none>
```

**6. Document.** When a pod is Pending, the event message names the failed filter. The four common
ones: `Insufficient <resource>` (capacity), `didn't match Pod's node affinity/selector` (labels),
`node(s) had untolerated taint` (taints — control-plane nodes are tainted by default, which is why
this bites on single-node clusters), and `had volume node affinity conflict` (the PV is in a zone the
pod cannot reach).

---

### Scenario 6 — Pending, way three: a PVC that never binds

Files: `02-scenarios/06-pending-unbound-pvc/{broken,fixed}.yaml`

**1. Identify.** A PVC asking for storage class `fast-nvme`, and a pod that mounts it.

```bash
kubectl apply -f 02-scenarios/06-pending-unbound-pvc/broken.yaml
kubectl get pod pending-pvc-broken -n hw14
kubectl get pvc -n hw14
```

```text
persistentvolumeclaim/reports-pvc-broken created
pod/pending-pvc-broken created

NAME                 READY   STATUS    RESTARTS   AGE     IP       NODE     NOMINATED NODE   READINESS GATES
pending-pvc-broken   0/1     Pending   0          2m52s   <none>   <none>   <none>           <none>

NAME                 STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
reports-pvc-broken   Pending                                      fast-nvme      <unset>                 2m7s
```

Two Pending objects. The important habit here: when a pod that mounts a PVC is Pending, always
`kubectl get pvc` before anything else — the pod is usually the victim, not the culprit.

**2. Investigate.**

```bash
kubectl describe pod pending-pvc-broken -n hw14
```

```text
Events:
  Type     Reason            Age    From               Message
  ----     ------            ----   ----               -------
  Warning  FailedScheduling  2m34s  default-scheduler  0/1 nodes are available: pod has unbound immediate PersistentVolumeClaims. not found
```

`unbound immediate PersistentVolumeClaims` — the word *immediate* refers to the storage class's
`volumeBindingMode`. With `Immediate`, the volume must be provisioned before the pod can be
scheduled. (With `WaitForFirstConsumer` the order reverses and you would instead see the PVC waiting
on the pod.) The pod's events say nothing about *why* the claim is unbound, so follow the chain:

```bash
kubectl describe pvc reports-pvc-broken -n hw14
```

```text
Name:          reports-pvc-broken
Namespace:     hw14
StorageClass:  fast-nvme
Status:        Pending
Volume:        
Labels:        scenario=pending-unbound-pvc
               state=broken
Annotations:   <none>
Finalizers:    [kubernetes.io/pvc-protection]
Capacity:      
Access Modes:  
VolumeMode:    Filesystem
Used By:       pending-pvc-broken
Events:
  Type     Reason              Age                  From                         Message
  ----     ------              ----                 ----                         -------
  Warning  ProvisioningFailed  2s (x12 over 2m41s)  persistentvolume-controller  storageclass.storage.k8s.io "fast-nvme" not found
```

There it is, from a third component — `persistentvolume-controller`, not the scheduler and not the
kubelet.

**3. Root cause.** The storage class `fast-nvme` does not exist on this cluster, so no provisioner
ever claims the PVC, so no PV is created, so the PVC stays Pending, so the pod cannot be scheduled.
Three objects deep. This is the classic manifest-portability failure: the YAML was written for a
cluster where `fast-nvme` existed (EBS gp3, say) and applied to one where it does not.

**4. Fix.** Use a storage class that exists. `kubectl get storageclass` showed exactly one,
`standard (default)`. The `fixed.yaml` sets `storageClassName: standard`.

Omitting `storageClassName` entirely would also work here, since `standard` is marked default — but
that is fragile, because a cluster with no default storage class will silently leave the PVC Pending
with no error at all.

**5. Verify.**

```bash
kubectl get pvc -n hw14
kubectl get pods -n hw14 -l scenario=pending-unbound-pvc -o wide --no-headers
```

```text
NAME                 STATUS    VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
reports-pvc-broken   Pending                                                                        fast-nvme      <unset>                 3m
reports-pvc-fixed    Bound     pvc-f2e5141e-47de-4082-917a-1af8fb6c8a83   1Gi        RWO            standard       <unset>                 11s

pending-pvc-broken   0/1   Pending   0     5m48s   <none>        <none>     <none>   <none>
pending-pvc-fixed    1/1   Running   0     2m59s   10.244.0.70   minikube   <none>   <none>
```

`Bound` with a real PV name and capacity, and the pod scheduled.

**6. Document.** Storage failures cascade across three controllers, so follow the chain
pod → PVC → StorageClass → PV and read the events at each level. `kubectl get storageclass` first
saves the most time. Other common PVC-Pending causes: an access mode the provisioner does not
support (`ReadWriteMany` on a block-storage CSI driver), a requested size no PV satisfies when using
static provisioning, and zone mismatch between the PV and the node.

---

### Scenario 7 — stuck in ContainerCreating (missing Secret volume)

Files: `02-scenarios/07-containercreating/{broken,fixed}.yaml`

**1. Identify.** A gateway pod mounting a Secret named `gateway-tls` that was never created.

```bash
kubectl apply -f 02-scenarios/07-containercreating/broken.yaml
kubectl get pod containercreating-broken -n hw14 -o wide
```

```text
pod/containercreating-broken created
NAME                       READY   STATUS              RESTARTS   AGE     IP       NODE       NOMINATED NODE   READINESS GATES
containercreating-broken   0/1     ContainerCreating   0          2m52s   <none>   minikube   <none>           <none>
```

`ContainerCreating` for a few seconds is normal — that is image pull and volume setup. `ContainerCreating`
for two and a half minutes is a hang. Note the difference from Pending: `NODE` is populated
(`minikube`) but `IP` is not. The scheduler succeeded; the kubelet is stuck.

**2. Investigate.**

```bash
kubectl describe pod containercreating-broken -n hw14
```

```text
Events:
  Type     Reason       Age                  From               Message
  ----     ------       ----                 ----               -------
  Normal   Scheduled    2m34s                default-scheduler  Successfully assigned hw14/containercreating-broken to minikube
  Warning  FailedMount  26s (x9 over 2m34s)  kubelet            MountVolume.SetUp failed for volume "tls" : secret "gateway-tls" not found
```

One event, said nine times, and it is unambiguous. `kubectl logs` is useless here — the container has
not been created, so there is no log stream.

**3. Root cause.** The pod references `secretName: gateway-tls`, nothing by that name exists in
`hw14`, and the kubelet cannot build the volume. By default a `secret` or `configMap` volume is
*required*: the kubelet blocks the container indefinitely rather than starting it without the data.
Adding `optional: true` to the volume source would let it start with an empty directory instead —
occasionally what you want, usually not.

The same symptom and almost the same message appears for a missing ConfigMap volume
(`configmap "x" not found`), so this scenario covers both.

**4. Fix.** Create the Secret. `fixed.yaml` ships it alongside the pod so the two apply together.

**5. Verify — the interesting part.** The *broken* pod recovers on its own, without being recreated:

```bash
kubectl apply -f 02-scenarios/07-containercreating/fixed.yaml
kubectl get pod containercreating-broken -n hw14
kubectl describe pod containercreating-broken -n hw14
```

```text
secret/gateway-tls created
pod/containercreating-fixed created

NAME                       READY   STATUS    RESTARTS   AGE
containercreating-broken   1/1     Running   0          4m17s

Events:
  Type     Reason       Age                   From               Message
  ----     ------       ----                  ----               -------
  Normal   Scheduled    4m17s                 default-scheduler  Successfully assigned hw14/containercreating-broken to minikube
  Warning  FailedMount  2m9s (x9 over 4m17s)  kubelet            MountVolume.SetUp failed for volume "tls" : secret "gateway-tls" not found
  Normal   Pulled       7s                    kubelet            spec.containers{gateway}: Container image "nginx:1.27-alpine" already present on machine and can be accessed by the pod
  Normal   Created      7s                    kubelet            spec.containers{gateway}: Container created
  Normal   Started      7s                    kubelet            spec.containers{gateway}: Container started
```

That is a genuinely important behaviour: the kubelet retries the mount with exponential backoff
forever, so creating the missing Secret heals the existing pod. No `kubectl delete pod` needed. The
event history preserves both the failures and the recovery, which is exactly the timeline you want in
a post-incident write-up. The retry interval does grow though (the gap between the last `FailedMount`
and the recovery here was over two minutes), so a pod can look stuck for a while after you have
already fixed the cause — deleting it forces an immediate retry if you are in a hurry.

And the mount is real:

```bash
kubectl exec containercreating-fixed -n hw14 -- ls -l /etc/nginx/tls
```

```text
total 0
lrwxrwxrwx    1 root     root            14 Oct  7 12:40 tls.crt -> ..data/tls.crt
lrwxrwxrwx    1 root     root            14 Oct  7 12:40 tls.key -> ..data/tls.key
```

The symlinks into `..data/` are how Kubernetes achieves atomic updates when a Secret changes.

**6. Document.** `ContainerCreating` that does not clear within ~30 seconds means the kubelet is
blocked. Go straight to `describe` events. The usual causes: a missing Secret or ConfigMap volume
(this scenario), a PVC that is bound but cannot attach or mount to this node, a slow first-time pull
of a very large image, or a CNI failure (`failed to set up sandbox ... network ...`).

---

### Scenario 8 — service connectivity: empty endpoints

Files: `02-scenarios/08-service-connectivity/{deployment,broken-selector-service,broken-targetport-service,fixed-service}.yaml`

**1. Identify.** Two healthy backend pods, a Service in front, and no traffic reaching them.

```bash
kubectl apply -f 02-scenarios/08-service-connectivity/deployment.yaml
kubectl apply -f 02-scenarios/08-service-connectivity/broken-selector-service.yaml
kubectl get pods -n hw14 -l app=shop-api -o wide
```

```text
deployment.apps/shop-api created
service/shop-api-svc created
NAME                        READY   STATUS    RESTARTS   AGE   IP            NODE       NOMINATED NODE   READINESS GATES
shop-api-76498ddf54-g65rs   1/1     Running   0          3s    10.244.0.79   minikube   <none>           <none>
shop-api-76498ddf54-wqd4c   1/1     Running   0          3s    10.244.0.78   minikube   <none>           <none>
```

The pods are perfectly healthy. This is the scenario where `kubectl get pods` actively misleads you.

```bash
kubectl exec netshoot -n hw14 -- curl -sS -m 5 -o /dev/null -w '%{http_code}\n' http://shop-api-svc.hw14.svc.cluster.local
```

```text
curl: (7) Failed to connect to shop-api-svc.hw14.svc.cluster.local:80 after 1 ms: Could not connect to server
000
command terminated with exit code 7
```

"after 1 ms" matters. A fast refusal means the name resolved and the connection was rejected
immediately — not a timeout, so not a firewall or NetworkPolicy drop (those hang until the client
gives up). Something answered "no" instantly.

**2. Investigate.** First prove DNS is not the problem, because "service unreachable" and "service
name does not resolve" are different bugs:

```bash
kubectl exec netshoot -n hw14 -- nslookup shop-api-svc.hw14.svc.cluster.local
```

```text
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	shop-api-svc.hw14.svc.cluster.local
Address: 10.98.7.160
```

DNS is fine. Now the single most valuable command for any Service problem:

```bash
kubectl get endpoints shop-api-svc -n hw14
```

```text
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME           ENDPOINTS   AGE
shop-api-svc   <none>      8s
```

`<none>`. The Service exists, has a ClusterIP, and routes to nothing. On v1.33+ the modern equivalent
is EndpointSlice, which says the same thing:

```bash
kubectl get endpointslice -n hw14 -l kubernetes.io/service-name=shop-api-svc
```

```text
NAME                 ADDRESSTYPE   PORTS     ENDPOINTS   AGE
shop-api-svc-682rp   IPv4          <unset>   <unset>     8s
```

```bash
kubectl describe svc shop-api-svc -n hw14
```

```text
Name:                     shop-api-svc
Namespace:                hw14
Labels:                   scenario=service-connectivity
                          state=broken
Annotations:              <none>
Selector:                 app=shop-api-v2
Type:                     ClusterIP
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       10.98.7.160
IPs:                      10.98.7.160
Port:                     http  80/TCP
TargetPort:               80/TCP
Endpoints:                
Session Affinity:         None
Internal Traffic Policy:  Cluster
Events:                   <none>
```

`Selector: app=shop-api-v2`. Compare against what the pods actually carry:

```bash
kubectl get pods -n hw14 -l app=shop-api --show-labels
kubectl get svc shop-api-svc -n hw14 -o jsonpath='{.spec.selector}{"\n"}'
kubectl get pods -n hw14 -l app=shop-api-v2
```

```text
NAME                        READY   STATUS    RESTARTS   AGE   LABELS
shop-api-76498ddf54-g65rs   1/1     Running   0          13s   app=shop-api,pod-template-hash=76498ddf54
shop-api-76498ddf54-wqd4c   1/1     Running   0          13s   app=shop-api,pod-template-hash=76498ddf54

{"app":"shop-api-v2"}

No resources found in hw14 namespace.
```

That last command is the proof: running the Service's selector as a label query returns nothing.

**3. Root cause.** Selector/label mismatch. The Service selects `app=shop-api-v2`; the pods are
labelled `app=shop-api`. The endpoints controller watches for pods matching the selector, finds none,
and writes an empty EndpointSlice. kube-proxy then programs a ClusterIP with no backends, which
rejects connections immediately.

Nothing warns you about this. There is no event, no validation error, no `kubectl apply` failure —
a Service with a selector that matches nothing is a completely legal object.

**4. Fix.** Correct the selector to `app: shop-api`.

**5. Verify.**

```bash
kubectl apply -f 02-scenarios/08-service-connectivity/fixed-service.yaml
kubectl get endpoints shop-api-svc -n hw14
kubectl exec netshoot -n hw14 -- curl -sS -m 5 -o /dev/null -w 'HTTP %{http_code} in %{time_total}s\n' http://shop-api-svc
```

```text
service/shop-api-svc configured
NAME           ENDPOINTS                       AGE
shop-api-svc   10.244.0.78:80,10.244.0.79:80   21s
HTTP 200 in 0.002945s
```

Both pod IPs are now listed, and they match the `-o wide` output from step 1 exactly. That
cross-check — endpoint IPs against pod IPs — is the fastest way to confirm a Service is wired up.

**5b. The second variant: endpoints exist but still nothing works.** Same Service, correct selector,
wrong `targetPort`:

```bash
kubectl apply -f 02-scenarios/08-service-connectivity/broken-targetport-service.yaml
kubectl get endpoints shop-api-svc -n hw14
kubectl exec netshoot -n hw14 -- curl -sS -m 5 -o /dev/null -w 'HTTP %{http_code}\n' http://shop-api-svc
```

```text
service/shop-api-svc configured
NAME           ENDPOINTS                           AGE
shop-api-svc   10.244.0.78:8080,10.244.0.79:8080   30s

curl: (7) Failed to connect to shop-api-svc:80 after 3 ms: Could not connect to server
HTTP 000
command terminated with exit code 7
```

The endpoints are populated this time — so "endpoints look fine" is not sufficient. Read the *port*
on each endpoint: `:8080`, while nginx listens on 80. The Service is faithfully forwarding to a port
nothing is bound to. `port` is what clients dial; `targetPort` is the container port traffic lands on.
Restoring `targetPort: 80`:

```bash
kubectl apply -f 02-scenarios/08-service-connectivity/fixed-service.yaml
kubectl get endpoints shop-api-svc -n hw14
kubectl exec netshoot -n hw14 -- curl -sS -m 5 -o /dev/null -w 'HTTP %{http_code}\n' http://shop-api-svc
```

```text
service/shop-api-svc configured
NAME           ENDPOINTS                       AGE
shop-api-svc   10.244.0.78:80,10.244.0.79:80   34s
HTTP 200
```

**6. Document.** For any "my Service doesn't work", run `kubectl get endpoints <svc>` first and branch
on the result. `<none>` → selector/label mismatch, or every matching pod is failing readiness (an
unready pod is pulled out of the endpoint list, which is the other common cause of empty endpoints).
Populated but wrong port → `targetPort` mismatch. Populated and correct → the problem is downstream:
NetworkPolicy, the application, or the client.

---

### Scenario 9 — DNS

Files: `02-scenarios/09-dns/netshoot.yaml` (the debug pod used throughout)

Kubernetes DNS failures are almost never "DNS is down". They are nearly always a name that is
correct somewhere else. The whole thing is governed by one file inside every pod:

```bash
kubectl exec netshoot -n hw14 -- cat /etc/resolv.conf
```

```text
search hw14.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5
```

Three lines that explain every DNS bug below. `nameserver 10.96.0.10` is the CoreDNS Service
ClusterIP. The `search` list is tried in order for any name with fewer than 5 dots (`ndots:5`), and
the first entry is **this pod's own namespace**. That is why a bare service name works inside its
namespace and nowhere else.

**Case A — wrong service name.**

```bash
kubectl exec netshoot -n hw14 -- nslookup shop-api-service
```

```text
Server:		10.96.0.10
Address:	10.96.0.10#53

** server can't find shop-api-service: NXDOMAIN

command terminated with exit code 1
```

`NXDOMAIN` = the name does not exist. CoreDNS answered — it is up and reachable — it simply has no
record. The actual Service is `shop-api-svc`, not `shop-api-service`:

```bash
kubectl exec netshoot -n hw14 -- nslookup shop-api-svc
```

```text
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	shop-api-svc.hw14.svc.cluster.local
Address: 10.98.7.160
```

Root cause: a typo, or an application config pointing at a service name that was renamed. Fix: use
the name `kubectl get svc` prints.

**Case B — cross-namespace short name.** This is the subtle one. The `kubernetes` Service lives in
the `default` namespace. From a pod in `hw14`:

```bash
kubectl exec netshoot -n hw14 -- nslookup kubernetes
```

```text
Server:		10.96.0.10
Address:	10.96.0.10#53

** server can't find kubernetes: NXDOMAIN

command terminated with exit code 1
```

NXDOMAIN — for a Service that definitely exists. The resolver tried `kubernetes.hw14.svc.cluster.local`
(from the search list), then `kubernetes.svc.cluster.local`, then `kubernetes.cluster.local`, and none
of those are the record. Qualifying the name fixes it instantly:

```bash
kubectl exec netshoot -n hw14 -- nslookup kubernetes.default.svc.cluster.local
```

```text
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	kubernetes.default.svc.cluster.local
Address: 10.96.0.1
```

Root cause: a short name is implicitly namespace-local. This is the single most common DNS bug in
practice, because the config works perfectly in dev (everything in one namespace) and breaks the
moment a service is split out. Fix: use `<service>.<namespace>` (two dots is enough for the search
list to resolve it as `<service>.<namespace>.svc.cluster.local`) or the full FQDN.

Both forms work for a same-namespace service, which is why the short name is safe to keep when the
caller and callee genuinely always live together:

```bash
kubectl exec netshoot -n hw14 -- sh -c 'curl -sS -m5 -o /dev/null -w "short name -> HTTP %{http_code}\n" http://shop-api-svc; curl -sS -m5 -o /dev/null -w "FQDN       -> HTTP %{http_code}\n" http://shop-api-svc.hw14.svc.cluster.local'
```

```text
short name -> HTTP 200
FQDN       -> HTTP 200
```

**Case C — ruling out CoreDNS itself.** Before blaming names, confirm the resolver is healthy:

```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide
kubectl get svc -n kube-system kube-dns
```

```text
NAME                       READY   STATUS    RESTARTS      AGE   IP           NODE       NOMINATED NODE   READINESS GATES
coredns-559f6c778d-bnc89   1/1     Running   1 (42m ago)   19d   10.244.0.2   minikube   <none>           <none>

NAME       TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)                  AGE
kube-dns   ClusterIP   10.96.0.10   <none>        53/UDP,53/TCP,9153/TCP   19d
```

`1/1 Running`, and its ClusterIP `10.96.0.10` matches the `nameserver` line in the pod's
`/etc/resolv.conf`. If it did not match, or if CoreDNS were crash-looping, *every* lookup would fail
rather than one specific name — a cluster-wide symptom, not a per-service one.

**How to tell DNS apart from everything else:**

| What you see | What it means |
| :--- | :--- |
| `NXDOMAIN` | DNS works, the name is wrong (typo or missing namespace) |
| `connection timed out; no servers could be reached` | CoreDNS is down or unreachable — a real DNS outage |
| Name resolves, then `Could not connect` | Not DNS. Go look at endpoints (scenario 8) |
| Only some lookups fail, intermittently | CoreDNS under-replicated or the conntrack UDP race; check CoreDNS resource limits |

---

### Scenario 10 — pod networking: the app binds to loopback

Files: `02-scenarios/10-pod-networking/{broken,fixed}.yaml`

This is the failure mode that survives every other check. The pod is `Running`, `1/1 Ready`, has no
restarts, logs look clean, and the Service has endpoints — and nothing can reach it.

**1. Identify.** Two nginx pods, identical except for one line of config: one listens on
`127.0.0.1:80`, the other on `0.0.0.0:80`.

```bash
kubectl apply -f 02-scenarios/10-pod-networking/broken.yaml
kubectl apply -f 02-scenarios/10-pod-networking/fixed.yaml
kubectl get pod netbind-broken netbind-fixed -n hw14 -o wide
```

```text
NAME             READY   STATUS    RESTARTS   AGE   IP            NODE       NOMINATED NODE   READINESS GATES
netbind-broken   1/1     Running   0          3s    10.244.0.81   minikube   <none>           <none>
netbind-fixed    1/1     Running   0          3s    10.244.0.82   minikube   <none>           <none>
```

Indistinguishable from `get`. Both look perfect.

**2. Investigate.** The decisive command is run *from inside the pod*:

```bash
kubectl exec netbind-broken -n hw14 -- netstat -tlnp
```

```text
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name
tcp        0      0 127.0.0.1:80            0.0.0.0:*               LISTEN      1/nginx: master pro
```

`Local Address 127.0.0.1:80`. That is the entire bug, visible in one line. Compare the healthy pod:

```bash
kubectl exec netbind-fixed -n hw14 -- netstat -tlnp
```

```text
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name
tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN      1/nginx: master pro
```

The app genuinely works — over loopback:

```bash
kubectl exec netbind-broken -n hw14 -- wget -qS -O /dev/null http://127.0.0.1/
```

```text
  HTTP/1.1 200 OK
  Server: nginx/1.27.5
```

This is why "I exec'd in and curl'd localhost and it was fine" is a trap: `curl localhost` from
inside the container succeeds on exactly the pods that are broken this way.

The right test is to dial the **pod IP**, not localhost. From another pod:

```bash
kubectl exec netshoot -n hw14 -- curl -sS -m 5 -o /dev/null -w 'HTTP %{http_code}\n' http://10.244.0.81
```

```text
curl: (7) Failed to connect to 10.244.0.81:80 after 0 ms: Could not connect to server
HTTP 000
command terminated with exit code 7
```

And, conclusively, it fails even from inside the broken pod itself when addressed by pod IP:

```bash
kubectl exec netbind-broken -n hw14 -- wget -q -T 3 -O /dev/null http://10.244.0.81/
```

```text
wget: can't connect to remote host (10.244.0.81): Connection refused
command terminated with exit code 1
```

Same container, same moment: `127.0.0.1` returns 200 and `10.244.0.81` is refused. That pair of
results proves the bind address beyond any doubt and rules out CNI, NetworkPolicy and kube-proxy in
one step.

**3. Root cause.** nginx is configured with `listen 127.0.0.1:80`, so it binds only the loopback
interface inside the pod's network namespace. The pod IP lives on `eth0`, which has no listener.
`containerPort: 80` in the manifest is purely informational and does not change what the process
binds to — a common source of false confidence.

The real-world versions of this: a Go service defaulting to `localhost:8080`, a Flask app started
without `--host=0.0.0.0`, a Spring Boot app with `server.address=127.0.0.1`, or a database bound to
loopback in its config file.

**4. Fix.** Change the bind address to `0.0.0.0:80` (`02-scenarios/10-pod-networking/fixed.yaml`).

**5. Verify.**

```bash
kubectl exec netshoot -n hw14 -- curl -sS -m 5 -o /dev/null -w 'HTTP %{http_code}\n' http://10.244.0.82
```

```text
HTTP 200
```

**6. Document.** When a pod is Running and Ready but unreachable, prove where the socket is bound
before touching networking config. `kubectl exec <pod> -- netstat -tlnp` (or `ss -tlnp`) is the
command. Reach the pod by **pod IP** from a second pod, never by `localhost` from inside it.

Two neighbouring causes worth knowing: a `readinessProbe` that passes on loopback while real traffic
fails, and a NetworkPolicy — which looks different because a policy *drops* packets, so the client
hangs until timeout instead of getting an instant `Connection refused`. Refused means nothing is
listening; timeout means something is dropping.

---

### Scenario 11 — configuration: a key that is not in the ConfigMap

Files: `02-scenarios/11-configuration/{configmap,broken,fixed}.yaml`

**1. Identify.** The ConfigMap exists and is correct. The pod asks it for a key that is not there.

```bash
kubectl apply -f 02-scenarios/11-configuration/configmap.yaml
kubectl apply -f 02-scenarios/11-configuration/broken.yaml
kubectl get pod config-broken -n hw14
```

```text
configmap/billing-config created
pod/config-broken created
NAME            READY   STATUS                       RESTARTS   AGE
config-broken   0/1     CreateContainerConfigError   0          2m34s
```

`CreateContainerConfigError` is its own status, distinct from both `ContainerCreating` and
`CrashLoopBackOff`. It means the kubelet assembled everything it needs to create the container,
tried, and the *configuration* it was handed was invalid. The container was never created, so
`RESTARTS` stays 0 and there are no logs.

**2. Investigate.**

```bash
kubectl describe pod config-broken -n hw14
```

```text
Events:
  Type     Reason     Age                  From               Message
  ----     ------     ----                 ----               -------
  Normal   Scheduled  2m34s                default-scheduler  Successfully assigned hw14/config-broken to minikube
  Normal   Pulled     7s (x13 over 2m34s)  kubelet            spec.containers{billing}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Warning  Failed     7s (x13 over 2m34s)  kubelet            spec.containers{billing}: Error: couldn't find key LOGLEVEL in ConfigMap hw14/billing-config
```

The message names the key, the ConfigMap and the namespace: `couldn't find key LOGLEVEL in ConfigMap
hw14/billing-config`. Confirm against the source of truth:

```bash
kubectl get configmap billing-config -n hw14 -o jsonpath='{.data}' | tr ',' '\n'
```

```text
{"CURRENCY":"INR"
"LOG_LEVEL":"info"
"RETRY_LIMIT":"3"}
```

**3. Root cause.** The pod requests `key: LOGLEVEL`; the ConfigMap holds `LOG_LEVEL`. An underscore.
`configMapKeyRef` is a hard reference — a missing key blocks container creation outright, which is
arguably the right default: starting the app with the variable silently unset would move the failure
into production behaviour instead of deployment.

**4. Fix.** Correct the key name to `LOG_LEVEL`. (The alternative, `optional: true` on the
`configMapKeyRef`, lets the container start with the variable unset — appropriate only when the
application has a sane default.)

**5. Verify.**

```bash
kubectl apply -f 02-scenarios/11-configuration/fixed.yaml
kubectl get pods -n hw14 -l scenario=configuration --no-headers
kubectl logs config-fixed -n hw14
```

```text
pod/config-fixed created
config-broken   0/1   CreateContainerConfigError   0     5m48s
config-fixed    1/1   Running                      0     2m59s

billing: LOG_LEVEL=info CURRENCY=INR
```

The application prints the values it received, which proves the wiring end to end rather than just
that the pod started.

**6. Document.** Configuration problems split cleanly by *when* they bite:

| Symptom | Cause |
| :--- | :--- |
| `CreateContainerConfigError` | `configMapKeyRef`/`secretKeyRef` names a key that does not exist |
| `CreateContainerConfigError` | The whole ConfigMap or Secret referenced by `envFrom` is missing |
| `ContainerCreating` forever + `FailedMount` | A ConfigMap or Secret mounted as a *volume* is missing (scenario 7) |
| `CrashLoopBackOff` | The variable was injected but holds a wrong value — the app starts and then rejects it |
| Running but behaving wrongly | A value is wrong and the app has a permissive default |

Note the asymmetry: a missing **key** as `env` fails loudly at container creation, while a missing
**key** in a mounted volume just produces a missing file, which usually surfaces later as a crash.

---

### Scenario 12 — OOMKilled (bonus: the crash loop that is not an application bug)

Files: `02-scenarios/12-oomkilled/{broken,fixed}.yaml`

Included because OOMKilled presents as `CrashLoopBackOff` and is the most commonly misdiagnosed one
— teams spend hours reading application logs that contain no error at all.

**1. Identify.** A cache service that allocates aggressively, with a 32Mi memory limit.

```bash
kubectl apply -f 02-scenarios/12-oomkilled/broken.yaml
kubectl get pod oomkilled-broken -n hw14
```

```text
pod/oomkilled-broken created
NAME               READY   STATUS      RESTARTS      AGE
oomkilled-broken   0/1     OOMKilled   2 (28s ago)   29s
```

**2. Investigate.**

```bash
kubectl describe pod oomkilled-broken -n hw14
```

```text
    State:          Terminated
      Reason:       OOMKilled
      Exit Code:    137
      Started:      Wed, 07 Oct 2026 18:10:13 +0530
      Finished:     Wed, 07 Oct 2026 18:10:13 +0530
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
      Started:      Wed, 07 Oct 2026 18:09:59 +0530
      Finished:     Wed, 07 Oct 2026 18:09:59 +0530
    Ready:          False
    Restart Count:  2
```

```text
Events:
  Type     Reason     Age                    From               Message
  ----     ------     ----                   ----               -------
  Normal   Scheduled  8m15s                  default-scheduler  Successfully assigned hw14/oomkilled-broken to minikube
  Normal   Pulled     2m31s (x7 over 8m14s)  kubelet            spec.containers{cache}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Normal   Created    2m31s (x7 over 8m14s)  kubelet            spec.containers{cache}: Container created
  Normal   Started    2m31s (x7 over 8m14s)  kubelet            spec.containers{cache}: Container started
  Warning  BackOff    62s (x10 over 8m13s)   kubelet            spec.containers{cache}: Back-off restarting failed container cache in pod oomkilled-broken_hw14(d9042029-9d03-4a79-b8cd-5cf18ab3fae5)
```

`Reason: OOMKilled`, `Exit Code: 137`. 137 = 128 + 9 = killed by SIGKILL.

Now look carefully at those events: `Scheduled`, `Pulled`, `Created`, `Started`, `BackOff`. There is
no event mentioning memory anywhere. This event list is **byte-for-byte the same shape** as the
CrashLoopBackOff one in scenario 1. If you only read `describe`'s Events block you would conclude the
application is crashing and go hunting through its code. The memory evidence lives exclusively in the
`State` / `Last State` block above, in the `Reason:` field — that is the one thing you must read.

And the logs confirm nothing:

```bash
kubectl logs oomkilled-broken -n hw14 --previous
```

```text
cache-service: warming in-memory cache
```

One line, mid-task, no error, no stack trace. The kernel SIGKILLed the process without warning, so
the application had no chance to log anything. That *absence* of an error message in a crash loop is
itself a strong signal to go check the exit code.

**3. Root cause.** The container's working set exceeds `resources.limits.memory: 32Mi`. The kernel
cgroup OOM killer terminates the process the instant it crosses the limit. There is no grace period,
no SIGTERM, and the application never gets a chance to log anything.

**4. Fix.** Either raise the limit to match the real working set, or reduce what the app allocates.
`fixed.yaml` does both: a bounded 32Mi allocation inside a 256Mi limit, with `requests: 128Mi` so the
scheduler reserves room.

**5. Verify.**

```bash
kubectl get pod oomkilled-fixed -n hw14
kubectl logs oomkilled-fixed -n hw14
```

```text
NAME              READY   STATUS    RESTARTS   AGE
oomkilled-fixed   1/1     Running   0          3s

cache-service: warming in-memory cache
32+0 records in
32+0 records out
33554432 bytes (32.0MB) copied, 0.015512 seconds, 2.0GB/s
cache-service: warm, serving
```

**6. Document.** Exit code 137 plus `Reason: OOMKilled` is conclusive — stop reading application logs
and go look at `resources.limits.memory`. Use `kubectl top pod` on a healthy replica to find the real
working set before picking a number.

One hard-won detail from building this scenario. An earlier version filled a memory-backed `emptyDir`
instead of allocating in-process, and produced a *different* and much more confusing status:

```text
    State:          Waiting
      Reason:       RunContainerError
    Last State:     Terminated
      Reason:       StartError
      Message:      failed to create containerd task: failed to create shim task: OCI runtime create failed: runc create failed: unable to start container process: container init was OOM-killed (memory limit too low?)
      Exit Code:    128
```

`RunContainerError` / `StartError` / exit 128, not `OOMKilled` / 137. The reason is that a
`medium: Memory` emptyDir is tmpfs and counts against the container's memory cgroup, but it *survives
container restarts within the pod* — so after the first kill the volume was still full and the
container could not even finish `init`. Worth recognising: `container init was OOM-killed` means the
limit is too small for the container to start at all, which is a different conversation from an app
that grows into its limit.

---

## Task 3 — Mini project: the Kubernetes Troubleshooting Challenge

This is the project from `session-14-kubernetes-troubleshooting/mini-project/`, worked end to end.
Manifests are in `03-mini-project/`. `deployment.yaml`, `service.yaml` and `broken-pod.yaml` are the
project's own, changed only to pin `namespace: hw14` and to add resource requests. `service-broken.yaml`
(the deliberate selector mismatch from step 8) and `fixed-pod.yaml` (the answer to step 7) are added
so both halves of the exercise are reproducible from a file rather than from a hand edit. The image
stays `nginx:1.27`, the Debian-based variant, because the project calls for
`kubectl exec -it <pod> -- bash` and the alpine image has no bash.

### 1. Deploy the application

```bash
kubectl apply -f 03-mini-project/deployment.yaml
kubectl apply -f 03-mini-project/service.yaml
kubectl get pods -n hw14 -l app=troubleshooting-app
kubectl get service troubleshooting-service -n hw14
```

```text
deployment.apps/troubleshooting-app created
service/troubleshooting-service created

NAME                                   READY   STATUS    RESTARTS   AGE
troubleshooting-app-66cbd59bf6-q7rw6   1/1     Running   0          3s
troubleshooting-app-66cbd59bf6-rt5tp   1/1     Running   0          3s

NAME                      TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
troubleshooting-service   ClusterIP   10.103.161.66   <none>        80/TCP    3s
```

### 2. Check the application

```bash
kubectl get pods -n hw14 -l app=troubleshooting-app -o wide
```

```text
NAME                                   READY   STATUS    RESTARTS   AGE   IP             NODE       NOMINATED NODE   READINESS GATES
troubleshooting-app-66cbd59bf6-q7rw6   1/1     Running   0          8s    10.244.0.104   minikube   <none>           <none>
troubleshooting-app-66cbd59bf6-rt5tp   1/1     Running   0          8s    10.244.0.103   minikube   <none>           <none>
```

Note the two pod IPs, `10.244.0.104` and `10.244.0.103` — these are what the Service's endpoint list
should contain.

```bash
kubectl describe pod troubleshooting-app-66cbd59bf6-q7rw6 -n hw14
```

```text
Name:             troubleshooting-app-66cbd59bf6-q7rw6
Namespace:        hw14
Priority:         0
Service Account:  default
Node:             minikube/192.168.49.2
Start Time:       Wed, 07 Oct 2026 18:19:20 +0530
Labels:           app=troubleshooting-app
                  pod-template-hash=66cbd59bf6
Annotations:      <none>
Status:           Running
IP:               10.244.0.104
IPs:
  IP:           10.244.0.104
Controlled By:  ReplicaSet/troubleshooting-app-66cbd59bf6
Containers:
  app:
    Container ID:   containerd://71d5af6a52a29bfc390abac4b7bc1389dd3a2ab04fbfd39078d77544778270e7
    Image:          nginx:1.27
    Image ID:       docker.io/library/nginx@sha256:6784fb0834aa7dbbe12e3d7471e69c290df3e6ba810dc38b34ae33d3c1c05f7d
    Port:           80/TCP
    Host Port:      0/TCP
    State:          Running
      Started:      Wed, 07 Oct 2026 18:19:20 +0530
    Ready:          True
    Restart Count:  0
```

```text
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  9s    default-scheduler  Successfully assigned hw14/troubleshooting-app-66cbd59bf6-q7rw6 to minikube
  Normal  Pulled     9s    kubelet            spec.containers{app}: Container image "nginx:1.27" already present on machine and can be accessed by the pod
  Normal  Created    9s    kubelet            spec.containers{app}: Container created
  Normal  Started    9s    kubelet            spec.containers{app}: Container started
```

Three important things in a *healthy* describe, which is worth knowing so you recognise its absence:
`Labels: app=troubleshooting-app` (what the Service must select), `Controlled By: ReplicaSet/...`
(delete this pod and it comes straight back), and `Scheduled → Pulled → Created → Started` with no
`Warning` line.

```bash
kubectl logs troubleshooting-app-66cbd59bf6-q7rw6 -n hw14 | tail -4
```

```text
2026/10/07 12:49:21 [notice] 1#1: start worker process 40
2026/10/07 12:49:21 [notice] 1#1: start worker process 41
2026/10/07 12:49:21 [notice] 1#1: start worker process 42
2026/10/07 12:49:21 [notice] 1#1: start worker process 43
```

```bash
kubectl exec -i troubleshooting-app-66cbd59bf6-q7rw6 -n hw14 -- bash -c 'curl -s -o /dev/null -w "HTTP %{http_code}\n" localhost; curl -s localhost | head -4'
```

```text
HTTP 200
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
```

nginx answers on localhost inside the container. The application layer is proven good, so any later
failure is routing, not the app.

### 3. Check the Service

```bash
kubectl describe service troubleshooting-service -n hw14
```

```text
Name:                     troubleshooting-service
Namespace:                hw14
Labels:                   <none>
Annotations:              <none>
Selector:                 app=troubleshooting-app
Type:                     ClusterIP
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       10.103.161.66
IPs:                      10.103.161.66
Port:                     <unset>  80/TCP
TargetPort:               80/TCP
Endpoints:                10.244.0.104:80,10.244.0.103:80
Session Affinity:         None
Internal Traffic Policy:  Cluster
Events:                   <none>
```

The three fields the project asks about: **Selector** `app=troubleshooting-app` matches the pod
labels; **TargetPort** `80/TCP` matches `containerPort: 80`; **Endpoints** lists both pod IPs.

### 4. Check endpoints

```bash
kubectl get endpoints troubleshooting-service -n hw14
kubectl exec netshoot -n hw14 -- curl -sS -m5 -o /dev/null -w 'HTTP %{http_code}\n' http://troubleshooting-service
```

```text
NAME                      ENDPOINTS                         AGE
troubleshooting-service   10.244.0.103:80,10.244.0.104:80   12s
HTTP 200
```

Both pod IPs are present and traffic flows end to end. This is the known-good baseline.

### 5. Create the broken pod

```bash
kubectl apply -f 03-mini-project/broken-pod.yaml
kubectl get pod project-broken-pod -n hw14
```

```text
pod/project-broken-pod created
NAME                 READY   STATUS         RESTARTS   AGE
project-broken-pod   0/1     ErrImagePull   0          12s
```

### 6. Troubleshoot it, without changing the YAML

```bash
kubectl describe pod project-broken-pod -n hw14
```

```text
Events:
  Type     Reason     Age   From               Message
  ----     ------     ----  ----               -------
  Normal   Scheduled  12s   default-scheduler  Successfully assigned hw14/project-broken-pod to minikube
  Normal   Pulling    11s   kubelet            spec.containers{app}: Pulling image "nginx:this-tag-does-not-exist"
  Warning  Failed     10s   kubelet            spec.containers{app}: Failed to pull image "nginx:this-tag-does-not-exist": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:this-tag-does-not-exist": failed to resolve reference "docker.io/library/nginx:this-tag-does-not-exist": docker.io/library/nginx:this-tag-does-not-exist: not found
  Warning  Failed     10s   kubelet            spec.containers{app}: Error: ErrImagePull
  Normal   BackOff    9s    kubelet            spec.containers{app}: Back-off pulling image "nginx:this-tag-does-not-exist"
  Warning  Failed     9s    kubelet            spec.containers{app}: Error: ImagePullBackOff
```

For completeness, what `kubectl logs` gives you here:

```bash
kubectl logs project-broken-pod -n hw14
```

```text
Error from server (BadRequest): container "app" in pod "project-broken-pod" is waiting to start: image can't be pulled
```

Worth reading carefully — the API server tells you *why there are no logs*, which is itself the
diagnosis. A container that never started has no log stream.

### 7. The project's five questions

**Question 1: What is the Pod status?**
`ErrImagePull` at 12 seconds, cycling to `ImagePullBackOff` and back. `READY 0/1`, `RESTARTS 0`. The
zero restart count is the giveaway that the container never ran at all — this is not a crash.

**Question 2: What is the actual error?**
```text
Failed to pull image "nginx:this-tag-does-not-exist": rpc error: code = NotFound desc = failed to
pull and unpack image "docker.io/library/nginx:this-tag-does-not-exist": failed to resolve reference
"docker.io/library/nginx:this-tag-does-not-exist": docker.io/library/nginx:this-tag-does-not-exist:
not found
```

**Question 3: Which command helped you find the reason?**
`kubectl describe pod project-broken-pod -n hw14`, specifically its `Events` section. `kubectl get`
only told me the status word; `kubectl logs` actively refused because the container never started.
The equivalent scoped form is `kubectl events -n hw14 --for pod/project-broken-pod`.

**Question 4: What is wrong with the image?**
The repository `docker.io/library/nginx` is correct and reachable — the failure is `code = NotFound`
on reference *resolution*, not an authentication failure. So the repo exists and the **tag**
`this-tag-does-not-exist` does not. If the repository itself had been wrong, the message would have
read `pull access denied, repository does not exist or may require authorization` instead, as in
Task 2 scenario 2.

**Question 5: How would you fix it?**
Replace the tag with one that exists — `nginx:1.27` — which is what `03-mini-project/fixed-pod.yaml`
does. Because a pod's image can be changed in place but its name cannot be reused while it exists,
the clean path for a bare pod is delete and re-create; for a Deployment it is
`kubectl set image deployment/<name> <container>=<image>`, which triggers a rolling update. The
durable fixes are to pin a digest (`nginx@sha256:...`) so a tag can never drift, and to verify tags
exist in CI before they reach a manifest.

### 8. Service troubleshooting challenge

Change the selector from `app: troubleshooting-app` to `app: wrong-app` and apply
(`03-mini-project/service-broken.yaml`):

```bash
kubectl apply -f 03-mini-project/service-broken.yaml
kubectl get service troubleshooting-service -n hw14
kubectl get endpoints troubleshooting-service -n hw14
```

```text
service/troubleshooting-service configured

NAME                      TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
troubleshooting-service   ClusterIP   10.103.161.66   <none>        80/TCP    38s

NAME                      ENDPOINTS   AGE
troubleshooting-service   <none>      38s
```

`<none>`, exactly as the project predicts. The Service object itself still looks completely healthy —
same ClusterIP, same port, no events, no warning. And traffic now fails:

```bash
kubectl exec netshoot -n hw14 -- curl -sS -m5 -o /dev/null -w 'HTTP %{http_code}\n' http://troubleshooting-service
```

```text
HTTP 000
curl: (7) Failed to connect to troubleshooting-service:80 after 4 ms: Could not connect to server
```

Meanwhile the pods never moved — still `1/1 Running`, still serving on localhost. This is the lesson
the project is driving at: a Service outage with perfectly healthy pods.

### 9. Find the root cause

```bash
kubectl get pods -n hw14 -l app=troubleshooting-app --show-labels
kubectl describe service troubleshooting-service -n hw14 | grep -E 'Selector|Endpoints'
```

```text
NAME                                   READY   STATUS    RESTARTS   AGE   LABELS
troubleshooting-app-66cbd59bf6-q7rw6   1/1     Running   0          39s   app=troubleshooting-app,pod-template-hash=66cbd59bf6
troubleshooting-app-66cbd59bf6-rt5tp   1/1     Running   0          39s   app=troubleshooting-app,pod-template-hash=66cbd59bf6

Selector:                 app=wrong-app
Endpoints:
```

Pod label `app=troubleshooting-app`, Service selector `app=wrong-app`. The mismatch is the root cause.
Restore the correct selector:

```bash
kubectl apply -f 03-mini-project/service.yaml
kubectl get endpoints troubleshooting-service -n hw14
kubectl exec netshoot -n hw14 -- curl -sS -m5 -o /dev/null -w 'HTTP %{http_code}\n' http://troubleshooting-service
```

```text
service/troubleshooting-service configured
NAME                      ENDPOINTS                         AGE
troubleshooting-service   10.244.0.103:80,10.244.0.104:80   48s
HTTP 200
```

And fix the broken pod:

```bash
kubectl apply -f 03-mini-project/fixed-pod.yaml
kubectl get pod project-broken-pod project-fixed-pod -n hw14
kubectl get endpoints troubleshooting-service -n hw14
```

```text
pod/project-fixed-pod created
NAME                 READY   STATUS         RESTARTS   AGE
project-broken-pod   0/1     ErrImagePull   0          34s
project-fixed-pod    1/1     Running        0          3s

NAME                      ENDPOINTS                                         AGE
troubleshooting-service   10.244.0.103:80,10.244.0.104:80,10.244.0.106:80   51s
```

A third endpoint appeared. `project-fixed-pod` carries `app: troubleshooting-app`, so the Service
adopted it immediately — a bare pod with the right label becomes a backend with no further
configuration. That is label-based selection working exactly as designed, and it is also how an
unrelated pod can accidentally start receiving production traffic.

```bash
kubectl exec netshoot -n hw14 -- nslookup troubleshooting-service
```

```text
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	troubleshooting-service.hw14.svc.cluster.local
Address: 10.103.161.66
```

### 10 & 11. Troubleshooting table

| Problem | What I Saw | Command I Used | Root Cause | Fix |
| :--- | :--- | :--- | :--- | :--- |
| **Broken Pod** | `0/1 ErrImagePull`, `RESTARTS 0`, flipping to `ImagePullBackOff`. `kubectl logs` refused with `container "app" ... is waiting to start: image can't be pulled` | `kubectl describe pod project-broken-pod -n hw14` → Events | The pod requests `nginx:this-tag-does-not-exist`; containerd resolved the repo but not the reference (`code = NotFound ... not found`) | Use a tag that exists (`nginx:1.27`); pin a digest in production |
| **Service Problem** | `kubectl get endpoints` returned `<none>`; curl through the ClusterIP failed in 4 ms with `Could not connect`; pods stayed `1/1 Running` throughout | `kubectl get endpoints troubleshooting-service -n hw14`, then `kubectl get pods --show-labels` vs `kubectl describe service` | Selector `app=wrong-app` matched no pod; pods are labelled `app=troubleshooting-app`. The endpoints controller wrote an empty EndpointSlice and kube-proxy programmed a ClusterIP with no backends | Restore `selector: app: troubleshooting-app`; endpoints repopulated within seconds and curl returned 200 |
| **Image Problem** | `Failed to pull image ... code = NotFound`, repeating `Pulling → Failed → BackOff` with `RESTARTS` stuck at 0 | `kubectl describe pod` Events, plus `.status.containerStatuses[0].state.waiting.reason` for the live phase | Valid repository, invalid tag. Distinct from a wrong repo name, which returns `pull access denied, repository does not exist or may require authorization` | Correct the tag; verify tags in CI before merge so a bad reference never ships |

### 12. The project's README questions

**1. What does `kubectl get` tell us?**
The current status of resources in one line each — `READY`, `STATUS`, `RESTARTS`, `AGE`. It answers
"what is the state right now" and nothing more. It is the fastest way to find *which* object is
unhealthy, and it never tells you why.

**2. What is the difference between `get` and `describe`?**
`get` is a summary across many objects; `describe` is everything the control plane knows about one
object. Concretely, `describe` adds the spec as applied (image, ports, mounts, resources), the
container `State` and `Last State` with exit codes, the pod `Conditions`, the volumes, the QoS class,
and — most importantly — the **Events** that explain what Kubernetes attempted. `get` tells you
*what*; `describe` tells you *why*.

**3. Why do we use `kubectl logs`?**
To read what the application itself wrote to stdout and stderr. `describe` reports what Kubernetes
did to the container; `logs` reports what the process inside it said. In a crash loop the critical
form is `kubectl logs <pod> --previous`, which reads the container that actually died rather than the
one that just restarted. For a multi-container pod, `-c <container>` is required.

**4. When would you use `kubectl exec`?**
When the answer is only visible from inside the container: is the file really mounted, what is the
process actually listening on (`netstat -tlnp`), does DNS resolve from here, can this pod reach that
pod. It requires a *running* container, so it is unavailable precisely when the pod is crash-looping
— `kubectl debug` with an ephemeral container covers that gap, as does `logs --previous`.

**5. What does `CrashLoopBackOff` mean?**
The container starts, exits, and the kubelet restarts it — repeatedly — so the kubelet is now
deliberately waiting between attempts, with the delay doubling from 10s up to a 5-minute cap. It is
not an error type but a *restart policy state*. The real error is in the exit code (`Last State`) and
the previous container's logs. Common causes: application exits on a missing config value, bad
entrypoint (exit 127), failing liveness probe, or OOMKilled (exit 137).

**6. What does `ImagePullBackOff` mean?**
The kubelet could not pull the container image and is waiting before trying again. The container has
never started, which is why `RESTARTS` stays 0 and there are no logs. Causes: wrong image name or
tag, private registry with no or invalid `imagePullSecrets`, or a node that cannot reach the registry
at all. The paired state `ErrImagePull` is the same problem caught during an attempt rather than
during a wait.

**7. Why can a Pod remain `Pending`?**
Because the scheduler cannot place it on any node. The event message names the filter that rejected
it: `Insufficient cpu/memory` (requests exceed allocatable), `didn't match Pod's node
affinity/selector` (no node has the required labels), `node(s) had untolerated taint` (needs a
toleration), or `pod has unbound immediate PersistentVolumeClaims` (its storage will not bind).
A Pending pod has no node and no IP, so `logs` and `exec` are both unavailable — `describe` is the
only tool.

**8. Why can a Service have no endpoints?**
Because no *ready* pod matches its selector. Either the selector does not match any pod's labels
(a typo, or a label changed during a refactor), or pods match but are failing their readiness probe —
an unready pod is removed from the endpoint list even while it is Running. A Service with a selector
matching nothing is a completely legal object: no event, no warning, no apply failure.

**9. What is the relationship between a Service selector and Pod labels?**
The selector is a label query. The endpoints controller continuously watches for pods whose labels
are a superset of the selector and whose readiness condition is true, and writes their IP:port into
an EndpointSlice. kube-proxy turns that slice into the forwarding rules behind the ClusterIP. The
coupling is purely by label — there is no reference by name and no ownership, so any pod that happens
to carry the right label becomes a backend, and removing a label silently removes a backend.

**10. What is Kubernetes DNS?**
CoreDNS, running in `kube-system` behind the `kube-dns` Service at `10.96.0.10` on this cluster. Every
Service gets an A record at `<service>.<namespace>.svc.cluster.local`. Each pod's
`/etc/resolv.conf` points at that ClusterIP and carries `search <ns>.svc.cluster.local
svc.cluster.local cluster.local` with `options ndots:5`, so a short name is tried against the pod's
own namespace first. That is why `shop-api-svc` works inside `hw14` but the same short name fails
from another namespace, where you need `shop-api-svc.hw14`.

### 13. Final architecture

```text
                        hw14 namespace
                              │
                              ▼
              ┌──────────────────────────────┐
              │  Service: troubleshooting-   │
              │  service  (ClusterIP         │
              │  10.103.161.66:80)           │
              └──────────────┬───────────────┘
                             │
                 selector: app=troubleshooting-app
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        10.244.0.103   10.244.0.104   10.244.0.106
         (Deployment    (Deployment    (project-
          replica 1)     replica 2)     fixed-pod)
              │              │              │
              └──────────────┼──────────────┘
                             │
                         nginx:1.27
```

Each address in that diagram was taken from the live `kubectl get endpoints` output above.

---

## Triage flowchart — symptom to first command to likely cause

The point of a flowchart is to stop you running `kubectl describe` on everything. Start at the
`STATUS` column of `kubectl get pods` and take one branch.

```text
                         kubectl get pods -n <ns> -o wide
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        ▼                             ▼                             ▼
   STATUS is Pending           STATUS is a wait/err state      STATUS is Running
   (NODE = <none>)             (container never ran)           (but something is wrong)
        │                             │                             │
        │                             │                             │
        ▼                             ▼                             ▼
  kubectl describe pod         kubectl describe pod           READY column?
  → read Events only           → read Events only                  │
        │                             │                  ┌─────────┴─────────┐
        │                             │                  │                   │
        │                             │                  ▼                   ▼
        │                             │               0/1 Ready           1/1 Ready
        │                             │          (readiness failing)   (truly running)
        │                             │                  │                   │
        │                             │                  ▼                   ▼
        │                             │          describe → Probe      RESTARTS > 0?
        │                             │          failed events          │        │
        │                             │          → check probe path    yes       no
        │                             │             and port            │        │
        │                             │                                 ▼        ▼
        │                             │                        logs --previous   it is a
        │                             │                        + Last State      networking or
        │                             │                        exit code         Service problem
        ▼                             ▼
  ── Event message says ──     ── STATUS is ──

  Insufficient cpu/memory      ErrImagePull  /  ImagePullBackOff
    → requests > allocatable     → describe Events, read the FULL image path
    → fix requests, or add         NotFound          → bad tag
      a node                       access denied     → bad repo, or missing imagePullSecrets
                                   i/o timeout       → node cannot reach the registry
  didn't match Pod's node
  affinity/selector            CreateContainerConfigError
    → nodeSelector label           → describe Events names the key
      does not exist               → configMapKeyRef / secretKeyRef points at a missing key
    → label the node, or
      fix the selector         ContainerCreating (stuck > 30s)
                                   → describe Events
  node(s) had untolerated          FailedMount "secret/configmap X not found" → create it
  taint                            FailedAttachVolume / FailedMount on a PVC  → check PVC + node
    → add a toleration             no events, large image                    → it is just pulling
                                   failed to set up sandbox ... network      → CNI problem
  pod has unbound immediate
  PersistentVolumeClaims       CrashLoopBackOff  /  Error  /  OOMKilled
    → kubectl get pvc              → kubectl describe pod, read Last State FIRST
    → kubectl describe pvc           Reason: OOMKilled, exit 137 → raise limits.memory. STOP HERE.
    → usually the storage            exit 127                    → command not found in image
      class does not exist           exit 1 / 2 / other          → kubectl logs --previous
                                                                    the app will tell you
```

And for the Running-but-unreachable branch, which the chart above hands off:

```text
        Pod is Running and Ready, but traffic does not arrive
                              │
                              ▼
          kubectl get endpoints <svc>   ← the single highest-value command
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   ENDPOINTS <none>    populated, wrong port   populated and correct
        │                     │                     │
        ▼                     ▼                     ▼
  compare labels        targetPort does not     the Service is fine.
  vs selector:          match the port the      Test lower down:
  kubectl get pods      container listens on          │
    --show-labels       → fix targetPort              ▼
  kubectl describe svc                          nslookup <svc> from a pod
        │                                             │
        ├── no pod matches → selector typo       ┌────┴────┐
        │                                        ▼         ▼
        └── pods match but 0/1 Ready        NXDOMAIN    resolves
            → readiness probe is failing,       │           │
              not a selector problem            ▼           ▼
                                           wrong name   curl pod IP
                                           or missing   directly
                                           namespace         │
                                           qualifier    ┌────┴────┐
                                                        ▼         ▼
                                                   refused    times out
                                                      │           │
                                                      ▼           ▼
                                              app bound to   NetworkPolicy
                                              127.0.0.1      dropping packets
                                              (netstat -tlnp (refused ≠ timeout:
                                               inside pod)    refused means nothing
                                                              is listening, timeout
                                                              means something drops)
```

The one rule underneath all of it: **a Pending pod has no logs and no shell**, so `describe` is the
only tool; **a Running pod's problem is rarely in `describe`**, so go to `logs` and `exec`.

---

## Symptom / cause / fix reference

All nine issue types from the task, plus OOMKilled.

| # | Symptom (`kubectl get`) | First command | Likely root cause | Fix | Real error text seen in this lab |
| :-- | :--- | :--- | :--- | :--- | :--- |
| 1 | `CrashLoopBackOff`, `RESTARTS` climbing | `kubectl logs <pod> --previous` | Container starts then exits. Missing env var, bad config, failing dependency, bad entrypoint | Supply the missing config / fix the command; fix the Deployment, not the pod | `[FATAL] DATABASE_URL environment variable is MISSING` with `lastState.terminated exitCode=1` |
| 2 | `ImagePullBackOff`, `RESTARTS 0` | `kubectl describe pod` → Events | Kubelet is backing off from a failed pull. Wrong repo path, or private registry without `imagePullSecrets` | Correct the image path; add `imagePullSecrets` | `pull access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed` |
| 3 | `ErrImagePull`, `RESTARTS 0` | `kubectl describe pod` → Events | Same problem as #2, caught during an attempt instead of a wait. Oscillates with `ImagePullBackOff` | Same as #2. Read the error text, not the status word | `rpc error: code = NotFound desc = failed to resolve reference "docker.io/library/nginx:1.27-alpine-typo": ... not found` |
| 4 | `Pending`, `NODE <none>` | `kubectl describe pod` → Events | `resources.requests` exceed every node's allocatable capacity | Right-size requests, or add capacity | `0/1 nodes are available: 1 Insufficient cpu, 1 Insufficient memory. preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.` |
| 5 | `Pending`, `NODE <none>` | `kubectl describe pod` → Events, then `kubectl get nodes --show-labels` | `nodeSelector` / nodeAffinity requires a label no node carries | Label the node, or correct the selector; prefer soft affinity | `0/1 nodes are available: 1 node(s) didn't match Pod's node affinity/selector.` |
| 6 | `Pending`, `NODE <none>`, PVC also `Pending` | `kubectl get pvc` then `kubectl describe pvc` | The PVC cannot bind — usually a storage class that does not exist on this cluster | Use an existing storage class | pod: `0/1 nodes are available: pod has unbound immediate PersistentVolumeClaims.` / pvc: `storageclass.storage.k8s.io "fast-nvme" not found` |
| 7 | `ContainerCreating` for minutes, `NODE` set but `IP <none>` | `kubectl describe pod` → Events | Kubelet cannot build a volume: a Secret or ConfigMap mounted as a volume does not exist | Create the Secret/ConfigMap — the stuck pod heals itself, no delete needed | `MountVolume.SetUp failed for volume "tls" : secret "gateway-tls" not found` |
| 8 | Pods `1/1 Running`, clients get connection refused | `kubectl get endpoints <svc>` | `<none>` → Service selector does not match pod labels (or all pods are unready). Populated with wrong port → `targetPort` mismatch | Align selector with labels; set `targetPort` to the real container port | `ENDPOINTS <none>` with `Selector: app=shop-api-v2` against pods labelled `app=shop-api`; and `curl: (7) Failed to connect ... after 1 ms` |
| 9 | App cannot reach another service by name | `kubectl exec <pod> -- nslookup <name>` | Wrong service name, or a short name used across namespaces (the search list starts with the pod's *own* namespace) | Use the right name, or qualify it: `<svc>.<namespace>` | `** server can't find kubernetes: NXDOMAIN` for a Service that exists in `default`, resolved by `kubernetes.default.svc.cluster.local` |
| 10 | Pod `1/1 Running`, endpoints correct, still unreachable | `kubectl exec <pod> -- netstat -tlnp` | The process is bound to `127.0.0.1` instead of `0.0.0.0`. `containerPort` is informational and does not change this | Bind to `0.0.0.0` (or `::`) in the app's own config | `tcp 0 0 127.0.0.1:80 0.0.0.0:* LISTEN 1/nginx` while `wget http://10.244.0.81/` from the same container gives `Connection refused` |
| 11 | `CreateContainerConfigError`, `RESTARTS 0` | `kubectl describe pod` → Events | `configMapKeyRef` / `secretKeyRef` names a key that is not in the ConfigMap or Secret | Fix the key name, or mark it `optional: true` if the app has a default | `Error: couldn't find key LOGLEVEL in ConfigMap hw14/billing-config` |
| 12 | `OOMKilled`, looks like a crash loop | `kubectl describe pod` → `Last State` → `Reason` | Working set exceeds `resources.limits.memory`; the kernel SIGKILLs with no warning | Raise the limit to the real working set (check with `kubectl top pod`), or reduce allocation | `Reason: OOMKilled`, `Exit Code: 137`, with events identical in shape to an ordinary crash loop and logs cut off mid-task |

Three cross-cutting rules that fall out of the table:

1. **`RESTARTS 0` separates two whole families.** Zero restarts with a non-Running status means the
   container never started (image, config, volume, scheduling). A climbing count means it started and
   died (application, memory, probes).
2. **`NODE` in `-o wide` separates scheduler problems from kubelet problems.** `<none>` means the
   scheduler rejected it; populated means the scheduler succeeded and the kubelet is struggling.
3. **Refused is not timeout.** An immediate `Connection refused` means nothing is listening at that
   address. A hang until timeout means something is dropping packets — NetworkPolicy, a firewall, or
   a wrong route.

---

## Interview questions

**1. A pod is in `CrashLoopBackOff`. Walk me through your first five minutes.**
`kubectl get pod -o wide` to confirm restart count and node. `kubectl describe pod` and read
`Last State` before anything else — the exit code branches the whole investigation: 137 with
`Reason: OOMKilled` means stop and go look at memory limits, 127 means the entrypoint binary is not
in the image, anything else means read the logs. Then `kubectl logs <pod> --previous`, because the
current container is either dead or freshly restarted and will not have the error. If `--previous`
fails with `unable to retrieve container logs`, the dead container was already garbage-collected —
fall back to `Last State` and to whatever the log shipper captured. Only then do I look at the
manifest.

**2. What is the difference between `ErrImagePull` and `ImagePullBackOff`?**
They are the same problem in two phases. `ErrImagePull` means a pull attempt just failed.
`ImagePullBackOff` means the kubelet is sleeping before the next attempt, with the delay growing each
round. A pod oscillates between them indefinitely. The status word is not diagnostic — the error text
in `describe`'s events is: `NotFound` means a bad tag, `pull access denied` / `insufficient_scope`
means a bad repository path or a missing pull secret, and an `i/o timeout` means the node cannot
reach the registry at all, which is a networking problem wearing an image problem's clothes.

**3. Pods are `1/1 Running` and healthy, but the Service returns nothing. Where do you look first?**
`kubectl get endpoints <svc>` — it collapses the search space in one command. `<none>` means no ready
pod matches the selector, so I compare `kubectl get pods --show-labels` against
`kubectl describe svc`'s `Selector` line, and I check readiness too, because an unready pod is pulled
out of the endpoint list even while it shows as Running. If endpoints are populated I check the port
on them against what the container actually listens on, and then I stop blaming the Service and start
testing from a pod: `nslookup` for DNS, then `curl` straight at a pod IP to bypass the Service
entirely.

**4. A pod has been `ContainerCreating` for ten minutes. What is happening, and does deleting it
help?**
The scheduler succeeded (the pod has a node) and the kubelet is blocked — almost always on a volume.
`kubectl describe pod` and read the `FailedMount` event: a missing Secret or ConfigMap volume, or a
PVC that cannot attach. Deleting the pod does not help if the cause is still there; it just recreates
the same wait. The useful thing to know is the opposite: once you create the missing object, the
kubelet's retry loop picks it up and the *existing* pod starts on its own. I demonstrated that in this
lab — a pod stuck for over four minutes went to `Running` once the Secret appeared, with both the
failures and the recovery preserved in its event history.

**5. Why can `kubectl top node` show a node at 10% CPU while the scheduler says `Insufficient cpu`?**
Because the scheduler filters on **requests**, not on usage. Requests are reservations: once a pod
requests 2 cores, those 2 cores are spoken for whether or not the process ever uses them. `top` shows
measured consumption. A cluster full of over-requesting, under-using pods looks idle and schedules
nothing. The fix is to right-size requests against observed usage — which is exactly what `top` is
good for, as a capacity-planning input rather than a triage tool.

**6. A service name resolves from one namespace but not another. Explain.**
Every pod's `/etc/resolv.conf` has `search <own-namespace>.svc.cluster.local svc.cluster.local
cluster.local` and `options ndots:5`. A bare name like `payments` has fewer than 5 dots, so the
resolver walks the search list and tries the pod's **own** namespace first. From `hw14`, `payments`
becomes `payments.hw14.svc.cluster.local` — which does not exist if the Service lives in `billing`.
The fix is `payments.billing`, which the search list completes correctly. I showed exactly this with
the `kubernetes` Service: `nslookup kubernetes` from `hw14` returns NXDOMAIN, while
`kubernetes.default.svc.cluster.local` returns `10.96.0.1`.

**7. What does `ndots:5` actually cost you?**
Every external lookup is tried against all three search suffixes before the bare name. `api.stripe.com`
has two dots, under the threshold, so the resolver tries `api.stripe.com.hw14.svc.cluster.local`,
then `.svc.cluster.local`, then `.cluster.local`, and only then the real name — four queries (eight
with IPv6 A and AAAA pairs) for one hostname. Under load that is real CoreDNS pressure and real
latency. Mitigations: a trailing dot to make the name fully qualified (`api.stripe.com.`), or a
per-pod `dnsConfig` lowering `ndots`, or NodeLocal DNSCache.

**8. How do you troubleshoot a pod that has no shell — distroless or scratch?**
`kubectl exec` is useless because there is no `/bin/sh`. `kubectl debug -it <pod> --image=nicolaka/netshoot
--target=<container>` attaches an ephemeral container that shares the target's network and (with
`--target`) its process namespace, so you get a full toolbox against the same pod IP and the same
sockets without changing the pod. For a pod that will not start at all, `kubectl debug <pod>
--copy-to=<name> --set-image=*=busybox --share-processes` makes a debuggable copy.

**9. Exit code 137 and exit code 143 — what is the difference and why does it matter?**
Both are `128 + signal`. 137 is SIGKILL (9), 143 is SIGTERM (15). 143 is usually *normal*: the
container was asked to shut down and complied, which is what you see during a rolling update or a
scale-down. 137 means something killed it outright — almost always the cgroup OOM killer, occasionally
a kubelet eviction, occasionally an application that ignored SIGTERM past
`terminationGracePeriodSeconds` and got escalated. Confusing the two sends people hunting for a bug
during what was an ordinary deployment.

**10. What is the first thing you check when `kubectl get pods` shows everything Running but users
report errors?**
The `READY` column, not `STATUS`. `1/1` versus `0/1` is the difference between "the container
process is alive" and "the container is receiving traffic". A pod can be Running and 0/1 forever
because its readiness probe fails, and that pod is silently removed from every Service's endpoints —
so users get errors from a cluster where nothing appears to be wrong. After that: `kubectl get
endpoints`, and then the application's own logs and error rates, because at that point Kubernetes has
done its job and the fault is in the application.

**11. Your `describe` output shows no Events at all. What does that mean?**
Events have a TTL — one hour by default — and they live in etcd, not in the object. An empty Events
block means the incident is older than the retention window, not that nothing happened. The durable
evidence that survives is in the object's own status: `Last State` with its exit code and timestamps,
`Restart Count`, and the pod `Conditions`. This is the main argument for shipping events to a
monitoring system; by the time a human is paged and logs in, the events are often already gone.

**12. How would you prove that a problem is a NetworkPolicy and not an application bug?**
By the failure mode. A NetworkPolicy drops packets, so the client hangs and eventually times out. An
application that is not listening refuses the connection immediately — `curl` reports
`Connection refused` in single-digit milliseconds. So: `curl` from a pod that should be allowed and
one that should not, and compare refused versus timeout. Then confirm the socket exists at all with
`netstat -tlnp` inside the target pod, and list policies with `kubectl get networkpolicy -n <ns> -o yaml`,
remembering that policies are additive-deny — once *any* ingress policy selects a pod, everything not
explicitly allowed is denied.

**13. What is the single most useful command in this whole toolkit, and why?**
`kubectl logs <pod> --previous`. Every other command tells you what Kubernetes observed from the
outside; this one is the only way to hear the dead process's last words, and in a crash loop that is
usually the entire answer. The catch is that it is time-limited — once the kubelet garbage-collects
the dead container, its log file goes with it, which I hit for real in this lab on a container that
crashed in under a second. So it is also the command with the shortest window to use it.

---

## Cleanup

Everything in this lab was created inside the namespace `hw14`, including the deliberately broken
workloads. Final inventory before teardown:

```bash
kubectl get all -n hw14
```

```text
NAME                                       READY   STATUS                       RESTARTS        AGE
pod/config-broken                          0/1     CreateContainerConfigError   0               16m
pod/config-fixed                           1/1     Running                      0               13m
pod/containercreating-broken               1/1     Running                      0               16m
pod/containercreating-fixed                1/1     Running                      0               13m
pod/crashloop-broken                       0/1     Error                        8 (5m26s ago)   16m
pod/crashloop-fixed                        1/1     Running                      0               13m
pod/demo-crasher                           0/1     CrashLoopBackOff             8 (4m1s ago)    22m
pod/demo-web                               1/1     Running                      0               23m
pod/errimagepull-broken                    0/1     ImagePullBackOff             0               19m
pod/errimagepull-fixed                     1/1     Running                      0               13m
pod/imagepullbackoff-broken                0/1     ImagePullBackOff             0               16m
pod/imagepullbackoff-fixed                 1/1     Running                      0               13m
pod/netbind-broken                         1/1     Running                      0               11m
pod/netbind-fixed                          1/1     Running                      0               11m
pod/netshoot                               1/1     Running                      0               11m
pod/oomkilled-broken                       0/1     CrashLoopBackOff             7 (2m42s ago)   13m
pod/oomkilled-fixed                        1/1     Running                      0               13m
pod/pending-nodeselector-broken            0/1     Pending                      0               16m
pod/pending-nodeselector-fixed             1/1     Running                      0               13m
pod/pending-pvc-broken                     0/1     Pending                      0               16m
pod/pending-pvc-fixed                      1/1     Running                      0               13m
pod/pending-resources-broken               0/1     Pending                      0               16m
pod/pending-resources-fixed                1/1     Running                      0               13m
pod/project-broken-pod                     0/1     ImagePullBackOff             0               4m8s
pod/project-fixed-pod                      1/1     Running                      0               3m37s
pod/shop-api-76498ddf54-g65rs              1/1     Running                      0               11m
pod/shop-api-76498ddf54-wqd4c              1/1     Running                      0               11m
pod/troubleshooting-app-66cbd59bf6-q7rw6   1/1     Running                      0               4m25s
pod/troubleshooting-app-66cbd59bf6-rt5tp   1/1     Running                      0               4m25s

NAME                              TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
service/shop-api-svc              ClusterIP   10.98.7.160     <none>        80/TCP    11m
service/troubleshooting-service   ClusterIP   10.103.161.66   <none>        80/TCP    4m25s

NAME                                  READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/shop-api              2/2     2            2           11m
deployment.apps/troubleshooting-app   2/2     2            2           4m25s

NAME                                             DESIRED   CURRENT   READY   AGE
replicaset.apps/shop-api-76498ddf54              2         2         2       11m
replicaset.apps/troubleshooting-app-66cbd59bf6   2         2         2       4m25s
```

That single screen is itself a useful artefact: eleven distinct failure states and their fixes, side
by side. Note `demo-crasher` and `oomkilled-broken` have both reached `CrashLoopBackOff` after enough
restarts, while `crashloop-broken` was caught in the `Error` phase between backoffs — the same
oscillation described in scenario 3, in a different pair of states. `containercreating-broken` reads
`1/1 Running` because it healed itself when its Secret was created.

The non-workload objects:

```bash
kubectl get pvc,configmap,secret -n hw14
kubectl get pv
```

```text
NAME                                       STATUS    VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
persistentvolumeclaim/reports-pvc-broken   Pending                                                                        fast-nvme      <unset>                 16m
persistentvolumeclaim/reports-pvc-fixed    Bound     pvc-f2e5141e-47de-4082-917a-1af8fb6c8a83   1Gi        RWO            standard       <unset>                 13m

NAME                            DATA   AGE
configmap/allhosts-nginx-conf   1      11m
configmap/billing-config        3      16m
configmap/kube-root-ca.crt      1      24m
configmap/loopback-nginx-conf   1      11m

NAME                 TYPE     DATA   AGE
secret/gateway-tls   Opaque   2      13m

NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                    STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
pvc-f2e5141e-47de-4082-917a-1af8fb6c8a83   1Gi        RWO            Delete           Bound    hw14/reports-pvc-fixed   standard       <unset>                          13m
```

Teardown is a single command, because every object is namespaced:

```bash
kubectl delete namespace hw14
```

```text
namespace "hw14" deleted
```

Verification — the namespace is gone, nothing survives inside it, the dynamically provisioned
PersistentVolume was reclaimed (its `RECLAIM POLICY` was `Delete`), and no pod from this lab is
running anywhere in the cluster:

```bash
kubectl get ns
kubectl get all -n hw14
kubectl get pv
kubectl get pods -A --no-headers | grep -E 'crashloop|imagepull|errimagepull|pending-|containercreating|netbind|netshoot|oomkilled|config-|shop-api|troubleshooting|demo-|project-' || echo "none"
```

```text
NAME              STATUS   AGE
default           Active   19d
hw13              Active   23m
ingress-nginx     Active   19d
kube-node-lease   Active   19d
kube-public       Active   19d
kube-system       Active   19d

No resources found in hw14 namespace.

No resources found

none
```

No cluster-scoped objects were created by this lab, so nothing outside the namespace needed cleaning
up. (`hw13` in that listing belongs to a different exercise running on the same shared cluster, not
to this one.)
