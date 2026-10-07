# 04 - VPC (Virtual Private Cloud)

## This ran against LocalStack, not real AWS

Every command below was executed against **LocalStack 3.8.1 (community edition)** on
`http://localhost:4566`. There are no real AWS credentials on this machine. `vpc-dbc380d2` and
everything inside it existed only in that container and was deleted at the end.

LocalStack models the VPC **control plane** - the objects, their relationships and their attributes
are real and the outputs below are the real shape of the real API. It does not implement the
**data plane**: no packet is ever forwarded, so routes, security groups and network ACLs are stored
but never evaluated. You can prove your topology is *described* correctly; you cannot prove traffic
flows. The NAT gateway here is an object with an Elastic IP of `127.141.93.225` - a loopback
address, which is the clearest possible signal that no real network exists.

Specific gaps noted inline: a custom network ACL on real AWS is created with implicit `deny all`
rules at number 32767 in both directions, and LocalStack omits them.

## What is a VPC

A VPC is a logically isolated virtual network inside an AWS region, with an IP address range you
choose. Everything with a network interface - EC2 instances, RDS databases, Lambda functions with
VPC access, load balancers, EKS nodes - lives in one.

The pieces and how they fit:

```text
Region  us-east-1
+-------------------------------------------------------------------+
|  VPC  10.42.0.0/16                                                 |
|                                                                    |
|   AZ us-east-1a                                                    |
|   +-------------------------------+   +------------------------+   |
|   | PUBLIC subnet 10.42.1.0/24    |   | PRIVATE subnet         |   |
|   |                               |   | 10.42.11.0/24          |   |
|   |  [ NAT gateway ] <------------|---|--- 0.0.0.0/0 route     |   |
|   |         |                     |   |                        |   |
|   |  route table: hw18-public-rt  |   | route table:           |   |
|   |    10.42.0.0/16 -> local      |   |  hw18-private-rt       |   |
|   |    0.0.0.0/0    -> igw        |   |   10.42.0.0/16 -> local|   |
|   +---------|---------------------+   |   0.0.0.0/0 -> nat     |   |
|             |                         +------------------------+   |
|      [ Internet Gateway ]                                          |
+-------------|------------------------------------------------------+
              |
          Internet
```

A VPC spans every availability zone in its region. A **subnet** does not - a subnet belongs to
exactly one AZ, and that is the fact that forces every highly available design to use at least two
subnets.

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-vpc --cidr-block 10.42.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=hw18-vpc}]' \
  --query 'Vpc.{Id:VpcId,Cidr:CidrBlock,State:State,Tenancy:InstanceTenancy,Default:IsDefault}'
```

```text
{
    "Id": "vpc-dbc380d2",
    "Cidr": "10.42.0.0/16",
    "State": "pending",
    "Tenancy": "default",
    "Default": null
}
```

Creating a VPC also silently creates three things you did not ask for: a **main route table**, a
**default network ACL** that allows everything, and a **default security group** that allows all
traffic from itself and all egress. Both defaults are shown later.

Every account also has a **default VPC** per region - `172.31.0.0/16`, with a public subnet in every
AZ and an internet gateway already attached. It is convenient and it is why a brand new EC2 instance
is on the internet without you configuring anything. Production should never use it.

## CIDR

CIDR notation is an address plus a prefix length: `10.42.0.0/16` means the first 16 bits are the
network, leaving 16 bits of host space, which is 65,536 addresses.

| Prefix | Addresses | Usable in AWS | Typical role |
|---|---|---|---|
| `/16` | 65,536 | 65,531 | A whole VPC. The largest AWS allows |
| `/20` | 4,096 | 4,091 | A generous subnet |
| `/24` | 256 | **251** | A comfortable subnet |
| `/28` | 16 | 11 | The smallest AWS allows |

AWS reserves **five addresses in every subnet**, and you can see it directly in the real output:

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-subnet --vpc-id vpc-dbc380d2 \
  --cidr-block 10.42.1.0/24 --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=hw18-public-1a}]' \
  --query 'Subnet.{Id:SubnetId,Cidr:CidrBlock,Az:AvailabilityZone,Free:AvailableIpAddressCount,AutoPublicIp:MapPublicIpOnLaunch}'

aws --endpoint-url=http://localhost:4566 ec2 create-subnet --vpc-id vpc-dbc380d2 \
  --cidr-block 10.42.11.0/24 --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=hw18-private-1a}]' \
  --query 'Subnet.{Id:SubnetId,Cidr:CidrBlock,Az:AvailabilityZone,Free:AvailableIpAddressCount,AutoPublicIp:MapPublicIpOnLaunch}'
```

```text
{
    "Id": "subnet-0f9f6846",
    "Cidr": "10.42.1.0/24",
    "Az": "us-east-1a",
    "Free": 251,
    "AutoPublicIp": false
}
{
    "Id": "subnet-52fae761",
    "Cidr": "10.42.11.0/24",
    "Az": "us-east-1a",
    "Free": 251,
    "AutoPublicIp": false
}
```

**`Free: 251`, not 256.** The five taken in `10.42.1.0/24` are:

| Address | Reserved for |
|---|---|
| `10.42.1.0` | Network address |
| `10.42.1.1` | VPC router |
| `10.42.1.2` | DNS (the "VPC+2" resolver, Route 53 Resolver) |
| `10.42.1.3` | Reserved for future use |
| `10.42.1.255` | Broadcast address (AWS does not support broadcast, but reserves it anyway) |

That `.2` DNS address is worth remembering - a resolver pointed anywhere else is why DNS inside a
VPC "mysteriously" stops working.

Planning rules that save real pain later:

- **Use RFC 1918 private space**: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`.
- **Never overlap with anything you might peer with** - another VPC, another account, your office,
  your data centre. VPC peering and Transit Gateway both refuse overlapping CIDRs, and there is no
  NAT workaround at that layer. Allocate from a central plan on day one.
- **Size generously.** A `/16` for a VPC and `/24` or `/20` per subnet costs nothing. You can add
  secondary CIDR blocks later, but you can never shrink or change the primary.
- **Leave a gap between public and private ranges.** Using `10.42.1-10.x` for public and
  `10.42.11-20.x` for private, as here, keeps room to grow each tier.
- **Count your ENIs, not your instances.** Fargate tasks, Lambda ENIs, RDS instances and load
  balancer nodes all consume subnet addresses. A `/28` runs out far faster than it looks.

## Route tables

A route table is a list of destination CIDRs and the targets packets for them should go to. Every
subnet is associated with exactly one route table; the route table is what makes a subnet "public"
or "private".

The VPC came with a main route table already:

```bash
aws --endpoint-url=http://localhost:4566 ec2 describe-route-tables \
  --filters Name=vpc-id,Values=vpc-dbc380d2 \
  --query 'RouteTables[].{Id:RouteTableId,Main:Associations[0].Main,Routes:Routes}'
```

```text
[
    {
        "Id": "rtb-ce2f034e",
        "Main": true,
        "Routes": [
            {
                "DestinationCidrBlock": "10.42.0.0/16",
                "GatewayId": "local",
                "Origin": "CreateRouteTable",
                "State": "active"
            }
        ]
    }
]
```

The `local` route is created automatically, cannot be deleted, and cannot be overridden. **Every
subnet in a VPC can reach every other subnet in that VPC, always.** There is no way to use routing
to isolate one subnet from another inside the same VPC - that is what security groups and NACLs are
for. People reach for a second VPC when they want hard network isolation.

Any subnet with only the `local` route is private. It can talk within the VPC and nowhere else.

## Internet gateway

An internet gateway is a horizontally scaled, highly available VPC component that does two things:
it provides a route target for internet-bound traffic, and it performs one-to-one NAT between an
instance's private IP and its public IP.

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=hw18-igw}]' \
  --query 'InternetGateway.{Id:InternetGatewayId,Attachments:Attachments}'
aws --endpoint-url=http://localhost:4566 ec2 attach-internet-gateway \
  --internet-gateway-id igw-a031f954 --vpc-id vpc-dbc380d2
```

```text
{
    "Id": "igw-a031f954",
    "Attachments": []
}
(no output on success)
```

`Attachments: []` on creation - an IGW exists independently and is attached to exactly one VPC. One
IGW per VPC, no more.

Attaching it is not enough. A subnet is only public once a route points at it:

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-route-table --vpc-id vpc-dbc380d2 \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=hw18-public-rt}]'
aws --endpoint-url=http://localhost:4566 ec2 create-route --route-table-id rtb-a1c4a765 \
  --destination-cidr-block 0.0.0.0/0 --gateway-id igw-a031f954
aws --endpoint-url=http://localhost:4566 ec2 associate-route-table \
  --route-table-id rtb-a1c4a765 --subnet-id subnet-0f9f6846
aws --endpoint-url=http://localhost:4566 ec2 modify-subnet-attribute \
  --subnet-id subnet-0f9f6846 --map-public-ip-on-launch

aws --endpoint-url=http://localhost:4566 ec2 describe-route-tables --route-table-ids rtb-a1c4a765 \
  --query 'RouteTables[0].{Id:RouteTableId,Routes:Routes,Assoc:Associations[].SubnetId}'
```

```text
{
    "Return": true
}
{
    "AssocId": "rtbassoc-84dbff8d",
    "State": null
}
(no output on success)
{
    "Id": "rtb-a1c4a765",
    "Routes": [
        {
            "DestinationCidrBlock": "10.42.0.0/16",
            "GatewayId": "local",
            "Origin": "CreateRouteTable",
            "State": "active"
        },
        {
            "DestinationCidrBlock": "0.0.0.0/0",
            "GatewayId": "igw-a031f954",
            "Origin": "CreateRoute",
            "State": "active"
        }
    ],
    "Assoc": [
        "subnet-0f9f6846"
    ]
}
```

Two routes now. Routing is **longest-prefix-match**: traffic to `10.42.x.x` matches the more
specific `/16` and stays local; everything else falls through to `0.0.0.0/0` and goes to the IGW.

Three conditions must all hold for an instance to reach the internet, and a missing one is the most
common "why can't my instance get out" ticket:

1. The subnet's route table has `0.0.0.0/0` to an **attached** IGW.
2. The instance has a **public IP or Elastic IP** - either from `MapPublicIpOnLaunch` (set above) or
   assigned explicitly. An instance in a public subnet with no public IP cannot reach the internet.
3. The security group allows the outbound traffic, and the NACL allows it in both directions.

## NAT gateway

Private subnets usually still need **outbound** internet: OS updates, pulling container images,
calling third-party APIs. A NAT gateway provides exactly that - outbound-initiated only, with no way
for anything on the internet to open a connection inward.

A NAT gateway needs an Elastic IP:

```bash
aws --endpoint-url=http://localhost:4566 ec2 allocate-address --domain vpc \
  --query '{Ip:PublicIp,AllocId:AllocationId,Domain:Domain}'
```

```text
{
    "Ip": "127.141.93.225",
    "AllocId": "eipalloc-95bf6c14",
    "Domain": "vpc"
}
```

`127.141.93.225` is in `127.0.0.0/8`, the loopback range. Real AWS would hand back a routable public
address. This is LocalStack's clearest tell and a reminder that nothing here is reachable.

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-nat-gateway \
  --subnet-id subnet-0f9f6846 --allocation-id eipalloc-95bf6c14 \
  --tag-specifications 'ResourceType=natgateway,Tags=[{Key=Name,Value=hw18-nat}]' \
  --query 'NatGateway.{Id:NatGatewayId,State:State,Subnet:SubnetId,Vpc:VpcId,Addr:NatGatewayAddresses}'
```

```text
{
    "Id": "nat-74596f845995c4a4d",
    "State": "available",
    "Subnet": "subnet-0f9f6846",
    "Vpc": "vpc-dbc380d2",
    "Addr": [
        {
            "AllocationId": "eipalloc-95bf6c14",
            "NetworkInterfaceId": "eni-4225645a",
            "PrivateIp": "10.183.50.78",
            "PublicIp": "127.141.93.225",
            "AssociationId": "eipassoc-7cde22b6"
        }
    ]
}
```

**The NAT gateway goes in the PUBLIC subnet.** This is the single most-made mistake in VPC design.
The NAT itself needs a route to the internet gateway to do its job; put it in the private subnet and
it has no path out, and nothing in the VPC can reach the internet. Note the subnet id in the output
is `subnet-0f9f6846` - the public one.

Then point the private subnet's route table at it:

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-route-table --vpc-id vpc-dbc380d2 \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=hw18-private-rt}]'
aws --endpoint-url=http://localhost:4566 ec2 create-route --route-table-id rtb-55bf695e \
  --destination-cidr-block 0.0.0.0/0 --nat-gateway-id nat-74596f845995c4a4d
aws --endpoint-url=http://localhost:4566 ec2 associate-route-table \
  --route-table-id rtb-55bf695e --subnet-id subnet-52fae761
```

### Public vs private subnet, side by side

```bash
aws --endpoint-url=http://localhost:4566 ec2 describe-route-tables \
  --filters Name=vpc-id,Values=vpc-dbc380d2 \
  --query 'RouteTables[].{Table:Tags[?Key==`Name`]|[0].Value,Id:RouteTableId,Subnets:Associations[].SubnetId,Default:Routes[?DestinationCidrBlock==`0.0.0.0/0`].[GatewayId,NatGatewayId]|[0]}'
```

```text
[
    {
        "Table": null,
        "Id": "rtb-ce2f034e",
        "Subnets": [],
        "Default": null
    },
    {
        "Table": "hw18-public-rt",
        "Id": "rtb-a1c4a765",
        "Subnets": [
            "subnet-0f9f6846"
        ],
        "Default": [
            "igw-a031f954",
            null
        ]
    },
    {
        "Table": "hw18-private-rt",
        "Id": "rtb-55bf695e",
        "Subnets": [
            "subnet-52fae761"
        ],
        "Default": [
            null,
            "nat-74596f845995c4a4d"
        ]
    }
]
```

That one query is the whole public/private distinction:

| | Public subnet | Private subnet |
|---|---|---|
| Route table | `hw18-public-rt` | `hw18-private-rt` |
| `0.0.0.0/0` target | `igw-a031f954` (internet gateway) | `nat-74596f845995c4a4d` (NAT gateway) |
| Inbound from internet | Possible, if an instance has a public IP and the SG allows it | **Impossible.** No path exists |
| Outbound to internet | Direct, via the IGW | Via the NAT gateway, source-NATted to the NAT's Elastic IP |
| What belongs here | Load balancers, NAT gateways, bastions (if any) | Application servers, databases, caches, worker nodes - almost everything |

The first row, `rtb-ce2f034e` with no name and no subnets, is the **main route table** created with
the VPC. Any subnet you create and forget to associate inherits it. Leaving the main route table
with only the `local` route is a good safety default: a forgotten subnet is private, not
accidentally public.

### NAT gateway cost and alternatives

NAT gateways are among the easiest ways to generate a surprising bill: roughly $0.045 per hour plus
$0.045 per GB processed, per gateway. Highly available means one per AZ, so a three-AZ VPC runs
three. A workload pulling container images or writing to S3 through NAT can process terabytes.

The fixes, in order of impact:

- **VPC endpoints.** A **gateway endpoint** for S3 and DynamoDB is free and adds a route so that
  traffic never touches the NAT. An **interface endpoint** (PrivateLink) costs per hour per AZ but
  is still usually cheaper than NAT for high-volume services like ECR, Secrets Manager and SSM, and
  it keeps the traffic off the public internet entirely.
- **One NAT gateway instead of three**, accepting that an AZ failure takes out egress for the
  others. A reasonable trade in non-production.
- **Check whether you need egress at all.** Many workloads only need S3 and ECR, both of which have
  endpoints.

## Security groups

Covered in depth in `../02-ec2/README.md`. In the VPC context, what matters is where they sit:

- A security group attaches to an **elastic network interface**, not to a subnet.
- It is **stateful**: return traffic for an allowed connection is permitted automatically.
- It is **allow-only**. There are no deny rules.
- It can reference **another security group** as the source, which is how you express "the database
  accepts connections from the app tier" without caring about IP addresses.
- The default security group in a new VPC allows all traffic from itself and all egress. Leaving
  resources in it is a common mistake; create purpose-built groups instead.

## Network ACLs

A network ACL is a **stateless** packet filter at the **subnet** boundary. It is the second layer,
and the one people forget exists until something breaks.

The default NACL created with the VPC:

```bash
aws --endpoint-url=http://localhost:4566 ec2 describe-network-acls \
  --filters Name=vpc-id,Values=vpc-dbc380d2 \
  --query 'NetworkAcls[].{Id:NetworkAclId,Default:IsDefault,Entries:Entries}'
```

```text
[
    {
        "Id": "acl-1cc14cf9",
        "Default": true,
        "Entries": [
            {
                "CidrBlock": "0.0.0.0/0",
                "Egress": true,
                "Protocol": "-1",
                "RuleAction": "allow",
                "RuleNumber": 100
            },
            {
                "CidrBlock": "0.0.0.0/0",
                "Egress": true,
                "Protocol": "-1",
                "RuleAction": "deny",
                "RuleNumber": 32767
            },
            {
                "CidrBlock": "0.0.0.0/0",
                "Egress": false,
                "Protocol": "-1",
                "RuleAction": "allow",
                "RuleNumber": 100
            },
            {
                "CidrBlock": "0.0.0.0/0",
                "Egress": false,
                "Protocol": "-1",
                "RuleAction": "deny",
                "RuleNumber": 32767
            }
        ]
    }
]
```

Rule 100 allows everything in both directions; rule **32767** is the implicit catch-all deny that
exists in every NACL and cannot be removed. Because 100 is evaluated first and matches everything,
the default NACL is effectively wide open - which is correct, because the security group is the
layer meant to do the filtering.

A custom NACL:

```bash
aws --endpoint-url=http://localhost:4566 ec2 create-network-acl --vpc-id vpc-dbc380d2 \
  --tag-specifications 'ResourceType=network-acl,Tags=[{Key=Name,Value=hw18-private-nacl}]'
aws --endpoint-url=http://localhost:4566 ec2 create-network-acl-entry --network-acl-id acl-84a711c5 \
  --rule-number 100 --protocol tcp --port-range From=443,To=443 \
  --cidr-block 0.0.0.0/0 --rule-action allow --ingress
aws --endpoint-url=http://localhost:4566 ec2 create-network-acl-entry --network-acl-id acl-84a711c5 \
  --rule-number 110 --protocol tcp --port-range From=1024,To=65535 \
  --cidr-block 0.0.0.0/0 --rule-action allow --egress
aws --endpoint-url=http://localhost:4566 ec2 describe-network-acls \
  --network-acl-ids acl-84a711c5 --query 'NetworkAcls[0].Entries'
```

```text
[
    {
        "CidrBlock": "0.0.0.0/0",
        "Egress": false,
        "PortRange": {
            "From": 443,
            "To": 443
        },
        "Protocol": "6",
        "RuleAction": "allow",
        "RuleNumber": 100
    },
    {
        "CidrBlock": "0.0.0.0/0",
        "Egress": true,
        "PortRange": {
            "From": 1024,
            "To": 65535
        },
        "Protocol": "6",
        "RuleAction": "allow",
        "RuleNumber": 110
    }
]
```

Two things to take from this.

First, the **honest discrepancy**: on real AWS a newly created custom NACL starts with the implicit
`* deny` entries at rule 32767 for both directions, and `describe` shows them. LocalStack did not
add them here. The real behaviour is that a custom NACL denies everything until you add rules - the
opposite of the default NACL.

Second, and this is the thing that actually bites in production: rule 110 allows **outbound ports
1024-65535**, which has nothing to do with the service on 443. Because a NACL is stateless, the
return packets of an inbound HTTPS connection are an outbound flow from a random high-numbered
**ephemeral port**. With only "allow 443 inbound", the request arrives and the response is silently
dropped. Every stateless NACL needs a matching ephemeral port rule in the opposite direction.

### Security group vs network ACL

| | Security group | Network ACL |
|---|---|---|
| Attached to | ENI (instance, RDS, load balancer) | Subnet |
| State | **Stateful** - return traffic automatic | **Stateless** - both directions needed |
| Rules | Allow only | Allow **and** Deny |
| Evaluation | All rules, union | In rule-number order, first match wins |
| Default (new, custom) | Deny all inbound, allow all outbound | Deny all both directions |
| Default (created with VPC) | Allow from self, allow all outbound | Allow all both directions |
| Typical use | Your primary access control | Coarse subnet guardrails, blocking specific IPs |

The practical guidance: **do your real filtering with security groups.** Use NACLs for a small
number of coarse rules - blocking a known-bad CIDR, or a belt-and-braces "this subnet never talks to
the internet". Complex NACLs are hard to reason about precisely because they are stateless and
order-dependent.

## Common use cases

| Need | Shape |
|---|---|
| Standard three-tier web app | Public subnets (2+ AZs) for the ALB; private subnets for app servers; isolated private subnets with no NAT route for RDS |
| Database that must never reach the internet | Private subnet whose route table has only the `local` route, plus a security group accepting only the app tier's SG |
| Admin access without a bastion | SSM Session Manager over interface endpoints - no IGW, no NAT, no port 22 |
| Connect to on-premises | Site-to-Site VPN for a quick start, Direct Connect for bandwidth and stable latency |
| Connect many VPCs and accounts | Transit Gateway. VPC peering does not transit, so a full mesh of N VPCs needs N(N-1)/2 connections |
| Reach S3 without NAT charges | Gateway VPC endpoint - free, and it adds a prefix-list route |
| Reach ECR, Secrets Manager, SSM privately | Interface endpoints (PrivateLink) |
| Expose a service to another account privately | PrivateLink endpoint service in front of an NLB |
| Debug "the connection times out" | VPC Flow Logs to CloudWatch or S3, plus Reachability Analyzer |

## When you would actually use this

You do not choose to use a VPC - every account has one and almost every resource lands in one.
The choice is whether you design it or inherit the default.

Design one deliberately when:

- **You are putting anything into production.** The default VPC has every subnet public. A database
  there is one security group mistake away from the internet.
- **You have data that must not be internet-reachable.** Private subnets plus VPC endpoints give you
  a genuinely unroutable blast radius, not just a firewall rule.
- **You need to connect to on-premises or another account.** The CIDR plan has to exist *before*
  the first VPC is created, because overlapping ranges cannot be peered and cannot be renumbered
  without a migration.
- **Compliance demands network isolation or auditable flows.** Flow Logs, NACLs and separate VPCs
  per environment are the standard evidence.
- **Your NAT gateway bill shows up on the monthly review.** That is a VPC design problem with a VPC
  design fix: endpoints.
- **You are running EKS.** Pod density, ENI limits and subnet sizing are all VPC decisions that are
  painful to change once the cluster exists.

You can reasonably stay in the default VPC for a throwaway experiment or a personal sandbox. Beyond
that, the time to design the network is before anything is in it.

## Interview questions

1. A `/24` subnet has 256 addresses but AWS reports 251 available. Where did the other five go?
2. What exactly makes a subnet "public"? Name every condition for an instance in it to reach the
   internet.
3. Why must a NAT gateway live in a public subnet?
4. Security groups are stateful and NACLs are stateless. Describe a concrete failure caused by not
   understanding that.
5. You can reach the instance on 443 but the response never arrives, and the security group looks
   right. Where do you look next?
6. Why can you not remove or override the `local` route, and how do you isolate workloads given
   that?
7. Two teams both used `10.0.0.0/16`. They now need to peer. What are the options?
8. Your NAT gateway costs more than your EC2 fleet. What do you investigate and what do you change?
9. What is the difference between a gateway VPC endpoint and an interface VPC endpoint?
10. How do you give an engineer shell access to an instance in a private subnet with no bastion and
    no inbound rules at all?
11. VPC peering versus Transit Gateway - when does the choice flip?
12. You need a highly available application across AZs. How does that constrain your subnet layout,
    and why?
