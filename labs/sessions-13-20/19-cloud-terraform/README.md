# Session 19 - Cloud & Terraform in Action

One Terraform project that builds a small but realistic AWS network plus the compute and storage
that use it, then proves every Terraform idea the session covers against the running result:
providers, variables, resources, outputs, dependencies, state, plan, apply and destroy.

```text
Terraform  ->  VPC  ->  Subnets  ->  Security Groups  ->  EC2  ->  S3
```

---

## Read this first: where this actually ran

**Every command and every block of output in this README was run against
[LocalStack](https://localstack.cloud) 3.8 community edition, not against real AWS.** There are no
AWS credentials on this machine and none were created. LocalStack is a container that speaks the AWS
APIs on `http://localhost:4566`, so Terraform, the AWS provider and the `aws` CLI all behave exactly
as they would against the real thing - but nothing is actually provisioned in a data centre.

The most important consequence, stated plainly:

> LocalStack community **emulates the EC2 API. It does not boot a virtual machine.** When you see
> `instance_state = "running"` further down, there is no operating system, no kernel, no sshd and no
> web server behind it. It is a record in the emulator's database. The `user_data` script in
> `main.tf` was accepted and stored; it never executed.

Section [What LocalStack could not do](#what-localstack-could-not-do) lists every other place the
emulator diverges from AWS, with the evidence. Nothing in this README is invented - where something
did not work, the real failure is shown instead of a plausible success.

Everything created here is named with the prefix `hw19-` so it is trivial to find and to delete.

The assignment asks for screenshots. There is no AWS console to screenshot - LocalStack community
ships no web UI - so the evidence in this README is terminal transcripts instead: the real command
and the real bytes it printed, in every case.

### Pointing the same code at real AWS

Only the provider changes. Delete the `endpoints` block, the three `skip_*` arguments and
`s3_use_path_style` from `versions.tf`, drop `access_key` / `secret_key`, and authenticate the
normal way (`aws configure`, SSO, or an instance role). The resources, variables and outputs are
unchanged.

---

## Layout

```text
19-cloud-terraform/
|
|-- README.md
|-- .gitignore
`-- terraform/
    |-- versions.tf                 provider and required_providers
    |-- variables.tf                18 input variables, typed and validated
    |-- main.tf                     2 data sources + 17 resource blocks
    |-- outputs.tf                  19 outputs, one of them sensitive
    |-- terraform.tfvars.example    copy to terraform.tfvars and edit
    `-- .terraform.lock.hcl         pinned provider hashes, committed on purpose
```

`terraform.tfvars` itself is **not** committed - `.gitignore` excludes `*.tfvars` and re-admits only
`terraform.tfvars.example`. The assignment does not name a tfvars file as a deliverable, so the
example is the only one shipped. The same `.gitignore` excludes `.terraform/`, `*.tfstate*` and
`*.tfplan`, because the state file holds every value Terraform knows, including the secrets - proved
in [State](#state-the-source-of-truth).

---

## Architecture

```text
                                   INTERNET
                                       |
                                       v
                           +-----------------------+
                           |       hw19-igw        |
                           |   internet gateway    |
                           +-----------+-----------+
                                       |
 Region us-east-1                      |
+--------------------------------------|-------------------------------------+
| VPC hw19-vpc   10.19.0.0/16          |                                     |
|                                      v                                     |
|                     +--------------------------------+                     |
|                     | hw19-public-rt                 |                     |
|                     |   10.19.0.0/16 -> local        |                     |
|                     |   0.0.0.0/0    -> hw19-igw     |                     |
|                     +---------------+----------------+                     |
|                                     | association                          |
|  AZ us-east-1a                      v                                      |
| +------------------------------------------------------+                   |
| | subnet hw19-public-subnet   10.19.1.0/24             |                   |
| | map_public_ip_on_launch = true                       |                   |
| | network acl: hw19-public-nacl                        |                   |
| |                                                      |                   |
| |  +------------------------------------------------+  |                   |
| |  | sg hw19-web-sg                                 |  |                   |
| |  |   in  tcp/80   from 0.0.0.0/0                  |  |                   |
| |  |   in  tcp/443  from 0.0.0.0/0                  |  |                   |
| |  |   in  tcp/22   from 10.19.1.0/24               |  |                   |
| |  |   out all      to   0.0.0.0/0                  |  |                   |
| |  |                                                |  |                   |
| |  |  +------------------------------------------+  |  |                   |
| |  |  | EC2 hw19-web   t3.micro   10.19.1.4      |  |  |                   |
| |  |  +------------------------------------------+  |  |                   |
| |  +-----------------------+------------------------+  |                   |
| +--------------------------|---------------------------+                   |
|                            | tcp/8080, allowed by SOURCE SG                |
|                            v                                               |
| +------------------------------------------------------+                   |
| | sg hw19-app-sg    in tcp/8080 from hw19-web-sg       |                   |
| +------------------------------------------------------+                   |
|                                                                            |
|  AZ us-east-1b                          AZ us-east-1c                      |
| +---------------------------------+   +---------------------------------+  |
| | subnet hw19-private-app-subnet  |   | subnet hw19-private-data-subnet |  |
| | 10.19.11.0/24                   |   | 10.19.12.0/24                   |  |
| | network acl: VPC default        |   | network acl: VPC default        |  |
| +----------------+----------------+   +----------------+----------------+  |
|                  |                                      |                  |
|                  +------------------+-------------------+                  |
|                                     v                                      |
|                     +--------------------------------+                     |
|                     | hw19-private-rt                |                     |
|                     |   10.19.0.0/16 -> local        |                     |
|                     |   no 0.0.0.0/0 route           |                     |
|                     +--------------------------------+                     |
+----------------------------------------------------------------------------+
```

```text
  Regional, outside the VPC:

  +------------------------------------------------------+
  | S3 bucket  hw19-artifacts-000000000000               |
  |   versioning      Enabled                            |
  |   public access   all four blocks on                 |
  |   bucket policy   deny s3:* when not TLS             |
  |   object          config/app.json                    |
  +------------------------------------------------------+
```

The EC2 instance is drawn inside `hw19-web-sg` because a security group is attached to the
instance's network interface, not to the subnet. The network ACL is drawn around the subnet because
that is where it attaches. That difference is the whole of
[security groups vs network ACLs](#security-groups-vs-network-acls).

---
---

## Concepts, grounded in what was built

### Cloud service models

The three models differ in one thing only: **where the line is drawn between what you operate and
what the provider operates.**

| Model | Provider operates | You operate | In this project |
|---|---|---|---|
| IaaS - Infrastructure as a Service | data centre, hypervisor, physical network | OS, patching, runtime, app, and the virtual network layout | everything here: `aws_vpc`, `aws_subnet`, `aws_instance` |
| PaaS - Platform as a Service | all of the above plus OS and runtime | your application code and its config | not used here; the equivalent would be Elastic Beanstalk or App Runner |
| SaaS - Software as a Service | all of it | your data and your users | not used here; Gmail, Slack, Microsoft 365 |

S3 is worth calling out because it does not fit the simple ladder. `aws_s3_bucket` is a **managed
service**: you never see a disk, a filesystem or a replica count, and you never patch anything. It
is closer to PaaS than to IaaS even though it is sold alongside EC2. Compare the two resources in
`main.tf` and the difference is obvious - the EC2 block has to specify an AMI, an instance type, a
subnet, an IP behaviour and a boot script; the S3 block specifies a name.

The practical rule: **the lower you go, the more knobs you get and the more you are on the hook
for.** This project chose IaaS for the network and compute because the session is about
understanding the network, and PaaS hides exactly the thing being taught.

### Regions and Availability Zones

A **region** is a separately operated geographic cluster of data centres - `us-east-1` is Northern
Virginia, `ap-south-1` is Mumbai. An **Availability Zone** is one or more physically separate data
centres inside a region, with independent power, cooling and networking.

The relationship matters because AWS resources are scoped to one or the other:

```bash
terraform output public_subnet_az
terraform output private_subnet_azs
terraform output vpc_cidr
```

```text
"us-east-1a"
{
  "app" = "us-east-1b"
  "data" = "us-east-1c"
}
"10.19.0.0/16"
```

The VPC has no AZ at all - it is **regional**, and its `10.19.0.0/16` range stretches across every
zone. Each subnet has exactly one AZ and cannot be moved. That is why three subnets were created
rather than one: a subnet is the unit that fails with its zone, so a workload that must survive the
loss of a zone needs at least two subnets in different zones.

LocalStack reports six zones for `us-east-1`:

```bash
aws ec2 describe-availability-zones --query 'AvailabilityZones[].ZoneName' --output text
```

```text
us-east-1a	us-east-1b	us-east-1c	us-east-1d	us-east-1e	us-east-1f
```

Terraform never hard-codes a zone name in this project. `variables.tf` takes an AZ *suffix*
(`"a"`, `"b"`, `"c"`) and `main.tf` glues it onto `var.aws_region`, so switching the whole project to
Mumbai is a one-line change to `aws_region`.

### VPC and subnets

A **VPC** is a private, isolated IPv4/IPv6 network you own inside a region. Nothing from outside can
reach into it unless you build a door. A **subnet** is a slice of the VPC's address range, pinned to
one AZ, that resources actually attach to.

```bash
aws ec2 describe-subnets --filters "Name=tag:Project,Values=hw19" \
  --query 'sort_by(Subnets,&CidrBlock)[].{Name:Tags[?Key==`Name`]|[0].Value,SubnetId:SubnetId,Cidr:CidrBlock,AZ:AvailabilityZone,PublicIp:MapPublicIpOnLaunch}' \
  --output table
```

```text
--------------------------------------------------------------------------------------------
|                                      DescribeSubnets                                     |
+------------+----------------+----------------------------+-----------+-------------------+
|     AZ     |     Cidr       |           Name             | PublicIp  |     SubnetId      |
+------------+----------------+----------------------------+-----------+-------------------+
|  us-east-1a|  10.19.1.0/24  |  hw19-public-subnet        |  True     |  subnet-06e8f5e4  |
|  us-east-1b|  10.19.11.0/24 |  hw19-private-app-subnet   |  False    |  subnet-55e1f360  |
|  us-east-1c|  10.19.12.0/24 |  hw19-private-data-subnet  |  False    |  subnet-a66e233f  |
+------------+----------------+----------------------------+-----------+-------------------+
```

Three subnets, three zones, three non-overlapping `/24` slices of the VPC's `/16`. `/16` gives
65,536 addresses; each `/24` takes 256 of them, of which AWS reserves five (network address, VPC
router, DNS, future use, broadcast), leaving 251 usable.

**"Public" is not a property of a subnet.** There is no `public = true` field. The only thing that
makes `hw19-public-subnet` public is that the route table attached to it has a route to an internet
gateway - which is the next section. `map_public_ip_on_launch = true` is a separate, additional
choice: it means instances launched here get a public address automatically, which is useless
without the route.

### Route tables and the internet gateway

An **internet gateway** is a horizontally scaled, managed component attached to the VPC that
performs NAT between private VPC addresses and public internet addresses. A **route table** is a
list of destination-CIDR-to-target rules that decides where a packet leaving a subnet goes.

Both route tables, as the API reports them:

```bash
aws ec2 describe-route-tables --filters "Name=tag:Project,Values=hw19" \
  --query 'RouteTables[].{Name:Tags[?Key==`Name`]|[0].Value,RtbId:RouteTableId,Routes:Routes[].join(` -> `,[DestinationCidrBlock,not_null(GatewayId,`local`)]),Assoc:Associations[].SubnetId}' \
  --output json
```

```text
[
    {
        "Name": "hw19-private-rt",
        "RtbId": "rtb-7dc464e2",
        "Routes": [
            "10.19.0.0/16-> local"
        ],
        "Assoc": [
            "subnet-a66e233f",
            "subnet-55e1f360"
        ]
    },
    {
        "Name": "hw19-public-rt",
        "RtbId": "rtb-7b1df825",
        "Routes": [
            "10.19.0.0/16-> local",
            "0.0.0.0/0-> igw-d59b4ba3"
        ],
        "Assoc": [
            "subnet-06e8f5e4"
        ]
    }
]
```

That single extra line - `0.0.0.0/0 -> igw-d59b4ba3` - is the entire difference between the public
subnet and the private ones. Three things to take from the output:

1. **The `local` route is free and implicit.** AWS adds `10.19.0.0/16 -> local` to every route
   table. It is why every subnet in the VPC can talk to every other subnet with no configuration at
   all, and it is why `hw19-app-sg` can be reached from the public subnet in the first place. It is
   not in `main.tf`; AWS put it there.
2. **The gateway alone changes nothing.** `hw19-igw` is attached to the VPC and therefore available
   to all three subnets, but the private route table does not point at it, so the private subnets
   have no path out. Creating a gateway does not make anything public.
3. **Association is the act that applies the table.** `aws_route_table_association.public` is what
   binds `hw19-public-rt` to `hw19-public-subnet`. Without it the subnet would silently fall back
   to the VPC's main route table.

A route table answers *where does this packet go*. It does not answer *is this packet allowed* -
that is the next section, and the two are routinely confused.

### Security groups vs network ACLs

Both filter traffic. They sit in different places and behave differently.

| | Security group | Network ACL |
|---|---|---|
| Attaches to | an instance's network interface | a subnet |
| In this project | `hw19-web-sg`, `hw19-app-sg` | `hw19-public-nacl` |
| Rule types | allow only | allow and deny |
| Evaluation | all rules together; if any allows, traffic passes | numbered rules in order; first match wins |
| State | stateful - a reply to an allowed request is always allowed back | stateless - the return packet is evaluated by the rules again |
| Default when created | deny all inbound, allow all outbound | the Terraform-managed one here allows what is listed |

The stateless/stateful difference is the one that bites people, and `hw19-public-nacl` shows it. The
ACL has an inbound rule for ports 1024-65535 that looks unnecessary:

```hcl
ingress {
  rule_no    = 120
  action     = "allow"
  protocol   = "tcp"
  from_port  = 1024
  to_port    = 65535
  cidr_block = "0.0.0.0/0"
}
```

That rule exists because the ACL is stateless. When the instance makes an outbound request, the
reply comes back to a high-numbered **ephemeral port**, and the ACL evaluates that inbound reply
from scratch with no memory of the outbound request. Without rule 120, every reply to an outbound
connection would be dropped. `hw19-web-sg` needs no such rule: it is stateful, so a reply to a
connection it allowed is allowed automatically.

Now the source of the rules, straight from the API:

```bash
aws ec2 describe-security-groups --group-ids sg-e37b39dc9ea8ce00e \
  --query 'SecurityGroups[0].{Ingress:IpPermissions[].{Proto:IpProtocol,From:FromPort,To:ToPort,Cidrs:IpRanges[].CidrIp},Egress:IpPermissionsEgress[].{Proto:IpProtocol,Cidrs:IpRanges[].CidrIp}}' \
  --output json
```

```text
{
    "Ingress": [
        {
            "Proto": "tcp",
            "From": 80,
            "To": 80,
            "Cidrs": [
                "0.0.0.0/0"
            ]
        },
        {
            "Proto": "tcp",
            "From": 22,
            "To": 22,
            "Cidrs": [
                "10.19.0.0/16"
            ]
        },
        {
            "Proto": "tcp",
            "From": 443,
            "To": 443,
            "Cidrs": [
                "0.0.0.0/0"
            ]
        }
    ],
    "Egress": [
        {
            "Proto": "-1",
            "Cidrs": [
                "0.0.0.0/0"
            ]
        }
    ]
}
```

HTTP and HTTPS are open to the world because a public web server has to be. SSH is **not**: it is
restricted to `10.19.0.0/16`, which is the VPC itself. Opening port 22 to `0.0.0.0/0` means every
scanner on the internet gets to try passwords against you, continuously.

The second security group shows the feature that has no equivalent in a network ACL:

```bash
aws ec2 describe-security-groups --group-ids sg-bf6b1ac74974fe6b5 \
  --query 'SecurityGroups[0].IpPermissions[].{Proto:IpProtocol,From:FromPort,To:ToPort,SourceSg:UserIdGroupPairs[].GroupId,Cidrs:IpRanges[].CidrIp}' \
  --output json
```

```text
[
    {
        "Proto": "tcp",
        "From": 8080,
        "To": 8080,
        "SourceSg": [
            "sg-e37b39dc9ea8ce00e"
        ],
        "Cidrs": []
    }
]
```

`Cidrs` is empty and `SourceSg` points at `hw19-web-sg`. The rule says *"accept port 8080 from
anything wearing the web security group"* - not from an address range. Add ten more web servers
tomorrow, in any subnet, with any IP, and they are allowed the moment they get that group. A network
ACL cannot express this at all; it only understands CIDRs. In `main.tf` it is one argument:

```hcl
ingress {
  from_port       = var.app_port
  to_port         = var.app_port
  protocol        = "tcp"
  security_groups = [aws_security_group.web.id]
}
```

And the two network ACLs that exist in the VPC:

```bash
aws ec2 describe-network-acls --filters "Name=vpc-id,Values=vpc-d6bd2fb9" \
  --query 'NetworkAcls[].{AclId:NetworkAclId,Default:IsDefault,Name:Tags[?Key==`Name`]|[0].Value,Entries:Entries[].{Rule:RuleNumber,Egress:Egress,Proto:Protocol,Action:RuleAction,Cidr:CidrBlock,Ports:PortRange},Assoc:Associations[].SubnetId}' \
  --output json
```

```text
[
    {
        "AclId": "acl-c1cfd814",
        "Default": true,
        "Name": null,
        "Entries": [
            {
                "Rule": 100,
                "Egress": true,
                "Proto": "-1",
                "Action": "allow",
                "Cidr": "0.0.0.0/0",
                "Ports": null
            },
            {
                "Rule": 32767,
                "Egress": true,
                "Proto": "-1",
                "Action": "deny",
                "Cidr": "0.0.0.0/0",
                "Ports": null
            },
            {
                "Rule": 100,
                "Egress": false,
                "Proto": "-1",
                "Action": "allow",
                "Cidr": "0.0.0.0/0",
                "Ports": null
            },
            {
                "Rule": 32767,
                "Egress": false,
                "Proto": "-1",
                "Action": "deny",
                "Cidr": "0.0.0.0/0",
                "Ports": null
            }
        ],
        "Assoc": [
            "subnet-55e1f360",
            "subnet-a66e233f"
        ]
    },
    {
        "AclId": "acl-74d05f5b",
        "Default": false,
        "Name": "hw19-public-nacl",
        "Entries": [
            {
                "Rule": 100,
                "Egress": true,
                "Proto": "-1",
                "Action": "allow",
                "Cidr": "0.0.0.0/0",
                "Ports": {
                    "From": 0,
                    "To": 0
                }
            },
            {
                "Rule": 100,
                "Egress": false,
                "Proto": "6",
                "Action": "allow",
                "Cidr": "0.0.0.0/0",
                "Ports": {
                    "From": 80,
                    "To": 80
                }
            },
            {
                "Rule": 120,
                "Egress": false,
                "Proto": "6",
                "Action": "allow",
                "Cidr": "0.0.0.0/0",
                "Ports": {
                    "From": 1024,
                    "To": 65535
                }
            },
            {
                "Rule": 110,
                "Egress": false,
                "Proto": "6",
                "Action": "allow",
                "Cidr": "0.0.0.0/0",
                "Ports": {
                    "From": 443,
                    "To": 443
                }
            }
        ],
        "Assoc": [
            "subnet-06e8f5e4"
        ]
    }
]
```

Two things here. First, the **default ACL** was created by AWS along with the VPC - Terraform does
not manage it - and the two private subnets fell back to it. Any subnet with no explicit ACL
association gets the VPC default, which allows everything in both directions.

Second, and this is a **LocalStack divergence, not how AWS behaves**: the custom ACL shows only the
four rules written in `main.tf`. Real AWS always appends an un-removable final rule `* deny
0.0.0.0/0` at number 32767 to every network ACL, which is exactly why rule 120 above is needed. The
default ACL in this very output *does* carry its 32767 deny rules; the custom one does not, because
LocalStack's implementation skips it. Reasoning about this ACL as if it were enforced the way AWS
would enforce it is therefore the correct exercise, but the emulator is not actually enforcing it.

---

## The Terraform project

### Providers

`versions.tf` does two separate jobs that beginners often merge.

The `terraform` block pins **what Terraform needs**: a minimum Terraform version and which providers
to download, with a version constraint. `~> 6.0` means "any 6.x, but not 7.0" - major versions of
the AWS provider carry breaking changes.

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
```

The `provider` block configures **how that provider talks to the API**. Everything below `region`
exists only because the target is LocalStack:

```hcl
provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key

  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  default_tags {
    tags = {
      Project     = var.project_prefix
      Session     = "19"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }

  endpoints {
    ec2 = var.aws_endpoint_url
    s3  = var.aws_endpoint_url
    sts = var.aws_endpoint_url
    iam = var.aws_endpoint_url
  }
}
```

| Argument | Why |
|---|---|
| `skip_credentials_validation` | the fake `test` / `test` keys would fail a real STS check |
| `skip_metadata_api_check` | stops the provider waiting on `169.254.169.254`, which is not there |
| `skip_requesting_account_id` | the provider would otherwise resolve the account id through IAM/STS at startup |
| `s3_use_path_style` | LocalStack serves `localhost:4566/bucket`, not `bucket.localhost:4566` |
| `endpoints` | redirects each service's API calls to the container |

`default_tags` is not LocalStack-specific and is worth keeping on real AWS: every resource the
provider creates gets these four tags merged into its own, so `Project = hw19` is guaranteed to be
present everywhere without repeating it twenty times. Every `aws ec2 describe-*` filter in this
README uses `Name=tag:Project,Values=hw19` and works because of it.

### Variables

Eighteen variables in `variables.tf`, each with a `description`, an explicit `type`, and a `default`
so the project runs with no `.tfvars` at all. Nine carry `validation` blocks, ten rules in total.

A simple one:

```hcl
variable "environment" {
  description = "Environment name. Applied to every resource through the provider default_tags block."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of dev, staging or prod."
  }
}
```

Validation is not decorative. It fails at plan time, before anything is sent to the API:

```bash
terraform plan -var='environment=production'
```

```text
Changes to Outputs:
  + app_admin_token = (sensitive value)

You can apply this plan to save these new output values to the Terraform
state, without changing any real infrastructure.

Error: Invalid value for variable

  on variables.tf line 42:
  42: variable "environment" {
    ├────────────────
    │ var.environment is "production"

environment must be one of dev, staging or prod.

This was checked by the validation rule at variables.tf:47,3-13.
```

`production` is a reasonable-looking typo for `prod` that would otherwise have silently tagged every
resource in the account with the wrong environment. Terraform refused to continue and said which
line to look at.

A harder one, which validates structure rather than membership:

```hcl
variable "vpc_cidr" {
  description = "Address range of the whole VPC. Every subnet CIDR has to fit inside this."
  type        = string
  default     = "10.19.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0)) && tonumber(split("/", var.vpc_cidr)[1]) <= 16
    error_message = "vpc_cidr must be a valid IPv4 CIDR with a prefix length of /16 or shorter."
  }
}
```

`cidrhost()` throws on a malformed CIDR; `can()` turns that throw into `false`. The second clause
catches a range that is syntactically valid but too small to hold the three `/24` subnets:

```bash
terraform plan -var='vpc_cidr=10.19.0.0/24'
```

```text
  + ami_id               = "ami-01f446d4eeaed8a3c"
  + app_admin_token      = (sensitive value)
  + artifacts_bucket     = "hw19-artifacts-000000000000"
  + artifacts_bucket_arn = (known after apply)

Error: Invalid value for variable

  on variables.tf line 53:
  53: variable "vpc_cidr" {
    ├────────────────
    │ var.vpc_cidr is "10.19.0.0/24"

vpc_cidr must be a valid IPv4 CIDR with a prefix length of /16 or shorter.

This was checked by the validation rule at variables.tf:58,3-13.
```

A complex type with two validation blocks drives the `for_each` further down:

```hcl
variable "private_subnets" {
  description = "Private subnets to create, keyed by role. Each entry becomes one subnet in its own Availability Zone through for_each."
  type = map(object({
    cidr      = string
    az_suffix = string
  }))
  default = {
    app = {
      cidr      = "10.19.11.0/24"
      az_suffix = "b"
    }
    data = {
      cidr      = "10.19.12.0/24"
      az_suffix = "c"
    }
  }

  validation {
    condition     = length(var.private_subnets) >= 1
    error_message = "Define at least one private subnet."
  }

  validation {
    condition     = alltrue([for s in values(var.private_subnets) : can(cidrhost(s.cidr, 0))])
    error_message = "Every private subnet cidr must be a valid IPv4 CIDR."
  }
}
```

### Overriding with a tfvars file

Defaults are the fallback. `terraform.tfvars` is loaded automatically and overrides them, and
`-var` on the command line overrides that. The file shipped here is the example:

```bash
cp terraform.tfvars.example terraform.tfvars
```

```hcl
aws_region       = "us-east-1"
aws_endpoint_url = "http://localhost:4566"
aws_access_key   = "test"
aws_secret_key   = "test"

project_prefix = "hw19"
environment    = "dev"

vpc_cidr                = "10.19.0.0/16"
public_subnet_cidr      = "10.19.1.0/24"
public_subnet_az_suffix = "a"

private_subnets = {
  app = {
    cidr      = "10.19.11.0/24"
    az_suffix = "b"
  }
  data = {
    cidr      = "10.19.12.0/24"
    az_suffix = "c"
  }
}

instance_type    = "t3.micro"
allowed_ssh_cidr = "10.19.0.0/16"
app_port         = 8080

app_admin_token = "hw19-local-demo-token"
```

`app_admin_token` is the reason `*.tfvars` is in `.gitignore` while `terraform.tfvars.example` is
re-admitted with a `!` negation. The real file carries a secret; the example carries a placeholder.

### Resources, including count / for_each

Seventeen resource blocks and two data sources. Seventeen blocks become **nineteen** objects in
state, because the project is not static: `aws_subnet.private` and
`aws_route_table_association.private` are both driven by `for_each` over the `private_subnets` map
and each produce two instances. Adding a third private subnet is four lines of tfvars and no new
HCL.

```hcl
resource "aws_subnet" "private" {
  for_each = var.private_subnets

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value.cidr
  availability_zone       = "${var.aws_region}${each.value.az_suffix}"
  map_public_ip_on_launch = false

  tags = {
    Name = "${local.name}-private-${each.key}-subnet"
    Tier = "private"
    Role = each.key
  }
}
```

`for_each` was chosen over `count` deliberately. With `count`, the instances are addressed by
position - `aws_subnet.private[0]`, `[1]` - so deleting the first entry from the list renumbers the
second one and Terraform destroys and recreates a subnet that did not change. With `for_each` the
address is the map key, which is stable:

```text
aws_subnet.private["app"]
aws_subnet.private["data"]
```

Delete `app` from the map and only `app` is destroyed. `data` is untouched.

The second `for_each` chains off the first, iterating the resource rather than the variable:

```hcl
resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}
```

Two data sources read things Terraform did not create. `aws_caller_identity` supplies the account id
used to make the bucket name globally unique, and `aws_ami` resolves an image name to an id, so the
AMI is never hard-coded:

```hcl
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = [var.ami_owner]

  filter {
    name   = "name"
    values = [var.ami_name_filter]
  }
}
```

---

## The workflow, run for real

### init

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
```

```text
Initializing the backend...

Initializing provider plugins...
- Finding hashicorp/aws versions matching "~> 6.0"...
- Installing hashicorp/aws v6.67.0...
- Installed hashicorp/aws v6.67.0 (signed by HashiCorp)

Terraform has created a lock file .terraform.lock.hcl to record the provider
selections it made above. Include this file in your version control repository
so that Terraform can guarantee to make the same selections by default when
you run "terraform init" in the future.

Terraform has been successfully initialized!
```

`init` downloads the provider into `.terraform/` and writes `.terraform.lock.hcl` with the exact
version and the checksums of every platform build. The lock file is committed; `.terraform/` is not,
because it is a 600 MB binary cache that any machine can rebuild. Nothing has been contacted on
LocalStack yet - `init` talks only to the Terraform registry.

### fmt and validate

```bash
terraform fmt
terraform validate
```

```text
Success! The configuration is valid.
```

`fmt` rewrites files to canonical HCL layout and prints the names of files it changed (silence means
nothing needed changing). `validate` is a **local** check: syntax, argument names, types, and now
variable `validation` blocks. It does not call AWS, so it cannot tell you whether a CIDR overlaps or
a bucket name is taken.

### plan

```bash
terraform plan -out=tfplan
```

```text
data.aws_ami.amazon_linux: Reading...
data.aws_caller_identity.current: Reading...
data.aws_caller_identity.current: Read complete after 1s [id=000000000000]
data.aws_ami.amazon_linux: Read complete after 1s [id=ami-01f446d4eeaed8a3c]

Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:
```

The data sources run **during the plan**, not during the apply - which is why `ami_id` and
`artifacts_bucket` show real values in the plan output while everything else says
`(known after apply)`. Terraform cannot know a VPC id before the VPC exists, but it can look up an
AMI immediately.

The tail of the plan:

```text
Plan: 19 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + ami_id                = "ami-01f446d4eeaed8a3c"
  + app_admin_token       = (sensitive value)
  + app_security_group_id = (known after apply)
  + artifacts_bucket      = "hw19-artifacts-000000000000"
  + artifacts_bucket_arn  = (known after apply)
  + instance_id           = (known after apply)
  + instance_private_ip   = (known after apply)
  + instance_public_ip    = (known after apply)
  + internet_gateway_id   = (known after apply)
  + network_acl_id        = (known after apply)
  + private_subnet_azs    = {
      + app  = "us-east-1b"
      + data = "us-east-1c"
    }
  + private_subnet_ids    = {
      + app  = (known after apply)
      + data = (known after apply)
    }
  + public_route_table_id = (known after apply)
  + public_subnet_az      = "us-east-1a"
  + public_subnet_id      = (known after apply)
  + resource_summary      = {
      + environment     = "dev"
      + region          = "us-east-1"
      + security_groups = 2
      + subnets_total   = 3
    }
  + vpc_cidr              = "10.19.0.0/16"
  + vpc_id                = (known after apply)
  + web_security_group_id = (known after apply)

─────────────────────────────────────────────────────────────────────────────

Saved the plan to: tfplan

To perform exactly these actions, run the following command to apply:
    terraform apply "tfplan"
```

Nineteen resources to create and nothing destroyed. `-out=tfplan` saves the plan to a file; applying
that file guarantees Terraform does exactly what was reviewed, even if someone edits the `.tf` files
in between. Without `-out`, `apply` re-plans and the thing you approve may not be the thing you
read. Note the warning Terraform prints when you skip it: *"you didn't use the -out option, so
Terraform can't guarantee to take exactly these actions"*.

The four plan symbols:

```text
+    create
~    update in place
-    destroy
-/+  destroy and recreate (replacement)
```

### apply

```bash
terraform apply tfplan
```

```text
aws_vpc.main: Creating...
aws_s3_bucket.artifacts: Creating...
aws_vpc.main: Creation complete after 0s [id=vpc-d6bd2fb9]
aws_internet_gateway.main: Creating...
aws_route_table.private: Creating...
aws_subnet.public: Creating...
aws_subnet.private["data"]: Creating...
aws_subnet.private["app"]: Creating...
aws_security_group.web: Creating...
aws_subnet.private["app"]: Creation complete after 0s [id=subnet-55e1f360]
aws_internet_gateway.main: Creation complete after 0s [id=igw-d59b4ba3]
aws_subnet.private["data"]: Creation complete after 0s [id=subnet-a66e233f]
aws_s3_bucket.artifacts: Creation complete after 0s [id=hw19-artifacts-000000000000]
aws_s3_bucket_public_access_block.artifacts: Creating...
aws_s3_bucket_versioning.artifacts: Creating...
aws_route_table.public: Creating...
aws_s3_object.app_config: Creating...
aws_s3_bucket_public_access_block.artifacts: Creation complete after 0s [id=hw19-artifacts-000000000000]
aws_s3_object.app_config: Creation complete after 0s [id=hw19-artifacts-000000000000/config/app.json]
aws_s3_bucket_policy.artifacts: Creating...
aws_s3_bucket_policy.artifacts: Creation complete after 0s [id=hw19-artifacts-000000000000]
aws_route_table.private: Creation complete after 1s [id=rtb-7dc464e2]
aws_route_table_association.private["data"]: Creating...
aws_route_table_association.private["app"]: Creating...
aws_route_table_association.private["data"]: Creation complete after 0s [id=rtbassoc-e0e3fd2a]
aws_route_table_association.private["app"]: Creation complete after 0s [id=rtbassoc-82d4716d]
aws_security_group.web: Creation complete after 1s [id=sg-e37b39dc9ea8ce00e]
aws_route_table.public: Creation complete after 1s [id=rtb-7b1df825]
aws_security_group.app: Creating...
aws_security_group.app: Creation complete after 0s [id=sg-bf6b1ac74974fe6b5]
aws_s3_bucket_versioning.artifacts: Creation complete after 2s [id=hw19-artifacts-000000000000]
aws_subnet.public: Still creating... [00m10s elapsed]
aws_subnet.public: Creation complete after 10s [id=subnet-06e8f5e4]
aws_route_table_association.public: Creating...
aws_network_acl.public: Creating...
aws_route_table_association.public: Creation complete after 0s [id=rtbassoc-6cc83c0e]
aws_instance.web: Creating...
aws_network_acl.public: Creation complete after 0s [id=acl-74d05f5b]
aws_instance.web: Still creating... [00m10s elapsed]
aws_instance.web: Creation complete after 11s [id=i-b15f937d0ca1b5c2f]

Apply complete! Resources: 19 added, 0 changed, 0 destroyed.

Outputs:

ami_id = "ami-01f446d4eeaed8a3c"
app_admin_token = <sensitive>
app_security_group_id = "sg-bf6b1ac74974fe6b5"
artifacts_bucket = "hw19-artifacts-000000000000"
artifacts_bucket_arn = "arn:aws:s3:::hw19-artifacts-000000000000"
instance_id = "i-b15f937d0ca1b5c2f"
instance_private_ip = "10.19.1.4"
instance_public_ip = "54.214.145.148"
internet_gateway_id = "igw-d59b4ba3"
network_acl_id = "acl-74d05f5b"
private_subnet_azs = {
  "app" = "us-east-1b"
  "data" = "us-east-1c"
}
private_subnet_ids = {
  "app" = "subnet-55e1f360"
  "data" = "subnet-a66e233f"
}
public_route_table_id = "rtb-7b1df825"
public_subnet_az = "us-east-1a"
public_subnet_id = "subnet-06e8f5e4"
resource_summary = {
  "environment" = "dev"
  "region" = "us-east-1"
  "security_groups" = 2
  "subnets_total" = 3
}
vpc_cidr = "10.19.0.0/16"
vpc_id = "vpc-d6bd2fb9"
web_security_group_id = "sg-e37b39dc9ea8ce00e"
```

That apply log is the proof for the next section, so it is worth keeping on screen.

---

## Dependencies

This is the part of Terraform that is easy to assert and hard to show. Terraform never runs
resources in file order. It builds a directed acyclic graph of dependencies and walks it, running
everything it can in parallel. Dependencies get into that graph two ways.

### Implicit dependencies - the normal kind

Any time one resource's argument references another resource's attribute, Terraform records an edge.
No keyword is involved:

```hcl
resource "aws_subnet" "public" {
  vpc_id = aws_vpc.main.id
  ...
}
```

`aws_vpc.main.id` is unknown until the VPC exists, so Terraform *must* create the VPC first. The
graph below has 21 edges and 19 of them were formed this way, including some that are not obvious:

- `aws_route_table.public` references `aws_internet_gateway.main.id` inside its `route` block, so
  the gateway is built before the route table.
- `aws_security_group.app` references `aws_security_group.web.id` as a rule source, so the groups
  are strictly ordered even though neither contains the other.
- `aws_s3_object.app_config` references `aws_vpc.main.id` inside its JSON body, which creates an
  edge from an S3 object to a VPC - two things with no architectural relationship whatsoever.

### Explicit dependencies - `depends_on`

`depends_on` is for ordering that is real but invisible to Terraform, because no attribute is
referenced. There are two in this project, and neither is decoration.

```hcl
resource "aws_instance" "web" {
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web.id]

  user_data = <<-EOT
    #!/bin/bash
    set -euo pipefail
    yum install -y httpd
    ...
  EOT

  depends_on = [aws_route_table_association.public]
}
```

The instance references the subnet and the security group, so those two edges exist already. It does
**not** reference `aws_route_table_association.public` - nothing about an instance mentions a route
table association. But the boot script runs `yum install -y httpd`, which needs to reach the
internet, which needs the subnet's route table to already carry the `0.0.0.0/0 -> igw` route. Without
`depends_on`, Terraform is free to launch the instance and wire up the route table in parallel, and
the boot script fails intermittently. This is the single most common real-world use of `depends_on`.

The second one is the standard S3 ordering problem:

```hcl
resource "aws_s3_bucket_policy" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  policy = jsonencode({ ... })

  depends_on = [aws_s3_bucket_public_access_block.artifacts]
}
```

Both resources target the same bucket and neither references the other, so Terraform would happily
run them at the same time. If the public access block lands second, it can reject or conflict with
the policy write. Ordering them is the fix.

### Proving the order: `terraform graph`

```bash
terraform graph
```

```text
digraph G {
  rankdir = "RL";
  node [shape = rect, fontname = "sans-serif"];
  "data.aws_ami.amazon_linux" [label="data.aws_ami.amazon_linux"];
  "data.aws_caller_identity.current" [label="data.aws_caller_identity.current"];
  "aws_instance.web" [label="aws_instance.web"];
  "aws_internet_gateway.main" [label="aws_internet_gateway.main"];
  "aws_network_acl.public" [label="aws_network_acl.public"];
  "aws_route_table.private" [label="aws_route_table.private"];
  "aws_route_table.public" [label="aws_route_table.public"];
  "aws_route_table_association.private" [label="aws_route_table_association.private"];
  "aws_route_table_association.public" [label="aws_route_table_association.public"];
  "aws_s3_bucket.artifacts" [label="aws_s3_bucket.artifacts"];
  "aws_s3_bucket_policy.artifacts" [label="aws_s3_bucket_policy.artifacts"];
  "aws_s3_bucket_public_access_block.artifacts" [label="aws_s3_bucket_public_access_block.artifacts"];
  "aws_s3_bucket_versioning.artifacts" [label="aws_s3_bucket_versioning.artifacts"];
  "aws_s3_object.app_config" [label="aws_s3_object.app_config"];
  "aws_security_group.app" [label="aws_security_group.app"];
  "aws_security_group.web" [label="aws_security_group.web"];
  "aws_subnet.private" [label="aws_subnet.private"];
  "aws_subnet.public" [label="aws_subnet.public"];
  "aws_vpc.main" [label="aws_vpc.main"];
  "aws_instance.web" -> "data.aws_ami.amazon_linux";
  "aws_instance.web" -> "aws_route_table_association.public";
  "aws_instance.web" -> "aws_security_group.web";
  "aws_internet_gateway.main" -> "aws_vpc.main";
  "aws_network_acl.public" -> "aws_subnet.public";
  "aws_route_table.private" -> "aws_vpc.main";
  "aws_route_table.public" -> "aws_internet_gateway.main";
  "aws_route_table_association.private" -> "aws_route_table.private";
  "aws_route_table_association.private" -> "aws_subnet.private";
  "aws_route_table_association.public" -> "aws_route_table.public";
  "aws_route_table_association.public" -> "aws_subnet.public";
  "aws_s3_bucket.artifacts" -> "data.aws_caller_identity.current";
  "aws_s3_bucket_policy.artifacts" -> "aws_s3_bucket_public_access_block.artifacts";
  "aws_s3_bucket_public_access_block.artifacts" -> "aws_s3_bucket.artifacts";
  "aws_s3_bucket_versioning.artifacts" -> "aws_s3_bucket.artifacts";
  "aws_s3_object.app_config" -> "aws_s3_bucket.artifacts";
  "aws_s3_object.app_config" -> "aws_vpc.main";
  "aws_security_group.app" -> "aws_security_group.web";
  "aws_security_group.web" -> "aws_vpc.main";
  "aws_subnet.private" -> "aws_vpc.main";
  "aws_subnet.public" -> "aws_vpc.main";
}
```

`A -> B` reads *"A depends on B, so B is created first"*. Graphviz is not installed on this machine,
so this is the raw DOT source rather than a rendered picture; `terraform graph | dot -Tpng > g.png`
renders it anywhere `dot` is available.

The two explicit dependencies are in there, indistinguishable from the implicit ones:

```text
"aws_instance.web" -> "aws_route_table_association.public";
"aws_s3_bucket_policy.artifacts" -> "aws_s3_bucket_public_access_block.artifacts";
```

`aws_s3_object.app_config -> aws_vpc.main` is the accidental edge from putting `aws_vpc.main.id`
inside the object's JSON. It is harmless here, but it is exactly how a configuration acquires a
dependency nobody intended - and later, a surprise replacement.

Two details in that output are worth pausing on.

`aws_subnet.private` appears once, not twice. `terraform graph` draws the *configuration* graph,
where a `for_each` resource is a single node; the apply then expands it into `["app"]` and
`["data"]`.

And there is no `"aws_instance.web" -> "aws_subnet.public"` edge, even though `main.tf` clearly
contains `subnet_id = aws_subnet.public.id`. Terraform applies a transitive reduction: the ordering
is already guaranteed by the longer path
`aws_instance.web -> aws_route_table_association.public -> aws_subnet.public`, so the direct edge is
redundant and gets dropped. The dependency is still enforced - it is just not drawn twice.

### Proving the order: the apply log

The graph is the theory. The apply log above is the evidence. Reading it top to bottom:

| Order | What happened | Why |
|---|---|---|
| 1 | `aws_vpc.main` and `aws_s3_bucket.artifacts` start together | neither depends on the other; the bucket only waited on the `aws_caller_identity` data source, which resolved during the plan |
| 2 | the moment the VPC completes, the IGW, both route tables, all three subnets and `hw19-web-sg` all start at once | every one of them has exactly one edge, to `aws_vpc.main` |
| 3 | `aws_security_group.app` starts only after `aws_security_group.web: Creation complete` | implicit edge through the rule's `security_groups` argument |
| 4 | `aws_route_table_association.public` waits for both `aws_route_table.public` and `aws_subnet.public` | two implicit edges; the subnet took 10s, so the association waited 10s |
| 5 | `aws_instance.web: Creating...` appears **after** `aws_route_table_association.public: Creation complete` | the explicit `depends_on`, doing its job |
| 6 | `aws_s3_bucket_policy.artifacts` starts after `aws_s3_bucket_public_access_block.artifacts` completes | the second explicit `depends_on` |

Step 5 is the one to check against the log. `aws_subnet.public` took 10 seconds in LocalStack while
everything else took under a second, which stretched the timeline enough to make the ordering
unmistakable:

```text
aws_subnet.public: Creation complete after 10s [id=subnet-06e8f5e4]
aws_route_table_association.public: Creating...
aws_network_acl.public: Creating...
aws_route_table_association.public: Creation complete after 0s [id=rtbassoc-6cc83c0e]
aws_instance.web: Creating...
```

The instance was the last resource to start, even though `aws_instance.web` is roughly in the middle
of `main.tf`. File order is irrelevant; the graph decides.

---

## Outputs

Nineteen outputs in `outputs.tf`. They are the project's public interface - the values another
module, a CI job or a human needs after the apply. Plain ones just surface an attribute:

```hcl
output "vpc_id" {
  description = "Id of the VPC every other resource hangs off."
  value       = aws_vpc.main.id
}
```

Three are computed rather than copied, which is where outputs earn their keep. This one turns the
`for_each` instances back into a map keyed the same way the input was:

```hcl
output "private_subnet_ids" {
  description = "Map of role name to private subnet id, built from the for_each instances."
  value       = { for k, s in aws_subnet.private : k => s.id }
}
```

```text
private_subnet_ids = {
  "app" = "subnet-55e1f360"
  "data" = "subnet-a66e233f"
}
```

### `sensitive = true`

```hcl
output "app_admin_token" {
  description = "Admin token handed to the application. Marked sensitive, so the bulk terraform output listing and the plan and apply logs redact it."
  value       = var.app_admin_token
  sensitive   = true
}
```

What `terraform output` actually does with it, run three ways:

```bash
terraform output
```

```text
ami_id = "ami-01f446d4eeaed8a3c"
app_admin_token = <sensitive>
app_security_group_id = "sg-bf6b1ac74974fe6b5"
artifacts_bucket = "hw19-artifacts-000000000000"
artifacts_bucket_arn = "arn:aws:s3:::hw19-artifacts-000000000000"
instance_id = "i-b15f937d0ca1b5c2f"
(13 more outputs, identical to the apply listing above)
```

```bash
terraform output app_admin_token
```

```text
"hw19-local-demo-token"
```

```bash
terraform output -raw app_admin_token
```

```text
hw19-local-demo-token
```

Read those carefully, because the common belief about `sensitive = true` is wrong.

It redacts the value **only in bulk output** - the unqualified `terraform output`, and the plan and
apply logs, which is genuinely useful because those get pasted into tickets and CI logs. The moment
you ask for the output by name it prints in full; `-raw` only strips the JSON quoting. `sensitive`
is a defence against accidental shoulder-surfing and log leakage, not an access control.

And it is not encryption. The same token sits in plain text in the state file, twice:

```bash
grep -o 'hw19-local-demo-token' terraform.tfstate | sort | uniq -c
```

```text
   2 hw19-local-demo-token
```

Once as the output value and once inside the `aws_s3_object` body. That is the real reason
`*.tfstate*` is in `.gitignore`, and the reason production setups put state in an encrypted S3
backend with restricted access rather than on a laptop.

---

## State, the source of truth

State is the mapping between the names in your `.tf` files and the real objects in the cloud.
Without it Terraform would have no way to know that `aws_vpc.main` means `vpc-d6bd2fb9`.

```bash
terraform state list
```

```text
data.aws_ami.amazon_linux
data.aws_caller_identity.current
aws_instance.web
aws_internet_gateway.main
aws_network_acl.public
aws_route_table.private
aws_route_table.public
aws_route_table_association.private["app"]
aws_route_table_association.private["data"]
aws_route_table_association.public
aws_s3_bucket.artifacts
aws_s3_bucket_policy.artifacts
aws_s3_bucket_public_access_block.artifacts
aws_s3_bucket_versioning.artifacts
aws_s3_object.app_config
aws_security_group.app
aws_security_group.web
aws_subnet.private["app"]
aws_subnet.private["data"]
aws_subnet.public
aws_vpc.main
```

Nineteen resources plus the two data sources. The `for_each` instances show their map keys, which is
how you address one of them for a targeted operation.

`terraform state show` prints everything Terraform knows about one address, including attributes you
never wrote:

```bash
terraform state show aws_subnet.public
```

```text
# aws_subnet.public:
resource "aws_subnet" "public" {
    arn                                            = "arn:aws:ec2:us-east-1:000000000000:subnet/subnet-06e8f5e4"
    assign_ipv6_address_on_creation                = false
    availability_zone                              = "us-east-1a"
    availability_zone_id                           = "use1-az6"
    cidr_block                                     = "10.19.1.0/24"
    customer_owned_ipv4_pool                       = null
    enable_dns64                                   = false
    enable_lni_at_device_index                     = 0
    enable_resource_name_dns_a_record_on_launch    = false
    enable_resource_name_dns_aaaa_record_on_launch = false
    id                                             = "subnet-06e8f5e4"
    ipv6_cidr_block                                = null
    ipv6_cidr_block_association_id                 = null
    ipv6_native                                    = false
    map_customer_owned_ip_on_launch                = false
    map_public_ip_on_launch                        = true
    outpost_arn                                    = null
    owner_id                                       = "000000000000"
    private_dns_hostname_type_on_launch            = "ip-name"
    region                                         = "us-east-1"
    tags                                           = {
        "Name" = "hw19-public-subnet"
        "Tier" = "public"
    }
    tags_all                                       = {
        "Environment" = "dev"
        "ManagedBy"   = "Terraform"
        "Name"        = "hw19-public-subnet"
        "Project"     = "hw19"
        "Session"     = "19"
        "Tier"        = "public"
    }
    vpc_id                                         = "vpc-d6bd2fb9"
}
```

`main.tf` set five arguments on this subnet. The state holds twenty-three, because AWS filled in the
rest: `availability_zone_id`, `owner_id`, the ARN, and every default the API applied. `tags` versus
`tags_all` is the `default_tags` mechanism made visible - `tags` is what the resource block asked
for, `tags_all` is that merged with the provider defaults.

The state file's own header:

```bash
python3 -c "
import json
d=json.load(open('terraform.tfstate'))
print('version        :', d['version'])
print('terraform_ver  :', d['terraform_version'])
print('serial         :', d['serial'])
print('resources      :', len(d['resources']))
print('outputs        :', len(d['outputs']))
"
```

```text
version        : 4
terraform_ver  : 1.16.4
serial         : 20
resources      : 19
outputs        : 19
```

The `serial` increments on every write, which is how remote-state locking detects two people
applying at once.

### Why state is the source of truth, and how it stops being one

State is what makes `plan` possible. Terraform compares three things: the configuration (what you
want), the state (what it last recorded), and a refresh of the real API (what is actually there).
`plan` is the diff.

That also means state can be **wrong**, and the plan is the tool that finds out. Changing a tag
outside Terraform:

```bash
aws ec2 create-tags --resources vpc-d6bd2fb9 --tags Key=Name,Value=someone-renamed-this
aws ec2 describe-vpcs --vpc-ids vpc-d6bd2fb9 --query 'Vpcs[0].Tags[?Key==`Name`]' --output json
```

```text
[
    {
        "Key": "Name",
        "Value": "someone-renamed-this"
    }
]
```

```bash
terraform plan
```

```text
  # aws_vpc.main will be updated in-place
  ~ resource "aws_vpc" "main" {
        id                                   = "vpc-d6bd2fb9"
      ~ tags                                 = {
          ~ "Name" = "someone-renamed-this" -> "hw19-vpc"
            "Tier" = "network"
        }
      ~ tags_all                             = {
          ~ "Name"        = "someone-renamed-this" -> "hw19-vpc"
            # (5 unchanged elements hidden)
        }
        # (19 unchanged attributes hidden)
    }
```

Terraform refreshed, found reality had moved, and proposed to move it back. Applying restores the
tag:

```bash
terraform apply
aws ec2 describe-vpcs --vpc-ids vpc-d6bd2fb9 --query 'Vpcs[0].Tags[?Key==`Name`]' --output json
```

```text
aws_vpc.main: Modifying... [id=vpc-d6bd2fb9]
aws_vpc.main: Modifications complete after 0s [id=vpc-d6bd2fb9]
aws_instance.web: Modifying... [id=i-5d11bf2d8eedb816c]
aws_instance.web: Modifications complete after 0s [id=i-5d11bf2d8eedb816c]
Apply complete! Resources: 0 added, 2 changed, 0 destroyed.

[
    {
        "Key": "Name",
        "Value": "hw19-vpc"
    }
]
```

The second changed resource in that apply is `aws_instance.web`, and it is not drift at all - it is
the LocalStack bug described in
[security group attachments do not round-trip](#2-security-group-attachments-do-not-round-trip-on-an-instance),
which makes that one resource show a diff on every single plan.

This is why clicking in the console on Terraform-managed infrastructure causes problems: the config
is the intent, and the next apply enforces it, silently reverting whatever was done by hand.

---

## Showing a change, not just create and destroy

### `~ update in place`

Two edits to `terraform.tfvars`:

```hcl
environment    = "staging"
allowed_ssh_cidr = "10.19.1.0/24"
```

```bash
terraform plan -out=tfplan-change
```

Thirteen resources are affected - every resource that carries tags picks up the new `Environment`
value through `default_tags`, and `hw19-web-sg` additionally gets a rewritten SSH rule. Two of the
thirteen, with the other eleven cut for length:

```text
  # aws_security_group.web will be updated in-place
  ~ resource "aws_security_group" "web" {
        id                     = "sg-e37b39dc9ea8ce00e"
      ~ ingress                = [
          - {
              - cidr_blocks      = [
                  - "10.19.0.0/16",
                ]
              - description      = "SSH from a trusted range only"
              - from_port        = 22
              - ipv6_cidr_blocks = []
              - prefix_list_ids  = []
              - protocol         = "tcp"
              - security_groups  = []
              - self             = false
              - to_port          = 22
            },
          + {
              + cidr_blocks      = [
                  + "10.19.1.0/24",
                ]
              + description      = "SSH from a trusted range only"
              + from_port        = 22
              + ipv6_cidr_blocks = []
              + prefix_list_ids  = []
              + protocol         = "tcp"
              + security_groups  = []
              + self             = false
              + to_port          = 22
            },
            # (2 unchanged elements hidden)
        ]
        name                   = "hw19-web-sg"
      ~ tags                   = {
          - "Environment" = "dev" -> null
            "Name"        = "hw19-web-sg"
            "Tier"        = "public"
        }
      ~ tags_all               = {
          ~ "Environment" = "dev" -> "staging"
            # (5 unchanged elements hidden)
        }
        # (8 unchanged attributes hidden)
    }

  # aws_vpc.main will be updated in-place
  ~ resource "aws_vpc" "main" {
        id                                   = "vpc-d6bd2fb9"
      ~ tags                                 = {
          - "Environment" = "dev" -> null
            "Name"        = "hw19-vpc"
            "Tier"        = "network"
        }
      ~ tags_all                             = {
          ~ "Environment" = "dev" -> "staging"
            # (5 unchanged elements hidden)
        }
        # (19 unchanged attributes hidden)
    }

Plan: 0 to add, 13 to change, 0 to destroy.

Changes to Outputs:
  ~ resource_summary      = {
      ~ environment     = "dev" -> "staging"
        # (3 unchanged attributes hidden)
    }
```

The `~` prefix and the `id` line staying put, rather than becoming `(known after apply)`, is the
signal: these objects keep their identity. Applying:

```bash
terraform apply tfplan-change
```

```text
aws_vpc.main: Modifying... [id=vpc-d6bd2fb9]
aws_s3_bucket.artifacts: Modifying... [id=hw19-artifacts-000000000000]
aws_vpc.main: Modifications complete after 0s [id=vpc-d6bd2fb9]
aws_internet_gateway.main: Modifying... [id=igw-d59b4ba3]
aws_route_table.private: Modifying... [id=rtb-7dc464e2]
aws_subnet.private["app"]: Modifying... [id=subnet-55e1f360]
aws_subnet.private["data"]: Modifying... [id=subnet-a66e233f]
aws_subnet.public: Modifying... [id=subnet-06e8f5e4]
aws_s3_bucket.artifacts: Modifications complete after 0s [id=hw19-artifacts-000000000000]
aws_security_group.web: Modifying... [id=sg-e37b39dc9ea8ce00e]
aws_s3_object.app_config: Modifying... [id=hw19-artifacts-000000000000/config/app.json]
aws_route_table.private: Modifications complete after 0s [id=rtb-7dc464e2]
aws_internet_gateway.main: Modifications complete after 0s [id=igw-d59b4ba3]
aws_subnet.public: Modifications complete after 0s [id=subnet-06e8f5e4]
aws_subnet.private["data"]: Modifications complete after 0s [id=subnet-a66e233f]
aws_subnet.private["app"]: Modifications complete after 0s [id=subnet-55e1f360]
aws_s3_object.app_config: Modifications complete after 0s [id=hw19-artifacts-000000000000/config/app.json]
aws_security_group.web: Modifications complete after 0s [id=sg-e37b39dc9ea8ce00e]
aws_route_table.public: Modifying... [id=rtb-7b1df825]
aws_network_acl.public: Modifying... [id=acl-74d05f5b]
aws_security_group.app: Modifying... [id=sg-bf6b1ac74974fe6b5]
aws_route_table.public: Modifications complete after 0s [id=rtb-7b1df825]
aws_network_acl.public: Modifications complete after 0s [id=acl-74d05f5b]
aws_security_group.app: Modifications complete after 0s [id=sg-bf6b1ac74974fe6b5]
aws_instance.web: Modifying... [id=i-b15f937d0ca1b5c2f]
aws_instance.web: Modifications complete after 0s [id=i-b15f937d0ca1b5c2f]
Apply complete! Resources: 0 added, 13 changed, 0 destroyed.
```

Every id before and after is identical - `vpc-d6bd2fb9`, `subnet-06e8f5e4`, `i-b15f937d0ca1b5c2f`.
Nothing was torn down. Verified independently:

```bash
aws ec2 describe-security-groups --group-ids sg-e37b39dc9ea8ce00e \
  --query 'SecurityGroups[0].IpPermissions[?FromPort==`22`].{From:FromPort,Cidrs:IpRanges[].CidrIp}' --output json
aws ec2 describe-vpcs --vpc-ids vpc-d6bd2fb9 --query 'Vpcs[0].Tags[?Key==`Environment`]' --output json
```

```text
[
    {
        "From": 22,
        "Cidrs": [
            "10.19.1.0/24"
        ]
    }
]
[
    {
        "Key": "Environment",
        "Value": "staging"
    }
]
```

One oddity in that diff is worth explaining rather than glossing over: `tags` shows
`- "Environment" = "dev" -> null` while `tags_all` shows `~ "dev" -> "staging"`. The `tags` argument
was never written with an `Environment` key - it comes from `default_tags`. On refresh the provider
reads all six tags back from the API and cannot tell which came from where, so it records them in
`tags` too and then proposes to remove the one it does not own. It is noise, not a real change, and
`tags_all` holds the truth.

### `-/+` forces replacement

Not every change can be made in place. The CIDR of a subnet is fixed at creation, so changing it
means AWS has to be given a new subnet:

```bash
terraform plan -var='public_subnet_cidr=10.19.2.0/24'
```

```text
  # aws_route_table_association.public must be replaced
-/+ resource "aws_route_table_association" "public" {
      ~ id             = "rtbassoc-6cc83c0e" -> (known after apply)
      ~ subnet_id      = "subnet-06e8f5e4" -> (known after apply) # forces replacement
        # (3 unchanged attributes hidden)
    }

  # aws_subnet.public must be replaced
-/+ resource "aws_subnet" "public" {
      ~ arn                                            = "arn:aws:ec2:us-east-1:000000000000:subnet/subnet-06e8f5e4" -> (known after apply)
      ~ availability_zone_id                           = "use1-az6" -> (known after apply)
      ~ cidr_block                                     = "10.19.1.0/24" -> "10.19.2.0/24" # forces replacement
      - enable_lni_at_device_index                     = 0 -> null
      ~ id                                             = "subnet-06e8f5e4" -> (known after apply)
      + ipv6_cidr_block                                = (known after apply)
      + ipv6_cidr_block_association_id                 = (known after apply)
      - map_customer_owned_ip_on_launch                = false -> null
      ~ owner_id                                       = "000000000000" -> (known after apply)
      ~ private_dns_hostname_type_on_launch            = "ip-name" -> (known after apply)
        tags                                           = {
            "Name" = "hw19-public-subnet"
            "Tier" = "public"
        }
        # (12 unchanged attributes hidden)
    }

Plan: 3 to add, 1 to change, 3 to destroy.
```

That is two of the three replaced resources; `aws_instance.web` is the third and is cut for length.
One edited variable, **three** resources replaced. Terraform marked the exact attribute with
`# forces replacement`, and then the dependency graph propagated it: the subnet's new id is
`(known after apply)`, so anything holding the old id - the route table association and the EC2
instance - cannot survive either. Scroll up to the graph and the blast radius is predictable in
advance.

```bash
terraform apply -var='public_subnet_cidr=10.19.2.0/24'
```

```text
aws_instance.web: Destroying... [id=i-b15f937d0ca1b5c2f]
aws_instance.web: Destruction complete after 10s
aws_route_table_association.public: Destroying... [id=rtbassoc-6cc83c0e]
aws_route_table_association.public: Destruction complete after 0s
aws_subnet.public: Destroying... [id=subnet-06e8f5e4]
aws_subnet.public: Destruction complete after 0s
aws_subnet.public: Creating...
aws_subnet.public: Creation complete after 10s [id=subnet-b2cf855f]
aws_route_table_association.public: Creating...
aws_network_acl.public: Modifying... [id=acl-74d05f5b]
aws_route_table_association.public: Creation complete after 0s [id=rtbassoc-246772dd]
aws_instance.web: Creating...
aws_network_acl.public: Modifications complete after 0s [id=acl-74d05f5b]
aws_instance.web: Creation complete after 10s [id=i-5d11bf2d8eedb816c]
Apply complete! Resources: 3 added, 1 changed, 3 destroyed.
```

The ordering is the graph run **backwards and then forwards**. Destruction goes from the most
dependent resource to the least - instance, then association, then subnet - because you cannot
delete a subnet that still has things in it. Creation then runs in the normal direction: subnet,
association, instance.

Three facts to take from that log:

1. The EC2 instance got a **new id** (`i-b15f937d0ca1b5c2f` to `i-5d11bf2d8eedb816c`) and a new
   private IP, for a change that was nominally about a subnet. On real AWS everything on that
   instance's local disk would be gone.
2. `aws_network_acl.public` was only *modified*, not replaced. It holds a list of subnet ids, which
   is a mutable attribute, so the provider could update it in place.
3. `terraform plan` said this would happen before anything was touched. That is the entire argument
   for reading plans.

This replacement was triggered with a command-line `-var` rather than by editing the committed
files; `terraform.tfvars.example` still ships `public_subnet_cidr = "10.19.1.0/24"`.

---

## S3: the storage end of the architecture

Four resources plus one object, chained off a single bucket. The bucket name is computed rather
than typed, because S3 bucket names are globally unique across all of AWS:

```hcl
locals {
  bucket_name = "${var.project_prefix}-artifacts-${data.aws_caller_identity.current.account_id}"
}
```

```bash
aws s3api list-buckets --query 'Buckets[].Name' --output json
aws s3api list-objects-v2 --bucket hw19-artifacts-000000000000 --query 'Contents[].{Key:Key,Size:Size}' --output table
aws s3api get-bucket-versioning --bucket hw19-artifacts-000000000000
aws s3api get-public-access-block --bucket hw19-artifacts-000000000000
```

```text
[
    "hw19-artifacts-000000000000"
]
-----------------------------
|       ListObjectsV2       |
+------------------+--------+
|        Key       | Size   |
+------------------+--------+
|  config/app.json |  137   |
+------------------+--------+
{
    "Status": "Enabled"
}
{
    "PublicAccessBlockConfiguration": {
        "BlockPublicAcls": true,
        "IgnorePublicAcls": true,
        "BlockPublicPolicy": true,
        "RestrictPublicBuckets": true
    }
}
```

`000000000000` is LocalStack's fixed account id. On real AWS this would be your twelve-digit account
number, which is what makes the name unique.

The object content is built with `jsonencode()` from live values, which is how the implicit
dependency on the VPC got there:

```bash
aws s3 cp s3://hw19-artifacts-000000000000/config/app.json -
```

```text
{
  "admin_token": "hw19-local-demo-token",
  "app_port": 8080,
  "environment": "dev",
  "project": "hw19",
  "region": "us-east-1",
  "vpc_id": "vpc-d6bd2fb9"
}
```

After the `environment = "staging"` change this object was rewritten by the same apply:

```bash
aws s3 cp s3://hw19-artifacts-000000000000/config/app.json - | python3 -c 'import sys,json;d=json.load(sys.stdin);print("environment =",d["environment"])'
```

```text
environment = staging
```

Note the token sitting in the object body in plain text. In a real system this would come from
Secrets Manager or SSM Parameter Store at boot, not be baked into an artifact - putting it here was
deliberate, to make the point in the [sensitive outputs](#sensitive--true) section concrete.

---

## What LocalStack could not do

Everything in this README ran against an emulator. These are the places that emulator and AWS
disagree, each one found by running the command, not by reading documentation.

### 1. The EC2 instance is a database row, not a machine

```bash
aws ec2 describe-instances --filters "Name=tag:Project,Values=hw19" \
  --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name,Type:InstanceType,AZ:Placement.AvailabilityZone,Subnet:SubnetId,PrivIp:PrivateIpAddress,PubIp:PublicIpAddress,Sg:SecurityGroups[].GroupName}' \
  --output json
```

```text
[
    {
        "Id": "i-b15f937d0ca1b5c2f",
        "State": "running",
        "Type": "t3.micro",
        "AZ": "us-east-1a",
        "Subnet": "subnet-06e8f5e4",
        "PrivIp": "10.19.1.4",
        "PubIp": "54.214.145.148",
        "Sg": []
    }
]
```

`"State": "running"` is not a lie exactly - the API field genuinely says running - but there is no
machine. LocalStack community has no hypervisor. Nothing new appeared on the host when the instance
was created:

```bash
docker ps --format '{{.Names}}\t{{.Image}}'
```

```text
hw20-node-exporter	prom/node-exporter:v1.9.1
hw20-grafana	grafana/grafana:12.1.1
hw20-prometheus	prom/prometheus:v3.5.0
hw20-alertmanager	prom/alertmanager:v0.28.1
localstack-main	localstack/localstack:3.8
buildx_buildkit_multiplatform-builder0	moby/buildkit:buildx-stable-1
minikube	gcr.io/k8s-minikube/kicbase:v0.0.51
```

Only `localstack-main` is relevant here; the rest belong to other sessions on this machine. There is
no container, VM or process for `i-b15f937d0ca1b5c2f`. The `user_data` script was stored as an
attribute and never executed - no `httpd` was installed and no `index.html` was written, because
there is no filesystem for them to be written to.

`54.214.145.148` deserves a warning of its own. LocalStack generated it at random, and it falls
inside a range that **really is allocated to AWS and really does belong to someone else**. It is not
yours, nothing of yours answers on it, and it must not be treated as an address to connect to. Any
`terraform output instance_public_ip` from a LocalStack run is a fiction with a real-looking shape.

### 2. Security group attachments do not round-trip on an instance

Look at `"Sg": []` in that output. The instance was created with `hw19-web-sg` attached and
Terraform recorded it, but LocalStack's `DescribeInstances` does not report security groups back.
The consequence is a plan that never converges:

```bash
terraform plan
```

```text
  # aws_instance.web will be updated in-place
  ~ resource "aws_instance" "web" {
        id                                   = "i-5d11bf2d8eedb816c"
        tags                                 = {
            "Name" = "hw19-web"
            "Tier" = "public"
        }
      ~ vpc_security_group_ids               = [
          + "sg-e37b39dc9ea8ce00e",
        ]
        # (40 unchanged attributes hidden)

        # (2 unchanged blocks hidden)
    }
```

Terraform refreshes, sees an empty list, and proposes to re-attach the group. Apply it and the same
diff is back on the next plan. This is an emulator bug, not a configuration error - against real AWS
this plan would be empty. It also means every `terraform plan` in this project after the first apply
reports `1 to change` even when nothing changed.

### 3. The bucket policy is stored but not enforced

```bash
aws s3api get-bucket-policy --bucket hw19-artifacts-000000000000 --query Policy --output text
```

```text
{
  "Statement": [
    {
      "Action": "s3:*",
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      },
      "Effect": "Deny",
      "Principal": "*",
      "Resource": [
        "arn:aws:s3:::hw19-artifacts-000000000000",
        "arn:aws:s3:::hw19-artifacts-000000000000/*"
      ],
      "Sid": "DenyInsecureTransport"
    }
  ],
  "Version": "2012-10-17"
}
```

That policy denies every S3 action when the request did not arrive over TLS. Every call in this
README went to `http://localhost:4566` - plain HTTP, `aws:SecureTransport` false. So this should be
denied:

```bash
aws s3api list-objects-v2 --bucket hw19-artifacts-000000000000 --query 'Contents[].Key' --output text
```

```text
config/app.json
```

It succeeded. LocalStack community stores bucket policies faithfully and returns them on request,
but does not run them through a policy evaluation engine. Real AWS would have returned
`An error occurred (AccessDenied)`. The same applies to IAM in general here - a policy's *presence*
can be tested, its *effect* cannot.

### 4. Custom network ACLs have no implicit deny

Covered in [security groups vs network ACLs](#security-groups-vs-network-acls). The VPC's default
ACL carries the `32767 deny 0.0.0.0/0` rules; `hw19-public-nacl` does not, because LocalStack does
not append it. Real AWS always does, in both directions, and it cannot be removed.

### 5. Services that simply are not there

The container's health endpoint lists what is enabled:

```bash
curl -s http://localhost:4566/_localstack/health | python3 -c "import sys,json;d=json.load(sys.stdin);print('edition:',d['edition'],'version:',d['version']);print('enabled:',sorted(k for k,v in d['services'].items() if v=='running'));print('disabled count:',sum(1 for v in d['services'].values() if v!='running'))"
```

```text
edition: community version: 3.8.1
enabled: ['ec2', 'iam', 's3', 'sts']
disabled count: 31
```

Four services are enabled, which is exactly the four this project needs. RDS is not in the community
image at all. Anything that would have needed CloudWatch, Lambda or Route 53 was left out of the
design rather than faked.

### Honest scorecard

| Claim in this README | Where it holds |
|---|---|
| VPC, subnets, IGW, route tables, associations created and queryable | identical to AWS |
| Security group rules, including source-security-group rules | stored and reported correctly; **enforcement untested** |
| Network ACL rules | stored; missing the implicit deny; **enforcement untested** |
| EC2 instance exists with an id, IP and state | API-level only; **no machine** |
| `user_data` boot script | stored; **never ran** |
| S3 bucket, versioning, public access block, object | behaves like AWS |
| S3 bucket policy | stored; **not enforced** |
| Terraform providers, variables, validation, outputs, dependencies, graph, state, plan, apply, change, replacement, destroy | fully real - these are Terraform behaviours, not AWS behaviours, and the emulator does not affect them |

The last row is the important one. Everything the *session* is actually about - how Terraform plans,
orders, records and reverses changes - is exercised for real. What the emulator weakens is the AWS
runtime behaviour underneath, and every instance of that is listed above.

---

## Destroy and cleanup

Always read the destroy plan before running the destroy. `-destroy` on `plan` shows exactly what
will go. The real output prints every attribute of every doomed resource across 754 lines; only the
header lines and the summary are reproduced here:

```bash
terraform plan -destroy
```

```text
  # aws_instance.web will be destroyed
  # aws_internet_gateway.main will be destroyed
  # aws_network_acl.public will be destroyed
  # aws_route_table.private will be destroyed
  # aws_route_table.public will be destroyed
  # aws_route_table_association.private["app"] will be destroyed
  # aws_route_table_association.private["data"] will be destroyed
  # aws_route_table_association.public will be destroyed
  # aws_s3_bucket.artifacts will be destroyed
  # aws_s3_bucket_policy.artifacts will be destroyed
  # aws_s3_bucket_public_access_block.artifacts will be destroyed
  # aws_s3_bucket_versioning.artifacts will be destroyed
  # aws_s3_object.app_config will be destroyed
  # aws_security_group.app will be destroyed
  # aws_security_group.web will be destroyed
  # aws_subnet.private["app"] will be destroyed
  # aws_subnet.private["data"] will be destroyed
  # aws_subnet.public will be destroyed
  # aws_vpc.main will be destroyed

Plan: 0 to add, 0 to change, 19 to destroy.
```

Nineteen - the same nineteen that were created. Terraform destroys only what is in its state; the
pre-existing `vpc-26226ba4` default VPC in this LocalStack instance is not in the state and is not
touched.

```bash
terraform destroy
```

```text
aws_s3_bucket_policy.artifacts: Destroying... [id=hw19-artifacts-000000000000]
aws_route_table_association.private["app"]: Destroying... [id=rtbassoc-82d4716d]
aws_route_table_association.private["data"]: Destroying... [id=rtbassoc-e0e3fd2a]
aws_security_group.app: Destroying... [id=sg-bf6b1ac74974fe6b5]
aws_s3_bucket_versioning.artifacts: Destroying... [id=hw19-artifacts-000000000000]
aws_s3_object.app_config: Destroying... [id=hw19-artifacts-000000000000/config/app.json]
aws_network_acl.public: Destroying... [id=acl-74d05f5b]
aws_instance.web: Destroying... [id=i-5d11bf2d8eedb816c]
aws_s3_bucket_versioning.artifacts: Destruction complete after 0s
aws_route_table_association.private["data"]: Destruction complete after 0s
aws_s3_bucket_policy.artifacts: Destruction complete after 0s
aws_route_table_association.private["app"]: Destruction complete after 0s
aws_s3_object.app_config: Destruction complete after 0s
aws_network_acl.public: Destruction complete after 0s
aws_security_group.app: Destruction complete after 0s
aws_s3_bucket_public_access_block.artifacts: Destroying... [id=hw19-artifacts-000000000000]
aws_route_table.private: Destroying... [id=rtb-7dc464e2]
aws_subnet.private["app"]: Destroying... [id=subnet-55e1f360]
aws_subnet.private["data"]: Destroying... [id=subnet-a66e233f]
aws_s3_bucket_public_access_block.artifacts: Destruction complete after 0s
aws_subnet.private["app"]: Destruction complete after 0s
aws_subnet.private["data"]: Destruction complete after 0s
aws_s3_bucket.artifacts: Destroying... [id=hw19-artifacts-000000000000]
aws_s3_bucket.artifacts: Destruction complete after 0s
aws_route_table.private: Destruction complete after 0s
aws_instance.web: Destruction complete after 10s
aws_route_table_association.public: Destroying... [id=rtbassoc-246772dd]
aws_security_group.web: Destroying... [id=sg-e37b39dc9ea8ce00e]
aws_route_table_association.public: Destruction complete after 0s
aws_security_group.web: Destruction complete after 0s
aws_route_table.public: Destroying... [id=rtb-7b1df825]
aws_subnet.public: Destroying... [id=subnet-b2cf855f]
aws_subnet.public: Destruction complete after 0s
aws_route_table.public: Destruction complete after 0s
aws_internet_gateway.main: Destroying... [id=igw-d59b4ba3]
aws_internet_gateway.main: Destruction complete after 0s
aws_vpc.main: Destroying... [id=vpc-d6bd2fb9]
aws_vpc.main: Destruction complete after 0s

Destroy complete! Resources: 19 destroyed.
```

This log is the dependency graph run in reverse, and it is as good a demonstration of the graph as
the apply was. Leaf resources go first - bucket policy, object, associations, `hw19-app-sg`,
`aws_instance.web`. The subnets wait for the instance and the associations. The IGW waits for the
route table that references it. `aws_vpc.main` is last, because everything else is inside it. AWS
would reject every one of those deletions if attempted in the wrong order; Terraform never attempts
the wrong order.

### Verification that nothing is left

```bash
terraform state list
terraform plan -destroy
```

```text
No changes. No objects need to be destroyed.

Either you have not created any objects yet or the existing objects were
already deleted outside of Terraform.
```

`terraform state list` printed nothing at all - the state is empty. Checking the API independently
rather than trusting Terraform:

```bash
for t in vpcs subnets internet-gateways route-tables security-groups network-acls; do
  printf '%-20s ' "$t"
  aws ec2 describe-$t --filters "Name=tag:Project,Values=hw19" --output json \
    | python3 -c "import sys,json;d=json.load(sys.stdin);k=[x for x in d if x!='ResponseMetadata'][0];print(k,'=',len(d[k]))"
done
aws ec2 describe-instances --filters "Name=tag:Project,Values=hw19" \
  "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'length(Reservations[].Instances[])' --output text
aws s3api list-buckets --query 'Buckets[].Name' --output json
```

```text
vpcs                 Vpcs = 0
subnets              Subnets = 0
internet-gateways    InternetGateways = 0
route-tables         RouteTables = 0
security-groups      SecurityGroups = 0
network-acls         NetworkAcls = 0
0
[]
```

Zero of everything, and no buckets at all. What remains in the account:

```bash
aws ec2 describe-vpcs --query 'Vpcs[].{Id:VpcId,Cidr:CidrBlock,Tags:Tags}' --output json
```

```text
[
    {
        "Id": "vpc-26226ba4",
        "Cidr": "172.31.0.0/16",
        "Tags": []
    }
]
```

That is the default VPC LocalStack creates on startup. It was there before this project and
Terraform never touched it.

Two residues are worth naming rather than hiding, because a bare `describe-instances` with no state
filter still returns rows:

```bash
aws ec2 describe-instances --filters "Name=tag:Project,Values=hw19" \
  --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name}' --output table
```

```text
---------------------------------------
|          DescribeInstances          |
+----------------------+--------------+
|          Id          |    State     |
+----------------------+--------------+
|  i-b15f937d0ca1b5c2f |  terminated  |
|  i-5d11bf2d8eedb816c |  terminated  |
+----------------------+--------------+
```

Both are `terminated`, which is **correct AWS behaviour**, not a failure to clean up. A terminated
instance stays visible in `DescribeInstances` for roughly an hour before AWS drops the record. The
two ids are the original instance and its replacement from the forced-replacement demo. Their root
volumes are genuinely gone:

```bash
aws ec2 describe-volumes --volume-ids vol-d59e94bf vol-60d57805
```

```text
aws: [ERROR]: An error occurred (InvalidVolume.NotFound) when calling the DescribeVolumes operation: The volume '{'vol-60d57805', 'vol-d59e94bf'}' does not exist.
```

The second residue is a LocalStack bug: `aws ec2 describe-tags --filters "Name=value,Values=hw19"`
still returns fifteen tag rows pointing at ids that no longer resolve, including the deleted VPC and
subnets. LocalStack does not purge its tag index when a resource is deleted. The resources
themselves are gone - every `describe-*` above proves that - but the tag index is stale.

The LocalStack container itself is deliberately left running, since other work on this machine uses
it:

```bash
docker ps --filter name=localstack-main --format '{{.Names}}  {{.Status}}'
```

```text
localstack-main  Up About an hour (healthy)
```

---

## Command reference

```text
terraform init                          download providers, write the lock file
terraform fmt                           canonicalise HCL layout
terraform validate                      local syntax, types and variable validation
terraform plan                          diff config vs state vs reality
terraform plan -out=tfplan              save that diff so apply runs exactly it
terraform plan -destroy                 preview the teardown
terraform apply tfplan                  execute a saved plan, no prompt
terraform apply                         re-plan, prompt, then execute
terraform apply -auto-approve           skip the prompt
terraform apply -var='k=v'              override one variable for this run
terraform output                        all outputs, sensitive ones redacted
terraform output <name>                 one output, sensitive ones NOT redacted
terraform output -raw <name>            one output with no quoting, for scripts
terraform state list                    every address Terraform tracks
terraform state show <address>          every attribute of one object
terraform graph                         the dependency graph as DOT
terraform destroy                       remove everything in the state
```

Plan symbols:

```text
+     create
~     update in place
-     destroy
-/+   replace: destroy then create, identity is lost
```

Variable precedence, lowest to highest:

```text
default in variables.tf
   <  terraform.tfvars  (loaded automatically)
   <  *.auto.tfvars
   <  -var-file=...
   <  -var='name=value'
   <  TF_VAR_name environment variable
```

---

## Interview questions this project answers

1. **IaaS vs PaaS vs SaaS?** Where the operational boundary sits. EC2 is IaaS - you own the OS. S3
   is a managed service closer to PaaS. Gmail is SaaS.
2. **Region vs Availability Zone?** A region is a geography and holds many AZs; an AZ is an isolated
   failure domain inside it. A VPC is regional, a subnet belongs to exactly one AZ.
3. **What makes a subnet public?** Not a flag. A route to an internet gateway in the route table
   associated with it. `map_public_ip_on_launch` is separate and useless without that route.
4. **Security group vs network ACL?** SG attaches to an interface, is stateful, allow-only. NACL
   attaches to a subnet, is stateless, allow and deny, first-match-wins by rule number. Only an SG
   can reference another SG as a source.
5. **Why does a stateless NACL need an ephemeral port rule?** Because the return packet of an
   outbound connection is evaluated from scratch, with no memory of the request that caused it.
6. **Implicit vs explicit dependency?** Implicit comes free from referencing an attribute; explicit
   is `depends_on`, for ordering that is real but not expressed by any reference - boot scripts
   needing a route, or two resources racing on the same bucket.
7. **`plan` vs `apply`?** `plan` computes the diff between config, state and reality and changes
   nothing. `apply` executes it. `-out` makes the second one provably identical to the first.
8. **What is Terraform state?** The record mapping configuration addresses to real object ids, plus
   a cached copy of every attribute. It is how `plan` knows what exists, and it contains secrets in
   plain text.
9. **What happens if someone changes a resource in the console?** The next `plan` refreshes, detects
   drift and proposes to revert it. Config is the intent.
10. **`~` vs `-/+`?** In-place update keeps the object and its id; replacement destroys and recreates
    it, losing everything not stored elsewhere. The plan marks the triggering attribute with
    `# forces replacement`.
11. **`count` vs `for_each`?** `count` addresses by index, so removing an element renumbers and
    churns the rest. `for_each` addresses by key, which is stable.
12. **What does `sensitive = true` actually protect?** Bulk output and logs. It does not encrypt the
    state file and does not stop `terraform output <name>` from printing the value.
