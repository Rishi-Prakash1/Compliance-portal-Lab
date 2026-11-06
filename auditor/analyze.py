#!/usr/bin/env python3
"""Automated compliance gap analysis - evaluates rules.yaml against the current
evidence snapshot, writes JSON + Markdown reports, and pushes results to the
Compliance Management Portal (which links evidence and maintains the CAP)."""
import datetime, json, os, re, sys, urllib.request
import yaml

EVID = os.environ.get("EVIDENCE_DIR", "/evidence")
RULES = os.environ.get("RULES_FILE", "/opt/audit/rules.yaml")
PORTAL = os.environ.get("PORTAL_URL", "http://portal:8080")
AUDIT_DATE = os.environ.get("AUDIT_DATE")  # YYYY-MM-DD, defaults to today
TODAY = datetime.date.fromisoformat(AUDIT_DATE) if AUDIT_DATE else datetime.date.today()


def get_path(obj, path):
    for part in path.split("."):
        obj = obj[part]
    return obj


def evaluate(chk, text):
    t = chk["type"]
    if t in ("regex_present", "regex_absent"):
        hits = [m.group(0) for m in re.finditer(chk["pattern"], text, re.MULTILINE)]
        if t == "regex_present":
            return (bool(hits), f"pattern {'found' if hits else 'NOT found'}: {chk['pattern']}")
        return (not hits, "no prohibited match" if not hits else "prohibited entries: " + " | ".join(hits))
    data = json.loads(text)
    if t == "json_equals":
        v = get_path(data, chk["path"])
        return (v == chk["value"], f"{chk['path']} = {v!r} (expected {chk['value']!r})")
    if t == "json_min":
        v = get_path(data, chk["path"])
        return (v >= chk["value"], f"{chk['path']} = {v} (minimum {chk['value']})")
    if t == "json_in":
        v = get_path(data, chk["path"])
        return (v in chk["values"], f"{chk['path']} = {v!r} (allowed {chk['values']})")
    if t == "json_none_match":
        items = get_path(data, chk["path"])
        bad = [i for i in items if all(i.get(k) == v for k, v in chk["where"].items())]
        names = [str(i.get(chk.get("report_field", "id"), "?")) for i in bad]
        return (not bad, "none matching" if not bad else f"matching {chk['where']}: {', '.join(names)}")
    if t == "json_none_expired":
        items = get_path(data, chk["path"])
        bad = [i for i in items if datetime.date.fromisoformat(i[chk["field"]]) < TODAY]
        names = [f"{i.get(chk.get('report_field', 'id'))} (expired {i[chk['field']]})" for i in bad]
        return (not bad, "all within validity" if not bad else "expired: " + ", ".join(names))
    if t == "date_within_days":
        d = datetime.date.fromisoformat(get_path(data, chk["path"]))
        age = (TODAY - d).days
        return (age <= chk["days"], f"{chk['path']} = {d} ({age} days old, max {chk['days']})")
    raise ValueError(f"unknown check type {t}")


def portal_obligations():
    try:
        return {o["id"] for o in json.load(urllib.request.urlopen(f"{PORTAL}/api/obligations", timeout=5))}
    except Exception as e:
        print(f"[!] Portal unreachable ({e}); continuing offline")
        return None


def main():
    rules = yaml.safe_load(open(RULES))["checks"]
    cur = os.path.join(EVID, "current")
    mpath = os.path.join(cur, "manifest.json")
    if not os.path.exists(mpath):
        print("[!] No evidence snapshot. Run 'collect' first.")
        return 2
    manifest = json.load(open(mpath))
    hashes = {a["path"]: a.get("sha256") for a in manifest["artifacts"]}
    registered = portal_obligations()
    results = []
    for c in rules:
        rel = f"{c['asset']}/{c['artifact']}"
        p = os.path.join(cur, rel)
        r = {k: c.get(k) for k in ("id", "obligation", "title", "asset", "artifact", "severity", "root_cause", "remediation")}
        r["sha256"] = hashes.get(rel)
        r["evidence_path"] = rel
        if not os.path.exists(p):
            r.update(status="NO_EVIDENCE", detail="artifact not present in evidence repository")
        else:
            try:
                passed, detail = evaluate(c, open(p, encoding="utf-8").read())
                r.update(status="PASS" if passed else "FAIL", detail=detail)
            except Exception as e:
                r.update(status="ERROR", detail=f"{type(e).__name__}: {e}")
        if registered is not None and c["obligation"] not in registered:
            r["unregistered"] = True
        results.append(r)

    counts = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "NO_EVIDENCE", "ERROR")}
    unreg = sorted({r["obligation"] for r in results if r.get("unregistered")})
    run = {"run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "audit_date": TODAY.isoformat(),
           "collection_id": manifest["collection_id"], "counts": counts, "unregistered_obligations": unreg,
           "results": results}

    os.makedirs(os.path.join(EVID, "reports"), exist_ok=True)
    stem = os.path.join(EVID, "reports", f"gap_{manifest['collection_id']}")
    json.dump(run, open(stem + ".json", "w"), indent=2)
    sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    with open(stem + ".md", "w") as md:
        md.write(f"# Compliance Gap Analysis - collection {manifest['collection_id']}\n\nAudit date: {TODAY}\n\n")
        md.write("| Result | Count |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in counts.items()))
        if unreg:
            md.write(f"\n**Unregistered obligations referenced by checks:** {', '.join(unreg)}\n")
        md.write("\n| Check | Obligation | Severity | Status | Evidence | Detail |\n|---|---|---|---|---|---|\n")
        for r in sorted(results, key=lambda r: (r["status"] == "PASS", sev_order.get(r["severity"], 9))):
            md.write(f"| {r['id']} | {r['obligation']} | {r['severity']} | {r['status']} | {r['evidence_path']} | {r['detail']} |\n")

    icon = {"PASS": "PASS", "FAIL": "FAIL", "NO_EVIDENCE": "NOEV", "ERROR": "ERR "}
    print(f"[*] Gap analysis against collection {manifest['collection_id']} (audit date {TODAY})\n")
    for r in results:
        flag = "  <-- UNREGISTERED OBLIGATION" if r.get("unregistered") else ""
        print(f"  [{icon[r['status']]}] {r['id']} {r['severity']:8s} {r['obligation']:17s} {r['title']}{flag}")
        if r["status"] != "PASS":
            print(f"         {r['detail']}")
    print(f"\n[*] PASS={counts['PASS']} FAIL={counts['FAIL']} NO_EVIDENCE={counts['NO_EVIDENCE']} ERROR={counts['ERROR']}")
    if unreg:
        print(f"[!] Checks reference obligations missing from the register: {', '.join(unreg)}")
        print("    Add them in the portal (Obligation Register) and re-run 'analyze'.")
    print(f"[*] Reports: {stem}.json / .md")

    try:
        req = urllib.request.Request(f"{PORTAL}/api/gaps", data=json.dumps(run).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        resp = json.load(urllib.request.urlopen(req, timeout=10))
        print(f"[*] Portal updated: run #{resp['run_id']}, CAP opened={resp['cap_opened']} "
              f"reopened={resp['cap_reopened']} verified-closed={resp['cap_verified']}")
    except Exception as e:
        print(f"[!] Could not push to portal: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
