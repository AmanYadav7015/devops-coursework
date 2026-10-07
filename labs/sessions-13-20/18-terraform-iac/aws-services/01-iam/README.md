# 01 - IAM (Identity and Access Management)

## This ran against LocalStack, not real AWS

Every command below was executed against **LocalStack 3.8.1 (community edition)** on
`http://localhost:4566`. There are no real AWS credentials on this machine. The users, groups,
policies and roles shown here existed only inside that container and were deleted at the end.

The single most important difference for this page: **LocalStack community does not evaluate IAM
policies.** It stores them and hands them back, but it does not enforce them. Every request
succeeds regardless of what the policy says, because the whole point of the emulator is to let you
develop without credentials. On real AWS the policy is the only thing standing between a caller and
your data, and a missing permission produces `AccessDenied`. So treat the policy documents here as
*syntax and structure* demos, not as proof the rules work.

Other differences from real AWS: the account id is always `000000000000`, ARNs are locally
generated, `iam:SimulatePrincipalPolicy` is not implemented (shown below), there is no Access
Analyzer, no credential report, no MFA, and no IAM propagation delay - on real AWS a new role can
take a few seconds to become usable.

## What is IAM

IAM answers one question on every single AWS API call: **is this principal allowed to perform this
action on this resource, under these conditions?**

It is global - not regional. A user created in `us-east-1` is the same user in `eu-west-1`. It is
also free, which means there is never a cost argument for cutting corners on it.

Every request to AWS goes through the same evaluation:

```text
Request: principal + action + resource + context
            |
            v
  1. Is there an explicit Deny anywhere?  -> DENY. Nothing overrides this.
            |  no
            v
  2. Is there an explicit Allow?          -> ALLOW
            |  no
            v
  3. Default                              -> DENY
```

Two rules fall out of this and they explain almost all IAM behaviour:

- **Implicit deny by default.** A brand new user can do nothing at all.
- **Explicit deny always wins.** No Allow anywhere - not an identity policy, not a resource policy,
  not an admin policy - can override an explicit Deny.

The identity is confirmed by `sts:GetCallerIdentity`, which is the "who am I" of AWS:

```bash
aws --endpoint-url=http://localhost:4566 sts get-caller-identity
```

```text
{
    "UserId": "AKIAIOSFODNN7EXAMPLE",
    "Account": "000000000000",
    "Arn": "arn:aws:iam::000000000000:root"
}
```

The `000000000000` account id is the LocalStack giveaway - a real account has 12 real digits. Note
also that this is the **root** identity. On real AWS you should never be seeing that ARN from a
terminal.

## Users

An IAM user is a long-lived identity for a human or, historically, an application. It can have a
console password and/or up to two access key pairs.

```bash
aws --endpoint-url=http://localhost:4566 iam create-user --user-name hw18-analyst
```

```text
{
    "User": {
        "Path": "/",
        "UserName": "hw18-analyst",
        "UserId": "rs3l0etelyr1q8l3zn49",
        "Arn": "arn:aws:iam::000000000000:user/hw18-analyst",
        "CreateDate": "2026-10-07T12:38:05.910000+00:00"
    }
}
```

The user is created with **zero permissions**. It cannot even list its own details. Everything it
can do has to be granted explicitly.

The ARN is the user's unique address and is what you reference from policies:
`arn:aws:iam::<account>:user/<name>`. `Path` is an optional organisational prefix like
`/engineering/` that most teams never use.

Modern practice is to create as few users as possible:

- Humans should sign in through **IAM Identity Center** (formerly AWS SSO) or federation from your
  existing identity provider, so there is one place to offboard someone.
- Applications on EC2, ECS, Lambda or EKS should use **roles**, never a user's access keys.
- GitHub Actions and other CI should use **OIDC federation** into a role, not a stored access key.

The remaining legitimate use for an IAM user is something outside AWS that genuinely cannot assume
a role.

## Groups

A group is a container for users. You attach policies to the group; every member inherits them.

```bash
aws --endpoint-url=http://localhost:4566 iam create-group --group-name hw18-analysts
aws --endpoint-url=http://localhost:4566 iam add-user-to-group \
  --user-name hw18-analyst --group-name hw18-analysts
aws --endpoint-url=http://localhost:4566 iam list-groups-for-user --user-name hw18-analyst
```

```text
{
    "Group": {
        "Path": "/",
        "GroupName": "hw18-analysts",
        "GroupId": "mhmcbmfjuio2qrjmiiz3",
        "Arn": "arn:aws:iam::000000000000:group/hw18-analysts",
        "CreateDate": "2026-10-07T12:38:06.291000+00:00"
    }
}
{
    "Groups": [
        {
            "Path": "/",
            "GroupName": "hw18-analysts",
            "GroupId": "mhmcbmfjuio2qrjmiiz3",
            "Arn": "arn:aws:iam::000000000000:group/hw18-analysts",
            "CreateDate": "2026-10-07T12:38:06.291000+00:00"
        }
    ]
}
```

`add-user-to-group` prints nothing on success, which is the AWS CLI convention for an operation
that returns no body. `list-groups-for-user` is how you confirm it.

Three facts people get wrong about groups:

- A group is **not** a principal. You cannot write `"Principal": {"AWS": "arn:...:group/x"}` in a
  resource policy. Only users and roles are principals.
- Groups cannot be nested. There is no group-of-groups.
- A user can belong to at most 10 groups, and permissions from all of them are unioned.

## Policies

A policy is a JSON document that grants or denies permissions. Three kinds matter day to day:

| Kind | Where it lives | When to use |
|---|---|---|
| **AWS managed** | Maintained by AWS, e.g. `arn:aws:iam::aws:policy/ReadOnlyAccess` | Quick start, but almost always broader than you need |
| **Customer managed** | Your account, reusable, versioned | The default choice. Write it once, attach it to many identities |
| **Inline** | Embedded in one user, group or role, dies with it | Only when the permission genuinely must never be reused |

```bash
cat hw18-ro-policy.json
```

```text
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOnlyOneBucket",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::hw18-reports", "arn:aws:s3:::hw18-reports/*"]
    }
  ]
}
```

```bash
aws --endpoint-url=http://localhost:4566 iam create-policy \
  --policy-name hw18-reports-readonly \
  --policy-document file://hw18-ro-policy.json
```

```text
{
    "Policy": {
        "PolicyName": "hw18-reports-readonly",
        "PolicyId": "A8Z1JDDNS989IASFNIFKM",
        "Arn": "arn:aws:iam::000000000000:policy/hw18-reports-readonly",
        "Path": "/",
        "DefaultVersionId": "v1",
        "AttachmentCount": 0,
        "CreateDate": "2026-10-07T12:38:07.039000+00:00",
        "UpdateDate": "2026-10-07T12:38:07.039000+00:00"
    }
}
```

`DefaultVersionId: v1` is worth noticing. Customer managed policies are **versioned**: you can keep
up to five versions and roll back to a previous one with `set-default-policy-version`. That is a
real advantage over inline policies, which have no history at all. `AttachmentCount: 0` tells you
nobody is using it yet - a useful audit signal for finding dead policies.

### Reading the policy elements

| Element | Meaning | Note |
|---|---|---|
| `Version` | Policy language version | Always `"2012-10-17"`. `"2008-10-17"` disables variables and should never be used |
| `Sid` | Statement id | Free text label. Must be unique within the policy |
| `Effect` | `Allow` or `Deny` | Deny beats Allow, always |
| `Action` | The API calls | `s3:GetObject`, or wildcards like `s3:Get*` |
| `Resource` | The ARNs the actions apply to | `*` here means "every resource", which is where over-permissioning starts |
| `Principal` | Who | **Only in resource policies and trust policies.** Identity policies have no `Principal` - the identity it is attached to *is* the principal |
| `Condition` | Extra constraints | `aws:SourceIp`, `aws:MultiFactorAuthPresent`, `s3:prefix`, `aws:PrincipalTag/...` |

The two S3 ARNs in `Resource` are not a typo and this catches everyone:
`arn:aws:s3:::hw18-reports` is the **bucket** and is what `s3:ListBucket` acts on;
`arn:aws:s3:::hw18-reports/*` is the **objects** and is what `s3:GetObject` acts on. Omit the first
and the user can read a file whose name they already know but cannot list the bucket. Omit the
second and they can see the file names but not open any of them.

Attach it to the group so every analyst inherits it:

```bash
aws --endpoint-url=http://localhost:4566 iam attach-group-policy \
  --group-name hw18-analysts \
  --policy-arn arn:aws:iam::000000000000:policy/hw18-reports-readonly
aws --endpoint-url=http://localhost:4566 iam list-attached-group-policies --group-name hw18-analysts
```

```text
{
    "AttachedPolicies": [
        {
            "PolicyName": "hw18-reports-readonly",
            "PolicyArn": "arn:aws:iam::000000000000:policy/hw18-reports-readonly"
        }
    ]
}
```

And read the document back from the policy version:

```bash
aws --endpoint-url=http://localhost:4566 iam get-policy-version \
  --policy-arn arn:aws:iam::000000000000:policy/hw18-reports-readonly --version-id v1
```

```text
{
    "PolicyVersion": {
        "Document": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "ReadOnlyOneBucket",
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:ListBucket"
                    ],
                    "Resource": [
                        "arn:aws:s3:::hw18-reports",
                        "arn:aws:s3:::hw18-reports/*"
                    ]
                }
            ]
        },
        "VersionId": "v1",
        "IsDefaultVersion": true,
        "CreateDate": "2026-10-07T12:38:07.039000+00:00"
    }
}
```

Note that the document comes back as parsed JSON here. On real AWS it comes back **URL-encoded** and
you have to decode it - a small but real difference when scripting against the API.

## Roles

A role is a set of permissions with **no credentials attached**. Something assumes it and receives
temporary credentials - an access key, a secret and a session token - that expire, typically in one
hour.

A role has two policies, and conflating them is the number one source of IAM confusion:

- The **trust policy** (`AssumeRolePolicyDocument`) says *who may assume the role*.
- The **permissions policy** says *what the role can do once assumed*.

```bash
cat hw18-trust.json
```

```text
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
```

```bash
aws --endpoint-url=http://localhost:4566 iam create-role \
  --role-name hw18-ec2-reports-role \
  --assume-role-policy-document file://hw18-trust.json
```

```text
{
    "Role": {
        "Path": "/",
        "RoleName": "hw18-ec2-reports-role",
        "RoleId": "AROAQAAAAAAADEAB4CZXP",
        "Arn": "arn:aws:iam::000000000000:role/hw18-ec2-reports-role",
        "CreateDate": "2026-10-07T12:38:07.777000+00:00",
        "AssumeRolePolicyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ec2.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
    }
}
```

The `RoleId` prefix `AROA` identifies a role; users get `AIDA`, access keys get `AKIA`. Useful when
reading CloudTrail.

Now grant the role its actual permissions:

```bash
aws --endpoint-url=http://localhost:4566 iam attach-role-policy \
  --role-name hw18-ec2-reports-role \
  --policy-arn arn:aws:iam::000000000000:policy/hw18-reports-readonly
aws --endpoint-url=http://localhost:4566 iam list-attached-role-policies \
  --role-name hw18-ec2-reports-role
```

```text
{
    "AttachedPolicies": [
        {
            "PolicyName": "hw18-reports-readonly",
            "PolicyArn": "arn:aws:iam::000000000000:policy/hw18-reports-readonly"
        }
    ]
}
```

The same customer managed policy is now attached to both the group and the role. That reuse is the
reason to prefer customer managed over inline.

### Who assumes roles

| Principal in the trust policy | Scenario |
|---|---|
| `{"Service": "ec2.amazonaws.com"}` | EC2 instance profile - the instance gets credentials from the metadata service, no keys on disk |
| `{"Service": "lambda.amazonaws.com"}` | Lambda execution role |
| `{"AWS": "arn:aws:iam::<other-account>:root"}` | Cross-account access |
| `{"Federated": "arn:aws:iam::<acct>:oidc-provider/token.actions.githubusercontent.com"}` | GitHub Actions via OIDC, with a `Condition` pinning the repo and branch |
| `{"Federated": "arn:aws:iam::<acct>:oidc-provider/oidc.eks.<region>...."}` | IRSA - a Kubernetes service account on EKS |

Add `Condition: {"StringEquals": {"sts:ExternalId": "..."}}` when a third-party SaaS vendor assumes
a role in your account. Without it, their other customers' role ARNs could be substituted - the
"confused deputy" problem.

### The big one: EC2 instance profile instead of access keys

Access keys on an instance are a standing liability. They sit in `~/.aws/credentials`, they get
baked into AMIs, they end up in a Docker image layer, they get committed. An instance profile gives
the instance role credentials that rotate automatically and never touch the filesystem. **An
application running on AWS should essentially never hold a long-lived access key.**

## Permissions and least privilege

Least privilege means: grant the smallest set of actions, on the narrowest set of resources, under
the tightest conditions that still lets the job get done - and nothing more.

Three progressively better versions of the same intent:

```json
{"Effect": "Allow", "Action": "s3:*", "Resource": "*"}
```

Every S3 action on every bucket in the account. Includes `s3:DeleteBucket` and
`s3:PutBucketPolicy`, which means this principal can delete your data and then grant the world
access to what is left.

```json
{"Effect": "Allow", "Action": "s3:*", "Resource": "arn:aws:s3:::hw18-reports/*"}
```

Scoped to one bucket. Better, but still includes delete and ACL changes, and still cannot list the
bucket because the bucket ARN itself is missing.

```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": ["arn:aws:s3:::hw18-reports", "arn:aws:s3:::hw18-reports/*"],
  "Condition": {"Bool": {"aws:SecureTransport": "true"}}
}
```

Two specific read actions, both required ARNs, and only over TLS. This is what the policy created
above looks like.

### Where IAM limits apply beyond identity policies

- **Permissions boundary** - an upper bound attached to a user or role. The effective permission is
  the intersection of the identity policy and the boundary. This is how you let a team create roles
  without letting them create `AdministratorAccess` roles.
- **Service Control Policies (SCPs)** - account-wide guardrails from AWS Organizations. An SCP
  never grants anything; it only limits what the account's policies can grant. Even the root user
  is subject to them.
- **Session policies** - passed at `sts:AssumeRole` time to further narrow a single session.
- **Resource policies** - attached to the resource (S3 bucket policy, KMS key policy, SQS queue
  policy) rather than the identity. Within one account, an Allow from either side is enough; across
  accounts, you need an Allow on **both** sides.

### Trying to verify this on LocalStack

The right tool for checking a policy is the simulator. It is not implemented here:

```bash
aws --endpoint-url=http://localhost:4566 iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::000000000000:user/hw18-analyst \
  --action-names s3:GetObject s3:DeleteObject \
  --resource-arns 'arn:aws:s3:::hw18-reports/q3.csv'
```

```text
aws: [ERROR]: An error occurred (InternalError) when calling the SimulatePrincipalPolicy operation
(reached max retries: 2): exception while calling iam.SimulatePrincipalPolicy: 404 Not Found:
<?xml version="1.0" encoding="UTF-8"?>
<ErrorResponse xmlns="https://iam.amazonaws.com/doc/2010-05-08/">
    <Error>
        <Code>NoSuchEntity</Code>
        <Message><![CDATA[Policy arn:aws:iam::000000000000:user/hw18-analyst not found]]></Message>
        <Type>Sender</Type>
        <RequestId>7a62c49f-347e-4fc4-9331-6e8eEXAMPLE</RequestId>
    </Error>
</ErrorResponse>
```

This is a genuine LocalStack community limitation, not a mistake in the command. On real AWS the
same call returns `EvaluationResult` entries with `allowed` for `s3:GetObject` and `implicitDeny`
for `s3:DeleteObject`, and it names the statement that decided it. The console equivalent is the
IAM Policy Simulator. **Use it before you ship a policy** - it is the only way to check the
intersection of identity policy, resource policy, boundary and SCP without actually trying the call.

## Best practices

1. **Lock the root user away.** Hardware MFA, no access keys, used only for the handful of tasks
   that require it (closing the account, changing support plan). Alert on every root login.
2. **MFA everywhere for humans.** Enforce it with a Deny condition rather than trusting people:
   `{"Effect":"Deny","Action":"*","Resource":"*","Condition":{"BoolIfExists":{"aws:MultiFactorAuthPresent":"false"}}}`.
   `BoolIfExists` matters - plain `Bool` breaks service-to-service calls where the key is absent.
3. **Roles over users, temporary credentials over keys.** Instance profiles, task roles, IRSA, OIDC
   federation for CI.
4. **Groups over per-user policies.** Attaching policies directly to a user does not scale and makes
   offboarding an archaeology exercise.
5. **Start from zero and add.** Granting `*` "to unblock the deploy" and promising to tighten it
   later is how every over-permissioned account was built.
6. **Rotate and prune.** `iam get-credential-report` lists every key and when it was last used.
   Access Analyzer's unused-access findings show roles nobody has assumed in 90 days.
7. **Use `Condition` aggressively.** `aws:SourceIp` for office ranges, `aws:RequestedRegion` to pin
   a region, `aws:SecureTransport` to demand TLS, `aws:PrincipalTag` for attribute-based access.
8. **Put it in Terraform.** A policy in version control gets reviewed, diffed and reverted. A policy
   someone edited in the console does not.
9. **Permissions boundaries and SCPs for guardrails.** Guardrails constrain even mistakes made by
   people with admin rights.
10. **CloudTrail on, and read it.** IAM failures are invisible until you look at `AccessDenied`
    events, and that log is also how you find out which permissions an over-broad policy never used.

## Common use cases

| Need | How |
|---|---|
| App on EC2 reads one S3 bucket | Role with an EC2 trust policy, attached as an instance profile |
| Lambda writes to DynamoDB and logs | Execution role with scoped table permissions plus `AWSLambdaBasicExecutionRole` |
| GitHub Actions deploys to AWS | OIDC provider plus a role whose trust policy pins `repo:org/name:ref:refs/heads/main` |
| A vendor needs read access to your account | Cross-account role with `sts:ExternalId` in the trust policy |
| Analysts get read-only on one bucket | Group plus a customer managed policy, users added to the group |
| Developers can create roles but not escalate | Permissions boundary required on every role they create |
| Nothing may run outside eu-west-1 | SCP with `Deny` on `aws:RequestedRegion != eu-west-1` |
| Pod on EKS calls AWS APIs | IRSA - service account annotated with a role ARN |

## When you would actually use this

IAM is not a thing you choose to use - it is on the path of every AWS API call whether you think
about it or not. The real decision is how much structure you put around it.

Reach for it deliberately when:

- **You are about to put an access key somewhere.** Stop. There is a role for that. Config file,
  environment variable, CI secret, Dockerfile - all of these are the wrong answer when the workload
  runs on AWS.
- **A second person joins the account.** That is the moment to create groups and stop using root.
- **You are wiring up CI/CD.** OIDC federation into a deploy role is a half-hour of setup that
  removes a permanent credential from your pipeline forever.
- **Someone asks for "just admin for now".** That is the moment to write the scoped policy instead,
  because "for now" never ends.
- **An incident happens.** The blast radius of a compromised credential is exactly the permissions
  you granted it. That number is decided months in advance.
- **You hand data to a third party.** Cross-account role with an external id, not a user with keys
  emailed over.

## Interview questions

1. What is the difference between an IAM user and an IAM role, and why does the industry push
   toward roles?
2. A user has an Allow for `s3:*` from a group policy and a Deny for `s3:DeleteObject` from an
   attached policy. Can they delete an object? Why?
3. Explain the difference between an identity policy and a resource policy. When do you need both?
4. Why does an S3 read policy need two ARNs, and what breaks if you supply only one?
5. What is a permissions boundary and how does it differ from an SCP?
6. An EC2 instance needs to read from S3. Walk through how you give it access without any access
   key existing anywhere.
7. What is the confused deputy problem and how does `sts:ExternalId` address it?
8. You inherit an account where everybody has `AdministratorAccess`. What do you do first, and how
   do you find out what permissions are actually being used?
9. Why is `"Version": "2012-10-17"` always that date, and what happens if you use `"2008-10-17"`?
10. How would you let a GitHub Actions workflow deploy to AWS without storing credentials in GitHub?
