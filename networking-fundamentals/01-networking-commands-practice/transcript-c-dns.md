# Networking — DNS

> Real session captured in container `net-t1`.
> Every command was executed; the output is verbatim.

[← Back](README.md)

---

```console
# --- dig: the full DNS query — question, answer, authority, additional sections ---
root@ubuntu-hw:~# dig google.com

; <<>> DiG 9.18.39-0ubuntu0.24.04.7-Ubuntu <<>> google.com
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 37038
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;google.com.			IN	A

;; ANSWER SECTION:
google.com.		103	IN	A	142.251.221.238

;; Query time: 3 msec
;; SERVER: 192.168.65.7#53(192.168.65.7) (UDP)
;; WHEN: Wed Sep 02 17:28:41 UTC 2026
;; MSG SIZE  rcvd: 54


# --- dig +short: just the resolved IP(s), nothing else — good for scripting ---
root@ubuntu-hw:~# dig +short google.com
142.251.221.238

# --- dig ... MX: mail-exchanger records for the domain ---
root@ubuntu-hw:~# dig google.com MX

; <<>> DiG 9.18.39-0ubuntu0.24.04.7-Ubuntu <<>> google.com MX
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 53897
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;google.com.			IN	MX

;; ANSWER SECTION:
google.com.		377	IN	MX	10 smtp.google.com.

;; Query time: 4367 msec
;; SERVER: 192.168.65.7#53(192.168.65.7) (UDP)
;; WHEN: Wed Sep 02 17:28:45 UTC 2026
;; MSG SIZE  rcvd: 69


# --- dig -x: reverse DNS lookup, IP -> PTR hostname ---
root@ubuntu-hw:~# dig -x 8.8.8.8

; <<>> DiG 9.18.39-0ubuntu0.24.04.7-Ubuntu <<>> -x 8.8.8.8
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 49456
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;8.8.8.8.in-addr.arpa.		IN	PTR

;; ANSWER SECTION:
8.8.8.8.in-addr.arpa.	4502	IN	PTR	dns.google.

;; Query time: 4111 msec
;; SERVER: 192.168.65.7#53(192.168.65.7) (UDP)
;; WHEN: Wed Sep 02 17:28:49 UTC 2026
;; MSG SIZE  rcvd: 82


# --- dig @server: bypass /etc/resolv.conf and ask a specific resolver directly (Cloudflare) ---
root@ubuntu-hw:~# dig @1.1.1.1 google.com

; <<>> DiG 9.18.39-0ubuntu0.24.04.7-Ubuntu <<>> @1.1.1.1 google.com
; (1 server found)
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 15174
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 4, ADDITIONAL: 4

;; QUESTION SECTION:
;google.com.			IN	A

;; ANSWER SECTION:
google.com.		24	IN	A	142.251.221.238

;; AUTHORITY SECTION:
google.com.		135087	IN	NS	ns4.google.com.
google.com.		135087	IN	NS	ns2.google.com.
google.com.		135087	IN	NS	ns1.google.com.
google.com.		135087	IN	NS	ns3.google.com.

;; ADDITIONAL SECTION:
ns4.google.com.		92167	IN	A	216.239.38.10
ns2.google.com.		147020	IN	A	216.239.34.10
ns1.google.com.		157359	IN	A	216.239.32.10
ns3.google.com.		150072	IN	A	216.239.36.10

;; Query time: 19 msec
;; SERVER: 1.1.1.1#53(1.1.1.1) (UDP)
;; WHEN: Wed Sep 02 17:28:50 UTC 2026
;; MSG SIZE  rcvd: 180


# --- nslookup: older, still-common interactive-style DNS lookup tool ---
root@ubuntu-hw:~# nslookup google.com
Server:		192.168.65.7
Address:	192.168.65.7#53

Non-authoritative answer:
Name:	google.com
Address: 142.251.221.238


# --- host: minimal, terse DNS lookup utility ---
root@ubuntu-hw:~# host google.com
google.com has address 142.251.221.238
google.com mail is handled by 10 smtp.google.com.

# --- host -t MX: same terse style, but for MX records, to compare against dig's MX section ---
root@ubuntu-hw:~# host -t MX google.com
google.com mail is handled by 10 smtp.google.com.
```
