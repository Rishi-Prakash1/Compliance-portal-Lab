# Exercise 5.1 — Compliance Obligation Register & Comprehensive Self-Audit (Docker Lab)

**Module 5 · Compliance & Supply Chain** · 180 minutes · IEC 62443-2-1 / IEC 62443-2-4 / Audit

Delivery platform: **HTML Compliance Management Portal + Virtual Evidence Repository**, backed by a
simulated OT plant (Plant Unit 2) whose assets expose their configuration for audit.

## Learning objectives
1. Build and manage a compliance obligation register mapping regulatory clauses (First Schedule,
   National Acts, IEC 62443 baselines) to technical controls.
2. Link technical configuration artifacts (firewall backups, IAM logs, encryption settings,
   compensating-control rules) directly to audit evidence requirements.
3. Execute automated compliance gap-analysis scripts and formulate actionable corrective action plans.

## Architecture

```
                IT zone (ex51_it_net)                         OT zone (ex51_ot_net, internal - no Internet)
  ┌───────────────────────────┐   ┌───────────────────┐       ┌──────────────────────────────────────┐
  │ portal :8080              │   │ evidence-repo     │       │ ot-fw      FW-OT-01 boundary firewall│
  │ Register / Evidence /     │   │ :8081 (nginx,     │       │ eng-ws     EWS-01 + OT AD IAM        │
  │ Gap Analysis / CAP        │   │ read-only index)  │       │ historian  HIST-01 crypto + NTP      │
  └────────────▲──────────────┘   └────────▲──────────┘       │ plc-gw     MBGW-01 + CC register    │
               │ POST /api/gaps            │ evidence vol     │ vendor-ra  vendor remote access GW   │
               │                ┌──────────┴──────────┐       │ grc-docs   IR plan, ISMS, audit cal. │
               └────────────────┤ auditor (both zones)├──────►└──────────────────────────────────────┘
                                │ collect · analyze   │  HTTP config export :8080
                                └─────────────────────┘
```

| Component | Purpose |
|---|---|
| `portal` | Obligation register, evidence linking, gap view, Corrective Action Plan (CAP), CSV exports |
| `evidence-repo` | Browsable read-only view of `/evidence` (snapshots, manifests, reports, `custody.log`) |
| `auditor` | Trainee workstation. `collect` (SHA-256 hashed evidence + chain of custody), `analyze` (rules → gaps → portal) |
| six OT/GRC assets | Serve the configuration files in `range/assets/<asset>/` — **these are what you remediate** |

## Requirements
Docker Engine 24+ with Compose v2, ~1 GB disk, ports 8080/8081 free. Works on Linux, macOS, Windows (Docker Desktop / WSL2).

## Quick start
```bash
./lab.sh up          # build + start; seeds range/assets/ from seed/assets/
./lab.sh audit       # collect evidence + run gap analysis
# Portal:     http://localhost:8080
# Repository: http://localhost:8081
./lab.sh shell       # auditor shell: collect | analyze | audit | curl http://ot-fw:8080/
./lab.sh reset       # restore the vulnerable baseline for the next batch
```
Windows without bash: `docker compose up -d --build` (after copying `seed/assets` to `range/assets`), then `docker compose exec auditor audit`.

---

## 4-Phase 180-Minute Step-by-Step Range Procedure

### Phase 1 — Build the obligation register (0:00 – 0:40)
1. `./lab.sh up`, open the portal → **Obligation Register**. Review the 10 seeded obligations.
2. For each obligation, check that the requirement is *testable* (who/what/threshold) and has a technical control reference. Edit weak wording.
3. Open `handouts/regulatory_extract.md`. Identify the **3 obligations missing** from the register and add them with the exact IDs given.
4. Assign an owner and review frequency to each new obligation.
5. Export `register.csv` — **Deliverable D1**.

> Checkpoint: if you run `./lab.sh audit` before finishing step 3, the analyzer and dashboard will flag
> *UNREGISTERED OBLIGATION*. That is the point — unregistered obligations are invisible to governance.

### Phase 2 — Collect and link evidence (0:40 – 1:30)
1. `./lab.sh shell` → `collect`. Note the collection ID and manifest hash; inspect `/evidence/custody.log`.
2. In the repository (:8081) open each artifact. Read them as an auditor — do not rely on the scripts yet.
3. In **Evidence**, manually link the documentary artifacts that no automated check covers:
   - `grc-docs/isms_policy.md` → `OBL-ITA-70` (what does it prove? what does it *not* prove?)
   - `grc-docs/audit_calendar.json` → `OBL-FS-04`
   - `eng-ws/auth.log` → `OBL-FS-02` and `OBL-62443-AUTH` (what does the log show about `operator` and `s.iyer`?)
4. Write an assessment note for every link. A link without a note is not evidence.
5. Export `evidence.csv` — **Deliverable D2** (evidence-to-requirement traceability matrix).

### Phase 3 — Automated gap analysis (1:30 – 2:20)
1. `analyze`. Review the console output, then **Gap Analysis** and the dashboard.
2. Open `/opt/audit/rules.yaml` (or `auditor/rules.yaml` on the host). For three failing checks, explain how the rule turns an artifact into a verdict.
3. Validate at least 3 findings manually against the raw artifact (Find → **Validate**). Record any you believe are false positives.
4. **Find what the scripts miss.** The rules do not cover everything. Identify at least 2 additional gaps from manual review (hint: `auth.log`, `k.menon`, `vendor_ctrl`, TLS ciphers, IR plan review cycle). Add them as notes on the relevant CAP or obligation.
5. Write one new rule in `rules.yaml` for one of your manual findings, re-run `analyze`, confirm it fires.

### Phase 4 — Corrective action plan, remediate, verify (2:20 – 3:00)
1. In **Corrective Actions**, assign an owner, due date and refined action for every Critical and High item. Use *Risk Accepted* only with written justification.
2. Remediate **at least 4 findings including both Criticals** by editing files under `range/assets/<asset>/` on the host (this simulates the asset owner applying the change).
3. `./lab.sh audit`. CAP items whose re-test passes move to **Verified-Closed** automatically; anything that regresses is re-opened.
4. Export `cap.csv` — **Deliverable D3**. Collect the final `/evidence/reports/gap_*.md` — **Deliverable D4**.
5. Debrief: record today's date as the self-audit completion in `grc-docs/audit_calendar.json`, re-run, and explain why this closes `CHK-21`.

## Deliverables
| ID | Artifact | Source |
|---|---|---|
| D1 | Obligation register (13+ obligations) | Portal → Export CSV |
| D2 | Evidence traceability matrix with assessment notes | Portal → Evidence → Export |
| D3 | Corrective Action Plan with owners, dates, verification state | Portal → CAP → Export |
| D4 | Final gap report + `custody.log` | Repository :8081 `/reports/`, `/custody.log` |

## Assessment rubric (100)
| Criterion | Marks |
|---|---|
| All 3 missing obligations registered, requirements testable, controls mapped | 20 |
| Documentary evidence linked with meaningful assessment notes | 15 |
| Findings manually validated; ≥2 gaps found beyond the scripts | 20 |
| Custom rule written and firing | 10 |
| CAP: owners, realistic dates, root-cause-driven actions, justified risk acceptance | 15 |
| Both Criticals + ≥2 others remediated and Verified-Closed by re-test | 20 |

## Notes
- Clause mappings are training paraphrases. Verify against the authoritative CERT-In Directions and licensed IEC 62443 texts before reuse in real audits.
- Date-based checks use today's date. Instructors can pin `AUDIT_DATE` in `docker-compose.yml` for reproducible runs.
- All data is fictitious. Nothing in the range touches real OT equipment; assets are static file servers.
