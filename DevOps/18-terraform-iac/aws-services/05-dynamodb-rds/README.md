# 05 · DynamoDB & RDS (Database Services)

> **Hands-on environment:** run against the local AWS emulator (moto server on
> `localhost:4566`, see the [Session 18 README](../../README.md)), not a real
> AWS account.
> - The DynamoDB part is a **working** key-value store in the emulator: the
>   items, queries and conditional writes below really executed.
> - For RDS the emulator implements only the **management API**. It records
>   instances, replicas and snapshots, but no PostgreSQL server runs, so there
>   was nothing to connect to with `psql`.
>
> Transcripts: [`evidence/dynamodb-handson.txt`](evidence/dynamodb-handson.txt)
> and [`evidence/rds-handson.txt`](evidence/rds-handson.txt). `aws` below means
> `aws --endpoint-url http://localhost:4566`.

---

# Part 1: DynamoDB

## NoSQL

DynamoDB is AWS's fully managed, serverless **NoSQL key-value and document**
database:

- no servers, versions or patches to manage;
- single-digit-millisecond latency at any scale;
- billed **on-demand** (per request) or **provisioned** (read/write capacity
  units).

"NoSQL" here means:

- **no fixed schema** beyond the primary key;
- **no joins** and no ad-hoc SQL queries. You design the table around the
  **access patterns** you know in advance.
- **horizontal scaling:** data is spread over partitions by hashing the
  partition key.

| | Relational (RDS) | DynamoDB |
|---|---|---|
| Schema | fixed columns, enforced | only the key is fixed |
| Query | any SQL, joins, aggregates | by key (GetItem / Query); Scan otherwise |
| Scale | vertical (bigger instance) + read replicas | horizontal, automatic, practically unlimited |
| Ops | instance size, storage, patches, failover | none |
| Design starts from | the data (normalise) | the access patterns (denormalise) |

## Tables

A table is a collection of items. You only declare its **key schema** (and any
indexes), its billing mode, and options such as TTL, streams and point-in-time
recovery.

```
$ aws dynamodb create-table --table-name Orders \
    --attribute-definitions AttributeName=CustomerId,AttributeType=S AttributeName=OrderDate,AttributeType=S AttributeName=Status,AttributeType=S \
    --key-schema AttributeName=CustomerId,KeyType=HASH AttributeName=OrderDate,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --global-secondary-indexes 'IndexName=ByStatus,KeySchema=[{AttributeName=Status,KeyType=HASH},{AttributeName=OrderDate,KeyType=RANGE}],Projection={ProjectionType=ALL}' ...
{
    "Table": "Orders",
    "Status": "ACTIVE",
    "Keys": [
        { "AttributeName": "CustomerId", "KeyType": "HASH" },
        { "AttributeName": "OrderDate",  "KeyType": "RANGE" }
    ],
    "Billing": "PAY_PER_REQUEST",
    "GSI": [ "ByStatus" ]
}
```

(Command wrapped and key objects condensed for reading; the exact text is in
the evidence file.) Only the three attributes used in keys are declared.
`Total`, `Items`, `GiftWrap` and `Address`, used below, are never declared
anywhere.

## Items

An **item** is one record, like a row, up to 400 KB in size. It is uniquely
identified by its primary key. Two items in the same table can have completely
different attributes:

```
$ aws dynamodb put-item --table-name Orders --item {"CustomerId":{"S":"C#101"},"OrderDate":{"S":"2026-09-30"},"Status":{"S":"SHIPPED"},"Total":{"N":"1499"},"Items":{"L":[{"S":"keyboard"},{"S":"mouse"}]}}
$ aws dynamodb put-item --table-name Orders --item {"CustomerId":{"S":"C#101"},"OrderDate":{"S":"2026-10-05"},"Status":{"S":"PENDING"},"Total":{"N":"299"},"GiftWrap":{"BOOL":true}}
$ aws dynamodb put-item --table-name Orders --item {"CustomerId":{"S":"C#202"},"OrderDate":{"S":"2026-10-01"},"Status":{"S":"PENDING"},"Total":{"N":"5400"},"Address":{"M":{"City":{"S":"Mohali"},"Pin":{"S":"140413"}}}}

$ aws dynamodb get-item --table-name Orders --key {"CustomerId":{"S":"C#101"},"OrderDate":{"S":"2026-10-05"}}
{
    "Item": {
        "CustomerId": { "S": "C#101" },
        "OrderDate": { "S": "2026-10-05" },
        "Status": { "S": "PENDING" },
        "Total": { "N": "299" },
        "GiftWrap": { "BOOL": true }
    }
}
```

(Output condensed: one attribute per line.)

## Attributes

An **attribute** is a name + typed value. The type tags seen above are:

| Tag | Type | Example |
|---|---|---|
| `S` | string | `"C#101"` |
| `N` | number (sent as a string, stored exactly) | `"1499"` |
| `BOOL` | boolean | `true` |
| `L` | list (mixed types allowed) | `[{"S":"keyboard"},{"S":"mouse"}]` |
| `M` | map, i.e. a nested document | `{"City":{"S":"Mohali"},"Pin":{"S":"140413"}}` |
| `SS` / `NS` / `BS` | sets of strings / numbers / binary | |
| `B`, `NULL` | binary, null | |

Key attributes must be scalar (`S`, `N` or `B`).

## Partition key

The **partition (hash) key** is hashed to decide **which physical partition**
stores the item. On its own it can be the whole primary key ("simple key"), in
which case it must be unique.

A good partition key has **high cardinality and evenly spread traffic**, e.g.
`CustomerId` or `DeviceId`. A bad one, like `Status` or `Country`, sends
everything to a few **hot partitions**, and those get throttled.

## Sort key

The **sort (range) key** is optional. With it, the primary key becomes
*composite*, and many items can share a partition key, **stored sorted by the
sort key**. That allows range queries within one partition: `=`, `<`, `>`,
`BETWEEN`, `begins_with`:

```
# all October orders of customer C#101 - one partition, sort-key prefix
$ aws dynamodb query --table-name Orders --key-condition-expression CustomerId = :c AND begins_with(OrderDate, :m) --expression-attribute-values {":c":{"S":"C#101"},":m":{"S":"2026-10"}} --query {...}
{
    "Count": 1,
    "Items": [
        [ "2026-10-05", "PENDING", "299" ]
    ]
}
```

C#101 has two orders, but only the one from 2026-10 matched. A query needs a
**partition key**, so "all PENDING orders" is impossible on the base table. A
**Global Secondary Index** with a different key makes that a query too:

```
$ aws dynamodb query --table-name Orders --index-name ByStatus --key-condition-expression #s = :p --expression-attribute-names {"#s":"Status"} --expression-attribute-values {":p":{"S":"PENDING"}} --query Items[].[CustomerId.S,OrderDate.S,Total.N] --output table
---------------------------------
|             Query             |
+-------+--------------+--------+
|  C#202|  2026-10-01  |  5400  |
|  C#101|  2026-10-05  |  299   |
+-------+--------------+--------+
```

**Conditional writes** give you safe concurrency without locks. "Mark as
shipped only if it is still PENDING" succeeds once and then refuses:

```
$ aws dynamodb update-item ... --update-expression SET #s = :new --condition-expression #s = :old ... --return-values UPDATED_NEW
{
    "Attributes": { "Status": { "S": "SHIPPED" } },
    ...
}
$ aws dynamodb update-item ... (same command again)
aws: [ERROR]: An error occurred (ConditionalCheckFailedException) when calling the UpdateItem operation: The conditional request failed

$ aws dynamodb scan --table-name Orders --query {ScannedCount:ScannedCount,Count:Count}
{
    "ScannedCount": 3,
    "Count": 3
}
```

`Scan` reads **every item** and charges for all of it. That's fine for 3 items,
but a red flag on a big table: add an index instead.

## DynamoDB use cases

- **Shopping carts, user sessions, user profiles:** key lookups at huge scale.
- **Gaming:** leaderboards and player state.
- **IoT / time-series:** `DeviceId` + timestamp sort key, with **TTL** to expire
  old readings.
- **Serverless back ends:** Lambda + API Gateway + DynamoDB, with no servers
  anywhere.
- **Event-driven pipelines:** DynamoDB Streams trigger Lambda on every change.
- **Terraform state locking** (the classic `dynamodb_table` backend option,
  now being replaced by S3-native locking).
- **Global apps:** Global Tables give multi-region, active-active replication.

---

# Part 2: RDS (Relational Database Service)

## Relational database

A relational database stores data in **tables of rows and columns with a fixed
schema**. Tables are linked by **foreign keys** and queried with **SQL**
(joins, aggregates, ad-hoc questions), with **ACID transactions** guaranteeing
consistency. RDS runs these engines for you as a **managed service**:

- **AWS handles:** provisioning, OS and engine patching, automated backups,
  failover, monitoring, storage scaling.
- **You handle:** schema, queries, indexes, users, parameter tuning.
- **You get no SSH/OS access.** That is the trade-off against running a
  database on EC2 yourself.

## Supported engines

| Engine | Notes |
|---|---|
| **PostgreSQL** | open source, very feature-rich (JSONB, extensions such as PostGIS) |
| **MySQL** | open source, the most widely deployed |
| **MariaDB** | community fork of MySQL |
| **Oracle** | bring-your-own-licence or licence-included |
| **Microsoft SQL Server** | Express / Web / Standard / Enterprise |
| **IBM Db2** | added 2023 |
| **Amazon Aurora** (MySQL- / PostgreSQL-compatible) | AWS's cloud-native engine: storage auto-grows to 128 TiB, is shared by up to 15 replicas, and keeps 6 copies across 3 AZs; Aurora Serverless v2 scales capacity automatically |

## DB instances

A **DB instance** is one database server. You choose:

- the engine and version,
- an **instance class** (`db.t4g.micro` is burstable and cheap; `db.m7g` is
  general purpose; `db.r7g` is memory-optimised),
- **storage**: gp3, or io1/io2 for guaranteed IOPS, with optional autoscaling,
  and
- the **DB subnet group**: the subnets RDS may place it in, which should be
  private subnets in at least two AZs.

```
$ aws rds create-db-subnet-group --db-subnet-group-name s18-db-subnets --db-subnet-group-description private subnets --subnet-ids subnet-798e9d94db9d4bbc5 subnet-09f3ce9d29d08fca1 ...
{
    "Name": "s18-db-subnets",
    "Subnets": [
        "ap-south-1a",
        "ap-south-1b"
    ]
}

$ aws rds create-db-instance --db-instance-identifier s18-postgres --engine postgres --engine-version 16.4 \
    --db-instance-class db.t4g.micro --allocated-storage 20 --storage-type gp3 \
    --master-username appadmin --manage-master-user-password \
    --db-subnet-group-name s18-db-subnets --vpc-security-group-ids sg-f15800655c674a131 \
    --no-publicly-accessible --multi-az --storage-encrypted \
    --backup-retention-period 7 --preferred-backup-window 20:00-21:00 --deletion-protection ...
{
    "Id": "s18-postgres",
    "Engine": "postgres",
    "Version": "16.4",
    "Class": "db.t4g.micro",
    "Status": "available",
    "MultiAZ": true,
    "Encrypted": true,
    "Public": false,
    "BackupDays": 7
}

$ aws rds describe-db-instances --db-instance-identifier s18-postgres --query DBInstances[0].{...}
{
    "Status": "available",
    "Endpoint": "s18-postgres.aaaaaaaaaa.ap-south-1.rds.amazonaws.com",
    "Port": 5432,
    "AZ": "ap-south-1a",
    "DeletionProtection": true
}
```

(Command wrapped for reading.) Applications connect to the **endpoint DNS
name**, never to an IP, because the IP behind the name changes on failover. On
real AWS the status would pass through `creating` → `backing-up` → `available`
over several minutes; the emulator reports `available` immediately.

## Security

Every line of the create command above is a security decision:

| Layer | Setting used | Why |
|---|---|---|
| Network placement | private subnet group, `--no-publicly-accessible` | no route from the internet to the DB at all |
| Firewall | SG allows 5432 **only from the app subnet 10.30.1.0/24** (in practice: from the app's SG) | only the app tier can even open a connection |
| Credentials | `--manage-master-user-password` | the master password is generated and rotated in **Secrets Manager**, never typed or committed |
| Encryption at rest | `--storage-encrypted` (KMS) | covers the volumes, backups, snapshots and replicas; can only be chosen at creation |
| Encryption in transit | `rds.force_ssl=1` parameter (Postgres) | rejects non-TLS clients |
| Identity | IAM database authentication (optional) | short-lived tokens instead of DB passwords |
| Accidents | `--deletion-protection` | see below |
| Audit | CloudTrail (API), engine logs to CloudWatch, Performance Insights | |

Deletion protection, tested:

```
$ aws rds delete-db-instance --db-instance-identifier s18-postgres --skip-final-snapshot
aws: [ERROR]: An error occurred (InvalidParameterCombination) when calling the DeleteDBInstance operation: Cannot delete protected DB Instance, please disable deletion protection and try again.
```

## Backups

- **Automated backups:**
  - a daily snapshot taken in the backup window, plus transaction logs shipped
    every ~5 minutes;
  - this enables **point-in-time restore** to any second within the retention
    period (1–35 days; 7 here);
  - they are deleted with the instance, unless you keep them.
- **Manual snapshots:** kept until **you** delete them; can be copied to other
  regions or accounts.
- **Final snapshot:** taken when an instance is deleted, unless you pass
  `--skip-final-snapshot`.
- A restore always creates a **new** instance with a new endpoint.

```
$ aws rds create-db-snapshot --db-instance-identifier s18-postgres --db-snapshot-identifier s18-before-migration ...
{
    "Snapshot": "s18-before-migration",
    "Status": "available",
    "Type": "manual",
    "Encrypted": true
}

$ aws rds modify-db-instance --db-instance-identifier s18-postgres --no-deletion-protection --apply-immediately ...
false
$ aws rds delete-db-instance --db-instance-identifier s18-postgres --final-db-snapshot-identifier s18-final ...
"deleting"

$ aws rds describe-db-snapshots --query DBSnapshots[].[DBSnapshotIdentifier,SnapshotType] --output table
+-----------------------+----------+
|  s18-before-migration |  manual  |
|  s18-final            |  manual  |
+-----------------------+----------+
```

The snapshot inherited `Encrypted: true` from the instance.

## Multi-AZ

`--multi-az` creates a **synchronous standby** in a second AZ, which is why the
subnet group spans `ap-south-1a` **and** `ap-south-1b`.

- Every write is committed on both copies before it is acknowledged.
- If the primary, its AZ or its storage fails (and also during patching or
  instance resizing), RDS **fails over automatically** in about 60–120 seconds
  by pointing the same endpoint DNS name at the standby.
- The standby **serves no reads**. It exists purely for **availability**.
- The *Multi-AZ DB cluster* variant has two **readable** standbys and fails
  over faster.

```
          endpoint s18-postgres.…rds.amazonaws.com
                         │
           ┌─────────────┴──────────────┐
   AZ ap-south-1a                 AZ ap-south-1b
   PRIMARY  ── synchronous ──►    STANDBY (no traffic)
      │       replication               ▲
      └────── failure ──► DNS flips ────┘
```

## Read replicas

A **read replica** is an **asynchronous** copy that **serves read-only
queries**. Its purpose is **scaling reads** (reports, analytics, read-heavy
pages), and each replica has its **own endpoint**.

- Up to 15 per source (engine-dependent).
- Can be in another AZ or **another region**, which also helps disaster
  recovery.
- Can be **promoted** to a standalone writable database.
- Because replication is asynchronous, a replica can lag behind the primary
  (replica lag).

```
$ aws rds create-db-instance-read-replica --db-instance-identifier s18-postgres-replica-1 --source-db-instance-identifier s18-postgres --db-instance-class db.t4g.micro ...
{
    "Id": "s18-postgres-replica-1",
    "Source": "s18-postgres"
}
$ aws rds describe-db-instances --db-instance-identifier s18-postgres --query DBInstances[0].ReadReplicaDBInstanceIdentifiers
[
    "s18-postgres-replica-1"
]
```

| | Multi-AZ standby | Read replica |
|---|---|---|
| Purpose | **availability** (failover) | **read scaling** (and DR if cross-region) |
| Replication | synchronous | asynchronous |
| Serves traffic | no | yes, reads only |
| Endpoint | same as primary | its own |
| Failover | automatic | manual promotion |

Two emulator quirks showed up during cleanup; they're kept in the evidence:

- The replica copied the source's deletion-protection flag.
- After the primary was deleted, deleting the replica returned
  `DBInstanceNotFound … s18-postgres`, yet the replica was already gone from
  `describe-db-instances`.

Everything was removed at the end (the instance list and snapshot list are empty).

## RDS use cases

- **Transactional (OLTP) back ends:** e-commerce orders, payments, banking,
  ERP/CRM. Anything with relationships and transactions.
- **Web/mobile apps on standard frameworks** (Django, Rails, Spring, Laravel)
  that expect SQL.
- **Lift-and-shift** of existing MySQL / PostgreSQL / Oracle / SQL Server
  databases without running the servers yourself.
- **Reporting** on read replicas, keeping the primary free for writes.
- **Multi-tenant SaaS** with schema-per-tenant or row-level security.

## DynamoDB or RDS?

| Choose **DynamoDB** when… | Choose **RDS** when… |
|---|---|
| access patterns are known and key-based | you need ad-hoc queries, joins, reporting |
| you need massive scale / unpredictable spikes with zero ops | data is relational, with integrity constraints |
| you're serverless (Lambda) | the app/framework expects SQL |
| you need single-digit-ms latency at any size | you need multi-row ACID transactions across tables (DynamoDB has transactions, but limited) |
