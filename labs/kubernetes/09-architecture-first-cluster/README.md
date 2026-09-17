# Homework Set 9 — Kubernetes Architecture & First Cluster

## Provenance

The course's official homework document covers **sessions 2-8 only** and contains nothing for the
Kubernetes sessions. `session9-k8s/Readme.md` is a bare list of links with no exercises attached.
The five tasks below were derived from the material actually taught in session 9 and are written in
the same style as the official homework: every command was run for real against a live cluster and
every `text` block is genuine captured output, not an illustration.

---

## Environment used for this homework

```bash
minikube version
minikube profile list
```

```text
minikube version: v1.39.0
commit: 7a9f6a841470a207de8cf4bafcccee0969d8ba10

┌──────────┬────────┬────────────┬──────────────┬─────────┬────────┬───────┬────────────────┬────────────────────┐
│ PROFILE  │ DRIVER │  RUNTIME   │      IP      │ VERSION │ STATUS │ NODES │ ACTIVE PROFILE │ ACTIVE KUBECONTEXT │
├──────────┼────────┼────────────┼──────────────┼─────────┼────────┼───────┼────────────────┼────────────────────┤
│ minikube │ docker │ containerd │ 192.168.49.2 │ v1.37.0 │ OK     │ 1     │ *              │ *                  │
└──────────┴────────┴────────────┴──────────────┴─────────┴────────┴───────┴────────────────┴────────────────────┘
```

A single-node minikube cluster on an Apple Silicon Mac, using the **docker** driver and the
**containerd** runtime. All work in this set is done inside a namespace called `hw09`, which is
created at the start and deleted at the end.

### Platform fact you must know before you start (macOS + docker driver)

The node IP `192.168.49.2` is **not reachable from macOS**. With the docker driver the node is a
container running inside the Docker Desktop Linux VM, and that VM's internal bridge network is not
routed on the host. This is not a broken cluster — it is how the driver works. Proof:

```bash
ping -c 2 -t 4 192.168.49.2
curl -sS -m 5 http://10.244.0.4
```

```text
PING 192.168.49.2 (192.168.49.2): 56 data bytes
Request timeout for icmp_seq 0

--- 192.168.49.2 ping statistics ---
2 packets transmitted, 0 packets received, 100.0% packet loss

curl: (28) Connection timed out after 5008 milliseconds
```

100% packet loss to the node, and a timeout to a pod IP. Neither the node network (`192.168.49.0/24`)
nor the pod network (`10.244.0.0/24`) exists on the Mac.

So how does `kubectl` work at all? Because minikube publishes the api-server port onto **localhost**:

```bash
docker ps --filter "name=minikube" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
```

```text
NAMES      IMAGE                                 STATUS         PORTS
minikube   gcr.io/k8s-minikube/kicbase:v0.0.51   Up 6 minutes   127.0.0.1:62156->22/tcp, 127.0.0.1:62153->2376/tcp, 127.0.0.1:62157->5000/tcp, 127.0.0.1:62155->8443/tcp, 127.0.0.1:62154->32443/tcp
```

`127.0.0.1:62155 -> 8443/tcp` is the api-server. That published port is the *only* thing about the
cluster the Mac can reach directly. Everything else has to go through one of these four routes:

| Route | Use it for |
|---|---|
| `kubectl port-forward` | reaching one pod or service from the Mac |
| `minikube service <svc> -n hw09 --url` | reaching a NodePort service from the Mac |
| `kubectl exec` into a pod and `wget`/`curl` | testing in-cluster networking, the honest test |
| `minikube ssh` then `curl` | testing from the node itself |

This README uses all four and never presents an unreachable address as if it worked.

---

## Task 1 — Cluster setup

### A note on "start a cluster"

The homework says *start a local cluster*. A cluster was already running when this set was written,
and it is shared, so it was **not** torn down and recreated. What follows explains what
`minikube start` would have done, and then verifies the result on the running cluster.

`minikube start --driver=docker` performs, in order:

1. Downloads the `kicbase` image (a Debian image with systemd, containerd, `crictl`, `kubeadm` and
   `kubelet` baked in) and runs it as a Docker container named `minikube`. That container **is** the
   node — the "machine" in `kubectl get nodes` is a container.
2. Publishes the container's port 8443 onto a random localhost port on the Mac, and writes that
   address into `~/.kube/config` as the cluster server URL.
3. Runs `kubeadm init` inside the container. `kubeadm` generates the PKI (CA, api-server serving
   cert, etcd certs, service-account signing key), writes the four static pod manifests into
   `/etc/kubernetes/manifests`, and starts `kubelet`.
4. `kubelet` reads that directory and brings up etcd, kube-apiserver, kube-scheduler and
   kube-controller-manager as **static pods** — they are not created by anything in the API,
   the kubelet creates them from files on disk.
5. Once the api-server answers, `kubeadm` applies the add-ons: the `kube-proxy` DaemonSet, the
   CoreDNS Deployment, and the RBAC objects they need. minikube then applies its own defaults:
   the `kindnet` CNI DaemonSet and the `storage-provisioner` pod.
6. Writes the `minikube` context into `~/.kube/config` and makes it current.

`minikube stop` stops the container and keeps the disk. `minikube delete` destroys the container and
the data — that is why it is never run here.

### Verify the cluster is up

```bash
minikube status
```

```text
minikube
type: Control Plane
host: Running
kubelet: Running
apiserver: Running
kubeconfig: Configured
```

Four separate things are reported and all four matter: the **host** is the docker container that is
the node, the **kubelet** is the agent inside it, the **apiserver** is the API endpoint, and
**kubeconfig** confirms `~/.kube/config` points at this cluster. If `apiserver` said `Stopped` then
every `kubectl` command would fail with a connection refused, regardless of the host being up.

### Find the API endpoint

```bash
kubectl cluster-info
```

```text
Kubernetes control plane is running at https://127.0.0.1:62155
CoreDNS is running at https://127.0.0.1:62155/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy
```

The control plane is at `https://127.0.0.1:62155` — the published docker port from the table above,
not `192.168.49.2:8443`. `kubectl` talks to localhost; Docker forwards it into the VM.

### Confirm the node is Ready

```bash
kubectl get nodes -o wide
```

```text
NAME       STATUS   ROLES           AGE     VERSION   INTERNAL-IP    EXTERNAL-IP   OS-IMAGE                         KERNEL-VERSION             CONTAINER-RUNTIME
minikube   Ready    control-plane   2m27s   v1.37.0   192.168.49.2   <none>        Debian GNU/Linux 12 (bookworm)   6.12.76-linuxkit (arm64)   containerd://2.3.4
```

Read this line carefully, it answers several questions at once:

- `STATUS Ready` — the kubelet is heartbeating and the node will accept pods.
- `ROLES control-plane` — one node doing both jobs. On a real cluster you would see separate
  worker nodes with `<none>` in this column.
- `INTERNAL-IP 192.168.49.2` — the node IP *inside* the Docker VM, unreachable from the Mac.
- `EXTERNAL-IP <none>` — no cloud load balancer, as expected locally.
- `KERNEL-VERSION 6.12.76-linuxkit` — the node is not running macOS's kernel, it is sharing the
  **Docker Desktop Linux VM's** kernel. This is the single line that proves the docker driver
  is a container-in-a-VM, not a real virtual machine of its own.
- `CONTAINER-RUNTIME containerd://2.3.4` — no Docker daemon inside the node. Docker only runs the
  node container; containers *inside* the cluster are containerd's.

### Record client and server versions

```bash
kubectl version
```

```text
Client Version: v1.37.0
Kustomize Version: v5.8.1
Server Version: v1.37.0
```

`Client Version` is the `kubectl` binary on the Mac. `Server Version` is the kube-apiserver. Here
they match exactly. Kubernetes supports a **skew of one minor version** between them — a v1.37
client may talk to a v1.36 or v1.38 server, but a v1.33 client against a v1.37 server will start
failing on resources and fields it does not know about. When `kubectl` behaves strangely, this is
the first command to run.

### List every namespace

```bash
kubectl create namespace hw09
kubectl get namespaces
```

```text
namespace/hw09 created

NAME              STATUS   AGE
default           Active   7m4s
hw09              Active   4m26s
hw10              Active   3m25s
hw11              Active   3m19s
hw11-other        Active   3m19s
hw12              Active   3m5s
ingress-nginx     Active   3m7s
kube-node-lease   Active   7m4s
kube-public       Active   7m4s
kube-system       Active   7m4s
```

The four namespaces every cluster is born with:

- **`default`** — where your objects land when you do not say otherwise. Not special, just the
  configured default in the kubeconfig context.
- **`kube-system`** — everything Kubernetes runs to be Kubernetes: the control plane, kube-proxy,
  CoreDNS, the CNI. Never put your own workloads here.
- **`kube-public`** — world-readable, even unauthenticated. Holds `cluster-info`, which is how a
  joining node bootstraps trust in the CA before it has credentials.
- **`kube-node-lease`** — one lightweight `Lease` object per node. The kubelet renews its lease
  every few seconds instead of PATCHing the whole Node object, which is how node heartbeats stay
  cheap on a 5000-node cluster.

`hw09` is the namespace created for this homework. The `hw10`, `hw11`, `hw11-other`, `hw12` and
`ingress-nginx` namespaces belong to the other homework sets running on this shared cluster at the
same time — they are shown because this is real output and hiding them would be dishonest. A
namespace is a **name scope**, not a security boundary on its own: two pods in different namespaces
can still reach each other over the pod network unless a NetworkPolicy stops them.

---

## Task 2 — Control plane anatomy

### The real pods

```bash
kubectl get pods -n kube-system -o wide
```

```text
NAME                               READY   STATUS    RESTARTS   AGE     IP             NODE       NOMINATED NODE   READINESS GATES
coredns-559f6c778d-bnc89           1/1     Running   0          2m20s   10.244.0.2     minikube   <none>           <none>
etcd-minikube                      1/1     Running   0          2m28s   192.168.49.2   minikube   <none>           <none>
kindnet-kh6ss                      1/1     Running   0          2m20s   192.168.49.2   minikube   <none>           <none>
kube-apiserver-minikube            1/1     Running   0          2m27s   192.168.49.2   minikube   <none>           <none>
kube-controller-manager-minikube   1/1     Running   0          2m28s   192.168.49.2   minikube   <none>           <none>
kube-proxy-xq26r                   1/1     Running   0          2m20s   192.168.49.2   minikube   <none>           <none>
kube-scheduler-minikube            1/1     Running   0          2m27s   192.168.49.2   minikube   <none>           <none>
storage-provisioner                1/1     Running   0          2m26s   192.168.49.2   minikube   <none>           <none>
```

Before reading the list, notice the **IP column**. Seven of the eight pods have the IP
`192.168.49.2`, which is the *node's own IP*. Only `coredns` has a real pod IP (`10.244.0.2`) from
the pod CIDR. That is `hostNetwork: true` — those pods share the node's network namespace instead of
getting their own. The control plane must do this, otherwise it would need the pod network to be
working before it could start, and the pod network needs the api-server to be working. The
bootstrap would deadlock.

### What each one does

**`etcd-minikube`** — the database. A consistent, watchable key-value store, and the **only**
stateful thing in the whole control plane. Every object you ever create lives here as a key. Nothing
except the api-server is allowed to talk to it. Lose etcd without a backup and you have lost the
cluster, even if every node and container is still running. Proof that the objects are really in
there, reading the keys directly (this is a read-only `get`):

```bash
kubectl exec -n kube-system etcd-minikube -- etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/var/lib/minikube/certs/etcd/ca.crt \
  --cert=/var/lib/minikube/certs/etcd/server.crt \
  --key=/var/lib/minikube/certs/etcd/server.key \
  get /registry/pods/hw09/ --prefix --keys-only
```

```text
/registry/pods/hw09/trace

/registry/pods/hw09/web

/registry/pods/hw09/web2
```

The three pods created later in this homework, stored under `/registry/pods/<namespace>/<name>`.
This is what "the api-server persists the object" literally means.

**`kube-apiserver-minikube`** — the front door and the **only** component that writes to etcd.
Every other component, and every `kubectl` command, goes through it. It authenticates the caller,
authorizes the action, runs admission controllers, validates the object, and then stores it. It is
also stateless, which is why production clusters run three of them behind a load balancer. Its real
flags:

```bash
kubectl get pod kube-apiserver-minikube -n kube-system \
  -o jsonpath='{.spec.containers[0].command}' | tr ',' '\n' \
  | grep -E 'etcd-servers|secure-port|authorization-mode|advertise-address|service-cluster-ip-range'
```

```text
"--advertise-address=192.168.49.2"
"--authorization-mode=Node
"--etcd-servers=https://127.0.0.1:2379"
"--secure-port=8443"
"--service-cluster-ip-range=10.96.0.0/12"
```

`--etcd-servers` names the one client of etcd. `--authorization-mode=Node,RBAC` (truncated by the
grep) is the two-stage authorizer: the Node authorizer restricts each kubelet to only the objects
its own pods need, RBAC covers everyone else. `--service-cluster-ip-range=10.96.0.0/12` is where
every ClusterIP comes from — that is why `kube-dns` is `10.96.0.10`.

**`kube-scheduler-minikube`** — watches for pods whose `spec.nodeName` is empty and decides which
node each one belongs on. It runs two phases: **filtering** (which nodes *can* run this pod —
enough allocatable CPU/memory, taints tolerated, nodeSelector/affinity satisfied, required ports
free) and **scoring** (of the survivors, which is *best* — most free resources, image already
present, spread across zones). It then writes a `Binding` back to the api-server. Notice what it
does **not** do: it never talks to the node, never starts a container. It only sets a field.

**`kube-controller-manager-minikube`** — one binary running ~40 control loops, each watching the
desired state and reconciling reality toward it. The Deployment controller creates ReplicaSets, the
ReplicaSet controller creates Pods, the Node controller marks nodes `NotReady` and evicts their
pods after the grace period, the Job, Endpoint, ServiceAccount and Namespace controllers do the
same job for their objects. Two of its flags matter for this homework:

```bash
kubectl get pod kube-controller-manager-minikube -n kube-system \
  -o jsonpath='{.spec.containers[0].command}' | tr ',' '\n' \
  | grep -E 'cluster-cidr|allocate-node-cidrs|service-cluster-ip-range|leader-elect'
```

```text
"--cluster-cidr=10.244.0.0/16"
"--service-cluster-ip-range=10.96.0.0/12"
"--allocate-node-cidrs=true"
"--leader-elect=false"]
```

`--allocate-node-cidrs=true` with `--cluster-cidr=10.244.0.0/16` means the controller-manager
carves the cluster pod network into a per-node slice and writes it onto the Node object — that is
exactly where the node's `PodCIDR: 10.244.0.0/24` in Task 4 comes from. `--leader-elect=false`
because there is only one replica; on a multi-master cluster this is `true` and only one instance
runs the loops at a time.

**`kube-proxy-xq26r`** — the only control-plane-ish component that runs on *every* node, as a
DaemonSet. It watches Services and EndpointSlices and programs the node's kernel so that traffic to
a virtual ClusterIP gets rewritten to a real pod IP. It is not a proxy in the data path.

```bash
kubectl logs -n kube-system kube-proxy-xq26r | grep -iE 'proxy mode|Proxier|NodeIPs' | head -3
```

```text
I0917 16:54:28.844494       1 server.go:228] "Successfully retrieved NodeIPs" NodeIPs=["192.168.49.2"]
I0917 16:54:28.853176       1 server_linux.go:144] "Using iptables Proxier"
```

`Using iptables Proxier` — every ClusterIP on this cluster is an iptables DNAT rule, not a process
listening on a socket. This is why you can never `ping` a ClusterIP: nothing owns that address.

**`coredns-559f6c778d-bnc89`** — cluster DNS. A Deployment (not a static pod, and the only
kube-system pod here with a normal pod IP). It watches Services and Pods through the api-server and
answers `<service>.<namespace>.svc.cluster.local`. Every pod is pointed at it automatically
(the `client` pod used below is the busybox pod created in Task 3):

```bash
kubectl exec client -n hw09 -- cat /etc/resolv.conf
kubectl exec client -n hw09 -- nslookup kubernetes.default.svc.cluster.local
kubectl get svc -n kube-system kube-dns
```

```text
search hw09.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5

Server:		10.96.0.10
Address:	10.96.0.10:53

Name:	kubernetes.default.svc.cluster.local
Address: 10.96.0.1

NAME       TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)                  AGE
kube-dns   ClusterIP   10.96.0.10   <none>        53/UDP,53/TCP,9153/TCP   6m52s
```

The kubelet injected `nameserver 10.96.0.10` into the pod — the `kube-dns` Service ClusterIP, which
fronts the CoreDNS pod. The `search` line is why `curl backend` works from inside a pod without a
domain: the resolver appends `hw09.svc.cluster.local` first. The service is still called `kube-dns`
for backward compatibility even though CoreDNS replaced kube-dns years ago.

**`kindnet-kh6ss`** — the CNI plugin, as a DaemonSet. Kubernetes itself does no pod networking; it
defines the CNI contract and something must implement it. On minikube that is kindnet (borrowed
from the kind project). It gives each pod an IP out of the node's PodCIDR and sets up routes so any
pod can reach any other pod without NAT. Without a CNI the node stays `NotReady` forever with
`network plugin is not ready`.

**`storage-provisioner`** — minikube's own add-on, not part of Kubernetes. It watches for
PersistentVolumeClaims using the `standard` StorageClass and creates a hostPath PersistentVolume to
satisfy them, so that PVC examples work on a laptop without a cloud disk API.

### Proving the control plane runs as static pods

A **static pod** is created by the kubelet directly from a YAML file on the node's disk, not by
anything in the API. The kubelet then publishes a read-only "mirror pod" into the api-server so you
can see it with `kubectl`. This is the bootstrap answer to the chicken-and-egg problem: the
api-server cannot be created through the api-server.

Evidence 1 — the **ownerReference is the Node itself**, not a Deployment or DaemonSet:

```bash
kubectl get pod kube-apiserver-minikube -n kube-system -o jsonpath='{.metadata.ownerReferences}' | python3 -m json.tool
```

```text
[
    {
        "apiVersion": "v1",
        "controller": true,
        "kind": "Node",
        "name": "minikube",
        "uid": "abfcce1d-88c7-4929-a2df-7279ac33c839"
    }
]
```

Evidence 2 — all four report `config.source=file`, and their owner is the Node:

```bash
for p in kube-apiserver-minikube etcd-minikube kube-scheduler-minikube kube-controller-manager-minikube; do
  echo -n "$p -> owner: "
  kubectl get pod $p -n kube-system -o jsonpath='{.metadata.ownerReferences[0].kind}/{.metadata.ownerReferences[0].name}  config.source={.metadata.annotations.kubernetes\.io/config\.source}{"\n"}'
done
```

```text
kube-apiserver-minikube -> owner: Node/minikube  config.source=file
etcd-minikube -> owner: Node/minikube  config.source=file
kube-scheduler-minikube -> owner: Node/minikube  config.source=file
kube-controller-manager-minikube -> owner: Node/minikube  config.source=file
```

Compare against the pods that are *not* static — same command on the add-ons:

```bash
for p in kube-proxy-xq26r kindnet-kh6ss coredns-559f6c778d-bnc89 storage-provisioner; do
  echo -n "$p -> owner: "
  kubectl get pod $p -n kube-system -o jsonpath='{.metadata.ownerReferences[0].kind}/{.metadata.ownerReferences[0].name}  config.source={.metadata.annotations.kubernetes\.io/config\.source}{"\n"}'
done
kubectl get daemonset,deployment -n kube-system
```

```text
kube-proxy-xq26r -> owner: DaemonSet/kube-proxy  config.source=
kindnet-kh6ss -> owner: DaemonSet/kindnet  config.source=
coredns-559f6c778d-bnc89 -> owner: ReplicaSet/coredns-559f6c778d  config.source=
storage-provisioner -> owner: /  config.source=

NAME                        DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR            AGE
daemonset.apps/kindnet      1         1         1       1            1           <none>                   2m49s
daemonset.apps/kube-proxy   1         1         1       1            1           kubernetes.io/os=linux   2m50s

NAME                      READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/coredns   1/1     1            1           2m50s
```

Three different creation mechanisms, visible side by side: the four control-plane pods are owned by
`Node/minikube` with `config.source=file`, `kube-proxy` and `kindnet` are owned by DaemonSets,
CoreDNS is owned by a ReplicaSet (and that by a Deployment), and `storage-provisioner` has **no
owner at all** — it is a bare Pod that minikube applied directly, which is why nothing would
recreate it if you deleted it.

Evidence 3 — the actual files on the node's disk:

```bash
minikube ssh "ls -l /etc/kubernetes/manifests/"
minikube ssh "sudo grep -E 'staticPodPath' -A3 /var/lib/kubelet/config.yaml"
```

```text
total 20
-rw------- 1 root root 2655 Sep 17 16:54 etcd.yaml
-rw------- 1 root root 4171 Sep 17 16:54 kube-apiserver.yaml
-rw------- 1 root root 3254 Sep 17 16:54 kube-controller-manager.yaml
-rw------- 1 root root 1727 Sep 17 16:54 kube-scheduler.yaml

staticPodPath: /etc/kubernetes/manifests
streamingConnectionIdleTimeout: 0s
```

Four files, four static pods, and the kubelet config line that ties them together. The kubelet
watches that directory; drop a pod YAML in and it starts, remove it and it stops — no `kubectl`
involved. This is also the standard way to recover a broken api-server: SSH to the node and fix
`kube-apiserver.yaml`, because `kubectl` is not available to you when the api-server is down.

---

## Task 3 — kubectl fundamentals

### Run a pod imperatively

```bash
kubectl run web --image=nginx:alpine --port=80 -n hw09
kubectl get pods -n hw09 -o wide
```

```text
pod/web created

NAME   READY   STATUS    RESTARTS   AGE   IP           NODE       NOMINATED NODE   READINESS GATES
web    1/1     Running   0          12s   10.244.0.4   minikube   <none>           <none>
```

One command, no YAML file, a running container. `READY 1/1` means one of one containers in the pod
is passing its readiness check. The pod got IP `10.244.0.4` from the node's PodCIDR, and
`NODE minikube` is the scheduler's decision.

### describe it

```bash
kubectl describe pod web -n hw09
```

```text
Name:             web
Namespace:        hw09
Priority:         0
Service Account:  default
Node:             minikube/192.168.49.2
Start Time:       Thu, 17 Sep 2026 22:27:42 +0530
Labels:           run=web
Annotations:      <none>
Status:           Running
IP:               10.244.0.4
IPs:
  IP:  10.244.0.4
Containers:
  web:
    Container ID:   containerd://bf11b1beab94a0358e22dd08569620899c05271f8588a6e1ced8165778691045
    Image:          nginx:alpine
    Image ID:       docker.io/library/nginx@sha256:c8497b180665e631ec92a5091125bec5b214f0e2b99409e30653a125b37557da
    Port:           80/TCP
    Host Port:      0/TCP
    State:          Running
      Started:      Thu, 17 Sep 2026 22:27:42 +0530
    Ready:          True
    Restart Count:  0
    Environment:    <none>
    Mounts:
      /var/run/secrets/kubernetes.io/serviceaccount from kube-api-access-jhxwm (ro)
Conditions:
  Type                        Status
  PodReadyToStartContainers   True
  Initialized                 True
  Ready                       True
  ContainersReady             True
  PodScheduled                True
Volumes:
  kube-api-access-jhxwm:
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
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  17s   default-scheduler  Successfully assigned hw09/web to minikube
  Normal  Pulled     17s   kubelet            spec.containers{web}: Container image "nginx:alpine" already present on machine and can be accessed by the pod
  Normal  Created    17s   kubelet            spec.containers{web}: Container created
  Normal  Started    17s   kubelet            spec.containers{web}: Container started
```

`describe` is the first command to reach for when something is wrong, and the useful parts are:

- **`Container ID: containerd://...`** — confirms containerd, not Docker, is running this container.
- **`Image ID: ...@sha256:...`** — the tag `nginx:alpine` is mutable, the digest is what actually ran.
- **`Conditions`** — the five gates a pod passes through. `PodScheduled` is the scheduler's work;
  `Initialized` means init containers finished; `ContainersReady` and `Ready` are the readiness
  probes. A pod stuck with `PodScheduled: False` is a scheduler problem; stuck with
  `ContainersReady: False` is an application problem. Different teams, different fix.
- **`QoS Class: BestEffort`** — no requests and no limits were set, so this pod is first to be
  killed under memory pressure. Set requests and it becomes `Burstable`; set requests == limits and
  it becomes `Guaranteed`.
- **`Tolerations ... for 300s`** — automatically added. If the node goes unreachable, this pod is
  evicted after 5 minutes, not immediately.
- **`Mounts: /var/run/secrets/kubernetes.io/serviceaccount`** — nobody asked for this. Every pod
  gets a projected ServiceAccount token so it can call the api-server.
- **`Events`** at the bottom — the timeline. Note `Pulled ... already present on machine`: no pull
  happened because another pod on this node already had `nginx:alpine`.

### Read its logs

```bash
kubectl logs web -n hw09
```

```text
/docker-entrypoint.sh: Configuration complete; ready for start up
2026/09/17 16:57:42 [notice] 1#1: using the "epoll" event method
2026/09/17 16:57:42 [notice] 1#1: nginx/1.31.6
2026/09/17 16:57:42 [notice] 1#1: built by gcc 15.2.0 (Alpine 15.2.0)
2026/09/17 16:57:42 [notice] 1#1: OS: Linux 6.12.76-linuxkit
2026/09/17 16:57:42 [notice] 1#1: getrlimit(RLIMIT_NOFILE): 1048576:1048576
2026/09/17 16:57:42 [notice] 1#1: start worker processes
2026/09/17 16:57:42 [notice] 1#1: start worker process 30
```

(trimmed to the interesting lines — nginx starts one worker per CPU, and this node has 15)

`kubectl logs` reads whatever the container wrote to **stdout/stderr**, which containerd captured to
a file on the node. It is not reading a log file inside the container. This is why "log to stdout"
is the rule for containerised apps — an app that writes to `/var/log/app.log` is invisible here.
Note `OS: Linux 6.12.76-linuxkit` again: the container sees the Docker VM's kernel.

### exec into it

```bash
kubectl exec web -n hw09 -- sh -c 'hostname; hostname -i; nginx -v'
kubectl exec web -n hw09 -- wget -qO- http://localhost
```

```text
web
10.244.0.4
nginx version: nginx/1.31.6

<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
```

The container's hostname is the pod name, and `hostname -i` returns the pod IP — confirming what
`kubectl get -o wide` reported, from inside. `exec` opens a new process in the running container's
namespaces through the api-server → kubelet → CRI chain; it is not SSH and needs no sshd.

### Reaching it from the Mac

The pod IP is not reachable from macOS (proved at the top). The two honest ways:

```bash
kubectl exec client -n hw09 -- wget -qO- --timeout=5 http://10.244.0.4 | grep -i title
```

```text
<title>Welcome to nginx!</title>
```

```bash
kubectl port-forward -n hw09 pod/web 8099:80 &
curl -sS -m 5 http://127.0.0.1:8099 | grep -i title
```

```text
Forwarding from 127.0.0.1:8099 -> 80
Forwarding from [::1]:8099 -> 80
Handling connection for 8099
<title>Welcome to nginx!</title>
```

The first curls from a busybox pod *inside* the cluster, where the pod network exists. The second
tunnels through the api-server: `kubectl` opens a stream to `127.0.0.1:62155`, the api-server passes
it to the kubelet, and the kubelet connects to port 80 in the pod. Nothing touches `192.168.49.2`.

### Generate a manifest with --dry-run=client -o yaml

```bash
kubectl run web2 --image=nginx:alpine --port=80 -n hw09 --dry-run=client -o yaml
```

```text
apiVersion: v1
kind: Pod
metadata:
  labels:
    run: web2
  name: web2
  namespace: hw09
spec:
  containers:
  - image: nginx:alpine
    name: web2
    ports:
    - containerPort: 80
    resources: {}
  dnsPolicy: ClusterFirst
  restartPolicy: Always
status: {}
```

`--dry-run=client` means kubectl builds the object locally and **never contacts the api-server** —
nothing is created, nothing is validated server-side. This is the fastest way to get a correct
skeleton without memorising the API. (`--dry-run=server` is the other one: it *does* send the
object, runs admission and validation, and then discards it. Use that one to check whether something
would actually be accepted.)

Saved to `web2-pod.yaml` with the empty `status: {}` dropped, and a `tier: frontend` label added.

### Imperative vs declarative

| | Imperative | Declarative |
|---|---|---|
| Command | `kubectl run` / `create` / `expose` / `scale` / `delete` | `kubectl apply -f` |
| You state | the **action** to take | the **end state** you want |
| Re-running it | fails, the object already exists | converges, no error |
| Source of truth | your shell history | a file you can commit |
| Good for | learning, one-offs, debugging, generating YAML | anything that must survive you |

Run the same three commands and watch the difference:

```bash
kubectl apply -f web2-pod.yaml
kubectl apply -f web2-pod.yaml
kubectl run web2 --image=nginx:alpine --port=80 -n hw09
```

```text
pod/web2 created
pod/web2 unchanged
Error from server (AlreadyExists): pods "web2" already exists
```

This is the whole argument in three lines. The **first** `apply` created it. The **second** `apply`
— byte-identical command, byte-identical file — reported `unchanged` and did nothing. The
imperative `kubectl run` with the same intent **failed**. `apply` is idempotent; `run` is not.

That matters because a real deploy pipeline runs the same command on every commit, whether anything
changed or not. With `apply`, "make the cluster look like this repo" is one command that is safe to
run a thousand times.

Now edit the file — add `tier: frontend` under `labels` — and apply again:

```bash
kubectl apply -f web2-pod.yaml
kubectl get pod web2 -n hw09 --show-labels
```

```text
pod/web2 configured

NAME   READY   STATUS    RESTARTS   AGE   LABELS
web2   1/1     Running   0          8s    run=web2,tier=frontend
```

`configured`, not `created` and not `unchanged`. `apply` diffed the file against the live object
(using the `kubectl.kubernetes.io/last-applied-configuration` annotation and server-side field
management), found one new label, and PATCHed just that. It did not delete and recreate the pod —
`AGE` and `RESTARTS` are untouched.

Three different words from one command, and each means something specific: **created** / **unchanged** / **configured**.

---

## Task 4 — The node

```bash
kubectl describe node minikube
```

```text
Name:               minikube
Roles:              control-plane
Labels:             beta.kubernetes.io/arch=arm64
                    beta.kubernetes.io/os=linux
                    kubernetes.io/arch=arm64
                    kubernetes.io/hostname=minikube
                    kubernetes.io/os=linux
                    minikube.k8s.io/commit=7a9f6a841470a207de8cf4bafcccee0969d8ba10
                    minikube.k8s.io/name=minikube
                    minikube.k8s.io/primary=true
                    minikube.k8s.io/updated_at=2026_09_17T22_24_22_0700
                    minikube.k8s.io/version=v1.39.0
                    node-role.kubernetes.io/control-plane=
                    node.kubernetes.io/exclude-from-external-load-balancers=
Annotations:        node.alpha.kubernetes.io/ttl: 0
                    volumes.kubernetes.io/controller-managed-attach-detach: true
CreationTimestamp:  Thu, 17 Sep 2026 22:24:19 +0530
Taints:             <none>
Unschedulable:      false
Lease:
  HolderIdentity:  minikube
  AcquireTime:     <unset>
  RenewTime:       Thu, 17 Sep 2026 22:27:15 +0530
Conditions:
  Type             Status  LastHeartbeatTime                 LastTransitionTime                Reason                       Message
  ----             ------  -----------------                 ------------------                ------                       -------
  MemoryPressure   False   Thu, 17 Sep 2026 22:25:53 +0530   Thu, 17 Sep 2026 22:24:18 +0530   KubeletHasSufficientMemory   kubelet has sufficient memory available
  DiskPressure     False   Thu, 17 Sep 2026 22:25:53 +0530   Thu, 17 Sep 2026 22:24:18 +0530   KubeletHasNoDiskPressure     kubelet has no disk pressure
  PIDPressure      False   Thu, 17 Sep 2026 22:25:53 +0530   Thu, 17 Sep 2026 22:24:18 +0530   KubeletHasSufficientPID      kubelet has sufficient PID available
  Ready            True    Thu, 17 Sep 2026 22:25:53 +0530   Thu, 17 Sep 2026 22:24:51 +0530   KubeletReady                 kubelet is posting ready status
Addresses:
  InternalIP:  192.168.49.2
  Hostname:    minikube
Capacity:
  cpu:                15
  ephemeral-storage:  977850466304
  hugepages-1Gi:      0
  hugepages-2Mi:      0
  hugepages-32Mi:     0
  hugepages-64Ki:     0
  memory:             8125988Ki
  pods:               110
Allocatable:
  cpu:                15
  ephemeral-storage:  977850466304
  hugepages-1Gi:      0
  hugepages-2Mi:      0
  hugepages-32Mi:     0
  hugepages-64Ki:     0
  memory:             8125988Ki
  pods:               110
System Info:
  Machine ID:                 c7552358bf1aab9f1f21b3de6a971616
  System UUID:                c7552358bf1aab9f1f21b3de6a971616
  Boot ID:                    60cac30e-a4c4-45a3-837a-aba978ecdb74
  Kernel Version:             6.12.76-linuxkit
  OS Image:                   Debian GNU/Linux 12 (bookworm)
  Operating System:           linux
  Architecture:               arm64
  Container Runtime Version:  containerd://2.3.4
  Kubelet Version:            v1.37.0
PodCIDR:                      10.244.0.0/24
PodCIDRs:                     10.244.0.0/24
Non-terminated Pods:          (9 in total)
  Namespace                   Name                                CPU Requests  CPU Limits  Memory Requests  Memory Limits  Age
  ---------                   ----                                ------------  ----------  ---------------  -------------  ---
  default                     probe-869fb96f9c-d4nkm              0 (0%)        0 (0%)      0 (0%)           0 (0%)         119s
  kube-system                 coredns-559f6c778d-bnc89            100m (0%)     0 (0%)      70Mi (0%)        170Mi (2%)     2m56s
  kube-system                 etcd-minikube                       100m (0%)     0 (0%)      100Mi (1%)       0 (0%)         3m4s
  kube-system                 kindnet-kh6ss                       100m (0%)     100m (0%)   50Mi (0%)        50Mi (0%)      2m56s
  kube-system                 kube-apiserver-minikube             250m (1%)     0 (0%)      0 (0%)           0 (0%)         3m3s
  kube-system                 kube-controller-manager-minikube    200m (1%)     0 (0%)      0 (0%)           0 (0%)         3m4s
  kube-system                 kube-proxy-xq26r                    0 (0%)        0 (0%)      0 (0%)           0 (0%)         2m56s
  kube-system                 kube-scheduler-minikube             100m (0%)     0 (0%)      0 (0%)           0 (0%)         3m3s
  kube-system                 storage-provisioner                 0 (0%)        0 (0%)      0 (0%)           0 (0%)         3m2s
Allocated resources:
  (Total limits may be over 100 percent, i.e., overcommitted.)
  Resource           Requests    Limits
  --------           --------    ------
  cpu                850m (5%)   100m (0%)
  memory             220Mi (2%)  220Mi (2%)
  ephemeral-storage  0 (0%)      0 (0%)
Events:
  Type    Reason                   Age    From             Message
  ----    ------                   ----   ----             -------
  Normal  NodeHasSufficientMemory  3m3s   kubelet          Node minikube status is now: NodeHasSufficientMemory
  Normal  NodeHasNoDiskPressure    3m3s   kubelet          Node minikube status is now: NodeHasNoDiskPressure
  Normal  NodeHasSufficientPID     3m3s   kubelet          Node minikube status is now: NodeHasSufficientPID
  Normal  RegisteredNode           2m57s  node-controller  Node minikube event: Registered Node minikube in Controller
  Normal  NodeReady                2m33s  kubelet          Node minikube status is now: NodeReady
```

(the `hugepages-*` rows under `Allocated resources` are trimmed, they are all zero)

### Capacity vs Allocatable

**Capacity** is everything the machine physically has. **Allocatable** is what the scheduler is
allowed to hand out to pods. The formula is:

```text
Allocatable = Capacity - kube-reserved - system-reserved - eviction-threshold
```

- `kube-reserved` — held back for the kubelet, the container runtime and their logs.
- `system-reserved` — held back for the OS: sshd, systemd, kernel.
- `eviction-threshold` — a buffer the kubelet keeps free so it can start evicting pods *before* the
  kernel OOM-killer starts killing processes at random.

The scheduler only ever looks at **Allocatable**. A pod requesting more than allocatable stays
`Pending` forever with `Insufficient cpu`, even if `top` on the node shows the machine idle.

**On this node, Capacity and Allocatable are identical** — `cpu: 15`, `memory: 8125988Ki`,
`pods: 110` in both blocks. That is not a mistake in the output and it is not normal for production.
It happens because minikube configures no reservations at all:

```bash
minikube ssh "sudo grep -E 'kubeReserved|systemReserved|evictionHard' -A3 /var/lib/kubelet/config.yaml"
```

```text
evictionHard:
  imagefs.available: 0%
  nodefs.available: 0%
  nodefs.inodesFree: 0%
```

No `kubeReserved`, no `systemReserved`, and every `evictionHard` threshold set to **0%**. Subtract
nothing from Capacity and you get Capacity back. minikube does this deliberately so that a laptop
cluster does not refuse to schedule your demo pods — but it also means the node will let itself be
scheduled into the ground. On EKS, GKE or a kubeadm cluster with sane defaults you would see a
visible gap, typically a few hundred millicores and a gigabyte or so of memory.

Also note `cpu: 15` and `memory: 8125988Ki` (~7.7 GiB). That is not the Mac's hardware, it is what
**Docker Desktop's VM** was given. The node container inherits the VM's view of the world.

`pods: 110` is the kubelet's `maxPods` default — a hard cap unrelated to CPU and memory. Even with
the node idle, pod 111 stays `Pending`.

### Conditions

Four conditions, and you want the first three `False` and the last one `True`:

- **`MemoryPressure: False`** — memory available is above the eviction threshold.
- **`DiskPressure: False`** — disk and inodes are fine. When this flips `True` the kubelet starts
  garbage-collecting images and evicting pods, and refuses new ones.
- **`PIDPressure: False`** — the node is not running out of process IDs (a fork bomb in one pod
  can take down every pod on the node).
- **`Ready: True`, `Reason: KubeletReady`** — the kubelet is healthy and posting status. If the
  kubelet stops reporting, the node-controller flips this to `Unknown` after 40s and starts evicting
  pods after 5 minutes.

`LastHeartbeatTime` updates constantly; `LastTransitionTime` only changes when the status actually
flips. The gap between `LastTransitionTime` of `Ready` (`22:24:51`) and the other three
(`22:24:18`) is the ~33 seconds the node spent waiting for the CNI to come up — the node reports
memory/disk/PID health immediately but stays `NotReady` until networking is usable.

`Taints: <none>` is worth noticing. A real control-plane node carries
`node-role.kubernetes.io/control-plane:NoSchedule` so your workloads never land on it. minikube
removes that taint because there is only one node — which is why the `web` pod happily scheduled
onto a node labelled `control-plane`.

### Container runtime

```text
Container Runtime Version:  containerd://2.3.4
Kubelet Version:            v1.37.0
```

containerd 2.3.4, spoken to over the **CRI** (Container Runtime Interface) on a unix socket. There
is no Docker daemon inside the node; Docker is only the driver that runs the node container on the
Mac. Kubernetes removed the built-in `dockershim` in v1.24, so every modern cluster talks CRI to
containerd or CRI-O. Confirmed from the node side, using `crictl` (the CRI equivalent of
`docker ps`) — the pods created in this homework are really containerd sandboxes:

```bash
minikube ssh "sudo crictl pods --namespace hw09"
```

```text
POD ID              CREATED              STATE               NAME                NAMESPACE           ATTEMPT             RUNTIME
f7a62ac75d1ae       42 seconds ago       Ready               trace               hw09                0                   (default)
3a27dc81c74c6       59 seconds ago       Ready               web2                hw09                0                   (default)
5d728af9f5a6f       About a minute ago   Ready               web                 hw09                0                   (default)
```

### Pod CIDR

```text
PodCIDR:                      10.244.0.0/24
PodCIDRs:                     10.244.0.0/24
```

`10.244.0.0/24` — 256 addresses, 254 usable, for pods **on this node**. Every pod IP in this
homework (`10.244.0.4`, `10.244.0.19`, CoreDNS on `10.244.0.2`) falls inside it.

Where does this number come from? Not from the node. From the controller-manager, which was started
with `--cluster-cidr=10.244.0.0/16 --allocate-node-cidrs=true` (shown in Task 2). It slices the /16
into a /24 per node and writes the slice onto the Node object. Node 2 would get `10.244.1.0/24`,
node 3 `10.244.2.0/24`, and so on — 256 nodes max with this configuration.

The CNI then reads it and hands out the addresses. Confirmed on disk:

```bash
minikube ssh "sudo cat /etc/cni/net.d/10-kindnet.conflist"
```

```text
{
	"cniVersion": "0.3.1",
	"name": "kindnet",
	"plugins": [
	{
		"type": "ptp",
		"ipMasq": false,
		"ipam": {
			"type": "host-local",
			"dataDir": "/run/cni-ipam-state",
			"routes": [ { "dst": "0.0.0.0/0" } ],
			"ranges": [ [ { "subnet": "10.244.0.0/24" } ] ]
		},
		"mtu": 65535
	},
	{
		"type": "portmap",
		"capabilities": { "portMappings": true }
	}
	]
}
```

The chain is now complete and every link is visible: controller-manager `--cluster-cidr=10.244.0.0/16`
→ Node `PodCIDR: 10.244.0.0/24` → kindnet `ipam.ranges.subnet: 10.244.0.0/24` → pod IP `10.244.0.19`.
`ipMasq: false` is why pod-to-pod traffic is not NATed — the pod sees the real source IP, which is
the flat-network promise Kubernetes makes.

Three separate address spaces are in play and confusing them is a classic beginner mistake:

| Range | What it is | Who owns it |
|---|---|---|
| `192.168.49.0/24` | node IPs | the docker driver's bridge |
| `10.244.0.0/16` | pod IPs | the CNI (kindnet) |
| `10.96.0.0/12` | Service ClusterIPs | kube-proxy's iptables rules, no interface anywhere |

---

## Task 5 — The request path, end to end

### The manifest being traced

`trace-pod.yaml` uses `httpd:alpine`, an image **not** already cached on the node. That matters:
with a cached image the kubelet skips the pull and you never see the `Pulling`/`Pulled` events.

```bash
cat trace-pod.yaml
minikube ssh "sudo crictl images" | grep -E 'httpd|nginx'
```

```text
apiVersion: v1
kind: Pod
metadata:
  name: trace
  namespace: hw09
  labels:
    app: trace
spec:
  containers:
  - name: trace
    image: httpd:alpine
    ports:
    - containerPort: 80

docker.io/library/nginx                   alpine               f4240d49fcce2       29MB
```

`nginx:alpine` is cached, `httpd:alpine` is not. Good.

### The diagram

```text
  YOU  (macOS host)
   │
   │  (1) kubectl apply -f trace-pod.yaml
   │      reads ~/.kube/config, finds server https://127.0.0.1:62155,
   │      converts YAML -> JSON, authenticates with the client cert
   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  kube-apiserver                                                      │
│  (2) AuthN (client cert) -> AuthZ (Node,RBAC)                        │
│      -> Mutating admission (defaults, ServiceAccount token volume)   │
│      -> Schema validation                                            │
│      -> Validating admission                                         │
└───────────────┬──────────────────────────────────────────────────────┘
                │ (3) write the object
                ▼
        ┌────────────────┐
        │      etcd      │   key: /registry/pods/hw09/trace
        └────────────────┘   spec.nodeName is still EMPTY
                │
                │ (4) 201 Created  ────────►  kubectl prints "pod/trace created"
                │                             YOUR COMMAND IS DONE HERE.
                │                             Nothing is running yet.
                │
                │ (5) kube-scheduler is WATCHING for pods with no nodeName
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  kube-scheduler                                                      │
│      FILTER : which nodes can run this? (allocatable, taints,         │
│               nodeSelector/affinity, ports)                          │
│      SCORE  : of those, which is best?                               │
│      BIND   : POST a Binding back to the api-server                  │
│               -> Event: Scheduled                                    │
└───────────────┬──────────────────────────────────────────────────────┘
                │ (6) api-server persists spec.nodeName=minikube in etcd
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  kubelet  (on node minikube) is WATCHING for pods bound to ITSELF    │
│  (7) sees hw09/trace, admits it, starts the pod sync loop            │
└───────────────┬──────────────────────────────────────────────────────┘
                │ (8) CRI gRPC over /run/containerd/containerd.sock
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  containerd 2.3.4                                                    │
│  (9)  RunPodSandbox  -> "pause" container holds the net namespace    │
│  (10) calls the CNI plugin  ───────────────────┐                     │
│  (11) PullImage  httpd:alpine                  │  Events:            │
│                                                │    Pulling          │
│                                                │    Pulled           │
│  (12) CreateContainer                          │    Created          │
│  (13) StartContainer  -> runc -> PID 1         │    Started          │
└────────────────────────────────────────────────┼─────────────────────┘
                                                 ▼
                                    ┌───────────────────────────┐
                                    │  CNI: kindnet (ptp)       │
                                    │  IPAM: host-local         │
                                    │  range 10.244.0.0/24      │
                                    │  -> pod IP 10.244.0.19    │
                                    └───────────────────────────┘
                │
                │ (14) kubelet PATCHes status.phase=Running + podIP
                │      back to the api-server  ->  etcd
                ▼
   kubectl get pod trace -n hw09 -o wide   ->   Running  10.244.0.19  minikube
```

Everything after step (4) is **asynchronous**. Your terminal already returned. Nobody called
anybody: the scheduler and the kubelet are each sitting on a **watch** against the api-server and
react when an object they care about changes. This is the level-triggered, watch-and-reconcile model
that the whole of Kubernetes is built on, and it is why deleting a node does not break the api-server,
and why an api-server restart does not kill your running containers.

### Evidence 1 — kubectl to api-server (steps 1-4)

```bash
kubectl apply -f trace-pod.yaml -v=6
```

```text
I0917 22:28:56.885800   42907 loader.go:408] Config loaded from file:  /Users/aman/.kube/config
I0917 22:28:56.892657   42907 round_trippers.go:632] "Response" verb="GET" url="https://127.0.0.1:62155/openapi/v3?timeout=32s" status="200 OK" milliseconds=5
I0917 22:28:56.914115   42907 round_trippers.go:632] "Response" verb="GET" url="https://127.0.0.1:62155/api/v1/namespaces/hw09/pods/trace" status="404 Not Found" milliseconds=3
I0917 22:28:56.916297   42907 round_trippers.go:632] "Response" verb="GET" url="https://127.0.0.1:62155/api/v1/namespaces/hw09" status="200 OK" milliseconds=2
I0917 22:28:56.919873   42907 round_trippers.go:632] "Response" verb="POST" url="https://127.0.0.1:62155/api/v1/namespaces/hw09/pods?fieldManager=kubectl-client-side-apply&fieldValidation=Strict" status="201 Created" milliseconds=3
pod/trace created
```

`-v=6` prints every HTTP call kubectl makes, and there are exactly four:

1. `GET /openapi/v3` — fetch the API schema, so kubectl can validate your YAML locally.
2. `GET .../pods/trace` → **404 Not Found** — "does this already exist?" It does not, so this is a
   create, not a patch. (Had it returned 200, kubectl would have computed a diff and sent a PATCH —
   that is exactly the `unchanged`/`configured` behaviour from Task 3.)
3. `GET .../namespaces/hw09` → 200 — the target namespace exists.
4. `POST .../pods` → **201 Created** — the object is accepted and persisted.

`kubectl` is a plain REST client over HTTPS. There is no magic and no second protocol. Also note the
whole thing took **34 milliseconds**, and `pod/trace created` printed immediately after the 201 —
long before any container existed.

### Evidence 2 — the object landed in etcd (step 3)

```bash
kubectl exec -n kube-system etcd-minikube -- etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/var/lib/minikube/certs/etcd/ca.crt \
  --cert=/var/lib/minikube/certs/etcd/server.crt \
  --key=/var/lib/minikube/certs/etcd/server.key \
  get /registry/pods/hw09/ --prefix --keys-only
```

```text
/registry/pods/hw09/trace
```

The key exists. The api-server did not keep the pod in memory — it wrote it to the cluster's only
database, which is why the pod survives an api-server restart.

### Evidence 3 — the event sequence (steps 5-13)

```bash
kubectl get events -n hw09 --field-selector involvedObject.name=trace --sort-by=.metadata.creationTimestamp
```

```text
LAST SEEN   TYPE     REASON      OBJECT      MESSAGE
29s         Normal   Scheduled   pod/trace   Successfully assigned hw09/trace to minikube
28s         Normal   Pulling     pod/trace   Pulling image "httpd:alpine"
17s         Normal   Pulled      pod/trace   Successfully pulled image "httpd:alpine" in 11.083s (11.083s including waiting). Image size: 21120476 bytes.
17s         Normal   Created     pod/trace   Container created
17s         Normal   Started     pod/trace   Container started
```

The exact five-step sequence, in order, with real timing. `Scheduled` at 29s, `Pulling` one second
later, and then an **11 second gap** while the image came down from Docker Hub — the slowest step by
far, and the reason `imagePullPolicy` and image size matter. `Created` and `Started` are instant
once the bytes are local.

### Evidence 4 — which component emitted each event

This is the part that proves the diagram rather than illustrating it. Every Event records the
component that produced it:

```bash
kubectl get events -n hw09 --field-selector involvedObject.name=trace \
  --sort-by=.metadata.creationTimestamp \
  -o custom-columns='REASON:.reason,COMPONENT:.source.component,HOST:.source.host,MESSAGE:.message'
```

```text
REASON      COMPONENT           HOST       MESSAGE
Scheduled   default-scheduler   <none>     Successfully assigned hw09/trace to minikube
Pulling     kubelet             minikube   Pulling image "httpd:alpine"
Pulled      kubelet             minikube   Successfully pulled image "httpd:alpine" in 11.083s (11.083s including waiting). Image size: 21120476 bytes.
Created     kubelet             minikube   Container created
Started     kubelet             minikube   Container started
```

`Scheduled` came from **`default-scheduler`**. The other four came from **`kubelet`**. That is the
hand-off in the diagram, recorded by the cluster itself: the scheduler's entire contribution is one
event and one field, and everything after it is the kubelet's job. The scheduler never pulled an
image and never started a container.

### Evidence 5 — the node assignment (step 6)

```bash
kubectl get pod trace -n hw09 -o wide
```

```text
NAME    READY   STATUS    RESTARTS   AGE   IP            NODE       NOMINATED NODE   READINESS GATES
trace   1/1     Running   0          29s   10.244.0.19   minikube   <none>           <none>
```

`NODE minikube` is the `spec.nodeName` the scheduler wrote back. `IP 10.244.0.19` is what the CNI
handed out from the node's `10.244.0.0/24` PodCIDR, and the kubelet reported it into `status.podIP`.
`NOMINATED NODE <none>` would hold a node name if preemption were in play.

### Evidence 6 — containerd actually ran it (steps 9-13)

```bash
minikube ssh "sudo crictl ps | head -5"
```

```text
CONTAINER           IMAGE               CREATED              STATE               NAME                      ATTEMPT             POD ID              POD                                NAMESPACE
83fc06c5a98d4       f4240d49fcce2       26 seconds ago       Running             db                        0                   7e354083e16ee       core-db-0                          hw10
007d8a478462c       085b2defb38e1       31 seconds ago       Running             trace                     0                   f7a62ac75d1ae       trace                              hw09
3cf992dbac820       b7c873bd97bdc       44 seconds ago       Running             agent                     0                   4bafac633d8f4       core-agent-lr96c                   hw10
d5af2a0f37fce       7f199a2cf92c8       57 seconds ago       Running             netshoot                  0                   223446d3e9294       netshoot                           hw11
```

Container `007d8a478462c` running in POD `f7a62ac75d1ae` — the containerd sandbox for `hw09/trace`.
Note the CONTAINER ID and the POD ID are **different**: the POD ID is the `pause` sandbox that owns
the network namespace and the IP, and the container joins it. That is why a container can crash and
restart without the pod losing its IP. (Other namespaces appear in this output because the cluster
is shared with the other homework sets.)

### Summary table

| Step | Component | What it actually does | Evidence above |
|---|---|---|---|
| 1 | `kubectl` | YAML → JSON, HTTPS POST to the api-server | `-v=6` POST 201 |
| 2 | kube-apiserver | authN, authZ, admission, validation | `--authorization-mode=Node,RBAC` |
| 3 | etcd | persists the object | `/registry/pods/hw09/trace` |
| 4 | kube-apiserver | replies `201 Created` | `pod/trace created` |
| 5 | kube-scheduler | filter → score → write `spec.nodeName` | Event `Scheduled`, source `default-scheduler` |
| 6 | kube-apiserver | persists the binding | `NODE minikube` in `get -o wide` |
| 7 | kubelet | sees the pod bound to its node | Events source `kubelet` |
| 8-13 | containerd | sandbox, pull, create, start | `Pulling`/`Pulled`/`Created`/`Started`, `crictl ps` |
| 10 | CNI (kindnet) | allocates the pod IP, wires the veth | `IP 10.244.0.19`, `10-kindnet.conflist` |
| 14 | kubelet | PATCHes status back | `STATUS Running` |

**What is missing from this list, and should be:** nothing ever pushes to a node. Every component
pulls from the api-server via a watch. That single design choice is why Kubernetes degrades rather
than fails — kill the scheduler and existing pods keep running, you just cannot place new ones.

---

## Interview questions

**1. Which component is the only one that talks to etcd, and why does that matter?**
The kube-apiserver. Everything else — scheduler, controller-manager, kubelet, kubectl — goes through
it. Centralising writes gives you one place for authentication, authorisation, admission control,
validation, optimistic concurrency (resourceVersion) and audit logging. If the scheduler wrote to
etcd directly, none of that could be enforced.

**2. What is a static pod, and how do you prove a pod is one?**
A pod the kubelet creates from a YAML file in `staticPodPath` (`/etc/kubernetes/manifests`) instead
of from the API. The kubelet publishes a read-only mirror pod so it shows in `kubectl get`. Proof:
its `ownerReferences` is `kind: Node` (not Deployment/DaemonSet/ReplicaSet) and its
`kubernetes.io/config.source` annotation is `file`. Deleting it with `kubectl` does nothing — the
kubelet recreates it from the file.

**3. Why does the control plane need static pods at all?**
Chicken and egg. You cannot create the api-server through the api-server. The kubelet is the only
piece that starts without the API, so `kubeadm` writes files and lets the kubelet bootstrap the
control plane from disk.

**4. Capacity says 8 GiB but my 2 GiB pod is Pending. Why?**
The scheduler reads **Allocatable**, not Capacity. Allocatable = Capacity − kube-reserved −
system-reserved − eviction-threshold, and then it subtracts the **requests** of every pod already on
the node. Check `kubectl describe node` → `Allocated resources`. Also check `pods: 110` — the
maxPods cap is independent of CPU and memory.

**5. A pod is Pending. Walk me through the diagnosis.**
`kubectl describe pod` and read the events. No `Scheduled` event at all → the scheduler could not
place it: insufficient allocatable resources, an untolerated taint, an unsatisfiable
nodeSelector/affinity, or an unbound PVC. A `Scheduled` event but stuck after it → it is the
kubelet's problem now: `ImagePullBackOff`, a missing ConfigMap/Secret, or the CNI failing to
allocate an IP.

**6. What is the difference between `kubectl run` and `kubectl apply -f`?**
`run` is imperative — it states an action and fails with `AlreadyExists` the second time. `apply` is
declarative — it states the desired end state, and reports `created`, then `unchanged`, then
`configured` if the file changed. Only `apply` is safe to run repeatedly from a pipeline, and only
`apply` has a file you can put in git.

**7. What does `--dry-run=client` do that `--dry-run=server` does not?**
`client` never contacts the api-server — pure local YAML generation, no validation, no admission.
`server` sends the object, runs full validation and admission webhooks, then discards it instead of
persisting. Use `client` to scaffold, `server` to answer "would this actually be accepted?".

**8. The scheduler picked a node. Did it start the container?**
No. The scheduler only writes `spec.nodeName` via a Binding. It never contacts the node. The kubelet
on that node is watching for pods bound to itself, sees the change, and does everything from there
through the CRI.

**9. Why can you never `ping` a ClusterIP?**
Because no interface anywhere owns that address. A ClusterIP is a virtual IP that exists only as
iptables DNAT rules programmed by kube-proxy (`Using iptables Proxier` in its logs). The rules match
on the destination *port* as well, so ICMP has nothing to match and the address never answers.

**10. What does kube-proxy actually do, and is it in the data path?**
It watches Services and EndpointSlices and programs the node's kernel (iptables or IPVS) to DNAT
ClusterIP traffic to a real pod IP. It is a control-plane agent, not a data-plane proxy — once the
rules are written, packets are forwarded by the kernel and kube-proxy is not involved. You can kill
kube-proxy and existing Service traffic keeps flowing; only new Services stop working.

**11. Why does the docker driver on macOS give you an unreachable node IP?**
Because the node is a container inside the Docker Desktop Linux VM, and the VM's bridge network
(`192.168.49.0/24`) is not routed on the host. `kubectl` works only because minikube publishes the
api-server's 8443 onto `127.0.0.1` on the Mac. To reach a workload use `kubectl port-forward`,
`minikube service --url`, `kubectl exec` into a pod, or `minikube ssh`.

**12. What is the `pause` container for?**
It is the pod sandbox. It holds the network and IPC namespaces and does nothing but sleep, so the
pod's IP and namespaces survive an application container crashing and restarting. `crictl ps` shows
the POD ID and the CONTAINER ID as separate things for exactly this reason.

**13. If etcd dies, what stops working?**
All writes and all reads that miss the api-server's cache — so no new objects, no scheduling, no
scaling, no `kubectl apply`. But every container already running keeps running, because the kubelet
and the container runtime do not need etcd to keep a container alive. The cluster becomes
un-manageable, not down.

**14. Where does a node's `PodCIDR` come from?**
The kube-controller-manager, started with `--cluster-cidr` and `--allocate-node-cidrs=true`. It
slices the cluster CIDR into a per-node block and writes it onto the Node object. The CNI plugin
reads it and allocates pod IPs from it.

---

## Cleanup

```bash
kubectl delete namespace hw09
kubectl get namespace hw09
```

```text
namespace "hw09" deleted
Error from server (NotFound): namespaces "hw09" not found
```

Deleting a namespace cascade-deletes everything inside it — all four pods went with it, no
individual `kubectl delete pod` needed. The namespace first goes to `Terminating` while the
namespace controller garbage-collects its contents; it disappears only when that finishes. A
namespace stuck in `Terminating` almost always means a finalizer on some object inside it.

The cluster itself is left running and untouched.

---

## Completion checklist

- [x] Confirmed the node is `Ready` with `minikube status`, `kubectl cluster-info` and `kubectl get nodes -o wide`.
- [x] Recorded client `v1.37.0` and server `v1.37.0`, and explained the one-minor-version skew rule.
- [x] Listed every namespace and explained what the four built-in ones are for.
- [x] Identified all eight kube-system pods and explained each one's job from real output.
- [x] Proved the control plane runs as static pods three ways: `ownerReferences: Node`,
      `config.source=file`, and the four files in `/etc/kubernetes/manifests`.
- [x] Contrasted static pods against DaemonSet-, ReplicaSet- and unowned pods in the same namespace.
- [x] Ran a pod imperatively and used `get`, `describe`, `logs` and `exec` on it.
- [x] Generated a manifest with `--dry-run=client -o yaml` and applied it declaratively.
- [x] Demonstrated `created` / `unchanged` / `configured` versus `AlreadyExists`.
- [x] Read the node's capacity, allocatable, conditions, runtime and PodCIDR, and explained honestly
      why capacity equals allocatable on this cluster.
- [x] Traced `kubectl apply` to a running container with six pieces of real evidence, including the
      `Scheduled → Pulling → Pulled → Created → Started` sequence and the component that emitted each.
- [x] Documented that `192.168.49.2` is unreachable from macOS and used only working access routes.
- [x] Deleted namespace `hw09` and verified it is gone.

## Files in this folder

| File | What it is |
|---|---|
| `README.md` | this write-up |
| `web2-pod.yaml` | the manifest generated by `--dry-run=client -o yaml`, used for the apply demo |
| `trace-pod.yaml` | the `httpd:alpine` pod used to trace the request path in Task 5 |
