# Networking Fundamentals — Homework

## Task 1 — Practise the networking commands
## Task 2 — Document each command, its output, and what I understood

Both tasks are covered by this single document. Every block below is **real
captured output** from Ubuntu 22.04, followed by an explanation of what the
command does and what the output actually tells you.

**Environment:** Ubuntu 22.04 container, interface `eth0`, IP `172.17.0.3/16`,
gateway `172.17.0.1`, DNS server `192.168.65.7`.

---

## Quick reference

| Layer | Question you are asking | Command |
|---|---|---|
| Interface | What are my IPs? | `ip addr`, `ifconfig`, `hostname -I` |
| Routing | How does traffic get out? | `ip route`, `route -n`, `ip route get <ip>` |
| ARP | Who is my neighbour on this LAN? | `ip neigh`, `arp -n` |
| Reachability | Is the host alive? | `ping` |
| Path | Where does it break? | `traceroute`, `mtr` |
| DNS | What IP is this name? | `dig`, `nslookup`, `host` |
| Sockets | What is listening here? | `ss -tulnp`, `netstat -tuln` |
| Remote port | Is that port open? | `nc -zv host port`, `telnet` |
| HTTP | Is the web app responding? | `curl`, `wget` |
| Packets | What is actually on the wire? | `tcpdump` |
| Ownership | Who owns this domain? | `whois` |

**The classic debugging ladder** — work up it in order, because each step
depends on the one before:

```
1. ip addr        Do I even have an IP?
2. ip route       Do I have a default gateway?
3. ping gateway   Can I reach my own router?
4. ping 8.8.8.8   Can I reach the internet by IP?      -> if this fails, routing/firewall
5. dig google.com Can I resolve names?                 -> if only this fails, it's DNS
6. curl https://  Does the application layer respond?  -> if only this fails, it's the app/TLS
```

> If steps 1–4 pass but step 5 fails, **it's DNS**. It is almost always DNS.

---

## 1. Interfaces — `ip addr`, `ifconfig`, `ip link`

```console
$ ip addr show
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host 
       valid_lft forever preferred_lft forever
2: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
3: gre0@NONE: <NOARP> mtu 1476 qdisc noop state DOWN group default qlen 1000
    link/gre 0.0.0.0 brd 0.0.0.0
4: gretap0@NONE: <BROADCAST,MULTICAST> mtu 1462 qdisc noop state DOWN group default qlen 1000
    link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
5: erspan0@NONE: <BROADCAST,MULTICAST> mtu 1450 qdisc noop state DOWN group default qlen 1000
    link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
6: ip_vti0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
7: ip6_vti0@NONE: <NOARP> mtu 1428 qdisc noop state DOWN group default qlen 1000
    link/tunnel6 :: brd :: permaddr f605:a46d:9e38::
8: sit0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/sit 0.0.0.0 brd 0.0.0.0
9: ip6tnl0@NONE: <NOARP> mtu 1452 qdisc noop state DOWN group default qlen 1000
    link/tunnel6 :: brd :: permaddr de88:bde1:eccd::
10: ip6gre0@NONE: <NOARP> mtu 1448 qdisc noop state DOWN group default qlen 1000
    link/gre6 :: brd :: permaddr 72d7:6192:ba7e::
11: eth0@if90: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 65535 qdisc noqueue state UP group default 
    link/ether f2:56:19:e6:9f:08 brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 172.17.0.3/16 brd 172.17.255.255 scope global eth0
       valid_lft forever preferred_lft forever

$ ip -brief addr show
lo               UNKNOWN        127.0.0.1/8 ::1/128 
tunl0@NONE       DOWN           
gre0@NONE        DOWN           
gretap0@NONE     DOWN           
erspan0@NONE     DOWN           
ip_vti0@NONE     DOWN           
ip6_vti0@NONE    DOWN           
sit0@NONE        DOWN           
ip6tnl0@NONE     DOWN           
ip6gre0@NONE     DOWN           
eth0@if90        UP             172.17.0.3/16 

$ ifconfig
eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 65535
        inet 172.17.0.3  netmask 255.255.0.0  broadcast 172.17.255.255
        ether f2:56:19:e6:9f:08  txqueuelen 0  (Ethernet)
        RX packets 2868  bytes 64800856 (64.8 MB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 1710  bytes 126780 (126.7 KB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536
        inet 127.0.0.1  netmask 255.0.0.0
        inet6 ::1  prefixlen 128  scopeid 0x10<host>
        loop  txqueuelen 1000  (Local Loopback)
        RX packets 0  bytes 0 (0.0 B)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 0  bytes 0 (0.0 B)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0


$ ip link show
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
3: gre0@NONE: <NOARP> mtu 1476 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/gre 0.0.0.0 brd 0.0.0.0
4: gretap0@NONE: <BROADCAST,MULTICAST> mtu 1462 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
5: erspan0@NONE: <BROADCAST,MULTICAST> mtu 1450 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
6: ip_vti0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
7: ip6_vti0@NONE: <NOARP> mtu 1428 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/tunnel6 :: brd :: permaddr f605:a46d:9e38::
8: sit0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/sit 0.0.0.0 brd 0.0.0.0
9: ip6tnl0@NONE: <NOARP> mtu 1452 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/tunnel6 :: brd :: permaddr de88:bde1:eccd::
10: ip6gre0@NONE: <NOARP> mtu 1448 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/gre6 :: brd :: permaddr 72d7:6192:ba7e::
11: eth0@if90: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 65535 qdisc noqueue state UP mode DEFAULT group default 
    link/ether f2:56:19:e6:9f:08 brd ff:ff:ff:ff:ff:ff link-netnsid 0

$ hostname
c071b53e37c7

$ hostname -I
172.17.0.3 

```

### What I understood — Interfaces

- `ip addr show` is the modern command (from `iproute2`); `ifconfig` is the
  deprecated `net-tools` equivalent still found in older docs. Both list the
  network interfaces and their addresses, but only `ip` understands modern
  features like multiple addresses per interface and network namespaces.
- **`lo`** is the loopback interface, always `127.0.0.1/8`. Traffic to it never
  leaves the machine. **`eth0`** is the real interface — here it has
  **`172.17.0.3/16`**, which is Docker's default bridge network range.
- The `/16` is the **CIDR prefix**: 16 bits of network, leaving 16 bits of host,
  so the usable range is `172.17.0.1`–`172.17.255.254` — which is what the
  `brd 172.17.255.255` (broadcast address) line confirms.
- **`link/ether f2:56:19:e6:9f:08`** is the MAC address — the layer 2 hardware
  address, used only within the local network segment.
- **`UP` and `LOWER_UP`** in the flags mean the interface is administratively
  enabled *and* the physical link is present. An interface that is `UP` but not
  `LOWER_UP` means "configured but the cable is unplugged".
- **`mtu 65535`** is the Maximum Transmission Unit — the biggest packet the
  interface will send in one piece. Normal Ethernet is 1500; this is high
  because it is a virtual interface.
- `eth0@if90` tells you this is one half of a **veth pair** — a virtual cable
  whose other end is device index 90 in the host's namespace. That is exactly
  how Docker connects a container to the bridge.
- `ip -brief addr show` is the one to remember day to day — same information,
  one line per interface.
- All the `tunl0`, `gre0`, `sit0` devices are unconfigured tunnel drivers the
  kernel exposes by default. They are `DOWN` and can be ignored.

---

## 2. Routing and ARP — `ip route`, `route`, `ip neigh`

```console
$ ip route show
default via 172.17.0.1 dev eth0 
172.17.0.0/16 dev eth0 proto kernel scope link src 172.17.0.3 

$ ip route get 8.8.8.8
8.8.8.8 via 172.17.0.1 dev eth0 src 172.17.0.3 uid 0 
    cache 

$ route -n
Kernel IP routing table
Destination     Gateway         Genmask         Flags Metric Ref    Use Iface
0.0.0.0         172.17.0.1      0.0.0.0         UG    0      0        0 eth0
172.17.0.0      0.0.0.0         255.255.0.0     U     0      0        0 eth0

$ ip neigh show
172.17.0.1 dev eth0 lladdr 1a:5a:85:04:3e:39 REACHABLE

$ arp -n
Address                  HWtype  HWaddress           Flags Mask            Iface
172.17.0.1               ether   1a:5a:85:04:3e:39   C                     eth0

```

### What I understood — Routing

- `ip route show` is the machine's routing table: the ordered list of rules
  deciding which interface a packet leaves by. It is read **most-specific
  first**.
- **`default via 172.17.0.1 dev eth0`** is the default gateway — "anything I
  don't have a more specific rule for, hand to 172.17.0.1". Without a default
  route a machine can talk to its own subnet and nothing else. This is the
  single most common cause of "I have an IP but no internet".
- **`172.17.0.0/16 dev eth0 ... src 172.17.0.3`** is the directly-connected
  route: addresses in my own subnet are reached **directly over the wire**, with
  no gateway involved.
- `ip route get 8.8.8.8` is the genuinely useful one for debugging — instead of
  making you read the table and apply the rules in your head, it asks the kernel
  "which route would you *actually* pick for this destination?" and shows the
  chosen source IP and interface.
- `route -n` is the old `net-tools` equivalent. `-n` means "don't try to resolve
  names", which makes it instant instead of hanging on DNS.
- **ARP** (`ip neigh` / `arp -n`) maps **IP addresses to MAC addresses** on the
  local segment. Before sending to 172.17.0.1 the kernel must know its MAC, so
  it broadcasts "who has 172.17.0.1?" and caches the answer. The output shows
  the gateway `172.17.0.1` at MAC `1a:5a:85:04:3e:39` in state `REACHABLE`. ARP
  only works within a broadcast domain — it never crosses a router.

---

## 3. Connectivity — `ping`

```console
$ ping -c 4 8.8.8.8
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=63 time=27.2 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=63 time=195 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=63 time=132 ms
64 bytes from 8.8.8.8: icmp_seq=4 ttl=63 time=143 ms

--- 8.8.8.8 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3010ms
rtt min/avg/max/mdev = 27.190/124.273/194.823/60.871 ms

$ ping -c 3 google.com
PING google.com (142.250.206.110) 56(84) bytes of data.
64 bytes from lcboma-az-in-f14.1e100.net (142.250.206.110): icmp_seq=1 ttl=63 time=31.1 ms
64 bytes from lcboma-az-in-f14.1e100.net (142.250.206.110): icmp_seq=2 ttl=63 time=181 ms
64 bytes from lcboma-az-in-f14.1e100.net (142.250.206.110): icmp_seq=3 ttl=63 time=156 ms

--- google.com ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2007ms
rtt min/avg/max/mdev = 31.137/122.501/180.655/65.401 ms

$ ping -c 2 -s 1000 8.8.8.8
PING 8.8.8.8 (8.8.8.8) 1000(1028) bytes of data.
1008 bytes from 8.8.8.8: icmp_seq=1 ttl=63 time=262 ms
1008 bytes from 8.8.8.8: icmp_seq=2 ttl=63 time=31.3 ms

--- 8.8.8.8 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1004ms
rtt min/avg/max/mdev = 31.278/146.498/261.719/115.220 ms

```

### What I understood — Connectivity (`ping`)

- `ping` sends an **ICMP echo request** and waits for an **echo reply**. It
  answers exactly one question: *is this host reachable, and how long does the
  round trip take?*
- **`-c 4`** stops after 4 packets. Without it, `ping` runs forever on Linux.
- The three numbers that matter in the output:
  - **`time=27.2 ms`** — round-trip latency for that packet.
  - **`0% packet loss`** — the health indicator. Any sustained loss above 0%
    on a wired path means a real problem.
  - **`rtt min/avg/max/mdev = 27.190/124.273/194.823/60.871`** — the summary.
    Here `mdev` (jitter) is 60 ms against a 124 ms average, which is very
    unstable. That is expected: this is a container inside a VM inside a laptop,
    not a datacentre link.
- **`ttl=63`** is Time To Live — a hop counter, decremented by one per router,
  and the packet is dropped at zero (this is what stops routing loops). Replies
  from Linux hosts start at 64, so `ttl=63` means the reply crossed **one**
  router to reach me. That single hop is the Docker bridge.
- `ping google.com` proved DNS *and* connectivity in one step, resolving to
  `142.250.206.110` and showing the reverse name `lcboma-az-in-f14.1e100.net`
  (`1e100.net` is Google's — 1×10¹⁰⁰ is a googol).
- **`-s 1000`** sets the payload size, so `1000(1028)` = 1000 bytes of payload
  plus 28 bytes of ICMP and IP headers. Useful for diagnosing MTU problems: if
  small pings succeed but large ones vanish, you have an MTU/fragmentation issue.
- **Important caveat:** many production hosts and cloud firewalls **block ICMP
  entirely**. A failed `ping` therefore does *not* prove a host is down — it may
  just be refusing to answer. Test the actual service port with `nc` or `curl`
  before concluding anything.

---

## 4. Path tracing — `traceroute`, `mtr`

```console
$ traceroute -m 12 8.8.8.8
traceroute to 8.8.8.8 (8.8.8.8), 12 hops max, 60 byte packets
 1  172.17.0.1 (172.17.0.1)  2.215 ms  0.035 ms  0.012 ms
 2  * * *
 3  * * *
 4  * * *
 5  * * *
 6  * * *
 7  * * *
 8  * * *
 9  * * *
10  * * *
11  * * *
12  * * *

$ traceroute -m 10 google.com
traceroute to google.com (142.250.206.110), 10 hops max, 60 byte packets
 1  172.17.0.1 (172.17.0.1)  0.064 ms  0.010 ms  0.006 ms
 2  * * *
 3  * * *
 4  * * *
 5  * * *
 6  * * *
 7  * * *
 8  * * *
 9  * * *
10  * * *

$ mtr -r -c 3 8.8.8.8
Start: 2026-09-03T16:43:23+0000
HOST: c071b53e37c7                Loss%   Snt   Last   Avg  Best  Wrst StDev
  1.|-- 172.17.0.1                 0.0%     3    0.3   0.3   0.2   0.3   0.1
  2.|-- dns.google                 0.0%     3  136.8 433.7 136.8 773.7 320.6


$ traceroute -I -m 12 8.8.8.8
traceroute to 8.8.8.8 (8.8.8.8), 12 hops max, 60 byte packets
 1  172.17.0.1 (172.17.0.1)  0.132 ms  0.100 ms  0.095 ms
 2  dns.google (8.8.8.8)  101.374 ms * *
```

### What I understood — Path tracing

- `traceroute` finds the **route** rather than just the destination. It exploits
  TTL: it sends a packet with `TTL=1` (the first router decrements it to 0 and
  returns an ICMP "time exceeded", revealing itself), then `TTL=2`, and so on.
  Each row is one hop further out. The three timings per row are three probes.
- **My output shows hop 1 = `172.17.0.1` (the Docker bridge gateway), then
  `* * *` for every hop after it.** `* * *` means "no reply received before the
  timeout". This is **not** a broken network — everything else here works. It is
  because the default `traceroute` uses **UDP** probes, and Docker Desktop's
  NAT layer inside its VM does not pass the resulting ICMP time-exceeded
  messages back. Intermediate routers on the public internet also very commonly
  drop or rate-limit these probes on purpose.
- Re-running with **`-I`** to use **ICMP** probes instead got further, and
  reached `dns.google (8.8.8.8)` at hop 2. This is the practical lesson:
  **if traceroute shows stars, change the probe type** (`-I` for ICMP, `-T` for
  TCP) before believing the path is broken. `-T` on port 443 is the most
  reliable on the modern internet, because firewalls rarely block it.
- `mtr` is `traceroute` and `ping` combined, run **continuously**. It is the
  better tool for real diagnosis because it shows **`Loss%` per hop over time**,
  turning "it feels slow sometimes" into a specific hop. `-r` gives a
  report-mode snapshot instead of a live UI, and `-c 3` sends 3 probes.
- Reading loss in `mtr` correctly: loss at one middle hop that **does not
  continue** to later hops is usually harmless — that router is just
  deprioritising ICMP replies to itself. **Only loss that persists from a hop
  all the way to the destination is real.**

---

## 5. DNS — `dig`, `nslookup`, `host`

```console
$ cat /etc/resolv.conf
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 192.168.65.7

# Based on host file: '/etc/resolv.conf' (legacy)
# Overrides: []

$ cat /etc/hosts
127.0.0.1	localhost
::1	localhost ip6-localhost ip6-loopback
fe00::	ip6-localnet
ff00::	ip6-mcastprefix
ff02::1	ip6-allnodes
ff02::2	ip6-allrouters
172.17.0.3	c071b53e37c7

$ nslookup github.com
Server:		192.168.65.7
Address:	192.168.65.7#53

Non-authoritative answer:
Name:	github.com
Address: 20.207.73.82


$ dig github.com

; <<>> DiG 9.18.39-0ubuntu0.22.04.6-Ubuntu <<>> github.com
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 57146
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;github.com.			IN	A

;; ANSWER SECTION:
github.com.		15	IN	A	20.207.73.82

;; Query time: 4 msec
;; SERVER: 192.168.65.7#53(192.168.65.7) (UDP)
;; WHEN: Thu Sep 03 16:44:07 UTC 2026
;; MSG SIZE  rcvd: 54


$ dig +short github.com
20.207.73.82

$ dig +short google.com A
142.250.206.110

$ dig google.com MX +short
;; communications error to 192.168.65.7#53: timed out
10 smtp.google.com.

$ dig google.com NS +short
ns1.google.com.
ns2.google.com.
ns4.google.com.
ns3.google.com.

$ dig +short -x 8.8.8.8
dns.google.

$ host github.com
github.com has address 20.207.73.82
github.com mail is handled by 0 github-com.mail.protection.outlook.com.

$ host 8.8.8.8
8.8.8.8.in-addr.arpa domain name pointer dns.google.

$ getent hosts github.com
20.207.73.82    github.com

```

### What I understood — DNS

- **`/etc/resolv.conf`** lists the DNS servers this machine asks. Mine shows
  `nameserver 192.168.65.7` — Docker's internal resolver, which is why DNS works
  inside the container at all. Note the header: Docker generates this file, so
  hand-edits inside a container are lost on recreate.
- **`/etc/hosts`** is checked **before** DNS and wins over it. That is why
  `172.17.0.3 c071b53e37c7` (this container's own hostname) resolves without any
  DNS query at all. Adding an entry here is the standard way to override a
  hostname locally for testing.
- **`nslookup`** is the simple, portable lookup tool. `Non-authoritative
  answer` means the reply came from a **cache**, not from the domain's own
  authoritative nameservers — normal and expected.
- **`dig`** is the tool to actually learn, because it shows the whole DNS
  protocol response:
  - **`->>HEADER<<- opcode: QUERY, status: NOERROR`** — the response code.
    `NOERROR` = fine; **`NXDOMAIN`** = the name does not exist;
    **`SERVFAIL`** = the resolver broke or DNSSEC validation failed.
  - **`flags: qr rd ra`** — `qr` response, `rd` recursion desired,
    `ra` recursion available. A missing `ra` means the server refuses to
    recurse for you.
  - **ANSWER SECTION** — the actual records, each with a **TTL** in seconds
    telling caches how long they may hold it. A low TTL before a migration is
    how you make a cut-over fast.
- **`dig +short`** strips all of that down to just the answer — the form you
  want inside scripts.
- **Record types demonstrated:** `A` (name → IPv4), `MX` (mail servers, with
  priority numbers — lower wins), `NS` (which nameservers are authoritative for
  the zone). Others worth knowing: `AAAA` (IPv6), `CNAME` (alias),
  `TXT` (SPF/DKIM/domain verification).
- **`dig -x 8.8.8.8`** is a **reverse** lookup (IP → name) via the
  `in-addr.arpa` zone, returning `dns.google`.
- `host` is the friendly middle ground, and `getent hosts` is the one that
  resolves **exactly the way a normal application would** — it honours
  `/etc/nsswitch.conf`, so it consults `/etc/hosts` too. `dig` talks to the DNS
  server directly and **bypasses `/etc/hosts` entirely**. That difference
  explains a classic confusion: `dig` says one IP, the app connects to another.

---

## 6. Ports and sockets — `ss`, `netstat`

```console
$ ss -tuln
Netid State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
udp   UNCONN 0      0      127.0.0.53%lo:53        0.0.0.0:*          
tcp   LISTEN 0      4096   127.0.0.53%lo:53        0.0.0.0:*          
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*          
tcp   LISTEN 0      511             [::]:80           [::]:*          

$ ss -tulnp
Netid State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess                                                                                                                                                                                                                                                                                                            
udp   UNCONN 0      0      127.0.0.53%lo:53        0.0.0.0:*    users:(("systemd-resolve",pid=36,fd=13))                                                                                                                                                                                                                                                                          
tcp   LISTEN 0      4096   127.0.0.53%lo:53        0.0.0.0:*    users:(("systemd-resolve",pid=36,fd=14))                                                                                                                                                                                                                                                                          
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*    users:(("nginx",pid=750,fd=6),("nginx",pid=749,fd=6),("nginx",pid=747,fd=6),("nginx",pid=746,fd=6),("nginx",pid=745,fd=6),("nginx",pid=744,fd=6),("nginx",pid=743,fd=6),("nginx",pid=742,fd=6),("nginx",pid=741,fd=6),("nginx",pid=740,fd=6),("nginx",pid=738,fd=6),("nginx",pid=737,fd=6),("nginx",pid=736,fd=6))
tcp   LISTEN 0      511             [::]:80           [::]:*    users:(("nginx",pid=750,fd=7),("nginx",pid=749,fd=7),("nginx",pid=747,fd=7),("nginx",pid=746,fd=7),("nginx",pid=745,fd=7),("nginx",pid=744,fd=7),("nginx",pid=743,fd=7),("nginx",pid=742,fd=7),("nginx",pid=741,fd=7),("nginx",pid=740,fd=7),("nginx",pid=738,fd=7),("nginx",pid=737,fd=7),("nginx",pid=736,fd=7))

$ ss -t state established
Recv-Q Send-Q Local Address:Port Peer Address:PortProcess

$ netstat -tuln
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State      
tcp        0      0 127.0.0.53:53           0.0.0.0:*               LISTEN     
tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN     
tcp6       0      0 :::80                   :::*                    LISTEN     
udp        0      0 127.0.0.53:53           0.0.0.0:*                          

$ netstat -i
Kernel Interface table
Iface      MTU    RX-OK RX-ERR RX-DRP RX-OVR    TX-OK TX-ERR TX-DRP TX-OVR Flg
eth0     65535     2940      0      0 0          1854      0      0      0 BMRU
lo       65536        0      0      0 0             0      0      0      0 LRU

$ netstat -s | head -n 20
Ip:
    Forwarding: 1
    2918 total packets received
    0 forwarded
    0 incoming packets discarded
    2918 incoming packets delivered
    1826 requests sent out
    OutTransmits: 1840
Icmp:
    41 ICMP messages received
    0 input ICMP message failed
    ICMP input histogram:
        timeout in transit: 12
        echo replies: 29
    46 ICMP messages sent
    0 ICMP messages failed
    ICMP output histogram:
        destination unreachable: 2
        echo requests: 44
IcmpMsg:

```

### What I understood — Ports and sockets

- `ss` ("socket statistics") is the modern replacement for `netstat`. It reads
  kernel socket data directly, so it is dramatically faster on busy servers.
- The flag combination to memorise is **`ss -tulnp`**:
  - **`-t`** TCP, **`-u`** UDP, **`-l`** listening sockets only,
  - **`-n`** numeric (don't resolve names or translate port numbers — much
    faster, and shows `:80` instead of `:http`),
  - **`-p`** show the **process** holding the socket (needs root).
- Reading my output: **`0.0.0.0:80 LISTEN`** with
  `users:(("nginx",pid=750,...))` means nginx is listening on port 80 on
  **all IPv4 interfaces**. `[::]:80` is the same for IPv6.
- **`0.0.0.0` vs `127.0.0.1` is the important distinction.** `0.0.0.0` means
  "reachable from anywhere"; **`127.0.0.53%lo:53`** (systemd-resolved) is bound
  to **loopback only**, so nothing outside the machine can reach it. When a
  service is unreachable from another host but works locally, this is the first
  thing to check — it is bound to localhost instead of `0.0.0.0`.
- `ss -t state established` showed no rows: this machine has no open TCP
  conversations at rest, only listeners. Same command mid-request would show
  the live connections.
- **`Send-Q` on a listening socket is the accept-queue backlog** (511 for
  nginx). On a *connected* socket, a persistently non-zero `Recv-Q` means the
  application is not reading fast enough — a real performance signal.
- Note the same port 80 is listed against **13 nginx PIDs**: the master process
  opened the socket and every worker inherited the file descriptor. That is how
  nginx load-balances across workers.
- `netstat -tuln` shows the same picture in the older format. `netstat -i` is
  per-interface packet counters — the **`RX-ERR`/`RX-DRP`** columns are what you
  check for a flaky NIC or cable.

**The single most useful one-liner:** `ss -tulnp | grep :8080` — "what on earth
is already using the port my app wants?"

---

## 7. Testing a remote port — `nc`, `telnet`

```console
$ nc -zv github.com 443
Connection to github.com (20.207.73.82) 443 port [tcp/https] succeeded!

$ nc -zv github.com 80
Connection to github.com (20.207.73.82) 80 port [tcp/http] succeeded!

$ nc -zvw3 github.com 12345 || echo '(port 12345 is closed/filtered - expected)'
nc: connect to github.com (20.207.73.82) port 12345 (tcp) timed out: Operation now in progress
(port 12345 is closed/filtered - expected)

$ timeout 5 bash -c 'cat < /dev/null > /dev/tcp/github.com/443' && echo 'port 443 reachable via bash /dev/tcp'
port 443 reachable via bash /dev/tcp

```

### What I understood — Testing a remote port

- `ping` tests a **host**; it cannot tell you whether a **service** is up. For
  that you must open a TCP connection to the port.
- **`nc -zv host port`** is the tool: **`-z`** means "scan only — connect, then
  close immediately without sending data", **`-v`** makes it report the result.
- The three outcomes and what each one means in practice:
  - **`succeeded!`** — the TCP handshake completed. Something is listening.
  - **`Connection refused`** — the packet *reached* the host and the OS actively
    replied "nothing is listening here" (a TCP RST). This is good news for
    debugging: the network path works, only the service is down.
  - **`timed out`** — no answer at all, which is what port 12345 gave. Almost
    always a **firewall / security group silently dropping** the packet, not a
    stopped service. **Refused = service problem; timed out = firewall problem.**
    This distinction saves hours.
- **`-w3`** sets a 3-second timeout, essential in scripts so a filtered port
  doesn't hang the run.
- `bash`'s built-in **`/dev/tcp/host/port`** does the same test with no tools
  installed at all — invaluable inside minimal containers where `nc`, `curl` and
  `telnet` are all absent.
- `telnet host port` is the old equivalent, and is still handy because it leaves
  the connection **open** so you can type raw protocol commands by hand.

---

## 8. HTTP — `curl`, `wget`

```console
$ curl -s -o /dev/null -w 'HTTP status: %{http_code}\nTotal time: %{time_total}s\nRemote IP: %{remote_ip}\n' https://github.com
HTTP status: 200
Total time: 0.609644s
Remote IP: 20.207.73.82

$ curl -I https://github.com
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0HTTP/2 200 
date: Thu, 03 Sep 2026 16:44:12 GMT
content-type: text/html; charset=utf-8
content-language: en-US
vary: X-PJAX, X-PJAX-Container, Turbo-Visit, Turbo-Frame, X-Requested-With, X-GitHub-Client-Version, Accept-Language, Sec-Fetch-Site,Accept-Encoding, Accept, X-Requested-With
etag: W/"36e52caafa78c45f4ae6f05c7a24d404"
cache-control: max-age=0, private, must-revalidate
strict-transport-security: max-age=31536000; includeSubdomains; preload
x-frame-options: deny
x-content-type-options: nosniff
x-xss-protection: 0
referrer-policy: origin-when-cross-origin, strict-origin-when-cross-origin
content-security-policy: default-src 'none'; base-uri 'self'; child-src github.githubassets.com github.com/assets-cdn/worker/ github.com/assets/ gist.github.com/assets-cdn/worker/; connect-src 'self' uploads.github.com www.githubstatus.com collector.github.com raw.githubusercontent.com api.github.com github-cloud.s3.amazonaws.com github-production-repository-file-5c1aeb.s3.amazonaws.com github-production-upload-manifest-file-7fdce7.s3.amazonaws.com github-production-user-asset-6210df.s3.amazonaws.com *.rel.tunnels.api.visualstudio.com wss://*.rel.tunnels.api.visualstudio.com github.githubassets.com objects-origin.githubusercontent.com copilot-proxy.githubusercontent.com proxy.individual.githubcopilot.com proxy.business.githubcopilot.com proxy.enterprise.githubcopilot.com *.actions.githubusercontent.com wss://*.actions.githubusercontent.com productionresultssa0.blob.core.windows.net productionresultssa1.blob.core.windows.net productionresultssa2.blob.core.windows.net productionresultssa3.blob.core.windows.net productionresultssa4.blob.core.windows.net productionresultssa5.blob.core.windows.net productionresultssa6.blob.core.windows.net productionresultssa7.blob.core.windows.net productionresultssa8.blob.core.windows.net productionresultssa9.blob.core.windows.net productionresultssa10.blob.core.windows.net productionresultssa11.blob.core.windows.net productionresultssa12.blob.core.windows.net productionresultssa13.blob.core.windows.net productionresultssa14.blob.core.windows.net productionresultssa15.blob.core.windows.net productionresultssa16.blob.core.windows.net productionresultssa17.blob.core.windows.net productionresultssa18.blob.core.windows.net productionresultssa19.blob.core.windows.net github-production-repository-image-32fea6.s3.amazonaws.com github-production-release-asset-2e65be.s3.amazonaws.com insights.github.com wss://alive.github.com wss://alive-staging.github.com api.githubcopilot.com api.individual.githubcopilot.com api.business.githubcopilot.com api.enterprise.githubcopilot.com wss://production-copilot-host.webpubsub.azure.com edge.fullstory.com rs.fullstory.com; font-src github.githubassets.com; form-action 'self' github.com gist.github.com copilot-workspace.githubnext.com objects-origin.githubusercontent.com; frame-ancestors 'none'; frame-src viewscreen.githubusercontent.com notebooks.githubusercontent.com www.youtube-nocookie.com; img-src 'self' data: blob: github.githubassets.com media.githubusercontent.com camo.githubusercontent.com identicons.github.com avatars.githubusercontent.com private-avatars.githubusercontent.com github-cloud.s3.amazonaws.com objects.githubusercontent.com release-assets.githubusercontent.com secured-user-images.githubusercontent.com user-images.githubusercontent.com private-user-images.githubusercontent.com opengraph.githubassets.com repository-images.githubusercontent.com marketplace-screenshots.githubusercontent.com copilotprodattachments.blob.core.windows.net/github-production-copilot-attachments/ github-production-user-asset-6210df.s3.amazonaws.com customer-stories-feed.github.com spotlights-feed.github.com explore-feed.github.com objects-origin.githubusercontent.com *.githubusercontent.com images.ctfassets.net/8aevphvgewt8/; manifest-src 'self'; media-src github.com user-images.githubusercontent.com secured-user-images.githubusercontent.com private-user-images.githubusercontent.com github-production-user-asset-6210df.s3.amazonaws.com gist.github.com github.githubassets  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
.com assets.ctfassets.net/8aevphvgewt8/ videos.ctfassets.net/8aevphvgewt8/; script-src github.githubassets.com; style-src 'unsafe-inline' github.githubassets.com; upgrade-insecure-requests; worker-src github.githubassets.com github.com/assets-cdn/worker/ github.com/assets/ gist.github.com/assets-cdn/worker/
server: github.com
accept-ranges: bytes
set-cookie: _gh_sess=lcNe7PGRdloX1tckHVWHCJPy3WV8wVkfdSHcVUoTOmD2XXJYeAPWWM2YHbA1tD%2BUwJ9%2FdbWogh2LDtfF%2BmJ%2BNumKJRhK5wJuu58NucOm9kYMUXk7B4kR87MNQq3tnL8ShY%2FDJyGbRfZdI1wJoypqVeleYBcIUOsERTAgWitzGyKHv0BSi2k2I8iACUIPgGnfGzLQuLXSUFAlFFoLYpp2e1Yxa5r6Aqs%2F003vdOGie0M9RFRVFnKl5bzOv%2BTukF4iOfCPU1gEwqvFR0bsfsxlMw%3D%3D--gnghCL7xSL6UsafY--CnEeXinVLmPV9VdCk2%2BSog%3D%3D; path=/; HttpOnly; secure; SameSite=Lax
set-cookie: _octo=GH1.1.1117933478.1788453861; expires=Fri, 03 Sep 2027 16:44:21 GMT; domain=.github.com; path=/; secure; SameSite=Lax
set-cookie: logged_in=no; expires=Fri, 03 Sep 2027 16:44:21 GMT; domain=.github.com; path=/; HttpOnly; secure; SameSite=Lax
x-github-request-id: E73C:13931C:62EC54:6AFE5F:6A99A3E5
x-github-edge-region: centralindia


$ curl -s https://api.github.com/users/astro-dude | head -n 12
{
  "login": "Astro-Dude",
  "id": 172935099,
  "node_id": "U_kgDOCk7Huw",
  "avatar_url": "https://avatars.githubusercontent.com/u/172935099?v=4",
  "gravatar_id": "",
  "url": "https://api.github.com/users/Astro-Dude",
  "html_url": "https://github.com/Astro-Dude",
  "followers_url": "https://api.github.com/users/Astro-Dude/followers",
  "following_url": "https://api.github.com/users/Astro-Dude/following{/other_user}",
  "gists_url": "https://api.github.com/users/Astro-Dude/gists{/gist_id}",
  "starred_url": "https://api.github.com/users/Astro-Dude/starred{/owner}{/repo}",

$ curl -sS -D - -o /dev/null https://example.com
HTTP/2 200 
date: Thu, 03 Sep 2026 16:44:23 GMT
content-type: text/html
server: cloudflare
last-modified: Sun, 30 Aug 2026 04:11:49 GMT
allow: GET, HEAD
accept-ranges: bytes
age: 1394
cf-cache-status: HIT
cf-ray: a35638097be47ff5-MAA


$ wget -q -O - https://example.com | head -n 12
<!doctype html><html lang="en"><head><title>Example Domain</title><link rel="icon" href="data:,"><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{background:#eee;width:60vw;margin:15vh auto;font-family:system-ui,sans-serif}h1{font-size:1.5em}div{opacity:0.8}a:link,a:visited{color:#348}</style></head><body><div><h1>Example Domain</h1><p>This domain is for use in documentation examples without needing permission. Avoid use in operations.</p><p><a href="https://iana.org/domains/example">Learn more</a></p></div></body></html>

$ wget --spider -S https://example.com 2>&1 | head -n 12
Spider mode enabled. Check if remote file exists.
--2026-09-03 16:44:24--  https://example.com/
Resolving example.com (example.com)... 172.66.147.243, 104.20.23.154
Connecting to example.com (example.com)|172.66.147.243|:443... connected.
HTTP request sent, awaiting response... 
  HTTP/1.1 200 OK
  Date: Thu, 03 Sep 2026 16:44:24 GMT
  Content-Type: text/html
  Connection: keep-alive
  Server: cloudflare
  last-modified: Sun, 30 Aug 2026 04:11:49 GMT
  allow: GET, HEAD

```

### What I understood — HTTP

- `curl` is the workhorse for testing anything that speaks HTTP.
- **`-I`** sends a `HEAD` request — headers only, no body. The fastest way to
  check status codes, redirects and cache headers.
- **`-s`** silences the progress meter, **`-o /dev/null`** discards the body,
  and **`-w`** prints selected variables. The combination
  `curl -s -o /dev/null -w '%{http_code}'` is the standard health-check idiom
  and is what I used to get **HTTP status 200**, the total time and the resolved
  remote IP in one line.
- **`-D -`** dumps the response headers to stdout while still discarding the
  body, which is how I captured `example.com`'s headers.
- Reading status codes: **2xx** success, **3xx** redirect (check the `Location`
  header), **4xx** you sent something wrong (401 unauthenticated, 403 forbidden,
  404 missing), **5xx** the server broke. `curl` follows redirects only if you
  pass **`-L`** — a very common gotcha when a `301` looks like an empty response.
- `curl https://api.github.com/users/astro-dude` returned live JSON from the
  GitHub API, showing curl is equally the tool for API work, not just web pages.
- `wget` overlaps but has a different default: **it saves to a file**, whereas
  curl prints to stdout. `wget -O -` forces stdout. `wget` wins for recursive
  downloads and for `--spider` (check a URL exists without downloading it);
  `curl` wins for APIs, custom methods and headers.
- Other flags worth knowing: `-L` follow redirects, `-H` add a header,
  `-X POST -d '...'` send a body, `-k` skip certificate verification (debugging
  only — never in production), `-v` show the whole TLS and HTTP exchange.

---

## 9. Packet capture — `tcpdump`

```console
$ tcpdump -i eth0 -c 5 -n icmp   (in one shell, while pinging in another)
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on eth0, link-type EN10MB (Ethernet), snapshot length 262144 bytes
16:44:26.495886 IP 172.17.0.3 > 8.8.8.8: ICMP echo request, id 5, seq 1, length 64
16:44:26.516802 IP 8.8.8.8 > 172.17.0.3: ICMP echo reply, id 5, seq 1, length 64
16:44:27.498094 IP 172.17.0.3 > 8.8.8.8: ICMP echo request, id 5, seq 2, length 64
16:44:27.742599 IP 8.8.8.8 > 172.17.0.3: ICMP echo reply, id 5, seq 2, length 64
16:44:28.505359 IP 172.17.0.3 > 8.8.8.8: ICMP echo request, id 5, seq 3, length 64
5 packets captured
5 packets received by filter
0 packets dropped by kernel

```

### What I understood — Packet capture

- `tcpdump` shows you what is **actually on the wire**, which is the final
  arbiter when the higher-level tools disagree with each other.
- Flags used: **`-i eth0`** the interface, **`-c 5`** stop after 5 packets,
  **`-n`** don't resolve names (fast, and avoids DNS traffic polluting your own
  capture), and the trailing **`icmp`** is a *filter expression*, not a flag.
- My capture ran while a `ping` was issued in parallel, and it recorded the
  conversation in matched pairs:
  `172.17.0.3 > 8.8.8.8: ICMP echo request` followed by
  `8.8.8.8 > 172.17.0.3: ICMP echo reply`, roughly 20 ms apart.
- **Seeing request-but-no-reply is the diagnostic gold.** It proves your packets
  are leaving the machine and the *other* end is the problem — which cleanly
  separates "my firewall is dropping outbound" from "they never answered".
- Useful filters: `port 80`, `host 10.0.0.5`, `tcp`, `udp port 53`, and
  combinations like `tcp and port 443 and host github.com`.
- `-w capture.pcap` writes a file you can open in **Wireshark** for a full GUI
  analysis; `-A` prints payloads as ASCII, which is readable for plain HTTP but
  useless for HTTPS since the payload is encrypted.
- Requires root, and on a busy interface you should **always** use a filter —
  an unfiltered capture on a production box floods instantly.

---

## 10. Domain ownership — `whois`

```console
$ whois github.com | head -n 25
   Domain Name: GITHUB.COM
   Registry Domain ID: 1264983250_DOMAIN_COM-VRSN
   Registrar WHOIS Server: whois.markmonitor.com
   Registrar URL: http://www.markmonitor.com
   Updated Date: 2024-09-07T09:16:32Z
   Creation Date: 2007-10-09T18:20:50Z
   Registry Expiry Date: 2026-10-09T18:20:50Z
   Registrar: MarkMonitor Inc.
   Registrar IANA ID: 292
   Registrar Abuse Contact Email: abusecomplaints@markmonitor.com
   Registrar Abuse Contact Phone: +1.2086851750
   Domain Status: clientDeleteProhibited https://icann.org/epp#clientDeleteProhibited
   Domain Status: clientTransferProhibited https://icann.org/epp#clientTransferProhibited
   Domain Status: clientUpdateProhibited https://icann.org/epp#clientUpdateProhibited
   Name Server: DNS1.P08.NSONE.NET
   Name Server: DNS2.P08.NSONE.NET
   Name Server: DNS3.P08.NSONE.NET
   Name Server: DNS4.P08.NSONE.NET
   Name Server: NS-1283.AWSDNS-32.ORG
   Name Server: NS-1707.AWSDNS-21.CO.UK
   Name Server: NS-421.AWSDNS-52.COM
   Name Server: NS-520.AWSDNS-01.NET
   DNSSEC: unsigned
   URL of the ICANN Whois Inaccuracy Complaint Form: https://www.icann.org/wicf/
>>> Last update of whois database: 2026-09-03T16:44:42Z <<<

```

### What I understood — WHOIS

- `whois` queries the **domain registration** databases — registrar, creation
  and expiry dates, status flags and authoritative nameservers.
- From the live output for `github.com`: registered **2007-10-09**, expiring
  **2026-10-09**, registrar **MarkMonitor Inc.**
- The **`Name Server`** lines are the operationally useful part — they must
  match what `dig NS` returns. A mismatch means a delegation problem, which is a
  genuinely nasty class of DNS bug.
- **`clientTransferProhibited`** and its siblings are registrar locks that stop
  the domain being transferred or deleted without explicit unlocking — a basic
  anti-hijacking protection every production domain should have set.
- Practical uses: checking whether a domain is about to **expire** (an
  embarrassingly common cause of total outages), confirming who to contact about
  abuse, and verifying ownership before a migration.
- Note that registrant contact details are now mostly redacted for privacy
  under GDPR, so modern `whois` output is far less revealing than older
  tutorials suggest.

---

## Summary

| # | Area | Commands practised | Status |
|---|---|---|---|
| 1 | Interfaces | `ip addr`, `ip -brief addr`, `ifconfig`, `ip link`, `hostname -I` | Done |
| 2 | Routing & ARP | `ip route`, `ip route get`, `route -n`, `ip neigh`, `arp -n` | Done |
| 3 | Connectivity | `ping` (count, size, by name and by IP) | Done |
| 4 | Path tracing | `traceroute`, `traceroute -I`, `mtr -r` | Done |
| 5 | DNS | `dig`, `dig +short`, `MX`/`NS`/reverse, `nslookup`, `host`, `getent`, `/etc/resolv.conf`, `/etc/hosts` | Done |
| 6 | Sockets | `ss -tuln`, `ss -tulnp`, `ss state established`, `netstat -tuln`, `netstat -i`, `netstat -s` | Done |
| 7 | Remote ports | `nc -zv`, `nc -zvw3`, bash `/dev/tcp` | Done |
| 8 | HTTP | `curl -I`, `curl -w`, `curl -D -`, `wget -O -`, `wget --spider` | Done |
| 9 | Packet capture | `tcpdump -i eth0 -c 5 -n icmp` | Done |
| 10 | Ownership | `whois` | Done |

### The three things I'll actually remember

1. **Work up the ladder in order** — IP, route, gateway, internet by IP, DNS,
   then the application. Each step only makes sense if the one below it passed.
2. **"Connection refused" and "timed out" mean completely different things.**
   Refused = the host answered, the service is down. Timed out = a firewall ate
   the packet silently.
3. **`ss -tulnp` and `curl -s -o /dev/null -w '%{http_code}'`** are the two
   commands I will type most often for the rest of my career.
