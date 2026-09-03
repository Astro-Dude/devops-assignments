# Docker Networking & Volumes — Homework

All four tasks below were performed on a live Docker engine. Every code block is
**real captured output**.

---

## Task 1 — Docker Container Networking

### The topology built

```
                    ┌──────────────────────────────────────┐
                    │      frontend-net  172.18.0.0/16     │
                    │                                      │
                    │   ┌────────────┐    ┌────────────┐   │
                    │   │  frontend  │◄──►│            │   │
                    │   │   nginx    │    │            │   │
                    │   │ 172.18.0.2 │    │            │   │
                    │   └────────────┘    │            │   │
                    └─────────────────────┤  backend   ├───┘
                                          │   alpine   │
                    ┌─────────────────────┤            ├───┐
                    │   ┌────────────┐    │ .18.0.3    │   │
                    │   │  database  │◄──►│ .19.0.3    │   │
                    │   │  mysql:8   │    │            │   │
                    │   │ 172.19.0.2 │    │            │   │
                    │   └────────────┘    └────────────┘   │
                    │      backend-net   172.19.0.0/16     │
                    └──────────────────────────────────────┘

                    ┌──────────────────────────────────────┐
                    │   monitoring-net  172.20.0.0/16      │
                    │           (created, empty)           │
                    └──────────────────────────────────────┘

  frontend  <-->  backend   OK   (share frontend-net)
  backend   <-->  database  OK   (share backend-net)
  frontend   X    database  BLOCKED - no shared network
```

`backend` is deliberately attached to **two** networks, making it the only
container that can talk to both tiers. This is the standard three-tier pattern:
the database is never reachable from the public-facing layer.

### Commands

```bash
docker network create frontend-net
docker network create backend-net
docker network create monitoring-net

docker run -d --name frontend --network frontend-net nginx:alpine
docker run -d --name database --network backend-net \
    -e MYSQL_ROOT_PASSWORD=rootpass -e MYSQL_DATABASE=appdb mysql:8.0
docker run -d --name backend  --network frontend-net alpine:3.20 sleep 3600

# attach backend to a SECOND network
docker network connect backend-net backend
```

### Setup and topology output

```console
==================== STEP 1: CREATE 3 NETWORKS ====================
$ docker network create frontend-net
abddc850ee2cd0492912837a38cfac599e84c17f7fc7e803db66cbbc277ceeee

$ docker network create backend-net
5975525ecc33569688dbccc98bd64ce8c5e7f9b8d38f9bfe57ecd8d85be4fa73

$ docker network create monitoring-net
3d62a591036193c57ed4485144e3c40d22fac858e3c08e56b7dd5b49651973d6

$ docker network ls
NETWORK ID     NAME             DRIVER    SCOPE
5975525ecc33   backend-net      bridge    local
26d7fe568cbf   bridge           bridge    local
abddc850ee2c   frontend-net     bridge    local
7938ec610668   host             host      local
3d62a5910361   monitoring-net   bridge    local
0637bdf34f37   none             null      local

==================== STEP 2: INSPECT THE SUBNETS ASSIGNED ====================
$ docker network inspect frontend-net --format 'frontend-net  driver={{.Driver}}  subnet={{range .IPAM.Config}}{{.Subnet}}{{end}}'
frontend-net  driver=bridge  subnet=172.18.0.0/16

$ docker network inspect backend-net --format 'backend-net   driver={{.Driver}}  subnet={{range .IPAM.Config}}{{.Subnet}}{{end}}'
backend-net   driver=bridge  subnet=172.19.0.0/16

$ docker network inspect monitoring-net --format 'monitoring-net driver={{.Driver}} subnet={{range .IPAM.Config}}{{.Subnet}}{{end}}'
monitoring-net driver=bridge subnet=172.20.0.0/16

==================== STEP 3: CREATE THE 3 CONTAINERS ====================
--- frontend: nginx, on frontend-net only
$ docker run -d --name frontend --network frontend-net nginx:alpine
8850c76b27b7f9b3f8c411b656b5ee1fad7be095dfb37b67c49ed64c7cf6fc0c

--- database: mysql, on backend-net only
$ docker run -d --name database --network backend-net -e MYSQL_ROOT_PASSWORD=rootpass -e MYSQL_DATABASE=appdb mysql:8.0
68d3034418f7ef5d7fa86e3a709c0cade4ddd656decc3939bdd0495eb3896353

--- backend: alpine, on frontend-net FIRST...
$ docker run -d --name backend --network frontend-net alpine:3.20 sleep 3600
ecb3b2c549b13cdb9217de3c2c899b28fe287a26ced21d3e4e894462fe984f29

--- ...then ATTACH it to a SECOND network (backend-net)
$ docker network connect backend-net backend

==================== STEP 4: VERIFY THE TOPOLOGY ====================
$ docker ps --filter name=frontend --filter name=backend --filter name=database --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
NAMES      IMAGE          STATUS
backend    alpine:3.20    Up Less than a second
database   mysql:8.0      Up Less than a second
frontend   nginx:alpine   Up Less than a second

--- which containers are on each network:
$ docker network inspect frontend-net --format 'frontend-net  -> {{range .Containers}}{{.Name}} ({{.IPv4Address}})  {{end}}'
frontend-net  -> frontend (172.18.0.2/16)  backend (172.18.0.3/16)  

$ docker network inspect backend-net --format 'backend-net   -> {{range .Containers}}{{.Name}} ({{.IPv4Address}})  {{end}}'
backend-net   -> database (172.19.0.2/16)  backend (172.19.0.3/16)  

$ docker network inspect monitoring-net --format 'monitoring-net -> {{range .Containers}}{{.Name}} ({{.IPv4Address}})  {{end}}'
monitoring-net -> 

--- backend has TWO network interfaces (one per network):
$ docker inspect backend --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} = {{$v.IPAddress}}{{println}}{{end}}'
backend-net = 172.19.0.3
frontend-net = 172.18.0.3


$ docker exec backend ip -brief addr show
BusyBox v1.36.1 (2025-11-23 14:32:18 UTC) multi-call binary.

Usage: ip [OPTIONS] address|route|link|tunnel|neigh|rule [ARGS]

OPTIONS := -f[amily] inet|inet6|link | -o[neline]

ip addr add|del IFADDR dev IFACE | show|flush [dev IFACE] [to PREFIX]
ip route list|flush|add|del|change|append|replace|test ROUTE
ip link set IFACE [up|down] [arp on|off] [multicast on|off]
	[promisc on|off] [mtu NUM] [name NAME] [qlen NUM] [address MAC]
	[master IFACE | nomaster] [netns PID]
ip tunnel add|change|del|show [NAME]
	[mode ipip|gre|sit] [remote ADDR] [local ADDR] [ttl TTL]
ip neigh show|flush [to PREFIX] [dev DEV] [nud STATE]
ip rule [list] | add|del SELECTOR ACTION

```

### Connectivity tests

```console
$ docker exec backend ip addr show | grep -E '^[0-9]+:|inet '
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN qlen 1000
    inet 127.0.0.1/8 scope host lo
2: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN qlen 1000
3: gre0@NONE: <NOARP> mtu 1476 qdisc noop state DOWN qlen 1000
4: gretap0@NONE: <BROADCAST,MULTICAST> mtu 1462 qdisc noop state DOWN qlen 1000
5: erspan0@NONE: <BROADCAST,MULTICAST> mtu 1450 qdisc noop state DOWN qlen 1000
6: ip_vti0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN qlen 1000
7: ip6_vti0@NONE: <NOARP> mtu 1428 qdisc noop state DOWN qlen 1000
8: sit0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN qlen 1000
9: ip6tnl0@NONE: <NOARP> mtu 1452 qdisc noop state DOWN qlen 1000
10: ip6gre0@NONE: <NOARP> mtu 1448 qdisc noop state DOWN qlen 1000
11: eth0@if131: <BROADCAST,MULTICAST,UP,LOWER_UP,M-DOWN> mtu 1500 qdisc noqueue state UP 
    inet 172.18.0.3/16 brd 172.18.255.255 scope global eth0
12: eth1@if132: <BROADCAST,MULTICAST,UP,LOWER_UP,M-DOWN> mtu 1500 qdisc noqueue state UP 
    inet 172.19.0.3/16 brd 172.19.255.255 scope global eth1

==================== STEP 5: CONNECTIVITY TESTS ====================
-------- 5a. backend -> frontend  (SHARE frontend-net: should WORK) --------
$ docker exec backend ping -c 2 frontend
PING frontend (172.18.0.2): 56 data bytes
64 bytes from 172.18.0.2: seq=0 ttl=64 time=0.502 ms
64 bytes from 172.18.0.2: seq=1 ttl=64 time=0.209 ms

--- frontend ping statistics ---
2 packets transmitted, 2 packets received, 0% packet loss
round-trip min/avg/max = 0.209/0.355/0.502 ms

-------- 5b. backend -> database  (SHARE backend-net: should WORK) --------
$ docker exec backend ping -c 2 database
PING database (172.19.0.2): 56 data bytes
64 bytes from 172.19.0.2: seq=0 ttl=64 time=0.944 ms
64 bytes from 172.19.0.2: seq=1 ttl=64 time=0.218 ms

--- database ping statistics ---
2 packets transmitted, 2 packets received, 0% packet loss
round-trip min/avg/max = 0.218/0.581/0.944 ms

-------- 5c. frontend -> backend  (SHARE frontend-net: should WORK) --------
$ docker exec frontend ping -c 2 backend
PING backend (172.18.0.3): 56 data bytes
64 bytes from 172.18.0.3: seq=0 ttl=64 time=0.078 ms
64 bytes from 172.18.0.3: seq=1 ttl=64 time=0.247 ms

--- backend ping statistics ---
2 packets transmitted, 2 packets received, 0% packet loss
round-trip min/avg/max = 0.078/0.162/0.247 ms

-------- 5d. frontend -> database  (NO SHARED NETWORK: should FAIL) --------
$ docker exec frontend ping -c 2 -W 2 database || echo '>>> FAILED AS EXPECTED - the two containers share no network'
ping: bad address 'database'
>>> FAILED AS EXPECTED - the two containers share no network

-------- 5e. database -> frontend  (NO SHARED NETWORK: should FAIL) --------
$ docker exec database ping -c 2 -W 2 frontend || echo '>>> FAILED AS EXPECTED - isolation confirmed'
OCI runtime exec failed: exec failed: unable to start container process: exec: "ping": executable file not found in $PATH
>>> FAILED AS EXPECTED - isolation confirmed

==================== STEP 6: DNS - CONTAINER NAMES RESOLVE ====================
--- Docker runs an embedded DNS server at 127.0.0.11 on user-defined networks:
$ docker exec backend cat /etc/resolv.conf
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal

$ docker exec backend nslookup frontend
Server:		127.0.0.11
Address:	127.0.0.11:53

Non-authoritative answer:

Non-authoritative answer:
Name:	frontend
Address: 172.18.0.2


$ docker exec backend nslookup database
Server:		127.0.0.11
Address:	127.0.0.11:53

Non-authoritative answer:

Non-authoritative answer:
Name:	database
Address: 172.19.0.2


--- from frontend, the database name does NOT resolve at all:
$ docker exec frontend nslookup database || echo '>>> NAME DOES NOT RESOLVE - not on a shared network'
Server:		127.0.0.11
Address:	127.0.0.11:53

Non-authoritative answer:

** server can't find database: NXDOMAIN

>>> NAME DOES NOT RESOLVE - not on a shared network

==================== STEP 7: REAL SERVICE CONNECTIVITY (not just ping) ====================
--- backend fetches the frontend nginx homepage over HTTP:
$ docker exec backend wget -qO- --timeout=5 http://frontend | head -n 5
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>

--- backend reaches the MySQL port 3306 on the database:
$ docker exec backend nc -zv -w 3 database 3306
database (172.19.0.2:3306) open

--- frontend CANNOT reach MySQL:
$ docker exec frontend nc -zv -w 3 database 3306 || echo '>>> BLOCKED AS EXPECTED'
nc: bad address 'database'
>>> BLOCKED AS EXPECTED

==================== STEP 8: THE BACKEND AS A BRIDGE BETWEEN TIERS ====================
--- backend is the ONLY container that can reach both tiers:
$ docker exec backend sh -c 'ping -c 1 -W 2 frontend >/dev/null && echo "backend -> frontend : OK" ; ping -c 1 -W 2 database >/dev/null && echo "backend -> database : OK"'
backend -> frontend : OK
backend -> database : OK


-------- 5e (redone). database -> frontend --------
The mysql image has no ping/nc, so bash's built-in /dev/tcp is used instead.
$ docker exec database bash -c 'command -v ping nc curl wget || echo "none of ping/nc/curl/wget exist in this image"'
/usr/bin/curl

--- can the database resolve the name 'frontend'?
$ docker exec database getent hosts frontend || echo '>>> NAME DOES NOT RESOLVE - frontend is not on any network the database is attached to'
>>> NAME DOES NOT RESOLVE - frontend is not on any network the database is attached to

--- and can it open a TCP connection to it?
$ docker exec database bash -c 'timeout 3 bash -c "cat < /dev/null > /dev/tcp/frontend/80" && echo CONNECTED || echo ">>> CONNECTION FAILED AS EXPECTED"'
bash: line 1: frontend: Name or service not known
bash: line 1: /dev/tcp/frontend/80: Invalid argument
>>> CONNECTION FAILED AS EXPECTED

--- control test: the database CAN reach the backend, which shares backend-net:
$ docker exec database getent hosts backend
172.19.0.3      backend

==================== PROVING IT IS ROUTING, NOT JUST DNS ====================
Bypass DNS entirely and use the frontend's raw IP address (172.18.0.2):
$ docker exec database bash -c 'timeout 3 bash -c "cat < /dev/null > /dev/tcp/172.18.0.2/80" && echo "CONNECTED - not isolated" || echo ">>> NO ROUTE TO 172.18.0.2 - genuinely network-isolated, not merely a DNS failure"'
>>> NO ROUTE TO 172.18.0.2 - genuinely network-isolated, not merely a DNS failure

--- and the same raw-IP test from the backend, which IS on frontend-net, succeeds:
$ docker exec backend sh -c 'nc -zv -w 3 172.18.0.2 80'
172.18.0.2 (172.18.0.2:80) open

```

### What the connectivity results prove

| From | To | Shared network? | Result |
|---|---|---|---|
| backend | frontend | frontend-net | **OK** — 0% loss |
| backend | database | backend-net | **OK** — 0% loss |
| frontend | backend | frontend-net | **OK** — 0% loss |
| frontend | database | **none** | **BLOCKED** |
| database | frontend | **none** | **BLOCKED** |

Three findings worth stating precisely:

1. **`backend` genuinely has two interfaces.** `ip addr` inside it shows
   `eth0 = 172.18.0.3` (frontend-net) and `eth1 = 172.19.0.3` (backend-net).
   Docker creates one veth pair per attached network.

2. **DNS by container name works, and is scoped per network.** Docker runs an
   embedded DNS server at **`127.0.0.11`** — visible in the container's
   `/etc/resolv.conf`. From `backend`, both `frontend` and `database` resolve.
   From `frontend`, `nslookup database` returns **`NXDOMAIN`**. Names only
   resolve for containers you share a network with.

   > This automatic name resolution is the main practical reason to always use
   > **user-defined** networks. The legacy `default bridge` network has **no**
   > DNS: containers there can only reach each other by IP address, or by the
   > deprecated `--link` flag.

3. **The isolation is real routing, not just missing DNS.** This needed
   checking properly. The first attempt was inconclusive: `docker exec database
   ping frontend` failed with *"ping: executable file not found"* — the
   `mysql:8.0` image simply has no `ping` binary, which proves nothing about the
   network.

   So the test was redone using bash's built-in `/dev/tcp`, **bypassing DNS by
   using the raw IP**:

   ```console
   $ docker exec database bash -c 'timeout 3 bash -c "cat < /dev/null > /dev/tcp/172.18.0.2/80" && echo CONNECTED || echo "NO ROUTE"'
   >>> NO ROUTE TO 172.18.0.2 - genuinely network-isolated, not merely a DNS failure

   $ docker exec backend sh -c 'nc -zv -w 3 172.18.0.2 80'      # control test
   172.18.0.2 (172.18.0.2:80) open
   ```

   The **same IP** is unreachable from `database` and reachable from `backend`.
   That is layer-3 isolation enforced by separate bridges and iptables rules,
   not a name-lookup problem.

4. **Real services, not just ICMP.** `backend` fetched the nginx homepage over
   HTTP (`wget -qO- http://frontend`) and confirmed MySQL's port was open
   (`nc -zv database 3306` → `open`), while the same probe from `frontend`
   failed.

### Network commands reference

| Goal | Command |
|---|---|
| List networks | `docker network ls` |
| Create | `docker network create <name>` |
| Create with a chosen subnet | `docker network create --subnet 10.5.0.0/24 <name>` |
| Inspect (containers, IPs, subnet) | `docker network inspect <name>` |
| Attach a **running** container | `docker network connect <net> <container>` |
| Detach | `docker network disconnect <net> <container>` |
| Run already attached | `docker run --network <net> ...` |
| Delete | `docker network rm <name>` |
| Delete all unused | `docker network prune` |

### The network drivers

| Driver | Scope | Use for |
|---|---|---|
| **bridge** | Single host | The default. Isolated container networks on one machine. |
| **host** | Single host | Removing network isolation for performance — Task 2. |
| **none** | Single host | Completely disabling networking. |
| **overlay** | **Multi-host** | Containers across a Swarm cluster — Task 4. |
| **macvlan** | Single host | Giving a container a real MAC/IP on the physical LAN. |

---

## Task 2 — Host Network

### What host networking does

`--network host` removes network isolation entirely. The container does not get
its own network namespace, its own IP or its own port space — it **shares the
host's**. There is no NAT and no `-p` port publishing, because there is nothing
to translate between.

### Commands

```bash
# Pull the Apache image
docker pull httpd:2.4

# Run it on the host network - note there is NO -p flag
docker run -d --name apache-host --network host httpd:2.4
```

### Output

```console
==================== TASK 2: HOST NETWORK ====================
-------- First attempt: the default port 80 --------
$ docker run -d --name apache-host --network host httpd:2.4
$ docker logs apache-host
(98)Address already in use: AH00072: make_sock: could not bind to address 0.0.0.0:80
no listening sockets available, shutting down
AH00015: Unable to open logs

>>> The container EXITED. Port 80 on this host is already taken by another
>>> container. This is the defining property of host networking: there is NO
>>> port remapping, so the container competes for the host's real ports.

-------- Second attempt: Apache configured to listen on 9097 --------
$ docker ps --filter name=apache-host --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Networks}}'
NAMES         STATUS          PORTS     NETWORKS
apache-host   Up 25 seconds             host

>>> Note the PORTS column is EMPTY and NETWORKS says 'host'.
>>> No -p flag was used, and Docker publishes nothing - there is nothing to publish.

$ docker logs apache-host
AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 192.168.65.3. Set the 'ServerName' directive globally to suppress this message
AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 192.168.65.3. Set the 'ServerName' directive globally to suppress this message
[Thu Sep 03 17:00:17.644462 2026] [mpm_event:notice] [pid 8:tid 8] AH00489: Apache/2.4.68 (Unix) configured -- resuming normal operations
[Thu Sep 03 17:00:17.645052 2026] [core:notice] [pid 8:tid 8] AH00094: Command line: 'httpd -D FOREGROUND'

-------- Verify from inside the host network namespace --------
$ docker run --rm --network host alpine:3.20 wget -qO- --timeout=5 http://localhost:9097
<!doctype html>
<html>
  <head><title>Apache on the Host Network</title></head>
  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:70px; background:#f6f8fa;">
    <h1>Hello World</h1>
    <p>Apache running with <strong>--network host</strong></p>
    <p>No <code>-p</code> port publishing was used. The container shares the host's network stack directly.</p>
  </body>
</html>

$ docker run --rm --network host alpine:3.20 sh -c 'nc -zv -w 3 localhost 9097'
localhost ([::1]:9097) open

-------- The container sees the HOST's interfaces, not its own --------
--- a normal BRIDGE container has its own private 172.x address:
$ docker run --rm alpine:3.20 sh -c 'ip addr show eth0 | grep inet'
    inet 172.17.0.11/16 brd 172.17.255.255 scope global eth0

--- a HOST-network container sees the host's real interfaces instead:
$ docker run --rm --network host alpine:3.20 sh -c 'ip addr show | grep -E "^[0-9]+: |inet " | head -n 12'
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN qlen 1000
    inet 127.0.0.1/8 scope host lo
2: bond0: <BROADCAST,MULTICAST400> mtu 1500 qdisc noop state DOWN qlen 1000
3: dummy0: <BROADCAST,NOARP> mtu 1500 qdisc noop state DOWN qlen 1000
4: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 65535 qdisc pfifo_fast state UP qlen 1000
    inet 192.168.65.3/24 brd 192.168.65.255 scope global eth0
5: teql0: <NOARP> mtu 1500 qdisc noop state DOWN qlen 100
6: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN qlen 1000
7: gre0@NONE: <NOARP> mtu 1476 qdisc noop state DOWN qlen 1000
8: gretap0@NONE: <BROADCAST,MULTICAST> mtu 1462 qdisc noop state DOWN qlen 1000
9: erspan0@NONE: <BROADCAST,MULTICAST> mtu 1450 qdisc noop state DOWN qlen 1000
10: ip_vti0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN qlen 1000

--- and its hostname is the HOST's hostname:
$ docker run --rm --network host alpine:3.20 hostname
docker-desktop

$ docker run --rm alpine:3.20 hostname
b1a0d7306bd7

--- the host-network container can see every port the host has open:
$ docker run --rm --network host alpine:3.20 sh -c 'netstat -tuln 2>/dev/null | head -n 10'
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State       
tcp        0      0 0.0.0.0:58409           0.0.0.0:*               LISTEN      
tcp        0      0 0.0.0.0:111             0.0.0.0:*               LISTEN      
tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN      
tcp        0      0 0.0.0.0:9093            0.0.0.0:*               LISTEN      
tcp        0      0 0.0.0.0:9092            0.0.0.0:*               LISTEN      
tcp        0      0 0.0.0.0:9095            0.0.0.0:*               LISTEN      
tcp        0      0 0.0.0.0:9094            0.0.0.0:*               LISTEN      
tcp        0      0 0.0.0.0:9091            0.0.0.0:*               LISTEN      

```

### What that proves, and an honest note about port 80

The task asks to access Apache on **port 80**. The first attempt did exactly
that — `docker run -d --network host httpd:2.4`, no `-p` flag — and the
container **exited immediately**:

```
(98)Address already in use: AH00072: could not bind to address 0.0.0.0:80
no listening sockets available, shutting down
```

**Port 80 on this machine was already bound by an unrelated pre-existing
container**, which I left running rather than disrupt. So Apache was
reconfigured with `Listen 9097` and the exercise repeated successfully.

That failure is worth keeping, because it *is* the lesson: in host mode there
is **no port remapping**, so the container competes directly for the host's real
ports. In bridge mode two containers can both listen on 80 internally and be
published to different host ports. In host mode, the second one simply dies. On
a machine with a free port 80 the original command works unchanged.

The evidence that host networking is genuinely in effect:

| Observation | Bridge container | **Host container** |
|---|---|---|
| `docker ps` PORTS column | `0.0.0.0:9098->80/tcp` | **empty** — nothing to publish |
| `docker ps` NETWORKS | `bridge` | **`host`** |
| IP address | private `172.17.0.11/16` | the host's own **`192.168.65.3/24`** |
| `hostname` | random ID `b1a0d7306bd7` | **`docker-desktop`** — the host's name |
| Visible listening ports | only its own | **every port the host has open** |

That last row is striking: `netstat` inside the container lists `0.0.0.0:80`,
`9091`–`9095` and the rest — ports belonging to *other* containers and to the
host. There is no isolation left at all.

> **macOS caveat, stated plainly.** Docker Desktop runs a Linux VM, so
> "the host" is that VM (`docker-desktop`, `192.168.65.3`), not macOS. The
> container really does join the VM's network namespace — verified from another
> `--network host` container — but Docker Desktop does not forward host-network
> ports out to macOS, so `curl localhost:9097` from macOS does not reach it.
> **On native Linux, `--network host` binds the machine's real ports directly
> and this caveat does not apply.**

### When to use host networking

**Use it for:** maximum network throughput (no NAT overhead — genuinely
measurable for high-traffic proxies), applications that need to open many
dynamic ports, or services that must see real client IPs rather than the
bridge's.

**Avoid it for:** almost everything else. You lose isolation, you lose the
ability to run two instances of the same service, and container names no longer
resolve via Docker's DNS. **Bridge networks are the right default.**

---

## Task 3 — Bind Mount

### What a bind mount is

`-v /path/on/host:/path/in/container` maps a host directory straight into the
container. It is not a copy — it is the **same directory**, visible from both
sides at once. Changes made from either side are immediately visible to the
other, because there is only one copy of the data.

### Commands

```bash
mkdir bind-mount-demo
echo '<h1>Hello students</h1>' > bind-mount-demo/index.html

docker run -d --name nginx-bind -p 9098:80 \
    -v "$PWD/bind-mount-demo":/usr/share/nginx/html:ro \
    nginx:alpine

curl http://localhost:9098          # -> Hello students
# edit the file on the host, then curl again - no restart needed
```

### Setup and first access

```console
==================== TASK 3: BIND MOUNT ====================
-------- STEP 1: the folder and file on the LOCAL machine --------
$ pwd
/Users/shaurya/sst/07-docker-network

$ ls -la bind-mount-demo/
total 8
drwxr-xr-x@ 3 shaurya  staff   96 Sep  3 22:30 .
drwxr-xr-x@ 4 shaurya  staff  128 Sep  3 22:30 ..
-rw-r--r--@ 1 shaurya  staff  225 Sep  3 22:30 index.html

$ cat bind-mount-demo/index.html
<!doctype html>
<html>
  <head><title>Bind Mount Demo</title></head>
  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:70px; background:#f6f8fa;">
    <h1>Hello students</h1>
  </body>
</html>

-------- STEP 2: bind mount that folder into an nginx container --------
$ docker run -d --name nginx-bind -p 9098:80 -v "$PWD/bind-mount-demo":/usr/share/nginx/html:ro nginx:alpine
feea779d1182e1ca64a7a9a8c0cd04b57a3d68e1c28d59dd569cd663298d34f4

$ docker ps --filter name=nginx-bind --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
NAMES        STATUS         PORTS
nginx-bind   Up 3 seconds   0.0.0.0:9098->80/tcp, [::]:9098->80/tcp

-------- STEP 3: confirm the mount exists --------
$ docker inspect nginx-bind --format '{{range .Mounts}}Type:   {{.Type}}{{println}}Source: {{.Source}}{{println}}Target: {{.Destination}}{{println}}ReadOnly: {{.RW}}{{end}}'
Type:   bind
Source: /Users/shaurya/sst/07-docker-network/bind-mount-demo
Target: /usr/share/nginx/html
ReadOnly: false

$ docker exec nginx-bind ls -la /usr/share/nginx/html
total 8
drwxr-xr-x    3 root     root            96 Sep  3 17:00 .
drwxr-xr-x    3 root     root          4096 Sep  2 21:05 ..
-rw-r--r--    1 root     root           225 Sep  3 17:00 index.html

-------- STEP 4: access the website --------
$ curl -s http://localhost:9098
<!doctype html>
<html>
  <head><title>Bind Mount Demo</title></head>
  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:70px; background:#f6f8fa;">
    <h1>Hello students</h1>
  </body>
</html>

$ curl -s http://localhost:9098 | grep -o 'Hello students'
Hello students

>>> VERIFIED: the container is serving the file from the local folder.

-------- STEP 5: MODIFY the file on the host (container untouched) --------
$ docker inspect nginx-bind --format 'Container started at: {{.State.StartedAt}}'
Container started at: 2026-09-03T17:00:59.508134506Z

```

### Modifying the file live

```console
--- the container has NOT been restarted; note this start time and PID:
$ docker inspect nginx-bind --format 'StartedAt: {{.State.StartedAt}}  PID: {{.State.Pid}}'
StartedAt: 2026-09-03T17:00:59.508134506Z  PID: 28079

-------- Now edit index.html ON THE HOST --------
$ cat > bind-mount-demo/index.html <<'HTML'
<!doctype html>
<html>
  <head><title>Bind Mount Demo - UPDATED</title></head>
  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:70px; background:#e8f5e9;">
    <h1>Hello students - this file was MODIFIED on the host!</h1>
    <p>The container was never restarted. Bind mounts are live.</p>
  </body>
</html>
HTML

$ cat bind-mount-demo/index.html
<!doctype html>
<html>
  <head><title>Bind Mount Demo - UPDATED</title></head>
  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:70px; background:#e8f5e9;">
    <h1>Hello students - this file was MODIFIED on the host!</h1>
    <p>The container was never restarted. Bind mounts are live.</p>
  </body>
</html>

-------- Request the page again, WITHOUT restarting the container --------
$ curl -s http://localhost:9098
<!doctype html>
<html>
  <head><title>Bind Mount Demo - UPDATED</title></head>
  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:70px; background:#e8f5e9;">
    <h1>Hello students - this file w
$ curl -s http://localhost:9098 | grep -o 'MODIFIED on the host'
MODIFIED on the host

-------- Prove the container really was not restarted --------
$ docker inspect nginx-bind --format 'StartedAt: {{.State.StartedAt}}  PID: {{.State.Pid}}'
StartedAt: 2026-09-03T17:00:59.508134506Z  PID: 28079

$ docker ps --filter name=nginx-bind --format 'table {{.Names}}\t{{.Status}}'
NAMES        STATUS
nginx-bind   Up 29 seconds

>>> Identical StartedAt and PID, and uptime kept counting: NO restart happened.

-------- Third edit, to make the point beyond doubt --------
$ echo '<h1>Hello students - third version</h1>' > bind-mount-demo/index.html

$ curl -s http://localhost:9098
<h1>Hello students - third version</h1>

-------- The mount is READ-ONLY (:ro), so the container cannot write back --------
$ docker exec nginx-bind sh -c 'echo hacked > /usr/share/nginx/html/index.html' || echo '>>> WRITE REFUSED - the :ro flag protects the host folder'
sh: can't create /usr/share/nginx/html/index.html: Read-only file system
>>> WRITE REFUSED - the :ro flag protects the host folder

$ cat bind-mount-demo/index.html
<h1>Hello students - third version</h1>

>>> The host file is unchanged - :ro worked.

-------- Restore a sensible final version --------
$ cat > bind-mount-demo/index.html <<'HTML'
<!doctype html>
<html>
  <head><title>Bind Mount Demo</title></head>
  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:70px; background:#f6f8fa;">
    <h1>Hello students</h1>
    <p>Served by Nginx from a bind-mounted folder on the host.</p>
  </body>
</html>
HTML

$ curl -s http://localhost:9098 | grep -o 'Hello students'
Hello students

```

### Screenshot

![Bind mount serving Hello students](screenshots/bind-mount.png)

### What that proves

1. **The container served the host's file**, confirmed by `docker inspect`
   showing `Type: bind`, `Source: /Users/shaurya/sst/07-docker-network/bind-mount-demo`,
   `Target: /usr/share/nginx/html`, and by `curl` returning **Hello students**.

2. **Edits appeared with no restart — this is the key requirement.** The file
   was rewritten on the host twice, and each time `curl` immediately returned
   the new content. The proof that nothing was restarted is that
   `StartedAt: 2026-09-03T17:00:59.508134506Z` and `PID: 28079` were
   **byte-identical before and after**, and `docker ps` uptime kept counting up
   from `Up 3 seconds` to `Up 29 seconds`. A restart would have reset both.

3. **`:ro` is enforced by the kernel.** Writing from inside the container was
   refused with `Read-only file system`, and the host file was untouched.

### Why this matters

In development, bind-mounting your source directory means **edit locally, see it
live in the container** — no rebuild, no restart. It is the single biggest
quality-of-life win when working with Docker.

### Bind mount vs named volume

| | **Bind mount** (`-v /host/path:/ctr/path`) | **Named volume** (`-v myvol:/ctr/path`) |
|---|---|---|
| Lives at | a path you choose on the host | Docker's own storage area |
| Managed by | you | Docker (`docker volume ls`) |
| Host path must exist | yes (Docker creates it if missing, owned by root) | n/a |
| Portable across machines | no — depends on the host's layout | yes |
| Performance on macOS/Windows | slower (crosses the VM boundary) | faster |
| Best for | **source code in development**, config files | **databases and production data** |

> Rule of thumb: **bind mounts for code you are editing, named volumes for data
> you must not lose.** Never bind-mount a database's data directory on
> macOS/Windows — the filesystem translation layer causes real corruption risks
> and poor performance.

---

## Task 4 — Overlay Networks (research)

*This task asked for research and understanding rather than a practical
exercise, since a working overlay network needs **multiple Docker hosts** in a
Swarm cluster, which a single laptop cannot meaningfully demonstrate.*

### The problem overlay networks solve

Every network in Task 1 was a **bridge**, and bridges are strictly
**single-host**. `frontend` at `172.18.0.2` is only reachable from containers on
*this* machine. Put the database on a second server and the bridge cannot help:
those private `172.x` addresses are not routable between hosts.

Historically you worked around this by publishing ports to each host's real IP
and hardcoding IPs and ports everywhere — brittle, insecure, and impossible to
scale.

An **overlay network** makes a group of Docker hosts behave as if their
containers were all plugged into **one flat virtual switch**, regardless of which
physical machine each container is on.

### How it works

```
        HOST A (10.0.1.5)                      HOST B (10.0.1.6)
   ┌──────────────────────────┐          ┌──────────────────────────┐
   │  ┌────────┐  ┌────────┐  │          │  ┌────────┐  ┌────────┐  │
   │  │  web   │  │  api   │  │          │  │  api   │  │   db   │  │
   │  │10.0.9.2│  │10.0.9.3│  │          │  │10.0.9.4│  │10.0.9.5│  │
   │  └───┬────┘  └───┬────┘  │          │  └───┬────┘  └───┬────┘  │
   │      └─────┬─────┘       │          │      └─────┬─────┘       │
   │       overlay br0        │          │       overlay br0        │
   └────────────┬─────────────┘          └────────────┬─────────────┘
                │        VXLAN tunnel (UDP 4789)      │
                └──────────── physical network ───────┘

   All four containers share ONE subnet 10.0.9.0/24 and can reach each
   other by name, even though they sit on two different physical machines.
```

1. **VXLAN encapsulation.** Each container's Ethernet frame is wrapped inside a
   **UDP packet on port 4789** and sent to the other host, which unwraps it and
   delivers it to the local bridge. The containers are unaware any of this
   happened — they believe they are on one LAN. This is the "overlay": a
   virtual layer-2 network riding on top of the real layer-3 network.
2. **A distributed control plane.** Swarm managers use a gossip protocol to
   share which container has which IP on which host, so every node knows where
   to send a given packet.
3. **Distributed DNS.** Each node runs a resolver, so a container name resolves
   cluster-wide — `api` works from any node.
4. **Built-in load balancing.** A *service* gets a single stable **VIP**, and
   Swarm's IPVS layer spreads connections across every replica on every node.
   Scaling from 1 to 10 replicas needs no client-side change at all.
5. **Optional encryption.** `--opt encrypted` turns on IPsec between nodes, so
   traffic crossing the physical network is protected.

### Commands

```bash
# Overlay networks require Swarm mode
docker swarm init --advertise-addr <MANAGER-IP>
docker swarm join --token <TOKEN> <MANAGER-IP>:2377      # on each worker

# Create the overlay
docker network create -d overlay --attachable my-overlay

# Encrypted variant
docker network create -d overlay --opt encrypted secure-overlay

# Use it for a service that spans nodes
docker service create --name api --network my-overlay --replicas 5 my-api:1.0

docker network ls          # SCOPE column reads "swarm", not "local"
docker service ps api      # shows which node each replica landed on
```

> **`--attachable` matters.** Without it, only Swarm *services* may join the
> overlay. With it, plain `docker run --network my-overlay` containers can
> attach too — very useful for debugging.

### Ports that must be open between hosts

| Port | Protocol | Purpose |
|---|---|---|
| **2377** | TCP | Swarm cluster management (managers only) |
| **7946** | TCP + UDP | Node-to-node control plane gossip |
| **4789** | UDP | **VXLAN data plane** — the actual container traffic |

A misconfigured firewall here is the classic overlay failure: the cluster forms
(2377 and 7946 are open) but containers cannot reach each other because
**4789/UDP** is blocked.

### Use cases

- **Multi-host container communication** — the core purpose.
- **Scaling a service across machines** while keeping one stable name and VIP.
- **High availability** — replicas spread across nodes survive a node failure.
- **Network segmentation at cluster scale** — separate overlays for frontend
  and backend tiers, exactly like Task 1 but spanning the whole cluster.
- **Encrypted service-to-service traffic** over untrusted networks.

### Trade-offs

- **VXLAN adds overhead:** 50 bytes per packet, so the effective MTU drops
  (1500 → ~1450). Applications that assume a 1500-byte MTU can see mysterious
  hangs on large payloads. Encryption costs more CPU on top.
- **More moving parts:** Swarm managers, a quorum, certificate rotation.
- **Kubernetes has largely displaced Swarm** in production, but the underlying
  idea is identical — Flannel's VXLAN backend, Calico and Weave all solve the
  same problem the same way. **Understanding overlay networking here transfers
  directly to understanding Kubernetes pod networking.**

### Bridge vs overlay

| | Bridge | Overlay |
|---|---|---|
| Scope | One host | **Many hosts** |
| Requires Swarm | No | **Yes** |
| Transport | Linux bridge + iptables | **VXLAN over UDP 4789** |
| DNS | Local to the host | Cluster-wide |
| Load balancing | None built in | **Built-in VIP + IPVS** |
| Encryption | n/a (local) | Optional IPsec |
| `docker network ls` SCOPE | `local` | `swarm` |

---

## Summary

| Task | Requirement | Status |
|---|---|---|
| 1 | Create 3 containers (frontend, backend, database) | Done |
| 1 | Nginx/Alpine for frontend and backend | Done — `nginx:alpine`, `alpine:3.20` |
| 1 | MySQL image for the database | Done — `mysql:8.0` |
| 1 | Create 3 different Docker networks | Done — frontend-net, backend-net, monitoring-net |
| 1 | Add the backend container to 2 networks | Done — verified two IPs, `eth0` + `eth1` |
| 1 | Check connectivity between containers | Done — 5 tests, incl. raw-IP isolation proof |
| 2 | Pull the Apache2 image | Done — `httpd:2.4` |
| 2 | Apache container on the host network | Done — `--network host`, NETWORKS=`host` |
| 2 | Access the Apache website on port 80 | Attempted on 80 (port occupied — error captured); succeeded on 9097 with full host-network evidence |
| 3 | Create a local folder | Done — `bind-mount-demo/` |
| 3 | `index.html` containing "Hello students" | Done |
| 3 | Bind mount it into an Nginx container | Done — `docker inspect` confirms `Type: bind` |
| 3 | Access the site and verify | Done — curl + screenshot |
| 3 | Modify the file | Done — twice |
| 3 | Changes reflected without restarting | Done — identical StartedAt and PID before/after |
| 4 | Research overlay networks | Done |
| 4 | Understand their use cases | Done |
| 4 | Understand how they work across hosts | Done — VXLAN, control plane, ports, MTU |
