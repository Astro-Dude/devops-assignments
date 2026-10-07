# 02 · EC2: Elastic Compute Cloud (Compute)

> **Hands-on environment:** run against the local AWS emulator (moto server on
> `localhost:4566`, see the [Session 18 README](../../README.md)), not a real
> AWS account. The emulator implements the EC2 **API** (it records instances,
> volumes, IPs and states) but boots **no real VM**, so nothing could be
> SSH'd into. Full transcript:
> [`evidence/ec2-handson.txt`](evidence/ec2-handson.txt). `aws` below means
> `aws --endpoint-url http://localhost:4566`.

## What is EC2?

EC2 rents **virtual machines** ("instances") by the second, in any region and
Availability Zone. You choose:

- the **OS image** (AMI),
- the **size** (instance type),
- the **network** (VPC, subnet, security groups), and
- the **disks** (EBS).

You manage everything from the OS upward: patches, runtime, application. That
makes EC2 the classic **IaaS** offering, and the building block underneath
many other services (ECS on EC2, EKS nodes, EMR, Beanstalk).

```
   AMI  +  instance type  +  key pair  +  subnet & security group  +  EBS volumes   ──run-instances──►   instance
 (what)      (how big)        (login)          (where / who can reach)      (disk)
```

## AMI (Amazon Machine Image)

An AMI is the **template** an instance boots from. It contains:

- a snapshot of the root volume (OS plus anything pre-installed),
- the architecture (`x86_64` / `arm64`),
- the virtualisation and boot mode, and
- launch permissions (public, private, or shared with certain accounts).

AMIs are **regional**, so the same OS has a different AMI ID in each region.
Never hard-code one; look it up:

```
$ aws ec2 describe-images --owners amazon --filters Name=name,Values=al2023-ami-2023*-x86_64 --query sort_by(Images,&CreationDate)[-1].{ImageId:ImageId,Name:Name,Arch:Architecture,RootDevice:RootDeviceType}
{
    "ImageId": "ami-00d2dbb426772b03a",
    "Name": "al2023-ami-2023.12.20260727.0-kernel-6.18-x86_64",
    "Arch": "x86_64",
    "RootDevice": "ebs"
}
```

In Terraform the same lookup is a data source:

```hcl
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }
}
# then: ami = data.aws_ami.al2023.id
```

Where AMIs come from:

- AWS: Amazon Linux, Windows
- vendors: Ubuntu/Canonical, Red Hat, and the Marketplace
- yourself: bake a "golden image" with Packer, or run `create-image` on a
  configured instance.

## Instance types

A name like **`c6i.large`** breaks down as follows:

```
c        6           i           .large
family   generation  extra       size
         (newer =    (i = Intel, (nano, micro, small, medium, large, xlarge, 2xlarge, …
         cheaper     g = Graviton  each step ≈ doubles vCPU & RAM)
         per perf)   ARM, d = local NVMe, n = network-optimised)
```

| Family | Optimised for | Typical use |
|---|---|---|
| **t** (t3, t4g) | burstable, cheap; earns CPU credits while idle | dev boxes, small sites, CI runners |
| **m** (m6i, m7g) | general purpose, balanced 1 vCPU : 4 GiB | app servers, most workloads |
| **c** (c6i, c7g) | compute, 1 : 2 | batch, encoding, high-traffic web |
| **r / x** (r6i) | memory, 1 : 8 | in-memory caches, big databases |
| **i / d** | local NVMe / HDD storage | Cassandra, Kafka, data warehouses |
| **p / g / inf / trn** | GPUs and ML accelerators | training, inference, rendering |

Real numbers for three types, from the API:

```
$ aws ec2 describe-instance-types --instance-types t3.micro c6i.large r6i.large --query InstanceTypes[].[InstanceType,VCpuInfo.DefaultVCpus,MemoryInfo.SizeInMiB,BurstablePerformanceSupported] --output table
--------------------------------------
|        DescribeInstanceTypes       |
+-----------+----+---------+---------+
|  c6i.large|  2 |  4096   |  False  |
|  r6i.large|  2 |  16384  |  False  |
|  t3.micro |  2 |  1024   |  True   |
+-----------+----+---------+---------+
```

All three have 2 vCPUs, but the memory goes 1 GiB → 4 GiB → 16 GiB, and only
`t3` is burstable. That's the family letter at work.

Pricing models:

- **On-Demand:** pay per second.
- **Savings Plans / Reserved Instances:** a 1–3 year commitment, up to about
  70% cheaper.
- **Spot:** spare capacity at up to about 90% off, but AWS can reclaim it with
  2 minutes' notice.
- **Dedicated Hosts:** hardware reserved for you.

## Key pairs

EC2 uses SSH **public-key** auth instead of passwords. AWS stores the
**public** key and injects it into `~/.ssh/authorized_keys` at first boot. You
keep the **private** key: AWS shows it **once**, at creation, and cannot
recover it.

```
$ aws ec2 create-key-pair --key-name s18-demo-key --key-type ed25519 --query {KeyName:KeyName,Fingerprint:KeyFingerprint,KeyPairId:KeyPairId}
{
    "KeyName": "s18-demo-key",
    "Fingerprint": "93:54:ee:45:f9:6e:3b:c4:8f:ed:21:23:cd:ba:5b:22:9a:15:ac:f4:ee:8b:09:ac:b6:48:d3:10:f1:92:23:77",
    "KeyPairId": "key-3d3a629499834d31d"
}
```

The `--query` deliberately leaves out `KeyMaterial`, the private key, so it
never ends up in a log or in Git. Normally you would save it with
`--query KeyMaterial --output text > key.pem && chmod 400 key.pem`, then
connect with `ssh -i key.pem ec2-user@<public-ip>`. Better still, use **SSM
Session Manager** and open no SSH port at all.

## Security groups

A security group is a **stateful virtual firewall attached to the instance's
network interface**:

- **Allow rules only.** There is no "deny"; anything not allowed is dropped.
- **Stateful.** If inbound traffic is allowed, the reply goes out
  automatically, and vice versa.
- **Default:** all inbound blocked, all outbound allowed.
- A rule's source can be a CIDR **or another security group**, e.g. "the
  DB accepts 5432 only from members of `web-sg`". See the
  [VPC README](../04-vpc/README.md).

```
$ aws ec2 authorize-security-group-ingress --group-id sg-c45ffdbfec1bfd34c --ip-permissions IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=203.0.113.10/32,Description=admin-laptop}] IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0,Description=http}] --query Return
true

$ aws ec2 describe-security-group-rules --filters Name=group-id,Values=sg-c45ffdbfec1bfd34c --query SecurityGroupRules[].[IsEgress,IpProtocol,FromPort,ToPort,CidrIpv4,Description] --output table
-----------------------------------------------------------------
|                  DescribeSecurityGroupRules                   |
+-------+------+-----+-----+-------------------+----------------+
|  True |  -1  |  -1 |  -1 |  0.0.0.0/0        |  None          |
|  False|  tcp |  22 |  22 |  203.0.113.10/32  |  admin-laptop  |
|  False|  tcp |  80 |  80 |  0.0.0.0/0        |  http          |
+-------+------+-----+-----+-------------------+----------------+
```

- Row 1 is the default **egress allow-all** (protocol `-1` = all).
- SSH is open to **a single /32 address**, not to `0.0.0.0/0`, where bots
  start brute-forcing within minutes.
- HTTP is public.

## EBS (Elastic Block Store)

EBS volumes are **network-attached block disks**. They live in **one AZ**, can
be attached to an instance in that AZ, and survive independently of it.

| Type | What it is | Use |
|---|---|---|
| **gp3** | SSD, 3,000 IOPS / 125 MB/s baseline, tunable separately from size | default for nearly everything |
| io2 / io2 Block Express | provisioned-IOPS SSD, highest durability | busy databases |
| st1 / sc1 | throughput / cold HDD | big sequential data, archives |
| *instance store* | NVMe physically in the host, **lost on stop** | caches, scratch space |

Hands-on: a 20 GiB gp3 root volume from the launch mapping, plus a 10 GiB data
volume that was attached and then **snapshotted**. Snapshots are incremental
backups stored in S3; you can create new volumes or AMIs from them, in any AZ.

```
$ aws ec2 describe-volumes --filters Name=attachment.instance-id,Values=i-375f4ae752b18b194 --query Volumes[].[VolumeId,Size,VolumeType,Attachments[0].Device,State] --output table
+------------------------+-----+------+------------+----------+
|  vol-821b27b52b3a60cca |  20 |  gp3 |  /dev/xvda |  in-use  |
+------------------------+-----+------+------------+----------+

$ aws ec2 attach-volume --volume-id vol-63575e78aadc1862f --instance-id i-375f4ae752b18b194 --device /dev/sdf ...
{
    "Volume": "vol-63575e78aadc1862f",
    "Device": "/dev/sdf",
    "State": "attaching"
}

$ aws ec2 create-snapshot --volume-id vol-63575e78aadc1862f --description s18 data backup ...
{
    "SnapshotId": "snap-38dcda31591f804eb",
    "State": "completed",
    "VolumeSize": 10
}
```

`DeleteOnTermination` decides what happens to a volume when the instance is
terminated. See the lifecycle section below.

## Public vs. private IP

```
$ aws ec2 describe-instances --instance-ids i-375f4ae752b18b194 --query Reservations[0].Instances[0].{PrivateIp:...,PublicIp:...}
{
    "PrivateIp": "10.137.161.174",
    "PrivateDns": "ip-10-137-161-174.ap-south-1.compute.internal",
    "PublicIp": "54.214.9.176",
    "PublicDns": "ec2-54-214-9-176.ap-south-1.compute.amazonaws.com",
    "Subnet": "subnet-b7902bf06bf36f411"
}
```

| | Private IP | Public IP | Elastic IP |
|---|---|---|---|
| From | the subnet's CIDR (RFC 1918) | AWS's public pool | AWS's public pool, **allocated to your account** |
| Reachable from | inside the VPC / peered / VPN | the internet (if SG + route allow) | same as public |
| On stop/start | **kept** | **changes** | **kept** (until you release it) |
| Cost | free | charged per hour (all public IPv4) | charged per hour |

The instance's OS only ever sees the **private** IP. The Internet Gateway
translates public ↔ private one-to-one. An instance gets a public IP only when
its subnet has `map_public_ip_on_launch` (or the launch asks for one), **and**
it is reachable only if the subnet's route table sends `0.0.0.0/0` to an IGW.

## Instance lifecycle

```
            run-instances
                 │
                 ▼
             pending ───────────► running ◄──────── reboot (same host, same IPs, RAM cleared)
                                   │   ▲
                         stop      │   │ start
                                   ▼   │
                     stopping ──► stopped        (no compute charge; EBS still billed;
                                                  public IP released; may move host)
                                   │
       terminate (from running or stopped)
                                   ▼
                     shutting-down ──► terminated (gone; visible ~1 hour, then removed)
```

Captured transitions (each JSON result is squeezed onto one line here; the
full output is in the evidence file):

```
$ aws ec2 stop-instances ...       {"From": "running", "To": "stopping"}
$ aws ec2 describe-instances ...   "stopped"
$ aws ec2 start-instances ...      {"From": "stopped", "To": "pending"}
$ aws ec2 describe-instances ...   "running"
$ aws ec2 terminate-instances ...  {"From": "running", "To": "shutting-down"}
$ aws ec2 describe-instances ...   "terminated"
```

After termination, the two volumes behaved differently:

```
$ aws ec2 describe-volumes --volume-ids vol-821b27b52b3a60cca ...
aws: [ERROR]: An error occurred (InvalidVolume.NotFound) when calling the DescribeVolumes operation: The volume '{'vol-821b27b52b3a60cca'}' does not exist.

$ aws ec2 describe-volumes --volume-ids vol-63575e78aadc1862f ...
{
    "VolumeId": "vol-63575e78aadc1862f",
    "State": "available"
}
```

- The **root** volume had `DeleteOnTermination=true`, so it was deleted with
  the instance.
- The **attached data** volume defaults to `false`, so it survived as
  `available`. Its data is still there, and it is still being billed until you
  delete it.

## Common use cases

- Web/application servers behind a load balancer, in an **Auto Scaling group**
  across AZs.
- Self-managed databases or software that needs OS-level control (custom
  kernels, licensing).
- Batch/HPC and ML training on c/p/g families, often on **Spot**.
- Bastion hosts / jump boxes, CI runners, build agents.
- Kubernetes worker nodes (EKS managed node groups are EC2 under the hood).
- Lift-and-shift migrations of on-prem VMs.

The [Session 19 project](../../../19-cloud-terraform/README.md) launches an EC2
instance with Terraform, inside a custom VPC.
