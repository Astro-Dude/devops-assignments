# Troubleshooting — the Trailing-Newline Secret Bug

Session 12, Task 5: *"Use the troubleshooting folder"*. The course's
troubleshooting folder
(`devops-heros/session-12-ingress-configmaps-secrets/troubleshooting/secret-base64-gotcha.md`)
describes one incident: PostgreSQL rejects the application with `FATAL:
password authentication failed for user "yatri_admin"`, and the developer
insists the password is correct because they "typed `echo "mypassword" |
base64`".

I rebuilt that incident on the `hw-legacy` kind cluster and worked through it
with the six required steps. All output is **real captured output**. Full
transcript:
[`../evidence/s12-troubleshooting-secret-newline.txt`](../evidence/s12-troubleshooting-secret-newline.txt).

| File | Role |
|---|---|
| [`00-namespace.yaml`](00-namespace.yaml) | namespace `s12-trouble` |
| [`01-db-secret.yaml`](01-db-secret.yaml) | the **database's** credentials, encoded correctly (`echo -n`) |
| [`02-postgres.yaml`](02-postgres.yaml) | PostgreSQL 16 (Deployment + Service), password from `postgres-db-secret` |
| [`03-broken-secret.yaml`](03-broken-secret.yaml) | the **application's** secret, password encoded with `echo "mypassword" \| base64` |
| [`04-app-job.yaml`](04-app-job.yaml) | the "application": a Job that logs in with `psql` using `app-db-secret` |
| [`05-fixed-secret.yaml`](05-fixed-secret.yaml) | the fix: the same secret encoded with `echo -n` |

The DB and the app each have their own Secret, as they usually do in real
setups (often owned by different teams). If both had used the broken value,
PostgreSQL would have set its password to `mypassword\n` and everything would
have "worked". The bug only appears when the two sides disagree.

```bash
kubectl apply -f 00-namespace.yaml -f 01-db-secret.yaml -f 02-postgres.yaml
kubectl -n s12-trouble rollout status deploy/postgres
kubectl apply -f 03-broken-secret.yaml -f 04-app-job.yaml
```

---

## 1. Identify the problem (before)

```console
$ kubectl -n s12-trouble get jobs,pods
NAME                     STATUS   COMPLETIONS   DURATION   AGE
job.batch/app-db-check   Failed   0/1           3s         3s

NAME                            READY   STATUS    RESTARTS   AGE
pod/app-db-check-dhh8l          0/1     Error     0          3s
pod/postgres-59d7f4876f-n5htt   1/1     Running   0          7s

$ kubectl -n s12-trouble logs job/app-db-check
connecting as yatri_admin to postgres/yatri
psql: error: connection to server at "postgres" (10.96.185.134), port 5432 failed: FATAL:  password authentication failed for user "yatri_admin"
```

The app Pod is in `Error`. The database Pod is `Running`. The message comes
from the **server** (`FATAL:`), so this is not a network or DNS problem.

## 2. Run troubleshooting commands

```console
$ kubectl -n s12-trouble describe job app-db-check | sed -n '/Pods Statuses/p;/^Events:/,$p'
Pods Statuses:    0 Active (0 Ready) / 0 Succeeded / 1 Failed
Events:
  Normal   SuccessfulCreate      3s    job-controller  Created pod: app-db-check-dhh8l
  Warning  BackoffLimitExceeded  0s    job-controller  Job has reached the specified backoff limit

$ kubectl -n s12-trouble logs deploy/postgres --tail=4
2026-10-07 13:39:32.882 UTC [1] LOG:  database system is ready to accept connections
2026-10-07 13:39:35.912 UTC [85] FATAL:  password authentication failed for user "yatri_admin"
2026-10-07 13:39:35.912 UTC [85] DETAIL:  Connection matched file "/var/lib/postgresql/data/pg_hba.conf" line 128: "host all all all scram-sha-256"
```

The server log confirms it: the connection arrived, matched the
`scram-sha-256` rule, and the password check failed. The user exists, and the
DB was ready 3 seconds before the attempt. So the suspect is the **password
value**. Compare the two Secrets:

```console
$ kubectl -n s12-trouble describe secret postgres-db-secret
Data
====
POSTGRES_PASSWORD:  10 bytes
POSTGRES_USER:      11 bytes

$ kubectl -n s12-trouble describe secret app-db-secret
Data
====
DB_PASSWORD:  11 bytes
DB_USER:      11 bytes
```

**10 bytes vs 11 bytes** for what should be the same password. That is the
first real clue, and `describe` shows it without revealing the value.

```console
$ kubectl -n s12-trouble get secret postgres-db-secret -o jsonpath='{.data.POSTGRES_PASSWORD}'; echo
bXlwYXNzd29yZA==
$ kubectl -n s12-trouble get secret app-db-secret -o jsonpath='{.data.DB_PASSWORD}'; echo
bXlwYXNzd29yZAo=

$ kubectl -n s12-trouble get secret postgres-db-secret -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d | xxd
00000000: 6d79 7061 7373 776f 7264                 mypassword
$ kubectl -n s12-trouble get secret app-db-secret -o jsonpath='{.data.DB_PASSWORD}' | base64 -d | xxd
00000000: 6d79 7061 7373 776f 7264 0a              mypassword.
```

Both decode to something that *prints* as `mypassword`. `xxd` shows the extra
byte **`0a`**, a newline. The base64 strings differ only at the end: `==`
versus `o=`.

And what the application process actually receives in its environment:

```console
$ kubectl -n s12-trouble run envcheck --image=busybox:1.36 --restart=Never --rm -i --quiet --overrides='{... env PGPASSWORD from app-db-secret ...}'
0000000   m   y   p   a   s   s   w   o   r   d  \n
0000013
length=11
```

## 3. Find the root cause

The Secret was generated with `echo` without `-n`. `echo` appends `\n`, and
base64 encodes it faithfully:

```console
$ echo 'mypassword' | base64
bXlwYXNzd29yZAo=
$ echo -n 'mypassword' | base64
bXlwYXNzd29yZA==
```

The kubelet decodes the Secret into the env var **byte for byte**, so `psql`
sent `mypassword\n` (11 characters) to a server whose password is `mypassword`
(10). The server rejected it correctly. Nothing in Kubernetes reports an error,
because the Secret is perfectly valid base64.

## 4. Fix the issue

Re-encode with `echo -n` ([`05-fixed-secret.yaml`](05-fixed-secret.yaml)), or
avoid shell encoding altogether with
`kubectl create secret generic app-db-secret --from-literal=DB_PASSWORD=mypassword`.

```console
$ kubectl apply -f 05-fixed-secret.yaml
secret/app-db-secret configured

$ kubectl -n s12-trouble get secret app-db-secret -o jsonpath='{.data.DB_PASSWORD}' | base64 -d | xxd
00000000: 6d79 7061 7373 776f 7264                 mypassword
```

Env vars from a Secret are only read **when the container starts** (the main
README's Task 4 showed they never update in place). So the app has to be run
again: here the Job is recreated. For a Deployment it would be `kubectl rollout
restart`.

```console
$ kubectl -n s12-trouble delete job app-db-check
$ kubectl apply -f 04-app-job.yaml
job.batch/app-db-check created
```

## 5. Before / after output

```console
# BEFORE
$ kubectl -n s12-trouble get jobs
NAME           STATUS   COMPLETIONS   DURATION   AGE
app-db-check   Failed   0/1           3s         3s
$ kubectl -n s12-trouble logs job/app-db-check
psql: error: connection to server at "postgres" (10.96.185.134), port 5432 failed: FATAL:  password authentication failed for user "yatri_admin"

# AFTER
$ kubectl -n s12-trouble get jobs,pods
NAME                     STATUS     COMPLETIONS   DURATION   AGE
job.batch/app-db-check   Complete   1/1           3s         3s

NAME                            READY   STATUS      RESTARTS   AGE
pod/app-db-check-tcd5b          0/1     Completed   0          3s
pod/postgres-59d7f4876f-n5htt   1/1     Running     0          13s

$ kubectl -n s12-trouble logs job/app-db-check
connecting as yatri_admin to postgres/yatri
         result          
-------------------------
 login ok as yatri_admin
(1 row)
```

The same database Pod (`postgres-59d7f4876f-n5htt`, never restarted) now
accepts the login. The PostgreSQL log has no new `FATAL` line after the fix.

## 6. Lessons

| Step | What found it |
|---|---|
| Not network/DNS | the error starts with `FATAL:` from the server |
| Suspect the value | server log: user exists, `scram-sha-256` rule matched, password check failed |
| First hard clue | `kubectl describe secret`: **10 bytes vs 11 bytes** |
| Proof | `base64 -d \| xxd` shows the trailing **`0a`**; `od -c` of the env var shows `\n` |

- Always use `echo -n` (or `printf %s`) when base64-encoding by hand, or let
  `kubectl create secret --from-literal` / `--from-env-file` do the encoding.
- A base64 value ending in `Cg==`, `K`, `o=` (and so on) often means a
  trailing newline. Check it with `xxd`.
- `describe secret` shows byte lengths without the value. Comparing lengths
  is a safe first check.

Cleanup: `kubectl delete namespace s12-trouble`.
