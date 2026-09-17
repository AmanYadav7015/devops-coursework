# Homework 10 — Core Objects, Pod Lifecycle & Deployment Strategies

## Provenance

The course's official homework document covers **sessions 2-8 only** and contains nothing for the
Kubernetes sessions. The six tasks below were derived from the material actually taught in
`session10-k8s-core-objects` (the `k8s-core-objects/`, `pod-lifecycle/` and the four strategy folders
`01-rolling-update`, `02-blue-green`, `03-canary`, `04-recreate`) and are written in the same style as
the official homework.

Every command in this document was actually run against a live cluster and every `text` block is the
real output. Nothing here is invented. The only edit made to any captured output is one clearly
marked elision of repetitive `rollout status` progress lines, plus the removal of the
`Warning: v1 Endpoints is deprecated in v1.33+` line from `kubectl get endpoints` (shown once, in
Task 4, so you know it is there).

---

## Environment

```bash
kubectl version
kubectl get nodes -o wide
kubectl get storageclass
```

```text
Client Version: v1.37.0
Kustomize Version: v5.8.1
Server Version: v1.37.0

NAME       STATUS   ROLES           AGE    VERSION   INTERNAL-IP    EXTERNAL-IP   OS-IMAGE                         KERNEL-VERSION             CONTAINER-RUNTIME
minikube   Ready    control-plane   3m1s   v1.37.0   192.168.49.2   <none>        Debian GNU/Linux 12 (bookworm)   6.12.76-linuxkit (arm64)   containerd://2.3.4

NAME                 PROVISIONER                RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION   AGE
standard (default)   k8s.io/minikube-hostpath   Delete          Immediate           false                  2m58s
```

Single-node minikube on the docker driver, containerd runtime, arm64. All work in this homework is
done inside a dedicated namespace:

```bash
kubectl create namespace hw10
```

```text
namespace/hw10 created
```

Every command below passes `-n hw10`.

### Platform note you must read before trusting any "open it in your browser" instruction

On this machine the node IP `192.168.49.2` is **not reachable from macOS**. minikube's docker driver
runs the node as a container inside the Docker Desktop VM, and that VM's bridge network is not routed
to the host. Every NodePort in this homework is therefore defined and correct, but it cannot be
curled from the Mac:

```bash
ping -c 2 -W 2000 192.168.49.2 | tail -3
curl -s -m 5 -o /dev/null -w 'http_code=%{http_code}\n' http://192.168.49.2:30100/
echo "curl exit=$?"
```

```text
--- 192.168.49.2 ping statistics ---
2 packets transmitted, 0 packets received, 100.0% packet loss

http_code=000
curl exit=28
```

`curl` exit 28 is "operation timed out". The NodePort itself is fine — it works from inside the node,
and `kubectl port-forward` works from the Mac:

```bash
echo "--- NodePort works from inside the node ---"
minikube ssh -- "curl -s http://192.168.49.2:30100/"
echo "--- port-forward from macOS ---"
kubectl port-forward -n hw10 svc/app-rolling 18080:80 &
curl -s http://127.0.0.1:18080/
```

```text
--- NodePort works from inside the node ---
APP VERSION v1

--- port-forward from macOS ---
APP VERSION v1
```

So throughout this homework, traffic is generated **from inside the cluster** using a small busybox
client pod (`06-strategies/client.yaml`). That is the honest way to test on this setup.

### Files in this folder

```text
01-core-objects/            01-pod.yaml 02-replicaset.yaml 03-deployment.yaml
                            04-daemonset.yaml 05-statefulset.yaml
02-ownership-selfhealing/   owner-demo.yaml
03-pod-lifecycle/           01-running.yaml 02-pending-resources.yaml 03-pending-nodeselector.yaml
                            04-succeeded.yaml 05-failed.yaml 06-crashloopbackoff.yaml
                            07-imagepullbackoff.yaml
04-probes/                  01-readiness.yaml 02-liveness.yaml 03-startup.yaml
05-init-multicontainer/     01-init-gate.yaml 02-gate-backend.yaml 03-multi-container.yaml
06-strategies/              client.yaml  sample-availability.sh
                            01-rolling-update/  02-blue-green/  03-canary/  04-recreate/
```

---

# Task 1 — The five core objects

## The ladder

Each object below wraps the one above it and adds exactly one capability. That is the whole mental
model:

```text
Pod          one or more containers that share a network namespace and volumes
 +-- ReplicaSet    keeps N identical Pods alive
      +-- Deployment    versions a ReplicaSet, so it can roll forward and roll back
DaemonSet     one Pod per node, no replica count at all
StatefulSet   ordered, stable identity + a private PersistentVolume per Pod
```

## Apply all five

```bash
kubectl apply -f 01-core-objects/ -n hw10
```

```text
pod/core-pod created
replicaset.apps/core-rs created
deployment.apps/core-deploy created
daemonset.apps/core-agent created
service/core-db created
statefulset.apps/core-db created
```

```bash
kubectl get all -n hw10
```

```text
NAME                              READY   STATUS    RESTARTS   AGE
pod/core-agent-lr96c              1/1     Running   0          41s
pod/core-db-0                     1/1     Running   0          41s
pod/core-db-1                     1/1     Running   0          41s
pod/core-deploy-dcc7c457b-7plmz   1/1     Running   0          41s
pod/core-deploy-dcc7c457b-v8llm   1/1     Running   0          41s
pod/core-pod                      1/1     Running   0          41s
pod/core-rs-997gh                 1/1     Running   0          41s
pod/core-rs-qb6qt                 1/1     Running   0          41s

NAME              TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE
service/core-db   ClusterIP   None         <none>        80/TCP    41s

NAME                        DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR   AGE
daemonset.apps/core-agent   1         1         1       1            1           <none>          41s

NAME                          READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/core-deploy   2/2     2            2           41s

NAME                                    DESIRED   CURRENT   READY   AGE
replicaset.apps/core-deploy-dcc7c457b   2         2         2       41s
replicaset.apps/core-rs                 2         2         2       41s

NAME                       READY   AGE
statefulset.apps/core-db   2/2     41s
```

Note the shape of the pod names already tells you which controller made them: `core-pod` (hand
written), `core-rs-997gh` (ReplicaSet: one random suffix), `core-deploy-dcc7c457b-7plmz` (Deployment:
a pod-template-hash **plus** a random suffix), `core-db-0` / `core-db-1` (StatefulSet: an ordinal).

## 1.1 Pod — what it is for, and what the level below cannot do

A Pod is the smallest deployable unit. It is a shared network namespace (one IP, one localhost) and a
shared set of volumes wrapped around one or more containers.

There is no level below a Pod, so the comparison runs the other way: **a bare container cannot have a
sidecar that shares its localhost and its filesystem**. That is proven in Task 5.

What a Pod cannot do: survive. Delete it and it is gone forever (proven in Task 2).

## 1.2 ReplicaSet — one thing a Pod cannot do

**Self-healing to a desired count.** A ReplicaSet runs a reconciliation loop: "I want 2 pods matching
this selector; I currently see N; create or delete the difference." A Pod has no such loop. Proven in
Task 2.

## 1.3 Deployment — one thing a ReplicaSet cannot do

**Change the pod template without downtime, and undo it.** A ReplicaSet has no `strategy` field and no
revision history. If you edit a ReplicaSet's template, the existing pods are *not* replaced — the new
template only applies to pods created from then on. A Deployment owns a *series* of ReplicaSets and
orchestrates traffic between them.

Look back at the `kubectl get all` output above: `core-deploy` has a Deployment **and** a ReplicaSet
called `core-deploy-dcc7c457b`, which nobody wrote a manifest for. That `dcc7c457b` is the
pod-template-hash. A second template produces a second ReplicaSet — that is
literally how a rolling update and a rollback work (Task 6).

## 1.4 DaemonSet — one thing a Deployment cannot do

**Guarantee exactly one pod per node.** A DaemonSet has no `replicas:` field at all; its replica count
is "however many nodes there are". A Deployment with `replicas: 3` could happily put all three pods on
one node.

```bash
kubectl get nodes --no-headers | wc -l
kubectl get pods -n hw10 -l app=core-agent -o custom-columns=POD:.metadata.name,NODE:.spec.nodeName
kubectl describe ds core-agent -n hw10 | head -12
```

```text
       1

POD                NODE
core-agent-lr96c   minikube

Name:           core-agent
Namespace:      hw10
Selector:       app=core-agent
Node-Selector:  <none>
Labels:         app=core-agent
Annotations:    deprecated.daemonset.template.generation: 1
Desired Number of Nodes Scheduled: 1
Current Number of Nodes Scheduled: 1
Number of Nodes Scheduled with Up-to-date Pods: 1
Number of Nodes Scheduled with Available Pods: 1
Number of Nodes Misscheduled: 0
Pods Status:  1 Running / 0 Waiting / 0 Succeeded / 0 Failed
```

One node in the cluster, `Desired Number of Nodes Scheduled: 1`, `Misscheduled: 0`, and exactly one
pod, on `minikube`. On a 5-node cluster the same manifest would produce 5 pods with zero edits — that
is the property a Deployment cannot express. This is why log collectors, CNI agents and node exporters
are DaemonSets.

## 1.5 StatefulSet — one thing a DaemonSet (and a Deployment) cannot do

**Stable ordinal identity plus a private PersistentVolume that follows the pod name.**

```bash
kubectl get pods -n hw10 -l app=core-db -o custom-columns=POD:.metadata.name,NODE:.spec.nodeName,IP:.status.podIP
kubectl get pvc -n hw10
```

```text
POD         NODE       IP
core-db-0   minikube   10.244.0.16
core-db-1   minikube   10.244.0.17

NAME             STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
data-core-db-0   Bound    pvc-99345ab1-2260-448f-a199-96cb30c6bfcb   100Mi      RWO            standard       <unset>                 44s
data-core-db-1   Bound    pvc-6533f9de-e991-492c-942d-9dbe5fa8b147   100Mi      RWO            standard       <unset>                 44s
```

The names are ordinals (`-0`, `-1`), not random suffixes, and the `volumeClaimTemplates` block created
one PVC **per pod**, named `<template>-<pod>`.

### Proving the identity is actually stable

Write a file to `core-db-0`'s volume, record its UID, delete the pod, and look again:

```bash
kubectl exec -n hw10 core-db-0 -- sh -c 'echo "written by core-db-0 at $(date -u +%H:%M:%S)" > /usr/share/nginx/html/data.txt'
kubectl get pod core-db-0 -n hw10 -o jsonpath='{.metadata.name}{"  uid="}{.metadata.uid}{"\n"}'
kubectl delete pod core-db-0 -n hw10
```

```text
written by core-db-0 at 16:59:13
core-db-0  uid=a30d3d50-952f-4421-a039-c1308ac4602b
pod "core-db-0" deleted from hw10 namespace
```

```bash
kubectl get pod core-db-0 -n hw10 -o jsonpath='{.metadata.name}{"  uid="}{.metadata.uid}{"\n"}'
kubectl exec -n hw10 core-db-0 -- cat /usr/share/nginx/html/data.txt
kubectl get pvc data-core-db-0 -n hw10
```

```text
core-db-0  uid=6421ad0f-50c5-436f-8d51-b4775bd38497
written by core-db-0 at 16:59:13
NAME             STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
data-core-db-0   Bound    pvc-99345ab1-2260-448f-a199-96cb30c6bfcb   100Mi      RWO            standard       <unset>                 60s
```

Read that carefully. **Same name, different UID** — it is genuinely a brand new pod object. But it
reattached to `pvc-99345ab1-...`, the exact same PersistentVolume, and the file written by the dead pod
is still there. A Deployment cannot do this: its replacement pod would get a new random name and,
with a shared PVC, would fight the other replicas over a ReadWriteOnce volume.

---

# Task 2 — Ownership and self-healing

## The deployment under test

```bash
kubectl apply -f 02-ownership-selfhealing/owner-demo.yaml
kubectl rollout status deploy/owner-demo -n hw10
```

```text
deployment.apps/owner-demo created
Waiting for deployment "owner-demo" rollout to finish: 0 of 2 updated replicas are available...
Waiting for deployment "owner-demo" rollout to finish: 1 of 2 updated replicas are available...
deployment "owner-demo" successfully rolled out
```

## 2.1 Delete an RS-owned pod and watch it come back

```bash
kubectl get pods -n hw10 -l app=owner-demo
kubectl delete pod owner-demo-6fc5dbc4cb-79mnl -n hw10
```

```text
NAME                          READY   STATUS    RESTARTS   AGE
owner-demo-6fc5dbc4cb-79mnl   1/1     Running   0          7s
owner-demo-6fc5dbc4cb-kmst7   1/1     Running   0          7s

pod "owner-demo-6fc5dbc4cb-79mnl" deleted from hw10 namespace
```

```bash
kubectl get pods -n hw10 -l app=owner-demo
```

```text
NAME                          READY   STATUS    RESTARTS   AGE
owner-demo-6fc5dbc4cb-kmst7   1/1     Running   0          16s
owner-demo-6fc5dbc4cb-wbghf   1/1     Running   0          9s
```

`...-79mnl` is gone for good. `...-wbghf` is a **new pod**, 9 seconds old while its sibling is 16
seconds old. The count is back to 2. Nothing restarted — a replacement was created.

The ReplicaSet's own event log records the decision:

```bash
kubectl get events -n hw10 --field-selector involvedObject.kind=ReplicaSet --sort-by=.lastTimestamp \
  -o custom-columns=TIME:.lastTimestamp,REASON:.reason,OBJECT:.involvedObject.name,MESSAGE:.message
```

```text
2026-09-17T16:59:41Z   SuccessfulCreate   owner-demo-6fc5dbc4cb   Created pod: owner-demo-6fc5dbc4cb-kmst7
2026-09-17T16:59:41Z   SuccessfulCreate   owner-demo-6fc5dbc4cb   Created pod: owner-demo-6fc5dbc4cb-79mnl
2026-09-17T16:59:48Z   SuccessfulCreate   owner-demo-6fc5dbc4cb   Created pod: owner-demo-6fc5dbc4cb-wbghf
```

Two creates at 16:59:41 (the initial rollout), then a third at 16:59:48 — seven seconds after the
delete. The controller noticed `observed=1, desired=2` and closed the gap.

## 2.2 The contrast: a bare Pod has no owner and no one to resurrect it

```bash
kubectl get pod core-pod -n hw10 -o jsonpath='{.metadata.name}{" ownerReferences="}{.metadata.ownerReferences}{"\n"}'
kubectl delete pod core-pod -n hw10
kubectl get pod core-pod -n hw10
```

```text
core-pod ownerReferences=
pod "core-pod" deleted from hw10 namespace
Error from server (NotFound): pods "core-pod" not found
```

`ownerReferences` is empty, so nothing is watching it, so it stays dead. This is the single most
important reason you never run bare Pods in production.

## 2.3 The ownerReferences chain: Pod -> ReplicaSet -> Deployment

```bash
kubectl get pod owner-demo-6fc5dbc4cb-wbghf -n hw10 \
  -o jsonpath='{.metadata.name}{" owned by "}{.metadata.ownerReferences[0].kind}{"/"}{.metadata.ownerReferences[0].name}{" controller="}{.metadata.ownerReferences[0].controller}{"\n"}'

kubectl get rs owner-demo-6fc5dbc4cb -n hw10 \
  -o jsonpath='{.metadata.name}{" owned by "}{.metadata.ownerReferences[0].kind}{"/"}{.metadata.ownerReferences[0].name}{" controller="}{.metadata.ownerReferences[0].controller}{"\n"}'

kubectl get deploy owner-demo -n hw10 -o jsonpath='{.metadata.name}{" owners: "}{.metadata.ownerReferences}{"\n"}'
```

```text
owner-demo-6fc5dbc4cb-wbghf owned by ReplicaSet/owner-demo-6fc5dbc4cb controller=true
owner-demo-6fc5dbc4cb owned by Deployment/owner-demo controller=true
owner-demo owners: 
```

The chain terminates: the Deployment is the root, owned by nobody. In full:

```bash
kubectl get pod owner-demo-6fc5dbc4cb-wbghf -n hw10 -o yaml | sed -n '/ownerReferences/,/resourceVersion/p'
```

```text
  ownerReferences:
  - apiVersion: apps/v1
    blockOwnerDeletion: true
    controller: true
    kind: ReplicaSet
    name: owner-demo-6fc5dbc4cb
    uid: add803cf-e93a-449d-941b-83ea27feefa8
  resourceVersion: "1245"
```

Two fields worth knowing:

* `controller: true` — this is the *one* owner that actively reconciles the object. An object can have
  several ownerReferences but only one controller.
* `blockOwnerDeletion: true` — the garbage collector will not finish deleting the ReplicaSet until this
  pod is gone. This is the mechanism behind cascading delete: `kubectl delete deploy owner-demo`
  deletes the Deployment, and the garbage collector then reaps the ReplicaSet and its pods by walking
  these references. Nothing "tells" the pods to die; they are collected because their owner vanished.

---

# Task 3 — Pod lifecycle

## Phase is not the same thing as STATUS

Before any of the demos, this is the point the whole task turns on. `kubectl get pod` prints a
human-friendly STATUS column that **merges** the pod phase with the container state. The API only has
five phases: `Pending`, `Running`, `Succeeded`, `Failed`, `Unknown`. `CrashLoopBackOff`,
`ImagePullBackOff`, `Completed`, `Error` and `ContainerCreating` are *not* phases.

All seven demo pods, applied at once:

```bash
kubectl apply -f 03-pod-lifecycle/ -n hw10
```

```text
pod/state-running created
pod/state-pending-cpu created
pod/state-pending-selector created
pod/state-succeeded created
pod/state-failed created
pod/state-imagepull created
Error from server (BadRequest): error when creating "06-crashloopbackoff.yaml": Pod in version "v1" cannot be handled as a Pod: json: cannot unmarshal object into Go struct field Container.spec.containers.command of type string
```

That error is a genuine YAML trap and worth keeping in the write-up. The command was originally
written as a bare scalar containing `app crashed: cannot reach database` — and in YAML, a `: ` inside
an unquoted scalar turns the whole thing into a **mapping**, so the API server received an object
where it expected a string. Wrapping the command in single quotes fixes it:

```yaml
      command:
        - sh
        - -c
        - 'echo "app booting"; sleep 3; echo "app crashed - cannot reach database"; exit 1'
```

```bash
kubectl apply -f 03-pod-lifecycle/06-crashloopbackoff.yaml
```

```text
pod/state-crashloop created
```

A few minutes later:

```bash
kubectl get pods -n hw10 -l demo=lifecycle
```

```text
NAME                     READY   STATUS             RESTARTS      AGE
state-crashloop          0/1     CrashLoopBackOff   4 (77s ago)   3m8s
state-failed             0/1     Error              0             3m17s
state-imagepull          0/1     ErrImagePull       0             3m17s
state-pending-cpu        0/1     Pending            0             3m17s
state-pending-selector   0/1     Pending            0             3m17s
state-running            1/1     Running            0             3m17s
state-succeeded          0/1     Completed          0             3m17s
```

Now the same pods, asking the API for the real phase:

```bash
kubectl get pods -n hw10 -l demo=lifecycle \
  -o 'custom-columns=NAME:.metadata.name,PHASE:.status.phase,WAITING_REASON:.status.containerStatuses[0].state.waiting.reason,RESTARTS:.status.containerStatuses[0].restartCount'
```

```text
NAME                     PHASE       WAITING_REASON     RESTARTS
state-crashloop          Running     CrashLoopBackOff   4
state-failed             Failed      <none>             0
state-imagepull          Pending     ErrImagePull       0
state-pending-cpu        Pending     <none>             <none>
state-pending-selector   Pending     <none>             <none>
state-running            Running     <none>             0
state-succeeded          Succeeded   <none>             0
```

Three things to take from that table:

* A CrashLoopBackOff pod is in phase **Running**. The *pod* is running; its *container* is in a
  Waiting state with reason CrashLoopBackOff.
* ImagePullBackOff is phase **Pending** — the pod is scheduled but no container has started.
* The two `state-pending-*` pods have no `containerStatuses` at all (`<none>`), because they were never
  admitted to a node. That is what distinguishes "not scheduled" from "scheduled but not started".

## 3.1 Running

`03-pod-lifecycle/01-running.yaml` — plain nginx.

```text
state-running            1/1     Running            0             3m17s
```

`1/1` means 1 of 1 containers passed its readiness check. Phase `Running`, restarts 0.

## 3.2 Pending — forced two different ways

### (a) An impossible resource request

```yaml
spec:
  containers:
    - name: greedy
      image: nginx:alpine
      resources:
        requests:
          cpu: "64"
          memory: "256Gi"
```

```bash
kubectl describe pod state-pending-cpu -n hw10 | sed -n '/^Events:/,$p'
```

```text
Events:
  Type     Reason            Age                    From               Message
  ----     ------            ----                   ----               -------
  Warning  FailedScheduling  2m23s (x4 over 3m22s)  default-scheduler  0/1 nodes are available: 1 Insufficient cpu, 1 Insufficient memory. preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.
```

The scheduler's filter phase rejected the only node on two predicates at once, then its preemption
phase concluded that evicting lower-priority pods would not help either (64 CPUs do not exist on this
node at any priority). `x4 over 3m22s` — the scheduler keeps retrying with backoff, which is why this
pod will sit here forever rather than failing.

### (b) A nodeSelector nothing matches

```yaml
spec:
  nodeSelector:
    disktype: nvme-that-does-not-exist
```

```bash
kubectl describe pod state-pending-selector -n hw10 | sed -n '/^Events:/,$p'
```

```text
Events:
  Type     Reason            Age    From               Message
  ----     ------            ----   ----               -------
  Warning  FailedScheduling  3m22s  default-scheduler  0/1 nodes are available: 1 node(s) didn't match Pod's node affinity/selector. preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.
```

Same phase, completely different cause, and the event message tells you which. This is why
`describe` is the first command for a Pending pod — `get pod` only ever says "Pending".

## 3.3 Succeeded

`restartPolicy: Never` plus a command that exits 0.

```bash
kubectl logs state-succeeded -n hw10
kubectl get pod state-succeeded -n hw10 -o jsonpath='{"phase="}{.status.phase}{" exitCode="}{.status.containerStatuses[0].state.terminated.exitCode}{" reason="}{.status.containerStatuses[0].state.terminated.reason}{"\n"}'
```

```text
batch job started
batch job finished cleanly
phase=Succeeded exitCode=0 reason=Completed
```

STATUS column says `Completed`; the phase is `Succeeded`; the container's terminated reason is
`Completed` with exit code 0. This is a terminal state — the kubelet will not restart it.

## 3.4 Failed

Identical pod, `exit 1` instead of `exit 0`.

```bash
kubectl logs state-failed -n hw10
kubectl get pod state-failed -n hw10 -o jsonpath='{"phase="}{.status.phase}{" exitCode="}{.status.containerStatuses[0].state.terminated.exitCode}{" reason="}{.status.containerStatuses[0].state.terminated.reason}{"\n"}'
```

```text
batch job started
batch job hit a fatal error
phase=Failed exitCode=1 reason=Error
```

The only difference between Succeeded and Failed is the exit code. `restartPolicy: Never` is what
makes it terminal — the next demo changes exactly that one field.

## 3.5 CrashLoopBackOff — the restart count climbing and the backoff event

Same crashing command, but `restartPolicy: Always` (the default). Sampled at four different moments:

```bash
kubectl get pod state-crashloop -n hw10
```

```text
NAME              READY   STATUS             RESTARTS      AGE
state-crashloop   0/1     Error              3 (30s ago)   54s
```

```text
NAME              READY   STATUS             RESTARTS      AGE
state-crashloop   0/1     CrashLoopBackOff   4 (71s ago)   3m2s
```

Then a live watch for 100 seconds, which catches the container flipping from a fresh crash into the
backoff wait:

```bash
kubectl get pod state-crashloop -n hw10 -w --request-timeout=100s
```

```text
NAME              READY   STATUS   RESTARTS       AGE
state-crashloop   0/1     Error    5 (103s ago)   3m34s
state-crashloop   0/1     CrashLoopBackOff   5 (80s ago)    4m39s
```

And one last sample several minutes later:

```bash
kubectl get pod state-crashloop -n hw10
```

```text
NAME              READY   STATUS             RESTARTS       AGE
state-crashloop   0/1     CrashLoopBackOff   6 (2m2s ago)   8m5s
```

RESTARTS climbs 3 -> 4 -> 5 -> 6, and look at the *gaps*: restart 3 happened 30s into the pod's life,
restart 4 at ~1m50s, restart 5 at ~2m40s, restart 6 at ~6m. The delay is doubling — 10s, 20s, 40s,
80s, 160s, capped at 5 minutes. That exponential backoff is the "BackOff" in CrashLoopBackOff, and it
is why a broken pod that has been crashing for an hour takes up to 5 minutes to retry after you push
a fix.

Also notice the STATUS column flips between `Error` (it just crashed) and `CrashLoopBackOff` (it is
waiting out the delay). Same pod, same problem, two different strings.

```bash
kubectl describe pod state-crashloop -n hw10
```

```text
    State:          Terminated
      Reason:       Error
      Exit Code:    1
      Started:      Thu, 17 Sep 2026 22:34:02 +0530
      Finished:     Thu, 17 Sep 2026 22:34:05 +0530
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
      Started:      Thu, 17 Sep 2026 22:32:34 +0530
      Finished:     Thu, 17 Sep 2026 22:32:37 +0530
    Ready:          False
    Restart Count:  5
...
Events:
  Type     Reason     Age                 From               Message
  ----     ------     ----                ----               -------
  Normal   Scheduled  3m20s               default-scheduler  Successfully assigned hw10/state-crashloop to minikube
  Normal   Pulled     4s (x6 over 3m19s)  kubelet            spec.containers{crasher}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Normal   Created    4s (x6 over 3m19s)  kubelet            spec.containers{crasher}: Container created
  Normal   Started    4s (x6 over 3m19s)  kubelet            spec.containers{crasher}: Container started
  Warning  BackOff    0s (x6 over 3m12s)  kubelet            spec.containers{crasher}: Back-off restarting failed container crasher in pod state-crashloop_hw10(64601ee1-b910-4cc4-a7ea-dbef00f3f0c7)
```

`Warning BackOff ... Back-off restarting failed container` is the event that names the condition.
`State` and `Last State` are both `Terminated / Error / Exit Code 1`, three seconds apart each time —
the container is starting fine and then dying, which is exactly what `Created x6`, `Started x6`
confirms. The image pull is *not* the problem here, which is the fastest way to tell CrashLoopBackOff
apart from ImagePullBackOff.

Debugging a crash loop, the container you want logs from is the dead one:

```bash
kubectl logs state-crashloop -n hw10 --previous
```

## 3.6 ImagePullBackOff

```yaml
image: nginx:this-tag-does-not-exist-999
```

```bash
kubectl describe pod state-imagepull -n hw10 | sed -n '/^Events:/,$p'
```

```text
Events:
  Type     Reason     Age                  From               Message
  ----     ------     ----                 ----               -------
  Normal   Scheduled  3m31s                default-scheduler  Successfully assigned hw10/state-imagepull to minikube
  Normal   Pulling    32s (x5 over 3m31s)  kubelet            spec.containers{broken}: Pulling image "nginx:this-tag-does-not-exist-999"
  Warning  Failed     30s (x5 over 3m29s)  kubelet            spec.containers{broken}: Failed to pull image "nginx:this-tag-does-not-exist-999": rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/library/nginx:this-tag-does-not-exist-999": failed to resolve reference "docker.io/library/nginx:this-tag-does-not-exist-999": docker.io/library/nginx:this-tag-does-not-exist-999: not found
  Warning  Failed     30s (x5 over 3m29s)  kubelet            spec.containers{broken}: Error: ErrImagePull
  Normal   BackOff    5s (x12 over 3m28s)  kubelet            spec.containers{broken}: Back-off pulling image "nginx:this-tag-does-not-exist-999"
  Warning  Failed     5s (x12 over 3m28s)  kubelet            spec.containers{broken}: Error: ImagePullBackOff
```

The pod **was** scheduled (`Successfully assigned ... to minikube`) — the failure is purely at the
container-runtime layer. `ErrImagePull` is the first failure; `ImagePullBackOff` is the retry-with-
backoff state that follows. Note the two different reasons in the same event stream; the STATUS column
alternates between them in the same way CrashLoopBackOff alternates with Error.

The containerd error text is worth reading in full: `failed to resolve reference ... not found` means a
404 from the registry (bad tag/name). A private registry with missing credentials produces a different
message (`401 Unauthorized` / `pull access denied`) — same STATUS, different root cause, and only
`describe` tells them apart.

---

# Task 4 — Probes

Three probes, three completely different jobs:

| Probe | Question it answers | What happens on failure |
| :--- | :--- | :--- |
| `readinessProbe` | Should this pod receive traffic? | Pod removed from Service endpoints. **Container is not restarted.** |
| `livenessProbe` | Is this container wedged? | Container is **killed and restarted**. |
| `startupProbe` | Has this slow app finished booting? | While it is failing, liveness/readiness are **suspended**. On final failure, container is killed. |

## 4.1 A failing readiness probe removes the pod from the Service endpoints

`04-probes/01-readiness.yaml` runs 2 nginx replicas behind a ClusterIP Service. The readiness probe
does an HTTP GET on `/ready.html`, and a `postStart` hook creates that file. So "readiness" is a file
I can delete by hand.

```yaml
          lifecycle:
            postStart:
              exec:
                command:
                  - sh
                  - -c
                  - 'echo ok > /usr/share/nginx/html/ready.html'
          readinessProbe:
            httpGet:
              path: /ready.html
              port: 80
            initialDelaySeconds: 3
            periodSeconds: 3
            failureThreshold: 1
```

### Before

```bash
kubectl get pods -n hw10 -l app=probe-readiness
kubectl get endpoints probe-readiness -n hw10
kubectl get endpointslices -n hw10 -l kubernetes.io/service-name=probe-readiness \
  -o 'custom-columns=SLICE:.metadata.name,ADDRESSES:.endpoints[*].addresses,READY:.endpoints[*].conditions.ready'
```

```text
NAME                               READY   STATUS    RESTARTS   AGE
probe-readiness-5587cf657c-6snxg   1/1     Running   0          6s
probe-readiness-5587cf657c-9zhvd   1/1     Running   0          6s

Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME              ENDPOINTS                       AGE
probe-readiness   10.244.0.44:80,10.244.0.45:80   6s

SLICE                   ADDRESSES                     READY
probe-readiness-whqqm   [10.244.0.45],[10.244.0.44]   true,true
```

Two pods, two endpoints, both `ready: true`.

### Break readiness on exactly one pod

```bash
kubectl exec -n hw10 probe-readiness-5587cf657c-6snxg -- rm /usr/share/nginx/html/ready.html
```

### After

```bash
kubectl get pods -n hw10 -l app=probe-readiness
kubectl get endpoints probe-readiness -n hw10
kubectl get endpointslices -n hw10 -l kubernetes.io/service-name=probe-readiness \
  -o 'custom-columns=SLICE:.metadata.name,ADDRESSES:.endpoints[*].addresses,READY:.endpoints[*].conditions.ready'
```

```text
NAME                               READY   STATUS    RESTARTS   AGE
probe-readiness-5587cf657c-6snxg   0/1     Running   0          22s
probe-readiness-5587cf657c-9zhvd   1/1     Running   0          22s

NAME              ENDPOINTS        AGE
probe-readiness   10.244.0.44:80   22s

SLICE                   ADDRESSES                     READY
probe-readiness-whqqm   [10.244.0.45],[10.244.0.44]   false,true
```

This is the proof, and there are three separate things in it:

1. The broken pod is `0/1` but **STATUS is still `Running` and RESTARTS is still `0`**. Readiness does
   not kill anything.
2. `kubectl get endpoints` dropped from two addresses to one. `10.244.0.45` — the broken pod's IP —
   is no longer a routable target.
3. The EndpointSlice tells the fuller story: the address is still *listed*, with
   `conditions.ready: false`. kube-proxy only programs `ready: true` addresses into its rules. (This
   matters for `publishNotReadyAddresses` and headless-service DNS, where not-ready addresses are
   still published.)

The event that explains it:

```bash
kubectl describe pod probe-readiness-5587cf657c-6snxg -n hw10 | sed -n '/^Events:/,$p'
```

```text
Events:
  Type     Reason     Age              From               Message
  ----     ------     ----             ----               -------
  Normal   Scheduled  22s              default-scheduler  Successfully assigned hw10/probe-readiness-5587cf657c-6snxg to minikube
  Normal   Pulled     21s              kubelet            spec.containers{web}: Container image "nginx:alpine" already present on machine and can be accessed by the pod
  Normal   Created    21s              kubelet            spec.containers{web}: Container created
  Normal   Started    21s              kubelet            spec.containers{web}: Container started
  Warning  Unhealthy  3s (x3 over 6s)  kubelet            spec.containers{web}: Readiness probe failed: HTTP probe failed with statuscode: 404
```

`Warning Unhealthy ... Readiness probe failed: HTTP probe failed with statuscode: 404`. No `Killing`
event — compare with liveness below.

### And it heals when the probe passes again

```bash
kubectl exec -n hw10 probe-readiness-5587cf657c-6snxg -- sh -c 'echo ok > /usr/share/nginx/html/ready.html'
kubectl get pods -n hw10 -l app=probe-readiness
kubectl get endpoints probe-readiness -n hw10
```

```text
NAME                               READY   STATUS    RESTARTS   AGE
probe-readiness-5587cf657c-6snxg   1/1     Running   0          33s
probe-readiness-5587cf657c-9zhvd   1/1     Running   0          33s

NAME              ENDPOINTS                       AGE
probe-readiness   10.244.0.44:80,10.244.0.45:80   33s
```

Still `RESTARTS 0` at 33s old. The pod was quarantined and released without ever being restarted —
that is the entire point of readiness.

## 4.2 A failing liveness probe restarts the container

`04-probes/02-liveness.yaml` — the container touches `/tmp/healthy`, sleeps 25 seconds, deletes the
file, then sleeps 600. The liveness probe is `test -f /tmp/healthy`, so after ~25s it starts failing.

```bash
kubectl get pod probe-liveness -n hw10
```

```text
NAME             READY   STATUS    RESTARTS     AGE
probe-liveness   1/1     Running   2 (5s ago)   2m15s
```

RESTARTS is **2** at 2m15s — and this will keep climbing, because every restart replays the same
script and deletes the file again 25 seconds later.

```bash
kubectl describe pod probe-liveness -n hw10 | sed -n '/^Events:/,$p'
```

```text
Events:
  Type     Reason     Age                 From               Message
  ----     ------     ----                ----               -------
  Normal   Scheduled  2m15s               default-scheduler  Successfully assigned hw10/probe-liveness to minikube
  Warning  Unhealthy  35s (x4 over 104s)  kubelet            spec.containers{app}: Liveness probe failed:
  Normal   Killing    35s (x2 over 99s)   kubelet            spec.containers{app}: Container app failed liveness probe, will be restarted
  Normal   Pulled     4s (x3 over 2m14s)  kubelet            spec.containers{app}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Normal   Created    4s (x3 over 2m14s)  kubelet            spec.containers{app}: Container created
  Normal   Started    4s (x3 over 2m14s)  kubelet            spec.containers{app}: Container started
```

The two events that prove it, side by side:

* `Warning Unhealthy ... Liveness probe failed:` **x4** — the probe has `failureThreshold: 2`, so four
  failures produced two kills.
* `Normal Killing ... Container app failed liveness probe, will be restarted` **x2** — matching the
  RESTARTS count of 2 exactly.
* `Created x3` / `Started x3` — one original start plus two restarts.

Compare this event list with the readiness one above: readiness produced `Unhealthy` and nothing else;
liveness produced `Unhealthy` **plus `Killing`**. That is the operational difference in one line of
output.

A liveness probe that is too aggressive is one of the classic self-inflicted outages: a slow-but-
healthy app fails the probe, gets killed, restarts slowly, fails again — you have built a crash loop
out of a latency spike. Which is what the startup probe is for.

## 4.3 The startup probe protects a slow boot

`04-probes/03-startup.yaml` — an app that takes 40 seconds to boot, with **both** a startup probe and
a liveness probe on the same condition. The liveness probe alone (`periodSeconds: 5`,
`failureThreshold: 2`) would kill this container after ~10 seconds.

While booting:

```bash
kubectl get pod probe-startup -n hw10
kubectl get pod probe-startup -n hw10 -o jsonpath='{"started="}{.status.containerStatuses[0].started}{" ready="}{.status.containerStatuses[0].ready}{"\n"}'
```

```text
NAME            READY   STATUS    RESTARTS   AGE
probe-startup   0/1     Running   0          36s

started=false ready=false
```

After the boot finishes:

```bash
kubectl get pod probe-startup -n hw10
kubectl get pod probe-startup -n hw10 -o jsonpath='{"started="}{.status.containerStatuses[0].started}{" ready="}{.status.containerStatuses[0].ready}{" restarts="}{.status.containerStatuses[0].restartCount}{"\n"}'
kubectl describe pod probe-startup -n hw10 | sed -n '/^Events:/,$p'
```

```text
NAME            READY   STATUS    RESTARTS   AGE
probe-startup   1/1     Running   0          2m21s

started=true ready=true restarts=0

Events:
  Type     Reason     Age                   From               Message
  ----     ------     ----                  ----               -------
  Normal   Scheduled  2m22s                 default-scheduler  Successfully assigned hw10/probe-startup to minikube
  Normal   Pulled     2m21s                 kubelet            spec.containers{slow-app}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Normal   Created    2m21s                 kubelet            spec.containers{slow-app}: Container created
  Normal   Started    2m21s                 kubelet            spec.containers{slow-app}: Container started
  Warning  Unhealthy  101s (x8 over 2m16s)  kubelet            spec.containers{slow-app}: Startup probe failed:
```

This is the whole argument for startup probes in one output: the probe failed **8 times** during the
boot, and `RESTARTS` is still **0**. There is no `Killing` event anywhere. The identical liveness
probe was held in suspension the entire time and only armed once `started` flipped to `true`. Without
the startup probe this container would have been killed after 10 seconds and would never have booted.

Note also `started=false ready=false` -> `started=true ready=true`. `started` is a distinct field from
`ready`, and it is the startup probe that sets it.

---

# Task 5 — Init containers and multi-container pods

## 5.1 An init container gating startup

Rather than a `sleep`, `05-init-multicontainer/01-init-gate.yaml` uses a real dependency gate: the init
container blocks until a Service named `gate-backend` resolves in DNS.

```yaml
  initContainers:
    - name: wait-for-backend
      image: busybox:1.36
      command:
        - sh
        - -c
        - 'echo "init: waiting for service gate-backend to exist"; until nslookup gate-backend.hw10.svc.cluster.local; do echo "init: gate-backend not resolvable yet"; sleep 3; done; echo "init: gate-backend resolved, releasing the main container"'
```

The Service does not exist yet, so the pod hangs:

```bash
kubectl apply -f 05-init-multicontainer/01-init-gate.yaml
kubectl get pod init-gate -n hw10
kubectl get pod init-gate -n hw10 -o jsonpath='{"phase="}{.status.phase}{" initContainerState="}{.status.initContainerStatuses[0].state}{"\n"}'
kubectl logs init-gate -n hw10 -c wait-for-backend --tail=8
```

```text
NAME        READY   STATUS     RESTARTS   AGE
init-gate   0/1     Init:0/1   0          15s

phase=Pending initContainerState={"running":{"startedAt":"2026-09-17T17:09:16Z"}}

Server:		10.96.0.10
Address:	10.96.0.10:53

** server can't find gate-backend.hw10.svc.cluster.local: NXDOMAIN

** server can't find gate-backend.hw10.svc.cluster.local: NXDOMAIN

init: gate-backend not resolvable yet
```

`STATUS: Init:0/1` — zero of one init containers have completed. The pod **phase is `Pending`**, even
though a container (the init container) is genuinely running. The main `web` container has not been
created at all.

Now create the Service the init container is waiting for:

```bash
kubectl get pod init-gate -n hw10 --no-headers
kubectl apply -f 05-init-multicontainer/02-gate-backend.yaml
kubectl get pod init-gate -n hw10
kubectl logs init-gate -n hw10 -c wait-for-backend --tail=6
```

```text
init-gate   0/1   Init:0/1   0     23s
service/gate-backend created

NAME        READY   STATUS    RESTARTS   AGE
init-gate   1/1     Running   0          27s


Name:	gate-backend.hw10.svc.cluster.local
Address: 10.105.250.29

init: gate-backend resolved, releasing the main container
```

`Init:0/1` at 23s -> `1/1 Running` at 27s. The gate opened the moment the dependency appeared.

The full transition, from `describe`:

```bash
kubectl describe pod init-gate -n hw10
```

```text
Init Containers:
  wait-for-backend:
    ...
    State:          Terminated
      Reason:       Completed
      Exit Code:    0
      Started:      Thu, 17 Sep 2026 22:39:16 +0530
      Finished:     Thu, 17 Sep 2026 22:39:40 +0530
    Ready:          True
    Restart Count:  0

Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  32s   default-scheduler  Successfully assigned hw10/init-gate to minikube
  Normal  Pulled     31s   kubelet            spec.initContainers{wait-for-backend}: Container image "busybox:1.36" already present on machine and can be accessed by the pod
  Normal  Created    31s   kubelet            spec.initContainers{wait-for-backend}: Container created
  Normal  Started    31s   kubelet            spec.initContainers{wait-for-backend}: Container started
  Normal  Pulled     7s    kubelet            spec.containers{web}: Container image "nginx:alpine" already present on machine and can be accessed by the pod
  Normal  Created    7s    kubelet            spec.containers{web}: Container created
  Normal  Started    7s    kubelet            spec.containers{web}: Container started
```

The init container started at age 31s and finished at 22:39:40 — a 24-second run. The `web` container
was only `Created` at age 7s, i.e. **after** the init container terminated with exit code 0. The
ordering is guaranteed, not a race.

Two properties an init container has that a regular container does not:

* It runs to completion **before** any app container starts, and if there are several they run in
  strict sequence.
* If it fails, the kubelet retries it according to the pod's `restartPolicy` and the app containers
  still never start. So an init container is a hard precondition, not a best-effort hint.

## 5.2 Two containers in one pod sharing a volume and localhost

`05-init-multicontainer/03-multi-container.yaml` — `web` (nginx) and `writer` (busybox) with one
`emptyDir` mounted at **different paths in each container**: `/usr/share/nginx/html` in `web`,
`/data` in `writer`.

```bash
kubectl get pod multi-container -n hw10
kubectl get pod multi-container -n hw10 -o jsonpath='{range .spec.containers[*]}{.name}{" -> "}{.image}{"\n"}{end}'
```

```text
NAME              READY   STATUS    RESTARTS   AGE
multi-container   2/2     Running   0          36s

web -> nginx:alpine
writer -> busybox:1.36
```

`2/2` — one pod, two containers.

### Shared volume: write in one container, read in the other

```bash
kubectl exec -n hw10 multi-container -c writer -- cat /data/index.html
kubectl exec -n hw10 multi-container -c web -- cat /usr/share/nginx/html/index.html
```

```text
written by the writer container at 17:09:46
written by the writer container at 17:09:46
```

The `writer` container wrote the file at `/data`; the `web` container reads the identical bytes at
`/usr/share/nginx/html`. One `emptyDir`, two mount paths, same inode.

### Shared localhost: curl across containers

```bash
kubectl exec -n hw10 multi-container -c writer -- wget -qO- http://localhost:80/
```

```text
written by the writer container at 17:09:46
```

The busybox container has no web server in it. `localhost:80` reached nginx **in the other container**,
because both containers share one network namespace. Confirmed two more ways:

```bash
kubectl exec -n hw10 multi-container -c writer -- netstat -tln
kubectl exec -n hw10 multi-container -c writer -- hostname -i
kubectl exec -n hw10 multi-container -c web -- hostname -i
```

```text
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State       
tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN      
tcp        0      0 :::80                   :::*                    LISTEN      

10.244.0.50
10.244.0.50
```

The busybox container's own `netstat` lists port 80 as LISTEN even though it is not the process
listening, and both containers report the same pod IP. This is the sidecar pattern in a nutshell: a
log shipper, a proxy or a config reloader can talk to the app over `localhost` with no service
discovery, no network hop and no TLS, and can read the app's files through a shared volume.

The cost: they live and die together, they are scheduled together on one node, and they scale
together. If the sidecar needs to scale independently, it should be its own Deployment.

---

# Task 6 — Deployment strategies

All four use distinguishable response bodies so the cutover is visible, and all traffic is generated
from the in-cluster busybox client (`06-strategies/client.yaml`) because of the platform note at the
top of this document.

```bash
kubectl apply -f 06-strategies/client.yaml
```

```text
pod/curl-client created
```

## 6.1 Rolling update

`06-strategies/01-rolling-update/` — 4 replicas, `nginx:1.27-alpine` in v1 and `nginx:1.29-alpine` in
v2, a `postStart` hook that writes the version into `index.html`, and a readiness probe so the rollout
actually waits for each new pod.

```yaml
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

`maxUnavailable: 0` is the setting that guarantees capacity never drops. `maxSurge: 1` lets the
Deployment temporarily run a 5th pod so it can add before it removes.

### v1 live

```bash
kubectl apply -f 06-strategies/01-rolling-update/deployment-v1.yaml -f 06-strategies/01-rolling-update/service.yaml
kubectl rollout status deploy/app-rolling -n hw10
kubectl get pods -n hw10 -l app=app-rolling -L version
for i in 1 2 3 4; do kubectl exec -n hw10 curl-client -- wget -qO- http://app-rolling.hw10.svc.cluster.local/; done
```

```text
deployment.apps/app-rolling created
service/app-rolling created
Waiting for deployment "app-rolling" rollout to finish: 0 of 4 updated replicas are available...
Waiting for deployment "app-rolling" rollout to finish: 1 of 4 updated replicas are available...
Waiting for deployment "app-rolling" rollout to finish: 2 of 4 updated replicas are available...
Waiting for deployment "app-rolling" rollout to finish: 3 of 4 updated replicas are available...
deployment "app-rolling" successfully rolled out

NAME                          READY   STATUS    RESTARTS   AGE   VERSION
app-rolling-7bfcbcb87-22z56   1/1     Running   0          11s   v1
app-rolling-7bfcbcb87-vn2h7   1/1     Running   0          11s   v1
app-rolling-7bfcbcb87-wrgd6   1/1     Running   0          11s   v1
app-rolling-7bfcbcb87-z8qpx   1/1     Running   0          11s   v1

APP VERSION v1
APP VERSION v1
APP VERSION v1
APP VERSION v1
```

### Roll to v2, while sampling capacity 20x a second

`06-strategies/sample-availability.sh` reads the Service's ready endpoint count in a tight loop and
timestamps every reading:

```bash
cat 06-strategies/sample-availability.sh
```

```text
#!/bin/sh
SVC="$1"
SECS="$2"
END=$(( $(date +%s) + SECS ))
while [ "$(date +%s)" -lt "$END" ]; do
  R=$(kubectl get endpointslices -n hw10 -l kubernetes.io/service-name="$SVC" \
        -o jsonpath='{.items[*].endpoints[*].conditions.ready}' 2>/dev/null \
        | tr ' ' '\n' | grep -c true)
  printf '%s  ready_endpoints=%s\n' "$(date +%H:%M:%S)" "$R"
done
```

Start it in one terminal, trigger the rollout in another:

```bash
# terminal 1
./06-strategies/sample-availability.sh app-rolling 70 > rolling-availability.txt

# terminal 2
kubectl apply -f 06-strategies/01-rolling-update/deployment-v2.yaml
kubectl rollout status deploy/app-rolling -n hw10
```

```text
deployment.apps/app-rolling configured
Waiting for deployment "app-rolling" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "app-rolling" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "app-rolling" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "app-rolling" rollout to finish: 1 old replicas are pending termination...
deployment "app-rolling" successfully rolled out
```

You can read the strategy directly off that output: 1 updated, 2 updated, 3 updated, then old replicas
pending termination. One at a time, each waiting for the new pod's readiness probe.

The sampler's verdict over 855 samples spanning the whole rollout:

```bash
awk '{print $2}' rolling-availability.txt | sort | uniq -c
```

```text
 855 ready_endpoints=4
```

**Every single sample saw 4 ready endpoints.** The ready capacity never dipped, not even to 3. That is
`maxUnavailable: 0` doing exactly what it promises.

### The end state: two ReplicaSets, one of them parked at zero

```bash
kubectl get rs -n hw10 -l app=app-rolling \
  -o 'custom-columns=NAME:.metadata.name,DESIRED:.spec.replicas,CURRENT:.status.replicas,READY:.status.readyReplicas,IMAGE:.spec.template.spec.containers[0].image'
for i in 1 2 3 4; do kubectl exec -n hw10 curl-client -- wget -qO- http://app-rolling.hw10.svc.cluster.local/; done
```

```text
NAME                     DESIRED   CURRENT   READY    IMAGE
app-rolling-7567bb6d89   4         4         4        nginx:1.29-alpine
app-rolling-7bfcbcb87    0         0         <none>   nginx:1.27-alpine

APP VERSION v2
APP VERSION v2
APP VERSION v2
APP VERSION v2
```

The old ReplicaSet is kept at `0` replicas. It is not garbage — it is the rollback target.

### Rollout history and a real undo

```bash
kubectl rollout history deploy/app-rolling -n hw10
```

```text
deployment.apps/app-rolling 
REVISION  CHANGE-CAUSE
1         v1 initial release
2         v2 image bump to nginx:1.29-alpine
```

The CHANGE-CAUSE column is populated because the manifests carry
`metadata.annotations."kubernetes.io/change-cause"`. Without that annotation this column says `<none>`
and the history is close to useless.

```bash
kubectl rollout undo deploy/app-rolling -n hw10
kubectl rollout status deploy/app-rolling -n hw10
kubectl get pods -n hw10 -l app=app-rolling -L version
kubectl rollout history deploy/app-rolling -n hw10
kubectl get deploy app-rolling -n hw10 -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

```text
Warning: resource deployments/app-rolling was previously managed with 'kubectl apply'. Rolling back will not update the kubectl.kubernetes.io/last-applied-configuration annotation, which may cause unexpected behavior on future 'kubectl apply' operations. Consider using 'kubectl apply' with your previous configuration file instead.
deployment.apps/app-rolling rolled back
Waiting for deployment "app-rolling" rollout to finish: 1 out of 4 new replicas have been updated...
[12 more progress lines, identical in shape to the forward rollout above]
Waiting for deployment "app-rolling" rollout to finish: 1 old replicas are pending termination...
deployment "app-rolling" successfully rolled out

NAME                          READY   STATUS    RESTARTS   AGE     VERSION
app-rolling-7bfcbcb87-8tcw9   1/1     Running   0          2m35s   v1
app-rolling-7bfcbcb87-c68cs   1/1     Running   0          2m27s   v1
app-rolling-7bfcbcb87-hvzls   1/1     Running   0          2m39s   v1
app-rolling-7bfcbcb87-hwjrp   1/1     Running   0          2m31s   v1

deployment.apps/app-rolling 
REVISION  CHANGE-CAUSE
2         v2 image bump to nginx:1.29-alpine
3         v1 initial release

nginx:1.27-alpine
```

Three things worth noting:

* The new pods carry the **old ReplicaSet's hash** (`7bfcbcb87`) — the rollback reused the parked
  ReplicaSet rather than building a new one.
* The history is now revisions 2 and 3. Revision 1 was *renumbered* to 3; an undo is recorded as a new
  revision, it does not rewind the log.
* The image is back to `nginx:1.27-alpine`.
* That `Warning` about `last-applied-configuration` is real and worth reading: after an imperative
  `rollout undo`, the stored apply-annotation still describes v2, so the next `kubectl apply -f v2`
  may behave oddly. In GitOps terms, the fix belongs in git; `rollout undo` is the emergency lever.

```bash
for i in 1 2 3 4; do kubectl exec -n hw10 curl-client -- wget -qO- http://app-rolling.hw10.svc.cluster.local/; done
```

```text
APP VERSION v1
APP VERSION v1
APP VERSION v1
APP VERSION v1
```

### Honest measurement: a rolling update is zero-*downtime*, not zero-*error*

A second run of the same rollout, this time with 400 sequential HTTP requests fired from the client
pod during the rollout:

```bash
kubectl exec -n hw10 curl-client -- sh -c \
  'for i in $(seq 1 400); do printf "%s %s\n" "$(date +%H:%M:%S)" "$(wget -T 2 -qO- http://app-rolling.hw10.svc.cluster.local/ 2>/dev/null || echo REQUEST_FAILED)"; done' \
  > rolling-http.txt

sed 's/^[0-9:]* //' rolling-http.txt | sort | uniq -c
```

```text
 206 APP VERSION v1
 189 APP VERSION v2
   5 REQUEST_FAILED
```

Five failures out of 400. But look at *where* they land:

```bash
grep -n REQUEST_FAILED rolling-http.txt | cut -d: -f1 | while read n; do
  sed -n "$((n-1)),$((n+1))p" rolling-http.txt; echo "   ---"
done
```

```text
17:21:03 APP VERSION v1
17:21:03 REQUEST_FAILED
17:21:05 APP VERSION v1
   ---
17:21:06 APP VERSION v2
17:21:06 REQUEST_FAILED
17:21:08 APP VERSION v2
   ---
17:21:10 APP VERSION v1
17:21:10 REQUEST_FAILED
17:21:10 APP VERSION v1
   ---
17:21:11 APP VERSION v2
17:21:11 REQUEST_FAILED
17:21:13 APP VERSION v2
   ---
17:21:15 APP VERSION v2
17:21:15 REQUEST_FAILED
17:21:17 APP VERSION v2
   ---
```

Every failure is a single isolated request with a **successful request immediately on either side**.
These are connections that raced a pod being terminated: the pod was removed from the endpoints and
killed at almost the same instant, and the in-flight connection was reset. The service never lost
capacity (the endpoint sampler proved that), it lost individual connections.

The production fix is a `preStop` hook (`sleep 5`) plus graceful shutdown in the app, so the container
keeps serving for a few seconds after it has been pulled out of the endpoint list. Compare this
scattered pattern with the Recreate result below — that is the real distinction.

## 6.2 Blue-green

`06-strategies/02-blue-green/` — two full Deployments, `app-blue` (v1) and `app-green` (v2), both
labelled `app: myapp` but differing on `slot: blue|green`. One Service selects on `slot`, and the
cutover is a one-field change to that selector.

### Blue is live

```bash
kubectl apply -f 06-strategies/02-blue-green/deployment-blue.yaml -f 06-strategies/02-blue-green/service.yaml
kubectl rollout status deploy/app-blue -n hw10
for i in 1 2 3 4; do kubectl exec -n hw10 curl-client -- wget -qO- http://myapp.hw10.svc.cluster.local/; done
kubectl get svc myapp -n hw10 -o jsonpath='{.spec.selector}{"\n"}'
kubectl get endpoints myapp -n hw10
```

```text
deployment.apps/app-blue created
service/myapp created
Waiting for deployment "app-blue" rollout to finish: 0 of 2 updated replicas are available...
Waiting for deployment "app-blue" rollout to finish: 1 of 2 updated replicas are available...
deployment "app-blue" successfully rolled out

BLUE SLOT - APP VERSION v1
BLUE SLOT - APP VERSION v1
BLUE SLOT - APP VERSION v1
BLUE SLOT - APP VERSION v1

{"app":"myapp","slot":"blue"}
NAME    ENDPOINTS                       AGE
myapp   10.244.0.64:80,10.244.0.65:80   4s
```

### Green deploys alongside, and takes zero traffic

```bash
kubectl apply -f 06-strategies/02-blue-green/deployment-green.yaml
kubectl rollout status deploy/app-green -n hw10
kubectl get pods -n hw10 -l app=myapp -o 'custom-columns=POD:.metadata.name,SLOT:.metadata.labels.slot,IP:.status.podIP'
kubectl get endpoints myapp -n hw10
for i in 1 2 3 4; do kubectl exec -n hw10 curl-client -- wget -qO- http://myapp.hw10.svc.cluster.local/; done
```

```text
deployment.apps/app-green created
Waiting for deployment "app-green" rollout to finish: 0 of 2 updated replicas are available...
Waiting for deployment "app-green" rollout to finish: 1 of 2 updated replicas are available...
deployment "app-green" successfully rolled out

POD                          SLOT    IP
app-blue-846dd749f6-9pxxp    blue    10.244.0.65
app-blue-846dd749f6-w95rq    blue    10.244.0.64
app-green-586ffc6df8-7288s   green   10.244.0.67
app-green-586ffc6df8-swtsn   green   10.244.0.66

NAME    ENDPOINTS                       AGE
myapp   10.244.0.64:80,10.244.0.65:80   15s

BLUE SLOT - APP VERSION v1
BLUE SLOT - APP VERSION v1
BLUE SLOT - APP VERSION v1
BLUE SLOT - APP VERSION v1
```

Four pods exist. The Service's endpoint list contains **only** `.64` and `.65` — the blue IPs. Green
is fully deployed, healthy, warm, and receiving nothing. This is the window where you would run smoke
tests against green directly (via its own test Service or a port-forward) before any user sees it.

### The cutover

```bash
date +%H:%M:%S
kubectl patch svc myapp -n hw10 -p '{"spec":{"selector":{"app":"myapp","slot":"green"}}}'
date +%H:%M:%S
kubectl get svc myapp -n hw10 -o jsonpath='{.spec.selector}{"\n"}'
kubectl get endpoints myapp -n hw10
for i in 1 2 3 4 5 6; do kubectl exec -n hw10 curl-client -- wget -qO- http://myapp.hw10.svc.cluster.local/; done
```

```text
22:47:28
service/myapp patched
22:47:28

{"app":"myapp","slot":"green"}
NAME    ENDPOINTS                       AGE
myapp   10.244.0.66:80,10.244.0.67:80   25s

GREEN SLOT - APP VERSION v2
GREEN SLOT - APP VERSION v2
GREEN SLOT - APP VERSION v2
GREEN SLOT - APP VERSION v2
GREEN SLOT - APP VERSION v2
GREEN SLOT - APP VERSION v2
```

Both timestamps read `22:47:28` — the flip completed inside the same second. The endpoint list swapped
from the two blue IPs to the two green IPs, and the response body changed from BLUE/v1 to GREEN/v2.
No pod was created, deleted, or restarted.

(The same thing declaratively: `kubectl apply -f 06-strategies/02-blue-green/service-green.yaml`.)

### Rollback is the same operation, backwards

```bash
date +%H:%M:%S
kubectl patch svc myapp -n hw10 -p '{"spec":{"selector":{"app":"myapp","slot":"blue"}}}'
date +%H:%M:%S
for i in 1 2 3 4; do kubectl exec -n hw10 curl-client -- wget -qO- http://myapp.hw10.svc.cluster.local/; done
kubectl get pods -n hw10 -l app=myapp --no-headers | wc -l
```

```text
22:47:37
service/myapp patched
22:47:37

BLUE SLOT - APP VERSION v1
BLUE SLOT - APP VERSION v1
BLUE SLOT - APP VERSION v1
BLUE SLOT - APP VERSION v1

       4
```

Sub-second rollback, because blue was never torn down. Compare with the rolling-update rollback above,
which needed a complete second rollout (14 progress polls) to finish. **That is what you are buying with blue-green: the
rollback is a selector change, not a redeploy.** The price is printed right there: `4` pods for a
2-replica app — 100% extra infrastructure for the duration of the cutover.

## 6.3 Canary with weighted replica counts

`06-strategies/03-canary/` — two Deployments (`app-stable` v1, `app-canary` v2) that share the label
`app: shop` and differ on `track: stable|canary`. **One** Service selects only on `app: shop`, so it
picks up both. There is no weighting mechanism here at all — kube-proxy load-balances evenly across
all ready endpoints, so the traffic split *is* the pod-count ratio.

### 3 stable : 1 canary = 25% expected

```bash
kubectl apply -f 06-strategies/03-canary/
kubectl rollout status deploy/app-stable -n hw10
kubectl rollout status deploy/app-canary -n hw10
kubectl get pods -n hw10 -l app=shop -L track,version
kubectl get endpoints shop -n hw10
```

```text
deployment.apps/app-canary created
deployment.apps/app-stable created
service/shop created
Waiting for deployment "app-stable" rollout to finish: 0 of 3 updated replicas are available...
Waiting for deployment "app-stable" rollout to finish: 1 of 3 updated replicas are available...
Waiting for deployment "app-stable" rollout to finish: 2 of 3 updated replicas are available...
deployment "app-stable" successfully rolled out
deployment "app-canary" successfully rolled out

NAME                          READY   STATUS    RESTARTS   AGE   TRACK    VERSION
app-canary-5777dd9556-llwp2   1/1     Running   0          5s    canary   v2
app-stable-55c94757f4-7t92m   1/1     Running   0          5s    stable   v1
app-stable-55c94757f4-mcns5   1/1     Running   0          5s    stable   v1
app-stable-55c94757f4-p5sh8   1/1     Running   0          5s    stable   v1

NAME   ENDPOINTS                                                  AGE
shop   10.244.0.68:80,10.244.0.69:80,10.244.0.70:80 + 1 more...   5s
```

200 requests through the Service:

```bash
kubectl exec -n hw10 curl-client -- sh -c 'for i in $(seq 1 200); do wget -qO- http://shop.hw10.svc.cluster.local/; done' | sort | uniq -c
```

```text
  58 CANARY v2
 142 STABLE v1
```

58/200 = **29%** against an expected 25%. Rough, not exact — kube-proxy picks a backend at random per
connection, so with 200 samples you get binomial noise around the target. That imprecision is the key
weakness of replica-count canaries and the reason real canary systems use a service mesh or an ingress
that can weight by percentage independent of pod counts.

### Shift the weight: 2 stable : 2 canary = 50% expected

```bash
kubectl scale deploy/app-canary -n hw10 --replicas=2
kubectl scale deploy/app-stable -n hw10 --replicas=2
kubectl rollout status deploy/app-canary -n hw10
kubectl rollout status deploy/app-stable -n hw10
kubectl get pods -n hw10 -l app=shop -L track
kubectl exec -n hw10 curl-client -- sh -c 'for i in $(seq 1 200); do wget -qO- http://shop.hw10.svc.cluster.local/; done' | sort | uniq -c
```

```text
deployment.apps/app-canary scaled
deployment.apps/app-stable scaled
Waiting for deployment "app-canary" rollout to finish: 1 of 2 updated replicas are available...
deployment "app-canary" successfully rolled out
deployment "app-stable" successfully rolled out

NAME                          READY   STATUS    RESTARTS   AGE   TRACK
app-canary-5777dd9556-llwp2   1/1     Running   0          30s   canary
app-canary-5777dd9556-pmnhc   1/1     Running   0          5s    canary
app-stable-55c94757f4-7t92m   1/1     Running   0          30s   stable
app-stable-55c94757f4-p5sh8   1/1     Running   0          30s   stable

  89 CANARY v2
 111 STABLE v1
```

89/200 = **44.5%** against an expected 50%. The ratio moved with the replica counts, exactly as the
model predicts.

### Promote

```bash
kubectl scale deploy/app-canary -n hw10 --replicas=4
kubectl scale deploy/app-stable -n hw10 --replicas=0
kubectl rollout status deploy/app-canary -n hw10
kubectl get pods -n hw10 -l app=shop -L track
kubectl exec -n hw10 curl-client -- sh -c 'for i in $(seq 1 100); do wget -qO- http://shop.hw10.svc.cluster.local/; done' | sort | uniq -c
```

```text
deployment.apps/app-canary scaled
deployment.apps/app-stable scaled
Waiting for deployment "app-canary" rollout to finish: 2 of 4 updated replicas are available...
Waiting for deployment "app-canary" rollout to finish: 3 of 4 updated replicas are available...
deployment "app-canary" successfully rolled out

NAME                          READY   STATUS    RESTARTS   AGE   TRACK
app-canary-5777dd9556-jbptv   1/1     Running   0          4s    canary
app-canary-5777dd9556-llwp2   1/1     Running   0          48s   canary
app-canary-5777dd9556-p7qdf   1/1     Running   0          4s    canary
app-canary-5777dd9556-pmnhc   1/1     Running   0          23s   canary

 100 CANARY v2
```

100/100 canary. Aborting instead of promoting is the mirror image: `kubectl scale deploy/app-canary
--replicas=0` and the bad version is out of rotation in seconds, with the blast radius limited to the
25% of users who saw it.

Note also what the canary granularity actually is: with 4 pods the smallest possible canary is 25%.
To canary at 5% you need 20 pods. Replica-ratio canaries do not scale down to small percentages.

## 6.4 Recreate — and the downtime window that makes the whole comparison worth doing

`06-strategies/04-recreate/` — identical app, 3 replicas, one line different:

```yaml
spec:
  replicas: 3
  strategy:
    type: Recreate
```

### v1 live

```bash
kubectl apply -f 06-strategies/04-recreate/service.yaml
kubectl apply -f 06-strategies/04-recreate/deployment-v1.yaml
kubectl rollout status deploy/app-recreate -n hw10
kubectl get pods -n hw10 -l app=app-recreate -L version
kubectl exec -n hw10 curl-client -- wget -qO- http://app-recreate.hw10.svc.cluster.local/
kubectl get endpoints app-recreate -n hw10
```

```text
service/app-recreate created
deployment.apps/app-recreate created
Waiting for deployment "app-recreate" rollout to finish: 0 of 3 updated replicas are available...
Waiting for deployment "app-recreate" rollout to finish: 1 of 3 updated replicas are available...
Waiting for deployment "app-recreate" rollout to finish: 2 of 3 updated replicas are available...
deployment "app-recreate" successfully rolled out

NAME                            READY   STATUS    RESTARTS   AGE   VERSION
app-recreate-797b47cf7c-6gv8t   1/1     Running   0          5s    v1
app-recreate-797b47cf7c-clpbt   1/1     Running   0          5s    v1
app-recreate-797b47cf7c-ljhzl   1/1     Running   0          5s    v1

RECREATE - APP VERSION v1
NAME           ENDPOINTS                                      AGE
app-recreate   10.244.0.78:80,10.244.0.79:80,10.244.0.80:80   20s
```

### Roll to v2 with two independent measurements running

```bash
# terminal 1 - measurement 1: ready endpoint count, sampled continuously
./06-strategies/sample-availability.sh app-recreate 60 > recreate-availability.txt

# terminal 2 - measurement 2: 400 sequential HTTP requests from the client pod
kubectl exec -n hw10 curl-client -- sh -c \
  'for i in $(seq 1 400); do printf "%s %s\n" "$(date +%H:%M:%S)" "$(wget -T 2 -qO- http://app-recreate.hw10.svc.cluster.local/ 2>/dev/null || echo REQUEST_FAILED)"; done' \
  > recreate-http.txt

# terminal 3 - the rollout itself
date +%H:%M:%S
kubectl apply -f 06-strategies/04-recreate/deployment-v2.yaml
kubectl rollout status deploy/app-recreate -n hw10
date +%H:%M:%S
```

```text
22:49:56
deployment.apps/app-recreate configured
Waiting for deployment "app-recreate" rollout to finish: 0 out of 3 new replicas have been updated...
Waiting for deployment "app-recreate" rollout to finish: 0 out of 3 new replicas have been updated...
Waiting for deployment "app-recreate" rollout to finish: 0 out of 3 new replicas have been updated...
Waiting for deployment "app-recreate" rollout to finish: 0 out of 3 new replicas have been updated...
Waiting for deployment "app-recreate" rollout to finish: 0 out of 3 new replicas have been updated...
Waiting for deployment "app-recreate" rollout to finish: 0 of 3 updated replicas are available...
Waiting for deployment "app-recreate" rollout to finish: 1 of 3 updated replicas are available...
Waiting for deployment "app-recreate" rollout to finish: 2 of 3 updated replicas are available...
deployment "app-recreate" successfully rolled out
22:50:00
```

Contrast that with the rolling-update output: there is no "1 out of 3 new replicas have been updated"
progression here. It sits at **0 out of 3 new replicas** for five polls, because it is waiting for all
the old pods to die first.

### Measurement 1 — the endpoint count really does hit zero

```bash
awk '{print $2}' recreate-availability.txt | sort | uniq -c
grep 'ready_endpoints=0' recreate-availability.txt | head -1
grep 'ready_endpoints=0' recreate-availability.txt | tail -1
```

```text
  98 ready_endpoints=0
   1 ready_endpoints=2
 523 ready_endpoints=3

22:49:56  ready_endpoints=0
22:50:00  ready_endpoints=0
```

**98 consecutive samples with zero ready endpoints**, running from 22:49:56 to 22:50:00 — a blackout
of roughly four seconds on a trivial nginx pod with no warm-up. The rolling update's sampler, over 855
samples, never once saw fewer than 4. That is the entire difference between the two strategies, in
numbers.

The Deployment's own events confirm the mechanism:

```bash
kubectl describe deploy app-recreate -n hw10 | sed -n '/^Events:/,$p'
```

```text
Events:
  Type    Reason             Age   From                   Message
  ----    ------             ----  ----                   -------
  Normal  ScalingReplicaSet  63s   deployment-controller  Scaled up replica set app-recreate-797b47cf7c from 0 to 3
  Normal  ScalingReplicaSet  36s   deployment-controller  Scaled down replica set app-recreate-797b47cf7c from 3 to 0
  Normal  ScalingReplicaSet  36s   deployment-controller  Scaled up replica set app-recreate-86bddb84b5 from 0 to 3
```

Old ReplicaSet `3 -> 0` **then** new ReplicaSet `0 -> 3`. Sequential, not overlapping.

### Measurement 2 — real users really do get errors

```bash
sed 's/^[0-9:]* //' recreate-http.txt | sort | uniq -c
```

```text
 119 RECREATE - APP VERSION v1
 274 RECREATE - APP VERSION v2
   7 REQUEST_FAILED
```

And the exact transition, request by request (the clock is UTC inside the pod):

```bash
sed -n '116,131p' recreate-http.txt
```

```text
17:19:55 RECREATE - APP VERSION v1
17:19:56 RECREATE - APP VERSION v1
17:19:56 RECREATE - APP VERSION v1
17:19:56 RECREATE - APP VERSION v1
17:19:56 REQUEST_FAILED
17:19:56 REQUEST_FAILED
17:19:56 REQUEST_FAILED
17:19:56 REQUEST_FAILED
17:19:56 REQUEST_FAILED
17:19:58 REQUEST_FAILED
17:19:59 REQUEST_FAILED
17:20:00 RECREATE - APP VERSION v2
17:20:01 RECREATE - APP VERSION v2
17:20:01 RECREATE - APP VERSION v2
17:20:01 RECREATE - APP VERSION v2
17:20:01 RECREATE - APP VERSION v2
```

This is the output the whole task exists to produce. **Seven consecutive failures with no successful
request anywhere between them** — a clean, unbroken outage, roughly 17:19:56 to 17:20:00. Then the very
first request that succeeds is already v2. At no instant did v1 and v2 serve simultaneously.

Put the two strategies' failure patterns next to each other:

| | Rolling (400 reqs) | Recreate (400 reqs) |
| :--- | :--- | :--- |
| Failures | 5 | 7 |
| Pattern | 5 isolated singles, a success on both sides of each | 7 in one unbroken block |
| Minimum ready endpoints | 4 of 4 (855 samples) | **0** for 98 samples (~4s) |
| Versions served together | yes, v1 and v2 overlapped | no, never |

Similar raw failure counts; completely different failure *shape*. The rolling update dropped
individual connections; Recreate took the service down. And "no two versions run at once" is exactly
what you want when v2 ships an incompatible database migration — that is the one case where Recreate
is the right answer and not just the lazy one.

---

## Comparison of the four strategies

| | Rolling Update | Blue-Green | Canary | Recreate |
| :--- | :--- | :--- | :--- | :--- |
| **Downtime** | None. Measured: 4/4 ready endpoints across 855 samples; 5 isolated dropped connections out of 400 requests | None. Cutover completed within the same second (22:47:28 -> 22:47:28) | None. Both versions serve throughout | **Real.** Measured: 0 ready endpoints for 98 samples (~4s), 7 consecutive failed requests out of 400 |
| **Rollback speed** | Slow: `rollout undo` is a whole second rollout (the undo above needed 14 `rollout status` progress polls for 4 trivial pods; far longer for real apps) | **Fastest.** One selector patch, sub-second, old version never left running | Seconds: `kubectl scale canary --replicas=0` | Slowest: another full stop-then-start, with another outage |
| **Resource cost** | Low: `desired + maxSurge` (5 pods for a 4-pod app during the rollout only) | **Highest: 2x.** Measured 4 pods for a 2-replica app, held for the whole soak period | Low-moderate: total pod count stays constant, you just re-slice it | **Lowest: 1x.** Never more pods than `replicas` |
| **Both versions live at once?** | Yes, briefly and uncontrollably | Yes, but only one receives traffic | Yes, deliberately, at a controlled ratio | **No, never** |
| **Traffic granularity** | None — you cannot steer it | All or nothing | Pod-count ratio (4 pods = 25% steps); measured 29% vs 25% target and 44.5% vs 50% | None |
| **Use case** | The sane default for stateless services with backward-compatible changes | Big, risky releases where you need a pre-warmed escape hatch and an instant abort | Validating a risky change on real traffic while limiting blast radius | Incompatible schema migrations, singleton apps, `ReadWriteOnce` volumes, dev environments |
| **Main drawback** | Two versions coexist, so every change must be backward compatible; in-flight connections still drop without a `preStop` hook | Doubles your bill, and stateful backends still have to be shared or migrated | Coarse percentages, and you need real metrics to judge the canary — otherwise it is just a slow rollout | Guaranteed user-visible outage |

---

## Interview questions

**1. `kubectl get pod` shows `CrashLoopBackOff`. What phase is the pod actually in?**
`Running`. CrashLoopBackOff is not a phase — it is the container's *waiting reason*. The pod exists,
is scheduled, has a sandbox and an IP; its container keeps dying and the kubelet is waiting out an
exponential backoff before the next restart. Proven in Task 3: `PHASE=Running`,
`WAITING_REASON=CrashLoopBackOff`. The five real phases are Pending, Running, Succeeded, Failed,
Unknown.

**2. What is the difference between a readiness probe failing and a liveness probe failing?**
A failed readiness probe removes the pod's IP from the Service's endpoints — no traffic, but the
container is untouched (Task 4: `0/1 Running`, `RESTARTS 0`, only an `Unhealthy` event). A failed
liveness probe kills and restarts the container (Task 4: `RESTARTS 2`, plus a `Killing ... will be
restarted` event). Use readiness for "temporarily busy / dependency down". Use liveness only for
"this process is wedged and only a restart will fix it". Pointing a liveness probe at a downstream
dependency is a classic way to turn one outage into a cascading one.

**3. Why would you add a startup probe to an app that already has a liveness probe?**
Because the liveness probe's timing has to serve two conflicting needs: fast detection of a hang in
steady state, and patience during a slow boot. A startup probe splits them — while it is failing, the
liveness and readiness probes are suspended. Task 4 shows a container whose startup probe failed 8
times over a 40-second boot with `RESTARTS 0`; the identical liveness probe (failureThreshold 2,
period 5s) would have killed it after 10 seconds and it would never have started.

**4. You delete a pod and it comes back. You delete another and it stays dead. Why?**
`ownerReferences`. The first pod had a `controller: true` reference to a ReplicaSet, whose
reconciliation loop noticed `observed < desired` and created a replacement (Task 2:
`SuccessfulCreate` 7 seconds after the delete, with a *new* pod name). The second was a bare Pod with
empty `ownerReferences` — nothing was watching it.

**5. Walk me from a Deployment down to a Pod.**
Deployment -> ReplicaSet -> Pod, linked by `ownerReferences` with `controller: true` at each hop, and
`blockOwnerDeletion: true` so the garbage collector reaps bottom-up. The Deployment does not create
pods; it creates a ReplicaSet per pod-template-hash and moves replica counts between them. That is
literally how rolling updates and rollbacks work — Task 6 shows the old ReplicaSet parked at 0
replicas, and `rollout undo` scaling that same hash (`7bfcbcb87`) back up.

**6. Why does a StatefulSet exist when a Deployment can also mount a PVC?**
Stable network identity and per-pod storage. StatefulSet pods get ordinals (`core-db-0`) instead of
random suffixes, and `volumeClaimTemplates` creates one PVC per pod, bound to the *name*. Task 1
deletes `core-db-0` and the replacement comes back with the same name, a **different UID**, the same
`pvc-99345ab1-...`, and the file the dead pod wrote. A Deployment's replacement would get a new random
name, and its replicas would contend for a single ReadWriteOnce volume.

**7. When would you use a DaemonSet instead of a Deployment with many replicas?**
When the workload is per-*node*, not per-*request*: log collectors, metrics agents, CNI plugins,
storage drivers. A DaemonSet has no `replicas` field; it tracks the node list. Task 1 shows `Desired
Number of Nodes Scheduled: 1` on a one-node cluster, `Misscheduled: 0`. The same manifest on a 20-node
cluster produces 20 pods with no edit, and it automatically places one on every node added later — a
Deployment cannot express either property.

**8. Which deployment strategy would you choose for a release containing a non-backward-compatible
database migration, and why?**
Recreate — or blue-green with a separate database. Rolling and canary both run v1 and v2 side by side
by definition, and if v2's schema breaks v1, that overlap is an outage with data corruption on top.
Recreate guarantees the versions never coexist (Task 6: the deployment scales the old ReplicaSet
3 -> 0 *before* scaling the new one 0 -> 3). You pay for it with a real, measured outage: 98 samples
at zero ready endpoints and 7 consecutive failed requests.

**9. Your rolling update has `maxSurge: 1, maxUnavailable: 0`. What does that cost you and what does it
buy you?**
It buys guaranteed capacity: the sampler in Task 6 saw 4 of 4 ready endpoints across all 855 samples,
never 3. It costs one extra pod's worth of resources for the duration of the rollout, and it makes
the rollout slower (each new pod must pass readiness before an old one is removed). The opposite
setting, `maxUnavailable: 1, maxSurge: 0`, rolls with no extra resources but runs at reduced capacity —
fine for a batch worker, bad for a latency-sensitive API at peak.

**10. A canary at `replicas: 1` alongside `replicas: 3` stable — is that exactly 25% of traffic?**
No, it is 25% *on average*. kube-proxy picks a ready endpoint at random per connection, so the actual
split is binomial noise around the target: Task 6 measured 58/200 = 29% at a 25% target, and 89/200 =
44.5% at a 50% target. Replica-ratio canaries are also coarse — with 4 pods your smallest step is 25%,
and a 5% canary needs 20 pods. For precise weighting you need an ingress controller or a service mesh
that splits by percentage rather than by pod count.

**11. `kubectl rollout history` shows `<none>` in the CHANGE-CAUSE column. How do you fix that?**
Set `metadata.annotations."kubernetes.io/change-cause"` in the manifest (or pass
`--record`, deprecated). Task 6's manifests carry it, which is why the history reads `v1 initial
release` / `v2 image bump to nginx:1.29-alpine`. Also note what an undo does to the history: after
`rollout undo`, revisions 1 and 2 became 2 and 3 — the undo is appended as a *new* revision, it does
not rewind the log.

**12. A pod is stuck Pending. What is your first command, and what are the two broad causes?**
`kubectl describe pod <name>` and read the Events — `get pod` only ever says "Pending". The message
distinguishes the causes. Task 3 shows both: `0/1 nodes are available: 1 Insufficient cpu, 1
Insufficient memory` (no node has the capacity the requests demand) versus `1 node(s) didn't match
Pod's node affinity/selector` (a constraint no node satisfies). Others in the same family: unbound
PVCs, taints without matching tolerations, and hitting a ResourceQuota. A useful tell: a Pending pod
that was never scheduled has **no `containerStatuses` at all**, which is how you separate "not
scheduled" from "scheduled but image won't pull".

**13. Blue-green is the fastest rollback. Why does anyone use anything else?**
Cost and state. Blue-green means running both versions at full scale — Task 6 held 4 pods for a
2-replica app, a 100% resource premium, and at production scale that is a doubled bill for every
release. It also does nothing for shared state: both slots usually talk to one database, so a
destructive migration is still a one-way door. Rolling update gets you zero downtime at roughly 1x
cost, which is why it is the default.

---

## Cleanup

```bash
kubectl get all -n hw10
kubectl delete namespace hw10
kubectl get ns
```

```text
NAME                               READY   STATUS    RESTARTS   AGE
pod/app-rolling-7567bb6d89-5s8p4   1/1     Running   0          11m
pod/app-rolling-7567bb6d89-dlw64   1/1     Running   0          10m
pod/app-rolling-7567bb6d89-ftz2t   1/1     Running   0          10m
pod/app-rolling-7567bb6d89-k4br8   1/1     Running   0          11m
pod/curl-client                    1/1     Running   0          19m

NAME                  TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
service/app-rolling   NodePort   10.96.117.36   <none>        80:30100/TCP   11m

NAME                          READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/app-rolling   4/4     4            4           11m

NAME                                     DESIRED   CURRENT   READY   AGE
replicaset.apps/app-rolling-7567bb6d89   4         4         4       11m
replicaset.apps/app-rolling-7bfcbcb87    0         0         0       11m

namespace "hw10" deleted

NAME              STATUS   AGE
default           Active   38m
ingress-nginx     Active   34m
kube-node-lease   Active   38m
kube-public       Active   38m
kube-system       Active   38m
```

`hw10` is gone from the namespace list, and with it every pod, Deployment, ReplicaSet, StatefulSet,
DaemonSet, Service, EndpointSlice and PVC created by this homework. Deleting a namespace is the
cleanest possible teardown — it is one cascading delete over every namespaced object inside it.

The cluster itself is left running and untouched: `minikube delete` / `stop` / `start` were never run,
no cluster-scoped object was removed, and nothing outside `hw10` was modified. (The `ingress-nginx`
namespace in that listing belongs to another exercise on this shared cluster, not to this one.)
