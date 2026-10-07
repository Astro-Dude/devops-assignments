# 01 · IAM: Identity and Access Management (Governance)

> **Hands-on environment:** the commands below ran against a local AWS
> emulator (moto server on `localhost:4566`, see the
> [Session 18 README](../../README.md)), not a real AWS account. The full
> transcript is in [`evidence/iam-handson.txt`](evidence/iam-handson.txt).
> In the excerpts, `aws` means `aws --endpoint-url http://localhost:4566`.
> The emulator stores IAM objects but does **not enforce** IAM policies on
> other API calls, so the enforcement behaviour described here is
> **conceptual** and was not tested.

## What is IAM?

IAM is the AWS service that answers two questions for **every** API call:

1. **Authentication: who is calling?** A user's password or access key, a
   role's temporary credentials, or a federated identity.
2. **Authorization: may they do this action on this resource?** This is
   decided by evaluating **policies**.

IAM is **global**: it is not tied to a region, and it costs nothing. A brand-new
identity can do **nothing** at all. Every permission has to be granted
explicitly.

```
  principal  ──(signed request: action + resource + context)──►  IAM policy evaluation  ──► Allow / Deny
  (user/role)                                                          ▲
                                                    identity policies, resource policies,
                                                    permission boundaries, SCPs, session policies
```

## Users

An IAM **user** is a long-lived identity for **one person or one application**.
It can have:

- a **console password**, used to sign in to the web console, and
- up to two **access keys** (`AKIA…` key ID + secret), used for the CLI and SDKs.

```
$ aws iam create-user --user-name shaurya-analyst --tags Key=Team,Value=Analytics
{
    "User": {
        "Path": "/",
        "UserName": "shaurya-analyst",
        "UserId": "i4kuuiqyjotl75okexdp",
        "Arn": "arn:aws:iam::123456789012:user/shaurya-analyst",
        ...
```

The **root user** (the account's sign-up email) is not an IAM user. It can do
everything, and policies cannot restrict it. Lock it away and use it only for
the few tasks that need it.

## Groups

A **group** is a collection of users that share permissions. A policy attached
to the group applies to every member. Groups cannot be nested, and a group is
not a principal: you can't name a group in a resource policy, and nobody can
"log in as" a group.

```
$ aws iam create-group --group-name report-readers
$ aws iam add-user-to-group --user-name shaurya-analyst --group-name report-readers

$ aws iam list-groups-for-user --user-name shaurya-analyst --query Groups[].GroupName
[
    "report-readers"
]

$ aws iam list-attached-user-policies --user-name shaurya-analyst
{
    "AttachedPolicies": []
}
```

The user has **no** policies of their own. Everything they can do comes from the
group, so changing what "report readers" may do is a single edit to the group.

## Roles

A **role** is an identity **without** permanent credentials. Someone or
something **assumes** it and receives **temporary credentials** that expire
(1 hour by default). A role has two policies:

- the **trust policy**: *who* may assume the role, and
- the **permission policies**: *what* the role may do once assumed.

Trust policy used here ([`ec2-trust-policy.json`](ec2-trust-policy.json)):
"EC2 instances may assume this role".

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Principal": { "Service": "ec2.amazonaws.com" }, "Action": "sts:AssumeRole" }
  ]
}
```

```
$ aws iam create-role --role-name app-server-role --assume-role-policy-document file://ec2-trust-policy.json
$ aws iam attach-role-policy --role-name app-server-role --policy-arn arn:aws:iam::123456789012:policy/S3ReadOneBucket
$ aws iam create-instance-profile --instance-profile-name app-server-profile
$ aws iam add-role-to-instance-profile --instance-profile-name app-server-profile --role-name app-server-role

$ aws sts assume-role --role-arn arn:aws:iam::123456789012:role/app-server-role --role-session-name demo --query {AssumedRole:AssumedRoleUser.Arn,Expires:Credentials.Expiration,KeyIdPrefix:Credentials.AccessKeyId}
{
    "AssumedRole": "arn:aws:sts::123456789012:assumed-role/app-server-role/demo",
    "Expires": "2026-10-07T15:18:14.421762+00:00",
    "KeyIdPrefix": "ASIARZPUZDIKOKZIUU5X"
}
```

Note that temporary keys begin with **`ASIA`**, while long-lived user keys begin
with `AKIA`. The credentials expire an hour after they are issued. An **instance profile** is the
container that hands a role to an EC2 instance. The application on the instance
then gets rotating credentials from the metadata service, so no key is ever
written to disk.

Typical role uses: EC2/Lambda/ECS tasks calling other AWS services,
cross-account access, SSO/federated humans, and CI pipelines (GitHub Actions
OIDC → `AssumeRoleWithWebIdentity`).

## Policies

A **policy** is a JSON document of **statements**. Each statement has:

| Element | Meaning |
|---|---|
| `Effect` | `Allow` or `Deny` |
| `Action` | API actions, e.g. `s3:GetObject`, `ec2:*` |
| `Resource` | the ARNs the statement applies to |
| `Condition` | optional extra checks (source IP, MFA present, tag values, TLS …) |
| `Principal` | **only in resource policies**: who the statement is about |

The least-privilege policy created here
([`s3-readonly-one-bucket.json`](s3-readonly-one-bucket.json)):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "ListOnlyThisBucket",      "Effect": "Allow", "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::astro-dude-reports" },
    { "Sid": "ReadObjectsInThisBucket", "Effect": "Allow", "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::astro-dude-reports/*" }
  ]
}
```

`ListBucket` acts on the **bucket** ARN, while `GetObject` acts on **object**
ARNs (`/*`). Mixing these up is the classic "Access Denied" mistake.

Kinds of policy:

- **AWS-managed**, e.g. `ReadOnlyAccess`: convenient, but usually broader than
  you need.
- **Customer-managed**, like `S3ReadOneBucket` above: reusable and versioned
  (`"DefaultVersionId": "v1"` in the output).
- **Inline**: embedded in one user, group or role, and deleted with it.
- **Resource-based**, e.g. S3 bucket policies or KMS key policies: attached to
  the resource, with a `Principal`.
- **Guardrails**: permission boundaries and Organizations SCPs. They set the
  *maximum* permissions and never grant anything themselves.

## Permissions: how a request is decided

```
1. Is there an explicit Deny in any applicable policy?   ──yes──► DENY   (explicit deny always wins)
2. Is there an Allow (identity or resource policy) that
   matches, and do SCPs / boundaries also allow it?      ──yes──► ALLOW
3. Otherwise                                             ───────► DENY   (implicit deny)
```

So for `shaurya-analyst`, the result *would be*:

| Action | Resource | Result | Why |
|---|---|---|---|
| `s3:GetObject` | `astro-dude-reports/q3.pdf` | Allow | matches statement 2 |
| `s3:PutObject` | `astro-dude-reports/q3.pdf` | Deny | nothing allows it (implicit) |
| `s3:GetObject` | `other-bucket/x` | Deny | resource does not match |

I tried to confirm this with the IAM policy simulator. The emulator does not
implement it and returned an HTTP 500, which is kept in the evidence file as-is:

```
$ aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::123456789012:user/shaurya-analyst --action-names s3:GetObject s3:PutObject s3:DeleteBucket ...
aws: [ERROR]: Unable to parse response (syntax error: line 1, column 0), invalid XML received. ...
b'<!doctype html>\n<html lang=en>\n<title>500 Internal Server Error</title>...
```

On real AWS the same command, or the console's Policy Simulator, prints an
`allowed` / `implicitDeny` / `explicitDeny` row for each action.

## Least privilege

Grant **only** the actions, on **only** the resources, under **only** the
conditions, that a job actually needs, and nothing "just in case".

The same need, written three ways:

| | Policy | Problem |
|---|---|---|
| Bad | `"Action": "*", "Resource": "*"` (AdministratorAccess) | a leaked key owns the account |
| Better | `"Action": "s3:*", "Resource": "*"` | can delete every bucket |
| Least privilege | `s3:GetObject` on `astro-dude-reports/*` + `s3:ListBucket` on the bucket | can only read one bucket |

How to get there in practice:

1. Start from an AWS-managed policy.
2. Use **IAM Access Analyzer** / "last accessed" data to see what was really used.
3. Replace it with a tight customer-managed policy.
4. Add **conditions**, e.g. `aws:MultiFactorAuthPresent`, `aws:SourceIp`, or
   `aws:ResourceTag/Team = ${aws:PrincipalTag/Team}`.

## IAM best practices

1. **Protect the root user:** MFA on, no access keys, use it only for
   root-only tasks.
2. **Humans use federation / IAM Identity Center** (SSO) with temporary
   credentials, not IAM users with long-lived keys.
3. **Workloads use roles:** instance profiles, ECS task roles, Lambda
   execution roles, and OIDC for CI. Never bake keys into AMIs, code or Git.
4. **MFA** for every human with console access.
5. **Permissions through groups / roles**, not policies on individual users.
6. **Least privilege**, reviewed regularly; remove unused users, keys and roles
   (credential report, last-accessed data).
7. **Rotate** any long-lived key that must exist.
8. **A strong password policy.** Applied here:

   ```
   $ aws iam update-account-password-policy --minimum-password-length 14 --require-symbols --require-numbers --require-uppercase-characters --require-lowercase-characters --max-password-age 90 --password-reuse-prevention 5
   $ aws iam get-account-password-policy
   {
       "PasswordPolicy": {
           "MinimumPasswordLength": 14,
           "RequireSymbols": true,
           "RequireNumbers": true,
           "RequireUppercaseCharacters": true,
           "RequireLowercaseCharacters": true,
           "AllowUsersToChangePassword": false,
           "ExpirePasswords": true,
           "MaxPasswordAge": 90,
           "PasswordReusePrevention": 5,
           "HardExpiry": false
       }
   }
   ```
9. **Guardrails at scale:** SCPs in AWS Organizations, e.g. "nobody may
   disable CloudTrail" or "only ap-south-1 and us-east-1 may be used".
10. **Audit:** CloudTrail logs every IAM-authorized API call. Access Analyzer
    flags resources that are shared outside the account.

## Common use cases

| Need | IAM building block |
|---|---|
| Team of analysts that read reports | group + customer-managed read-only policy (done above) |
| App on EC2 reads S3 without keys | role + instance profile (done above) |
| GitHub Actions deploys with Terraform | role trusted for the GitHub OIDC provider |
| Another AWS account reads your bucket | role with a cross-account trust policy, or a bucket policy |
| Developers may only touch resources tagged with their team | ABAC: condition on `aws:PrincipalTag` / `aws:ResourceTag` |
| Contractor access that expires | federated session / role with short `MaxSessionDuration` |
| Prevent anyone deleting audit logs | explicit Deny in an SCP or bucket policy |

## The same thing in Terraform

```hcl
resource "aws_iam_group" "readers" { name = "report-readers" }

resource "aws_iam_policy" "s3_read_one" {
  name   = "S3ReadOneBucket"
  policy = file("${path.module}/s3-readonly-one-bucket.json")
}

resource "aws_iam_group_policy_attachment" "readers" {
  group      = aws_iam_group.readers.name
  policy_arn = aws_iam_policy.s3_read_one.arn
}

resource "aws_iam_user" "analyst" { name = "shaurya-analyst" }

resource "aws_iam_user_group_membership" "analyst" {
  user   = aws_iam_user.analyst.name
  groups = [aws_iam_group.readers.name]
}
```
