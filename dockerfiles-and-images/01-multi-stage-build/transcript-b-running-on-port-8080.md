# Multi-stage build — running on port 8080

> Real session — every command was executed and the output is verbatim.

[← Back](README.md)

---

```console
root@ubuntu-hw:~/01-multi-stage-build# docker run -d --name ms-app -p 18090:8080 ms-app:multistage
cbe6e719ba320c51c9c3f2c3a110d8a7fbad5a572579c4933d51411b7493d691

# --- Host port 18090 was chosen to avoid clashing with other homework
# --- sections running on this same machine; the container itself listens
# --- on 8080, satisfying "confirm the application is running on port 8080". ---

root@ubuntu-hw:~/01-multi-stage-build# docker ps --filter name=ms-app
CONTAINER ID   IMAGE               COMMAND   CREATED        STATUS        PORTS                                           NAMES
cbe6e719ba32   ms-app:multistage   "/app"    1 second ago   Up 1 second   0.0.0.0:18090->8080/tcp, [::]:18090->8080/tcp   ms-app
```

### Verifying the required string

```console
root@ubuntu-hw:~/01-multi-stage-build# curl -s http://localhost:18090
Hello World from Docker multi-stage build

# --- Exact match against the assignment's required text:
# --- "Hello World from Docker multi-stage build" ---

root@ubuntu-hw:~/01-multi-stage-build# curl -I http://localhost:18090
HTTP/1.1 200 OK
Content-Type: text/plain; charset=utf-8
Date: Wed, 02 Sep 2026 17:29:59 GMT
Content-Length: 41

root@ubuntu-hw:~/01-multi-stage-build# docker logs ms-app
2026/09/02 17:29:58 multi-stage demo app listening on :8080
```

### docker history - proof the runtime image really is just the binary

```console
root@ubuntu-hw:~/01-multi-stage-build# docker history ms-app:multistage
IMAGE          CREATED          CREATED BY                      SIZE      COMMENT
73c5490ed912   27 seconds ago   ENTRYPOINT ["/app"]             0B        buildkit.dockerfile.v0
<missing>      27 seconds ago   EXPOSE [8080/tcp]               0B        buildkit.dockerfile.v0
<missing>      27 seconds ago   COPY /out/app /app # buildkit   5.08MB    buildkit.dockerfile.v0
<missing>      27 seconds ago   USER 65534                      0B        buildkit.dockerfile.v0

# --- The entire final image is exactly one 5.08MB layer (the compiled Go
# --- binary) plus zero-byte metadata layers (USER/EXPOSE/ENTRYPOINT). No
# --- compiler, no shell, no package manager, no base OS at all - the
# --- FROM scratch base contributes 0 bytes. ---

# --- For contrast, the single-stage image's history (first few layers): ---
root@ubuntu-hw:~/01-multi-stage-build# docker history ms-app:singlestage | head -5
IMAGE          CREATED          CREATED BY                                      SIZE      COMMENT
901d99e7fe4f   16 seconds ago   ENTRYPOINT ["/app/app"]                         0B        buildkit.dockerfile.v0
<missing>      16 seconds ago   EXPOSE [8080/tcp]                               0B        buildkit.dockerfile.v0
<missing>      16 seconds ago   RUN /bin/sh -c CGO_ENABLED=0 GOOS=linux GOAR…   82.7MB    buildkit.dockerfile.v0
<missing>      16 seconds ago   COPY /out/app /app # buildkit                   12.3kB    buildkit.dockerfile.v0

# --- Even the RUN step that builds the binary adds 82.7MB to this image
# --- (Go's build cache under /root/.cache), on top of the golang:1.23-alpine
# --- base itself - none of which the multi-stage image carries. ---
```
