# Docker — running & verifying Hello World

> Real session — every command was executed and the output is verbatim.

[← Back](README.md)

---

```console
aman@macbook docker-fundamentals % docker run -d --name df-nodejs -p 18081:3000 df-nodejs:1.0
e7683ba014123e083bf76f9b29db49adea5d5442bb186880f06e43e75a8e8d0e

aman@macbook docker-fundamentals % docker run -d --name df-python -p 18082:5000 df-python:1.0
98cec450a066d85eeddfc232c56adc739f84cbf6b2b09aa47909a2f24a0da5df

aman@macbook docker-fundamentals % docker run -d --name df-java -p 18083:8080 df-java:1.0
5e531ea16c95b014513820d99f69680a3eec491ba4309c50e14ff8bc7f11a456

aman@macbook docker-fundamentals % docker run -d --name df-apache -p 18084:80 df-apache:1.0
e9a587857c0774f9f909656d3fc35efa7bbcb8e70d98402a218acc224368d90d

aman@macbook docker-fundamentals % docker run -d --name df-react -p 18085:80 df-react:1.0
25e3d2b91f3bd9b8d51945d6d0c24b6b1df4edb39965c7f0e98e79b9bda452a5

aman@macbook docker-fundamentals % docker run -d --name df-nginx -p 18086:80 df-nginx:1.0
5143c34a495ef48bcc0e88b559a14fd2dfb059fdefc2c2c0f9dc6c30a14babf9

# --- df-java initially crashed (NoClassDefFoundError) - see docker-a.txt for the
#     root cause (javac's nested-class .class file wasn't copied) and the fix.
#     Re-running with the rebuilt image: ---

aman@macbook docker-fundamentals % docker run -d --name df-java -p 18083:8080 df-java:1.0
37438bc6a5efc005ef893115745aa8bfd246697728f732891b91a590ed722c6a
```

### All six containers running

```console
aman@macbook docker-fundamentals % docker ps --filter name=df-
CONTAINER ID   IMAGE           COMMAND                  CREATED              STATUS              PORTS                                           NAMES
37438bc6a5ef   df-java:1.0     "/__cacert_entrypoin…"   7 seconds ago        Up 6 seconds        0.0.0.0:18083->8080/tcp, [::]:18083->8080/tcp   df-java
5143c34a495e   df-nginx:1.0    "/docker-entrypoint.…"   About a minute ago   Up About a minute   0.0.0.0:18086->80/tcp, [::]:18086->80/tcp       df-nginx
25e3d2b91f3b   df-react:1.0    "/docker-entrypoint.…"   About a minute ago   Up About a minute   0.0.0.0:18085->80/tcp, [::]:18085->80/tcp       df-react
e9a587857c07   df-apache:1.0   "httpd-foreground"       About a minute ago   Up About a minute   0.0.0.0:18084->80/tcp, [::]:18084->80/tcp       df-apache
98cec450a066   df-python:1.0   "python app.py"          About a minute ago   Up About a minute   0.0.0.0:18082->5000/tcp, [::]:18082->5000/tcp   df-python
e7683ba01412   df-nodejs:1.0   "docker-entrypoint.s…"   About a minute ago   Up About a minute   0.0.0.0:18081->3000/tcp, [::]:18081->3000/tcp   df-nodejs

aman@macbook docker-fundamentals % docker images | grep -E 'REPOSITORY|IMAGE ID|^df-'
IMAGE                                                                                         ID             DISK USAGE   CONTENT SIZE   EXTRA
df-apache:1.0                                                                                 6c4b459f6748        105MB         21.1MB   U    
df-java:1.0                                                                                   f3ce876611a1        286MB         73.4MB   U    
df-nginx:1.0                                                                                  9d53a5be511e       92.8MB         26.2MB   U    
df-nodejs:1.0                                                                                 020b6db88d99        228MB         58.1MB   U    
df-python:1.0                                                                                 f1e8b23353d3       87.8MB         21.4MB   U    
df-react:1.0                                                                                  54e2417c8b9a       92.9MB         26.2MB   U    
```

### curl verification - every app must show 'Hello World' in the real HTML

```console
# --- nodejs (host port 18081) ---

aman@macbook docker-fundamentals % curl -s http://localhost:18081 | grep -i 'hello world'
  <title>Node.js Hello World</title>
  <h1>Hello World</h1>

aman@macbook docker-fundamentals % curl -I http://localhost:18081
HTTP/1.1 200 OK
Content-Type: text/html
Date: Wed, 02 Sep 2026 17:32:20 GMT
Connection: keep-alive
Keep-Alive: timeout=5


# --- python (host port 18082) ---

aman@macbook docker-fundamentals % curl -s http://localhost:18082 | grep -i 'hello world'
  <title>Python Hello World</title>
  <h1>Hello World</h1>

aman@macbook docker-fundamentals % curl -I http://localhost:18082
HTTP/1.0 501 Unsupported method ('HEAD')
Server: BaseHTTP/0.6 Python/3.12.14
Date: Wed, 02 Sep 2026 17:32:20 GMT
Connection: close
Content-Type: text/html;charset=utf-8
Content-Length: 357


# --- java (host port 18083) ---

aman@macbook docker-fundamentals % curl -s http://localhost:18083 | grep -i 'hello world'
<head><meta charset="UTF-8"><title>Java Hello World</title>
<h1>Hello World</h1>

aman@macbook docker-fundamentals % curl -I http://localhost:18083
HTTP/1.1 200 OK
Date: Wed, 02 Sep 2026 17:32:20 GMT
Content-type: text/html; charset=utf-8


# --- apache (host port 18084) ---

aman@macbook docker-fundamentals % curl -s http://localhost:18084 | grep -i 'hello world'
  <title>Apache Hello World</title>
  <h1>Hello World</h1>

aman@macbook docker-fundamentals % curl -I http://localhost:18084
HTTP/1.1 200 OK
Date: Wed, 02 Sep 2026 17:32:20 GMT
Server: Apache/2.4.68 (Unix)
Last-Modified: Wed, 02 Sep 2026 17:27:48 GMT
ETag: "1ed-65a835aa14d00"
Accept-Ranges: bytes
Content-Length: 493
Content-Type: text/html


# --- react (host port 18085) ---

aman@macbook docker-fundamentals % curl -s http://localhost:18085 | grep -i 'hello world'
  <title>React Hello World</title>
    This initial markup (with "Hello World" already in it) is what curl / view-source
    which renders the same "Hello World" text from the App component.
    <h1>Hello World</h1>

aman@macbook docker-fundamentals % curl -I http://localhost:18085
HTTP/1.1 200 OK
Server: nginx/1.31.4
Date: Wed, 02 Sep 2026 17:32:20 GMT
Content-Type: text/html
Content-Length: 820
Last-Modified: Wed, 02 Sep 2026 17:28:44 GMT
Connection: keep-alive
ETag: "6a985ccc-334"
Accept-Ranges: bytes


# --- nginx (host port 18086) ---

aman@macbook docker-fundamentals % curl -s http://localhost:18086 | grep -i 'hello world'
  <title>Nginx Hello World</title>
  <h1>Hello World</h1>

aman@macbook docker-fundamentals % curl -I http://localhost:18086
HTTP/1.1 200 OK
Server: nginx/1.31.4
Date: Wed, 02 Sep 2026 17:32:20 GMT
Content-Type: text/html
Content-Length: 485
Last-Modified: Wed, 02 Sep 2026 17:27:58 GMT
Connection: keep-alive
ETag: "6a985c9e-1e5"
X-Served-By: nginx-app-docker-homework
Accept-Ranges: bytes
```
