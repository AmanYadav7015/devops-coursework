# Kubernetes Labs — Sessions 9 to 12

**Name:** Aman Yadav
**Roll Number:** 24bcs10183
**Year:** 2nd Year
**Batch:** A
**Run date:** 17 September 2026
**Cluster:** minikube v1.39.0, docker driver, Kubernetes **v1.37.0**, containerd 2.3.4, node `minikube` at 192.168.49.2

---

## Provenance

The course's official homework document covers **sessions 2-8 only** and contains nothing for the
Kubernetes sessions. The four assignment sets below were **derived from the material actually taught**
in `session9-k8s`, `session10-k8s-core-objects`, `session-11-kubernetes-services` and
`session-12-ingress-configmaps-secrets`, and are written in the same style as the official homework.
They are not official assignments.

---

## Sections

| # | Session | Write-up | Manifests | What it proves |
|---|---|---|---|---|
| 09 | [Architecture & First Cluster](09-architecture-first-cluster/README.md) | 1,393 lines | 2 | Control-plane anatomy, static pods proven three ways, and the full `kubectl apply` request path traced with `-v=6` and etcd |
| 10 | [Core Objects, Lifecycle & Strategies](10-core-objects-lifecycle-strategies/README.md) | 2,016 lines | 33 | All six pod states reproduced, probes changing endpoints and restarting containers, and the four deployment strategies measured for real downtime |
| 11 | [Services, DNS & Endpoints](11-services-dns-endpoints/README.md) | 1,750 lines | 11 | All five service types, the `ndots:5` search-list cost shown in tcpdump, and an empty-endpoints triage drill |
| 12 | [Ingress, ConfigMaps & Secrets](12-ingress-configmaps-secrets/README.md) | 2,031 lines | 11 | Env-var vs volume update behaviour timed side by side, and four distinct Ingress failures with their distinguishing signals |

7,190 lines of write-up, 57 manifests, every command executed against the live cluster above.

---

## Read this before running the labs on a Mac

The node IP is **not reachable from macOS**. Verified:

```bash
ping -c 3 192.168.49.2
curl --max-time 5 http://192.168.49.2/
```

```text
3 packets transmitted, 0 packets received, 100.0% packet loss
curl: (28) Connection timed out after 5009 milliseconds
```

With the docker driver the node is a container inside the Docker Desktop Linux VM, and macOS has no
route into that network. `docker ps` shows minikube publishing only the SSH, Docker, registry and
API-server ports — not port 80, and not any NodePort.

This matters because **`session-12-ingress-configmaps-secrets/lab.md` Part 6 instructs students to run
`curl -H "Host: yatri.local" http://$(minikube ip)/`**, which cannot work on a Mac. It is correct for
the Linux cloud instance the course targets. Three alternatives that do work here, in order of
faithfulness:

| Method | Command | Proves NodePort/Ingress? |
|---|---|---|
| Curl from inside the node | `minikube ssh -- curl http://192.168.49.2:<nodePort>` | Yes — same IP, same port, only a different shell |
| minikube service tunnel | `minikube service <svc> -n <ns> --url` | Yes, via a local tunnel |
| Port-forward | `kubectl port-forward svc/<svc> 8080:80` | No — bypasses the Service's nodePort entirely |

On Linux, the documented command works as written.

---

## Correction to the course material

`lab.md:563` tells students to run `echo "secretpassword" | base64` and **"Observe the output ends in
`Ao=`"**. It does not:

```bash
echo "secretpassword" | base64
echo "mypassword"     | base64
```

```text
c2VjcmV0cGFzc3dvcmQK
bXlwYXNzd29yZAo=
```

Only `mypassword` ends in `Ao=`. Whether the trailing newline produces an `Ao=` suffix depends on the
input length modulo 3, so the `Ao=` test silently passes for most passwords. `lab.md:157` is correct
because it is about `mypassword`; Part 8 reused the claim after switching the example. Note that
`lab.md:570` itself quotes the correct string `c2VjcmV0cGFzc3dvcmQK`, so the file contradicts itself.

Section 12 documents the real rule and reproduces the failure inside a running pod with `wc -c`
(14 vs 15 bytes) and `od -c` showing the literal `\n`.

---

## Cluster conventions

Each section worked in its own namespace (`hw09` … `hw12`) with its own NodePort range
(30090-30099, 30100-30109, 30110-30119, 30120-30129), so all four ran concurrently on one cluster
without collisions. Every namespace was deleted afterwards; the `ingress-nginx` addon is left enabled.

To rebuild the cluster these labs ran on:

```bash
minikube start --driver=docker --cpus=4 --memory=6144
minikube addons enable ingress
```
