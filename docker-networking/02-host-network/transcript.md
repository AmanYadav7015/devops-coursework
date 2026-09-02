# Docker networking — host network on macOS

> Real session — every command was executed and the output is verbatim.

[← Back](README.md)

---

```console
# Docker Hub's official "Apache2" image is published under the name "httpd".
[aman@macos ~]$ docker pull httpd:latest
latest: Pulling from library/httpd
fff91e36faf1: Pulling fs layer
bf7af0229701: Pulling fs layer
4f4fb700ef54: Pulling fs layer
01289bdb7344: Pulling fs layer
cea950926c89: Pulling fs layer
91eac6ee2743: Pulling fs layer
4f4fb700ef54: Already exists
fff91e36faf1: Download complete
01289bdb7344: Download complete
d461d957ad8a: Download complete
cea950926c89: Download complete
e78b009430d6: Download complete
91eac6ee2743: Download complete
bf7af0229701: Download complete
01289bdb7344: Pull complete
bf7af0229701: Pull complete
4f4fb700ef54: Pull complete
cea950926c89: Pull complete
fff91e36faf1: Pull complete
91eac6ee2743: Pull complete
Digest: sha256:979c38c2228d28c2edfd45c6e27dcee1c7b4a101a5526721ae8ece454e89e99e
Status: Downloaded newer image for httpd:latest
docker.io/library/httpd:latest
```

### Attempt 1: --network host, as the assignment literally asks for

```console
[aman@macos ~]$ docker run -d --name dn-apache --network host httpd:latest
15938554dd2fd33d829b647d500464a49320a86611824c0c913d38d5b03a427d

[aman@macos ~]$ docker ps --filter name=dn-apache
CONTAINER ID   IMAGE          COMMAND              CREATED                  STATUS                  PORTS     NAMES
15938554dd2f   httpd:latest   "httpd-foreground"   Less than a second ago   Up Less than a second             dn-apache


# --- try to reach it from macOS, exactly as the assignment expects ---
[aman@macos ~]$ curl -v http://localhost:80/ --max-time 5
* Host localhost:80 was resolved.
* IPv6: ::1
* IPv4: 127.0.0.1
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed

  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0*   Trying [::1]:80...
* connect to ::1 port 80 from ::1 port 55111 failed: Connection refused
*   Trying 127.0.0.1:80...
* connect to 127.0.0.1 port 80 from 127.0.0.1 port 55112 failed: Connection refused
* Failed to connect to localhost port 80 after 1 ms: Couldn't connect to server

  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
* Closing connection
curl: (7) Failed to connect to localhost port 80 after 1 ms: Couldn't connect to server


[aman@macos ~]$ curl -v http://127.0.0.1:80/ --max-time 5
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed

  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0*   Trying 127.0.0.1:80...
* connect to 127.0.0.1 port 80 from 127.0.0.1 port 55113 failed: Connection refused
* Failed to connect to 127.0.0.1 port 80 after 0 ms: Couldn't connect to server

  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
* Closing connection
curl: (7) Failed to connect to 127.0.0.1 port 80 after 0 ms: Couldn't connect to server
```

### Prove the server itself is fine — curl from INSIDE the container/VM

### Prove the server itself is fine — connect from INSIDE the container/VM

```console
# httpd's slim Debian image ships neither curl nor wget; use bash's built-in
# /dev/tcp to open a raw TCP socket and speak HTTP/1.0 by hand.
[aman@macos ~]$ docker exec dn-apache bash -c 'exec 3<>/dev/tcp/127.0.0.1/80; printf "GET / HTTP/1.0\r\n\r\n" >&3; cat <&3'
HTTP/1.1 200 OK
Date: Wed, 02 Sep 2026 17:36:19 GMT
Server: Apache/2.4.68 (Unix)
Last-Modified: Fri, 07 Nov 2025 08:23:08 GMT
ETag: "bf-642fce432f300"
Accept-Ranges: bytes
Content-Length: 191
Connection: close
Content-Type: text/html

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>It works! Apache httpd</title>
</head>
<body>
<p>It works!</p>
</body>
</html>

# --- verdict: Apache is listening and serving correctly INSIDE the Docker Desktop  ---
# --- Linux VM's network namespace (that's what --network host actually joined it   ---
# --- to). It is macOS's curl, running OUTSIDE that VM, that could never reach it.   ---
```

### Root cause: checked this Docker Desktop install for the opt-in "host networking" toggle (Settings -> Features in development)

```console
[aman@macos ~]$ docker version --format 'Client: {{.Client.Os}}/{{.Client.Arch}}   Server: {{.Server.Os}}/{{.Server.Arch}}'
Client: darwin/arm64   Server: linux/arm64

[aman@macos ~]$ grep -io 'hostnetworking[a-zA-Z0-9_": ]*' '/Users/aman/Library/Group Containers/group.com.docker/settings-store.json' || echo 'no hostNetworking key present in settings-store.json (feature not enabled on this install)'
no hostNetworking key present in settings-store.json (feature not enabled on this install)

# --- confirms the split: client is darwin/arm64 (macOS), server is linux/arm64      ---
# --- (the Docker Desktop VM). --network host attaches the container to the SERVER's ---
# --- (Linux VM's) network namespace, not macOS's. No "hostNetworking" opt-in is set ---
# --- in this install's settings-store.json, so Docker Desktop did not bridge that   ---
# --- VM-side port 80 out to the macOS loopback interface -> curl on macOS refused.  ---
[aman@macos ~]$ docker rm -f dn-apache
dn-apache
```

### Attempt 2: the working equivalent — explicit published port mapping

```console
# The task's real intent ("access Apache on port 80") is met with -p, which
# DOES cross the VM boundary (Docker Desktop's own port-forwarder handles it).
[aman@macos ~]$ docker run -d --name dn-apache --network bridge -p 80:80 httpd:latest
7d2287fcabc873d048723ea23b72214d551087b6c4caf1efc863b99ecb2f2963

[aman@macos ~]$ docker ps --filter name=dn-apache --format 'table {{.Names}}	{{.Status}}	{{.Ports}}'
NAMES       STATUS         PORTS
dn-apache   Up 6 seconds   0.0.0.0:80->80/tcp, [::]:80->80/tcp

[aman@macos ~]$ curl -s http://localhost:80/
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>It works! Apache httpd</title>
</head>
<body>
<p>It works!</p>
</body>
</html>

[aman@macos ~]$ curl -sI http://localhost:80/
HTTP/1.1 200 OK
Date: Wed, 02 Sep 2026 17:37:15 GMT
Server: Apache/2.4.68 (Unix)
Last-Modified: Fri, 07 Nov 2025 08:23:08 GMT
ETag: "bf-642fce432f300"
Accept-Ranges: bytes
Content-Length: 191
Content-Type: text/html



# --- port 80 IS a privileged port (<1024) on a real Linux/macOS kernel, normally    ---
# --- requiring root/CAP_NET_BIND_SERVICE to bind directly. It worked unprivileged   ---
# --- here because Docker Desktop's own port-forwarding daemon (running with its own ---
# --- elevated helper) owns the actual bind, not this macOS shell -> no sudo needed  ---
# --- from us. A plain `python3 -m http.server 80` as a normal user would fail with  ---
# --- 'Permission denied' on a real Linux host, confirming the rule still applies    ---
# --- underneath; Docker Desktop just absorbs it for us.                             ---
```

### Cleanup (Task 2)

```console
[aman@macos ~]$ docker rm -f dn-apache
dn-apache
```
