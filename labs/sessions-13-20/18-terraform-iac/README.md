# Session 18 - Terraform and Infrastructure as Code

Homework for session 18, covering both tasks: a complete Terraform S3 lifecycle and research
write-ups for five AWS services.

## Read this first: everything here ran against LocalStack, not real AWS

There are no real AWS credentials on this machine and none were added. Every command in every
README below was executed against **LocalStack 3.8.1 (community edition)**, an AWS API emulator
running in a local Docker container on `http://localhost:4566`.

**No resource documented here ever existed in a real AWS account.** Every ARN, instance id, bucket
name and IP address is locally generated and means nothing outside that container. Every `hw18-`
prefixed resource was destroyed at the end and the cleanup is verified with real output at the
bottom of this page.

What is genuinely real here: the Terraform behaviour (plan symbols, state, the dependency graph,
drift detection, replace-vs-update), the shape of every AWS API response, and the failures. What is
not real: enforcement, cost, and anything that requires a working network data plane.

### What differs on real AWS

| | LocalStack (here) | Real AWS |
|---|---|---|
| **ARNs** | Locally generated against account `000000000000` | Real ARNs in a real 12-digit account |
| **Cost** | Zero | Every instance-hour, GB-month, NAT gateway hour and API request is billed |
| **IAM** | Stored but **not evaluated**. Every call succeeds whatever the policy says | Enforced on every call. Missing permission means `AccessDenied` |
| **Bucket policies** | Not enforced - proven in `aws-services/03-s3` where a `Deny` did not deny | Enforced |
| **S3 lifecycle rules** | Stored, never execute | Run daily in the background |
| **Security groups / NACLs** | Stored, never evaluated - no packets exist | Filter real traffic |
| **Consistency** | Immediate | S3 object reads are strongly consistent; bucket config, IAM and route propagation are not |
| **Bucket name uniqueness** | Local to the container | Globally unique across every AWS customer |
| **EC2** | API objects only - no OS boots, nothing to SSH into | Real virtual machines |
| **Availability** | `s3`, `ec2`, `iam`, `sts` only | Everything |

Per-page caveats are stated at the top of each README.

## Folder map

```text
18-terraform-iac/
├── README.md                        this file
├── .gitignore                       excludes .terraform/, state, plan files, *.tfvars
│
├── terraform-s3-demo/               TASK 1 - the full Terraform lifecycle
│   ├── README.md                    init, fmt, validate, plan, apply, show, output, destroy
│   ├── provider.tf                  terraform{} block + aws provider pointed at LocalStack
│   ├── main.tf                      bucket, versioning, encryption, public access block, policy
│   ├── variables.tf                 typed inputs, descriptions, defaults, one validation rule
│   ├── outputs.tf                   five outputs surfaced after apply
│   ├── terraform.tfvars             actual values - gitignored, not committed
│   ├── terraform.tfvars.example     the committed template
│   ├── .gitignore                   state, plans, tfvars, provider cache
│   └── .terraform.lock.hcl          provider version pin - this one IS committed
│
└── aws-services/                    TASK 2 - service research with real commands
    ├── 01-iam/README.md             users, groups, roles, policies, least privilege
    ├── 02-ec2/README.md             AMIs, instance types, key pairs, SGs, EBS, IPs, lifecycle
    ├── 03-s3/README.md              buckets, objects, storage classes, versioning, lifecycle,
    │                                encryption, bucket policies
    ├── 04-vpc/README.md             CIDR, subnets, route tables, IGW, NAT, SGs, NACLs
    └── 05-dynamodb-rds/README.md    DynamoDB and RDS - neither runnable here, failures shown
```

## Task 1 - Terraform S3 demo

[`terraform-s3-demo/README.md`](terraform-s3-demo/README.md)

Creates `hw18-terraform-s3-demo` with versioning, SSE-S3 encryption, a public access block and a
bucket policy, then walks the full lifecycle with captured output at every step.

It is written to teach rather than transcribe, so it does several things a plain walkthrough would
not:

- **`terraform fmt` runs on a genuinely misformatted file** and the real before/after diff is shown.
- **`terraform validate` catches a real error first** - a `var.enviroment` typo - and the error
  message is shown before the fix.
- **All four plan symbols are demonstrated against actual plans.** `+` on the first apply, `~` when
  versioning flips to Suspended, `+` again when a bucket policy is added, `-/+ forces replacement`
  when the bucket is renamed, `-` on destroy.
- **Drift detection is proven**: the bucket is changed out of band with the AWS CLI, and
  `terraform plan` then proposes to put it back with no configuration change at all.
- **State is examined and explained** - `state list`, `show`, `state show`, the raw JSON, `serial`
  and `lineage` - along with the three reasons it must never be committed, verified with
  `git check-ignore`.
- **Every Terraform claim is cross-checked with the AWS CLI**, because Terraform reporting success
  is not the same as success.

Lifecycle commands covered: `init`, `fmt`, `fmt -check -diff`, `validate`, `plan`, `plan -out`,
`plan -destroy`, `apply`, `apply <planfile>`, `show`, `state list`, `state show`, `output`,
`output -raw`, `output -json`, `destroy`.

### Running it yourself

```bash
cd terraform-s3-demo
cp terraform.tfvars.example terraform.tfvars
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
terraform init
terraform plan -out=tfplan
terraform apply tfplan
terraform destroy -auto-approve
```

Requires a LocalStack container listening on `4566` with `s3` enabled.

## Task 2 - AWS services research

Five write-ups under [`aws-services/`](aws-services/). Each one is structured the same way: what the
service is, the concepts the task lists, real commands with real captured output where LocalStack
supports the service, a "when you would actually use this" section, and interview questions.

| Page | Covers | Ran for real? |
|---|---|---|
| [`01-iam`](aws-services/01-iam/README.md) | IAM, users, groups, roles, policies, permissions, least privilege, best practices, use cases | **Yes** - user, group, customer managed policy, role with a trust policy, all attached and inspected. Policy *evaluation* is not emulated, and `simulate-principal-policy` fails - both shown |
| [`02-ec2`](aws-services/02-ec2/README.md) | EC2, AMI, instance types, key pairs, security groups, EBS, public vs private IP, lifecycle, use cases | **Yes** - AMI listed, key pair created, security group with real rules, `t3.micro` launched, EBS volume created and attached, stop/start cycle captured |
| [`03-s3`](aws-services/03-s3/README.md) | S3, buckets, objects, storage classes, versioning, lifecycle policies, encryption, bucket policies, use cases | **Yes** - two versions of one key, a delete marker, recovery of an old version, lifecycle config, SSE-S3, and a bucket policy that **failed to deny**, shown as proof |
| [`04-vpc`](aws-services/04-vpc/README.md) | VPC, CIDR, subnets, route tables, IGW, NAT gateway, security groups, NACLs, public vs private subnet | **Yes** - a complete `10.42.0.0/16` VPC with public and private subnets, IGW, NAT gateway, two route tables and a custom NACL. Control plane only; no packets flow |
| [`05-dynamodb-rds`](aws-services/05-dynamodb-rds/README.md) | DynamoDB (tables, items, attributes, partition key, sort key, use cases); RDS (engines, instances, security, backups, multi-AZ, read replicas, use cases) | **No** - and the real errors are shown. DynamoDB is excluded by this container's `SERVICES` allow-list; RDS is not in LocalStack community at all |

### Findings worth highlighting

Three things the labs proved that a pure write-up would have only asserted:

1. **An auto-assigned public IP is not yours.** Stopping and starting the instance returned
   `54.214.106.37` → `null` → `54.214.151.227` while the private IP stayed `10.238.38.230`
   throughout. That is the entire argument for Elastic IPs and load balancers, in one output.
2. **A `/24` subnet reports 251 usable addresses, not 256.** AWS reserves five per subnet, and
   `AvailableIpAddressCount: 251` shows it directly.
3. **Deleting a versioned S3 object destroys nothing.** `list-objects-v2` returned `null` while
   `list-object-versions` showed both data versions intact under a delete marker, and the original
   content came back with a `--version-id` read.

And one finding about the tooling itself: **LocalStack validates syntax, not authorisation.** A
bucket policy denying all non-TLS requests was accepted, stored, read back correctly - and then did
not block a plain-HTTP upload. An emulator can tell you a policy parses. It cannot tell you a policy
is correct.

## Environment

| Component | Version |
|---|---|
| Terraform | v1.16.4 (darwin_arm64) |
| AWS provider | hashicorp/aws v6.67.0, pinned by `.terraform.lock.hcl` |
| LocalStack | 3.8.1, community edition, container `localstack-main` on port 4566 |
| Services enabled | `s3`, `ec2`, `iam`, `sts` |
| AWS CLI | v2, pointed at `--endpoint-url=http://localhost:4566` |
| Credentials | `AWS_ACCESS_KEY_ID=test`, `AWS_SECRET_ACCESS_KEY=test`, `AWS_DEFAULT_REGION=us-east-1` |

Every resource created anywhere in this homework is prefixed `hw18-` so it can be identified and
cleaned up without touching concurrent work in the same container.

## What is committed and what is not

`.gitignore` at this level and inside `terraform-s3-demo/` exclude:

```text
.terraform/          provider binaries - hundreds of MB, rebuilt by `terraform init`
*.tfstate            state: secrets in plaintext, unmergeable, generated not authored
*.tfstate.backup     same
*.tfvars             environment-specific and often secret values
tfplan, *.tfplan     saved binary plans
```

Committed instead: all `*.tf` files, `terraform.tfvars.example` as the template, and
`.terraform.lock.hcl` so every checkout resolves the identical provider version.

## Cleanup

Everything created was destroyed. `terraform destroy` removed the Terraform-managed stack, and the
resources created directly with the AWS CLI for the research pages were deleted individually. The
verification below is real output, run after cleanup.

```bash
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
E="--endpoint-url=http://localhost:4566"
aws $E s3api list-buckets --query 'Buckets[?starts_with(Name, `hw18-`)].Name'
aws $E ec2 describe-instances --filters 'Name=tag:Name,Values=hw18-*' --query 'Reservations[].Instances[].[InstanceId,State.Name]'
aws $E ec2 describe-vpcs --filters 'Name=tag:Name,Values=hw18-*' --query 'Vpcs[].VpcId'
aws $E ec2 describe-security-groups --filters 'Name=group-name,Values=hw18-*' --query 'SecurityGroups[].GroupName'
aws $E ec2 describe-volumes --filters 'Name=tag:Name,Values=hw18-*' --query 'Volumes[].VolumeId'
aws $E ec2 describe-key-pairs --filters 'Name=key-name,Values=hw18-*' --query 'KeyPairs[].KeyName'
aws $E iam list-users  --query 'Users[?starts_with(UserName, `hw18-`)].UserName'
aws $E iam list-groups --query 'Groups[?starts_with(GroupName, `hw18-`)].GroupName'
aws $E iam list-roles  --query 'Roles[?starts_with(RoleName, `hw18-`)].RoleName'
aws $E iam list-policies --scope Local --query 'Policies[?starts_with(PolicyName, `hw18-`)].PolicyName'
```

See [CLEANUP-VERIFICATION](#cleanup-verification) below for the captured result.

## Cleanup verification

```text
===== S3 buckets named hw18-*
[]
===== all S3 buckets
[]
===== EC2 instances tagged hw18-*
[
    [
        "i-70bf2561a14791eef",
        "terminated"
    ]
]
===== VPCs tagged hw18-*
[]
===== security groups named hw18-*
[]
===== EBS volumes tagged hw18-*
[]
===== key pairs named hw18-*
[]
===== subnets tagged hw18-*
[]
===== route tables tagged hw18-*
[]
===== internet gateways tagged hw18-*
[]
===== NAT gateways tagged hw18-*
[
    [
        "nat-74596f845995c4a4d",
        "deleted"
    ]
]
===== network ACLs tagged hw18-*
[]
===== Elastic IPs (all)
[]
===== IAM users named hw18-*
[]
===== IAM groups named hw18-*
[]
===== IAM roles named hw18-*
[]
===== IAM customer managed policies named hw18-*
[]
```

Every list is empty. The two non-empty entries are **tombstones, not live resources**: a terminated
EC2 instance stays visible in `describe-instances` with `State: terminated` for a while (about an
hour on real AWS) before it disappears, and a deleted NAT gateway likewise shows `State: deleted`.
Neither consumes anything or costs anything. Both match real AWS behaviour.

Note also that `list-buckets` with no filter returns `[]` - not just no `hw18-` buckets, but no
buckets at all, so nothing was left behind under a different name either.

```bash
docker ps --filter name=localstack-main --format '{{.Names}} {{.Image}} {{.Status}}'
```

```text
localstack-main localstack/localstack:3.8 Up 49 minutes (healthy)
```


The LocalStack container `localstack-main` was deliberately left running - it is shared with other
work and must not be restarted.
