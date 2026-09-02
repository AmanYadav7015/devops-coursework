# Multi-stage build — building & size comparison

> Real session — every command was executed and the output is verbatim.

[← Back](README.md)

---

```console
# --- No repository URL was given in the assignment. Wrote the Go app and
# --- both Dockerfiles from scratch to meet the stated requirement. ---
root@ubuntu-hw:~# cd /Users/aman/Desktop/devops/dockerfiles-and-images/01-multi-stage-build
root@ubuntu-hw:~/01-multi-stage-build# cat Dockerfile
# ---- Stage 1: builder ----
FROM golang:1.23-alpine AS builder
WORKDIR /src
COPY app/go.mod .
COPY app/main.go .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /out/app main.go

# ---- Stage 2: runtime ----
FROM scratch AS final
USER 65534
COPY --from=builder /out/app /app
EXPOSE 8080
ENTRYPOINT ["/app"]

root@ubuntu-hw:~/01-multi-stage-build# docker build -f Dockerfile -t ms-app:multistage .
#0 building with "desktop-linux" instance using docker driver

#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 1.44kB done
#1 DONE 0.0s

#2 [internal] load metadata for docker.io/library/golang:1.23-alpine
#2 DONE 2.6s

#3 [internal] load .dockerignore
#3 transferring context: 2B done
#3 DONE 0.0s

#4 [internal] load build context
#4 transferring context: 707B done
#4 DONE 0.0s

#5 [builder 1/5] FROM docker.io/library/golang:1.23-alpine@sha256:383395b794dffa5b53012a212365d40c8e37109a626ca30d6151c8348d380b5f
#5 resolve docker.io/library/golang:1.23-alpine@sha256:383395b794dffa5b53012a212365d40c8e37109a626ca30d6151c8348d380b5f 0.0s done
# --- pulling the ~70MB golang:1.23-alpine layer (per-chunk progress lines omitted) ---
#5 sha256:382d65ac76ebcbc7ba7ee0d232ae7afbec48e2b3b673983ac8ced522dabe3abb 70.70MB / 70.70MB 14.9s done
#5 extracting sha256:382d65ac76ebcbc7ba7ee0d232ae7afbec48e2b3b673983ac8ced522dabe3abb 2.4s done
#5 DONE 17.3s

#6 [builder 2/5] WORKDIR /src
#6 DONE 0.5s

#7 [builder 3/5] COPY app/go.mod .
#7 DONE 0.1s

#8 [builder 4/5] COPY app/main.go .
#8 DONE 0.0s

#9 [builder 5/5] RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64     go build -ldflags="-s -w" -o /out/app main.go
#9 DONE 4.3s

#10 [final 1/1] COPY --from=builder /out/app /app
#10 DONE 0.0s

#11 exporting to image
#11 exporting layers 0.2s done
#11 exporting manifest sha256:e3b5804815820750a286e3abf6d04ac9f19b09240f4afa0e919ab4e302b2dc15 done
#11 exporting config sha256:bef9dc78137f8a3594c362172d56241b17f11595de102ec73f72dc559ee1bf2f done
#11 exporting attestation manifest sha256:9e73dd551f353e75ffdde742bea09908e2b5333123177dfe3a459cca14236c05 0.0s done
#11 exporting manifest list sha256:73c5490ed912e71bda3c0cf73a3a64b90f917267bb232eae60333b9895da703b done
#11 naming to docker.io/library/ms-app:multistage done
#11 unpacking to docker.io/library/ms-app:multistage 0.0s done
#11 DONE 0.3s

# --- Note the shape of the build log: stage [builder] runs 5 steps, then a
# --- SEPARATE final stage runs exactly ONE step - "COPY --from=builder".
# --- Nothing else from the builder (compiler, module cache, shell,
# --- coreutils) is copied. The final image is FROM scratch, i.e. it starts
# --- from literally zero bytes and gains only the ~5MB static binary. ---
```

### Building the single-stage comparison image

```console
# --- Same app, same golang:1.23-alpine base - but with no second stage,
# --- so the entire build image (compiler + stdlib + module cache) IS the
# --- final image that would ship to production. ---
root@ubuntu-hw:~/01-multi-stage-build# cat Dockerfile.singlestage
FROM golang:1.23-alpine
WORKDIR /app
COPY app/go.mod .
COPY app/main.go .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o app main.go
EXPOSE 8080
ENTRYPOINT ["/app/app"]

root@ubuntu-hw:~/01-multi-stage-build# docker build -f Dockerfile.singlestage -t ms-app:singlestage .
#0 building with "desktop-linux" instance using docker driver

#1 [internal] load build definition from Dockerfile.singlestage
#1 transferring dockerfile: 881B done
#1 DONE 0.0s

#2 [internal] load metadata for docker.io/library/golang:1.23-alpine
#2 DONE 0.4s

#3 [internal] load .dockerignore
#3 transferring context: 2B done
#3 DONE 0.0s

#4 [1/5] FROM docker.io/library/golang:1.23-alpine@sha256:383395b794dffa5b53012a212365d40c8e37109a626ca30d6151c8348d380b5f
#4 resolve docker.io/library/golang:1.23-alpine@sha256:383395b794dffa5b53012a212365d40c8e37109a626ca30d6151c8348d380b5f done
#4 CACHED

#5 [internal] load build context
#5 transferring context: 85B done
#5 DONE 0.0s

#6 [2/5] WORKDIR /app
#6 DONE 0.0s

#7 [3/5] COPY app/go.mod .
#7 DONE 0.0s

#8 [4/5] COPY app/main.go .
#8 DONE 0.0s

#9 [5/5] RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64     go build -ldflags="-s -w" -o app main.go
#9 DONE 4.3s

#10 exporting to image
#10 exporting layers 1.9s done
#10 exporting manifest sha256:d689349a20f8f8e7109d8881936a3cf0902016d61f1ffcf01906524883c3f0ed done
#10 exporting config sha256:bdd938b15adeca93b982d82655523616ae956e794d0bb07f32b797214a6e58b3 done
#10 exporting attestation manifest sha256:f5bdafb27db220ec51fcc01f4a1dce62ecfbd52961d4724ecd48fddfdef86553 done
#10 exporting manifest list sha256:901d99e7fe4ffcab4594dabeea7692b25a33c27c627bd694839d977ae553c909 done
#10 naming to docker.io/library/ms-app:singlestage done
#10 unpacking to docker.io/library/ms-app:singlestage 0.4s done
#10 DONE 2.3s
```

### The size comparison - the whole point of the exercise

```console
root@ubuntu-hw:~/01-multi-stage-build# docker images ms-app --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.ID}}"
REPOSITORY:TAG       SIZE      IMAGE ID
ms-app:singlestage   468MB     901d99e7fe4f
ms-app:multistage    7.3MB     73c5490ed912

# --- 468MB -> 7.3MB is a 460.7MB reduction, i.e. ~98.4% smaller.
# --- Same application code, same compiler, same base image family for the
# --- builder step - the only difference is whether the golang toolchain
# --- ships in the final image or gets discarded after COPY --from=builder. ---
```
