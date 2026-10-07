# Task 1 - Terraform S3 Demo

Create an S3 bucket with Terraform and walk the complete lifecycle: `init`, `fmt`, `validate`,
`plan`, `apply`, `show`, `output`, `destroy`.


## A deliberate exception: `terraform.tfvars` is committed here

The standard rule is **never commit `.tfvars`** — it is where environment-specific values and secrets
live, which is why the `.gitignore` carries `*.tfvars`.

This project commits it anyway, via an explicit negation:

```text
*.tfvars
!terraform.tfvars.example
!terraform.tfvars
```

Two reasons, both specific to this assignment:

1. The task lists `terraform.tfvars` as one of the six required files in the project layout, so a
   submission without it is incomplete.
2. This file holds no secrets. Every value in it is a LocalStack endpoint, a region, a bucket name
   and a boolean — nothing that would be sensitive even on real AWS.

On a real project you would delete that negation, keep only `terraform.tfvars.example` in version
control, and supply the real values through CI variables, a secrets manager, or a local file that
never leaves the machine. State files stay ignored here regardless — `terraform.tfstate` contains
resource attributes in plaintext and is never safe to commit.


## Read this first: this ran against LocalStack, not real AWS

There are no real AWS credentials on this machine and none were added. Every command below was run
against **LocalStack 3.8.1 (community edition)**, a local AWS API emulator listening on
`http://localhost:4566`. The bucket `hw18-terraform-s3-demo` existed inside that container and
nowhere else. **No resource was ever created in a real AWS account.**

The Terraform configuration itself is the same configuration you would use against real AWS. Only
the `provider "aws"` block differs, and only by the skip flags and the `endpoints` override.

What would be different on real AWS:

| | This lab (LocalStack) | Real AWS |
|---|---|---|
| ARN | `arn:aws:s3:::hw18-terraform-s3-demo` - locally generated, means nothing outside the container | A real ARN in a real 12-digit account, globally resolvable |
| Account id | Always `000000000000`; `skip_requesting_account_id` means Terraform never even asks | Your real account id, resolved through STS |
| Cost | Zero | S3 storage, requests and data transfer are billed |
| IAM | Not enforced. LocalStack community accepts the request whatever the policy says | Enforced on every call. A missing `s3:PutBucketVersioning` permission fails the apply |
| Bucket name uniqueness | Local to the container, so `hw18-terraform-s3-demo` is always free | Globally unique across every AWS customer. The same name would almost certainly collide |
| Consistency | Immediate | S3 is strongly consistent for object reads now, but bucket-level settings and IAM propagation are still eventually consistent, so a `plan` straight after an `apply` can briefly show drift |
| Deletion | Instant | `force_destroy` has to page through and delete every object and every version first, which on a large bucket takes a long time and can time out |

Everything else below - the HCL, the plan symbols, the state behaviour, the dependency graph - is
real Terraform behaviour and transfers unchanged.

## Files

| File | Purpose |
|---|---|
| `provider.tf` | `terraform {}` block (required version, required providers) and the `provider "aws"` block pointed at LocalStack |
| `variables.tf` | Input variables with types, descriptions, defaults and one validation rule |
| `main.tf` | The resources: bucket, versioning, encryption, public access block, bucket policy |
| `outputs.tf` | Values surfaced after apply |
| `terraform.tfvars` | The actual values for this run. **Not committed** - see below |
| `terraform.tfvars.example` | The committed template. Copy it to `terraform.tfvars` |
| `.gitignore` | Keeps `.terraform/`, state, plan files and `*.tfvars` out of git |

`terraform.tfvars` is in `.gitignore` because real tfvars files carry environment-specific and often
secret values. The example file is what gets committed. To run this lab:

```bash
cp terraform.tfvars.example terraform.tfvars
```

## Setup

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
curl -s http://localhost:4566/_localstack/health
```

```text
{"services": {"ec2": "running", "iam": "available", "s3": "running", "sts": "running", ...},
 "edition": "community", "version": "3.8.1"}
```

LocalStack is up and the four services this lab needs are live. The credentials are the literal
strings `test`/`test` - LocalStack accepts any non-empty pair and never checks them.

## The provider block

```hcl
provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key

  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    s3  = var.aws_endpoint_url
    sts = var.aws_endpoint_url
    iam = var.aws_endpoint_url
    ec2 = var.aws_endpoint_url
  }
}
```

Each flag earns its place:

- `skip_credentials_validation` - without it the provider calls `sts:GetCallerIdentity` against real
  AWS to check the keys. `test`/`test` would be rejected.
- `skip_metadata_api_check` - stops the provider trying to reach the EC2 instance metadata service
  at `169.254.169.254` looking for a role. On a laptop that just hangs until it times out.
- `skip_requesting_account_id` - stops it resolving the account id, which it uses when building ARNs.
- `s3_use_path_style` - forces `http://localhost:4566/bucket-name` instead of
  `http://bucket-name.localhost:4566`. Virtual-host style needs wildcard DNS, which localhost does
  not have.
- `endpoints {}` - redirects each service's API calls to LocalStack. Anything not listed here still
  goes to real AWS, which is why only the four enabled services are listed.

**Delete these five things and the exact same configuration deploys to real AWS.**

## 1. terraform init

```bash
terraform init
```

```text
Initializing the backend...

Initializing provider plugins...
- Reusing previous version of hashicorp/aws from the dependency lock file
- Using previously-installed hashicorp/aws v6.67.0

Terraform has been successfully initialized!

You may now begin working with Terraform. Try running "terraform plan" to see
any changes that are required for your infrastructure. All Terraform commands
should now work.
```

`init` does three jobs: it configures the backend (here the default local backend, so state is a
file in this directory), it downloads the provider plugins named in `required_providers` into
`.terraform/`, and it writes or verifies `.terraform.lock.hcl`.

The lock file is the important one. It pins the exact provider version and its checksums:

```bash
head -8 .terraform.lock.hcl
```

```text
# This file is maintained automatically by "terraform init".
# Manual edits may be lost in future updates.

provider "registry.terraform.io/hashicorp/aws" {
  version     = "6.67.0"
  constraints = "~> 6.0"
  hashes = [
    "h1:OgdIUAQDtJBxlKjoPgChD1w57vl6hm6PyJHiBYgsgQA=",
```

`constraints = "~> 6.0"` is what the config asked for, `version = "6.67.0"` is what was resolved.
The lock file **is** committed, so every teammate and every CI run gets byte-identical provider
binaries. `.terraform/` is **not** committed - it is a 600 MB cache that `init` rebuilds on demand.

## 2. terraform fmt - on a file that actually needs it

`main.tf` was deliberately written with sloppy indentation and unaligned `=` signs. `fmt -check`
reports what is wrong without touching anything, and `-diff` shows it:

```bash
terraform fmt -check -diff
```

```text
main.tf
--- old/main.tf
+++ new/main.tf
@@ -1,35 +1,35 @@
 resource "aws_s3_bucket" "demo" {
-    bucket = var.bucket_name
-  force_destroy    = true
+  bucket        = var.bucket_name
+  force_destroy = true
 
-      tags = {
-    Name = var.bucket_name
-        Environment = var.enviroment
-    ManagedBy = "Terraform"
-    Session = "18"
+  tags = {
+    Name        = var.bucket_name
+    Environment = var.enviroment
+    ManagedBy   = "Terraform"
+    Session     = "18"
   }
 }
 
 resource "aws_s3_bucket_versioning" "demo" {
   bucket = aws_s3_bucket.demo.id
-      versioning_configuration {
+  versioning_configuration {
     status = var.enable_versioning ? "Enabled" : "Suspended"
-      }
+  }
 }
 
 resource "aws_s3_bucket_server_side_encryption_configuration" "demo" {
   bucket = aws_s3_bucket.demo.id
   rule {
-        apply_server_side_encryption_by_default {
+    apply_server_side_encryption_by_default {
       sse_algorithm = "AES256"
     }
   }
 }
 
 resource "aws_s3_bucket_public_access_block" "demo" {
-  bucket = aws_s3_bucket.demo.id
-  block_public_acls   = true
-  block_public_policy       = true
-  ignore_public_acls = true
-    restrict_public_buckets = true
+  bucket                  = aws_s3_bucket.demo.id
+  block_public_acls       = true
+  block_public_policy     = true
+  ignore_public_acls      = true
+  restrict_public_buckets = true
 }
```

Now actually rewrite the file:

```bash
terraform fmt
```

```text
main.tf
```

It prints the name of every file it changed. Run it again and it prints nothing, because there is
nothing left to fix:

```bash
terraform fmt
```

```text
```

Three things worth noticing in that diff. `fmt` normalises every block to two-space indentation. It
vertically aligns the `=` of consecutive single-line arguments inside a block, which is why
`bucket`, `force_destroy` and the four `block_public_*` arguments all line up. And it did **not**
touch `var.enviroment` - `fmt` only reformats, it never changes meaning. That typo is still there,
and the next command finds it.

`terraform fmt -check` exits non-zero when a file needs reformatting, which is exactly what you want
as a CI gate.

## 3. terraform validate - catching a real error

```bash
terraform validate
```

```text
Error: Reference to undeclared input variable

  on main.tf line 7, in resource "aws_s3_bucket" "demo":
   7:     Environment = var.enviroment

An input variable with the name "enviroment" has not been declared. Did you
mean "environment"?
```

`validate` checks the configuration for internal consistency: syntax, argument names the provider
schema recognises, types, and references that resolve. Here `var.enviroment` is missing an `n`, and
no such variable is declared in `variables.tf`, so the reference does not resolve. Terraform even
guesses the intended name.

`validate` runs entirely offline. It never contacts AWS, never reads state, and costs nothing - that
is what makes it the right thing to run on every commit. It also means it cannot tell you that your
bucket name is already taken or that your IAM role lacks a permission. Those only surface at `apply`.

Fix the typo:

```bash
sed -i '' 's/var\.enviroment/var.environment/' main.tf
terraform validate
```

```text
Success! The configuration is valid.
```

### A second validation gate: the variable's own rule

`variables.tf` also carries a `validation` block:

```hcl
variable "bucket_name" {
  description = "Globally unique name of the S3 bucket."
  type        = string

  validation {
    condition     = can(regex("^hw18-", var.bucket_name))
    error_message = "Bucket name must start with hw18- so this lab never collides with other labs."
  }
}
```

`bucket_name` has no default, so Terraform would prompt for it if `terraform.tfvars` did not supply
it. The validation rule enforces the naming convention at plan time rather than leaving it to a code
review.

## 4. terraform plan

```bash
terraform plan -out=tfplan
```

```text
Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # aws_s3_bucket.demo will be created
  + resource "aws_s3_bucket" "demo" {
      + arn                         = (known after apply)
      + bucket                      = "hw18-terraform-s3-demo"
      + bucket_domain_name          = (known after apply)
      + force_destroy               = true
      + hosted_zone_id              = (known after apply)
      + id                          = (known after apply)
      + region                      = "us-east-1"
      + tags                        = {
          + "Environment" = "dev"
          + "ManagedBy"   = "Terraform"
          + "Name"        = "hw18-terraform-s3-demo"
          + "Session"     = "18"
        }
      ...
    }

  # aws_s3_bucket_public_access_block.demo will be created
  + resource "aws_s3_bucket_public_access_block" "demo" {
      + block_public_acls       = true
      + block_public_policy     = true
      + bucket                  = (known after apply)
      + id                      = (known after apply)
      + ignore_public_acls      = true
      + region                  = "us-east-1"
      + restrict_public_buckets = true
    }

  # aws_s3_bucket_server_side_encryption_configuration.demo will be created
  + resource "aws_s3_bucket_server_side_encryption_configuration" "demo" {
      + bucket = (known after apply)
      + id     = (known after apply)
      + region = "us-east-1"

      + rule {
          + bucket_key_enabled       = (known after apply)

          + apply_server_side_encryption_by_default {
              + kms_master_key_id = (known after apply)
              + sse_algorithm     = "AES256"
            }
        }
    }

  # aws_s3_bucket_versioning.demo will be created
  + resource "aws_s3_bucket_versioning" "demo" {
      + bucket = (known after apply)
      + id     = (known after apply)
      + region = "us-east-1"

      + versioning_configuration {
          + mfa_delete = (known after apply)
          + status     = "Enabled"
        }
    }

Plan: 4 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + bucket_arn           = (known after apply)
  + bucket_name          = "hw18-terraform-s3-demo"
  + bucket_region        = "us-east-1"
  + encryption_algorithm = "AES256"
  + versioning_status    = "Enabled"

Saved the plan to: tfplan

To perform exactly these actions, run the following command to apply:
    terraform apply "tfplan"
```

(This plan was captured before the `aws_s3_bucket_policy` resource in section 8 was added, which is
why it shows four resources and the shipped `main.tf` has five. The sections below follow the same
chronological order they were run in.)

A `plan` is a three-way comparison: **configuration** (what you wrote) against **state** (what
Terraform last recorded) against **the real world** (what the provider's refresh just read back).
The difference is the plan. It changes nothing.

`-out=tfplan` saves the plan to a binary file so the apply does **exactly** this and nothing else.
Without it, `apply` recomputes the plan from scratch, and anything that changed in between - another
engineer's apply, a console click - silently lands in the result. In CI, always plan to a file and
apply that file.

### The plan symbols, read off this plan

| Symbol | Meaning | Where it appears in this lab |
|---|---|---|
| `+` | **create** - the resource is in the config but not in state | Every resource in the plan above. Also at attribute level: `+ sse_algorithm = "AES256"` is an attribute being set on a new resource |
| `-` | **destroy** - the resource is in state but no longer in the config, or you ran `plan -destroy` | Section 10, where all five resources show `- resource ...` |
| `~` | **update in place** - the resource stays, one or more attributes change. The provider can do this with an API call that does not replace the resource | Section 8: `~ status = "Enabled" -> "Suspended"` on `aws_s3_bucket_versioning.demo` |
| `-/+` | **replace** - an attribute changed that the provider cannot update in place, so Terraform destroys the old resource and creates a new one. Always annotated `# forces replacement` | Section 7, renaming the bucket. S3 has no rename API, so the bucket has to be deleted and recreated |
| `+/-` | **create before destroy** - same as `-/+` but reversed, when the resource has `lifecycle { create_before_destroy = true }` | Not used in this lab |
| `<=` | **read** - a data source will be read during apply | Not used in this lab |

`(known after apply)` means Terraform cannot compute the value yet because AWS assigns it. `arn`,
`id` and `hosted_zone_id` only exist once the bucket exists. Note that
`aws_s3_bucket_versioning.demo` shows `bucket = (known after apply)` even though the bucket name is
a literal in the tfvars - that is because it references `aws_s3_bucket.demo.id`, and Terraform will
not assume the id equals the name.

### Implicit dependencies

Nothing in `main.tf` says "create the bucket first". Terraform works it out: the three configuration
resources all reference `aws_s3_bucket.demo.id`, which builds an edge in the dependency graph. That
is why the apply below creates the bucket, then the other three in parallel.

Use `depends_on` only when the dependency is real but invisible to Terraform - as in the bucket
policy in section 8, which must land after the public access block even though it never references it.

## 5. terraform apply

```bash
terraform apply tfplan
```

```text
aws_s3_bucket.demo: Creating...
aws_s3_bucket.demo: Creation complete after 0s [id=hw18-terraform-s3-demo]
aws_s3_bucket_public_access_block.demo: Creating...
aws_s3_bucket_versioning.demo: Creating...
aws_s3_bucket_server_side_encryption_configuration.demo: Creating...
aws_s3_bucket_public_access_block.demo: Creation complete after 0s [id=hw18-terraform-s3-demo]
aws_s3_bucket_server_side_encryption_configuration.demo: Creation complete after 0s [id=hw18-terraform-s3-demo]
aws_s3_bucket_versioning.demo: Creation complete after 1s [id=hw18-terraform-s3-demo]

Apply complete! Resources: 4 added, 0 changed, 0 destroyed.

Outputs:

bucket_arn = "arn:aws:s3:::hw18-terraform-s3-demo"
bucket_name = "hw18-terraform-s3-demo"
bucket_region = "us-east-1"
encryption_algorithm = "AES256"
versioning_status = "Enabled"
```

The bucket goes first and completes before the other three even start - the dependency graph in
action. The three dependants then run concurrently (Terraform's default parallelism is 10).

Applying a saved plan file does not re-prompt for approval, because the approval already happened
when you reviewed the plan. `terraform apply` with no plan file prompts `Enter a value: yes`;
`-auto-approve` skips it and belongs in CI, not in a terminal pointed at production.

### Verify independently, outside Terraform

Terraform saying it worked is not the same as it having worked. Check with the AWS CLI:

```bash
aws --endpoint-url=http://localhost:4566 s3api list-buckets --query 'Buckets[].Name' --output table
aws --endpoint-url=http://localhost:4566 s3api get-bucket-versioning --bucket hw18-terraform-s3-demo
aws --endpoint-url=http://localhost:4566 s3api get-bucket-encryption --bucket hw18-terraform-s3-demo
aws --endpoint-url=http://localhost:4566 s3api get-public-access-block --bucket hw18-terraform-s3-demo
```

```text
----------------------------
|        ListBuckets       |
+--------------------------+
|  hw18-terraform-s3-demo  |
+--------------------------+
{
    "Status": "Enabled"
}
{
    "ServerSideEncryptionConfiguration": {
        "Rules": [
            {
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                },
                "BucketKeyEnabled": false
            }
        ]
    }
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

The bucket exists, versioning is on, AES256 default encryption is set and all four public access
blocks are true. Exactly what the configuration asked for. On real AWS these are the same four
commands - only `--endpoint-url` comes off.

## 6. terraform show, state list and output

### What is in state

```bash
terraform state list
```

```text
aws_s3_bucket.demo
aws_s3_bucket_public_access_block.demo
aws_s3_bucket_server_side_encryption_configuration.demo
aws_s3_bucket_versioning.demo
```

Four addresses, one per managed resource. These addresses are what you pass to `terraform state show`,
`terraform taint`, `terraform state rm` and `-target`.

### Full state, human readable

```bash
terraform show
```

```text
# aws_s3_bucket.demo:
resource "aws_s3_bucket" "demo" {
    acceleration_status         = null
    arn                         = "arn:aws:s3:::hw18-terraform-s3-demo"
    bucket                      = "hw18-terraform-s3-demo"
    bucket_domain_name          = "hw18-terraform-s3-demo.s3.amazonaws.com"
    bucket_namespace            = "global"
    bucket_prefix               = null
    bucket_region               = "us-east-1"
    bucket_regional_domain_name = "hw18-terraform-s3-demo.s3.us-east-1.amazonaws.com"
    force_destroy               = true
    hosted_zone_id              = "Z3AQBSTGFYJSTF"
    id                          = "hw18-terraform-s3-demo"
    object_lock_enabled         = false
    policy                      = null
    region                      = "us-east-1"
    request_payer               = "BucketOwner"
    tags                        = {
        "Environment" = "dev"
        "ManagedBy"   = "Terraform"
        "Name"        = "hw18-terraform-s3-demo"
        "Session"     = "18"
    }
    tags_all                    = {
        "Environment" = "dev"
        "ManagedBy"   = "Terraform"
        "Name"        = "hw18-terraform-s3-demo"
        "Session"     = "18"
    }

    grant {
        id          = "75aa57f09aa0c8caeab4f8c24e99d10f8e7faeebf76c078efc7c6caea54ba06a"
        permissions = [
            "FULL_CONTROL",
        ]
        type        = "CanonicalUser"
        uri         = null
    }

    server_side_encryption_configuration {
        rule {
            bucket_key_enabled = false

            apply_server_side_encryption_by_default {
                kms_master_key_id = null
                sse_algorithm     = "AES256"
            }
        }
    }

    versioning {
        enabled    = false
        mfa_delete = false
    }
}
```

Every attribute, including ones never written in the config - `hosted_zone_id`, `tags_all`, the
owner `grant`. These came back from the API and Terraform recorded them.

One honest oddity: the nested `versioning { enabled = false }` block reads false while versioning is
demonstrably Enabled. That block is the **deprecated** inline attribute on `aws_s3_bucket`, populated
once at create time before the separate `aws_s3_bucket_versioning` resource ran. The authoritative
value lives on the dedicated resource:

```bash
terraform state show aws_s3_bucket_versioning.demo
```

```text
# aws_s3_bucket_versioning.demo:
resource "aws_s3_bucket_versioning" "demo" {
    bucket                = "hw18-terraform-s3-demo"
    expected_bucket_owner = null
    id                    = "hw18-terraform-s3-demo"
    region                = "us-east-1"

    versioning_configuration {
        mfa_delete = "Disabled"
        status     = "Enabled"
    }
}
```

This is the general lesson for the AWS provider v4 and later: bucket settings moved out of
`aws_s3_bucket` into their own resources. Never configure the same setting in both places.

### Outputs

```bash
terraform output
```

```text
bucket_arn = "arn:aws:s3:::hw18-terraform-s3-demo"
bucket_name = "hw18-terraform-s3-demo"
bucket_region = "us-east-1"
encryption_algorithm = "AES256"
versioning_status = "Enabled"
```

```bash
terraform output -raw bucket_arn
```

```text
arn:aws:s3:::hw18-terraform-s3-demo
```

```bash
terraform output -json
```

```text
{
  "bucket_arn": {
    "sensitive": false,
    "type": "string",
    "value": "arn:aws:s3:::hw18-terraform-s3-demo"
  },
  "bucket_name": {
    "sensitive": false,
    "type": "string",
    "value": "hw18-terraform-s3-demo"
  },
  "bucket_region": {
    "sensitive": false,
    "type": "string",
    "value": "us-east-1"
  },
  "encryption_algorithm": {
    "sensitive": false,
    "type": "string",
    "value": "AES256"
  },
  "versioning_status": {
    "sensitive": false,
    "type": "string",
    "value": "Enabled"
  }
}
```

Three forms, three jobs. Bare `terraform output` is for humans. `-raw` emits the value with no quotes
and no newline, so it drops straight into a shell variable:
`BUCKET=$(terraform output -raw bucket_name)`. `-json` is for machines - a pipeline step, another
tool, or a wrapper script.

Outputs are also the public interface of a module. When this directory becomes a module consumed by
another configuration, the outputs are the only values the caller can read.

### Why state exists, and why it must never be committed

```bash
head -20 terraform.tfstate
```

```text
{
  "version": 4,
  "terraform_version": "1.16.4",
  "serial": 10,
  "lineage": "9b9f5e63-4bca-5e97-6a4e-9f77423a8879",
  "outputs": {
    "bucket_arn": {
      "value": "arn:aws:s3:::hw18-terraform-s3-demo",
      "type": "string"
    },
    "bucket_name": {
      "value": "hw18-terraform-s3-demo",
      "type": "string"
    },
    "bucket_region": {
      "value": "us-east-1",
      "type": "string"
    },
    "encryption_algorithm": {
      "value": "AES256",
```

State is the map from the names in your configuration to the real objects in the provider. Without
it Terraform has no idea that `aws_s3_bucket.demo` *is* the bucket called `hw18-terraform-s3-demo` -
it would try to create it again. State is also how Terraform knows a resource you deleted from the
config used to exist, which is the only way it can decide to destroy it. And it caches attributes so
`plan` does not have to re-read everything on every run.

`serial` increments on every write (10 here, after five applies and refreshes). `lineage` identifies
this state's ancestry, so Terraform can refuse to overwrite one state file with an unrelated one.

Why it is never committed:

1. **Secrets in plaintext.** State stores every attribute the provider returns, including ones
   marked `sensitive` in the configuration. An RDS `password`, a generated IAM secret key, a
   private key from `tls_private_key` - all sit in the JSON in clear text. Marking an output
   `sensitive` only hides it from the terminal, not from the file.
2. **Concurrency.** Two engineers applying from two git checkouts produce two divergent state files
   and git has no way to merge them. Remote backends (S3 with DynamoDB locking, Terraform Cloud,
   GCS) solve this with a lock. A git repository cannot.
3. **It is generated, not authored.** It is the output of applies, not the input. Committing it
   produces merge conflicts in JSON nobody can resolve by hand.

Proof it is ignored here:

```bash
git check-ignore -v terraform.tfstate terraform.tfvars tfplan .terraform/providers terraform.tfvars.example
```

```text
coursework-labs/18-terraform-iac/terraform-s3-demo/.gitignore:2:*.tfstate	terraform.tfstate
coursework-labs/18-terraform-iac/terraform-s3-demo/.gitignore:9:*.tfvars	terraform.tfvars
coursework-labs/18-terraform-iac/terraform-s3-demo/.gitignore:6:tfplan	tfplan
coursework-labs/18-terraform-iac/terraform-s3-demo/.gitignore:1:.terraform/	.terraform/providers
coursework-labs/18-terraform-iac/terraform-s3-demo/.gitignore:10:!terraform.tfvars.example	terraform.tfvars.example
```

Each line names the `.gitignore` rule that matched. The last line is the negation `!terraform.tfvars.example`,
so the example file is tracked while every other `*.tfvars` is ignored.

**Committed:** `*.tf`, `terraform.tfvars.example`, `.terraform.lock.hcl`, `README.md`.
**Never committed:** `.terraform/`, `*.tfstate`, `*.tfstate.backup`, `*.tfvars`, `tfplan`.

## 7. The `-/+` symbol: renaming the bucket forces replacement

Run a plan with a different bucket name, without applying it:

```bash
terraform plan -var='bucket_name=hw18-renamed-demo'
```

```text
Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
-/+ destroy and then create replacement

Terraform will perform the following actions:

  # aws_s3_bucket.demo must be replaced
-/+ resource "aws_s3_bucket" "demo" {
      + acceleration_status         = (known after apply)
      + acl                         = (known after apply)
      ~ arn                         = "arn:aws:s3:::hw18-terraform-s3-demo" -> (known after apply)
      ~ bucket                      = "hw18-terraform-s3-demo" -> "hw18-renamed-demo" # forces replacement
      ~ bucket_domain_name          = "hw18-terraform-s3-demo.s3.amazonaws.com" -> (known after apply)
      ~ bucket_namespace            = "global" -> (known after apply)
      + bucket_prefix               = (known after apply)
      ~ bucket_region               = "us-east-1" -> (known after apply)
      ~ bucket_regional_domain_name = "hw18-terraform-s3-demo.s3.us-east-1.amazonaws.com" -> (known after apply)
      ~ hosted_zone_id              = "Z3AQBSTGFYJSTF" -> (known after apply)
      ~ id                          = "hw18-terraform-s3-demo" -> (known after apply)
      ...
    }

  # aws_s3_bucket_public_access_block.demo must be replaced
      ~ bucket                  = "hw18-terraform-s3-demo" -> (known after apply) # forces replacement

  # aws_s3_bucket_server_side_encryption_configuration.demo must be replaced
      ~ bucket                = "hw18-terraform-s3-demo" -> (known after apply) # forces replacement

  # aws_s3_bucket_versioning.demo must be replaced
      ~ bucket                = "hw18-terraform-s3-demo" -> (known after apply) # forces replacement

Plan: 4 to add, 0 to change, 4 to destroy.
```

This is the most dangerous plan output there is, and it is why you read plans.

`bucket` is a **force-new** attribute: S3 has no rename API, so changing it means delete and
recreate. The annotation `# forces replacement` is on exactly the one attribute responsible.
Everything else marked `~` is just a consequence - new bucket, new ARN, new id.

Worse, the replacement cascades. All three dependent resources reference
`aws_s3_bucket.demo.id`, which becomes `(known after apply)`, so they must be replaced too.
**One renamed string replaces the entire stack, and on real AWS that deletes every object in the
bucket.**

`Plan: 4 to add, 0 to change, 4 to destroy` is the summary. 4+4, not 4 changed - a replacement counts
in both columns. This plan was **not** applied.

## 8. The `~` symbol: versioning, and adding a bucket policy

Two changes at once. Add a bucket policy resource to `main.tf`:

```hcl
resource "aws_s3_bucket_policy" "demo" {
  bucket = aws_s3_bucket.demo.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyUnencryptedTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.demo.arn,
          "${aws_s3_bucket.demo.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.demo]
}
```

and flip one line in `terraform.tfvars`:

```hcl
enable_versioning = false
```

```bash
terraform plan -out=tfplan2
```

```text
Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create
  ~ update in-place

Terraform will perform the following actions:

  # aws_s3_bucket_policy.demo will be created
  + resource "aws_s3_bucket_policy" "demo" {
      + bucket = "hw18-terraform-s3-demo"
      + id     = (known after apply)
      + policy = jsonencode(
            {
              + Statement = [
                  + {
                      + Action    = "s3:*"
                      + Condition = {
                          + Bool = {
                              + "aws:SecureTransport" = "false"
                            }
                        }
                      + Effect    = "Deny"
                      + Principal = "*"
                      + Resource  = [
                          + "arn:aws:s3:::hw18-terraform-s3-demo",
                          + "arn:aws:s3:::hw18-terraform-s3-demo/*",
                        ]
                      + Sid       = "DenyUnencryptedTransport"
                    },
                ]
              + Version   = "2012-10-17"
            }
        )
      + region = "us-east-1"
    }

  # aws_s3_bucket_versioning.demo will be updated in-place
  ~ resource "aws_s3_bucket_versioning" "demo" {
        id                    = "hw18-terraform-s3-demo"
        # (3 unchanged attributes hidden)

      ~ versioning_configuration {
          ~ status     = "Enabled" -> "Suspended"
            # (1 unchanged attribute hidden)
        }
    }

Plan: 1 to add, 1 to change, 0 to destroy.

Changes to Outputs:
  ~ versioning_status    = "Enabled" -> "Suspended"
```

Both interesting symbols in one plan. `+` on the new policy; `~` on versioning, and critically the
`~` is in-place - `PutBucketVersioning` is an API call that modifies the existing bucket, so nothing
is destroyed.

`jsonencode` renders expanded with per-field `+` markers, so a policy diff is reviewable line by
line. This matters: policy changes are where security regressions hide, and a plan that showed only
`policy = (sensitive value)` would be useless in review.

`# (3 unchanged attributes hidden)` - Terraform hides what did not change so the diff stays readable.
`-no-color` plus `terraform show -json tfplan2` gives you the full machine-readable version when a
policy tool needs it.

`depends_on` is needed here because `block_public_policy = true` on the public access block makes
S3 reject a policy that it judges public. Terraform cannot see that relationship from the
references, so it is declared explicitly. The policy itself is a Deny, not public, but the ordering
still has to be deterministic.

```bash
terraform apply tfplan2
```

```text
aws_s3_bucket_policy.demo: Creating...
aws_s3_bucket_versioning.demo: Modifying... [id=hw18-terraform-s3-demo]
aws_s3_bucket_policy.demo: Creation complete after 0s [id=hw18-terraform-s3-demo]
aws_s3_bucket_versioning.demo: Modifications complete after 2s [id=hw18-terraform-s3-demo]

Apply complete! Resources: 1 added, 1 changed, 0 destroyed.

Outputs:

bucket_arn = "arn:aws:s3:::hw18-terraform-s3-demo"
bucket_name = "hw18-terraform-s3-demo"
bucket_region = "us-east-1"
encryption_algorithm = "AES256"
versioning_status = "Suspended"
```

`Modifying...` not `Destroying...` - the bucket was never touched. State now holds five resources:

```bash
terraform state list
```

```text
aws_s3_bucket.demo
aws_s3_bucket_policy.demo
aws_s3_bucket_public_access_block.demo
aws_s3_bucket_server_side_encryption_configuration.demo
aws_s3_bucket_versioning.demo
```

## 9. Drift: what happens when someone changes things outside Terraform

Re-enable versioning behind Terraform's back, the way a colleague clicking in the console would:

```bash
aws --endpoint-url=http://localhost:4566 s3api put-bucket-versioning \
  --bucket hw18-terraform-s3-demo --versioning-configuration Status=Enabled
aws --endpoint-url=http://localhost:4566 s3api get-bucket-versioning --bucket hw18-terraform-s3-demo
```

```text
{
    "Status": "Enabled"
}
```

Now plan:

```bash
terraform plan
```

```text
aws_s3_bucket.demo: Refreshing state... [id=hw18-terraform-s3-demo]
aws_s3_bucket_versioning.demo: Refreshing state... [id=hw18-terraform-s3-demo]
aws_s3_bucket_public_access_block.demo: Refreshing state... [id=hw18-terraform-s3-demo]
aws_s3_bucket_server_side_encryption_configuration.demo: Refreshing state... [id=hw18-terraform-s3-demo]
aws_s3_bucket_policy.demo: Refreshing state... [id=hw18-terraform-s3-demo]

Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  ~ update in-place

Terraform will perform the following actions:

  # aws_s3_bucket_versioning.demo will be updated in-place
  ~ resource "aws_s3_bucket_versioning" "demo" {
        id                    = "hw18-terraform-s3-demo"
        # (3 unchanged attributes hidden)

      ~ versioning_configuration {
          ~ status     = "Enabled" -> "Suspended"
            # (1 unchanged attribute hidden)
        }
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

Nothing in the configuration changed, but the plan is not empty. Those `Refreshing state...` lines
are the provider re-reading the real world; the `status` it found is `Enabled`, the configuration
says `Suspended`, so Terraform proposes to put it back.

This is the whole point of declarative infrastructure. The config is the source of truth and
Terraform continuously pulls reality back toward it. The practical consequence is that
`terraform plan` in CI on a schedule is a drift detector, and a non-empty plan on an unchanged
branch means somebody edited infrastructure by hand.

```bash
terraform apply -auto-approve
```

```text
aws_s3_bucket_versioning.demo: Modifying... [id=hw18-terraform-s3-demo]
aws_s3_bucket_versioning.demo: Modifications complete after 1s [id=hw18-terraform-s3-demo]

Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

## 10. terraform destroy

First put an object in the bucket, so `force_destroy` has something to do:

```bash
aws --endpoint-url=http://localhost:4566 s3 cp hello.txt s3://hw18-terraform-s3-demo/hello.txt
aws --endpoint-url=http://localhost:4566 s3 ls s3://hw18-terraform-s3-demo/
```

```text
upload: ./hello.txt to s3://hw18-terraform-s3-demo/hello.txt
2026-10-07 18:03:18         25 hello.txt
```

Always dry-run the destroy before running it:

```bash
terraform plan -destroy
```

```text
Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  - destroy

Terraform will perform the following actions:

  # aws_s3_bucket.demo will be destroyed
  - resource "aws_s3_bucket" "demo" {
      - arn                         = "arn:aws:s3:::hw18-terraform-s3-demo" -> null
      - bucket                      = "hw18-terraform-s3-demo" -> null
      - bucket_domain_name          = "hw18-terraform-s3-demo.s3.amazonaws.com" -> null
      - bucket_namespace            = "global" -> null
      - bucket_region               = "us-east-1" -> null
      - bucket_regional_domain_name = "hw18-terraform-s3-demo.s3.us-east-1.amazonaws.com" -> null
      - force_destroy               = true -> null
      - hosted_zone_id              = "Z3AQBSTGFYJSTF" -> null
      - id                          = "hw18-terraform-s3-demo" -> null
      - object_lock_enabled         = false -> null
      ...
    }

  # aws_s3_bucket_policy.demo will be destroyed
  # aws_s3_bucket_public_access_block.demo will be destroyed
  # aws_s3_bucket_server_side_encryption_configuration.demo will be destroyed
  # aws_s3_bucket_versioning.demo will be destroyed

Plan: 0 to add, 0 to change, 5 to destroy.

Changes to Outputs:
  - bucket_arn           = "arn:aws:s3:::hw18-terraform-s3-demo" -> null
  - bucket_region        = "us-east-1" -> null
  - encryption_algorithm = "AES256" -> null
  - versioning_status    = "Suspended" -> null
```

`-` on everything, every attribute going `-> null`. **Read this list before typing yes.** `plan
-destroy` is a dry run; `destroy` is not. The habit that saves production is: run `plan -destroy`,
read the resource names out loud, confirm every one is something you meant to delete.

```bash
terraform destroy -auto-approve
```

```text
aws_s3_bucket_versioning.demo: Destroying... [id=hw18-terraform-s3-demo]
aws_s3_bucket_server_side_encryption_configuration.demo: Destroying... [id=hw18-terraform-s3-demo]
aws_s3_bucket_policy.demo: Destroying... [id=hw18-terraform-s3-demo]
aws_s3_bucket_versioning.demo: Destruction complete after 0s
aws_s3_bucket_server_side_encryption_configuration.demo: Destruction complete after 0s
aws_s3_bucket_policy.demo: Destruction complete after 0s
aws_s3_bucket_public_access_block.demo: Destroying... [id=hw18-terraform-s3-demo]
aws_s3_bucket_public_access_block.demo: Destruction complete after 0s
aws_s3_bucket.demo: Destroying... [id=hw18-terraform-s3-demo]
aws_s3_bucket.demo: Destruction complete after 0s

Destroy complete! Resources: 5 destroyed.
```

Destroy walks the dependency graph **backwards**: the four dependants go first, the bucket last.
Creating in dependency order and deleting in reverse dependency order is what stops Terraform
trying to delete a bucket that still has a policy attached.

`force_destroy = true` is what let the bucket go while `hello.txt` was still in it. By default S3
refuses to delete a non-empty bucket and the apply fails with `BucketNotEmpty`. `force_destroy` is
fine for a lab and genuinely dangerous in production - it is a single line that makes
`terraform destroy` able to delete every object you have.

### State is empty

```bash
terraform state list
```

```text
```

No output at all. State has no managed resources left.

```bash
terraform output
```

```text
Warning: No outputs found

The state file either has no outputs defined, or all the defined outputs are
empty. Please define an output in your configuration with the `output`
keyword and run `terraform refresh` for it to become available.
```

Outputs are stored in state, so when state empties the outputs go with it. `outputs.tf` still
declares five of them - there is just nothing to populate them from.

### The bucket is actually gone

```bash
aws --endpoint-url=http://localhost:4566 s3api list-buckets
aws --endpoint-url=http://localhost:4566 s3api head-bucket --bucket hw18-terraform-s3-demo
```

```text
{
    "Buckets": [],
    "Owner": {
        "DisplayName": "webfile",
        "ID": "75aa57f09aa0c8caeab4f8c24e99d10f8e7faeebf76c078efc7c6caea54ba06a"
    },
    "Prefix": null
}

aws: [ERROR]: An error occurred (404) when calling the HeadBucket operation: Not Found
```

Zero buckets, and `head-bucket` returns 404. Verified outside Terraform, which is the only
verification that counts.

## Command summary

| Command | Contacts AWS? | Changes infrastructure? | Changes state? |
|---|---|---|---|
| `terraform init` | Registry only, for provider download | No | No |
| `terraform fmt` | No | No | No |
| `terraform validate` | No | No | No |
| `terraform plan` | Yes - reads for refresh | No | No (unless `-refresh-only` is applied) |
| `terraform apply` | Yes - reads and writes | **Yes** | Yes |
| `terraform show` | No - reads state | No | No |
| `terraform output` | No - reads state | No | No |
| `terraform state list` | No - reads state | No | No |
| `terraform destroy` | Yes - reads and deletes | **Yes** | Yes |

## What I would do differently on real AWS

- **Remote backend.** The local state file is fine for one person on a laptop. Any team needs an S3
  backend with DynamoDB state locking, or Terraform Cloud.
- **Drop `force_destroy`.** On a production bucket, leave it unset so a careless destroy fails
  loudly instead of deleting data.
- **Add a unique suffix.** Bucket names are globally unique across all of AWS, so a fixed name like
  `hw18-terraform-s3-demo` would collide. Use `bucket_prefix` and let AWS append entropy, or a
  `random_id` resource.
- **Encrypt with KMS.** `AES256` is S3-managed SSE-S3. Production usually wants `aws:kms` with a
  customer-managed key, which gives you a key policy, rotation and an audit trail per decrypt.
- **Add lifecycle rules.** With versioning on, non-current versions accumulate forever and get
  billed forever. An `aws_s3_bucket_lifecycle_configuration` expiring non-current versions is
  essentially mandatory.
- **CI gating.** `fmt -check`, `validate`, `tflint` and a policy scanner on every pull request;
  `plan` posted as a PR comment; `apply` only after a human approves.

## Practice questions

1. What are the three inputs `terraform plan` compares, and which one does `plan` ever change?
2. You see `-/+` with `# forces replacement` on a production RDS instance. What do you do before
   typing `yes`?
3. Why does `terraform validate` pass on a configuration that then fails during `apply`? Give two
   concrete causes.
4. State is in `.gitignore`. So how do two engineers on the same team apply the same configuration
   without overwriting each other?
5. `terraform plan` on an untouched branch returns `1 to change`. What happened, and how do you find
   out who did it?
6. What is the difference between marking an output `sensitive = true` and keeping the value out of
   state entirely?
