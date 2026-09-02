# Docker — inspection & cleanup

> Real session — every command was executed and the output is verbatim.

[← Back](README.md)

---

### docker logs - startup messages from two of the apps

```console
aman@macbook docker-fundamentals % docker logs df-nodejs
Node.js Hello World server listening on port 3000

aman@macbook docker-fundamentals % docker logs df-python
# --- empty! Python buffers stdout when not attached to a TTY, so print()/
#     log_message() output was sitting in a buffer and never reached
#     `docker logs`, even though curl requests were served correctly.
#     Confirmed by re-running curl and checking logs again - still empty: ---

aman@macbook docker-fundamentals % curl -s http://localhost:18082 >/dev/null && docker logs df-python
# (no output)

# --- fix: add ENV PYTHONUNBUFFERED=1 to python-app/Dockerfile and rebuild
#     (see docker-a.txt for the rebuild). Re-checking logs on the new container: ---

aman@macbook docker-fundamentals % docker logs df-python
127.0.0.1 - - [02/Sep/2026 17:33:xx] "GET / HTTP/1.1" 200 -
```

### docker inspect --format - container IP address and port bindings

```console
# --- first attempt used {{.NetworkSettings.IPAddress}}, which is empty on
#     this Docker setup because containers attach via the named "bridge"
#     network entry rather than the legacy top-level field: ---

aman@macbook docker-fundamentals % docker inspect --format '{{.NetworkSettings.IPAddress}}' df-nodejs
template parsing error: template: :1:18: executing "" at <.NetworkSettings.IPAddress>: map has no entry for key "IPAddress"

# --- correct path for this Docker version: .NetworkSettings.Networks.bridge.IPAddress ---


aman@macbook docker-fundamentals % docker inspect --format '{{.Name}} IP={{.NetworkSettings.Networks.bridge.IPAddress}} Ports={{.NetworkSettings.Ports}}' df-nodejs
/df-nodejs IP=172.17.0.8 Ports=map[3000/tcp:[{0.0.0.0 18081} {:: 18081}]]
aman@macbook docker-fundamentals % docker inspect --format '{{.Name}} IP={{.NetworkSettings.Networks.bridge.IPAddress}} Ports={{.NetworkSettings.Ports}}' df-python
/df-python IP=172.17.0.7 Ports=map[5000/tcp:[{0.0.0.0 18082} {:: 18082}]]
aman@macbook docker-fundamentals % docker inspect --format '{{.Name}} IP={{.NetworkSettings.Networks.bridge.IPAddress}} Ports={{.NetworkSettings.Ports}}' df-java
/df-java IP=172.17.0.16 Ports=map[8080/tcp:[{0.0.0.0 18083} {:: 18083}]]
aman@macbook docker-fundamentals % docker inspect --format '{{.Name}} IP={{.NetworkSettings.Networks.bridge.IPAddress}} Ports={{.NetworkSettings.Ports}}' df-apache
/df-apache IP=172.17.0.12 Ports=map[80/tcp:[{0.0.0.0 18084} {:: 18084}]]
aman@macbook docker-fundamentals % docker inspect --format '{{.Name}} IP={{.NetworkSettings.Networks.bridge.IPAddress}} Ports={{.NetworkSettings.Ports}}' df-react
/df-react IP=172.17.0.11 Ports=map[80/tcp:[{0.0.0.0 18085} {:: 18085}]]
aman@macbook docker-fundamentals % docker inspect --format '{{.Name}} IP={{.NetworkSettings.Networks.bridge.IPAddress}} Ports={{.NetworkSettings.Ports}}' df-nginx
/df-nginx IP=172.17.0.13 Ports=map[80/tcp:[{0.0.0.0 18086} {:: 18086}]]
```

### docker exec - look inside a running container

```console
aman@macbook docker-fundamentals % docker exec df-nginx ls -la /usr/share/nginx/html
total 16
drwxr-xr-x    1 root     root          4096 Sep  2 17:30 .
drwxr-xr-x    1 root     root          4096 Aug 19 19:07 ..
-rw-r--r--    1 root     root           497 Aug 11 23:21 50x.html
-rw-r--r--    1 root     root           485 Sep  2 17:27 index.html

aman@macbook docker-fundamentals % docker exec df-nginx cat /etc/nginx/conf.d/default.conf
server {
    listen 80;
    server_name localhost;

    add_header X-Served-By "nginx-app-docker-homework" always;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location /health {
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }
}

aman@macbook docker-fundamentals % docker exec df-java ls -la /app
total 16
drwxr-xr-x 1 root root 4096 Sep  2 17:31 .
drwxr-xr-x 1 root root 4096 Sep  2 17:32 ..
-rw-r--r-- 1 root root 2468 Sep  2 17:29 HelloWorld$HelloHandler.class
-rw-r--r-- 1 root root 1707 Sep  2 17:29 HelloWorld.class

aman@macbook docker-fundamentals % docker exec df-java java -version
```

### docker stats --no-stream - live resource usage snapshot

```console
aman@macbook docker-fundamentals % docker stats --no-stream df-nodejs df-python df-java df-apache df-react df-nginx
CONTAINER ID   NAME        CPU %     MEM USAGE / LIMIT    MEM %     NET I/O           BLOCK I/O         PIDS
e7683ba01412   df-nodejs   0.00%     9.594MiB / 7.75GiB   0.12%     10.2kB / 3.41kB   8.19kB / 0B       7
20d6bd7875d1   df-python   0.02%     12.05MiB / 7.75GiB   0.15%     1.83kB / 1.17kB   754kB / 1.72MB    1
37438bc6a5ef   df-java     0.11%     27.1MiB / 7.75GiB    0.34%     3.96kB / 3.48kB   3.07MB / 135kB    20
e9a587857c07   df-apache   0.01%     7.832MiB / 7.75GiB   0.10%     10kB / 3.77kB     3.17MB / 4.1kB    82
25e3d2b91f3b   df-react    0.00%     12.32MiB / 7.75GiB   0.16%     10.2kB / 4.99kB   4.1kB / 12.3kB    16
5143c34a495e   df-nginx    0.00%     12.18MiB / 7.75GiB   0.15%     10.1kB / 4.15kB   12.3kB / 8.19kB   16
```

### Cleanup - stop and remove all six containers (images are kept)

```console
aman@macbook docker-fundamentals % docker stop df-nodejs df-python df-java df-apache df-react df-nginx
df-nodejs
df-python
df-java
df-apache
df-react
df-nginx

aman@macbook docker-fundamentals % docker rm df-nodejs df-python df-java df-apache df-react df-nginx
df-nodejs
df-python
df-java
df-apache
df-react
df-nginx

aman@macbook docker-fundamentals % docker ps -a --filter name=df-
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES

aman@macbook docker-fundamentals % docker images | grep -E 'REPOSITORY|^df-'
IMAGE                                                                                         ID             DISK USAGE   CONTENT SIZE   EXTRA
df-apache:1.0                                                                                 6c4b459f6748        105MB         21.1MB        
df-java:1.0                                                                                   f3ce876611a1        286MB         73.4MB        
df-nginx:1.0                                                                                  9d53a5be511e       92.8MB         26.2MB        
df-nodejs:1.0                                                                                 020b6db88d99        228MB         58.1MB        
df-python:1.0                                                                                 8285121e79b1       87.8MB         21.4MB        
df-react:1.0                                                                                  54e2417c8b9a       92.9MB         26.2MB        
```
