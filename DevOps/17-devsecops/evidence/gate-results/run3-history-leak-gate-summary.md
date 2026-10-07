## Security gate: FAILED - push and deploy are blocked

| Stage | Tool | Findings | Blocking | Result | Note |
|---|---|---:|---:|---|---|
| SAST | semgrep | 0 | 0 | PASS |  |
| SAST | bandit | 0 | 0 | PASS |  |
| SAST | trivy_config | 0 | 0 | PASS |  |
| SCA | pip_audit | 0 | 0 | PASS |  |
| SCA | trivy_fs | 0 | 0 | PASS |  |
| Secret scan | gitleaks | 1 | 1 | FAIL |  |
| Image scan | trivy | 165 | 0 | PASS | H:44 M:58 L:61 U:2; 44 HIGH/CRITICAL have no upstream fix (reported, not blocking) |

### Blocking findings: Secret scan / gitleaks

- hw-payment-live-key in DevOps/17-devsecops/app/config.py:5 (commit 3d214ab)
