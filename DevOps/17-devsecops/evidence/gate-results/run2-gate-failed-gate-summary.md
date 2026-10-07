## Security gate: FAILED - push and deploy are blocked

| Stage | Tool | Findings | Blocking | Result | Note |
|---|---|---:|---:|---|---|
| SAST | semgrep | 5 | 4 | FAIL |  |
| SAST | bandit | 2 | 1 | FAIL |  |
| SAST | trivy_config | 0 | 0 | PASS |  |
| SCA | pip_audit | 4 | 4 | FAIL |  |
| SCA | trivy_fs | 2 | 2 | FAIL | H:2 |
| Secret scan | gitleaks | 1 | 1 | FAIL |  |
| Image scan | trivy | 167 | 2 | FAIL | H:46 M:58 L:61 U:2; 44 HIGH/CRITICAL have no upstream fix (reported, not blocking) |

### Blocking findings: SAST / semgrep

- ERROR s17-subprocess-shell-true at DevOps/17-devsecops/app/main.py:115
- ERROR subprocess-injection at DevOps/17-devsecops/app/main.py:115
- ERROR dangerous-subprocess-use at DevOps/17-devsecops/app/main.py:115
- ERROR subprocess-shell-true at DevOps/17-devsecops/app/main.py:115

### Blocking findings: SAST / bandit

- HIGH/HIGH B602 subprocess_popen_with_shell_equals_true at app/main.py:115

### Blocking findings: SCA / pip_audit

- PYSEC-2026-1434 gunicorn 21.2.0 -> fix 22.0.0
- PYSEC-2026-1433 gunicorn 21.2.0 -> fix 22.0.0
- PYSEC-2026-1434 gunicorn 21.2.0 -> fix 22.0.0
- PYSEC-2026-1433 gunicorn 21.2.0 -> fix 22.0.0

### Blocking findings: SCA / trivy_fs

- HIGH CVE-2024-1135 gunicorn 21.2.0 -> fixed in 22.0.0
- HIGH CVE-2024-6827 gunicorn 21.2.0 -> fixed in 22.0.0

### Blocking findings: Secret scan / gitleaks

- hw-payment-live-key in DevOps/17-devsecops/app/config.py:5 (commit 3d214ab)

### Blocking findings: Image scan / trivy

- HIGH CVE-2024-1135 gunicorn 21.2.0 -> fixed in 22.0.0
- HIGH CVE-2024-6827 gunicorn 21.2.0 -> fixed in 22.0.0
