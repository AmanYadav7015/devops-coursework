# Networking — ports, sockets & HTTP

> Real session captured in container `net-t1`.
> Every command was executed; the output is verbatim.

[← Back](README.md)

---

```console
# --- start nginx inside the container so we have something listening on :80 ---
root@ubuntu-hw:~# service nginx start && sleep 1
 * Starting nginx nginx
   ...done.

# --- ss -tuln: TCP(t)+UDP(u) LISTEN(l) sockets, numeric(n) ports/addresses ---
root@ubuntu-hw:~# ss -tuln
Netid State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*          
tcp   LISTEN 0      511             [::]:80           [::]:*          

# --- ss -tulnp: same, plus (p)rocess owning each socket — needs root, which we have ---
root@ubuntu-hw:~# ss -tulnp
Netid State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess                        
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*    users:(("nginx",pid=952,fd=5))
tcp   LISTEN 0      511             [::]:80           [::]:*    users:(("nginx",pid=952,fd=6))

# --- netstat -tuln: legacy net-tools equivalent of ss -tuln ---
root@ubuntu-hw:~# netstat -tuln
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State      
tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN     
tcp6       0      0 :::80                   :::*                    LISTEN     

# --- curl -I: send the request, print only the response headers ---
root@ubuntu-hw:~# curl -I http://localhost
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed

  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
  0   615    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
HTTP/1.1 200 OK
Server: nginx/1.24.0 (Ubuntu)
Date: Wed, 02 Sep 2026 17:28:56 GMT
Content-Type: text/html
Content-Length: 615
Last-Modified: Wed, 02 Sep 2026 16:46:29 GMT
Connection: keep-alive
ETag: "6a9852e5-267"
Accept-Ranges: bytes


# --- curl -sv ... -o /dev/null: verbose mode shows the connect + request + response headers; body is thrown away ---
root@ubuntu-hw:~# curl -sv http://localhost -o /dev/null
* Host localhost:80 was resolved.
* IPv6: ::1
* IPv4: 127.0.0.1
*   Trying [::1]:80...
* Connected to localhost (::1) port 80
> GET / HTTP/1.1
> Host: localhost
> User-Agent: curl/8.5.0
> Accept: */*
> 
< HTTP/1.1 200 OK
< Server: nginx/1.24.0 (Ubuntu)
< Date: Wed, 02 Sep 2026 17:28:56 GMT
< Content-Type: text/html
< Content-Length: 615
< Last-Modified: Wed, 02 Sep 2026 16:46:29 GMT
< Connection: keep-alive
< ETag: "6a9852e5-267"
< Accept-Ranges: bytes
< 
{ [615 bytes data]
* Connection #0 to host localhost left intact

# --- nc -zv: TCP connect-scan a port that IS open -> "succeeded" ---
root@ubuntu-hw:~# nc -zv localhost 80
Connection to localhost (::1) 80 port [tcp/http] succeeded!

# --- nc -zv: TCP connect-scan a port that is NOT listening -> real "Connection refused" ---
root@ubuntu-hw:~# nc -zv localhost 9999
nc: connect to localhost (::1) port 9999 (tcp) failed: Connection refused
nc: connect to localhost (127.0.0.1) port 9999 (tcp) failed: Connection refused
```

### Packet capture: watching the HTTP request actually leave the wire

```console
# --- tcpdump backgrounded with -c 5 (self-limiting, exits after 5 packets), ---
# --- then a curl fires 1s later to generate the traffic, then `wait` blocks ---
# --- until tcpdump's own packet-count limit ends it — nothing left running. ---
root@ubuntu-hw:~# tcpdump -i lo -c 5 -n port 80 & sleep 1; curl -s localhost >/dev/null; wait
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on lo, link-type EN10MB (Ethernet), snapshot length 262144 bytes
5 packets captured
20 packets received by filter
0 packets dropped by kernel
17:28:58.001261 IP6 ::1.53786 > ::1.80: Flags [S], seq 2081888073, win 65476, options [mss 65476,sackOK,TS val 109792286 ecr 0,nop,wscale 7], length 0
17:28:58.001282 IP6 ::1.80 > ::1.53786: Flags [S.], seq 653240365, ack 2081888074, win 65464, options [mss 65476,sackOK,TS val 109792286 ecr 109792286,nop,wscale 7], length 0
17:28:58.001290 IP6 ::1.53786 > ::1.80: Flags [.], ack 1, win 512, options [nop,nop,TS val 109792286 ecr 109792286], length 0
17:28:58.001340 IP6 ::1.53786 > ::1.80: Flags [P.], seq 1:73, ack 1, win 512, options [nop,nop,TS val 109792286 ecr 109792286], length 72: HTTP: GET / HTTP/1.1
17:28:58.001343 IP6 ::1.80 > ::1.53786: Flags [.], ack 73, win 511, options [nop,nop,TS val 109792286 ecr 109792286], length 0
```
