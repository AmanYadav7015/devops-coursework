# Task 3 — journalctl · terminal transcript

> Real session captured on Ubuntu 24.04 in container `hw-t3`.
> Every command was executed; the output is verbatim.

[← Back to Task 3 — journalctl](README.md) · [Topic index](../README.md)

---

### 0. Prove this is a real systemd + journald environment (not a fake log file)

```console
root@ubuntu-hw:~# systemctl is-system-running
running

root@ubuntu-hw:~# journalctl --version
systemd 255 (255.4-1ubuntu8.17)
+PAM +AUDIT +SELINUX +APPARMOR +IMA +SMACK +SECCOMP +GCRYPT -GNUTLS +OPENSSL +ACL +BLKID +CURL +ELFUTILS +FIDO2 +IDN2 -IDN +IPTC +KMOD +LIBCRYPTSETUP +LIBFDISK +PCRE2 -PWQUALITY +P11KIT +QRENCODE +TPM2 +BZIP2 +LZ4 +XZ +ZLIB +ZSTD -BPF_FRAMEWORK -XKBCOMMON +UTMP +SYSVINIT default-hierarchy=unified

root@ubuntu-hw:~# hostnamectl 2>/dev/null | head -6
 Static hostname: ubuntu-hw
       Icon name: computer-container
         Chassis: container ☐
      Machine ID: ac2a3af98bbe47748816619e669976ff
         Boot ID: c22d0fdd55ab4cd6936edce54378118a
  Virtualization: docker
```

### 1. Viewing system logs -- the basics

```console
# --- first 20 lines of the whole journal (oldest first, chronological) ---
root@ubuntu-hw:~# journalctl --no-pager | head -20
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Journal started
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Runtime Journal (/run/log/journal/ac2a3af98bbe47748816619e669976ff) is 8.0M, max 158.7M, 150.7M free.
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Missed 267 kernel messages
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0b.0: BAR 0 [mem 0x280070000-0x28007ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0c.0: BAR 0 [mem 0x280080000-0x28008ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0d.0: BAR 0 [mem 0x280090000-0x28009ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0e.0: BAR 0 [mem 0x2800a0000-0x2800affff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:10.0: BAR 0 [mem 0x2800b0000-0x2800bffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0f.0: BAR 0 [mem 0x2800c0000-0x2800c7fff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:05.0: BAR 2 [mem 0x50000000-0x5000007f]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0e.0: BAR 2 [mem 0x50000080-0x500000ff]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:01.0: BAR 2 [mem 0x50000100-0x5000013f]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:06.0: BAR 2 [mem 0x50000140-0x5000017f]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:07.0: BAR 2 [mem 0x50000180-0x500001bf]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:08.0: BAR 2 [mem 0x500001c0-0x500001ff]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:09.0: BAR 2 [mem 0x50000200-0x5000023f]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0a.0: BAR 2 [mem 0x50000240-0x5000027f]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0b.0: BAR 2 [mem 0x50000280-0x500002bf]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0c.0: BAR 2 [mem 0x500002c0-0x500002ff]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0d.0: BAR 2 [mem 0x50000300-0x5000033f]: assigned

# --- last 15 entries (most recent), still oldest-to-newest within that window ---
root@ubuntu-hw:~# journalctl -n 15 --no-pager
Sep 02 16:49:03 ubuntu-hw systemd[1]: Started rsyslog.service - System Logging Service.
Sep 02 16:49:03 ubuntu-hw rsyslogd[78]: rsyslogd's userid changed to 101
Sep 02 16:49:03 ubuntu-hw systemd[1]: Started systemd-logind.service - User Login Management.
Sep 02 16:49:03 ubuntu-hw rsyslogd[78]: [origin software="rsyslogd" swVersion="8.2312.0" x-pid="78" x-info="https://www.rsyslog.com"] start
Sep 02 16:49:03 ubuntu-hw systemd[1]: Reached target multi-user.target - Multi-User System.
Sep 02 16:49:03 ubuntu-hw systemd[1]: Reached target graphical.target - Graphical Interface.
Sep 02 16:49:03 ubuntu-hw systemd[1]: Starting systemd-update-utmp-runlevel.service - Record Runlevel Change in UTMP...
Sep 02 16:49:03 ubuntu-hw systemd[1]: systemd-update-utmp-runlevel.service: Deactivated successfully.
Sep 02 16:49:03 ubuntu-hw systemd[1]: Finished systemd-update-utmp-runlevel.service - Record Runlevel Change in UTMP.
Sep 02 16:49:03 ubuntu-hw systemd[1]: Startup finished in 256ms.
Sep 02 16:49:03 ubuntu-hw systemd[1]: dmesg.service: Deactivated successfully.
Sep 02 16:51:32 ubuntu-hw dbus-daemon[66]: [system] Activating via systemd: service name='org.freedesktop.hostname1' unit='dbus-org.freedesktop.hostname1.service' requested by ':1.2' (uid=0 pid=161 comm="hostnamectl")
Sep 02 16:51:32 ubuntu-hw systemd[1]: Starting systemd-hostnamed.service - Hostname Service...
Sep 02 16:51:32 ubuntu-hw dbus-daemon[66]: [system] Successfully activated service 'org.freedesktop.hostname1'
Sep 02 16:51:32 ubuntu-hw systemd[1]: Started systemd-hostnamed.service - Hostname Service.

# --- last 10 entries, newest first (-r = reverse) ---
root@ubuntu-hw:~# journalctl -r -n 10 --no-pager
Sep 02 16:51:32 ubuntu-hw systemd[1]: Started systemd-hostnamed.service - Hostname Service.
Sep 02 16:51:32 ubuntu-hw dbus-daemon[66]: [system] Successfully activated service 'org.freedesktop.hostname1'
Sep 02 16:51:32 ubuntu-hw systemd[1]: Starting systemd-hostnamed.service - Hostname Service...
Sep 02 16:51:32 ubuntu-hw dbus-daemon[66]: [system] Activating via systemd: service name='org.freedesktop.hostname1' unit='dbus-org.freedesktop.hostname1.service' requested by ':1.2' (uid=0 pid=161 comm="hostnamectl")
Sep 02 16:49:03 ubuntu-hw systemd[1]: dmesg.service: Deactivated successfully.
Sep 02 16:49:03 ubuntu-hw systemd[1]: Startup finished in 256ms.
Sep 02 16:49:03 ubuntu-hw systemd[1]: Finished systemd-update-utmp-runlevel.service - Record Runlevel Change in UTMP.
Sep 02 16:49:03 ubuntu-hw systemd[1]: systemd-update-utmp-runlevel.service: Deactivated successfully.
Sep 02 16:49:03 ubuntu-hw systemd[1]: Starting systemd-update-utmp-runlevel.service - Record Runlevel Change in UTMP...
Sep 02 16:49:03 ubuntu-hw systemd[1]: Reached target graphical.target - Graphical Interface.
```

### 2. Boot logs

```console
# --- logs from the current boot only ---
root@ubuntu-hw:~# journalctl -b --no-pager | head -15
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Journal started
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Runtime Journal (/run/log/journal/ac2a3af98bbe47748816619e669976ff) is 8.0M, max 158.7M, 150.7M free.
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Missed 267 kernel messages
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0b.0: BAR 0 [mem 0x280070000-0x28007ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0c.0: BAR 0 [mem 0x280080000-0x28008ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0d.0: BAR 0 [mem 0x280090000-0x28009ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0e.0: BAR 0 [mem 0x2800a0000-0x2800affff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:10.0: BAR 0 [mem 0x2800b0000-0x2800bffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0f.0: BAR 0 [mem 0x2800c0000-0x2800c7fff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:05.0: BAR 2 [mem 0x50000000-0x5000007f]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0e.0: BAR 2 [mem 0x50000080-0x500000ff]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:01.0: BAR 2 [mem 0x50000100-0x5000013f]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:06.0: BAR 2 [mem 0x50000140-0x5000017f]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:07.0: BAR 2 [mem 0x50000180-0x500001bf]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:08.0: BAR 2 [mem 0x500001c0-0x500001ff]: assigned

# --- list every boot journald knows about (this container has one) ---
root@ubuntu-hw:~# journalctl --list-boots --no-pager
IDX BOOT ID                          FIRST ENTRY                 LAST ENTRY
  0 c22d0fdd55ab4cd6936edce54378118a Wed 2026-09-02 16:49:03 UTC Wed 2026-09-02 16:51:32 UTC
```

### 3. Time filtering

```console
# --- everything logged in the last 10 minutes ---
root@ubuntu-hw:~# journalctl --since "10 minutes ago" --no-pager | head -10
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Journal started
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Runtime Journal (/run/log/journal/ac2a3af98bbe47748816619e669976ff) is 8.0M, max 158.7M, 150.7M free.
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Missed 267 kernel messages
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0b.0: BAR 0 [mem 0x280070000-0x28007ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0c.0: BAR 0 [mem 0x280080000-0x28008ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0d.0: BAR 0 [mem 0x280090000-0x28009ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0e.0: BAR 0 [mem 0x2800a0000-0x2800affff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:10.0: BAR 0 [mem 0x2800b0000-0x2800bffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0f.0: BAR 0 [mem 0x2800c0000-0x2800c7fff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:05.0: BAR 2 [mem 0x50000000-0x5000007f]: assigned

# --- explicit --since/--until window (wide enough to catch container-start logs) ---
root@ubuntu-hw:~# journalctl --since "2026-09-02 00:00:00" --until "2026-09-03 00:00:00" --no-pager | head -10
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Journal started
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Runtime Journal (/run/log/journal/ac2a3af98bbe47748816619e669976ff) is 8.0M, max 158.7M, 150.7M free.
Sep 02 16:49:03 ubuntu-hw systemd-journald[22]: Missed 267 kernel messages
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0b.0: BAR 0 [mem 0x280070000-0x28007ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0c.0: BAR 0 [mem 0x280080000-0x28008ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0d.0: BAR 0 [mem 0x280090000-0x28009ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0e.0: BAR 0 [mem 0x2800a0000-0x2800affff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:10.0: BAR 0 [mem 0x2800b0000-0x2800bffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0f.0: BAR 0 [mem 0x2800c0000-0x2800c7fff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:05.0: BAR 2 [mem 0x50000000-0x5000007f]: assigned
```

### 4. Priority filtering (0 emerg .. 7 debug)

```console
# --- only error (and worse) messages ---
root@ubuntu-hw:~# journalctl -p err --no-pager | head
-- No entries --

# --- warning through error range ---
root@ubuntu-hw:~# journalctl -p warning..err --no-pager | head
Sep 02 16:49:03 ubuntu-hw kernel: netlink: 'initd': attribute type 4 has an invalid length.
Sep 02 16:49:03 ubuntu-hw kernel: fakeowner: loading out-of-tree module taints kernel.
Sep 02 16:49:03 ubuntu-hw systemd-sysctl[29]: Couldn't write '1' to 'kernel/yama/ptrace_scope', ignoring: No such file or directory
Sep 02 16:49:03 ubuntu-hw (cron)[65]: cron.service: Referenced but unset environment variable evaluates to an empty string: EXTRA_OPTS
```

### 5. Checking logs for a specific service -- nginx

```console
# --- make sure nginx is running and check its unit status first ---
root@ubuntu-hw:~# systemctl start nginx

root@ubuntu-hw:~# systemctl status nginx --no-pager
● nginx.service - A high performance web server and a reverse proxy server
     Loaded: loaded (/usr/lib/systemd/system/nginx.service; enabled; preset: enabled)
     Active: active (running) since Wed 2026-09-02 16:49:03 UTC; 2min 29s ago
       Docs: man:nginx(8)
    Process: 69 ExecStartPre=/usr/sbin/nginx -t -q -g daemon on; master_process on; (code=exited, status=0/SUCCESS)
    Process: 79 ExecStart=/usr/sbin/nginx -g daemon on; master_process on; (code=exited, status=0/SUCCESS)
   Main PID: 83 (nginx)
      Tasks: 16 (limit: 9520)
     Memory: 9.3M (peak: 10.7M)
        CPU: 27ms
     CGroup: /docker/a16ae842dd1c431dee435d22beca5d0b23c0be4b9044f50b8cb80a7c6d26ee0f/system.slice/nginx.service
             ├─83 "nginx: master process /usr/sbin/nginx -g daemon on; master_process on;"
             ├─84 "nginx: worker process"
             ├─85 "nginx: worker process"
             ├─86 "nginx: worker process"
             ├─87 "nginx: worker process"
             ├─88 "nginx: worker process"
             ├─90 "nginx: worker process"
             ├─91 "nginx: worker process"
             ├─92 "nginx: worker process"
             ├─93 "nginx: worker process"
             ├─94 "nginx: worker process"
             ├─95 "nginx: worker process"
             ├─96 "nginx: worker process"
             ├─97 "nginx: worker process"
             ├─98 "nginx: worker process"
             └─99 "nginx: worker process"

Sep 02 16:49:03 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:49:03 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.

# --- full journal history for the nginx unit ---
root@ubuntu-hw:~# journalctl -u nginx --no-pager
Sep 02 16:49:03 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:49:03 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.

# --- just the last 20 nginx log lines ---
root@ubuntu-hw:~# journalctl -u nginx -n 20 --no-pager
Sep 02 16:49:03 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:49:03 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.

# --- restart nginx to generate fresh log entries ---
root@ubuntu-hw:~# systemctl restart nginx

root@ubuntu-hw:~# sleep 1

# --- prove the fresh entries show up when filtering by recent time + unit ---
root@ubuntu-hw:~# journalctl -u nginx --since "1 minute ago" --no-pager
Sep 02 16:51:32 ubuntu-hw systemd[1]: Stopping nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:32 ubuntu-hw systemd[1]: nginx.service: Deactivated successfully.
Sep 02 16:51:32 ubuntu-hw systemd[1]: Stopped nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:32 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:32 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
```

### 6. Break nginx on purpose -- real error, captured in the journal

```console
# --- write an invalid directive into a new conf.d file ---
root@ubuntu-hw:~# echo "this_is_not_a_real_directive;" > /etc/nginx/conf.d/broken.conf

# --- test the config explicitly (this itself logs to the journal via nginx -t) ---
root@ubuntu-hw:~# nginx -t
2026/09/02 16:51:34 [emerg] 334#334: unknown directive "this_is_not_a_real_directive" in /etc/nginx/conf.d/broken.conf:1
nginx: configuration file /etc/nginx/nginx.conf test failed

# --- now try to restart the broken service ---
root@ubuntu-hw:~# systemctl restart nginx
Job for nginx.service failed because the control process exited with error code.
See "systemctl status nginx.service" and "journalctl -xeu nginx.service" for details.

# --- confirm systemd sees it as failed ---
root@ubuntu-hw:~# systemctl status nginx --no-pager
× nginx.service - A high performance web server and a reverse proxy server
     Loaded: loaded (/usr/lib/systemd/system/nginx.service; enabled; preset: enabled)
     Active: failed (Result: exit-code) since Wed 2026-09-02 16:51:34 UTC; 57ms ago
   Duration: 1.240s
       Docs: man:nginx(8)
    Process: 352 ExecStartPre=/usr/sbin/nginx -t -q -g daemon on; master_process on; (code=exited, status=1/FAILURE)
        CPU: 3ms

Sep 02 16:51:34 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:34 ubuntu-hw nginx[352]: 2026/09/02 16:51:34 [emerg] 352#352: unknown directive "this_is_not_a_real_directive" in /etc/nginx/conf.d/broken.conf:1
Sep 02 16:51:34 ubuntu-hw nginx[352]: nginx: configuration file /etc/nginx/nginx.conf test failed
Sep 02 16:51:34 ubuntu-hw systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE
Sep 02 16:51:34 ubuntu-hw systemd[1]: nginx.service: Failed with result 'exit-code'.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.

# --- see the real failure captured in the journal ---
root@ubuntu-hw:~# journalctl -u nginx -n 20 --no-pager
Sep 02 16:49:03 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:49:03 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:32 ubuntu-hw systemd[1]: Stopping nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:32 ubuntu-hw systemd[1]: nginx.service: Deactivated successfully.
Sep 02 16:51:32 ubuntu-hw systemd[1]: Stopped nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:32 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:32 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Stopping nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:34 ubuntu-hw systemd[1]: nginx.service: Deactivated successfully.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Stopped nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:34 ubuntu-hw nginx[352]: 2026/09/02 16:51:34 [emerg] 352#352: unknown directive "this_is_not_a_real_directive" in /etc/nginx/conf.d/broken.conf:1
Sep 02 16:51:34 ubuntu-hw nginx[352]: nginx: configuration file /etc/nginx/nginx.conf test failed
Sep 02 16:51:34 ubuntu-hw systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE
Sep 02 16:51:34 ubuntu-hw systemd[1]: nginx.service: Failed with result 'exit-code'.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
```

### 7. Fix it and show recovery in the journal

```console
# --- remove the bad config file ---
root@ubuntu-hw:~# rm -f /etc/nginx/conf.d/broken.conf

# --- config now validates clean ---
root@ubuntu-hw:~# nginx -t
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful

# --- restart should now succeed ---
root@ubuntu-hw:~# systemctl restart nginx

root@ubuntu-hw:~# systemctl status nginx --no-pager
● nginx.service - A high performance web server and a reverse proxy server
     Loaded: loaded (/usr/lib/systemd/system/nginx.service; enabled; preset: enabled)
     Active: active (running) since Wed 2026-09-02 16:51:34 UTC; 54ms ago
       Docs: man:nginx(8)
    Process: 394 ExecStartPre=/usr/sbin/nginx -t -q -g daemon on; master_process on; (code=exited, status=0/SUCCESS)
    Process: 395 ExecStart=/usr/sbin/nginx -g daemon on; master_process on; (code=exited, status=0/SUCCESS)
   Main PID: 397 (nginx)
      Tasks: 16 (limit: 9520)
     Memory: 9.5M (peak: 10.6M)
        CPU: 17ms
     CGroup: /docker/a16ae842dd1c431dee435d22beca5d0b23c0be4b9044f50b8cb80a7c6d26ee0f/system.slice/nginx.service
             ├─397 "nginx: master process /usr/sbin/nginx -g daemon on; master_process on;"
             ├─398 "nginx: worker process"
             ├─399 "nginx: worker process"
             ├─400 "nginx: worker process"
             ├─401 "nginx: worker process"
             ├─402 "nginx: worker process"
             ├─403 "nginx: worker process"
             ├─404 "nginx: worker process"
             ├─406 "nginx: worker process"
             ├─407 "nginx: worker process"
             ├─408 "nginx: worker process"
             ├─409 "nginx: worker process"
             ├─410 "nginx: worker process"
             ├─411 "nginx: worker process"
             ├─412 "nginx: worker process"
             └─413 "nginx: worker process"

Sep 02 16:51:34 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:34 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.

# --- the journal shows the failure AND the successful recovery back to back ---
root@ubuntu-hw:~# journalctl -u nginx -n 30 --no-pager
Sep 02 16:49:03 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:49:03 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:32 ubuntu-hw systemd[1]: Stopping nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:32 ubuntu-hw systemd[1]: nginx.service: Deactivated successfully.
Sep 02 16:51:32 ubuntu-hw systemd[1]: Stopped nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:32 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:32 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Stopping nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:34 ubuntu-hw systemd[1]: nginx.service: Deactivated successfully.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Stopped nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:34 ubuntu-hw nginx[352]: 2026/09/02 16:51:34 [emerg] 352#352: unknown directive "this_is_not_a_real_directive" in /etc/nginx/conf.d/broken.conf:1
Sep 02 16:51:34 ubuntu-hw nginx[352]: nginx: configuration file /etc/nginx/nginx.conf test failed
Sep 02 16:51:34 ubuntu-hw systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE
Sep 02 16:51:34 ubuntu-hw systemd[1]: nginx.service: Failed with result 'exit-code'.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:34 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
```

### 8. A second service -- cron

```console
root@ubuntu-hw:~# journalctl -u cron --no-pager | head
Sep 02 16:49:03 ubuntu-hw systemd[1]: Started cron.service - Regular background program processing daemon.
Sep 02 16:49:03 ubuntu-hw (cron)[65]: cron.service: Referenced but unset environment variable evaluates to an empty string: EXTRA_OPTS
Sep 02 16:49:03 ubuntu-hw cron[65]: (CRON) INFO (pidfile fd = 3)
Sep 02 16:49:03 ubuntu-hw cron[65]: (CRON) INFO (Running @reboot jobs)
```

### 9. Output formats

```console
# --- ISO-8601 timestamps ---
root@ubuntu-hw:~# journalctl -u nginx -n 3 -o short-iso --no-pager
2026-09-02T16:51:34+00:00 ubuntu-hw systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
2026-09-02T16:51:34+00:00 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
2026-09-02T16:51:34+00:00 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.

# --- full structured JSON of a single entry, pretty-printed ---
root@ubuntu-hw:~# journalctl -u nginx -n 1 -o json-pretty --no-pager | head -25
{
	"_COMM" : "systemd",
	"CODE_FUNC" : "job_emit_done_message",
	"_PID" : "1",
	"_HOSTNAME" : "ubuntu-hw",
	"_UID" : "0",
	"__SEQNUM" : "4277",
	"_CAP_EFFECTIVE" : "1ffffffffff",
	"_SYSTEMD_SLICE" : "-.slice",
	"UNIT" : "nginx.service",
	"_MACHINE_ID" : "ac2a3af98bbe47748816619e669976ff",
	"SYSLOG_IDENTIFIER" : "systemd",
	"_SYSTEMD_CGROUP" : "/init.scope",
	"__REALTIME_TIMESTAMP" : "1788367894393146",
	"SYSLOG_FACILITY" : "3",
	"JOB_ID" : "315",
	"INVOCATION_ID" : "baca07751c19482daaa2ea44763e1f13",
	"__CURSOR" : "s=25bb2b64fae349c7a4f2c6bed165baf5;i=10b5;b=c22d0fdd55ab4cd6936edce54378118a;m=3b61985ad9;t=65a82d912b13a;x=28ad6fe8aa5b7fb3",
	"JOB_RESULT" : "done",
	"_SOURCE_REALTIME_TIMESTAMP" : "1788367894393124",
	"_SYSTEMD_UNIT" : "init.scope",
	"_RUNTIME_SCOPE" : "system",
	"__SEQNUM_ID" : "25bb2b64fae349c7a4f2c6bed165baf5",
	"__MONOTONIC_TIMESTAMP" : "255040445145",
	"MESSAGE_ID" : "39f53479d3a045ac8e11786248231fbf",
```

### 10. Kernel messages

```console
root@ubuntu-hw:~# journalctl -k --no-pager | head -5
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0b.0: BAR 0 [mem 0x280070000-0x28007ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0c.0: BAR 0 [mem 0x280080000-0x28008ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0d.0: BAR 0 [mem 0x280090000-0x28009ffff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:0e.0: BAR 0 [mem 0x2800a0000-0x2800affff 64bit]: assigned
Sep 02 16:49:03 ubuntu-hw kernel: pci 0000:00:10.0: BAR 0 [mem 0x2800b0000-0x2800bffff 64bit]: assigned
```

### 11. Filtering by structured field

```console
# --- filter directly on the _SYSTEMD_UNIT field (bypasses -u's unit-name normalization) ---
root@ubuntu-hw:~# journalctl _SYSTEMD_UNIT=nginx.service -n 5 --no-pager
Sep 02 16:51:34 ubuntu-hw nginx[352]: 2026/09/02 16:51:34 [emerg] 352#352: unknown directive "this_is_not_a_real_directive" in /etc/nginx/conf.d/broken.conf:1
Sep 02 16:51:34 ubuntu-hw nginx[352]: nginx: configuration file /etc/nginx/nginx.conf test failed

# --- everything logged by PID 1 (systemd itself) ---
root@ubuntu-hw:~# journalctl _PID=1 -n 5 --no-pager
Sep 02 16:51:34 ubuntu-hw systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE
Sep 02 16:51:34 ubuntu-hw systemd[1]: nginx.service: Failed with result 'exit-code'.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
Sep 02 16:51:34 ubuntu-hw systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 02 16:51:34 ubuntu-hw systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
```

### 12. Disk usage and maintenance

```console
root@ubuntu-hw:~# journalctl --disk-usage
Archived and active journals take up 8.0M in the file system.

root@ubuntu-hw:~# journalctl --verify --no-pager | tail -3
PASS: /var/log/journal/ac2a3af98bbe47748816619e669976ff/system.journal

# --- vacuum commands (safe to actually run in this disposable container) ---
root@ubuntu-hw:~# journalctl --vacuum-time=2d
Vacuuming done, freed 0B of archived journals from /var/log/journal/ac2a3af98bbe47748816619e669976ff.
Vacuuming done, freed 0B of archived journals from /var/log/journal.
Vacuuming done, freed 0B of archived journals from /run/log/journal.

root@ubuntu-hw:~# journalctl --vacuum-size=50M
Vacuuming done, freed 0B of archived journals from /var/log/journal.
Vacuuming done, freed 0B of archived journals from /run/log/journal.
Vacuuming done, freed 0B of archived journals from /var/log/journal/ac2a3af98bbe47748816619e669976ff.
```

### 13. Persistent vs volatile storage

```console
# --- persistent journal directory (survives reboots) ---
root@ubuntu-hw:~# ls -la /var/log/journal
total 20
drwxr-sr-x+ 1 root systemd-journal 4096 Sep  2 16:49 .
drwxrwxr-x  1 root syslog          4096 Sep  2 16:49 ..
drwxr-sr-x+ 2 root systemd-journal 4096 Sep  2 16:49 ac2a3af98bbe47748816619e669976ff

root@ubuntu-hw:~# ls -la /var/log/journal/*/ 2>/dev/null | head -10
total 8204
drwxr-sr-x+ 2 root systemd-journal    4096 Sep  2 16:49 .
drwxr-sr-x+ 1 root systemd-journal    4096 Sep  2 16:49 ..
-rw-r-----+ 1 root systemd-journal 8388608 Sep  2 16:51 system.journal

# --- volatile journal directory (tmpfs, /run, wiped on reboot) ---
root@ubuntu-hw:~# ls -la /run/log/journal 2>&1
total 0
drwxr-sr-x 2 root systemd-journal 40 Sep  2 16:49 .
drwxr-xr-x 3 root root            60 Sep  2 16:49 ..

# --- the config knob that controls persistent vs volatile: Storage= ---
root@ubuntu-hw:~# grep -vE '^\s*#|^$' /etc/systemd/journald.conf
[Journal]
```
