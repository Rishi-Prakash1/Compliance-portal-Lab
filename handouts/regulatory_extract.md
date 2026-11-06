# Handout 5.1-A - Regulatory Extract (Phase 1 input)

The seeded register was built by the previous compliance officer. Compare it against
the obligations below. **Three of them are not in the register.** Add each missing
obligation in the portal, using EXACTLY the IDs shown (the automated checks reference them).

| Obligation ID | Source | Clause | Requirement (testable) | Technical control ref |
|---|---|---|---|---|
| OBL-FS-01..04 | First Schedule | Items 1-4 | (already registered - verify wording) | - |
| OBL-ITA-70 | National Act | IT Act 2000 s.70 + Protected System Rules 2018 | (already registered) | - |
| OBL-CERTIN-01 | National Act | CERT-In Directions 28.04.2022 - logs | (already registered) | - |
| **OBL-CERTIN-02** | National Act | CERT-In Directions 28.04.2022 - clock synchronisation | All ICT systems shall synchronise clocks to the NTP servers of NIC or NPL, or to servers traceable to them. | IEC 62443-3-3 SR 2.11 (Timestamps) |
| **OBL-CERTIN-03** | National Act | CERT-In Directions 28.04.2022 - incident reporting | Reportable cyber incidents shall be reported to CERT-In within 6 hours of noticing them. | IEC 62443-2-1 (event / incident management) |
| **OBL-24-RA** | IEC 62443 Baseline | IEC 62443-2-4 SP.07 (Remote access) | Service-provider remote access shall be on-demand, approved per session, use MFA and be recorded. | IEC 62443-2-4 SP.07; IEC 62443-3-3 SR 1.13 |
| OBL-62443-ZC / AUTH / AUTHZ / CRYPTO | IEC 62443 Baseline | 62443-3-3 SRs | (already registered) | - |

> Note for trainees: the clause wording here is a training paraphrase. In a real engagement,
> quote the authoritative text (CERT-In Directions; licensed IEC 62443 copies) in the register.
