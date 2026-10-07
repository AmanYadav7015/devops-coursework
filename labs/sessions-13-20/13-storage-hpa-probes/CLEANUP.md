# Cleanup

Everything this homework created lived in the namespace `hw13`, plus two cluster-scoped objects
prefixed `hw13-` and some directories on the minikube node. All of it is removed below, with
verification.

---

## 1. Inventory before teardown

```bash
kubectl get all,pvc -n hw13
```

```text
NAME                          READY   STATUS    RESTARTS   AGE
pod/web-app-97bc5bcf6-dwx2q   1/1     Running   0          4m30s
pod/web-app-97bc5bcf6-rzp9s   1/1     Running   0          4m30s

NAME                  TYPE       CLUSTER-IP       EXTERNAL-IP   PORT(S)        AGE
service/web-service   NodePort   10.105.120.147   <none>        80:30130/TCP   30m

NAME                      READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/web-app   2/2     2            2           30m

NAME                                 DESIRED   CURRENT   READY   AGE
replicaset.apps/web-app-55db44c68f   0         0         0       9m30s
replicaset.apps/web-app-5654d6b4d9   0         0         0       8m8s
replicaset.apps/web-app-97bc5bcf6    2         2         2       30m

NAME                                              REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
horizontalpodautoscaler.autoscaling/web-app-hpa   Deployment/web-app   cpu: 1%/50%   2         5         2          30m

NAME                             STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
persistentvolumeclaim/web-data   Bound    pvc-6c679b7b-61a0-4d1c-97dc-d10c2d9fd376   500Mi      RWO            standard       <unset>                 31m
```

```bash
kubectl get pv | grep -E 'NAME|hw13'
```

```text
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM           STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
pvc-6c679b7b-61a0-4d1c-97dc-d10c2d9fd376   500Mi      RWO            Delete           Bound    hw13/web-data   standard       <unset>                          31m
```

The two `hw13-` prefixed cluster-scoped objects created during Task 1 — the PersistentVolume
`hw13-static-pv` and the StorageClass `hw13-retain-sc` — had already been removed at the end of that
task, along with the retained PV `pvc-e2b8c504-...` that `reclaimPolicy: Retain` deliberately left
behind.

---

## 2. Delete the namespace

```bash
kubectl delete namespace hw13
```

```text
namespace "hw13" deleted
```

This removes every namespaced object in one go: Pods, Deployments, ReplicaSets, Services, HPAs and
PVCs. Deleting the PVC `web-data` cascades to its PV, because the `standard` StorageClass uses
`reclaimPolicy: Delete`.

---

## 3. Verify

```bash
kubectl get ns | grep hw13 || echo "namespace hw13: gone"
kubectl get pv
kubectl get sc
kubectl get pv,sc,clusterrole,clusterrolebinding,ns 2>/dev/null | grep hw13 || echo "no hw13 cluster-scoped resources remain"
```

```text
namespace hw13: gone
--- PVs ---
No resources found
--- StorageClasses ---
NAME                 PROVISIONER                RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION   AGE
standard (default)   k8s.io/minikube-hostpath   Delete          Immediate           false                  19d
--- anything named hw13 anywhere cluster-scoped ---
no hw13 cluster-scoped resources remain
```

`kubectl get pv` returning `No resources found` confirms the dynamically provisioned PV was garbage
collected with its claim. The only StorageClass left is `standard`, which came with the cluster and
was not touched.

---

## 4. Clean the node filesystem

Two kinds of directory were created on the node: the `hostPath` paths used in Task 1, and the
`hostpath-provisioner` tree used by dynamic provisioning.

```bash
minikube ssh -- "ls -d /tmp/hw13-* 2>&1; ls /tmp/hostpath-provisioner/ 2>&1"
```

```text
ls: cannot access '/tmp/hw13-*': No such file or directory
hw10  hw13  hw14
```

The `/tmp/hw13-hostpath-data` and `/tmp/hw13-static-data` directories were already removed at the end
of Task 1. The provisioner left an empty `hw13` tree behind:

```bash
minikube ssh -- "sudo ls -laR /tmp/hostpath-provisioner/hw13"
```

```text
/tmp/hostpath-provisioner/hw13:
total 12
drwxr-xr-x 3 root root 4096 Oct  7 13:47 .
drwxr-xr-x 5 root root 4096 Oct  7 12:40 ..
drwxrwxrwx 2 root root 4096 Oct  7 12:36 retain-pvc

/tmp/hostpath-provisioner/hw13/retain-pvc:
total 8
drwxrwxrwx 2 root root 4096 Oct  7 12:36 .
drwxr-xr-x 3 root root 4096 Oct  7 13:47 ..
```

Worth noticing what this shows: `retain-pvc` is the claim from the `hw13-retain-sc` StorageClass,
the one with `reclaimPolicy: Retain`. Its Kubernetes objects were deleted long ago, but its
*directory* was never cleaned up — exactly the behaviour `Retain` promises, and exactly the kind of
orphaned storage that quietly accumulates cost on a real cloud provider. Every other PVC's directory
is already gone because those classes used `reclaimPolicy: Delete`.

```bash
minikube ssh -- "sudo rm -rf /tmp/hostpath-provisioner/hw13 && ls /tmp/hostpath-provisioner/ && ls -d /tmp/hw13-* 2>&1"
```

```text
hw10  hw14
ls: cannot access '/tmp/hw13-*': No such file or directory
```

Only other sessions' directories remain. Nothing belonging to this homework is left on the node.

---

## 5. Final state

```bash
kubectl get ns,pv,sc 2>/dev/null | grep -i hw13 || echo "clean: no hw13 resources in the cluster"
```

```text
clean: no hw13 resources in the cluster
```

The cluster, the `standard` StorageClass, the `metrics-server` addon and every other session's
resources were left exactly as they were found.
