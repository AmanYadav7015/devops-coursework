# 03 - S3 (Simple Storage Service)

## This ran against LocalStack, not real AWS

Every command below was executed against **LocalStack 3.8.1 (community edition)** on
`http://localhost:4566`. There are no real AWS credentials on this machine. The bucket
`hw18-s3-research` existed only inside that container and was deleted at the end.

S3 is LocalStack's best-emulated service, and nearly everything on this page genuinely works: real
version ids, real delete markers, real lifecycle configuration, real encryption metadata. The
differences that matter:

- **Bucket policies are stored but not enforced.** Demonstrated below - a `Deny` statement that
  should have blocked an upload did not. On real AWS that same upload returns `AccessDenied`.
- **Lifecycle rules are stored but never execute.** No transition to `STANDARD_IA` or `GLACIER` ever
  happens, and nothing ever expires, because LocalStack community has no lifecycle engine.
- **Storage classes are a label.** Setting `STANDARD_IA` changes the metadata, not the cost, the
  retrieval time or the minimum storage duration.
- Bucket names are only unique inside this container, not globally.
- No cost, no CloudFront, no replication, no Object Lock enforcement, no Glacier restore delays.

## What is S3

S3 is object storage: a flat key-value store for files, reachable over HTTP, with effectively
unlimited capacity. It is not a filesystem. There are no directories, no partial writes, no append,
and no POSIX semantics. You `PUT` a whole object and you `GET` a whole object.

The things that make it the backbone of most AWS architectures:

- **Durability of 99.999999999% (eleven nines)** for `STANDARD`, achieved by replicating across at
  least three availability zones.
- **No capacity planning.** You never provision size or IOPS.
- **Strong read-after-write consistency** for all operations since December 2020. A `GET` straight
  after a `PUT` returns the new object - you no longer have to design around eventual consistency
  for object reads. (Bucket-level configuration such as policies and replication rules is still
  eventually consistent.)
- **Pay for what you store and what you request**, with no minimum.

## Buckets

A bucket is the top-level container. Everything else lives inside one.

```bash
aws --endpoint-url=http://localhost:4566 s3api create-bucket --bucket hw18-s3-research
```

```text
{
    "Location": "/hw18-s3-research"
}
```

Bucket rules that bite people:

- **The name is globally unique across every AWS account on earth.** Not per-account, not per-region.
  If someone already has `reports`, you cannot have it. This is why real bucket names look like
  `acme-prod-reports-eu-west-1-8f3a`. In Terraform, use `bucket_prefix` and let AWS add entropy, or
  append a `random_id`.
- **The name is DNS-compatible**: 3-63 characters, lowercase, digits, hyphens and dots. Dots break
  TLS on virtual-hosted-style URLs, so avoid them.
- **A bucket lives in one region** even though the namespace is global. Data stays in that region
  unless you replicate it. This is a compliance control, not just a latency one.
- **Default limit of 100 buckets per account** (raisable to 1,000). Buckets are not the unit of
  organisation - prefixes are.
- **The name is permanent.** There is no rename. Changing it means create, copy, delete, which in
  Terraform shows up as `-/+ forces replacement`.

## Objects

An object is the data plus its metadata, addressed by a **key**.

```bash
aws --endpoint-url=http://localhost:4566 s3api put-object \
  --bucket hw18-s3-research --key logs/cold.txt --body cold.txt --storage-class STANDARD_IA
aws --endpoint-url=http://localhost:4566 s3api list-objects-v2 --bucket hw18-s3-research \
  --query 'Contents[].{Key:Key,Size:Size,Class:StorageClass}' --output table
```

```text
------------------------------------------
|              ListObjectsV2             |
+--------------+-----------------+-------+
|     Class    |       Key       | Size  |
+--------------+-----------------+-------+
|  STANDARD_IA |  logs/cold.txt  |  10   |
+--------------+-----------------+-------+
```

`logs/cold.txt` **looks** like a file in a directory. It is not. The key is the literal string
`logs/cold.txt`; the slash has no special meaning to S3. The console renders a folder tree by
grouping on `/` using the `Delimiter` and `CommonPrefixes` parameters, but there is no directory
object underneath.

This matters practically:

- There is no "move a folder" operation. Renaming a prefix means copying every object and deleting
  the originals.
- `aws s3 ls s3://bucket/logs/` is a `ListObjectsV2` call with a prefix filter, and it pages 1,000
  keys at a time. On a bucket with millions of objects, listing is slow and expensive; use S3
  Inventory instead.
- **Prefix design determines performance.** S3 scales to 3,500 `PUT`/s and 5,500 `GET`/s *per
  prefix*. A date-first key like `2026/10/07/...` concentrates all of today's writes on one prefix;
  putting a high-cardinality component first spreads them.

Other object facts:

- Max object size is 5 TB, but a single `PUT` is capped at 5 GB. Beyond that you need multipart
  upload - which the CLI and SDKs do automatically.
- `ETag` is the MD5 of the content for a simple upload, and something else entirely for a multipart
  upload, so it is not a reliable checksum. Use the `ChecksumAlgorithm` parameters if you need one.
- Objects carry user-defined metadata (`x-amz-meta-*`), a content type, and optional tags that
  policies and lifecycle rules can filter on.

## Storage classes

A storage class trades retrieval speed and minimum duration against price.

| Class | Retrieval | Min duration | Typical use |
|---|---|---|---|
| `STANDARD` | Immediate | None | Active data, anything served to users |
| `INTELLIGENT_TIERING` | Immediate | None | **The safe default when access patterns are unknown.** Moves objects between tiers automatically for a small monitoring fee |
| `STANDARD_IA` | Immediate | 30 days | Known-infrequent access, still needs instant reads. Charged a per-GB retrieval fee |
| `ONEZONE_IA` | Immediate | 30 days | Same, but one AZ only - cheaper, and you lose it if that AZ is lost. Only for reproducible data |
| `GLACIER_IR` | Immediate | 90 days | Archives you occasionally need right now |
| `GLACIER` (Flexible Retrieval) | Minutes to 12 hours | 90 days | Backups, compliance archives |
| `DEEP_ARCHIVE` | 12-48 hours | 180 days | Records you must keep for 7 years and hope never to read |

The traps, all of which cost real money:

- **Minimum duration is billed whether or not the object survives.** Delete a `STANDARD_IA` object
  after 3 days and you are billed for 30.
- **Minimum billable object size.** `STANDARD_IA` and below bill every object as at least 128 KB.
  Moving a million 2 KB files to `STANDARD_IA` *increases* the bill.
- **Retrieval fees.** `STANDARD_IA` charges per GB retrieved. Data you read monthly is not
  infrequent access.
- **Each lifecycle transition is a billed request.** Transitioning millions of tiny objects can cost
  more than the storage saved.

Setting it explicitly worked here:

```bash
aws --endpoint-url=http://localhost:4566 s3api put-object \
  --bucket hw18-s3-research --key logs/cold.txt --body cold.txt --storage-class STANDARD_IA
```

```text
{
    "VersionId": "9Sv6hasJBnuJth1iqrMhcIU_gekgOQV7"
}
```

But on LocalStack that string is metadata only - there is no tiering engine and no price difference.

## Versioning

Versioning keeps every version of every key, including deletes. It is the single most valuable
safety feature S3 has, and it is **off by default**.

```bash
aws --endpoint-url=http://localhost:4566 s3api put-bucket-versioning \
  --bucket hw18-s3-research --versioning-configuration Status=Enabled

echo "revision one" > report.txt
aws --endpoint-url=http://localhost:4566 s3api put-object --bucket hw18-s3-research --key report.txt --body report.txt
echo "revision two" > report.txt
aws --endpoint-url=http://localhost:4566 s3api put-object --bucket hw18-s3-research --key report.txt --body report.txt

aws --endpoint-url=http://localhost:4566 s3api list-object-versions --bucket hw18-s3-research \
  --query 'Versions[].{Key:Key,VersionId:VersionId,Latest:IsLatest,Size:Size,Class:StorageClass}' --output table
```

```text
{
    "VersionId": ".Bj9JRhWIUgrCh.sf0AO7lEpoQ65O6aQ",
    "ETag": "\"4717bea2e29d8ce93ac3a3c32503cd3b\""
}
{
    "VersionId": "A5IKqPy8Zx6UfoTpzUR65kmfOJkYOEJG",
    "ETag": "\"9e7aa03f22a55551692032fa2378da6e\""
}
----------------------------------------------------------------------------------
|                               ListObjectVersions                               |
+----------+-------------+---------+-------+-------------------------------------+
|   Class  |     Key     | Latest  | Size  |              VersionId              |
+----------+-------------+---------+-------+-------------------------------------+
|  STANDARD|  report.txt |  True   |  13   |  A5IKqPy8Zx6UfoTpzUR65kmfOJkYOEJG   |
|  STANDARD|  report.txt |  False  |  13   |  .Bj9JRhWIUgrCh.sf0AO7lEpoQ65O6aQ   |
+----------+-------------+---------+-------+-------------------------------------+
```

One key, two versions, different ETags. The second `PUT` did not overwrite the first - it became the
new current version and pushed the old one to non-current.

### Delete creates a marker, it does not erase

```bash
aws --endpoint-url=http://localhost:4566 s3api delete-object --bucket hw18-s3-research --key report.txt
aws --endpoint-url=http://localhost:4566 s3api list-objects-v2 --bucket hw18-s3-research --query 'Contents'
aws --endpoint-url=http://localhost:4566 s3api list-object-versions --bucket hw18-s3-research \
  --query '{Versions:Versions[].{V:VersionId,Latest:IsLatest},DeleteMarkers:DeleteMarkers[].{V:VersionId,Latest:IsLatest}}'
```

```text
{
    "DeleteMarker": true,
    "VersionId": "Av_hjxEwD2FDxpf99PFpoadEArdwD.pM"
}
null
{
    "Versions": [
        {
            "V": "A5IKqPy8Zx6UfoTpzUR65kmfOJkYOEJG",
            "Latest": false
        },
        {
            "V": ".Bj9JRhWIUgrCh.sf0AO7lEpoQ65O6aQ",
            "Latest": false
        }
    ],
    "DeleteMarkers": [
        {
            "V": "Av_hjxEwD2FDxpf99PFpoadEArdwD.pM",
            "Latest": true
        }
    ]
}
```

This is the whole mechanism in one output. `list-objects-v2` returns `null` - as far as a normal
read is concerned, the object is gone. But `list-object-versions` shows both data versions intact
and a **delete marker** sitting on top as the new current version. Nothing was destroyed.

Recovery is just reading past the marker:

```bash
aws --endpoint-url=http://localhost:4566 s3api get-object --bucket hw18-s3-research \
  --key report.txt --version-id .Bj9JRhWIUgrCh.sf0AO7lEpoQ65O6aQ recovered.txt
cat recovered.txt
```

```text
{
    "Length": 13,
    "Modified": "2026-10-07T12:40:28+00:00"
}
revision one
```

The very first revision came back after the object had been overwritten once and deleted once. To
restore properly you delete the delete marker (`delete-object --version-id <marker>`) and the
previous version becomes current again.

Things to know:

- **Versioning cannot be turned off, only suspended.** Once enabled, the bucket is either `Enabled`
  or `Suspended` forever. Suspending stops new versions being created but does not remove existing
  ones.
- **You pay for every version.** A 1 GB file rewritten daily for a year is 365 GB of storage unless
  a lifecycle rule cleans up non-current versions. Enabling versioning without that rule is a
  reliable way to generate a surprise bill.
- **MFA Delete** can require an MFA token to delete a version or change versioning state. It can
  only be configured by the root user, which is why almost nobody uses it.
- Versioning is a prerequisite for cross-region replication and for a sane S3-as-Terraform-backend
  setup.

## Lifecycle policies

Lifecycle rules automate transition and expiration so nobody has to remember.

```bash
cat lifecycle.json
```

```text
{
  "Rules": [
    {
      "ID": "logs-tier-then-expire",
      "Filter": {"Prefix": "logs/"},
      "Status": "Enabled",
      "Transitions": [
        {"Days": 30, "StorageClass": "STANDARD_IA"},
        {"Days": 90, "StorageClass": "GLACIER"}
      ],
      "Expiration": {"Days": 365}
    },
    {
      "ID": "clean-old-versions",
      "Filter": {},
      "Status": "Enabled",
      "NoncurrentVersionExpiration": {"NoncurrentDays": 30},
      "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
    }
  ]
}
```

```bash
aws --endpoint-url=http://localhost:4566 s3api put-bucket-lifecycle-configuration \
  --bucket hw18-s3-research --lifecycle-configuration file://lifecycle.json
aws --endpoint-url=http://localhost:4566 s3api get-bucket-lifecycle-configuration --bucket hw18-s3-research
```

```text
{
    "Rules": [
        {
            "Expiration": {
                "Days": 365
            },
            "ID": "logs-tier-then-expire",
            "Filter": {
                "Prefix": "logs/"
            },
            "Status": "Enabled",
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 90,
                    "StorageClass": "GLACIER"
                }
            ]
        },
        {
            "ID": "clean-old-versions",
            "Filter": {},
            "Status": "Enabled",
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 30
            },
            "AbortIncompleteMultipartUpload": {
                "DaysAfterInitiation": 7
            }
        }
    ]
}
```

The configuration stored and read back exactly. **It will never execute on LocalStack** - there is no
lifecycle engine in the community edition, so nothing in `logs/` will ever transition or expire here.
On real AWS these rules run once a day in the background.

Reading the two rules:

- **Rule 1** applies to keys under `logs/`. After 30 days an object moves to `STANDARD_IA`, after
  90 to `GLACIER`, and at 365 days it is deleted. Days are counted from object creation, not from
  the last transition.
- **Rule 2** has an empty filter, so it applies to the whole bucket. `NoncurrentVersionExpiration`
  is the rule that makes versioning affordable - old versions are deleted 30 days after being
  superseded. `AbortIncompleteMultipartUpload` cleans up failed multipart uploads, which otherwise
  consume storage **invisibly**: the parts are billed but do not appear in `ListObjectsV2`. Put this
  rule on every bucket you own; it is free money.

Other lifecycle facts:

- Filters can combine prefix, object tags and object size. Tag-based filtering lets the application
  decide an object's retention by tagging it at write time.
- `ExpiredObjectDeleteMarker: true` cleans up delete markers left with no versions behind them.
- Transitions only ever move *down* the cost ladder. There is no automatic promotion back to
  `STANDARD`.
- `INTELLIGENT_TIERING` is often simpler than hand-written transition rules, because it reacts to
  actual access rather than guessed ages.

## Encryption

Two independent axes: data at rest and data in transit.

### At rest

| Mode | Key managed by | Notes |
|---|---|---|
| **SSE-S3** (`AES256`) | AWS, invisible | Free. **On by default for all new buckets since January 2023** |
| **SSE-KMS** (`aws:kms`) | AWS KMS, your CMK | Key policy, rotation, and a CloudTrail record of every decrypt. Costs per API call - enable **S3 Bucket Keys** or a high-volume bucket gets expensive |
| **DSSE-KMS** | KMS, applied twice | Dual-layer, for specific compliance regimes |
| **SSE-C** | You send the key on every request | AWS never stores it. You own all the key management pain |
| Client-side | You, before upload | S3 only ever sees ciphertext |

```bash
aws --endpoint-url=http://localhost:4566 s3api put-bucket-encryption --bucket hw18-s3-research \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":false}]}'

aws --endpoint-url=http://localhost:4566 s3api head-object --bucket hw18-s3-research \
  --key logs/cold.txt --query '{Encryption:ServerSideEncryption,Class:StorageClass,Length:ContentLength}'
```

```text
{
    "Encryption": "AES256",
    "Class": "STANDARD_IA",
    "Length": 10
}
```

`head-object` reporting `ServerSideEncryption: AES256` is how you verify encryption actually applied
to a specific object, rather than trusting that the bucket default was configured.

### In transit

S3 accepts both HTTP and HTTPS. Requiring TLS is your job, via a bucket policy condition on
`aws:SecureTransport` - shown next.

## Bucket policies

A bucket policy is a **resource policy**: it is attached to the bucket and names a `Principal`,
unlike an IAM identity policy. Within one account either side granting access is enough; across
accounts you need both sides to allow it.

```bash
cat bucketpolicy.json
```

```text
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyUnencryptedUploads",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::hw18-s3-research/*",
      "Condition": {
        "StringNotEquals": {"s3:x-amz-server-side-encryption": "AES256"}
      }
    },
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::hw18-s3-research",
        "arn:aws:s3:::hw18-s3-research/*"
      ],
      "Condition": {"Bool": {"aws:SecureTransport": "false"}}
    }
  ]
}
```

```bash
aws --endpoint-url=http://localhost:4566 s3api put-bucket-policy \
  --bucket hw18-s3-research --policy file://bucketpolicy.json
aws --endpoint-url=http://localhost:4566 s3api get-bucket-policy --bucket hw18-s3-research \
  --query Policy --output text | python3 -m json.tool
```

```text
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DenyUnencryptedUploads",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:PutObject",
            "Resource": "arn:aws:s3:::hw18-s3-research/*",
            "Condition": {
                "StringNotEquals": {
                    "s3:x-amz-server-side-encryption": "AES256"
                }
            }
        },
        {
            "Sid": "DenyInsecureTransport",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": [
                "arn:aws:s3:::hw18-s3-research",
                "arn:aws:s3:::hw18-s3-research/*"
            ],
            "Condition": {
                "Bool": {
                    "aws:SecureTransport": "false"
                }
            }
        }
    ]
}
```

Note the two `Resource` forms again. `arn:aws:s3:::bucket` is the bucket itself, for bucket-level
actions like `s3:ListBucket`. `arn:aws:s3:::bucket/*` is the objects, for `s3:GetObject` and
`s3:PutObject`. The second statement lists both, because `s3:*` covers both kinds of action.

### LocalStack does not enforce it, and here is the proof

The whole endpoint is plain HTTP, so `aws:SecureTransport` is `false` on every request. The
`DenyInsecureTransport` statement should block everything. Instead:

```bash
aws --endpoint-url=http://localhost:4566 s3api put-object \
  --bucket hw18-s3-research --key should-be-denied.txt --body denied.txt
aws --endpoint-url=http://localhost:4566 s3 ls s3://hw18-s3-research/ --recursive
```

```text
{
    "VersionId": "p78UxekioK8JdB7B4iJtGJ6NWJdHNVxP"
}
2026-10-07 18:10:47         10 logs/cold.txt
2026-10-07 18:11:07         17 should-be-denied.txt
```

The upload succeeded with exit code 0 and the object is in the listing. On real AWS the same call
returns:

```text
An error occurred (AccessDenied) when calling the PutObject operation: Access Denied
```

This is worth dwelling on, because it is the most important caveat on this entire page. **An
emulator can tell you your policy is syntactically valid. It cannot tell you your policy is
correct.** Policy behaviour has to be verified against real AWS, or at minimum reasoned through with
the IAM Policy Simulator and a tool like `cfn-policy-validator` or Access Analyzer.

### Public access, and how buckets leak

Nearly every "S3 data breach" headline is a bucket policy with `"Principal": "*"` and no
`Condition`, or an object ACL granting `AllUsers`.

**S3 Block Public Access** is the backstop, and since April 2023 it is on by default for new
buckets. Four independent switches:

| Setting | Blocks |
|---|---|
| `BlockPublicAcls` | New public ACLs being set |
| `IgnorePublicAcls` | Existing public ACLs having any effect |
| `BlockPublicPolicy` | New bucket policies that S3 judges public |
| `RestrictPublicBuckets` | Public access through any existing policy |

It can be set at the account level too, which overrides every bucket. Turn it on account-wide and
the class of mistake disappears.

The correct way to serve public content is **CloudFront with Origin Access Control** - the bucket
stays private and only the CloudFront distribution's service principal can read it. You get caching,
TLS, a custom domain and a WAF, and the bucket never has a public policy.

ACLs are the legacy mechanism and should be considered dead. Set `ObjectOwnership: BucketOwnerEnforced`
to disable them entirely, which is the default for new buckets.

## Common use cases

| Need | How |
|---|---|
| Static website | S3 private, CloudFront with OAC, Route 53 alias |
| Application uploads | Presigned `PUT` URL so the browser uploads directly, bypassing your servers |
| Data lake | Parquet partitioned by date, queried with Athena or Glue |
| Backups | `GLACIER`/`DEEP_ARCHIVE` via lifecycle, Object Lock for WORM compliance |
| Log aggregation | ALB, CloudTrail and VPC Flow Logs all write to S3 natively |
| Terraform state backend | Versioning on, encryption on, Block Public Access on, DynamoDB table for locking |
| Static assets for a CDN | `STANDARD`, long `Cache-Control`, CloudFront in front |
| Cross-region DR | Cross-Region Replication, which requires versioning on both ends |
| Large file ingest | Multipart upload plus Transfer Acceleration for distant clients |
| Event-driven processing | S3 event notification to Lambda, SQS or EventBridge on `ObjectCreated` |

## When you would actually use this

S3 is the default answer for storing anything that is not a row in a database. Specifically:

- **Any file a user uploads.** Images, PDFs, CSVs, videos. Generate a presigned URL so the file goes
  browser-to-S3 and never through your application servers - that removes a scaling bottleneck and
  a disk you would otherwise have to manage.
- **Anything you want to keep but rarely read.** Backups, exports, audit logs, old invoices. The
  lifecycle rule writes itself and `DEEP_ARCHIVE` is about a dollar per terabyte per month.
- **Static assets and whole static sites.** S3 plus CloudFront replaces a web server fleet entirely
  and is close to free at small scale.
- **A data lake.** Decoupling storage from compute is the entire point of the modern analytics
  stack; S3 is the storage half and Athena, EMR, Glue and Redshift Spectrum all read from it.
- **Terraform remote state.** Versioning turns a corrupted state file into a one-command recovery.
- **The glue between services.** An object landing in a bucket is an event. S3 to Lambda, S3 to SQS,
  S3 to EventBridge is the backbone of most AWS pipelines.

Do **not** reach for S3 when:

- **You need a filesystem.** Multiple instances needing POSIX semantics on shared storage want EFS,
  or FSx. S3 has no locking, no partial writes and no append.
- **You need low-latency random access to small records.** That is DynamoDB. S3 request latency is
  tens of milliseconds and you pay per request.
- **You need transactions or queries across records.** That is a database. Athena over S3 is for
  analytics, not for an application's read path.
- **The object changes constantly.** Every write is a full rewrite of the whole object.

## Interview questions

1. What actually happens when you delete an object in a versioned bucket, and how do you recover it?
2. Why does an S3 read policy need both `arn:aws:s3:::bucket` and `arn:aws:s3:::bucket/*`?
3. S3 has no directories. So what is `logs/2026/10/report.csv`, and what does that imply for
   renaming a "folder"?
4. A team enables versioning and the storage bill triples over six months. What went wrong and what
   is the fix?
5. When is `STANDARD_IA` more expensive than `STANDARD`? Give two distinct reasons.
6. What is the difference between a bucket policy and an IAM policy, and when do you need both?
7. How would you serve a static website over HTTPS on a custom domain without ever making the
   bucket public?
8. What is S3 Block Public Access and why are its four settings separate?
9. Explain multipart upload. What is `AbortIncompleteMultipartUpload` for and why does it matter to
   the bill?
10. A bucket is hitting request rate limits. How does S3 partition throughput and how do you design
    keys around it?
11. Your bucket must only ever accept encrypted uploads. Write the policy condition and explain how
    you would verify it works.
12. What changed about S3 consistency in December 2020, and what design workaround did it make
    obsolete?
