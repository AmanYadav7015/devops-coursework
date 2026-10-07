# 02 - EC2 (Elastic Compute Cloud)

## This ran against LocalStack, not real AWS

Every command below was executed against **LocalStack 3.8.1 (community edition)** on
`http://localhost:4566`. There are no real AWS credentials on this machine and nothing here was
created in a real AWS account. The instance, key pair, security group and EBS volumes shown were
objects inside that container and were deleted at the end.

LocalStack's EC2 emulator is API-level. It models instance state, networking metadata, volumes and
security groups faithfully enough that the outputs below are the real shape of the real API, but:

- **No Linux is actually booting.** There is no machine to SSH into. The AMI id is a label.
- The AMI catalogue is a small frozen 2017 set (`ubuntu-xenial-16.04`, Windows Server 2016), not the
  live Amazon Linux 2023 / Ubuntu 24.04 images you would see today.
- Security group rules are stored but **not enforced**, because there is no traffic to filter.
- Nothing is billed, so none of the cost reasoning below can be demonstrated - only stated.
- State transitions are instant. Real instances take 30-90 seconds to reach `running`, and a status
  check takes longer still.
- IP addresses come from LocalStack's own ranges and are not routable.

## What is EC2

EC2 is virtual machines as an API call. You pick a template (AMI), a size (instance type), a network
(VPC and subnet), a firewall (security group) and a login mechanism (key pair), and a few seconds
later you have a server you can log into.

The mental model worth holding:

```text
  AMI                  the disk image: OS + preinstalled software
   +
  Instance type        how much CPU / memory / network you get
   +
  Subnet               which VPC and which availability zone
   +
  Security group       stateful firewall on the instance's network interface
   +
  Key pair             the SSH public key baked in at first boot
   =
  Instance             a running virtual machine
   +
  EBS volumes          the virtual disks attached to it
```

EC2 is the oldest and least managed compute service AWS has. That is both the appeal - you control
everything - and the cost: patching, scaling, monitoring and hardening are all yours.

## AMI (Amazon Machine Image)

An AMI is the template an instance boots from: the root filesystem snapshot, the architecture, the
virtualization type and the block device mapping.

```bash
aws --endpoint-url=http://localhost:4566 ec2 describe-images \
  --filters 'Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-xenial*' \
  --query 'Images[].{Id:ImageId,Name:Name,Arch:Architecture,Root:RootDeviceType,Virt:VirtualizationType}' \
  --output table
```

```text
-----------------------------------------------------------------------------
|                              DescribeImages                               |
+------+--------------------------------------------------------------------+
|  Arch|  x86_64                                                            |
|  Id  |  ami-785db401                                                      |
|  Name|  ubuntu/images/hvm-ssd/ubuntu-xenial-16.04-amd64-server-20170721   |
|  Root|  ebs                                                               |
|  Virt|  hvm                                                               |
+------+--------------------------------------------------------------------+
```

Four things to read off that:

- **`ImageId` is region-specific.** `ami-785db401` means something in `us-east-1` and nothing in
  `eu-west-1`. Hardcoding an AMI id in Terraform and then deploying to a second region is a classic
  failure. Use an `aws_ami` data source with filters instead.
- **`Architecture`** must match the instance type. An `x86_64` AMI will not boot on a Graviton
  `t4g.*` instance; you need the `arm64` build.
- **`RootDeviceType: ebs`** means the root disk is a network-attached EBS volume that survives a
  stop/start. The alternative, `instance-store`, is physically attached, faster, and wiped the
  moment the instance stops.
- **`VirtualizationType: hvm`** is the only one that matters now. `paravirtual` is legacy.

Kinds of AMI:

| Kind | Who maintains it | Use |
|---|---|---|
| AWS-provided | AWS (Amazon Linux 2023, Ubuntu, Windows) | Starting point |
| Marketplace | A vendor, often with a per-hour licence charge | Commercial appliances |
| Community | Anyone | Treat with suspicion - nobody is auditing these |
| Your own | You, usually built with Packer or EC2 Image Builder | The right answer for production: a "golden image" with your agents, hardening and base packages already in it, so boot time is seconds and the configuration is identical everywhere |

## Instance types

An instance type is a CPU/memory/network/storage ratio. The naming is systematic:
`m7g.2xlarge` reads as family `m`, generation `7`, processor `g` (Graviton/ARM), size `2xlarge`.

| Family | Optimised for | Typical workload |
|---|---|---|
| `t` | Burstable, cheapest | Dev boxes, low-traffic web servers, anything mostly idle |
| `m` | Balanced | General application servers, the sane default |
| `c` | Compute | Batch processing, CI runners, game servers, video encoding |
| `r`, `x`, `z` | Memory | Databases, in-memory caches, Spark executors |
| `i`, `d` | Storage, local NVMe | NoSQL, data warehouses, anything IO-bound |
| `p`, `g`, `inf`, `trn` | Accelerators | Training, inference, rendering |

Two traps worth knowing:

- **The `t` family burst credit model.** A `t3.micro` gets a baseline fraction of a vCPU and
  accumulates credits while idle. Sustained load burns the credits and then the instance is
  throttled to baseline - which looks exactly like a mysterious performance cliff an hour into a
  load test. `unlimited` mode removes the cliff and adds a surcharge instead.
- **Graviton (`g` suffix: `t4g`, `m7g`, `c7g`) is usually 20-40% cheaper** for the same performance,
  but it is `arm64`. Every container image and every compiled binary has to have an ARM build.

Launch one:

```bash
aws --endpoint-url=http://localhost:4566 ec2 run-instances \
  --image-id ami-785db401 --instance-type t3.micro --count 1 \
  --key-name hw18-demo-key --security-group-ids sg-a68b081ff44139882 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=hw18-web-01},{Key=Environment,Value=dev}]' \
  --query 'Instances[0].{Id:InstanceId,Type:InstanceType,Ami:ImageId,State:State.Name,Private:PrivateIpAddress,Az:Placement.AvailabilityZone,Root:RootDeviceName}'
```

```text
{
    "Id": "i-70bf2561a14791eef",
    "Type": "t3.micro",
    "Ami": "ami-785db401",
    "State": "pending",
    "Private": "10.238.38.230",
    "Az": "us-east-1a",
    "Root": "/dev/sda1"
}
```

`State: pending` is the first state in the lifecycle. Tagging at launch with
`--tag-specifications` rather than a follow-up `create-tags` call matters more than it looks: on
real AWS the gap between the two is a window where a cost-allocation or auto-stop rule that keys off
tags sees an untagged instance.

## Key pairs

A key pair is an SSH keypair where AWS keeps the public half and you keep the private half. At first
boot, cloud-init writes the public key into `~/.ssh/authorized_keys` for the default user
(`ec2-user` on Amazon Linux, `ubuntu` on Ubuntu).

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-key-pair --key-name hw18-demo-key \
  --query '{Name:KeyName,Fingerprint:KeyFingerprint,Id:KeyPairId}'
```

```text
{
    "Name": "hw18-demo-key",
    "Fingerprint": "ee:e7:94:02:c1:1b:c1:d8:28:6e:3a:70:6c:6b:8a:fe",
    "Id": "key-5f59b06a"
}
```

The private key is returned **once**, in the `KeyMaterial` field of the create response, and AWS
never shows it again. Lose it and the only recovery path is to stop the instance, detach the root
volume, attach it to another instance, edit `authorized_keys`, and reattach.

Create it a second time and the API refuses, because key pair names are unique per region:

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-key-pair --key-name hw18-demo-key
```

```text
aws: [ERROR]: An error occurred (InvalidKeyPair.Duplicate) when calling the CreateKeyPair
operation: The keypair 'hw18-demo-key' already exists.
```

Better than key pairs, in order of preference:

1. **AWS Systems Manager Session Manager.** Browser or CLI shell into the instance with no SSH key,
   no port 22 open, no bastion host, and every session logged to CloudTrail and optionally S3. If
   you take one thing from this page, take this one.
2. **EC2 Instance Connect**, which pushes a one-minute-lifetime key.
3. **SSH key pairs**, which is a long-lived secret somebody has to store and rotate.

Changing the key pair on a running instance is not possible through the EC2 API. In Terraform,
`key_name` is a force-new attribute, which is why it shows `# forces replacement` in a plan.

## Security groups

A security group is a **stateful** firewall attached to an elastic network interface. Stateful means
return traffic for an allowed outbound connection is automatically permitted - you do not write a
matching rule for it.

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-security-group \
  --group-name hw18-web-sg --description "hw18 web tier" --vpc-id vpc-26226ba4

aws --endpoint-url=http://localhost:4566 ec2 authorize-security-group-ingress --group-name hw18-web-sg \
  --ip-permissions 'IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=203.0.113.0/24,Description="office"}]' \
                   'IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0,Description="public https"}]'

aws --endpoint-url=http://localhost:4566 ec2 describe-security-groups --group-names hw18-web-sg
```

```text
{
    "GroupId": "sg-a68b081ff44139882",
    "Tags": []
}
{
    "SecurityGroups": [
        {
            "GroupId": "sg-a68b081ff44139882",
            "IpPermissionsEgress": [
                {
                    "IpProtocol": "-1",
                    "UserIdGroupPairs": [],
                    "IpRanges": [
                        {
                            "CidrIp": "0.0.0.0/0"
                        }
                    ],
                    "Ipv6Ranges": [],
                    "PrefixListIds": []
                }
            ],
            "Tags": [],
            "VpcId": "vpc-26226ba4",
            "OwnerId": "000000000000",
            "GroupName": "hw18-web-sg",
            "Description": "hw18 web tier",
            "IpPermissions": [
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "UserIdGroupPairs": [],
                    "IpRanges": [
                        {
                            "Description": "office",
                            "CidrIp": "203.0.113.0/24"
                        }
                    ],
                    "Ipv6Ranges": [],
                    "PrefixListIds": []
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 443,
                    "ToPort": 443,
                    "UserIdGroupPairs": [],
                    "IpRanges": [
                        {
                            "Description": "public https",
                            "CidrIp": "0.0.0.0/0"
                        }
                    ],
                    "Ipv6Ranges": [],
                    "PrefixListIds": []
                }
            ]
        }
    ]
}
```

Everything important about security groups is visible in that output:

- **`IpPermissions` is empty until you add rules.** A new security group allows no inbound traffic
  at all. There is no implicit SSH rule.
- **`IpPermissionsEgress` has `IpProtocol: "-1"` to `0.0.0.0/0` by default** - all outbound traffic
  is allowed, and that rule appeared without anyone asking for it. Locking egress down is a real
  hardening step most teams skip; it is what stops a compromised instance from exfiltrating data or
  calling out to a C2 server.
- **There are no Deny rules.** A security group is allow-list only. If you need to block a specific
  IP, that is a network ACL or AWS Network Firewall, not a security group.
- **`UserIdGroupPairs`** is the field that makes security groups better than CIDR firewalls: a rule
  can reference *another security group* instead of an IP range. "Allow 5432 from `sg-app`" keeps
  working as the app tier autoscales, because it follows identity rather than addresses. Always
  prefer this over a subnet CIDR for internal traffic.
- **`Description` on each `IpRanges` entry** is free documentation. Six months later, `203.0.113.0/24`
  means nothing and `"office"` means everything.

One honest note on the output above: the `authorize-security-group-ingress` response from LocalStack
only echoed back one of the two rules in its `SecurityGroupRules` array, while `describe` correctly
shows both. Real AWS returns both. The authoritative source is always `describe-security-groups`.

A security group applies to the **ENI**, not the subnet. An instance can have up to five, and the
effective permission is the union of all of them - rules are additive, so adding a group can only
ever open more.

## EBS (Elastic Block Store)

EBS is network-attached block storage. It looks like a local disk to the OS, but it lives on
separate hardware and is replicated within one availability zone.

The root volume created with the instance:

```bash
aws --endpoint-url=http://localhost:4566 ec2 describe-volumes \
  --filters Name=attachment.instance-id,Values=i-70bf2561a14791eef \
  --query 'Volumes[].{Id:VolumeId,Size:Size,Type:VolumeType,State:State,Device:Attachments[0].Device,DeleteOnTerm:Attachments[0].DeleteOnTermination}' \
  --output table
```

```text
-------------------------------------------------------------------------
|                            DescribeVolumes                            |
+--------------+------------+---------------+-------+----------+--------+
| DeleteOnTerm |  Device    |      Id       | Size  |  State   | Type   |
+--------------+------------+---------------+-------+----------+--------+
|  False       |  /dev/sda1 |  vol-b0d1393a |  8    |  in-use  |  gp2   |
+--------------+------------+---------------+-------+----------+--------+
```

`DeleteOnTermination` is the attribute to get right. On a real root volume it defaults to `true`, so
terminating the instance deletes the disk. On an attached data volume it defaults to `false`, so the
volume survives - and quietly bills you forever if nobody notices. Orphaned EBS volumes are one of
the top line items in every "why is our AWS bill like this" investigation.

Add a separate data volume:

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-volume \
  --availability-zone us-east-1a --size 20 --volume-type gp3 \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=hw18-data-vol}]' \
  --query '{Id:VolumeId,Size:Size,Type:VolumeType,Az:AvailabilityZone,State:State}'

aws --endpoint-url=http://localhost:4566 ec2 attach-volume \
  --volume-id vol-7fc358fc --instance-id i-70bf2561a14791eef --device /dev/sdf
```

```text
{
    "Id": "vol-7fc358fc",
    "Size": 20,
    "Type": "gp3",
    "Az": "us-east-1a",
    "State": "creating"
}
{
    "VolumeId": "vol-7fc358fc",
    "InstanceId": "i-70bf2561a14791eef",
    "Device": "/dev/sdf",
    "State": "attaching",
    "AttachTime": "2026-10-07T12:39:14+00:00"
}
```

**`--availability-zone us-east-1a` is mandatory and must match the instance.** An EBS volume lives in
exactly one AZ and can only attach to an instance in that same AZ. This is the single most important
EBS constraint and it shapes architecture: if your data is on EBS in `us-east-1a`, your instance
cannot fail over to `us-east-1b` without a snapshot-and-restore. If you need a filesystem shared
across AZs, that is EFS, not EBS.

Volume types:

| Type | Backing | Characteristics | Use for |
|---|---|---|---|
| `gp3` | SSD | 3,000 IOPS and 125 MB/s baseline, independent of size; both tunable | The default. Almost always cheaper and better than `gp2` |
| `gp2` | SSD | IOPS scale with size (3 per GB) | Legacy. Migrate to `gp3` |
| `io2` / `io2 Block Express` | SSD | Up to 256,000 IOPS, 99.999% durability, multi-attach | Serious databases |
| `st1` | HDD | Throughput-optimised, cheap per GB, poor at random IO | Log processing, big sequential scans |
| `sc1` | HDD | Coldest and cheapest | Rarely accessed archives on block storage |

Other EBS facts that matter:

- **Snapshots are incremental and go to S3**, which means they are regional and can be copied across
  regions or shared with another account. That makes snapshots the backup and DR mechanism.
- **Encryption is per-volume and set at creation.** You cannot encrypt a volume in place - you
  snapshot it, copy the snapshot with encryption enabled, and create a new volume. Turn on
  "EBS encryption by default" at the account level and the question never comes up.
- **`gp3`/`io2` volumes can be resized and retyped live**, though the filesystem still needs
  `growpart` plus `resize2fs`/`xfs_growfs` inside the OS.
- **Instance store is not EBS.** `i3`, `d3` and similar types have physically attached NVMe that is
  far faster and is **wiped on stop or terminate**. Use it for scratch, cache and shuffle space,
  never for anything you need to keep.

## Public vs private IP

This is where LocalStack actually models real behaviour well enough to prove the point.

At launch:

```bash
aws --endpoint-url=http://localhost:4566 ec2 describe-instances \
  --instance-ids i-70bf2561a14791eef \
  --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name,Type:InstanceType,Private:PrivateIpAddress,Public:PublicIpAddress,Az:Placement.AvailabilityZone,Vpc:VpcId,Subnet:SubnetId}' \
  --output table
```

```text
------------------------------------
|         DescribeInstances        |
+----------+-----------------------+
|  Az      |  us-east-1a           |
|  Id      |  i-70bf2561a14791eef  |
|  Private |  10.238.38.230        |
|  Public  |  54.214.106.37        |
|  State   |  running              |
|  Subnet  |  subnet-4cf732aa      |
|  Type    |  t3.micro             |
|  Vpc     |  vpc-26226ba4         |
+----------+-----------------------+
```

Now stop it and start it again:

```bash
aws --endpoint-url=http://localhost:4566 ec2 stop-instances --instance-ids i-70bf2561a14791eef
aws --endpoint-url=http://localhost:4566 ec2 describe-instances --instance-ids i-70bf2561a14791eef \
  --query 'Reservations[].Instances[].{State:State.Name,Public:PublicIpAddress,Private:PrivateIpAddress}'
aws --endpoint-url=http://localhost:4566 ec2 start-instances --instance-ids i-70bf2561a14791eef
aws --endpoint-url=http://localhost:4566 ec2 describe-instances --instance-ids i-70bf2561a14791eef \
  --query 'Reservations[].Instances[].{State:State.Name,Public:PublicIpAddress,Private:PrivateIpAddress}'
```

```text
[
    {
        "State": "stopped",
        "Public": null,
        "Private": "10.238.38.230"
    }
]
[
    {
        "State": "running",
        "Public": "54.214.151.227",
        "Private": "10.238.38.230"
    }
]
```

Read that carefully, because it is the whole lesson:

- The **private IP `10.238.38.230` never changed.** It is allocated from the subnet's CIDR at launch
  and is fixed for the life of the instance. It is the address other things in the VPC use.
- The **public IP went away entirely while stopped** (`null`), and came back as a **different
  address**: `54.214.106.37` before, `54.214.151.227` after. An auto-assigned public IP is leased
  from a shared pool, not owned.

So: **never hardcode an auto-assigned public IP, never point DNS at one.** A single stop/start, or
any instance replacement, invalidates it. The fixes, in increasing order of goodness:

1. **Elastic IP** - a static public IPv4 you own and can remap between instances. Note that since
   2024 AWS charges for every public IPv4 address, attached or not.
2. **Load balancer** - the ALB/NLB has the stable DNS name and the instances behind it stay private.
3. **Private only, plus a NAT gateway for outbound.** The best answer for anything that does not
   need to be reachable from the internet. See `../04-vpc/README.md`.

A public IP is also not configured on the instance's interface. The OS only ever sees
`10.238.38.230`; the public address is a one-to-one NAT performed by the VPC. That is why
`ip addr` on a real EC2 instance never shows the public IP and confuses people the first time.

## Instance lifecycle

```text
                run-instances
                     |
                     v
                 [pending]
                     |
                     v
   stop-instances [running] <------- start-instances
        |            |   |                  ^
        v            |   | reboot-instances |
   [stopping]        |   +------------------+
        |            |
        v            | terminate-instances
   [stopped] --------+------> [shutting-down] ----> [terminated]
```

Captured from the real transitions above:

```text
stop:   {"Id": "i-70bf2561a14791eef", "Prev": "running", "Now": "stopping"}
start:  {"Id": "i-70bf2561a14791eef", "Prev": "stopped", "Now": "pending"}
```

What each transition actually does:

| State / action | Billing | Root EBS | Instance store | Private IP | Public IP |
|---|---|---|---|---|---|
| `pending` | Not yet | Being attached | - | Assigned | Assigned if the subnet says so |
| `running` | **Charged per second** | Attached | Attached | Fixed | Fixed until stop |
| `stopping` / `stopped` | No compute charge, **EBS still billed** | Preserved | **Wiped** | Preserved | **Released** |
| `reboot` | Charged throughout | Preserved | **Preserved** | Preserved | **Preserved** |
| `shutting-down` / `terminated` | Stops | Deleted if `DeleteOnTermination` | Wiped | Gone | Gone |

Three consequences worth internalising:

- **Reboot is not stop-then-start.** Reboot keeps instance store data and the public IP; a
  stop/start loses both. If you need a configuration change that requires an instance type change,
  you need a stop/start, and that means you need an Elastic IP or a load balancer in front.
- **A stopped instance still costs money** - EBS volumes, snapshots and any Elastic IP are billed
  whether the instance is running or not.
- **Termination protection** (`disable-api-termination`) is a one-line setting that has saved a lot
  of production databases.

Purchase options, since lifecycle and cost are entangled:

| Option | Discount | Catch |
|---|---|---|
| On-Demand | None | Baseline |
| Savings Plans / Reserved | Up to ~72% | 1 or 3 year commitment |
| Spot | Up to ~90% | AWS can reclaim it with a 2-minute warning. Great for CI, batch and stateless workers; wrong for a database |
| Dedicated Host | Surcharge | Compliance, or BYOL licensing tied to physical sockets |

## Common use cases

| Need | Shape |
|---|---|
| Web application tier | ALB in public subnets, Auto Scaling group of instances in private subnets, security group that only allows the ALB's SG on 443 |
| Self-managed database | `r` or `i` family, `io2` or `gp3` EBS, multi-AZ via replication, snapshot schedule. Usually you should be using RDS instead |
| CI/CD runners | Spot instances in an Auto Scaling group, scaled to zero when idle |
| Batch / ETL | Spot fleet, driven by AWS Batch or a queue |
| Legacy lift-and-shift | Whatever matched the on-prem box, then right-sized afterwards with Compute Optimizer |
| Bastion host | Do not. Use SSM Session Manager and delete the bastion |
| GPU training / inference | `p`/`g` family, usually with a Deep Learning AMI |
| Licensed commercial software | Dedicated Host when the licence is bound to physical cores |

## When you would actually use this

EC2 is the most flexible and the most work. The honest default in 2026 is to reach for something
higher up the stack first and drop to EC2 when you hit a reason.

Pick EC2 when:

- **You need the OS.** Kernel modules, a specific kernel version, a sysctl, a custom filesystem, a
  licensed agent that has to run as root. Containers and Lambda cannot give you that.
- **The workload is long-running and steady.** A process that runs 24/7 at predictable load is
  cheaper on a Reserved or Savings Plan instance than on anything per-request.
- **Lift-and-shift.** Moving an existing VM into AWS with minimal change is exactly EC2's job, and
  re-architecting later is a legitimate second step.
- **The workload exceeds the limits of managed compute.** Lambda caps at 15 minutes and 10 GB of
  memory. A six-hour job with 400 GB of RAM is an EC2 instance.
- **You need specific hardware.** GPUs, local NVMe, bare metal, a particular network throughput.
- **Spot economics are decisive.** Interruptible batch at 10% of the price is hard to beat.

Prefer something else when:

- **It is a container.** ECS Fargate or EKS removes the instances you would otherwise patch.
- **It is event-driven or bursty.** Lambda bills per millisecond and scales to zero; an idle EC2
  instance bills all night.
- **It is a database, cache or queue.** RDS, Aurora, ElastiCache and SQS exist so you do not run
  these on instances you maintain.
- **It is a static site.** S3 plus CloudFront. A web server is not needed.
- **You would be building an autoscaling, self-healing, patched, monitored fleet from scratch.**
  That is a platform team's full-time job, and managed services already did it.

## Interview questions

1. You stop and start an EC2 instance and the application becomes unreachable, even though nothing
   in the code changed. What happened and what are three ways to prevent it?
2. What is the difference between rebooting and stopping/starting an instance, in terms of instance
   store data and the public IP?
3. Why can an EBS volume only attach to an instance in the same availability zone, and what does
   that imply for a highly available design?
4. A security group has no inbound rules and the instance is still making outbound HTTPS calls
   successfully. Explain.
5. What does it mean that a security group is *stateful*, and how does that differ from a network
   ACL?
6. You need to allow your app tier to reach your database tier. Why is referencing the app tier's
   security group better than allowing the subnet CIDR?
7. An engineer reports that a `t3.micro` was fast for an hour and then crawled. What is happening?
8. How do you give an EC2 instance access to an S3 bucket without putting any credentials on it?
9. You terminate 50 instances and the bill barely moves. Where would you look?
10. When would you choose Spot instances, and what has to be true about the workload?
11. Why is hardcoding an AMI id in Terraform a problem, and what do you do instead?
12. You have lost the private key for a running production instance that you need shell access to.
    What are your options?
