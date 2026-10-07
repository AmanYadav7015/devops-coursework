# Task 1 — Kubernetes Volumes

Everything below was executed against a live single-node minikube cluster
(Kubernetes v1.37.0, containerd, `k8s.io/minikube-hostpath` provisioner) in the namespace `hw13`.
Every `text` block is the real output of the `bash` block above it.

---

## Contents

1. [Why volumes exist](#1-why-volumes-exist)
2. [Setup](#2-setup)
3. [emptyDir](#3-emptydir)
4. [hostPath](#4-hostpath)
5. [PersistentVolume](#5-persistentvolume-pv)
6. [PersistentVolumeClaim](#6-persistentvolumeclaim-pvc)
7. [StorageClass](#7-storageclass)
8. [Dynamic provisioning](#8-dynamic-provisioning)
9. [Reclaim policies](#9-reclaim-policies-delete-vs-retain)
10. [Access modes](#10-access-modes-rwo--rox--rwx--rwop)
11. [Comparison table](#11-comparison-table)
12. [Decision guide](#12-which-volume-type-should-i-use)

---

## 1. Why volumes exist

A container's writable layer is created when the container starts and thrown away when the container
is destroyed. Two separate problems follow from that:

| Problem | What is lost | Fixed by |
| :--- | :--- | :--- |
| A container crashes and the kubelet restarts it | The container's own filesystem | Any volume, even `emptyDir` |
| The Pod is deleted or rescheduled | The Pod and everything scoped to it | A volume whose lifetime is independent of the Pod (`hostPath`, PV/PVC) |

A **volume** is a directory, backed by some medium, that is mounted into one or more containers of a
Pod. The medium decides the lifetime:

```text
container filesystem   lives as long as the container
emptyDir               lives as long as the Pod
hostPath               lives as long as the node's directory
PersistentVolume       lives as long as the cluster admin / reclaim policy allows
```

---

## 2. Setup

Every manifest in this folder targets the namespace `hw13`.

```bash
kubectl apply -f 00-namespace.yaml
```

```text
namespace/hw13 created
```

The cluster has exactly one StorageClass to start with:

```bash
kubectl get sc
```

```text
NAME                 PROVISIONER                RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION   AGE
standard (default)   k8s.io/minikube-hostpath   Delete          Immediate           false                  19d
```

`standard` is marked `(default)`, which matters a lot in section 6.

---

## 3. emptyDir

`emptyDir` is an empty directory created when the Pod is assigned to a node, shared by every
container in that Pod, and deleted **when the Pod is removed from the node**. It is not deleted when
a container restarts — that distinction is the whole point of this section.

`01-emptydir-pod.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: emptydir-demo
  namespace: hw13
spec:
  containers:
    - name: app
      image: busybox:1.36
      command:
        - sh
        - -c
        - "while [ ! -f /tmp/exit-now ]; do sleep 1; done; exit 1"
      volumeMounts:
        - name: scratch
          mountPath: /data
  volumes:
    - name: scratch
      emptyDir: {}
```

The command is a deliberate switch: the container runs until somebody creates `/tmp/exit-now`, then
exits non-zero so the kubelet restarts it. `/tmp` is the container filesystem, `/data` is the
emptyDir — so the flag file disappears on restart while the test data should not.

```bash
kubectl apply -f 01-emptydir-pod.yaml
kubectl wait --for=condition=Ready pod/emptydir-demo -n hw13 --timeout=90s
kubectl get pod emptydir-demo -n hw13
```

```text
pod/emptydir-demo created
pod/emptydir-demo condition met
NAME            READY   STATUS    RESTARTS   AGE
emptydir-demo   1/1     Running   0          1s
```

### 3.1 Write a file into the emptyDir

```bash
kubectl exec -n hw13 emptydir-demo -- sh -c 'echo "Hello from emptyDir" > /data/message.txt'
kubectl exec -n hw13 emptydir-demo -- cat /data/message.txt
```

```text
Hello from emptyDir
```

### 3.2 Restart the container — the data survives

```bash
kubectl exec -n hw13 emptydir-demo -- touch /tmp/exit-now
sleep 25
kubectl get pod emptydir-demo -n hw13
kubectl exec -n hw13 emptydir-demo -- cat /data/message.txt
```

```text
NAME            READY   STATUS    RESTARTS      AGE
emptydir-demo   1/1     Running   1 (24s ago)   30s
Hello from emptyDir
```

`RESTARTS 1` proves the container process really died and was recreated by the kubelet. The file is
still there, because the emptyDir belongs to the **Pod**, not to the container. A brand-new container
filesystem was mounted on top of the same volume.

### 3.3 Delete the Pod — the data is gone

```bash
kubectl delete pod emptydir-demo -n hw13
kubectl apply -f 01-emptydir-pod.yaml
kubectl wait --for=condition=Ready pod/emptydir-demo -n hw13 --timeout=90s
kubectl exec -n hw13 emptydir-demo -- cat /data/message.txt; echo "exit code: $?"
```

```text
pod "emptydir-demo" deleted from hw13 namespace
pod/emptydir-demo created
pod/emptydir-demo condition met
cat: can't open '/data/message.txt': No such file or directory
command terminated with exit code 1
exit code: 1
```

Same manifest, same Pod name, same mount path — empty directory. When the Pod object was deleted the
kubelet deleted the backing directory on the node.

**The rule in one line:** `emptyDir` survives a container restart, not a Pod delete.

Two options worth knowing:

```yaml
emptyDir:
  medium: Memory       # tmpfs, counts against the container's memory limit, very fast, never on disk
  sizeLimit: 512Mi     # the Pod is evicted if the volume grows past this
```

Real uses: scratch space for a build, a cache, and the classic sidecar pattern where one container
writes logs into `/var/log/app` and a shipper container in the same Pod reads them.

---

## 4. hostPath

`hostPath` mounts a path from the **node's own filesystem** into the Pod.

`02-hostpath-pod.yaml`:

```yaml
      volumeMounts:
        - name: node-disk
          mountPath: /data
  volumes:
    - name: node-disk
      hostPath:
        path: /tmp/hw13-hostpath-data
        type: DirectoryOrCreate
```

`type: DirectoryOrCreate` means "create the directory if it is missing"; without a `type` Kubernetes
does no checking at all and you get a confusing mount failure if the path is wrong.

```bash
kubectl apply -f 02-hostpath-pod.yaml
kubectl wait --for=condition=Ready pod/hostpath-demo -n hw13 --timeout=90s
kubectl exec -n hw13 hostpath-demo -- sh -c 'echo "written by hostpath-demo" > /data/node-file.txt'
kubectl exec -n hw13 hostpath-demo -- cat /data/node-file.txt
```

```text
pod/hostpath-demo created
pod/hostpath-demo condition met
written by hostpath-demo
```

The file is genuinely on the node, not inside the container — read it over SSH to the node:

```bash
minikube ssh -- "ls -l /tmp/hw13-hostpath-data && cat /tmp/hw13-hostpath-data/node-file.txt"
```

```text
total 4
-rw-r--r-- 1 root root 25 Oct  7 12:31 node-file.txt
written by hostpath-demo
```

### 4.1 hostPath survives a Pod delete

```bash
kubectl delete pod hostpath-demo -n hw13
kubectl apply -f 02-hostpath-pod.yaml
kubectl wait --for=condition=Ready pod/hostpath-demo -n hw13 --timeout=90s
kubectl exec -n hw13 hostpath-demo -- cat /data/node-file.txt
```

```text
pod "hostpath-demo" deleted from hw13 namespace
pod/hostpath-demo created
pod/hostpath-demo condition met
written by hostpath-demo
```

Unlike the emptyDir, the data came back. The directory lives on the node and nothing cleaned it up.

### 4.2 Why hostPath is still the wrong answer in production

```bash
kubectl get pod hostpath-demo -n hw13 -o wide
```

```text
NAME            READY   STATUS    RESTARTS   AGE   IP            NODE       NOMINATED NODE   READINESS GATES
hostpath-demo   1/1     Running   0          1s    10.244.0.39   minikube   <none>           <none>
```

This worked only because there is exactly one node. On a real cluster the scheduler could place the
replacement Pod on a different node, where `/tmp/hw13-hostpath-data` is empty or does not exist —
the data silently "disappears". `hostPath` also punches a hole through the container boundary: a Pod
that can mount `/` or `/var/run/docker.sock` effectively owns the node, which is why Pod Security
Standards `baseline` and `restricted` forbid it.

Legitimate uses: node-level agents (log shippers, CNI plugins, monitoring agents) that are *supposed*
to read the node, and local development.

---

## 5. PersistentVolume (PV)

A **PersistentVolume** is a cluster-scoped object representing a piece of real storage. It is not
namespaced, and its lifecycle is independent of any Pod.

`03-static-pv.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: hw13-static-pv
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: hw13-manual
  hostPath:
    path: /tmp/hw13-static-data
    type: DirectoryOrCreate
```

```bash
kubectl apply -f 03-static-pv.yaml
kubectl get pv hw13-static-pv
```

```text
persistentvolume/hw13-static-pv created
NAME             CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      CLAIM   STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
hw13-static-pv   1Gi        RWO            Retain           Available           hw13-manual    <unset>                          0s
```

`STATUS Available` means the PV exists and nothing has claimed it yet. A PV moves through
`Available -> Bound -> Released -> (Available | deleted)`.

Note `storageClassName: hw13-manual`. No StorageClass object with that name exists, and that is
intentional — it is used purely as a label so that only a PVC asking for `hw13-manual` can match
this PV. This is the standard trick for pre-provisioned ("static") volumes.

---

## 6. PersistentVolumeClaim (PVC)

A **PersistentVolumeClaim** is a namespaced request for storage. A Pod never references a PV
directly; it references a PVC, and the control plane binds the PVC to a PV.

```text
Pod  ──mounts──>  PVC  ──bound to──>  PV  ──backed by──>  real storage
```

### 6.1 The mistake almost everybody makes first

`04-naive-pvc.yaml` asks for 500Mi RWO and says nothing about a StorageClass:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: naive-pvc
  namespace: hw13
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 500Mi
```

The intuition is "there is a 1Gi Available PV sitting right there, it will bind to that". It does not:

```bash
kubectl apply -f 04-naive-pvc.yaml
kubectl get pvc -n hw13
kubectl get pv | grep -E 'NAME|hw13'
```

```text
persistentvolumeclaim/naive-pvc created
NAME        STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
naive-pvc   Bound    pvc-e4181fe2-ac27-45bc-8677-011e742f9389   500Mi      RWO            standard       <unset>                 5s
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      CLAIM            STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
hw13-static-pv                             1Gi        RWO            Retain           Available                    hw13-manual    <unset>                          5s
pvc-e4181fe2-ac27-45bc-8677-011e742f9389   500Mi      RWO            Delete           Bound       hw13/naive-pvc   standard       <unset>                          5s
```

Omitting `storageClassName` does **not** mean "any class". The `DefaultStorageClass` admission
plugin stamps the default class (`standard`) onto the claim, so it was dynamically provisioned a
brand-new PV and the hand-made `hw13-static-pv` is still `Available`.

To bind to a PV with no real StorageClass you must write `storageClassName: ""` (empty string) or
name the exact class the PV carries.

### 6.2 A PVC that actually binds to the static PV

`05-static-pvc.yaml` names the class explicitly:

```yaml
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: hw13-manual
  resources:
    requests:
      storage: 500Mi
```

```bash
kubectl apply -f 05-static-pvc.yaml
kubectl get pvc static-pvc -n hw13
kubectl get pv hw13-static-pv
```

```text
persistentvolumeclaim/static-pvc created
NAME         STATUS   VOLUME           CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
static-pvc   Bound    hw13-static-pv   1Gi        RWO            hw13-manual    <unset>                 4s
NAME             CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM             STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
hw13-static-pv   1Gi        RWO            Retain           Bound    hw13/static-pvc   hw13-manual    <unset>                          13s
```

The claim asked for 500Mi and got the whole 1Gi volume. Binding is **not** a partition: a PVC binds
to a single PV that is *at least* as big as the request, and the rest of the capacity is wasted.
Binding is also exclusive and one-to-one in both directions.

```bash
kubectl describe pv hw13-static-pv
```

```text
Name:            hw13-static-pv
Labels:          <none>
Annotations:     pv.kubernetes.io/bound-by-controller: yes
Finalizers:      [kubernetes.io/pv-protection]
StorageClass:    hw13-manual
Status:          Bound
Claim:           hw13/static-pvc
Reclaim Policy:  Retain
Access Modes:    RWO
VolumeMode:      Filesystem
Capacity:        1Gi
Node Affinity:   <none>
Message:         
Source:
    Type:          HostPath (bare host directory volume)
    Path:          /tmp/hw13-static-data
    HostPathType:  DirectoryOrCreate
Events:            <none>
```

### 6.3 The capture that matters: data outlives the Pod

```bash
kubectl apply -f 06-static-pod.yaml
kubectl wait --for=condition=Ready pod/static-storage-demo -n hw13 --timeout=90s
kubectl exec -n hw13 static-storage-demo -- sh -c 'echo "PVC data written at $(date -u +%H:%M:%SZ)" > /data/pvc-message.txt'
kubectl exec -n hw13 static-storage-demo -- cat /data/pvc-message.txt
kubectl delete pod static-storage-demo -n hw13
kubectl apply -f 06-static-pod.yaml
kubectl wait --for=condition=Ready pod/static-storage-demo -n hw13 --timeout=90s
kubectl exec -n hw13 static-storage-demo -- cat /data/pvc-message.txt
```

```text
pod/static-storage-demo created
pod/static-storage-demo condition met
PVC data written at 12:32:56Z
pod "static-storage-demo" deleted from hw13 namespace
pod/static-storage-demo created
pod/static-storage-demo condition met
PVC data written at 12:32:56Z
```

The timestamp is the proof. It was generated once, before the Pod was destroyed, and the brand-new
Pod read back the identical string — so this is the original file, not a file the new Pod wrote.
Compare with section 3.3, where the same experiment on an `emptyDir` returned
`No such file or directory`.

---

## 7. StorageClass

A **StorageClass** describes a *kind* of storage the cluster can create on demand. It has three
fields that decide almost everything:

| Field | What it controls |
| :--- | :--- |
| `provisioner` | Which driver creates the volume (`ebs.csi.aws.com`, `disk.csi.azure.com`, `k8s.io/minikube-hostpath`, …) |
| `reclaimPolicy` | What happens to the PV when its PVC is deleted — `Delete` or `Retain` |
| `volumeBindingMode` | `Immediate` (provision as soon as the PVC appears) or `WaitForFirstConsumer` (wait until a Pod is scheduled, so the volume is created in the right zone/node) |
| `parameters` | Driver-specific knobs: disk type, IOPS, filesystem, encryption key |
| `allowVolumeExpansion` | Whether a PVC can be grown later by editing `resources.requests.storage` |

```bash
kubectl describe sc standard
```

```text
Name:            standard
IsDefaultClass:  Yes
Annotations:     kubectl.kubernetes.io/last-applied-configuration={"apiVersion":"storage.k8s.io/v1","kind":"StorageClass","metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"},"labels":{"addonmanager.kubernetes.io/mode":"EnsureExists"},"name":"standard"},"provisioner":"k8s.io/minikube-hostpath"}
,storageclass.kubernetes.io/is-default-class=true
Provisioner:           k8s.io/minikube-hostpath
Parameters:            <none>
AllowVolumeExpansion:  <unset>
MountOptions:          <none>
ReclaimPolicy:         Delete
VolumeBindingMode:     Immediate
Events:                <none>
```

`IsDefaultClass: Yes` comes from the annotation `storageclass.kubernetes.io/is-default-class=true`.
That single annotation is what silently captured `naive-pvc` in section 6.1.

### 7.1 A custom StorageClass

`09-storageclass.yaml` keeps the same provisioner but flips the reclaim policy:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: hw13-retain-sc
provisioner: k8s.io/minikube-hostpath
reclaimPolicy: Retain
volumeBindingMode: Immediate
allowVolumeExpansion: false
```

```bash
kubectl apply -f 09-storageclass.yaml
kubectl get sc
```

```text
storageclass.storage.k8s.io/hw13-retain-sc created
NAME                 PROVISIONER                RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION   AGE
hw13-retain-sc       k8s.io/minikube-hostpath   Retain          Immediate           false                  0s
standard (default)   k8s.io/minikube-hostpath   Delete          Immediate           false                  19d
```

### 7.2 What did not work, and why

The first version of this StorageClass used `volumeBindingMode: WaitForFirstConsumer`
(kept as `09b-storageclass-waitforfirstconsumer.yaml`). The PVC behaved correctly at first:

```bash
kubectl apply -f 09b-storageclass-waitforfirstconsumer.yaml
kubectl apply -f 10-retain-pvc.yaml
kubectl get pvc retain-pvc -n hw13
kubectl describe pvc retain-pvc -n hw13 | tail -8
```

```text
NAME         STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS     VOLUMEATTRIBUTESCLASS   AGE
retain-pvc   Pending                                      hw13-retain-sc   <unset>                 6s
Capacity:      
Access Modes:  
VolumeMode:    Filesystem
Used By:       <none>
Events:
  Type    Reason                Age   From                         Message
  ----    ------                ----  ----                         -------
  Normal  WaitForFirstConsumer  6s    persistentvolume-controller  waiting for first consumer to be created before binding
```

That is exactly right: `Pending`, waiting for a Pod. But creating the Pod did not unblock it:

```bash
kubectl apply -f 11-retain-pod.yaml
sleep 45
kubectl get pvc retain-pvc -n hw13
kubectl get pod retain-demo -n hw13
kubectl describe pvc retain-pvc -n hw13 | tail -10
```

```text
NAME         STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS     VOLUMEATTRIBUTESCLASS   AGE
retain-pvc   Pending                                      hw13-retain-sc   <unset>                 45s
NAME          READY   STATUS    RESTARTS   AGE
retain-demo   0/1     Pending   0          45s
Events:
  Type     Reason                Age               From                                                                    Message
  ----     ------                ----              ----                                                                    -------
  Normal   WaitForFirstConsumer  45s               persistentvolume-controller                                             waiting for first consumer to be created before binding
  Normal   ExternalProvisioning  1s (x4 over 45s)  persistentvolume-controller                                             Waiting for a volume to be created either by the external provisioner 'k8s.io/minikube-hostpath' or manually by the system administrator. If volume creation is delayed, please verify that the provisioner is running and correctly registered.
  Warning  ProvisioningFailed    0s (x3 over 45s)  k8s.io/minikube-hostpath_minikube_f3469645-44ac-4eb9-8d78-6c13965a2d6b  failed to get target node: nodes "minikube" is forbidden: User "system:serviceaccount:kube-system:storage-provisioner" cannot get resource "nodes" in API group "" at the cluster scope
```

Root cause, read straight off the event: for delayed binding the provisioner must look up the node
the Pod was scheduled to, and minikube's `storage-provisioner` ServiceAccount has no `get nodes`
permission at cluster scope. Delayed binding is therefore **not usable on stock minikube**; it is a
limitation of this provisioner's RBAC, not of the YAML. Fixing it would mean editing a ClusterRole in
`kube-system`, which is out of scope for this exercise, so the class was recreated with
`volumeBindingMode: Immediate`.

`volumeBindingMode` is immutable, so this required deleting and recreating the StorageClass, not
editing it. With `Immediate` the same PVC binds instantly:

```bash
kubectl delete sc hw13-retain-sc
kubectl apply -f 09-storageclass.yaml
kubectl apply -f 10-retain-pvc.yaml
kubectl get pvc retain-pvc -n hw13
```

```text
storageclass.storage.k8s.io "hw13-retain-sc" deleted
storageclass.storage.k8s.io/hw13-retain-sc created
persistentvolumeclaim/retain-pvc created
NAME         STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS     VOLUMEATTRIBUTESCLASS   AGE
retain-pvc   Bound    pvc-e2b8c504-b1c5-4e74-b107-626776dd2dd2   200Mi      RWO            hw13-retain-sc   <unset>                 6s
```

On a real multi-zone cloud cluster `WaitForFirstConsumer` is the setting you want, because an
`Immediate` EBS volume can be created in `us-east-1a` while the scheduler wanted to put the Pod in
`us-east-1c`, and the Pod then never starts.

---

## 8. Dynamic provisioning

Static provisioning means an administrator creates PVs by hand ahead of time. Dynamic provisioning
means the PVC itself triggers creation of the PV.

```text
PVC created  ->  StorageClass named on the PVC  ->  provisioner (CSI driver)  ->  real disk  ->  PV  ->  Bound
```

### 8.1 `kubectl get pv` before

```bash
kubectl get pv
```

```text
NAME             CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM             STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
hw13-static-pv   1Gi        RWO            Retain           Bound    hw13/static-pvc   hw13-manual    <unset>                          64s
```

One PV: the one created by hand in section 5.

### 8.2 Create a PVC only — no PV is written by anyone

`07-dynamic-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dynamic-pvc
  namespace: hw13
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: standard
  resources:
    requests:
      storage: 500Mi
```

```bash
kubectl apply -f 07-dynamic-pvc.yaml
```

```text
persistentvolumeclaim/dynamic-pvc created
```

### 8.3 `kubectl get pv` after

```bash
kubectl get pv
kubectl get pvc dynamic-pvc -n hw13
```

```text
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM              STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
hw13-static-pv                             1Gi        RWO            Retain           Bound    hw13/static-pvc    hw13-manual    <unset>                          70s
pvc-dd514f66-3be1-442f-8fe4-f30b2322dc54   500Mi      RWO            Delete           Bound    hw13/dynamic-pvc   standard       <unset>                          6s

NAME          STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
dynamic-pvc   Bound    pvc-dd514f66-3be1-442f-8fe4-f30b2322dc54   500Mi      RWO            standard       <unset>                 6s
```

A second PV appeared six seconds later and nobody wrote a PV manifest. Three fingerprints identify
a dynamically provisioned PV:

- the provisioner names it `pvc-<uid-of-the-claim>`, which no human would type
- the capacity is exactly the requested 500Mi, not a rounded-up admin guess
- the reclaim policy is `Delete`, inherited from the `standard` StorageClass

The provisioner also created the real directory on the node:

```bash
kubectl get pv pvc-dd514f66-3be1-442f-8fe4-f30b2322dc54 -o jsonpath='{.spec.hostPath.path}{"\n"}'
kubectl apply -f 08-dynamic-pod.yaml
kubectl exec -n hw13 dynamic-storage-demo -- sh -c 'echo "dynamic provisioning works" > /data/dyn.txt'
minikube ssh -- "sudo cat /tmp/hostpath-provisioner/hw13/dynamic-pvc/dyn.txt"
```

```text
/tmp/hostpath-provisioner/hw13/dynamic-pvc
pod/dynamic-storage-demo created
dynamic provisioning works
```

The path `/tmp/hostpath-provisioner/<namespace>/<pvc-name>` is minikube's convention. On AWS the
equivalent step would have created an EBS volume; the Kubernetes objects would look identical.

---

## 9. Reclaim policies: Delete vs Retain

The reclaim policy decides what happens to the PV, and to the data, when the PVC is deleted.

### 9.1 `Delete` — the PV disappears with the claim

The dynamic PV behind `naive-pvc` inherited `Delete` from `standard`:

```bash
kubectl delete pvc naive-pvc -n hw13
kubectl get pv
```

```text
persistentvolumeclaim "naive-pvc" deleted from hw13 namespace
NAME             CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM             STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
hw13-static-pv   1Gi        RWO            Retain           Bound    hw13/static-pvc   hw13-manual    <unset>                          64s
```

`pvc-e4181fe2-...` is simply gone, and with it the data. One `kubectl delete pvc` on a production
database is enough.

### 9.2 `Retain` — the PV survives as `Released`

`retain-pvc` used `hw13-retain-sc` with `reclaimPolicy: Retain`:

```bash
RETAIN_PV=$(kubectl get pvc retain-pvc -n hw13 -o jsonpath='{.spec.volumeName}')
kubectl delete pvc retain-pvc -n hw13
kubectl get pv $RETAIN_PV
```

```text
persistentvolumeclaim "retain-pvc" deleted from hw13 namespace
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS     CLAIM             STORAGECLASS     VOLUMEATTRIBUTESCLASS   REASON   AGE
pvc-e2b8c504-b1c5-4e74-b107-626776dd2dd2   200Mi      RWO            Retain           Released   hw13/retain-pvc   hw13-retain-sc   <unset>                          16s
```

`STATUS Released` is the important state. The PV still exists, the data is still on disk, but the PV
is **not reusable**: it still carries `claimRef` pointing at the deleted claim, so no new PVC can
bind to it. An administrator must either delete the PV or clear `spec.claimRef` to return it to
`Available`. That manual step is the price of safety:

```bash
kubectl delete pv $RETAIN_PV
```

```text
persistentvolume "pvc-e2b8c504-b1c5-4e74-b107-626776dd2dd2" deleted
```

| Policy | On `kubectl delete pvc` | Data | Who cleans up |
| :--- | :--- | :--- | :--- |
| `Delete` | PV and the underlying disk are deleted | Lost immediately | Nobody — automatic |
| `Retain` | PV goes to `Released`, disk untouched | Preserved | An administrator, by hand |
| `Recycle` | Deprecated and removed; used to `rm -rf` the volume | — | — |

---

## 10. Access modes: RWO / ROX / RWX / RWOP

| Access mode | Short | Meaning |
| :--- | :--- | :--- |
| `ReadWriteOnce` | RWO | Mounted read-write by **one node**. Several Pods on that same node may share it. |
| `ReadOnlyMany` | ROX | Mounted read-only by **many nodes** at once. |
| `ReadWriteMany` | RWX | Mounted read-write by **many nodes** at once. Needs a shared filesystem (NFS, CephFS, EFS, Azure Files). |
| `ReadWriteOncePod` | RWOP | Mounted read-write by **exactly one Pod** in the whole cluster. Stable since Kubernetes 1.29. |

The subtlety people miss: RWO is a *node*-level guarantee, not a Pod-level one. Two Pods of the same
Deployment landing on the same node can both write to one RWO volume and corrupt each other. RWOP
exists precisely to close that gap.

### 10.1 What minikube's provisioner actually supports

All three non-default modes were requested against `standard`:

```bash
kubectl apply -f 12-accessmode-pvcs.yaml
kubectl get pvc -n hw13
```

```text
persistentvolumeclaim/am-rox created
persistentvolumeclaim/am-rwx created
persistentvolumeclaim/am-rwop created
NAME          STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
am-rox        Bound    pvc-d998d400-8e04-430c-8d5a-a94c772014bd   100Mi      ROX            standard       <unset>                 8s
am-rwop       Bound    pvc-d1d4eed8-9cda-440f-aa5d-70ea5e035669   100Mi      RWOP           standard       <unset>                 8s
am-rwx        Bound    pvc-0e6d13dc-f15e-45b5-8a66-848cbf75c2c4   100Mi      RWX            standard       <unset>                 8s
```

Every one of them bound. **A successful bind proves nothing about the storage.** The hostpath
provisioner copies whatever access modes the claim asked for straight onto the PV it creates; it
never validates them. On a real cloud block-storage class, an RWX claim on `gp3` would stay `Pending`
with a `ProvisioningFailed` event, because EBS genuinely cannot do it.

### 10.2 RWX "works" here — for the wrong reason

```bash
kubectl apply -f 13-rwx-two-pods.yaml
kubectl wait --for=condition=Ready pod/rwx-writer pod/rwx-reader -n hw13 --timeout=90s
kubectl exec -n hw13 rwx-writer -- sh -c 'echo "written by rwx-writer" > /data/shared.txt'
kubectl exec -n hw13 rwx-reader -- cat /data/shared.txt
kubectl get pods -n hw13 -o wide | grep -E 'NAME|rwx'
```

```text
pod/rwx-writer created
pod/rwx-reader created
pod/rwx-writer condition met
pod/rwx-reader condition met
written by rwx-writer
NAME                   READY   STATUS    RESTARTS   AGE     IP            NODE       NOMINATED NODE   READINESS GATES
rwx-reader             1/1     Running   0          0s      10.244.0.55   minikube   <none>           <none>
rwx-writer             1/1     Running   0          0s      10.244.0.54   minikube   <none>           <none>
```

Two Pods really did share one volume. But look at the `NODE` column: both are on `minikube`. This is
a single-node cluster, so "many nodes" is trivially satisfied — it is a local directory bind-mounted
twice. The same manifest on a multi-node cluster with a hostpath-style provisioner would give the two
Pods two *different* empty directories. Do not read this as "minikube supports RWX".

### 10.3 ROX is not enforced either

```bash
kubectl apply -f 15-rox-pod.yaml
kubectl exec -n hw13 rox-demo -- sh -c 'echo "can I write?" > /data/test.txt' ; echo "exit code: $?"
kubectl exec -n hw13 rox-demo -- cat /data/test.txt
```

```text
pod/rox-demo created
pod/rox-demo condition met
exit code: 0
can I write?
```

A write into a `ReadOnlyMany` claim succeeded. `accessModes` on a PVC is matching metadata used by
the binder and the scheduler — it is not a mount option. If you want a genuinely read-only mount you
must say so in the Pod:

```yaml
volumeMounts:
  - name: readonly-claim
    mountPath: /data
    readOnly: true
```

### 10.4 RWOP *is* enforced — by the scheduler

Two Pods were pointed at the same `ReadWriteOncePod` claim:

```bash
kubectl apply -f 14-rwop-two-pods.yaml
kubectl get pods -n hw13 | grep -E 'NAME|rwop'
kubectl describe pod rwop-second -n hw13 | tail -6
```

```text
pod/rwop-first created
pod/rwop-second created
NAME                   READY   STATUS    RESTARTS   AGE
rwop-first             1/1     Running   0          20s
rwop-second            0/1     Pending   0          20s
Events:
  Type     Reason            Age   From               Message
  ----     ------            ----  ----               -------
  Warning  FailedScheduling  20s   default-scheduler  0/1 nodes are available: 1 node(s) unavailable due to PersistentVolumeClaim with ReadWriteOncePod access mode already in-use by another pod. preemption: 0/1 nodes are available: 1 No preemption victims found for incoming pod.
```

This is the honest summary for minikube:

| Mode | PVC binds? | Actually enforced / honoured? |
| :--- | :--- | :--- |
| RWO | Yes | Yes, but only against a second *node* — and there is only one node |
| ROX | Yes | **No** — the mount is still writable (10.3) |
| RWX | Yes | Only trivially — one node, one directory (10.2) |
| RWOP | Yes | **Yes** — the scheduler refuses the second Pod (10.4) |

RWOP is enforced by the kube-scheduler itself, which is why it works everywhere. The other three
depend entirely on the storage driver, and `k8s.io/minikube-hostpath` implements none of them.

---

## 11. Comparison table

| | `emptyDir` | `hostPath` | PV + PVC (static) | PV + PVC (dynamic) |
| :--- | :--- | :--- | :--- | :--- |
| Scope of the object | Pod spec | Pod spec | PV cluster-scoped, PVC namespaced | same |
| Who creates the storage | kubelet | Pre-existing node path | Administrator, by hand | The provisioner, on demand |
| Survives container restart | Yes (3.2) | Yes | Yes | Yes |
| Survives Pod delete | **No** (3.3) | Yes, same node only (4.1) | **Yes** (6.3) | **Yes** |
| Survives node change | No | **No** | Depends on backend | Depends on backend |
| Survives PVC delete | n/a | n/a | `Retain` -> yes (9.2) | `Delete` -> **no** (9.1) |
| Needs a StorageClass | No | No | No (uses a dummy class name) | Yes |
| Shareable between Pods | Containers in the same Pod only | Any Pod on that node | Per access mode | Per access mode |
| Scales to many developers | n/a | n/a | No — admin bottleneck | Yes |
| Production use | Scratch, cache, sidecar hand-off | Node agents only | Pre-existing SAN/NFS exports | The normal answer |

---

## 12. Which volume type should I use?

```text
Does the data need to outlive the Pod?
├── No  ──> emptyDir
│           (scratch, cache, sidecar log hand-off; medium: Memory for speed)
└── Yes
     │
     ├── Am I a node-level agent that is supposed to read the node?
     │      └── Yes ──> hostPath  (log shipper, CNI, node exporter)
     │
     └── No
          ├── Does the cluster have a StorageClass with a working provisioner?
          │      └── Yes ──> PVC naming that class  (dynamic provisioning — the default answer)
          │                   multi-zone cloud ──> volumeBindingMode: WaitForFirstConsumer
          │                   data you cannot lose ──> reclaimPolicy: Retain
          │
          └── No ──> admin pre-creates a PV + a PVC that names its storageClassName
```

Two rules worth memorising:

1. **A Pod never names a PV.** It names a PVC. That indirection is what lets the same Deployment
   manifest run on minikube, EKS and AKS unchanged.
2. **Omitting `storageClassName` is not neutral.** It means "use the default class". Use
   `storageClassName: ""` when you really mean "no class, bind to a pre-made PV".

---

## Manifests in this folder

| File | Purpose |
| :--- | :--- |
| `00-namespace.yaml` | Namespace `hw13` |
| `01-emptydir-pod.yaml` | emptyDir, with a self-exit switch to force a container restart |
| `02-hostpath-pod.yaml` | hostPath on `/tmp/hw13-hostpath-data` |
| `03-static-pv.yaml` | Hand-made PV, class `hw13-manual`, `Retain` |
| `04-naive-pvc.yaml` | PVC with no `storageClassName` — captured by the default class |
| `05-static-pvc.yaml` | PVC that names `hw13-manual` and binds to the static PV |
| `06-static-pod.yaml` | Pod that mounts `static-pvc` |
| `07-dynamic-pvc.yaml` | PVC on `standard` — triggers dynamic provisioning |
| `08-dynamic-pod.yaml` | Pod that mounts `dynamic-pvc` |
| `09-storageclass.yaml` | Custom class `hw13-retain-sc`, `Retain` + `Immediate` (working) |
| `09b-storageclass-waitforfirstconsumer.yaml` | The `WaitForFirstConsumer` variant that minikube's provisioner cannot serve (7.2) |
| `10-retain-pvc.yaml` | PVC on `hw13-retain-sc` |
| `11-retain-pod.yaml` | Consumer Pod for `retain-pvc` |
| `12-accessmode-pvcs.yaml` | ROX / RWX / RWOP claims |
| `13-rwx-two-pods.yaml` | Two Pods sharing one RWX claim |
| `14-rwop-two-pods.yaml` | Two Pods contending for one RWOP claim |
| `15-rox-pod.yaml` | Pod that writes into a ROX claim |

## References

- Volumes — https://kubernetes.io/docs/concepts/storage/volumes/
- Persistent Volumes — https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- Storage Classes — https://kubernetes.io/docs/concepts/storage/storage-classes/
- Dynamic Provisioning — https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/
