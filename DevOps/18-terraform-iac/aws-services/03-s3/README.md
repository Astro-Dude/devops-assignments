# 03 · S3: Simple Storage Service (Storage)

> **Hands-on environment:** run against the local AWS emulator (moto server on
> `localhost:4566`, see the [Session 18 README](../../README.md)), not a real
> AWS account. Transcripts:
> [`evidence/s3-handson.txt`](evidence/s3-handson.txt) and
> [`evidence/s3-handson-policy-enforced.txt`](evidence/s3-handson-policy-enforced.txt).
> `aws` below means `aws --endpoint-url http://localhost:4566`; local file
> paths in the transcript were shortened. The Terraform-managed bucket from
> Task 1 is in [`../../terraform-s3-demo/`](../../terraform-s3-demo/README.md).

## What is S3?

S3 is **object storage** behind an HTTPS API. You `PUT` a blob of bytes under a
name and `GET` it back by that name. It is not a file system (no real
directories, no in-place edits, no locking) and not a block device (you can't
mount it as a disk). In exchange it gives you:

- **Practically unlimited** capacity; single objects up to 50 TB.
- **11 nines (99.999999999%) durability:** data is stored redundantly across at
  least 3 AZs (except One Zone classes).
- **Strong read-after-write consistency** for every PUT and DELETE (since
  December 2020).
- Pay only for GB stored, requests made and data transferred out.

## Buckets

A **bucket** is the top-level container. It has:

- a **globally unique** name (3–63 chars, lowercase letters, digits and
  hyphens; DNS-compatible),
- a **home region**, which is where the data physically lives, and
- its own settings: versioning, encryption, lifecycle, policy, public-access
  block, logging, replication, tags.

```
$ aws s3api create-bucket --bucket astro-dude-s18-research --create-bucket-configuration LocationConstraint=ap-south-1
{
    "Location": "/astro-dude-s18-research"
}
```

Outside `us-east-1` the region must be passed as a `LocationConstraint`. By
default an account can have 10,000 buckets.

## Objects

An object is **key + data + metadata (+ version ID)**. The key is the object's
whole name. The "folders" shown in the console are just a `/` convention in
key names, which the API exposes as **prefixes**:

```
$ aws s3api list-objects-v2 --bucket astro-dude-s18-research --query Contents[].[Key,Size,StorageClass] --output table
+--------------------------+-----+---------------+
|  archive/2019-audit.txt  |  9  |  GLACIER      |
|  logs/app-2026-07-01.log |  9  |  STANDARD_IA  |
|  reports/2026/q3.txt     |  12 |  STANDARD     |
+--------------------------+-----+---------------+

$ aws s3api list-objects-v2 --bucket astro-dude-s18-research --prefix reports/ --delimiter / --query CommonPrefixes
[
    {
        "Prefix": "reports/2026/"
    }
]

$ aws s3api head-object --bucket astro-dude-s18-research --key reports/2026/q3.txt --query {...}
{
    "ContentLength": 12,
    "ContentType": "binary/octet-stream",
    "ETag": "\"856175bbfb75a5c7264b14141237836f\"",
    "LastModified": "2026-10-07T14:19:42+00:00"
}
```

- `ETag` is the MD5 of the content for single-part uploads.
- Objects are **immutable**: "editing" one means uploading a whole new object
  under the same key.
- Uploads larger than about 100 MB should use **multipart upload**.
- **Pre-signed URLs** give someone temporary access to a single object without
  any AWS credentials:

```
$ aws s3 presign s3://astro-dude-s18-research/reports/2026/q3.txt --expires-in 300
http://localhost:4566/astro-dude-s18-research/reports/2026/q3.txt?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=test%2F20261007%2Fap-south-1%2Fs3%2Faws4_request&X-Amz-Date=20261007T141946Z&X-Amz-Expires=300&X-Amz-SignedHeaders=host&X-Amz-Signature=<redacted>
```

## Storage classes

The class is set **per object**. You trade retrieval speed, retrieval fees and
minimum storage duration for a lower price per GB:

| Class | Retrieval | Min. duration | Good for |
|---|---|---|---|
| **STANDARD** | ms | none | hot data, websites, anything read often |
| **INTELLIGENT_TIERING** | ms (archive tiers optional) | none | unknown / changing access patterns, moves objects automatically |
| **STANDARD_IA** (Infrequent Access) | ms, + per-GB retrieval fee | 30 days | backups, older logs read occasionally |
| **ONEZONE_IA** | ms | 30 days | re-creatable data; lives in **one** AZ |
| **GLACIER_IR** (Instant Retrieval) | ms | 90 days | archives that still need instant reads (e.g. medical images) |
| **GLACIER** (Flexible Retrieval) | minutes – 12 h; must **restore** first | 90 days | archives, DR copies |
| **DEEP_ARCHIVE** | 12 – 48 h | 180 days | compliance data kept 7–10 years; cheapest |

The three objects above were uploaded with `--storage-class STANDARD`,
`STANDARD_IA` and `GLACIER`. Usually you don't pick by hand at upload; a
**lifecycle policy** moves objects down the tiers as they age.

## Versioning

With versioning **Enabled**, every PUT creates a new version, and a DELETE
does not erase data: it adds a **delete marker** on top. A bucket is in one of
three states: *unversioned* (the default), *Enabled*, or *Suspended*. Once
enabled, it can never return to unversioned.

```
$ aws s3api put-bucket-versioning --bucket astro-dude-s18-research --versioning-configuration Status=Enabled
$ aws s3api put-object --bucket astro-dude-s18-research --key reports/2026/q3.txt --body r.txt --query VersionId
"816bf178-b1dc-44fe-9a6a-ebe0c58bf2b5"

$ aws s3api delete-object --bucket astro-dude-s18-research --key reports/2026/q3.txt
{
    "DeleteMarker": true,
    "VersionId": "bdcbc386-8e15-432b-b3a3-38b3f1a90c01"
}

$ aws s3api list-object-versions --bucket astro-dude-s18-research --prefix reports/ --query {...}
{
    "Versions": [
        [ "reports/2026/q3.txt", "816bf178-b1dc-44fe-9a6a-ebe0c58bf2b5", false, 15 ],
        [ "reports/2026/q3.txt", "null", false, 12 ]
    ],
    "DeleteMarkers": [
        [ "reports/2026/q3.txt", "bdcbc386-8e15-432b-b3a3-38b3f1a90c01", true ]
    ]
}
```

(The JSON arrays are condensed onto single lines; see the evidence file.) The
key looks deleted, but both versions are still there. The copy uploaded
*before* versioning was switched on has version ID **`null`**. Deleting the
delete marker "undeletes" the object:

```
$ aws s3api delete-object --bucket astro-dude-s18-research --key reports/2026/q3.txt --version-id bdcbc386-8e15-432b-b3a3-38b3f1a90c01
$ aws s3 cp s3://astro-dude-s18-research/reports/2026/q3.txt -
report body v2
```

Versioning is what protects you from accidental overwrites, deletes and
ransomware. **MFA Delete** and **Object Lock** (WORM) go further. Every
version is billed, so pair versioning with a lifecycle rule for noncurrent
versions.

## Lifecycle policies

Rules that automatically **transition** objects to cheaper classes, or
**expire** them (delete them), based on age, prefix or tag. Policy used here
([`lifecycle.json`](lifecycle.json)):

```json
{
  "Rules": [
    { "ID": "logs-tiering", "Status": "Enabled", "Filter": { "Prefix": "logs/" },
      "Transitions": [ { "Days": 30,  "StorageClass": "STANDARD_IA" },
                       { "Days": 90,  "StorageClass": "GLACIER_IR" },
                       { "Days": 180, "StorageClass": "DEEP_ARCHIVE" } ],
      "Expiration": { "Days": 365 } },
    { "ID": "trim-old-versions", "Status": "Enabled", "Filter": {},
      "NoncurrentVersionExpiration": { "NoncurrentDays": 30 },
      "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 7 } }
  ]
}
```

```
$ aws s3api put-bucket-lifecycle-configuration --bucket astro-dude-s18-research --lifecycle-configuration file://lifecycle.json
$ aws s3api get-bucket-lifecycle-configuration --bucket astro-dude-s18-research --query Rules[].{ID:ID,Status:Status,Transitions:...,Expiration:...}
[
    { "ID": "logs-tiering", "Status": "Enabled",
      "Transitions": [ [30, "STANDARD_IA"], [90, "GLACIER_IR"], [180, "DEEP_ARCHIVE"] ],
      "Expiration": 365 },
    { "ID": "trim-old-versions", "Status": "Enabled", "Transitions": null, "Expiration": null }
]
```

(Output condensed as above.) A log written today will sit in STANDARD for 30
days, IA until day 90, Glacier IR until day 180, Deep Archive until day 365,
and is then deleted. Rule 2 removes old versions 30 days after they are
replaced, and cleans up abandoned multipart uploads, which otherwise cost
money invisibly. The emulator stores lifecycle rules but does not run them, so
the time-based transitions themselves are **conceptual** here.

## Encryption

- **At rest.** Since January 2023 every new object is encrypted by default.
  The choices are:
  - **SSE-S3** (AES-256, keys managed by S3). This is the default.
  - **SSE-KMS:** keys in AWS KMS. Gives you key policies, CloudTrail logs of
    every key use, and the ability to revoke access by disabling the key. Turn
    on **S3 Bucket Keys** to cut KMS request costs.
  - **DSSE-KMS:** two layers of encryption, for compliance.
  - **SSE-C:** you send the key with every request.
  - **Client-side:** encrypt before uploading.
- **In transit.** Use HTTPS. Enforce it with a bucket policy that denies
  `aws:SecureTransport = false` (next section).

```
$ aws s3api put-bucket-encryption --bucket astro-dude-s18-research --server-side-encryption-configuration {"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}
$ aws s3api put-object --bucket astro-dude-s18-research --key reports/2026/q4.txt --body r.txt --query {ServerSideEncryption:ServerSideEncryption}
{
    "ServerSideEncryption": "AES256"
}
```

In Terraform this is `aws_s3_bucket_server_side_encryption_configuration`, as
used in the [S3 demo](../../terraform-s3-demo/main.tf).

## Bucket policies

A **resource-based** IAM policy attached to the bucket, with a `Principal`. It
can grant access to other accounts, roles or services, or **deny** things for
everyone. Policy used here ([`bucket-policy.json`](bucket-policy.json)):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
      "Resource": ["arn:aws:s3:::astro-dude-s18-research", "arn:aws:s3:::astro-dude-s18-research/*"],
      "Condition": { "Bool": { "aws:SecureTransport": "false" } } },
    { "Sid": "AllowAppRoleRead", "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::123456789012:role/app-server-role" },
      "Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::astro-dude-s18-research/reports/*" }
  ]
}
```

The emulator **enforced the first statement**, and it did so on me. The
emulator endpoint is plain `http://`, so every request has
`aws:SecureTransport = false`, and once the policy was attached, even the
bucket owner was refused:

```
$ aws s3 rb s3://astro-dude-s18-research --force
delete failed: s3://astro-dude-s18-research/logs/app-2026-07-01.log An error occurred (403) when calling the DeleteObject operation: Forbidden
...
$ aws s3api get-object --bucket astro-dude-s18-research --key reports/2026/q3.txt /dev/stdout
aws: [ERROR]: An error occurred (403) when calling the GetObject operation: Forbidden

$ aws s3api delete-bucket-policy --bucket astro-dude-s18-research
$ aws s3api get-object --bucket astro-dude-s18-research --key reports/2026/q3.txt /dev/stdout --query ContentLength
report body v2
15
```

That is exactly the point of a Deny: **explicit deny beats every allow,
including the owner's**. On real AWS, the same policy blocks plain-HTTP clients
while HTTPS clients work normally. Bucket policies vs. other controls:

- **Bucket policy:** a JSON policy on the bucket. Use it for cross-account
  access, enforcing TLS or encryption, or restricting to a VPC endpoint.
- **ACLs:** legacy. Disabled by default ("Bucket owner enforced"); avoid them.
- **Block Public Access:** an account/bucket-level override that wins over any
  policy or ACL that would make data public. Keep it on unless you are
  deliberately hosting public content.

### Clean-up lesson

`aws s3 rb --force` only deletes **current** versions, so a versioned bucket
still counts as "not empty":

```
remove_bucket failed: s3://astro-dude-s18-research An error occurred (BucketNotEmpty) ...
$ aws s3api list-object-versions --bucket astro-dude-s18-research --query {Versions:length(...),DeleteMarkers:length(...)}
{
    "Versions": 5,
    "DeleteMarkers": 4
}
```

Every version and delete marker had to be deleted by version ID before
`delete-bucket` succeeded. Terraform's `force_destroy = true` does the same loop
for you.

## Common use cases

- **Static website / SPA hosting** behind CloudFront.
- **Data lake:** raw and processed data queried in place by Athena, EMR,
  Redshift Spectrum.
- **Backups and archives:** database dumps, EBS snapshots (stored in S3
  internally), Glacier for compliance retention.
- **Logs:** CloudTrail, ALB and VPC Flow Logs all write to S3.
- **Application uploads:** user images and documents via pre-signed URLs.
- **Artifacts:** build outputs, Docker layers (ECR is backed by S3), ML models.
- **Terraform remote state:** an S3 backend with versioning, encryption and
  locking.

```hcl
terraform {
  backend "s3" {
    bucket       = "astro-dude-tf-state"
    key          = "session19/terraform.tfstate"
    region       = "ap-south-1"
    encrypt      = true
    use_lockfile = true   # S3-native state locking (Terraform >= 1.10)
  }
}
```
