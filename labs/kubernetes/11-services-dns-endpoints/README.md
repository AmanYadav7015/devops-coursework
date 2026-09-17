# Homework Set 11 — Services, DNS & Endpoints

> **Provenance:** the course's official homework document covers sessions 2–8 only and contains
> nothing for the Kubernetes sessions. The seven tasks below were derived from the material actually
> taught in `session-11-kubernetes-services` (`service.md`, `fqdn.md`, folders `01-clusterip`
> through `05-headless`, and `troubleshooting/empty-endpoints.yaml`) and are written in the same
> style as the official homework.

Every command in this README was run against a live cluster and every `text` block is real,
unedited output. Nothing is invented.

---

## Environment

| Item | Value |
| :--- | :--- |
| Cluster | minikube v1.39.0, `docker` driver |
| Kubernetes | client **v1.37.0**, server **v1.37.0** |
| Container runtime | containerd 2.3.4 |
| Node | `minikube`, internal IP `192.168.49.2`, Debian 12, kernel 6.12.76-linuxkit (arm64) |
| Host | macOS (Apple silicon), Docker Desktop |
| Namespaces used | `hw11` and `hw11-other` |
| NodePorts used | `30110` (NodePort svc), `30111` (LoadBalancer svc) |

```bash
kubectl get nodes -o wide
```

```text
NAME       STATUS   ROLES           AGE     VERSION   INTERNAL-IP    EXTERNAL-IP   OS-IMAGE                         KERNEL-VERSION             CONTAINER-RUNTIME
minikube   Ready    control-plane   3m13s   v1.37.0   192.168.49.2   <none>        Debian GNU/Linux 12 (bookworm)   6.12.76-linuxkit (arm64)   containerd://2.3.4
```

Single-node cluster, so every pod IP comes out of `10.244.0.0/24` and every Service IP out of the
`10.96.0.0/12` service CIDR. That makes the difference between the two address ranges very easy to
see in the output below: `10.244.x.x` is always a real pod, `10.96.x.x` / `10.9x.x.x` is always a
virtual Service IP that belongs to no network card anywhere.

---

## Files in this folder

```text
11-services-dns-endpoints/
├── README.md
└── manifests/
    ├── 00-namespaces.yaml            hw11 and hw11-other
    ├── 01-backend.yaml               ConfigMap + backend Deployment (2 replicas, nginx:alpine)
    ├── 02-clusterip-service.yaml     Task 1 — ClusterIP
    ├── 03-client-pod.yaml            netshoot client (curl + dig + nslookup + tcpdump)
    ├── 04-nodeport-service.yaml      Task 2 — NodePort on 30110
    ├── 05-loadbalancer-service.yaml  Task 3 — LoadBalancer, nodePort pinned to 30111
    ├── 06-externalname-service.yaml  Task 4 — two ExternalName services
    ├── 07-headless.yaml              Task 5 — headless svc + ClusterIP svc + StatefulSet
    ├── 08-other-namespace.yaml       Task 6 — payments svc in hw11-other
    ├── 09-broken-service.yaml        Task 7 — the broken service (selector mismatch)
    └── 10-fixed-service.yaml         Task 7 — the fix
```

The backend is `nginx:alpine` with a one-line config that returns its own pod name, so every curl
tells you **which pod answered**. That single trick is what makes load balancing, headless DNS and
the endpoints drill all visible without any extra tooling:

```text
server {
  listen 80;
  location / {
    default_type text/plain;
    return 200 "hello from backend pod $hostname\n";
  }
  location /healthz {
    default_type text/plain;
    return 200 "ok\n";
  }
}
```

### Setup

```bash
kubectl apply -f manifests/00-namespaces.yaml
kubectl apply -f manifests/01-backend.yaml
kubectl apply -f manifests/03-client-pod.yaml
kubectl wait --for=condition=Ready pod -l app=backend -n hw11 --timeout=180s
kubectl wait --for=condition=Ready pod/netshoot -n hw11 --timeout=300s
kubectl get pods -n hw11 -o wide
```

```text
namespace/hw11 created
namespace/hw11-other created
configmap/backend-nginx-conf created
deployment.apps/backend created
pod/netshoot created
pod/backend-77bd96dd69-4g585 condition met
pod/backend-77bd96dd69-xf5jd condition met
pod/netshoot condition met
NAME                       READY   STATUS    RESTARTS   AGE   IP           NODE       NOMINATED NODE   READINESS GATES
backend-77bd96dd69-4g585   1/1     Running   0          38s   10.244.0.6   minikube   <none>           <none>
backend-77bd96dd69-xf5jd   1/1     Running   0          38s   10.244.0.5   minikube   <none>           <none>
netshoot                   1/1     Running   0          38s   10.244.0.7   minikube   <none>           <none>
```

Two backend pods on `10.244.0.5` and `10.244.0.6`, and a `nicolaka/netshoot` client on
`10.244.0.7`. Netshoot is used instead of `curlimages/curl` because this homework needs `dig`
(to see CNAME records), `nslookup` and `tcpdump` (to prove `ndots:5`) in the same container.

---

## Task 1 — ClusterIP: reach a backend by service name

### The manifest

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-clusterip
  namespace: hw11
  labels:
    app: backend
spec:
  type: ClusterIP
  selector:
    app: backend
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 80
```

### Apply and inspect

```bash
kubectl apply -f manifests/02-clusterip-service.yaml
kubectl get svc backend-clusterip -n hw11 -o wide
kubectl describe svc backend-clusterip -n hw11
```

```text
service/backend-clusterip created
NAME                TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE   SELECTOR
backend-clusterip   ClusterIP   10.102.20.51   <none>        80/TCP    46s   app=backend

Name:                     backend-clusterip
Namespace:                hw11
Labels:                   app=backend
Annotations:              <none>
Selector:                 app=backend
Type:                     ClusterIP
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       10.102.20.51
IPs:                      10.102.20.51
Port:                     http  80/TCP
TargetPort:               80/TCP
Endpoints:                10.244.0.5:80,10.244.0.6:80
Session Affinity:         None
Internal Traffic Policy:  Cluster
Events:                   <none>
```

`EXTERNAL-IP` is `<none>` — that is the whole point of ClusterIP. The `Endpoints` line is the
important one: the endpoint controller watched the selector `app=backend`, found the two ready
pods, and wrote their IPs in. `10.102.20.51` is a virtual IP: no interface on any machine owns it,
it only exists as iptables DNAT rules.

### Prove pod-to-pod access by service name

```bash
kubectl exec -n hw11 netshoot -- curl -s http://backend-clusterip
kubectl exec -n hw11 netshoot -- curl -s http://backend-clusterip.hw11.svc.cluster.local
```

```text
hello from backend pod backend-77bd96dd69-4g585
hello from backend pod backend-77bd96dd69-xf5jd
```

No IP address was typed anywhere. The client pod said `backend-clusterip`, CoreDNS turned that into
`10.102.20.51`, and kube-proxy turned that into a real pod IP.

### Prove it load balances

```bash
kubectl exec -n hw11 netshoot -- sh -c 'for i in $(seq 1 8); do curl -s http://backend-clusterip; done'
```

```text
hello from backend pod backend-77bd96dd69-4g585
hello from backend pod backend-77bd96dd69-4g585
hello from backend pod backend-77bd96dd69-xf5jd
hello from backend pod backend-77bd96dd69-xf5jd
hello from backend pod backend-77bd96dd69-xf5jd
hello from backend pod backend-77bd96dd69-4g585
hello from backend pod backend-77bd96dd69-4g585
hello from backend pod backend-77bd96dd69-xf5jd
```

Both pod names appear, and not in a neat alternating pattern. That is exactly what iptables mode
does — it is **random** per connection, not round-robin. Interviewers like this detail: the default
`kube-proxy` iptables backend uses the `statistic random probability` module, so with 2 backends
each new connection has a coin-flip. Perfectly even distribution is not promised.

### The DNS record behind it

```bash
kubectl exec -n hw11 netshoot -- nslookup backend-clusterip
```

```text
;; Got recursion not available from 10.96.0.10
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	backend-clusterip.hw11.svc.cluster.local
Address: 10.102.20.51
;; Got recursion not available from 10.96.0.10
```

One name, **one A record**, pointing at the single virtual IP. Remember this — Task 5 contrasts it
directly with a headless service.

### Endpoints and EndpointSlices

```bash
kubectl get endpoints backend-clusterip -n hw11
kubectl get endpointslices -n hw11
```

```text
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME                ENDPOINTS                     AGE
backend-clusterip   10.244.0.5:80,10.244.0.6:80   46s
NAME                      ADDRESSTYPE   PORTS   ENDPOINTS               AGE
backend-clusterip-bw84n   IPv4          80      10.244.0.5,10.244.0.6   46s
```

`kubectl` itself prints the deprecation warning. More on that in Task 7.

---

## Task 2 — NodePort: the four-port chain, and an honest look at minikube on macOS

### The manifest

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-nodeport
  namespace: hw11
  labels:
    app: backend
spec:
  type: NodePort
  selector:
    app: backend
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 80
      nodePort: 30110
```

```bash
kubectl apply -f manifests/04-nodeport-service.yaml
kubectl get svc backend-nodeport -n hw11 -o wide
```

```text
service/backend-nodeport created
NAME               TYPE       CLUSTER-IP    EXTERNAL-IP   PORT(S)        AGE   SELECTOR
backend-nodeport   NodePort   10.97.124.9   <none>        80:30110/TCP   1s    app=backend
```

Note `PORT(S)` reads `80:30110/TCP` — a NodePort service **still has a ClusterIP**. It is a
ClusterIP service with an extra door bolted onto every node.

### The nodePort / port / targetPort / containerPort chain

```text
  Client outside the cluster
          │
          │  http://<any-node-ip>:30110
          ▼
  ┌───────────────────────────────────────────────────────────┐
  │  NODE  minikube  (192.168.49.2)                           │
  │                                                           │
  │   [ nodePort: 30110 ]   ← Service.spec.ports[].nodePort   │
  │          │                 range 30000-32767              │
  │          │  iptables DNAT (kube-proxy)                    │
  │          ▼                                                │
  │   [ port: 80 ]          ← Service.spec.ports[].port       │
  │     on ClusterIP          the cluster-internal front door │
  │     10.97.124.9           other pods dial THIS            │
  │          │                                                │
  │          │  iptables DNAT to a random ready endpoint      │
  │          ▼                                                │
  │   [ targetPort: 80 ]    ← Service.spec.ports[].targetPort │
  │          │                 the port ON THE POD            │
  │          ▼                                                │
  │   ┌──────────────────────┐   ┌──────────────────────┐     │
  │   │ pod 10.244.0.5       │   │ pod 10.244.0.6       │     │
  │   │ containerPort: 80    │   │ containerPort: 80    │     │
  │   │  ← purely metadata   │   │                      │     │
  │   └──────────────────────┘   └──────────────────────┘     │
  └───────────────────────────────────────────────────────────┘
```

| Port | Lives in | Who dials it | Value here | Mandatory? |
| :--- | :--- | :--- | :--- | :--- |
| `nodePort` | `Service.spec.ports[].nodePort` | clients outside the cluster, hitting a node IP | `30110` | no — omit and Kubernetes picks a free one from 30000–32767 |
| `port` | `Service.spec.ports[].port` | other pods, via the ClusterIP or the DNS name | `80` | **yes** |
| `targetPort` | `Service.spec.ports[].targetPort` | the Service, forwarding to a pod | `80` | no — defaults to the same value as `port` |
| `containerPort` | `Pod.spec.containers[].ports[].containerPort` | **nobody** | `80` | no — it is documentation |

The one that surprises people: **`containerPort` does nothing.** It does not open, publish or
firewall anything. If you delete it from the Deployment the service keeps working, because
`targetPort` addresses the pod's network namespace directly. It exists so humans and tools can read
the manifest and see what the app listens on, and so `targetPort` can refer to it *by name*
(`targetPort: http`) instead of by number.

`targetPort` is the one that actually has to be right. If `targetPort` does not match the port the
process inside the container is bound to, you get exactly the symptom from Task 7 — a healthy
service with connection refused — except the endpoints will be populated, which is how you tell the
two failures apart.

### Reaching it from outside — the honest macOS result first

The instinctive move is to curl the node IP. On minikube with the `docker` driver on macOS, it
does not work, and it is worth showing why rather than hiding it:

```bash
minikube ip
ping -c 3 -t 5 192.168.49.2
curl -sS --max-time 5 http://192.168.49.2:30110
```

```text
192.168.49.2

PING 192.168.49.2 (192.168.49.2): 56 data bytes
Request timeout for icmp_seq 0
Request timeout for icmp_seq 1

--- 192.168.49.2 ping statistics ---
3 packets transmitted, 0 packets received, 100.0% packet loss

curl: (28) Connection timed out after 5009 milliseconds
```

100% packet loss, and curl times out. **This is not a broken cluster and not a broken service.**
`192.168.49.2` is an address on a Docker bridge network that lives *inside the Docker Desktop Linux
VM*. On Linux, Docker bridges are attached to the host's own network stack and this curl would
succeed. On macOS, Docker Desktop runs the whole Docker engine inside a hypervisor VM, and macOS
has no route into that VM's bridge networks. The packet never leaves the Mac.

Understanding that distinction is the real lesson: a NodePort is genuinely open on the node; your
laptop just is not on the node's network.

### Method 1 — curl the nodePort from inside the node (the most faithful demonstration)

```bash
minikube ssh -- "curl -s http://192.168.49.2:30110"
minikube ssh -- "curl -s http://127.0.0.1:30110"
```

```text
hello from backend pod backend-77bd96dd69-4g585
hello from backend pod backend-77bd96dd69-xf5jd
```

There it is. From a shell **on the node**, port 30110 answers on both the node's real IP and on
loopback, and it load balances across both pods. The NodePort was working the entire time.

### What is actually listening on 30110?

```bash
minikube ssh -- "sudo netstat -lntp 2>/dev/null | grep 30110 || sudo ss -lntp 2>/dev/null | grep 30110 || echo 'no listening socket; iptables mode does not open a socket per service'"
minikube ssh -- "sudo iptables -t nat -L KUBE-NODEPORTS -n 2>/dev/null | head -20"
```

```text
no listening socket; iptables mode does not open a socket per service

Chain KUBE-NODEPORTS (1 references)
target     prot opt source               destination
KUBE-EXT-7YLIHDKLMNGEWDMX  6    --  0.0.0.0/0            127.0.0.0/8          /* hw11/backend-nodeport:http */ tcp dpt:30110 nfacct-name  localhost_nps_accepted_pkts
KUBE-EXT-7YLIHDKLMNGEWDMX  6    --  0.0.0.0/0            0.0.0.0/0            /* hw11/backend-nodeport:http */ tcp dpt:30110
```

This is the best thing in the whole task. **There is no process listening on port 30110.**
The old `userspace` kube-proxy mode did open a real socket per service; modern `iptables` mode does
not. Instead kube-proxy writes netfilter rules — you can see the two rules it added to the
`KUBE-NODEPORTS` chain, complete with a comment naming the service `hw11/backend-nodeport:http`.
Packets arriving for `tcp dpt:30110` get DNAT'd in the kernel before anything in userspace sees
them. That is why NodePort costs essentially nothing per service and why `netstat` looks empty.

### Method 2 — `minikube service --url` (works from macOS)

```bash
minikube service backend-nodeport -n hw11 --url
curl -sS http://127.0.0.1:62786
curl -sS http://127.0.0.1:62786
curl -sS http://127.0.0.1:62786
```

```text
http://127.0.0.1:62786
! Because you are using a Docker driver on darwin, the terminal needs to be open to run it.

hello from backend pod backend-77bd96dd69-xf5jd
hello from backend pod backend-77bd96dd69-4g585
hello from backend pod backend-77bd96dd69-4g585
```

minikube itself tells you what is going on: on the Docker driver on darwin it has to hold a tunnel
open. It picks a random high port on `127.0.0.1` (62786 here, it differs every run) and forwards it
into the node. The terminal must stay open — close it and the URL dies.

### Method 3 — `kubectl port-forward`

```bash
kubectl port-forward -n hw11 svc/backend-nodeport 8111:80
curl -sS http://127.0.0.1:8111
```

```text
Forwarding from 127.0.0.1:8111 -> 80
Forwarding from [::1]:8111 -> 80

hello from backend pod backend-77bd96dd69-4g585
```

Worth being precise about what this proves: `port-forward` tunnels over the **Kubernetes API
server** straight to a pod. It does **not** use the nodePort at all — notice it maps to `80`, the
service `port`, not `30110`. It is the right tool for debugging any service including a plain
ClusterIP, but it is not a demonstration that NodePort works. Method 1 is.

### Summary of the three methods

| Method | Works from macOS? | Actually exercises the nodePort? | Needs a terminal held open? |
| :--- | :--- | :--- | :--- |
| `curl 192.168.49.2:30110` | **no** (docker driver on macOS) | yes, if you could reach it | no |
| `minikube ssh -- curl ...:30110` | yes (runs on the node) | **yes** | no |
| `minikube service --url` | yes | yes, via a tunnel to the nodePort | yes |
| `kubectl port-forward` | yes | **no** — API-server tunnel to the pod | yes |

---

## Task 3 — LoadBalancer: what really happens without a cloud provider

### The manifest

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-loadbalancer
  namespace: hw11
  labels:
    app: backend
spec:
  type: LoadBalancer
  selector:
    app: backend
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 80
      nodePort: 30111
```

`nodePort` is pinned to 30111 on purpose. A LoadBalancer service *always* allocates a nodePort
underneath; leaving it to chance would have grabbed a random port from the whole 30000–32767 range,
and this cluster is shared.

### Apply it and look at the truth

```bash
kubectl apply -f manifests/05-loadbalancer-service.yaml
kubectl get svc backend-loadbalancer -n hw11 -o wide
kubectl get svc backend-loadbalancer -n hw11 -o jsonpath='{.status.loadBalancer}'
```

```text
service/backend-loadbalancer created
NAME                   TYPE           CLUSTER-IP       EXTERNAL-IP   PORT(S)        AGE   SELECTOR
backend-loadbalancer   LoadBalancer   10.108.109.237   <pending>     80:30111/TCP   9s    app=backend
{}
```

Four minutes later, nothing has changed:

```bash
kubectl get svc backend-loadbalancer -n hw11 -o wide
kubectl get svc backend-loadbalancer -n hw11 -o jsonpath='{.status.loadBalancer}'
```

```text
NAME                   TYPE           CLUSTER-IP       EXTERNAL-IP   PORT(S)        AGE    SELECTOR
backend-loadbalancer   LoadBalancer   10.108.109.237   <pending>     80:30111/TCP   4m4s   app=backend
{}
```

**`EXTERNAL-IP` is `<pending>` and `status.loadBalancer` is an empty object `{}`.** It will stay
that way forever. This is the honest result and it is not a failure — it is the correct behaviour.

### Why it is pending

`type: LoadBalancer` is a *request*, not an implementation. Kubernetes core does not know how to
build a load balancer. The work is done by a **cloud controller manager**, and this cluster does not
have one running. The service object sits there with an unfulfilled request and an empty status.

```bash
kubectl describe svc backend-loadbalancer -n hw11
```

```text
Name:                     backend-loadbalancer
Namespace:                hw11
Labels:                   app=backend
Annotations:              <none>
Selector:                 app=backend
Type:                     LoadBalancer
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       10.108.109.237
IPs:                      10.108.109.237
Port:                     http  80/TCP
TargetPort:               80/TCP
NodePort:                 http  30111/TCP
Endpoints:                10.244.0.5:80,10.244.0.6:80
Session Affinity:         None
External Traffic Policy:  Cluster
Internal Traffic Policy:  Cluster
Events:                   <none>
```

`Events: <none>` is itself evidence — a cluster with an unhappy cloud controller would log a failed
provisioning event. Here nothing is even trying.

### The "Russian doll" is real — the inner two layers work fine

```bash
kubectl exec -n hw11 netshoot -- curl -s --max-time 5 http://backend-loadbalancer
minikube ssh -- "curl -s http://192.168.49.2:30111"
```

```text
hello from backend pod backend-77bd96dd69-4g585
hello from backend pod backend-77bd96dd69-xf5jd
```

A LoadBalancer service is built out of the other two:

```text
      LoadBalancer  ──► not provisioned here  (EXTERNAL-IP <pending>)
           wraps
        NodePort    ──► 30111, WORKING (proved above from inside the node)
           wraps
        ClusterIP   ──► 10.108.109.237, WORKING (proved above from a pod)
           wraps
          Pods      ──► 10.244.0.5, 10.244.0.6
```

Only the outermost doll is missing. Everything underneath was created and is serving traffic.

### What a cloud provider would have done instead

On EKS / GKE / AKS the sequence on `kubectl apply` is:

1. The API server stores the Service with `type: LoadBalancer`.
2. The **cloud controller manager** (running as a pod in `kube-system`, with an IAM role / service
   account granted by the cloud) sees a LoadBalancer service whose `status.loadBalancer` is empty.
3. It calls the cloud API — `CreateLoadBalancer` on AWS ELBv2, `compute.forwardingRules.insert` on
   GCP — and creates a **real, billable** device outside the cluster.
4. It registers every node as a target on the LB's backend pool, pointed at the nodePort `30111`.
5. It health-checks the nodes on that port.
6. When the cloud returns the LB's address it patches it into `status.loadBalancer.ingress`, and
   `EXTERNAL-IP` flips from `<pending>` to something like `a1b2c3.elb.us-east-1.amazonaws.com`
   (AWS returns a hostname) or `34.120.55.18` (GCP returns an IP).

Then the path for a real user is:

```text
[browser] ──:443──► [AWS NLB, public IP]
                        │
                        └──:30111──► [node-1] [node-2] [node-3]
                                          │
                                          └── iptables DNAT ──► [pod]
```

**Cost note, and the reason Ingress exists:** every LoadBalancer service creates its own cloud
device, roughly $15–30/month each on AWS before data transfer. Fifty microservices exposed this way
is fifty load balancers. Production practice is one LoadBalancer in front of one ingress controller,
with every application service left as plain ClusterIP behind it — which is exactly session 12.

### Ways to make it resolve locally, and why they were not used here

| Option | What it does | Used here? |
| :--- | :--- | :--- |
| `minikube tunnel` | runs a local process that creates a route and assigns the service an external IP on the host | **no** — it requires `sudo` and this shell has no passwordless sudo (`sudo: a password is required`), and the cluster is shared, so forcing an interactive password prompt was not acceptable |
| MetalLB | a real bare-metal LB implementation; hands out IPs from a pool you configure | no — needs a cluster-wide install, out of scope for a shared cluster |
| `kubectl port-forward` | tunnels through the API server | not a LoadBalancer demonstration |

No external IP was faked. `<pending>` is the true state.

---

## Task 4 — ExternalName: a CNAME with no pods, no IP and no proxy

### The manifests

```yaml
apiVersion: v1
kind: Service
metadata:
  name: external-db
  namespace: hw11
spec:
  type: ExternalName
  externalName: example.com
---
apiVersion: v1
kind: Service
metadata:
  name: legacy-rds
  namespace: hw11
spec:
  type: ExternalName
  externalName: my-postgres-prod.c2345892.us-east-1.rds.amazonaws.com
```

Two of them on purpose: `external-db` points at a name that really resolves, so the full CNAME → A
chain is visible; `legacy-rds` points at an RDS hostname that does **not** exist, to prove a
separate point below.

```bash
kubectl apply -f manifests/06-externalname-service.yaml
kubectl get svc external-db legacy-rds -n hw11 -o wide
```

```text
service/external-db created
service/legacy-rds created
NAME          TYPE           CLUSTER-IP   EXTERNAL-IP                                             PORT(S)   AGE   SELECTOR
external-db   ExternalName   <none>       example.com                                             <none>    17s   <none>
legacy-rds    ExternalName   <none>       my-postgres-prod.c2345892.us-east-1.rds.amazonaws.com   <none>    17s   <none>
```

Read that row carefully — it is the odd one out in every column. `CLUSTER-IP` is `<none>`, `PORT(S)`
is `<none>`, `SELECTOR` is `<none>`, and the external name is shown in the `EXTERNAL-IP` column even
though it is a hostname, not an IP.

### Resolve it from a pod

```bash
kubectl exec -n hw11 netshoot -- nslookup external-db
```

```text
Server:		10.96.0.10
Address:	10.96.0.10#53

external-db.hw11.svc.cluster.local	canonical name = example.com.
Name:	example.com
Address: 172.66.147.243
Name:	example.com
Address: 104.20.23.154
```

`canonical name =` is nslookup's way of printing a CNAME.

### The CNAME, clearly, with dig

```bash
kubectl exec -n hw11 netshoot -- dig +noall +answer external-db.hw11.svc.cluster.local
```

```text
external-db.hw11.svc.cluster.local. 30 IN CNAME	example.com.
example.com.		30	IN	A	172.66.147.243
example.com.		30	IN	A	104.20.23.154
```

This is the requested proof. The answer section has **three records**: one `CNAME` written by
CoreDNS, then the two `A` records the resolver followed on to. CoreDNS answers "that name is really
called `example.com`" and the client's own resolver finishes the job.

### The second service proves ExternalName is pure DNS

```bash
kubectl exec -n hw11 netshoot -- dig legacy-rds.hw11.svc.cluster.local
```

```text
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 4511
;; flags: qr aa rd; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1
;; WARNING: recursion requested but not available

;; ANSWER SECTION:
legacy-rds.hw11.svc.cluster.local. 30 IN CNAME	my-postgres-prod.c2345892.us-east-1.rds.amazonaws.com.
```

`status: NOERROR`, one answer, a perfectly good CNAME — pointing at a host that does not exist.
Kubernetes **never validates `externalName`**. It never connects to it, never health-checks it,
never resolves it at creation time. It just writes a CNAME. If the target is wrong you will not find
out from `kubectl get svc`; you find out when your application's connection fails.

### No endpoints, ever

```bash
kubectl get endpoints external-db legacy-rds -n hw11
```

```text
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
Error from server (NotFound): endpoints "external-db" not found
Error from server (NotFound): endpoints "legacy-rds" not found
```

Not "empty" — **not found**. The objects do not exist. ExternalName is the only service type with no
selector, no endpoints, no ClusterIP, and no kube-proxy involvement whatsoever. No packet of your
traffic is ever touched by Kubernetes; the pod talks straight to the external host.

### Two consequences worth knowing

- **TLS and HTTP Host headers.** Because the pod ends up connecting to the real external host, the
  certificate it is presented belongs to `example.com`, not to `external-db`. ExternalName does not
  rewrite anything. This is the single most common surprise with it.
- **`ports` are meaningless.** You may write a `ports` block on an ExternalName service and
  Kubernetes will store it, but nothing acts on it — there is no proxy to apply it. Your client must
  use the real port.

The production value is config portability: your app always reads `DB_HOST=db-service`. In dev
`db-service` is a ClusterIP in front of a Postgres pod; in prod it is an ExternalName pointing at
Aurora. The application code and its ConfigMap never change.

---

## Task 5 — Headless service: one A record per pod

This is the task where the side-by-side matters, so the manifests deliberately create **two
services selecting the same three pods** — one headless, one normal ClusterIP. Same backends, same
selector, completely different DNS behaviour. That isolates the variable to the single line
`clusterIP: None`.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: cache-headless
  namespace: hw11
  labels:
    app: cache
spec:
  clusterIP: None
  selector:
    app: cache
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: cache-clusterip
  namespace: hw11
  labels:
    app: cache
spec:
  type: ClusterIP
  selector:
    app: cache
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 80
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: cache
  namespace: hw11
  labels:
    app: cache
spec:
  serviceName: cache-headless
  replicas: 3
  selector:
    matchLabels:
      app: cache
  template:
    metadata:
      labels:
        app: cache
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          ports:
            - name: http
              containerPort: 80
          resources:
            requests:
              cpu: "25m"
              memory: "32Mi"
            limits:
              cpu: "100m"
              memory: "64Mi"
```

`serviceName: cache-headless` in the StatefulSet is what creates the per-pod DNS names. It is the
**governing service**, and it must be headless for the per-pod records to be produced.

```bash
kubectl apply -f manifests/07-headless.yaml
kubectl rollout status statefulset/cache -n hw11 --timeout=180s
kubectl get svc cache-headless cache-clusterip -n hw11 -o wide
kubectl get pods -n hw11 -l app=cache -o custom-columns=NAME:.metadata.name,IP:.status.podIP,STATUS:.status.phase
```

```text
partitioned roll out complete: 3 new pods have been updated...
NAME              TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE   SELECTOR
cache-headless    ClusterIP   None           <none>        80/TCP    32s   app=cache
cache-clusterip   ClusterIP   10.97.113.25   <none>        80/TCP    32s   app=cache

NAME      IP            STATUS
cache-0   10.244.0.31   Running
cache-1   10.244.0.33   Running
cache-2   10.244.0.34   Running
```

`CLUSTER-IP` literally reads `None`. Also note the pod names: `cache-0`, `cache-1`, `cache-2` — a
StatefulSet gives ordinal, stable names, unlike a Deployment's random hash suffixes.

### The side-by-side — the key insight of this task

```bash
kubectl exec -n hw11 netshoot -- dig +noall +answer cache-clusterip.hw11.svc.cluster.local
kubectl exec -n hw11 netshoot -- dig +noall +answer cache-headless.hw11.svc.cluster.local
```

```text
cache-clusterip.hw11.svc.cluster.local.	30 IN A	10.97.113.25

cache-headless.hw11.svc.cluster.local. 30 IN A	10.244.0.34
cache-headless.hw11.svc.cluster.local. 30 IN A	10.244.0.33
cache-headless.hw11.svc.cluster.local. 30 IN A	10.244.0.31
```

**Same three pods. Same selector. Two completely different answers.**

- The ClusterIP service returns **one A record**, and the address `10.97.113.25` is a virtual IP
  that belongs to no pod. The client has no idea how many backends exist. kube-proxy decides.
- The headless service returns **three A records**, and each address is a **real pod IP**. There is
  no virtual IP and no kube-proxy in the path. The client gets the full membership list and decides
  for itself who to talk to.

That is the entire difference: a ClusterIP hides the backends behind a proxy, a headless service
publishes them.

The same thing through nslookup, which shows the multiple addresses just as plainly:

```bash
kubectl exec -n hw11 netshoot -- nslookup cache-headless
```

```text
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	cache-headless.hw11.svc.cluster.local
Address: 10.244.0.34
Name:	cache-headless.hw11.svc.cluster.local
Address: 10.244.0.31
Name:	cache-headless.hw11.svc.cluster.local
Address: 10.244.0.33
```

Notice the order differs between the two lookups above. CoreDNS shuffles the record order on each
response — that is the only "load balancing" a headless service does, and it is done by the DNS
server, not by the network.

### One stable DNS name per pod

```bash
for i in 0 1 2; do
  kubectl exec -n hw11 netshoot -- dig +noall +answer cache-$i.cache-headless.hw11.svc.cluster.local
done
```

```text
cache-0.cache-headless.hw11.svc.cluster.local. 30 IN A 10.244.0.31
cache-1.cache-headless.hw11.svc.cluster.local. 30 IN A 10.244.0.33
cache-2.cache-headless.hw11.svc.cluster.local. 30 IN A 10.244.0.34
```

Each pod is individually addressable at
`<pod-name>.<headless-service>.<namespace>.svc.cluster.local`. This is how a Kafka broker finds
broker 0, how a MongoDB replica finds the primary, how Cassandra seeds itself.

### Prove the name is stable when the pod is not

```bash
kubectl get pod cache-1 -n hw11 -o custom-columns=NAME:.metadata.name,IP:.status.podIP
kubectl delete pod cache-1 -n hw11
kubectl wait --for=condition=Ready pod/cache-1 -n hw11 --timeout=120s
kubectl get pod cache-1 -n hw11 -o custom-columns=NAME:.metadata.name,IP:.status.podIP
kubectl exec -n hw11 netshoot -- dig +noall +answer cache-1.cache-headless.hw11.svc.cluster.local
```

```text
NAME      IP
cache-1   10.244.0.33

pod "cache-1" deleted from hw11 namespace
pod/cache-1 condition met

NAME      IP
cache-1   10.244.0.39

cache-1.cache-headless.hw11.svc.cluster.local. 30 IN A 10.244.0.39
```

The pod IP changed from `10.244.0.33` to `10.244.0.39`. The **name did not change**, and CoreDNS
updated the record to follow it. A peer that had hardcoded `10.244.0.33` is now broken; a peer that
uses `cache-1.cache-headless` never noticed. That is the reason headless services exist.

### Headless services still have endpoints

```bash
kubectl get endpointslices -n hw11 -l kubernetes.io/service-name=cache-headless
kubectl get endpointslices -n hw11 -l kubernetes.io/service-name=cache-clusterip
```

```text
NAME                   ADDRESSTYPE   PORTS   ENDPOINTS                             AGE
cache-headless-g54mb   IPv4          80      10.244.0.31,10.244.0.33,10.244.0.34   32s
NAME                    ADDRESSTYPE   PORTS   ENDPOINTS                             AGE
cache-clusterip-7hhqb   IPv4          80      10.244.0.31,10.244.0.33,10.244.0.34   32s
```

Identical endpoint lists. The endpoint controller behaves exactly the same for both. What differs is
what happens downstream: for the ClusterIP service kube-proxy turns that list into iptables rules,
for the headless service CoreDNS turns the same list into A records and kube-proxy ignores it.

---

## Task 6 — DNS, `/etc/resolv.conf`, `ndots:5` and crossing namespaces

### What Kubernetes injects into every pod

```bash
kubectl exec -n hw11 netshoot -- cat /etc/resolv.conf
```

```text
search hw11.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5
```

Three lines, and every one of them matters.

**`nameserver 10.96.0.10`** — every DNS query from this pod goes here. It is not a special address;
it is an ordinary ClusterIP:

```bash
kubectl get svc kube-dns -n kube-system
kubectl get pods -n kube-system -l k8s-app=kube-dns
```

```text
NAME       TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)                  AGE
kube-dns   ClusterIP   10.96.0.10   <none>        53/UDP,53/TCP,9153/TCP   7m34s
NAME                       READY   STATUS    RESTARTS   AGE
coredns-559f6c778d-bnc89   1/1     Running   0          7m27s
```

The service is still named `kube-dns` for backwards compatibility even though the software behind it
has been CoreDNS since Kubernetes 1.13. Note the pleasing recursion: DNS itself is reached through a
ClusterIP service, resolved by kube-proxy's iptables rules rather than by DNS.

**`search hw11.svc.cluster.local svc.cluster.local cluster.local`** — the autocomplete list. When
you type a name that is not fully qualified, the resolver tries each suffix **in order** until one
answers:

| Attempt | Name actually queried | Purpose |
| :--- | :--- | :--- |
| 1 | `<name>.hw11.svc.cluster.local` | services in **my own namespace** — this is why short names work locally |
| 2 | `<name>.svc.cluster.local` | lets you write `payments.hw11-other` and have the rest filled in |
| 3 | `<name>.cluster.local` | matches `<pod-ip>.<ns>.pod.cluster.local` style records |
| 4 | `<name>` as typed | the outside internet |

The first suffix is namespace-specific. It is generated from the namespace the pod runs in, and it
is the single reason short names do not cross namespaces.

**`options ndots:5`** — "if the name you typed has fewer than 5 dots, treat it as a short name and
walk the search list first." Almost every real name has fewer than 5 dots, so almost everything goes
through the search list. That is convenient inside the cluster and wasteful outside it — proved
with a packet capture below.

### Same namespace: short name works

```bash
kubectl exec -n hw11 netshoot -- dig +noall +answer +search backend-clusterip
kubectl exec -n hw11 netshoot -- curl -s --max-time 5 http://backend-clusterip
```

```text
backend-clusterip.hw11.svc.cluster.local. 30 IN	A 10.102.20.51
hello from backend pod backend-77bd96dd69-xf5jd
```

Look at the left-hand side of the answer: the question was `backend-clusterip`, the answer came back
for `backend-clusterip.hw11.svc.cluster.local.`. The first search suffix was appended and matched.

### Full FQDN works too

```bash
kubectl exec -n hw11 netshoot -- dig +noall +answer backend-clusterip.hw11.svc.cluster.local
kubectl exec -n hw11 netshoot -- curl -s --max-time 5 http://backend-clusterip.hw11.svc.cluster.local
```

```text
backend-clusterip.hw11.svc.cluster.local. 30 IN	A 10.102.20.51
hello from backend pod backend-77bd96dd69-4g585
```

Same IP, no search-list guessing needed.

### Crossing namespaces: the short name FAILS

There is a `payments` service in `hw11-other`:

```bash
kubectl get svc payments -n hw11-other -o wide
```

```text
NAME       TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE   SELECTOR
payments   ClusterIP   10.101.195.213   <none>        80/TCP    71s   app=payments
```

From the `netshoot` pod, which lives in `hw11`:

```bash
kubectl exec -n hw11 netshoot -- nslookup payments
kubectl exec -n hw11 netshoot -- curl -s --max-time 5 http://payments
```

```text
Server:		10.96.0.10
Address:	10.96.0.10#53

** server can't find payments: NXDOMAIN
command terminated with exit code 1

command terminated with exit code 6
```

`NXDOMAIN`, and curl exits **6** — "couldn't resolve host". Not a timeout, not connection refused:
the name genuinely does not exist from where this pod is standing. The resolver tried
`payments.hw11.svc.cluster.local` first, and there is no `payments` in `hw11`:

```bash
kubectl exec -n hw11 netshoot -- dig payments.hw11.svc.cluster.local | grep -E 'HEADER|status'
```

```text
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 25229
```

This is the single most common "my app can't reach the database" ticket in real life, and the error
message is a big clue: **exit code 6 / NXDOMAIN means a naming problem, not a networking or firewall
problem.** Nothing was blocked. Nothing was refused. The name was never resolved.

### `service.namespace` works

```bash
kubectl exec -n hw11 netshoot -- dig +noall +answer +search payments.hw11-other
kubectl exec -n hw11 netshoot -- curl -s --max-time 5 http://payments.hw11-other
```

```text
payments.hw11-other.svc.cluster.local. 30 IN A	10.101.195.213
hello from payments in hw11-other, pod payments-688cb67584-rxxqf
```

`payments.hw11-other` has one dot, so the search list runs. Suffix 1 gives
`payments.hw11-other.hw11.svc.cluster.local` — NXDOMAIN. Suffix 2 gives
`payments.hw11-other.svc.cluster.local` — **match**. The second search suffix exists precisely to
make this two-part form work.

### The full FQDN works and is unambiguous

```bash
kubectl exec -n hw11 netshoot -- dig +noall +answer payments.hw11-other.svc.cluster.local
kubectl exec -n hw11 netshoot -- curl -s --max-time 5 http://payments.hw11-other.svc.cluster.local
```

```text
payments.hw11-other.svc.cluster.local. 30 IN A	10.101.195.213
hello from payments in hw11-other, pod payments-688cb67584-rxxqf
```

Same pod answers. Summary of the three attempts:

| From a pod in `hw11`, dialling... | Result | Why |
| :--- | :--- | :--- |
| `payments` | **NXDOMAIN** | expands to `payments.hw11.svc.cluster.local`; wrong namespace |
| `payments.hw11-other` | works | expands via suffix 2 to `payments.hw11-other.svc.cluster.local` |
| `payments.hw11-other.svc.cluster.local` | works | already fully qualified |

Note that DNS is *not* a security boundary. The cross-namespace lookup succeeded with no permission
of any kind — namespaces separate names, not traffic. Blocking pod-to-pod traffic between namespaces
requires NetworkPolicy.

### Proving `ndots:5` with a packet capture

Talk is cheap; here is `tcpdump` running inside the pod while it resolves `example.com`, which has
only 2 dots and is therefore below the `ndots:5` threshold:

```bash
kubectl exec -n hw11 netshoot -- sh -c \
  'timeout 8 tcpdump -l -n -i any udp port 53 > /tmp/dA.txt 2>/dev/null &
   sleep 2; nslookup -type=a example.com >/dev/null 2>&1; sleep 3; head -8 /tmp/dA.txt'
```

```text
17:03:10.128262 eth0  Out IP 10.244.0.7.33218 > 10.96.0.10.53: 28242+ A? example.com.hw11.svc.cluster.local. (52)
17:03:10.128873 eth0  In  IP 10.96.0.10.53 > 10.244.0.7.33218: 28242 NXDomain*- 0/1/0 (145)
17:03:10.130766 eth0  Out IP 10.244.0.7.51354 > 10.96.0.10.53: 47226+ A? example.com.svc.cluster.local. (47)
17:03:10.130926 eth0  In  IP 10.96.0.10.53 > 10.244.0.7.51354: 47226 NXDomain*- 0/1/0 (140)
17:03:10.132062 eth0  Out IP 10.244.0.7.56553 > 10.96.0.10.53: 40249+ A? example.com.cluster.local. (43)
17:03:10.132240 eth0  In  IP 10.96.0.10.53 > 10.244.0.7.56553: 40249 NXDomain*- 0/1/0 (136)
17:03:10.133449 eth0  Out IP 10.244.0.7.47627 > 10.96.0.10.53: 38221+ A? example.com. (29)
17:03:10.133577 eth0  In  IP 10.96.0.10.53 > 10.244.0.7.47627: 38221* 2/0/0 A 104.20.23.154, A 172.66.147.243 (83)
```

There it is on the wire. **Four queries to answer one lookup**, three of them returning `NXDomain`,
walking the search list in exactly the order `/etc/resolv.conf` lists it, before the fourth query
asks the real question and gets `2/0/0` — two answers.

Now the same name with a trailing dot, which tells the resolver it is already fully qualified:

```bash
kubectl exec -n hw11 netshoot -- sh -c \
  'timeout 8 tcpdump -l -n -i any udp port 53 > /tmp/dB.txt 2>/dev/null &
   sleep 2; nslookup -type=a example.com. >/dev/null 2>&1; sleep 3; head -8 /tmp/dB.txt'
```

```text
17:03:15.218440 eth0  Out IP 10.244.0.7.49099 > 10.96.0.10.53: 6365+ A? example.com. (29)
17:03:15.218836 eth0  In  IP 10.96.0.10.53 > 10.244.0.7.49099: 6365* 2/0/0 A 172.66.147.243, A 104.20.23.154 (83)
```

**One query.** Four packets became two.

Why a senior engineer cares: multiply three wasted round-trips by every outbound call your service
makes to an external API. At a few thousand requests per second that is thousands of pointless UDP
queries per second hitting CoreDNS, which shows up as CoreDNS CPU saturation and mysterious
tail-latency spikes on external calls. The fixes, in increasing order of blast radius:

1. Add the trailing dot in application config (`api.stripe.com.`) — zero-risk, per-name.
2. Lower `ndots` for one pod with `dnsConfig` — affects only that workload:
   ```yaml
   spec:
     dnsConfig:
       options:
         - name: ndots
           value: "2"
   ```
   Careful: with `ndots:2`, `payments.hw11-other` has 1 dot and still uses the search list, but a
   name with 2+ dots is tried literally first. Set it too low and in-cluster short names break.
3. Run NodeLocal DNSCache — a per-node caching DNS agent, so the wasted queries never leave the node.

---

## Task 7 — Troubleshooting drill: a service with empty endpoints

This mirrors `session-11-kubernetes-services/troubleshooting/empty-endpoints.yaml`: a service whose
selector does not match any pod's labels.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: broken-backend
  namespace: hw11
spec:
  type: ClusterIP
  selector:
    app: wrong-backend-name
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 80
```

The backend pods carry `app: backend`. The service is hunting for `app: wrong-backend-name`.

### Step 1 — it looks perfectly healthy

```bash
kubectl apply -f manifests/09-broken-service.yaml
kubectl get svc broken-backend -n hw11 -o wide
```

```text
service/broken-backend created
NAME             TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE   SELECTOR
broken-backend   ClusterIP   10.105.19.229   <none>        80/TCP    11s   app=wrong-backend-name
```

`kubectl apply` succeeded. The service has a ClusterIP. There is no error, no warning, no event.
Kubernetes will happily create a service pointing at labels that match nothing — a selector is a
query, and an empty result is a valid result.

### Step 2 — the symptom

```bash
kubectl exec -n hw11 netshoot -- curl -sS --max-time 5 http://broken-backend
```

```text
curl: (7) Failed to connect to broken-backend:80 after 3 ms: Could not connect to server
command terminated with exit code 7
```

**Exit code 7, and it failed in 3 milliseconds.** Both facts are diagnostic. Exit 7 is "failed to
connect", not exit 6 "couldn't resolve" — so DNS worked. And 3ms is far too fast for a network
timeout; the kernel rejected it instantly. A firewall would hang; a wrong `targetPort` would refuse
at the pod. This is something else.

### Step 3 — rule out DNS

```bash
kubectl exec -n hw11 netshoot -- dig +noall +answer broken-backend.hw11.svc.cluster.local
```

```text
broken-backend.hw11.svc.cluster.local. 30 IN A	10.105.19.229
```

DNS is fine. The name resolves to the ClusterIP. Confirms what exit code 7 already implied — the
problem is behind the name, not in it.

### Step 4 — the smoking gun

```bash
kubectl get endpoints broken-backend -n hw11
```

```text
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME             ENDPOINTS   AGE
broken-backend   <none>      11s
```

**`ENDPOINTS` is `<none>`.** This is the answer. The service has a ClusterIP and a DNS record, but
zero backends behind it. kube-proxy wrote a rule that says "packets for `10.105.19.229:80` go
to... nothing", so the kernel `REJECT`s them immediately — which is precisely why curl failed in
3ms instead of hanging.

`describe` says the same thing:

```bash
kubectl describe svc broken-backend -n hw11
```

```text
Name:                     broken-backend
Namespace:                hw11
Labels:                   <none>
Annotations:              <none>
Selector:                 app=wrong-backend-name
Type:                     ClusterIP
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       10.105.19.229
IPs:                      10.105.19.229
Port:                     http  80/TCP
TargetPort:               80/TCP
Endpoints:
Session Affinity:         None
Internal Traffic Policy:  Cluster
Events:                   <none>
```

An empty `Endpoints:` line. `Events: <none>` again — Kubernetes does not consider this an error, so
it never tells you. You have to go looking.

### Step 5 — the EndpointSlice tells the same story

```bash
kubectl get endpointslices -n hw11 -l kubernetes.io/service-name=broken-backend
kubectl get endpointslices -n hw11 -l kubernetes.io/service-name=broken-backend -o yaml | grep -E 'addressType|endpoints:'
```

```text
NAME                   ADDRESSTYPE   PORTS     ENDPOINTS   AGE
broken-backend-9248z   IPv4          <unset>   <unset>     11s

- addressType: IPv4
  endpoints: null
```

The slice was created (the controller always creates one) but `endpoints: null`. `PORTS` shows
`<unset>` too — with no pods to inspect, the controller could not even resolve the target port.

### Step 6 — diagnose: selector vs labels, side by side

This is the actual diagnostic technique. Ask what the service is looking for, then ask what the pods
have:

```bash
kubectl get svc broken-backend -n hw11 -o jsonpath='{.spec.selector}'
kubectl get pods -n hw11 --show-labels
```

```text
{"app":"wrong-backend-name"}

NAME                       READY   STATUS    RESTARTS   AGE     LABELS
backend-77bd96dd69-4g585   1/1     Running   0          5m47s   app=backend,pod-template-hash=77bd96dd69,tier=api
backend-77bd96dd69-xf5jd   1/1     Running   0          5m47s   app=backend,pod-template-hash=77bd96dd69,tier=api
cache-0                    1/1     Running   0          2m58s   app=cache,apps.kubernetes.io/pod-index=0,controller-revision-hash=cache-578795bf7,statefulset.kubernetes.io/pod-name=cache-0
cache-1                    1/1     Running   0          2m14s   app=cache,apps.kubernetes.io/pod-index=1,controller-revision-hash=cache-578795bf7,statefulset.kubernetes.io/pod-name=cache-1
cache-2                    1/1     Running   0          2m56s   app=cache,apps.kubernetes.io/pod-index=2,controller-revision-hash=cache-578795bf7,statefulset.kubernetes.io/pod-name=cache-2
netshoot                   1/1     Running   0          5m47s   app=netshoot,role=client
```

The service wants `app=wrong-backend-name`. Not one pod in the namespace has it. The backend pods
have `app=backend`.

Confirm it by running the service's own selector as a label query — this is the exact operation the
endpoint controller performs:

```bash
kubectl get pods -n hw11 -l app=wrong-backend-name
kubectl get pods -n hw11 -l app=backend
```

```text
No resources found in hw11 namespace.

NAME                       READY   STATUS    RESTARTS   AGE
backend-77bd96dd69-4g585   1/1     Running   0          5m47s
backend-77bd96dd69-xf5jd   1/1     Running   0          5m47s
```

Diagnosis complete: `kubectl get pods -l <the service's selector>` returning nothing **is** the bug.

### Step 7 — fix it

Change one line, `app: wrong-backend-name` → `app: backend`:

```bash
kubectl apply -f manifests/10-fixed-service.yaml
kubectl get endpoints broken-backend -n hw11
kubectl get endpointslices -n hw11 -l kubernetes.io/service-name=broken-backend
```

```text
service/broken-backend configured
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME             ENDPOINTS                     AGE
broken-backend   10.244.0.5:80,10.244.0.6:80   31s
NAME                   ADDRESSTYPE   PORTS   ENDPOINTS               AGE
broken-backend-9248z   IPv4          80      10.244.0.5,10.244.0.6   31s
```

`configured`, not `created` — and the endpoints populated immediately. `PORTS` went from `<unset>`
to `80`.

### Step 8 — prove traffic flows

```bash
kubectl exec -n hw11 netshoot -- sh -c 'for i in 1 2 3 4; do curl -sS --max-time 5 http://broken-backend; done'
kubectl get svc broken-backend -n hw11 -o wide
```

```text
hello from backend pod backend-77bd96dd69-4g585
hello from backend pod backend-77bd96dd69-4g585
hello from backend pod backend-77bd96dd69-xf5jd
hello from backend pod backend-77bd96dd69-4g585

NAME             TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE   SELECTOR
broken-backend   ClusterIP   10.105.19.229   <none>        80/TCP    31s   app=backend
```

Traffic flows, across both pods. And notice: **the ClusterIP is still `10.105.19.229`** — the same
address that was failing a minute ago. No pod restarted, no DNS record changed, no IP was
reallocated. One label fixed it. That is worth internalising: a service is just a label query plus a
port mapping.

### Endpoints is deprecated — the version, and why

```bash
kubectl api-resources | grep -iE 'endpoint'
kubectl version -o json | grep gitVersion
```

```text
endpoints                           ep           v1                                true         Endpoints
endpointslices                                   discovery.k8s.io/v1               true         EndpointSlice
    "gitVersion": "v1.37.0",
    "gitVersion": "v1.37.0",
```

**`v1 Endpoints` is deprecated as of Kubernetes v1.33**, which is exactly what `kubectl` prints on
every `get endpoints` on this v1.37.0 cluster:

```text
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
```

It still works — v1 is a GA API and cannot simply be removed — but it is frozen, and the control
plane's source of truth is `discovery.k8s.io/v1 EndpointSlice`. `Endpoints` objects are now
mirrored from slices for compatibility.

Why the replacement was needed:

| | `Endpoints` (v1) | `EndpointSlice` (discovery.k8s.io/v1) |
| :--- | :--- | :--- |
| Shape | **one object per service** holding every backend | many objects, **100 endpoints per slice** by default |
| Update cost | change one pod → rewrite and re-broadcast the whole object to every node | change one pod → rewrite one small slice |
| Scale ceiling | a 5,000-pod service is one enormous object; churn saturates the API server and every kube-proxy | scales linearly |
| Dual-stack | one address family only | `addressType: IPv4` / `IPv6` / `FQDN`, multiple slices per service |
| Topology | none | `nodeName`, `zone`, `hints` — enables topology-aware routing |
| Readiness detail | in or out | `ready`, `serving`, `terminating` as three separate conditions |

That last row is visible in the real object:

```bash
kubectl get endpointslices -n hw11 -l kubernetes.io/service-name=backend-clusterip -o yaml
```

```text
- addressType: IPv4
  apiVersion: discovery.k8s.io/v1
  endpoints:
  - addresses:
    - 10.244.0.5
    conditions:
      ready: true
      serving: true
      terminating: false
    nodeName: minikube
    targetRef:
      kind: Pod
      name: backend-77bd96dd69-xf5jd
      namespace: hw11
      uid: 6ea3e902-7abc-4ebe-b41b-91e6fc11ff58
  - addresses:
    - 10.244.0.6
    conditions:
      ready: true
      serving: true
      terminating: false
    nodeName: minikube
    targetRef:
      kind: Pod
      name: backend-77bd96dd69-4g585
      namespace: hw11
      uid: a123f8d1-f604-409c-98a7-4a2582c1045a
  kind: EndpointSlice
  metadata:
    labels:
      endpointslice.kubernetes.io/managed-by: endpointslice-controller.k8s.io
      kubernetes.io/service-name: backend-clusterip
```

`serving: true, terminating: false` is the pair that `Endpoints` could never express. During a
graceful shutdown a pod becomes `ready: false, serving: true, terminating: true` — still finishing
in-flight requests, no longer accepting new ones. Under the old model it simply vanished from the
list, which is where a lot of "500s during every deploy" bugs came from.

Practical rule for 2025+: **debug with `kubectl get endpointslices`**, and treat
`kubectl get endpoints` as a convenient shorthand that prints a deprecation warning.

### Empty-endpoints triage checklist

`ENDPOINTS: <none>` has four common causes. Work them in this order:

| # | Cause | How to confirm | Fix |
| :--- | :--- | :--- | :--- |
| 1 | **Selector does not match pod labels** (this drill) | `kubectl get pods -l <selector>` returns nothing | correct the selector, or the pod labels |
| 2 | **Right labels, wrong namespace** | pods exist but `kubectl get pods -n <svc-ns> -l <selector>` is empty | a Service only ever selects pods in its **own** namespace |
| 3 | **Pods failing readiness** | `kubectl get pods` shows `0/1 READY`; `describe pod` shows probe failures | fix the probe or the app |
| 4 | **No pods at all** | `kubectl get deploy` shows `0/0` or pods Pending | scale up / fix scheduling |

And the important near-miss: if endpoints **are** populated but curl still fails, it is not a
selector problem — it is a wrong `targetPort`, or the app bound to `127.0.0.1` inside the container
instead of `0.0.0.0`.

---

## The five service types, side by side

All five were built in this homework. Here they are in one listing:

```bash
kubectl get svc -n hw11 -o wide
```

```text
NAME                   TYPE           CLUSTER-IP       EXTERNAL-IP                                             PORT(S)        AGE     SELECTOR
backend-clusterip      ClusterIP      10.102.20.51     <none>                                                  80/TCP         6m19s   app=backend
backend-loadbalancer   LoadBalancer   10.108.109.237   <pending>                                               80:30111/TCP   4m14s   app=backend
backend-nodeport       NodePort       10.97.124.9      <none>                                                  80:30110/TCP   5m19s   app=backend
broken-backend         ClusterIP      10.105.19.229    <none>                                                  80/TCP         53s     app=backend
cache-clusterip        ClusterIP      10.97.113.25     <none>                                                  80/TCP         3m30s   app=cache
cache-headless         ClusterIP      None             <none>                                                  80/TCP         3m30s   app=cache
external-db            ExternalName   <none>           example.com                                             <none>         3m30s   <none>
legacy-rds             ExternalName   <none>           my-postgres-prod.c2345892.us-east-1.rds.amazonaws.com   <none>         3m30s   <none>
```

You can read the whole comparison table straight off that output — `None` for headless, `<pending>`
for the unfulfilled LoadBalancer, `<none>` selectors and hostnames in the `EXTERNAL-IP` column for
ExternalName.

| Criterion | ClusterIP | NodePort | LoadBalancer | ExternalName | Headless (`None`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Default when `type` omitted | **yes** | no | no | no | no (`clusterIP: None`) |
| ClusterIP allocated | yes | yes (also creates one) | yes (also creates one) | **no** | **no** |
| NodePort allocated | no | yes | yes (implicitly) | no | no |
| Reachable from outside | no | yes, `<node-ip>:<nodePort>` | yes, via cloud LB | n/a — points outward | no |
| DNS answer | 1 A record → virtual IP | 1 A record → virtual IP | 1 A record → virtual IP | **CNAME** → external FQDN | **N A records**, one per ready pod |
| Creates Endpoints/Slices | yes | yes | yes | **no** | yes |
| kube-proxy in the path | yes | yes | yes | **no** | **no** |
| Load balancing done by | kube-proxy (iptables/IPVS) | kube-proxy | cloud LB + kube-proxy | nothing — DNS alias only | **the client application** |
| Needs a cloud provider | no | no | **yes** | no | no |
| Port range | 1–65535 | nodePort 30000–32767 | any (80/443 on the LB) | n/a | 1–65535 |
| Verified in this homework | `10.102.20.51`, curl by name | `30110`, curl from inside the node | **`<pending>`** — no cloud controller | CNAME to `example.com` | 3 A records for 3 pods |
| Typical use | internal microservice calls | bare metal, dev, ingress entry point | one per cluster, in front of ingress | RDS / Atlas / SaaS APIs | Kafka, Cassandra, MongoDB, StatefulSets |

### The ports table

| Field | Path in the manifest | Owned by | Who dials it | Required | Default |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `port` | `Service.spec.ports[].port` | the Service object | other pods, via ClusterIP or DNS | **yes** | — |
| `targetPort` | `Service.spec.ports[].targetPort` | the pod | the Service, when forwarding | no | same as `port` |
| `nodePort` | `Service.spec.ports[].nodePort` | every node's kernel | external clients | no | auto-assigned 30000–32767 |
| `containerPort` | `Pod.spec.containers[].ports[].containerPort` | nobody — metadata | nobody | no | — |

One-line memory hook: **`nodePort` → `port` → `targetPort` → the process.** `containerPort` is a
comment that happens to be YAML.

### Decision tree

```text
Do clients outside the cluster need to reach it?
│
├── NO ─► Do peers need to address individual pods (StatefulSet, leader election, gRPC LB)?
│          ├── YES ─► HEADLESS  (clusterIP: None)
│          └── NO  ─► CLUSTERIP (the default; use this ~90% of the time)
│
└── YES ─► Is the real destination outside the cluster (RDS, Atlas, a SaaS API)?
             ├── YES ─► EXTERNALNAME
             └── NO  ─► Is this a managed cloud cluster?
                          ├── YES ─► HTTP/HTTPS? ─► one LOADBALANCER in front of an ingress
                          │                         controller, apps stay CLUSTERIP
                          │          raw TCP/UDP? ─► LOADBALANCER directly
                          └── NO (bare metal / minikube) ─► NODEPORT, or MetalLB
```

---

## Interview questions

**Q1 — What is the default Service type, and what does it give you?**
`ClusterIP`. A stable virtual IP from the service CIDR plus a DNS name
`<svc>.<ns>.svc.cluster.local`, reachable only from inside the cluster. It is a stable front door for
a set of pods whose IPs change constantly.

**Q2 — Walk me through `nodePort`, `port`, `targetPort` and `containerPort`.**
`nodePort` (30000–32767) is opened on every node for external clients. `port` is the Service's own
port, what other pods dial. `targetPort` is the port on the pod that the Service forwards to.
`containerPort` is pure metadata in the Pod spec — delete it and nothing breaks. Traffic flows
`nodePort → port → targetPort → process`. The one that must be correct is `targetPort`.

**Q3 — Is anything listening on a NodePort?**
No, not in modern `iptables` or `IPVS` mode. `netstat -lntp` on the node shows nothing for port
30110; kube-proxy writes netfilter rules in the `KUBE-NODEPORTS` chain and the kernel DNATs the
packet before userspace ever sees it. The old `userspace` mode did open a real socket, which is why
this trips people up. Verified in Task 2.

**Q4 — Why is `EXTERNAL-IP` stuck on `<pending>`?**
Because `type: LoadBalancer` is a request that only a **cloud controller manager** can fulfil, and a
local cluster has none. The ClusterIP and the NodePort underneath are created and working; only the
outermost layer is missing. Fixes: run `minikube tunnel`, install MetalLB on bare metal, or use a
managed cluster.

**Q5 — NodePort vs LoadBalancer?**
LoadBalancer is a superset. It creates a ClusterIP, then a NodePort, then asks the cloud to
provision an external device that forwards to `<node-ips>:<nodePort>`. NodePort stops one layer
short and makes the client know a node IP and an ugly high port — with no failover if that node
dies.

**Q6 — Why not give every microservice a LoadBalancer?**
Cost and capability. Each one is a separate billable cloud device (~$15–30/month on AWS before
traffic), so fifty services means fifty load balancers. And a LoadBalancer is Layer 4 — it cannot do
path routing, host routing or SNI-based TLS for many domains. One LoadBalancer in front of one
ingress controller solves both.

**Q7 — What does a headless service return that a ClusterIP does not?**
A ClusterIP returns one A record: a virtual IP. A headless service (`clusterIP: None`) gets no
virtual IP, and DNS returns one A record **per ready pod** — the real pod IPs. Proved in Task 5 with
two services selecting the same three pods: one answer versus three.

**Q8 — Why does a StatefulSet need a headless service?**
For the per-pod DNS names `<pod>.<svc>.<ns>.svc.cluster.local`. Clustered systems need to address
specific members — "replicate to `mongo-1`", "the leader is `kafka-0`" — which a load-balanced VIP
makes impossible. The `serviceName` field in the StatefulSet names the governing headless service
that produces those records.

**Q9 — Is a pod's DNS name stable if the pod is rescheduled?**
Yes for a StatefulSet pod under a headless service. Task 5 deleted `cache-1`; it came back with the
same name and a **new IP** (`10.244.0.33` → `10.244.0.39`), and its DNS record followed. Anything
that had cached the old IP is broken; anything using the name is not.

**Q10 — What is `ExternalName` and what does it not do?**
A CoreDNS CNAME to an external FQDN. No ClusterIP, no selector, no endpoints, no kube-proxy. It does
not proxy, does not health-check, does not rewrite the Host header or terminate TLS, and does not
validate the target — Task 4 created a CNAME to a non-existent RDS hostname and Kubernetes accepted
it with `status: NOERROR`. Because the pod connects to the real host, the TLS certificate it sees
belongs to that host, not to your service name.

**Q11 — `ExternalName` vs a selector-less Service with manual Endpoints?**
`ExternalName` maps a **name to a name** via DNS; traffic never enters the cluster network.
A selector-less Service plus a hand-written `Endpoints`/`EndpointSlice` maps a name to specific
**IP addresses** and routes through kube-proxy — which means it works for hosts that have no DNS
name, and lets you apply NetworkPolicy and see it in service metrics.

**Q12 — Can a Service have no selector?**
Yes. Kubernetes then creates no endpoints, and you supply them yourself. That is how you front an
external database, an on-prem host or a migration target with an ordinary in-cluster service name.

**Q13 — Explain `/etc/resolv.conf` in a pod.**
`nameserver 10.96.0.10` is the CoreDNS ClusterIP. `search <ns>.svc.cluster.local svc.cluster.local
cluster.local` is the autocomplete list tried in order, and its first entry is namespace-specific.
`options ndots:5` means any name with fewer than 5 dots walks that list before being tried literally.

**Q14 — Why does `ndots:5` hurt, and how do you fix it?**
Any external hostname has fewer than 5 dots, so every lookup burns extra queries first. Task 6's
packet capture showed `example.com` producing **four** queries — three NXDOMAIN, then the real one —
versus **one** for `example.com.`. At scale that is thousands of wasted queries per second hitting
CoreDNS. Fixes: trailing dot in config, lower `ndots` via pod `dnsConfig`, or NodeLocal DNSCache.

**Q15 — A pod in `staging` cannot reach a database in `prod`. First guess?**
The config uses the short name `mysql`, which expands to `mysql.staging.svc.cluster.local` and
returns NXDOMAIN. Fix it to `mysql.prod` or `mysql.prod.svc.cluster.local`. The tell is the error:
DNS resolution failure (curl exit 6) rather than connection refused or timeout.

**Q16 — Is DNS a security boundary between namespaces?**
No. Task 6 resolved and curled a service in another namespace with no permission at all. Namespaces
scope *names*, not traffic. Restricting cross-namespace traffic requires NetworkPolicy.

**Q17 — `kubectl get endpoints` shows `<none>`. Walk me through it.**
Check the selector against the pods (`kubectl get pods -l <selector>` — if it returns nothing that
is the bug), then check the pods are in the **same namespace** as the service, then check they are
`READY` (a failing readiness probe removes a pod from endpoints), then check any exist at all.
Task 7 was cause #1: selector `app=wrong-backend-name` against pods labelled `app=backend`.

**Q18 — Endpoints populated but curl still fails. Now what?**
Not a selector problem. Either `targetPort` does not match the port the process listens on, or the
app bound to `127.0.0.1` instead of `0.0.0.0` inside the container, or a NetworkPolicy is dropping
it. `kubectl exec` into a backend pod and curl `localhost:<targetPort>` to split the two.

**Q19 — What happens when a pod fails its readiness probe?**
The endpoint controller sets `ready: false` on that endpoint and kube-proxy removes its DNAT rule,
so no new traffic reaches it. The container is **not** restarted — that is what a liveness probe
does. Readiness controls traffic; liveness controls restarts.

**Q20 — Endpoints vs EndpointSlice, and when did that change?**
`v1 Endpoints` is deprecated **as of Kubernetes v1.33** — this v1.37.0 cluster prints the warning on
every `get endpoints`. Endpoints is one object per service, so a 5,000-pod service is one giant
object rewritten and rebroadcast on every pod change. EndpointSlices cap at 100 endpoints each,
support dual-stack via `addressType`, carry `nodeName`/`zone` for topology-aware routing, and expose
`ready`/`serving`/`terminating` separately — that last one is what lets a terminating pod drain
in-flight requests instead of vanishing mid-deploy.

**Q21 — How does kube-proxy actually route?**
`iptables` mode (default) writes netfilter DNAT rules and picks a backend with the `statistic random
probability` module — random per connection, not round-robin, which is why Task 1's eight curls were
unevenly distributed. `IPVS` mode uses kernel hash tables for O(1) lookup at 10,000+ services plus
real algorithms (least-connection, weighted round-robin). `nftables` mode is the newer default track.

**Q22 — Why can you curl a ClusterIP but not ping it?**
It is a virtual IP that exists only as DNAT rules matching TCP/UDP destined for a **service port**.
ICMP has no ports, so no rule matches and nothing answers. A ClusterIP not responding to ping is
normal and is not evidence of a problem.

---

## Cleanup

```bash
pgrep -fl "minikube tunnel" || echo "no minikube tunnel running"
kubectl delete namespace hw11 hw11-other
kubectl get ns
kubectl get svc,endpointslices --all-namespaces | grep -E 'hw11' || echo "no hw11 resources remain"
```

```text
no minikube tunnel running

namespace "hw11" deleted
namespace "hw11-other" deleted

NAME              STATUS   AGE
default           Active   18m
hw10              Active   15m
hw12              Active   14m
ingress-nginx     Active   15m
kube-node-lease   Active   18m
kube-public       Active   18m
kube-system       Active   18m

no hw11 resources remain
```

Both namespaces are gone and no Service or EndpointSlice from this homework remains anywhere in the
cluster. Deleting the namespaces removes every Service, Deployment, StatefulSet, Pod, ConfigMap and
EndpointSlice created here in one operation — that is the value of scoping a lab to its own
namespace instead of working in `default`.

The `hw10`, `hw12` and `ingress-nginx` namespaces in that listing belong to the other homework sets
running on the same shared cluster; they are not part of this one and were deliberately left alone.

No cluster-scoped object was ever created by this homework, so nothing else needs removing.
`minikube tunnel` was never started — it needs `sudo`, and this shell has no passwordless sudo, so
forcing a password prompt on a shared cluster was not acceptable. That is why Task 3 records
`<pending>` rather than an external IP. The cluster itself is left running and untouched:
`minikube delete`, `minikube stop` and `minikube start` were never run.
