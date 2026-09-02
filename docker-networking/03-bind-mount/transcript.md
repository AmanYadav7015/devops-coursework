# Docker networking — bind mount live reload

> Real session — every command was executed and the output is verbatim.

[← Back](README.md)

---

```console
[aman@macos ~]$ mkdir -p /Users/aman/Desktop/devops/docker-networking/03-bind-mount/site

[aman@macos ~]$ printf 'Hello students' > /Users/aman/Desktop/devops/docker-networking/03-bind-mount/site/index.html

[aman@macos ~]$ cat /Users/aman/Desktop/devops/docker-networking/03-bind-mount/site/index.html
Hello students
```

### Run nginx with the folder bind-mounted read-only into the doc root

```console
[aman@macos ~]$ docker run -d --name dn-nginx-bind -p 18103:80 -v /Users/aman/Desktop/devops/docker-networking/03-bind-mount/site:/usr/share/nginx/html:ro nginx:alpine
c1d651722ceff22320f286c2b401d3a5babc5f2d4dcc6ce70e3ac0a43227ed6c


# --- first curl: content served from the bind-mounted file ---
[aman@macos ~]$ curl -s http://localhost:18103/
Hello students
```

### Modify the file from macOS, WITHOUT touching the container at all

```console
[aman@macos ~]$ printf 'Hello students - updated at %s' "$(date)" > /Users/aman/Desktop/devops/docker-networking/03-bind-mount/site/index.html

[aman@macos ~]$ cat /Users/aman/Desktop/devops/docker-networking/03-bind-mount/site/index.html
Hello students - updated at Wed Sep  2 23:07:50 IST 2026

# --- second curl, no restart of dn-nginx-bind happened -> live propagation ---
[aman@macos ~]$ docker ps --filter name=dn-nginx-bind --format '{{.Names}} up-since={{.RunningFor}}'
dn-nginx-bind up-since=9 seconds ago

[aman@macos ~]$ curl -s http://localhost:18103/
Hello students - updated at Wed Sep  2 23:07:50 IST 2026

# --- restore the deliverable file to the assignment's exact required content ---
[aman@macos ~]$ printf 'Hello students' > /Users/aman/Desktop/devops/docker-networking/03-bind-mount/site/index.html

[aman@macos ~]$ curl -s http://localhost:18103/
Hello students
```

### Real mount metadata — what docker actually recorded for this mount

```console
[aman@macos ~]$ docker inspect --format '{{json .Mounts}}' dn-nginx-bind | python3 -m json.tool
[
    {
        "Type": "bind",
        "Source": "/Users/aman/Desktop/devops/docker-networking/03-bind-mount/site",
        "Destination": "/usr/share/nginx/html",
        "Mode": "ro",
        "RW": false,
        "Propagation": "rprivate"
    }
]
```

### Contrast: a NAMED VOLUME instead of a bind mount

```console
[aman@macos ~]$ docker volume create dn-demo-vol
dn-demo-vol

[aman@macos ~]$ docker volume inspect dn-demo-vol
[
    {
        "CreatedAt": "2026-09-02T17:38:05Z",
        "Driver": "local",
        "Labels": null,
        "Mountpoint": "/var/lib/docker/volumes/dn-demo-vol/_data",
        "Name": "dn-demo-vol",
        "Options": null,
        "Scope": "local"
    }
]


# --- write into the named volume THROUGH a container (Docker owns this storage; ---
# --- we don't address it by a macOS path the way we did the bind mount) ---
[aman@macos ~]$ docker run --rm -v dn-demo-vol:/data alpine:latest sh -c "echo 'stored in a named volume' > /data/vol.txt && cat /data/vol.txt"
stored in a named volume

[aman@macos ~]$ docker run --name dn-nginx-vol -d -v dn-demo-vol:/usr/share/nginx/html nginx:alpine
8fa69486c70b178227d5632dade5e3e0a1f64f778f5fc77c6fecb64bd9e279fd

[aman@macos ~]$ docker inspect --format '{{json .Mounts}}' dn-nginx-vol | python3 -m json.tool
[
    {
        "Type": "volume",
        "Name": "dn-demo-vol",
        "Source": "/var/lib/docker/volumes/dn-demo-vol/_data",
        "Destination": "/usr/share/nginx/html",
        "Driver": "local",
        "Mode": "z",
        "RW": true,
        "Propagation": ""
    }
]

# --- note: the volume's Source is a path INSIDE the Docker Desktop Linux VM        ---
# --- (/var/lib/docker/volumes/...), not a macOS path — unlike the bind mount, whose ---
# --- Source was our real macOS folder. That's the core difference in practice.     ---
```

### Cleanup (Task 3)

```console
[aman@macos ~]$ docker rm -f dn-nginx-bind dn-nginx-vol
dn-nginx-bind
dn-nginx-vol

[aman@macos ~]$ docker volume rm dn-demo-vol
dn-demo-vol
```
