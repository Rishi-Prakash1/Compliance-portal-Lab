# Exercise 5.1 — Instructor Answer Key (do not distribute)

## Baseline result (fresh range)
`PASS=3  FAIL=18` — passes: CHK-03 (deny logging), CHK-12 (encryption at rest), CHK-19 (vendor MFA).
Unregistered until Phase 1 is done: OBL-CERTIN-02, OBL-CERTIN-03, OBL-24-RA.

## Planted automated gaps and the expected fix
| Check | Sev | Obligation | Artifact | Fix in `range/assets/` |
|---|---|---|---|---|
| CHK-01 | High | ZC | ot-fw/iptables.rules | `:FORWARD ACCEPT` → `:FORWARD DROP` |
| CHK-02 | Critical | ZC | ot-fw/iptables.rules | delete the `-s 10.10.0.0/16 ... --dport 502` rule (CHG-1184 leftover) |
| CHK-04 | Medium | FS-01 | ot-fw/backup_meta.json | `last_backup` → today |
| CHK-05 | Low | FS-01 | ot-fw/backup_meta.json | `integrity_hash_recorded: true` |
| CHK-06 | High | FS-02 | eng-ws/accounts.json | `operator` → `enabled: false` (named accounts issued) |
| CHK-07 | High | AUTH | eng-ws/accounts.json | `s.iyer` → `mfa: true` |
| CHK-08 | Medium | AUTH | eng-ws/iam_policy.json | `min_length: 12`+ |
| CHK-09 | Medium | AUTH | eng-ws/iam_policy.json | `lockout.threshold: 5` (+ duration) |
| CHK-10 | High | CERTIN-01 | eng-ws/iam_policy.json | `retention_days: 180`+ |
| CHK-11 | High | CRYPTO | historian/crypto.json | `min_version: TLSv1.2`, drop 3DES cipher |
| CHK-13 | Medium | CRYPTO | historian/crypto.json | `backup.encrypted: true` |
| CHK-14 | Medium | CERTIN-02 | historian/ntp.conf | `server time.nplindia.org iburst` / `samay1.nic.in` |
| CHK-15 | High | FS-03 | plc-gw/compensating_controls.json | CC-001: re-approve with new `valid_until` (or remove after permanent fix) |
| CHK-16 | Critical | AUTHZ | plc-gw/modbus_gw.json | remove `0.0.0.0/0` from write sources |
| CHK-17 | High | 24-RA | vendor-ra/ra_policy.json | `access_mode: on-demand` |
| CHK-18 | Medium | 24-RA | vendor-ra/ra_policy.json | `session_recording: true` |
| CHK-20 | High | CERTIN-03 | grc-docs/incident_response_plan.md | §4: "within 6 hours of noticing" |
| CHK-21 | Medium | FS-04 | grc-docs/audit_calendar.json | `self_audit.last_completed` → today |

`instructor/solve.sh` applies all fixes; then `./lab.sh audit` → `PASS=21 FAIL=0`.

## Gaps the scripts do NOT catch (Phase 3, step 4 — expected trainee findings)
1. **Shared account in active use** — `auth.log` shows `operator` logging in from HMI-01/02/03; corroborates CHK-06 and proves non-attribution of operator actions.
2. **Brute-force with no lockout** — six failed `s.iyer` logins in 17 s from **10.10.44.7 (corporate IT)** into EWS-01: IT→OT path to the EWS exists *and* no lockout (CHK-09). Possible incident → CERT-In 6-hour clock question.
3. **Weak cipher** — `TLS_RSA_WITH_3DES_EDE_CBC_SHA` enabled (Sweet32, no forward secrecy) even after TLS 1.2 is set.
4. **Dormant privileged vendor account** — `vendor_ctrl` privileged, last login 2026-09-02, with always-on remote access.
5. **CC-001 is invalid even before expiry** — its compensating control ("write only from EWS") is defeated by `0.0.0.0/0` in modbus_gw (CHK-16). Good trainees connect the two.
6. **IR plan review cycle** — two-yearly review; plan predates 2022 Directions; no evidence of 6-hour reporting drill.
7. **Backup location** — firewall backup on the same NAS as historian backups, unencrypted, no hash; single point of failure.
8. **s.70 evidence gap** — ISMS policy *claims* annual empanelled audit; `audit_calendar.json` shows auditor "TBD" with next audit due 2026-11-20 → Manual Review, not Compliant.
9. `historian` NTP has internal `10.20.5.1 prefer` — acceptable only if documented as traceable to NIC/NPL.

## Model custom rule (Phase 3, step 5)
```yaml
  - id: CHK-22
    obligation: OBL-62443-CRYPTO
    title: No 3DES / static-RSA cipher suites
    asset: historian
    artifact: crypto.json
    type: regex_absent
    pattern: 'TLS_RSA_WITH_|3DES'
    severity: Medium
    root_cause: Legacy cipher list retained for old OPC clients.
    remediation: Restrict to ECDHE AEAD suites.
```

## Discussion prompts
- Why does closure require a passing re-test rather than an owner ticking "done"?
- An automated PASS on CHK-19 (vendor MFA) — is OBL-24-RA compliant? (No: aggregate status is driven by the worst check.)
- When is *Risk Accepted* defensible in OT? Who signs it, and what compensating control and expiry must accompany it?
