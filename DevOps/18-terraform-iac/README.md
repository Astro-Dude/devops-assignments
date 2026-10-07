# Terraform & Infrastructure as Code — Homework

Session 18. Two tasks:

1. **[`terraform-s3-demo/`](terraform-s3-demo/README.md):** an S3 bucket
   managed by Terraform through the full `init → fmt → validate → plan → apply
   → show → output → destroy` workflow, checked against the API with the AWS
   CLI.
2. **[`aws-services/`](aws-services/):** one README per AWS service (IAM, EC2,
   S3, VPC, DynamoDB & RDS) covering every point in the spec, each with a small
   hands-on run.

All command output in this folder is **real captured output**. Raw transcripts
are in [`evidence/`](evidence/) and in each service's `evidence/` folder.

---

## Where the "AWS" resources were created

**There is no AWS account behind this homework.** Everything was created
against a **local AWS API emulator** running in Docker on `localhost:4566`.

The plan was to use LocalStack, but the current `localstack/localstack` image
refuses to start without a licence token:

```
$ docker run --rm --name hw-localstack-try -p 4570:4566 localstack/localstack:latest
LocalStack version: 2026.9.1
...
Localstack returning with exit code 55. Reason: 
===============================================
License activation failed! 🔑❌
Reason: No credentials were found in the environment. Please set the LOCALSTACK_AUTH_TOKEN variable to a valid auth token. ...
[exit code: 55]
```

So the container `hw-localstack` runs **[moto](https://github.com/getmoto/moto)
in server mode** instead. Moto is an open-source AWS emulator that speaks the
same APIs:

```
$ docker run -d --name hw-localstack -p 4566:5000 -m 768m motoserver/moto:latest
$ docker ps --filter name=hw-localstack --format "{{.Names}}  {{.Image}}  {{.Status}}  {{.Ports}}"
hw-localstack  motoserver/moto:latest  Up 3 minutes  0.0.0.0:4566->5000/tcp, [::]:4566->5000/tcp
$ docker exec hw-localstack pip show moto | head -2
Name: moto
Version: 5.2.3.dev0
$ aws --endpoint-url http://localhost:4566 sts get-caller-identity
{
    "UserId": "AKIAIOSFODNN7EXAMPLE",
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:user/moto"
}
```

(Full transcript: [`evidence/s18-00-localstack-vs-moto.txt`](evidence/s18-00-localstack-vs-moto.txt).)
`123456789012` is the emulator's fake account ID.

What this means for the results:

| Works exactly like AWS | Differs from AWS |
|---|---|
| Terraform provider and AWS CLI calls, request/response formats, IDs, ARNs, validation errors | no real VMs boot, no packets flow, no PostgreSQL server runs behind RDS |
| S3 objects, versions, encryption headers, bucket policies (the TLS-deny policy was even enforced) | IAM policies are stored but not enforced; the IAM policy simulator is not implemented |
| DynamoDB items, queries, GSIs, conditional writes | lifecycle rules are stored but never run |
| | small quirks, e.g. tags sent at bucket creation are ignored (a drift that Terraform caught and fixed, see the S3 demo §5b) |

Each README marks what was hands-on and what is conceptual only.

### Pointing the same Terraform at real AWS

Only the provider block changes. Emulator version (`terraform-s3-demo/provider.tf`):

```hcl
provider "aws" {
  region                      = var.aws_region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  s3_use_path_style           = true
  endpoints {
    s3  = "http://localhost:4566"
    sts = "http://localhost:4566"
    iam = "http://localhost:4566"
  }
}
```

Real AWS version, after `aws configure` / `export AWS_PROFILE=…`:

```hcl
provider "aws" {
  region = var.aws_region
}
```

For the AWS CLI, drop `--endpoint-url http://localhost:4566`.

---

## Tools

```
$ terraform version
Terraform v1.16.4
on darwin_arm64
$ aws --version
aws-cli/2.36.48 Python/3.14.7 Darwin/27.0.0 source/arm64
```

Terraform was installed with
`brew tap hashicorp/tap && brew install hashicorp/tap/terraform`. The AWS
provider resolved to `hashicorp/aws v6.67.0`.

---

## Task 1: Terraform S3 demo

[`terraform-s3-demo/`](terraform-s3-demo/) contains exactly the requested files
(`main.tf`, `variables.tf`, `outputs.tf`, `provider.tf`, `terraform.tfvars`,
`README.md`), plus `.gitignore` and the provider lock file.

| Step | Result | Evidence |
|---|---|---|
| `terraform init` | `hashicorp/aws v6.67.0` installed, lock file written | [s18-01-init.txt](evidence/s18-01-init.txt) |
| `terraform fmt` | fixed a deliberately mis-aligned `terraform.tfvars` | [s18-02-fmt-validate.txt](evidence/s18-02-fmt-validate.txt) |
| `terraform validate` | `Success! The configuration is valid.` | same |
| `terraform plan` | `Plan: 5 to add, 0 to change, 0 to destroy.` | [s18-03-plan.txt](evidence/s18-03-plan.txt) |
| `terraform apply` | `Apply complete! Resources: 5 added` | [s18-04-apply.txt](evidence/s18-04-apply.txt) |
| drift → re-apply | emulator dropped the tags; plan caught it, apply fixed it | [s18-04b-drift.txt](evidence/s18-04b-drift.txt) |
| `terraform show` | full state, incl. object `server_side_encryption = "AES256"` | [s18-05-show.txt](evidence/s18-05-show.txt) |
| `terraform output` | name / ARN / region / versioning / URL | [s18-06-output-state.txt](evidence/s18-06-output-state.txt) |
| AWS CLI check | bucket, versioning, encryption, public-access block, tags, object, 2 versions | [s18-07-aws-cli-verify.txt](evidence/s18-07-aws-cli-verify.txt) |
| out-of-band change | `plan` noticed a CLI overwrite (partly) | [s18-07b-out-of-band-plan.txt](evidence/s18-07b-out-of-band-plan.txt) |
| `terraform destroy` | `Destroy complete! Resources: 5 destroyed.`, `head-bucket` → 404 | [s18-08-destroy.txt](evidence/s18-08-destroy.txt) |

The step-by-step walkthrough is in the
[S3 demo README](terraform-s3-demo/README.md).

## Task 2: AWS services research

| # | Service | Spec points covered | Hands-on on the emulator |
|---|---|---|---|
| 01 | [IAM](aws-services/01-iam/README.md) | what is IAM, users, groups, roles, policies, permissions, least privilege, best practices, use cases | group + least-privilege policy + user; EC2 role + instance profile + `assume-role`; password policy |
| 02 | [EC2](aws-services/02-ec2/README.md) | what is EC2, AMI, instance types, key pairs, security groups, EBS, public vs private IP, lifecycle, use cases | AMI lookup, type comparison, key pair, SG, launch, EBS attach + snapshot, stop/start/terminate, volume fate |
| 03 | [S3](aws-services/03-s3/README.md) | what is S3, buckets, objects, storage classes, versioning, lifecycle, encryption, bucket policies, use cases | 3 storage classes, prefixes, delete marker + undelete, lifecycle rules, SSE, TLS-only bucket policy (enforced), presigned URL |
| 04 | [VPC](aws-services/04-vpc/README.md) | what is VPC, CIDR, subnets, route tables, IGW, NAT GW, security groups, NACLs, public vs private | CIDR maths in Python; VPC with 2 public + 2 private subnets, IGW, NAT, 2 route tables, SG-to-SG rule, NACL with deny |
| 05 | [DynamoDB & RDS](aws-services/05-dynamodb-rds/README.md) | NoSQL, tables, items, attributes, partition/sort key, use cases; relational, engines, instances, security, backups, Multi-AZ, read replicas, use cases | table + GSI, put/get/query/conditional update/scan; Multi-AZ encrypted Postgres, read replica, snapshots, deletion protection |

Everything created in Task 2 was deleted again at the end of each run.

---

## Terraform concepts used in this session

| Concept | Where it appears |
|---|---|
| **IaC:** infrastructure described in version-controlled text, applied by a tool | this whole folder; `git diff` shows infrastructure changes |
| **Declarative:** you describe the end state, and Terraform computes the steps | `main.tf` never says "create"; `plan` decides create / update / destroy |
| **Architecture:** Terraform core + **providers** (plugins that call APIs) + **state** | `required_providers` in `provider.tf`; `.terraform/` holds the downloaded plugin |
| **Resources** `resource "<type>" "<name>"` | 5 resources in `main.tf`, addressed as `aws_s3_bucket.demo` etc. |
| **Variables** with types, defaults, validation; values from `terraform.tfvars` | `variables.tf`, `terraform.tfvars` |
| **Outputs** | `outputs.tf`, `terraform output -raw / -json` |
| **Dependencies:** implicit (references) and explicit (`depends_on`) | `bucket = aws_s3_bucket.demo.id`; `depends_on` on `aws_s3_object.hello` |
| **State:** Terraform's record mapping config ↔ real IDs | `terraform show`, `terraform state list`; `*.tfstate` is git-ignored |
| **Drift:** reality ≠ state/config, detected by plan's refresh | S3 demo §5b and §8 |
| **Destroy:** delete everything in the state, in reverse dependency order | S3 demo §9 |

[Session 19](../19-cloud-terraform/README.md) builds a full VPC → subnets →
IGW → security group → EC2 → S3 stack on the same emulator.
