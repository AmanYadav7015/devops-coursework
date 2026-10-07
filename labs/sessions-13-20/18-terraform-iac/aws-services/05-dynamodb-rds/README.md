# 05 - DynamoDB and RDS

## Neither service could be run here, and here is the proof

The other four pages in this folder include real commands with real output, because LocalStack
community emulates S3, EC2, IAM and STS. **DynamoDB and RDS are the two services on this homework
that could not be executed at all.** Rather than invent plausible output, this page shows the real
failures and then documents both services honestly as research.

There are no real AWS credentials on this machine and none will be added.

### Why DynamoDB is unavailable

The running LocalStack container was started with an explicit service allow-list:

```bash
docker inspect localstack-main --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^SERVICES='
curl -s http://localhost:4566/_localstack/health | python3 -m json.tool \
  | grep -E '"(dynamodb|rds|s3|ec2|iam|sts|edition|version)"'
```

```text
SERVICES=s3,ec2,iam,sts
        "dynamodb": "disabled",
        "ec2": "running",
        "iam": "running",
        "s3": "running",
        "sts": "running",
    "edition": "community",
    "version": "3.8.1"
```

DynamoDB is a community-edition service, so LocalStack *could* run it - but this shared container
limits `SERVICES` to four, and `rds` does not appear in the health output at all. The container is
shared with other concurrent work and must not be restarted, so enabling DynamoDB was not an option.

```bash
aws --endpoint-url=http://localhost:4566 dynamodb create-table --table-name hw18-orders \
  --attribute-definitions AttributeName=customer_id,AttributeType=S AttributeName=order_date,AttributeType=S \
  --key-schema AttributeName=customer_id,KeyType=HASH AttributeName=order_date,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
```

```text
aws: [ERROR]: An error occurred (InternalFailure) when calling the CreateTable operation:
Service 'dynamodb' is not enabled. Please check your 'SERVICES' configuration variable.
```

```bash
aws --endpoint-url=http://localhost:4566 dynamodb list-tables
echo "exit: $?"
```

```text
aws: [ERROR]: An error occurred (InternalFailure) when calling the ListTables operation:
Service 'dynamodb' is not enabled. Please check your 'SERVICES' configuration variable.
exit: 254
```

### Why RDS is unavailable

RDS is different: it is **not in LocalStack community at all**.

```bash
aws --endpoint-url=http://localhost:4566 rds create-db-instance \
  --db-instance-identifier hw18-orders-db --db-instance-class db.t3.micro \
  --engine postgres --allocated-storage 20 \
  --master-username appuser --master-user-password 'NotARealPassword1'
```

```text
aws: [ERROR]: An error occurred (InternalFailure) when calling the CreateDBInstance operation:
API for service 'rds' not yet implemented or pro feature - please check
https://docs.localstack.cloud/references/coverage/ for further information
```

```bash
aws --endpoint-url=http://localhost:4566 rds describe-db-instances
echo "exit: $?"
```

```text
aws: [ERROR]: An error occurred (InternalFailure) when calling the DescribeDBInstances operation:
API for service 'rds' not yet implemented or pro feature - please check
https://docs.localstack.cloud/references/coverage/ for further information
exit: 254
```

"not yet implemented or pro feature" is LocalStack telling you this needs the paid Pro edition. No
amount of configuration on the community image will change that.

### What you would do instead

- **DynamoDB**: run `amazon/dynamodb-local` (a separate official container from AWS) or
  `localstack` with `SERVICES` including `dynamodb`. The DynamoDB API is one of the easiest to
  emulate faithfully, and `dynamodb-local` is what AWS themselves recommend for offline development.
- **RDS**: there is no meaningful emulation, because RDS is mostly *operations* - provisioning,
  backups, failover, patching. Running Postgres or MySQL in a local Docker container gets you the
  engine and gives you none of RDS. The RDS behaviours worth learning (multi-AZ failover, read
  replica lag, automated backups, parameter groups) can only be exercised on real AWS.

Everything below is therefore documentation, not a captured run. It is marked as such.

---

# DynamoDB

## What it is

A fully managed, serverless NoSQL key-value and document database. Single-digit millisecond latency
at any scale, no servers, no version upgrades, no capacity planning if you use on-demand mode.

The trade is sharp: you get predictable performance at unlimited scale, and you give up ad-hoc
queries. **You must know your access patterns before you design the table.** DynamoDB is not a
database you explore; it is a database you plan.

## Tables, items and attributes

| Relational term | DynamoDB term | Difference |
|---|---|---|
| Table | **Table** | No fixed schema beyond the key |
| Row | **Item** | Max 400 KB, including attribute names |
| Column | **Attribute** | Every item can have different attributes |
| Schema | Key schema only | Only the partition key and optional sort key are declared |

An item is a JSON-like document with typed attributes: `S` string, `N` number, `B` binary, `BOOL`,
`NULL`, `L` list, `M` map, `SS`/`NS`/`BS` sets.

```json
{
  "customer_id": {"S": "CUST#4417"},
  "order_date":  {"S": "2026-10-07T12:40:00Z"},
  "total":       {"N": "249.90"},
  "status":      {"S": "shipped"},
  "items":       {"L": [{"M": {"sku": {"S": "ABC-1"}, "qty": {"N": "2"}}}]}
}
```

Only `customer_id` and `order_date` are declared in the table's key schema. Every other attribute is
whatever that item happens to have - two items in the same table need share nothing else.

## Partition key and sort key

The **primary key** is either:

- **Partition key alone** (simple key) - must be unique across the table.
- **Partition key + sort key** (composite key) - the *pair* must be unique. Many items can share a
  partition key.

The partition key is hashed to decide which physical partition stores the item. That single fact
drives everything:

- **A `GetItem` by full primary key is O(1)** and costs one read unit regardless of table size.
- **A `Query` must supply the partition key**, and can then filter or range over the sort key:
  `customer_id = "CUST#4417" AND order_date BETWEEN "2026-01" AND "2026-06"`. This is the efficient
  access pattern.
- **A `Scan` reads every item in the table.** It is the thing to avoid. On a large table it is slow
  and expensive, and it will not get faster as you add capacity.

### Choosing a partition key

The goal is **high cardinality and even distribution**. Each partition supports about 3,000 read
units and 1,000 write units per second, so a key that concentrates traffic creates a "hot
partition" that throttles while the rest of the table idles.

| Bad partition key | Why | Better |
|---|---|---|
| `status` (5 values) | Only 5 partitions, all traffic on "pending" | `order_id` |
| `date` (today) | Every write today hits one partition | `customer_id`, with date as the sort key |
| `country` | Skewed - one country dominates | `country#user_id` composite |

When a naturally low-cardinality key is unavoidable, **write sharding** appends a random or
calculated suffix (`status#0` … `status#9`) and the reader queries all shards in parallel.

### Secondary indexes

Because you can only query by the primary key, indexes are how you support a second access pattern.

| | Local Secondary Index (LSI) | Global Secondary Index (GSI) |
|---|---|---|
| Partition key | Same as the table | **Any attribute** |
| Sort key | Different attribute | Any attribute |
| Created | Only at table creation, never after | Any time |
| Limit | 5 per table | 20 per table (soft) |
| Consistency | Strong reads possible | **Eventually consistent only** |
| Capacity | Shares the table's | Its own, provisioned separately |

GSIs are the workhorse. The important and frequently missed detail: **a GSI with its own capacity
can throttle, and when a GSI throttles it back-pressures writes to the base table.** Under-providing
a GSI breaks the table.

### Single-table design

The advanced DynamoDB pattern puts multiple entity types in one table with generic key names (`PK`,
`SK`) and composite values like `CUSTOMER#4417` / `ORDER#2026-10-07`. It lets one `Query` retrieve a
customer and all their orders in a single round trip - something that would be a join in SQL.

It is powerful and it is genuinely hard. Opinion worth having: use it when you have a well-understood
high-scale access pattern, not as a default for a new application.

## Capacity, consistency and cost

- **On-demand**: pay per request, scales instantly, no planning. Correct for spiky or unknown
  traffic, and the right default for a new table.
- **Provisioned**: set read and write capacity units, optionally with auto-scaling. Significantly
  cheaper for steady, predictable load, and eligible for reserved capacity.
- A **read capacity unit** is one strongly consistent read of up to 4 KB per second, or two
  eventually consistent reads. A **write capacity unit** is one write of up to 1 KB per second.
- **Reads are eventually consistent by default.** Pass `ConsistentRead=true` for a strongly
  consistent read at twice the cost. GSI reads can never be strongly consistent.
- **Transactions** (`TransactWriteItems`) give ACID across up to 100 items, at twice the capacity
  cost.

## Other things worth knowing

- **TTL** - name an attribute holding a Unix timestamp and DynamoDB deletes expired items for free,
  within about 48 hours. Perfect for sessions, carts and caches.
- **DynamoDB Streams** - an ordered change log of every item modification, consumable by Lambda.
  This is how you build event-driven reactions, cross-table denormalisation and audit trails.
- **Global tables** - multi-region active-active replication with last-writer-wins conflict
  resolution.
- **DAX** - a managed in-memory cache in front of DynamoDB, taking reads to microseconds.
- **PITR** - point-in-time recovery to any second in the last 35 days. One switch; turn it on.

## When you would actually use DynamoDB

Use it when:

- **The access pattern is "fetch this item by its id"** and you need it fast and at scale. Sessions,
  user profiles, shopping carts, feature flags, device state, game state, leaderboards.
- **Traffic is spiky or unpredictable.** On-demand mode absorbs a traffic spike that would require a
  database failover elsewhere.
- **You are building serverless.** Lambda plus DynamoDB has no connection pool problem. Lambda plus
  RDS does, which is why RDS Proxy exists.
- **You need single-digit millisecond latency at any volume**, and the data model can be shaped to
  fit.
- **You want zero operational burden.** No patching, no failover drills, no storage resizing.
- **You need a write-heavy event or time-series store**, especially with TTL for automatic
  expiration.

Do **not** use it when:

- **You do not yet know the access patterns.** Early-stage products change queries weekly; a
  relational database tolerates that and DynamoDB does not.
- **You need joins, aggregations, or ad-hoc analytical queries.** There is no `GROUP BY` and no
  `JOIN`. Exporting to S3 and querying with Athena is the workaround, and it is a workaround.
- **Items exceed 400 KB**, or you need strong consistency across many entities at once.
- **Your team knows SQL and the scale is modest.** A `db.t4g.medium` Postgres instance handles an
  enormous amount of traffic, and your developers already know how to query it.

---

# RDS (Relational Database Service)

## What it is

Managed relational databases. AWS runs the engine, the host, the storage, the backups, the patching
and the failover; you get a connection endpoint and a parameter group.

The crucial boundary: **RDS manages the database, not your data model.** Schema design, indexing,
query performance and migrations are still entirely your problem.

## Supported engines

| Engine | Notes |
|---|---|
| **PostgreSQL** | The strongest default in 2026. Rich types, extensions (PostGIS, pgvector), excellent tooling |
| **MySQL** | Huge ecosystem, very widely known |
| **MariaDB** | MySQL fork, drop-in for most purposes |
| **Oracle** | Licence-included or bring-your-own |
| **SQL Server** | Several editions; licensing drives the cost |
| **Db2** | IBM workloads |
| **Aurora** (PostgreSQL- and MySQL-compatible) | AWS's own re-architecture: storage is a distributed 6-copy-across-3-AZ layer. Faster failover (typically under 30s), up to 15 read replicas with low lag, storage autoscaling to 128 TB. Aurora Serverless v2 scales capacity in fine-grained steps |

Aurora is technically a separate service that shares the RDS API surface. For a new application on
AWS with no constraint pulling the other way, Aurora PostgreSQL is usually the better choice.

## DB instances

A DB instance is the running database: an instance class, storage, and an endpoint.

- **Instance classes** mirror EC2: `db.t4g.*` burstable for dev, `db.m7g.*` general purpose,
  `db.r7g.*` memory-optimised for production. Graviton (`g`) classes are typically cheaper.
- **Storage**: `gp3` SSD for most workloads, `io2` for high sustained IOPS, magnetic only for
  legacy. **Storage autoscaling** should be enabled - running out of disk takes the database down.
- **Endpoint**: a DNS name, e.g. `mydb.abc123.eu-west-1.rds.amazonaws.com`. Always connect by the
  endpoint, never by IP - failover changes the IP behind that name and that is the whole point.
- **Parameter groups** hold engine settings (`max_connections`, `shared_buffers`). Some parameters
  are dynamic; others need a reboot.
- **Option groups** hold engine-specific add-ons.
- **Maintenance window** - a weekly slot when AWS may apply patches, which can involve a brief
  failover. Set it deliberately.

## Security

Layered, and all of it is your responsibility to configure:

1. **Put it in a private subnet.** A DB subnet group spanning at least two AZs, none of them with an
   internet gateway route. Set `publicly_accessible = false`. A publicly accessible RDS instance is
   a finding in every audit that has ever been run.
2. **Security group** allowing only the application tier's security group on the engine port -
   5432, 3306 - and nothing else. Reference the SG, not a CIDR.
3. **Encryption at rest** with KMS. It must be enabled **at creation**; converting an unencrypted
   instance means snapshot, copy-with-encryption, restore.
4. **TLS in transit.** Enforce it with `rds.force_ssl=1` (Postgres) or
   `require_secure_transport=ON` (MySQL) in the parameter group, and verify the certificate against
   the RDS CA bundle.
5. **Credentials in Secrets Manager**, with managed rotation. Better still, **IAM database
   authentication**: the client fetches a 15-minute token through IAM and no password exists at all.
6. **Audit logging** to CloudWatch Logs, plus Performance Insights and Enhanced Monitoring.

## Backups

Two distinct mechanisms, and people conflate them:

| | Automated backups | Manual snapshots |
|---|---|---|
| Created by | RDS, daily, in the backup window | You, on demand |
| Retention | 0-35 days, then deleted | Until you delete them |
| Point-in-time recovery | **Yes**, to any second in the window | No, only to the snapshot moment |
| On instance deletion | **Deleted** unless you take a final snapshot | Kept |

**Set `backup_retention_period` greater than 0.** Setting it to 0 disables automated backups *and*
point-in-time recovery, and it is also the setting that silently disables the binlog many
replication tools depend on.

Restore always creates a **new instance**. You cannot restore in place - which means a real recovery
involves restoring, verifying, and then repointing the application. Practise it before you need it.
Add deletion protection, and set `skip_final_snapshot = false` in Terraform.

## Multi-AZ

**Multi-AZ is high availability, not scaling, and not backup.**

- **Multi-AZ instance deployment**: a synchronous standby replica in a second AZ. It serves **no
  traffic** - you cannot read from it. On failure AWS flips the DNS endpoint to the standby,
  typically in 60-120 seconds. It roughly doubles the cost.
- **Multi-AZ DB cluster**: one writer and two readable standbys across three AZs, with faster
  failover (usually under 35 seconds). The standbys *can* serve reads.
- **Aurora**: storage is already replicated six ways across three AZs; any replica can be promoted,
  typically in under 30 seconds.

Multi-AZ also removes the downtime from maintenance: AWS patches the standby, fails over, then
patches the former primary.

## Read replicas

**Read replicas are scaling, not HA.**

- **Asynchronous** replication, so there is always some lag. An application that writes and then
  immediately reads its own write from a replica will read stale data. Design for it or read from
  the writer.
- Up to 5 (RDS) or 15 (Aurora) replicas.
- Can live in **another region**, which is both a latency win for distant users and a DR building
  block.
- Can be **promoted** to a standalone writable instance - manually, and it does not rejoin
  afterwards. That is a DR procedure, not an automatic failover.
- Aurora replicas share the same storage layer, so lag is typically milliseconds rather than the
  seconds you can see on RDS.

| | Multi-AZ standby | Read replica |
|---|---|---|
| Purpose | Availability | Read scaling |
| Replication | Synchronous | Asynchronous |
| Serves reads | No (instance deployment) | Yes |
| Failover | Automatic | Manual promotion |
| Cross-region | No | Yes |

The right answer for a production database is usually **both**: Multi-AZ for availability and read
replicas for scale.

## When you would actually use RDS

Use it when:

- **Your data is relational and you want it to stay that way.** Foreign keys, joins, transactions
  across tables, `GROUP BY` - the things a relational engine does that a key-value store does not.
- **The access patterns will change.** New product requirements mean new queries; SQL absorbs that
  and a denormalised NoSQL schema does not.
- **You are migrating an existing application.** Lift-and-shift a Postgres or MySQL database into
  RDS and the application connection string is the only change.
- **You want a managed database without re-architecting.** You get backups, patching, failover and
  monitoring for the price of an instance - all things you would otherwise build and operate.
- **Your team knows SQL.** This is a real and underrated argument. Operational familiarity prevents
  outages.
- **You need strong consistency and ACID transactions** across many rows as the normal case, not the
  exception.

Do **not** use it when:

- **You need to scale writes beyond one node.** RDS has a single writer. Read replicas do not help
  write throughput. At that point you are looking at Aurora Limitless, sharding, or a different data
  model.
- **The workload is key-value at extreme scale.** DynamoDB is cheaper and faster for that shape.
- **You are fully serverless with very spiky traffic.** Lambda opening thousands of connections to
  Postgres exhausts `max_connections`; you need RDS Proxy, and at that point ask whether DynamoDB or
  Aurora Serverless v2 fits better.
- **It is analytics, not transactions.** Redshift, Athena over S3, or a lakehouse - not a row-store
  OLTP database running a six-hour aggregate.
- **You genuinely need full control of the host.** Custom extensions, specific minor versions, OS
  access. That is EC2, and you take on the operations.

## DynamoDB vs RDS, side by side

| | DynamoDB | RDS |
|---|---|---|
| Model | Key-value / document | Relational |
| Schema | Key only | Fixed, enforced |
| Query | By key, or by index | Full SQL |
| Joins | No | Yes |
| Scaling | Horizontal, automatic, unbounded | Vertical for writes; replicas for reads |
| Consistency | Eventual by default, strong optional | Strong (ACID) |
| Latency | Single-digit ms, flat with scale | Low, degrades with load and data size |
| Capacity planning | None in on-demand mode | Instance class, storage, IOPS |
| Connections | HTTPS API, no pooling needed | TCP connection pool, a real constraint |
| Cost model | Per request and per GB stored | Per instance-hour plus storage, running or not |
| Design effort | High up front, must know access patterns | Low up front, tune later |
| Operations | Essentially none | Patching, failover, parameter tuning |

## Interview questions

### DynamoDB

1. What is a partition key and what happens if you choose one with low cardinality?
2. Explain the difference between `Query` and `Scan`, and why `Scan` is discouraged.
3. When would you use a GSI instead of an LSI? What can you not change after table creation?
4. Reads are eventually consistent by default. When does that actually hurt, and what is the fix?
5. What is a hot partition and what are two ways to avoid one?
6. How would you model "get a customer and their last 20 orders in one request"?
7. What are DynamoDB Streams and give a concrete use for them.
8. You have an under-provisioned GSI. What happens to writes on the base table?

### RDS

1. What is the difference between Multi-AZ and a read replica? Which gives you high availability?
2. Your application writes a row and immediately reads it back from a read replica, and it is not
   there. Why, and what do you do?
3. What happens to automated backups when you delete a DB instance? What about manual snapshots?
4. How do you connect to RDS from a Lambda function without storing a password anywhere?
5. An RDS instance was created unencrypted. How do you encrypt it?
6. Why must you always connect via the RDS endpoint rather than the IP address?
7. When would you choose Aurora over standard RDS PostgreSQL?
8. Thousands of Lambda invocations are exhausting `max_connections`. What are your options?

### Choosing between them

1. You are designing a URL shortener expecting a billion lookups a day. DynamoDB or RDS? Justify it.
2. You are building an internal admin tool for a finance team who will want new reports every week.
   DynamoDB or RDS? Justify it.
3. What does "you must know your access patterns up front" mean in practice, and what is the cost of
   getting it wrong in each system?
