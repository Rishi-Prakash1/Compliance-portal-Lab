"""Exercise 5.1 - HTML Compliance Management Portal
Obligation register, evidence linking, gap analysis view and Corrective Action Plan."""
import csv, datetime, io, json, os, sqlite3
from flask import Flask, Response, abort, flash, g, jsonify, redirect, render_template, request, url_for

DB = os.environ.get("PORTAL_DB", "/data/portal.db")
EVID = os.environ.get("EVIDENCE_DIR", "/evidence")
SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed", "obligations.json")
DUE_DAYS = {"Critical": 7, "High": 30, "Medium": 60, "Low": 90}
SEV_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
CAP_STATES = ["Open", "In Progress", "Remediated - Pending Verification", "Risk Accepted", "Verified-Closed"]

app = Flask(__name__)
app.secret_key = os.environ.get("PORTAL_SECRET", "ex51-training-lab")

SCHEMA = """
CREATE TABLE IF NOT EXISTS obligations(id TEXT PRIMARY KEY, source TEXT, clause TEXT, title TEXT,
  requirement TEXT, control_ref TEXT, owner TEXT, frequency TEXT, origin TEXT DEFAULT 'seed', created TEXT);
CREATE TABLE IF NOT EXISTS links(id INTEGER PRIMARY KEY AUTOINCREMENT, obligation_id TEXT, artifact TEXT,
  sha256 TEXT, linked_by TEXT, note TEXT, ts TEXT, UNIQUE(obligation_id, artifact));
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, audit_date TEXT,
  collection_id TEXT, counts TEXT, unregistered TEXT);
CREATE TABLE IF NOT EXISTS results(run_id INTEGER, check_id TEXT, obligation_id TEXT, title TEXT, asset TEXT,
  artifact TEXT, sha256 TEXT, status TEXT, severity TEXT, detail TEXT, root_cause TEXT, remediation TEXT);
CREATE TABLE IF NOT EXISTS cap(id TEXT PRIMARY KEY, check_id TEXT UNIQUE, obligation_id TEXT, severity TEXT,
  gap TEXT, root_cause TEXT, action TEXT, owner TEXT, due TEXT, status TEXT, opened TEXT, closed TEXT,
  verified_run INTEGER, notes TEXT);
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM obligations LIMIT 1").fetchone():
        now = datetime.datetime.now().isoformat(timespec="seconds")
        for o in json.load(open(SEED)):
            con.execute("INSERT INTO obligations VALUES(?,?,?,?,?,?,?,?,'seed',?)",
                        (o["id"], o["source"], o["clause"], o["title"], o["requirement"], o["control_ref"],
                         o["owner"], o["frequency"], now))
    con.commit()
    con.close()


def manifest():
    p = os.path.join(EVID, "current", "manifest.json")
    return json.load(open(p)) if os.path.exists(p) else None


def latest_run():
    return db().execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()


def obligation_rows():
    run = latest_run()
    rows = []
    for o in db().execute("SELECT * FROM obligations ORDER BY source, id"):
        res = db().execute("SELECT status FROM results WHERE run_id=? AND obligation_id=?",
                           (run["id"] if run else -1, o["id"])).fetchall()
        st = [r["status"] for r in res]
        nlinks = db().execute("SELECT COUNT(*) FROM links WHERE obligation_id=?", (o["id"],)).fetchone()[0]
        if "FAIL" in st:
            status = "Non-Compliant"
        elif "NO_EVIDENCE" in st or "ERROR" in st:
            status = "No Evidence"
        elif st:
            status = "Compliant"
        elif nlinks:
            status = "Evidence Linked - Manual Review"
        else:
            status = "Not Assessed"
        rows.append(dict(o, status=status, checks=len(st), fails=st.count("FAIL"), links=nlinks))
    return rows


@app.context_processor
def inject():
    return {"now": datetime.date.today().isoformat()}


@app.route("/")
def dashboard():
    obs = obligation_rows()
    run = latest_run()
    total = len(obs)
    by = {}
    for o in obs:
        by[o["status"]] = by.get(o["status"], 0) + 1
    assessed = [o for o in obs if o["status"] in ("Compliant", "Non-Compliant", "Evidence Linked - Manual Review")]
    score = round(100 * sum(1 for o in assessed if o["status"] != "Non-Compliant") / total) if total else 0
    caps = db().execute("SELECT status, severity FROM cap").fetchall()
    open_caps = [c for c in caps if c["status"] not in ("Verified-Closed", "Risk Accepted")]
    sev = {s: sum(1 for c in open_caps if c["severity"] == s) for s in SEV_ORDER}
    return render_template("dashboard.html", obs=obs, run=run, by=by, total=total, score=score,
                           open_caps=len(open_caps), closed_caps=len(caps) - len(open_caps), sev=sev,
                           counts=json.loads(run["counts"]) if run else None,
                           unreg=json.loads(run["unregistered"]) if run else [], m=manifest())


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        oid = f["id"].strip().upper()
        if not oid.startswith("OBL-"):
            flash("Obligation ID must start with OBL-", "err")
            return redirect(url_for("register"))
        vals = [f.get(k, "").strip() for k in ("source", "clause", "title", "requirement", "control_ref", "owner", "frequency")]
        exists = db().execute("SELECT 1 FROM obligations WHERE id=?", (oid,)).fetchone()
        if exists:
            db().execute("UPDATE obligations SET source=?,clause=?,title=?,requirement=?,control_ref=?,owner=?,frequency=? WHERE id=?", (*vals, oid))
            flash(f"{oid} updated", "ok")
        else:
            db().execute("INSERT INTO obligations VALUES(?,?,?,?,?,?,?,?,'trainee',?)",
                         (oid, *vals, datetime.datetime.now().isoformat(timespec="seconds")))
            flash(f"{oid} added to register", "ok")
        db().commit()
        return redirect(url_for("register"))
    edit = None
    if request.args.get("edit"):
        edit = db().execute("SELECT * FROM obligations WHERE id=?", (request.args["edit"],)).fetchone()
    return render_template("register.html", obs=obligation_rows(), edit=edit)


@app.route("/register/<oid>/delete", methods=["POST"])
def delete_obligation(oid):
    db().execute("DELETE FROM obligations WHERE id=?", (oid,))
    db().execute("DELETE FROM links WHERE obligation_id=?", (oid,))
    db().commit()
    flash(f"{oid} removed", "ok")
    return redirect(url_for("register"))


@app.route("/register/<oid>")
def obligation_detail(oid):
    o = db().execute("SELECT * FROM obligations WHERE id=?", (oid,)).fetchone()
    if not o:
        abort(404)
    run = latest_run()
    res = db().execute("SELECT * FROM results WHERE run_id=? AND obligation_id=?", (run["id"] if run else -1, oid)).fetchall()
    links = db().execute("SELECT * FROM links WHERE obligation_id=? ORDER BY ts", (oid,)).fetchall()
    caps = db().execute("SELECT * FROM cap WHERE obligation_id=?", (oid,)).fetchall()
    st = next((r["status"] for r in obligation_rows() if r["id"] == oid), "")
    return render_template("obligation.html", o=o, res=res, links=links, caps=caps, status=st)


@app.route("/evidence", methods=["GET", "POST"])
def evidence():
    m = manifest()
    if request.method == "POST":
        f = request.form
        art = f["artifact"]
        sha = next((a.get("sha256") for a in (m or {}).get("artifacts", []) if a["path"] == art), None)
        db().execute("INSERT OR REPLACE INTO links(obligation_id,artifact,sha256,linked_by,note,ts) VALUES(?,?,?,?,?,?)",
                     (f["obligation_id"], art, sha, f.get("linked_by") or "trainee", f.get("note", ""),
                      datetime.datetime.now().isoformat(timespec="seconds")))
        db().commit()
        flash(f"Linked {art} -> {f['obligation_id']}", "ok")
        return redirect(url_for("evidence"))
    links = db().execute("SELECT * FROM links ORDER BY artifact, obligation_id").fetchall()
    by_art = {}
    for l in links:
        by_art.setdefault(l["artifact"], []).append(l)
    obs = db().execute("SELECT id, title FROM obligations ORDER BY id").fetchall()
    return render_template("evidence.html", m=m, by_art=by_art, obs=obs, repo=os.environ.get("REPO_URL", "http://localhost:8081"))


@app.route("/evidence/unlink/<int:lid>", methods=["POST"])
def unlink(lid):
    db().execute("DELETE FROM links WHERE id=?", (lid,))
    db().commit()
    return redirect(request.referrer or url_for("evidence"))


@app.route("/gaps")
def gaps():
    run = latest_run()
    res = []
    if run:
        res = [dict(r) for r in db().execute("SELECT * FROM results WHERE run_id=?", (run["id"],))]
        res.sort(key=lambda r: (r["status"] == "PASS", SEV_ORDER.get(r["severity"], 9), r["check_id"]))
    want = request.args.get("status")
    if want:
        res = [r for r in res if r["status"] == want]
    known = {r["id"] for r in db().execute("SELECT id FROM obligations")}
    runs = db().execute("SELECT * FROM runs ORDER BY id DESC LIMIT 10").fetchall()
    return render_template("gaps.html", run=run, res=res, known=known, runs=runs, want=want, json=json)


@app.route("/cap", methods=["GET", "POST"])
def cap():
    if request.method == "POST":
        f = request.form
        c = db().execute("SELECT * FROM cap WHERE id=?", (f["id"],)).fetchone()
        if c and c["status"] == "Verified-Closed" and f["status"] != "Verified-Closed":
            flash("Verified-Closed items can only be reopened by a failing analyzer run.", "err")
        elif f["status"] == "Verified-Closed":
            flash("Verified-Closed is set only by a passing re-test (run 'analyze'). Use 'Remediated - Pending Verification'.", "err")
        else:
            db().execute("UPDATE cap SET owner=?, due=?, status=?, action=?, notes=? WHERE id=?",
                         (f["owner"], f["due"], f["status"], f["action"], f.get("notes", ""), f["id"]))
            db().commit()
            flash(f"{f['id']} updated", "ok")
        return redirect(url_for("cap"))
    rows = [dict(r) for r in db().execute("SELECT * FROM cap")]
    rows.sort(key=lambda r: (r["status"] == "Verified-Closed", SEV_ORDER.get(r["severity"], 9), r["id"]))
    return render_template("cap.html", rows=rows, states=[s for s in CAP_STATES if s != "Verified-Closed"],
                           today=datetime.date.today().isoformat())


# ---------------- API ----------------
@app.route("/api/obligations")
def api_obligations():
    return jsonify([dict(r) for r in db().execute("SELECT * FROM obligations ORDER BY id")])


@app.route("/api/status")
def api_status():
    return jsonify({"obligations": obligation_rows(),
                    "cap": [dict(r) for r in db().execute("SELECT * FROM cap ORDER BY id")]})


@app.route("/api/gaps", methods=["POST"])
def api_gaps():
    run = request.get_json(force=True)
    d = db()
    cur = d.execute("INSERT INTO runs(ts,audit_date,collection_id,counts,unregistered) VALUES(?,?,?,?,?)",
                    (run["run_at"], run["audit_date"], run["collection_id"], json.dumps(run["counts"]),
                     json.dumps(run.get("unregistered_obligations", []))))
    rid = cur.lastrowid
    today = datetime.date.fromisoformat(run["audit_date"])
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    opened = reopened = verified = 0
    for r in run["results"]:
        d.execute("INSERT INTO results VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (rid, r["id"], r["obligation"], r["title"], r["asset"], r["artifact"], r.get("sha256"),
                   r["status"], r["severity"], r["detail"], r.get("root_cause"), r.get("remediation")))
        if r["status"] in ("PASS", "FAIL") and r.get("sha256"):
            d.execute("INSERT OR REPLACE INTO links(obligation_id,artifact,sha256,linked_by,note,ts) VALUES(?,?,?,?,?,?)",
                      (r["obligation"], r["evidence_path"], r["sha256"], "analyzer", f"{r['id']}: {r['status']}", stamp))
        c = d.execute("SELECT * FROM cap WHERE check_id=?", (r["id"],)).fetchone()
        if r["status"] in ("FAIL", "NO_EVIDENCE"):
            if not c:
                n = d.execute("SELECT COUNT(*) FROM cap").fetchone()[0] + 1
                due = (today + datetime.timedelta(days=DUE_DAYS.get(r["severity"], 90))).isoformat()
                gap = f"{r['title']} - {r['detail']}"
                d.execute("INSERT INTO cap VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (f"CAP-{n:03d}", r["id"], r["obligation"], r["severity"], gap, r.get("root_cause"),
                           r.get("remediation"), "", due, "Open", stamp, None, None, ""))
                opened += 1
            elif c["status"] in ("Verified-Closed", "Remediated - Pending Verification"):
                d.execute("UPDATE cap SET status='Open', closed=NULL, notes=COALESCE(notes,'') || ? WHERE id=?",
                          (f"\n[{stamp}] Re-test run #{rid} FAILED - reopened.", c["id"]))
                reopened += 1
        elif r["status"] == "PASS" and c and c["status"] != "Verified-Closed":
            d.execute("UPDATE cap SET status='Verified-Closed', closed=?, verified_run=?, notes=COALESCE(notes,'') || ? WHERE id=?",
                      (stamp, rid, f"\n[{stamp}] Re-test run #{rid} PASSED (evidence sha256 {r['sha256'][:16]}...).", c["id"]))
            verified += 1
    d.commit()
    return jsonify({"run_id": rid, "cap_opened": opened, "cap_reopened": reopened, "cap_verified": verified})


@app.route("/export/<name>.csv")
def export(name):
    out = io.StringIO()
    w = csv.writer(out)
    if name == "register":
        rows = obligation_rows()
        cols = ["id", "source", "clause", "title", "requirement", "control_ref", "owner", "frequency", "status", "checks", "fails", "links", "origin"]
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])
    elif name == "cap":
        rows = db().execute("SELECT * FROM cap ORDER BY id").fetchall()
        if rows:
            w.writerow(rows[0].keys())
        for r in rows:
            w.writerow(list(r))
    elif name == "evidence":
        w.writerow(["obligation_id", "artifact", "sha256", "linked_by", "note", "ts"])
        for r in db().execute("SELECT obligation_id,artifact,sha256,linked_by,note,ts FROM links ORDER BY obligation_id"):
            w.writerow(list(r))
    else:
        abort(404)
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=ex51_{name}.csv"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), threaded=True)
