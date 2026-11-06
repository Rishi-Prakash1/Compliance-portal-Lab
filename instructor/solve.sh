#!/usr/bin/env bash
# Applies every planted-gap fix to range/assets (instructor demo / verification).
set -euo pipefail
cd "$(dirname "$0")/../range/assets"
TODAY=$(date +%F)
sed -i 's/^:FORWARD ACCEPT/:FORWARD DROP/; /-s 10\.10\.0\.0\/16/d; /^# TEMP - corporate/d' ot-fw/iptables.rules
python3 - "$TODAY" <<'PY'
import json, sys
t = sys.argv[1]
def upd(p, f):
    d = json.load(open(p)); f(d); json.dump(d, open(p, "w"), indent=2)
upd("ot-fw/backup_meta.json", lambda d: d.update(last_backup=t, integrity_hash_recorded=True))
def acc(d):
    for a in d["accounts"]:
        if a["username"] == "operator": a["enabled"] = False
        if a["username"] == "s.iyer": a["mfa"] = True
upd("eng-ws/accounts.json", acc)
def iam(d):
    d["password"]["min_length"] = 14; d["lockout"] = {"threshold": 5, "duration_minutes": 15}
    d["mfa"]["enforced_for_privileged"] = True; d["logging"]["retention_days"] = 180
upd("eng-ws/iam_policy.json", iam)
def cr(d):
    d["tls"]["min_version"] = "TLSv1.2"; d["tls"]["ciphers"] = ["TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256"]; d["backup"]["encrypted"] = True
upd("historian/crypto.json", cr)
def cc(d):
    for c in d["controls"]:
        if c["id"] == "CC-001": c.update(valid_until="2027-06-30", approved_on=t, last_reviewed=t)
upd("plc-gw/compensating_controls.json", cc)
upd("plc-gw/modbus_gw.json", lambda d: d["write_access"].update(allowed_sources=["10.30.2.15/32"]))
upd("vendor-ra/ra_policy.json", lambda d: d.update(access_mode="on-demand", session_recording=True, session_timeout_minutes=120))
upd("grc-docs/audit_calendar.json", lambda d: d["self_audit"].update(last_completed=t))
PY
sed -i 's/^server pool.ntp.org iburst/server time.nplindia.org iburst/' historian/ntp.conf
sed -i 's/within 24 hours of the incident being confirmed by the OT Security Lead/within 6 hours of noticing the incident/' grc-docs/incident_response_plan.md
echo "[*] All fixes applied. Run ./lab.sh audit"
