# Terraform S3 Demo

Session 18, Task 1. Creates an S3 bucket with Terraform and runs the full
workflow: `init`, `fmt`, `validate`, `plan`, `apply`, `show`, `output` and
`destroy`.

> **Where these resources were created:** this ran against a **local AWS
> emulator**, not a real AWS account (there are no AWS credentials). The plan
> was LocalStack, but the current `localstack/localstack` image exits with
> `License activation failed` unless it has an auth token (captured in
> [`../evidence/s18-00-localstack-vs-moto.txt`](../evidence/s18-00-localstack-vs-moto.txt)).
> So the container `hw-localstack` runs **[moto](https://github.com/getmoto/moto)
> in server mode** (`motoserver/moto`, moto 5.2.3) on `localhost:4566`. It is
> also an open-source AWS API emulator, so Terraform and the AWS CLI talk to it
> exactly as they would to AWS.
> Every output below is real and was captured on that emulator.

## Files

```
terraform-s3-demo/
├── provider.tf          terraform{} block (version pins) + aws provider (emulator endpoints)
├── variables.tf         input variables, with a validation rule on bucket_name
├── terraform.tfvars     values for those variables
├── main.tf              bucket + versioning + encryption + public-access-block + one object
├── outputs.tf           bucket name / ARN / region / versioning / object URL
├── .terraform.lock.hcl  provider version lock, written by `terraform init` (committed on purpose)
├── .gitignore           keeps .terraform/ and *.tfstate out of git
└── README.md
```

### What gets created (`main.tf`)

| Resource | Purpose |
|---|---|
| `aws_s3_bucket.demo` | the bucket `astro-dude-24bcs10151-s18-demo`, with tags |
| `aws_s3_bucket_versioning.demo` | versioning **Enabled**: overwrites keep the older copies |
| `aws_s3_bucket_server_side_encryption_configuration.demo` | default encryption at rest, SSE-S3 (AES-256) |
| `aws_s3_bucket_public_access_block.demo` | all four "block public access" switches on |
| `aws_s3_object.hello` | a `hello.txt` object, so the bucket has content |

Since AWS provider v4, versioning, encryption and the public-access block are
**separate resources** instead of blocks inside `aws_s3_bucket`. Each one refers
to `aws_s3_bucket.demo.id`, and that reference is an **implicit dependency**:
Terraform creates the bucket first. `aws_s3_object.hello` also has an
**explicit** `depends_on` on the encryption config, so the object is only
uploaded once encryption is on.

### Provider: emulator vs. real AWS

`provider.tf` as used here:

```hcl
provider "aws" {
  region = var.aws_region                     # ap-south-1

  access_key                  = "test"        # dummy; the emulator accepts anything
  secret_key                  = "test"
  skip_credentials_validation = true          # don't call STS to check the keys
  skip_requesting_account_id  = true          # don't look up the account ID
  skip_metadata_api_check     = true          # don't probe the EC2 instance metadata service
  s3_use_path_style           = true          # http://host:4566/bucket/key instead of bucket.host

  endpoints {
    s3  = var.aws_endpoint                    # http://localhost:4566
    sts = var.aws_endpoint
    iam = var.aws_endpoint
  }

  default_tags { tags = { ManagedBy = "Terraform", Owner = var.owner } }
}
```

To create the same bucket in **real AWS**, run `aws configure` (or export
`AWS_PROFILE`), then cut the provider down to:

```hcl
provider "aws" {
  region = var.aws_region
  default_tags { tags = { ManagedBy = "Terraform", Owner = var.owner } }
}
```

Nothing in `main.tf`, `variables.tf` or `outputs.tf` has to change.

---

## Workflow

Setup:

```bash
brew tap hashicorp/tap && brew install hashicorp/tap/terraform
docker run -d --name hw-localstack -p 4566:5000 motoserver/moto:latest
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=ap-south-1   # for the aws CLI only
```

### 1. `terraform init`

Downloads the providers named in `required_providers` into `.terraform/` and
writes `.terraform.lock.hcl`.

```
$ terraform version
Terraform v1.16.4
on darwin_arm64

$ terraform init -no-color
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

`~> 6.0` allows any 6.x release, and init picked the newest one, 6.67.0. The
lock file pins that exact version and its hashes, so everyone who clones the
repo gets the same provider. That's why it is committed.

### 2. `terraform fmt`

I wrote `terraform.tfvars` with its `=` signs **out of line on purpose**, so
`fmt` would have something to fix:

```
$ terraform fmt -check -diff -no-color
terraform.tfvars
--- old/terraform.tfvars
+++ new/terraform.tfvars
@@ -1,4 +1,4 @@
-bucket_name = "astro-dude-24bcs10151-s18-demo"
-environment = "dev"
-owner = "shaurya-verma-24bcs10151"
+bucket_name       = "astro-dude-24bcs10151-s18-demo"
+environment       = "dev"
+owner             = "shaurya-verma-24bcs10151"
 enable_versioning = true
[exit code: 3]

$ terraform fmt
terraform.tfvars

$ terraform fmt -check
[exit code: 0]
```

`fmt -check` exits non-zero when a file needs formatting, which makes it useful
as a CI gate. Plain `fmt` rewrites the files and prints the names of the ones it
changed.

### 3. `terraform validate`

```
$ terraform validate -no-color
Success! The configuration is valid.
```

`validate` checks syntax, types and references without contacting any API.
The custom `validation` block on `bucket_name` is enforced when variable values
are known, which happens at plan time.

### 4. `terraform plan`

The full plan is in [`../evidence/s18-03-plan.txt`](../evidence/s18-03-plan.txt).
Excerpt:

```
Terraform will perform the following actions:

  # aws_s3_bucket.demo will be created
  + resource "aws_s3_bucket" "demo" {
      + arn                         = (known after apply)
      + bucket                      = "astro-dude-24bcs10151-s18-demo"
      + force_destroy               = true
      + region                      = "ap-south-1"
      + tags                        = {
          + "Environment" = "dev"
          + "Name"        = "astro-dude-24bcs10151-s18-demo"
          + "Project"     = "Session18-S3-Demo"
        }
      + tags_all                    = {
          + "Environment" = "dev"
          + "ManagedBy"   = "Terraform"
          + "Name"        = "astro-dude-24bcs10151-s18-demo"
          + "Owner"       = "shaurya-verma-24bcs10151"
          + "Project"     = "Session18-S3-Demo"
        }
      ...
  # aws_s3_bucket_public_access_block.demo will be created
  # aws_s3_bucket_server_side_encryption_configuration.demo will be created
  # aws_s3_bucket_versioning.demo will be created
  # aws_s3_object.hello will be created

Plan: 5 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + bucket_arn        = (known after apply)
  + bucket_name       = "astro-dude-24bcs10151-s18-demo"
  + bucket_region     = "ap-south-1"
  + object_url        = "http://localhost:4566/astro-dude-24bcs10151-s18-demo/hello.txt"
  + versioning_status = "Enabled"
```

`+` means create. `(known after apply)` marks values that only the API can
return, such as the ARN. `tags_all` is `tags` merged with the provider's
`default_tags`.

### 5. `terraform apply`

```
$ terraform apply -no-color      # typed "yes" at the prompt
...
Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value: 
aws_s3_bucket.demo: Creating...
aws_s3_bucket.demo: Creation complete after 0s [id=astro-dude-24bcs10151-s18-demo]
aws_s3_bucket_public_access_block.demo: Creating...
aws_s3_bucket_versioning.demo: Creating...
aws_s3_bucket_server_side_encryption_configuration.demo: Creating...
aws_s3_bucket_server_side_encryption_configuration.demo: Creation complete after 0s [id=astro-dude-24bcs10151-s18-demo]
aws_s3_bucket_public_access_block.demo: Creation complete after 0s [id=astro-dude-24bcs10151-s18-demo]
aws_s3_object.hello: Creating...
aws_s3_object.hello: Creation complete after 0s [id=astro-dude-24bcs10151-s18-demo/hello.txt]
aws_s3_bucket_versioning.demo: Creation complete after 1s [id=astro-dude-24bcs10151-s18-demo]

Apply complete! Resources: 5 added, 0 changed, 0 destroyed.

Outputs:

bucket_arn = "arn:aws:s3:::astro-dude-24bcs10151-s18-demo"
bucket_name = "astro-dude-24bcs10151-s18-demo"
bucket_region = "ap-south-1"
object_url = "http://localhost:4566/astro-dude-24bcs10151-s18-demo/hello.txt"
versioning_status = "Enabled"
```

The order follows the dependency graph:

1. The bucket is created first.
2. Its three settings resources are then created **in parallel**.
3. `hello.txt` starts only after the encryption config has finished. That is
   the `depends_on` at work: `hello.txt` begins before versioning completes,
   because it has no dependency on versioning.

#### 5b. A real drift moment

The next `plan` was not clean. Moto ignores tags sent inside the
CreateBucket call, so on refresh Terraform found the bucket untagged:

```
$ terraform plan -no-color -detailed-exitcode
  # aws_s3_bucket.demo will be updated in-place
  ~ resource "aws_s3_bucket" "demo" {
        id                          = "astro-dude-24bcs10151-s18-demo"
      ~ tags                        = {
          + "Environment" = "dev"
          + "Name"        = "astro-dude-24bcs10151-s18-demo"
          + "Project"     = "Session18-S3-Demo"
        }
      ...
Plan: 0 to add, 1 to change, 0 to destroy.
[exit code: 2]

$ terraform apply -auto-approve -no-color
aws_s3_bucket.demo: Modifying... [id=astro-dude-24bcs10151-s18-demo]
aws_s3_bucket.demo: Modifications complete after 0s [id=astro-dude-24bcs10151-s18-demo]

Apply complete! Resources: 0 added, 1 changed, 0 destroyed.

$ terraform plan -no-color -detailed-exitcode
No changes. Your infrastructure matches the configuration.
[exit code: 0]
```

This is an emulator quirk; real S3 keeps tags sent at creation. It is still a
fair example of what `plan` is for: Terraform compares the **real** resource
with the configuration, finds the difference (**drift**), and a single apply
corrects it. `-detailed-exitcode` returns 2 when there are changes and 0 when
there are none, which is how a scheduled CI job can detect drift. Full
transcript: [`../evidence/s18-04b-drift.txt`](../evidence/s18-04b-drift.txt).

### 6. `terraform show`

`show` prints the **state**: what Terraform recorded about every resource after
apply, including values that were "known after apply" in the plan. Full output
in [`../evidence/s18-05-show.txt`](../evidence/s18-05-show.txt). Two excerpts:

```
# aws_s3_bucket_versioning.demo:
resource "aws_s3_bucket_versioning" "demo" {
    bucket                = "astro-dude-24bcs10151-s18-demo"
    id                    = "astro-dude-24bcs10151-s18-demo"
    region                = "ap-south-1"

    versioning_configuration {
        mfa_delete = "Disabled"
        status     = "Enabled"
    }
}

# aws_s3_object.hello:
resource "aws_s3_object" "hello" {
    arn                           = "arn:aws:s3:::astro-dude-24bcs10151-s18-demo/hello.txt"
    content_type                  = "text/plain"
    etag                          = "dcffcbc6416e209474a1aeae6c79b82b"
    key                           = "hello.txt"
    server_side_encryption        = "AES256"
    storage_class                 = "STANDARD"
    version_id                    = "0af8f759-2e89-435e-89fc-1aba7039dfa1"
    ...
}
```

The object came back with `server_side_encryption = "AES256"` even though the
object resource never asked for encryption: the bucket's default encryption was
applied to it. It also has a `version_id`, because versioning was on.

### 7. `terraform output`

```
$ terraform output
bucket_arn = "arn:aws:s3:::astro-dude-24bcs10151-s18-demo"
bucket_name = "astro-dude-24bcs10151-s18-demo"
bucket_region = "ap-south-1"
object_url = "http://localhost:4566/astro-dude-24bcs10151-s18-demo/hello.txt"
versioning_status = "Enabled"

$ terraform output -raw bucket_name
astro-dude-24bcs10151-s18-demo

$ terraform output -json versioning_status
"Enabled"

$ terraform state list
aws_s3_bucket.demo
aws_s3_bucket_public_access_block.demo
aws_s3_bucket_server_side_encryption_configuration.demo
aws_s3_bucket_versioning.demo
aws_s3_object.hello
```

`-raw` prints the bare string, for use in shell scripts. `-json` is for tools.

### 8. Checking the emulator directly (between apply and destroy)

Terraform reporting success is not the same as the bucket existing, so I
queried the S3 API with the AWS CLI
([`../evidence/s18-07-aws-cli-verify.txt`](../evidence/s18-07-aws-cli-verify.txt)):

```
$ aws --endpoint-url http://localhost:4566 s3 ls
2026-10-07 19:45:22 astro-dude-24bcs10151-s18-demo

$ aws --endpoint-url http://localhost:4566 s3api head-bucket --bucket astro-dude-24bcs10151-s18-demo
{
    "BucketRegion": "ap-south-1"
}

$ aws --endpoint-url http://localhost:4566 s3api get-bucket-versioning --bucket astro-dude-24bcs10151-s18-demo
{
    "Status": "Enabled"
}

$ aws --endpoint-url http://localhost:4566 s3api get-bucket-encryption --bucket astro-dude-24bcs10151-s18-demo
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

$ aws --endpoint-url http://localhost:4566 s3api get-public-access-block --bucket astro-dude-24bcs10151-s18-demo
{
    "PublicAccessBlockConfiguration": {
        "BlockPublicAcls": true,
        "IgnorePublicAcls": true,
        "BlockPublicPolicy": true,
        "RestrictPublicBuckets": true
    }
}

$ aws --endpoint-url http://localhost:4566 s3 cp s3://astro-dude-24bcs10151-s18-demo/hello.txt -
Created by Terraform for Session 18 - shaurya-verma-24bcs10151
```

Tags are also present (`get-bucket-tagging` is in the evidence file). To
exercise versioning, I overwrote `hello.txt` from the CLI. Both versions remain:

```
$ aws --endpoint-url http://localhost:4566 s3api list-object-versions --bucket astro-dude-24bcs10151-s18-demo --query Versions[].{Key:Key,VersionId:VersionId,IsLatest:IsLatest,Size:Size} --output table
---------------------------------------------------------------------------
|                           ListObjectVersions                            |
+----------+------------+-------+-----------------------------------------+
| IsLatest |    Key     | Size  |                VersionId                |
+----------+------------+-------+-----------------------------------------+
|  True    |  hello.txt |  24   |  622d98bf-eb9f-4a78-b836-6edc4bd67b83   |
|  False   |  hello.txt |  63   |  0af8f759-2e89-435e-89fc-1aba7039dfa1   |
+----------+------------+-------+-----------------------------------------+
```

The older 63-byte version is the one Terraform wrote (`version_id` matches the
`terraform show` output above).

That CLI upload was a change made **outside Terraform**. The next `plan`
detected it, but only partly
([`../evidence/s18-07b-out-of-band-plan.txt`](../evidence/s18-07b-out-of-band-plan.txt)):

```
  # aws_s3_object.hello will be updated in-place
  ~ resource "aws_s3_object" "hello" {
        id                            = "astro-dude-24bcs10151-s18-demo/hello.txt"
        tags                          = {}
      ~ tags_all                      = {
          + "ManagedBy" = "Terraform"
          + "Owner"     = "shaurya-verma-24bcs10151"
        }
        # (26 unchanged attributes hidden)
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

Terraform saw that the new current version had lost its tags, but **not** that
its content changed: the provider does not read object bodies back. Drift
detection only covers the attributes a provider refreshes. That is one reason
people say "don't change Terraform-managed resources by hand".

### 9. `terraform destroy`

```
$ terraform destroy -no-color      # typed "yes" at the prompt
...
Plan: 0 to add, 0 to change, 5 to destroy.
...
Do you really want to destroy all resources?
...
  Enter a value: 
aws_s3_bucket_public_access_block.demo: Destroying... [id=astro-dude-24bcs10151-s18-demo]
aws_s3_bucket_versioning.demo: Destroying... [id=astro-dude-24bcs10151-s18-demo]
aws_s3_object.hello: Destroying... [id=astro-dude-24bcs10151-s18-demo/hello.txt]
aws_s3_bucket_versioning.demo: Destruction complete after 0s
aws_s3_bucket_public_access_block.demo: Destruction complete after 0s
aws_s3_object.hello: Destruction complete after 0s
aws_s3_bucket_server_side_encryption_configuration.demo: Destroying... [id=astro-dude-24bcs10151-s18-demo]
aws_s3_bucket_server_side_encryption_configuration.demo: Destruction complete after 0s
aws_s3_bucket.demo: Destroying... [id=astro-dude-24bcs10151-s18-demo]
aws_s3_bucket.demo: Destruction complete after 0s

Destroy complete! Resources: 5 destroyed.

$ terraform state list
[exit code: 0]

$ aws --endpoint-url http://localhost:4566 s3 ls
[exit code: 0]

$ aws --endpoint-url http://localhost:4566 s3api head-bucket --bucket astro-dude-24bcs10151-s18-demo
aws: [ERROR]: An error occurred (404) when calling the HeadBucket operation: Not Found
[exit code: 254]
```

Destroy runs in **reverse dependency order**: the object waits for the
encryption config, and the encryption config is removed before the bucket,
which goes last. `force_destroy = true` let Terraform remove the bucket even
though it still held two object versions. On a real production bucket you
would leave that off.

---

## The workflow in one picture

```
 write .tf ──► init ──► fmt ──► validate ──► plan ──► apply ──► (show / output / state)
                │                              │         │
                │ downloads providers          │         └─ calls the AWS API, writes terraform.tfstate
                └─ writes .terraform.lock.hcl  └─ diff: config vs. refreshed state
                                                                   │
                                                  destroy ◄────────┘  (plan -destroy, then delete in reverse order)
```

All raw transcripts are in [`../evidence/`](../evidence/) (`s18-0*.txt`).
