# 04 · VPC: Virtual Private Cloud (Networking)

> **Hands-on environment:** run against the local AWS emulator (moto server on
> `localhost:4566`, see the [Session 18 README](../../README.md)), not a real
> AWS account. The emulator implements the VPC **API** (IDs, CIDR checks,
> routes, rules), but **no packets flow**, so reachability and the firewall
> behaviour below are **conceptual**. Transcripts:
> [`evidence/vpc-handson.txt`](evidence/vpc-handson.txt) and
> [`evidence/cidr-math.txt`](evidence/cidr-math.txt). `aws` below means
> `aws --endpoint-url http://localhost:4566`. The
> [Session 19 project](../../../19-cloud-terraform/README.md) builds a VPC like
> this one with Terraform.

## What is a VPC?

A VPC is **your own logically isolated private network inside an AWS
region**. You choose:

- its IP range,
- how it is cut into subnets,
- how traffic is routed, and
- what may enter or leave.

A VPC **spans every AZ in its region**, while each subnet lives in exactly
one AZ. Every account gets a *default VPC* (`172.31.0.0/16`) in each region, so
beginners can launch instances immediately. Real workloads use custom VPCs
like the one below.

```
Region ap-south-1 ─────────────────────────────────────────────────────────────────────
│  VPC 10.0.0.0/16                                                     Internet
│  ┌──────────── AZ ap-south-1a ─────────┐ ┌──────────── AZ ap-south-1b ─────────┐  ▲
│  │ public-a  10.0.1.0/24               │ │ public-b  10.0.2.0/24               │  │
│  │   NAT GW (Elastic IP), ALB, bastion │ │   ALB                               │──┤ IGW
│  ├─────────────────────────────────────┤ ├─────────────────────────────────────┤  │
│  │ private-a 10.0.11.0/24              │ │ private-b 10.0.12.0/24              │  │
│  │   app servers, RDS primary          │ │   app servers, RDS standby          │  │
│  └─────────────────────────────────────┘ └─────────────────────────────────────┘  │
│   public RT : 10.0.0.0/16 → local, 0.0.0.0/0 → igw-…                              │
│   private RT: 10.0.0.0/16 → local, 0.0.0.0/0 → nat-…  (outbound only)             │
───────────────────────────────────────────────────────────────────────────────────────
```

## CIDR

**Classless Inter-Domain Routing** notation `a.b.c.d/n` means "the first *n*
bits are the network, and the remaining 32−*n* bits number the hosts". So a
`/n` block contains 2^(32−n) addresses:

| CIDR | Host bits | Addresses | Typical use |
|---|---|---|---|
| /16 | 16 | 65,536 | a VPC (the largest AWS allows) |
| /20 | 12 | 4,096 | a large subnet (default-VPC subnets are /20) |
| /24 | 8 | 256 (251 usable in AWS) | a normal subnet |
| /28 | 4 | 16 (11 usable) | the smallest subnet AWS allows |
| /32 | 0 | 1 | one host (e.g. "SSH only from my laptop") |

Use the private ranges from RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`,
`192.168.0.0/16`). Pick ranges that **don't overlap** other VPCs or your office
network, or you won't be able to peer or VPN them later.

The maths for this layout, done with Python's `ipaddress` module
([`cidr_math.py`](cidr_math.py)), with real output:

```
$ python3 cidr_math.py
VPC 10.0.0.0/16: netmask 255.255.0.0, 65536 addresses (10.0.0.0 - 10.0.255.255)
/16 split into /24s -> 256 subnets of 256 addresses
public-a  (ap-south-1a)  10.0.1.0/24    total=256  usable in AWS=251  first usable=10.0.1.4  last usable=10.0.1.254
public-b  (ap-south-1b)  10.0.2.0/24    total=256  usable in AWS=251  first usable=10.0.2.4  last usable=10.0.2.254
private-a (ap-south-1a)  10.0.11.0/24   total=256  usable in AWS=251  first usable=10.0.11.4  last usable=10.0.11.254
private-b (ap-south-1b)  10.0.12.0/24   total=256  usable in AWS=251  first usable=10.0.12.4  last usable=10.0.12.254
reserved in 10.0.1.0/24: 10.0.1.0, 10.0.1.1, 10.0.1.2, 10.0.1.3, 10.0.1.255
10.0.1.25    in VPC? True   -> public-a  (ap-south-1a)
10.0.12.200  in VPC? True   -> private-b (ap-south-1b)
10.1.0.5     in VPC? False  -> not in any subnet
overlap 10.0.0.0/16 vs 10.0.128.0/17 : True
overlap 10.0.0.0/16 vs 10.1.0.0/16   : False
```

AWS reserves **5 addresses in every subnet**:

| Address | Reserved for |
|---|---|
| `.0` | network address |
| `.1` | VPC router |
| `.2` | Amazon DNS |
| `.3` | future use |
| `.255` | broadcast (not supported, still reserved) |

Hence 256 − 5 = **251**.

## Subnets

A subnet is a slice of the VPC's CIDR, **pinned to one AZ**. Resources (EC2,
RDS, Lambda ENIs …) are always launched *into a subnet*. Spread subnets across
at least 2 AZs so that one AZ failing doesn't take you down.

```
$ aws ec2 create-vpc --cidr-block 10.0.0.0/16 ... --query Vpc.VpcId --output text
vpc-3063ec3332b392c96
$ aws ec2 create-subnet --vpc-id vpc-3063ec3332b392c96 --cidr-block 10.0.1.0/24 --availability-zone ap-south-1a ...
subnet-74faecc42a1671314
   (… public-b 10.0.2.0/24, private-a 10.0.11.0/24, private-b 10.0.12.0/24 …)
$ aws ec2 modify-subnet-attribute --subnet-id subnet-74faecc42a1671314 --map-public-ip-on-launch

# a subnet outside the VPC's CIDR is rejected
$ aws ec2 create-subnet --vpc-id vpc-3063ec3332b392c96 --cidr-block 10.1.0.0/24
aws: [ERROR]: An error occurred (InvalidSubnet.Range) when calling the CreateSubnet operation: The CIDR '10.1.0.0/24' is invalid.
```

The `10.1.0.0/24` rejection is the same answer `cidr_math.py` gave
(`10.1.0.5 in VPC? False`). Final layout:

```
$ aws ec2 describe-subnets --filters Name=vpc-id,Values=vpc-3063ec3332b392c96 --query ...[Name,CidrBlock,AZ,MapPublicIpOnLaunch,AvailableIpAddressCount] --output table
+-----------+----------------+---------------+--------+------+
|  public-a |  10.0.1.0/24   |  ap-south-1a  |  True  |  250 |
|  private-a|  10.0.11.0/24  |  ap-south-1a  |  False |  251 |
|  private-b|  10.0.12.0/24  |  ap-south-1b  |  False |  251 |
|  public-b |  10.0.2.0/24   |  ap-south-1b  |  True  |  251 |
+-----------+----------------+---------------+--------+------+
```

`public-a` shows **250** free addresses, not 251. The NAT gateway created in it
(below) took one address for its network interface.

## Route tables

A route table is a set of `destination CIDR → target` rules, and each subnet is
associated with **exactly one** table. The **most specific match wins**
(longest prefix). Every table automatically has the `VPC-CIDR → local` route,
which lets all subnets in the VPC talk to each other and can't be removed.

```
$ aws ec2 describe-route-tables --route-table-ids rtb-ff2c1baffe8ee701a rtb-3e483b10daa5c4e5e --query ...
[
    {
        "RouteTable": "rtb-ff2c1baffe8ee701a",
        "Routes": [ ["10.0.0.0/16", "local"], ["0.0.0.0/0", "igw-a92adf35cb92b8c3d"] ],
        "Subnets": [ "subnet-74faecc42a1671314", "subnet-09ee94ea805516ede" ]
    },
    {
        "RouteTable": "rtb-3e483b10daa5c4e5e",
        "Routes": [ ["10.0.0.0/16", "local"], ["0.0.0.0/0", "nat-761fbaee539b0385c"] ],
        "Subnets": [ "subnet-b625d2292bd23505a", "subnet-c9741e805f1b8061e" ]
    }
]
```

(Inner arrays condensed onto one line.) Take a packet from `10.0.11.20` to
`142.250.1.1`. It doesn't match `10.0.0.0/16`, so it matches `0.0.0.0/0` and
goes to the NAT gateway. A packet from the same host to `10.0.2.9` matches
`local` and stays inside the VPC.

## Internet Gateway (IGW)

The IGW is the VPC's door to the internet:

- **one per VPC**,
- horizontally scaled by AWS, with no bandwidth limit or single point of
  failure, and
- free.

It does **1:1 NAT** between an instance's private IP and its public/Elastic
IP. On its own it does nothing; a route table has to point `0.0.0.0/0` at it.

```
$ aws ec2 create-internet-gateway --query InternetGateway.InternetGatewayId --output text
igw-a92adf35cb92b8c3d
$ aws ec2 attach-internet-gateway --internet-gateway-id igw-a92adf35cb92b8c3d --vpc-id vpc-3063ec3332b392c96
$ aws ec2 create-route --route-table-id rtb-ff2c1baffe8ee701a --destination-cidr-block 0.0.0.0/0 --gateway-id igw-a92adf35cb92b8c3d
{
    "Return": true
}
```

## NAT Gateway

A NAT gateway lets instances in **private** subnets start **outbound**
connections (OS updates, calling external APIs, pulling images) while
remaining **unreachable from the internet**. It translates many private IPs to
its one Elastic IP (port address translation).

- It must live in a **public** subnet and have an **Elastic IP**.
- It is **per-AZ**. For high availability, use one NAT per AZ, each with its own
  private route table.
- It is charged per hour plus per GB processed, often a surprisingly large line
  on the bill. VPC endpoints for S3/DynamoDB avoid sending that traffic through
  NAT.

```
$ aws ec2 allocate-address --domain vpc --query AllocationId --output text
eipalloc-4ac851e37c8c7e6f3
$ aws ec2 create-nat-gateway --subnet-id subnet-74faecc42a1671314 --allocation-id eipalloc-4ac851e37c8c7e6f3 --query NatGateway.NatGatewayId --output text
nat-761fbaee539b0385c
$ aws ec2 create-route --route-table-id rtb-3e483b10daa5c4e5e --destination-cidr-block 0.0.0.0/0 --nat-gateway-id nat-761fbaee539b0385c
{
    "Return": true
}
```

## Security Groups

A security group is a **stateful, allow-only** firewall on each network
interface (instance level). Rules can reference **other security groups**,
which is the cleanest way to express tiers. Below, the DB tier accepts
PostgreSQL **only from members of `web-sg`**, whatever their IPs are:

```
$ aws ec2 authorize-security-group-ingress --group-id sg-66eff1d853a7a3a15 --protocol tcp --port 443 --cidr 0.0.0.0/0 --query Return
true
$ aws ec2 authorize-security-group-ingress --group-id sg-1d810a9ee881adac8 --protocol tcp --port 5432 --source-group sg-66eff1d853a7a3a15 --query Return
true
$ aws ec2 describe-security-groups --group-ids sg-1d810a9ee881adac8 --query SecurityGroups[0].IpPermissions[].{Port:FromPort,FromSG:UserIdGroupPairs[0].GroupId}
[
    {
        "Port": 5432,
        "FromSG": "sg-66eff1d853a7a3a15"
    }
]
```

The EC2 side of security groups is covered in the
[EC2 README](../02-ec2/README.md#security-groups).

## Network ACLs

A network ACL is a **stateless, subnet-level** firewall with numbered **allow
and deny** rules, evaluated **lowest number first**; the first match wins.
Because it is stateless, return traffic needs its own rule. For example,
outbound to the **ephemeral ports** 1024–65535, which is where client replies
go.

```
$ aws ec2 create-network-acl-entry --network-acl-id acl-f2b3ebab3f72ec8fa --ingress --rule-number 100 --protocol tcp --port-range From=443,To=443 --cidr-block 0.0.0.0/0 --rule-action allow
$ aws ec2 create-network-acl-entry --network-acl-id acl-f2b3ebab3f72ec8fa --ingress --rule-number 90 --protocol tcp --port-range From=443,To=443 --cidr-block 198.51.100.0/24 --rule-action deny
$ aws ec2 create-network-acl-entry --network-acl-id acl-f2b3ebab3f72ec8fa --egress --rule-number 100 --protocol tcp --port-range From=1024,To=65535 --cidr-block 0.0.0.0/0 --rule-action allow

$ aws ec2 describe-network-acls --network-acl-ids acl-f2b3ebab3f72ec8fa --query ...[Egress,RuleNumber,Protocol,From,To,CidrBlock,RuleAction] --output table
+-------+------+----+-------+--------+-------------------+---------+
|  False|  100 |  6 |  443  |  443   |  0.0.0.0/0        |  allow  |
|  False|  90  |  6 |  443  |  443   |  198.51.100.0/24  |  deny   |
|  True |  100 |  6 |  1024 |  65535 |  0.0.0.0/0        |  allow  |
+-------+------+----+-------+--------+-------------------+---------+
```

(Protocol `6` = TCP.) A request from `198.51.100.7:443` hits rule **90** first
and is denied, even though rule 100 would allow it. That "block one bad range"
job is something a security group **cannot** do, since it has no deny. On real
AWS every NACL also ends in an unremovable `*` rule that denies everything
else. The emulator does not list that rule.

| | Security Group | Network ACL |
|---|---|---|
| Level | network interface (instance) | subnet |
| State | **stateful** (replies allowed automatically) | **stateless** (both directions need rules) |
| Rules | allow only | allow **and** deny |
| Evaluation | all rules together | in number order, first match wins |
| Default | custom SG: deny in / allow out | default NACL: allow all; custom NACL: deny all |
| Typical use | the main, fine-grained control | coarse subnet guardrails, blocking IP ranges |

## Public vs. private subnet

The only thing that makes a subnet "public" is **its route table having
`0.0.0.0/0 → Internet Gateway`**. There is no "public" checkbox.

| | Public subnet | Private subnet |
|---|---|---|
| Default route | `0.0.0.0/0 → igw-…` | `0.0.0.0/0 → nat-…` (or none at all = isolated) |
| Instances get a public IP | yes (`map_public_ip_on_launch = true`) | no |
| Reachable from the internet | yes, if the SG allows it | **no**, never directly |
| Can reach the internet | yes, directly | outbound only, through NAT |
| Put here | load balancers, NAT gateways, bastion hosts | app servers, databases, caches, internal services |

The usual pattern: users → ALB in the public subnets → app servers in the
private subnets → RDS in the private subnets. The app servers get updates
through the NAT gateway. The only internet-facing thing is the load balancer.

## Cleanup

Deletion has to happen in reverse dependency order:

1. route-table associations
2. NACL and security groups
3. route tables
4. NAT gateway, then release the Elastic IP
5. detach and delete the IGW
6. subnets
7. the VPC

```
$ aws ec2 delete-vpc --vpc-id vpc-3063ec3332b392c96
$ aws ec2 describe-vpcs --filters Name=tag:Name,Values=s18-vpc --query Vpcs
[]
```

Getting that order right by hand is tedious and error-prone. Terraform works it
out from the dependency graph, which is a large part of
[Session 19](../../../19-cloud-terraform/README.md).
