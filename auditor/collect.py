#!/usr/bin/env python3
"""Evidence collector - pulls configuration artifacts from OT assets into the
virtual evidence repository with SHA-256 hashing and a chain-of-custody log."""
import datetime, hashlib, json, os, shutil, sys, urllib.request
import yaml

EVID = os.environ.get("EVIDENCE_DIR", "/evidence")
CONF = os.environ.get("ASSETS_FILE", "/opt/audit/assets.yaml")
URL_TPL = os.environ.get("ASSET_URL_TEMPLATE", "http://{asset}:8080/{file}")
COLLECTOR = os.environ.get("AUDITOR_NAME", "trainee")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def main():
    assets = yaml.safe_load(open(CONF))["assets"]
    now = datetime.datetime.now(datetime.timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    snap_dir = os.path.join(EVID, "collections", ts)
    cur_dir = os.path.join(EVID, "current")
    tmp_dir = cur_dir + ".tmp"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    manifest = {"collection_id": ts, "collected_at": now.isoformat(), "collector": COLLECTOR, "artifacts": []}
    ok = fail = 0
    print(f"[*] Collection {ts}  ->  {snap_dir}")
    for asset, meta in assets.items():
        for f in meta["files"]:
            url = URL_TPL.format(asset=asset, file=f)
            try:
                data = urllib.request.urlopen(url, timeout=5).read()
            except Exception as e:
                print(f"  [!] {asset}/{f}: unreachable ({e})")
                manifest["artifacts"].append({"asset": asset, "file": f, "path": f"{asset}/{f}", "status": "UNREACHABLE", "source_url": url})
                fail += 1
                continue
            for d in (snap_dir, tmp_dir):
                os.makedirs(os.path.join(d, asset), exist_ok=True)
                with open(os.path.join(d, asset, f), "wb") as out:
                    out.write(data)
            h = sha256(data)
            manifest["artifacts"].append({"asset": asset, "file": f, "path": f"{asset}/{f}", "sha256": h,
                                          "size": len(data), "source_url": url, "status": "COLLECTED",
                                          "asset_description": meta.get("description", "")})
            print(f"  [+] {asset}/{f:28s} {len(data):6d} B  sha256={h[:16]}...")
            ok += 1
    if ok == 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(snap_dir, ignore_errors=True)
        print("[!] No artifacts collected - evidence repository left unchanged.")
        print("    The asset containers are serving empty folders. On the host run:")
        print("      ./lab.sh seed      (copies seed/assets into range/assets)")
        print("    then re-run collect. './lab.sh doctor' checks the range.")
        return 2
    os.makedirs(snap_dir, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)
    for d in (snap_dir, tmp_dir):
        with open(os.path.join(d, "manifest.json"), "w") as out:
            json.dump(manifest, out, indent=2)
    shutil.rmtree(cur_dir, ignore_errors=True)
    os.rename(tmp_dir, cur_dir)
    mh = sha256(open(os.path.join(snap_dir, "manifest.json"), "rb").read())
    with open(os.path.join(EVID, "custody.log"), "a") as log:
        log.write(f"{now.isoformat()}\tCOLLECT\t{ts}\tcollector={COLLECTOR}\tartifacts={ok}\tfailed={fail}\tmanifest_sha256={mh}\n")
    print(f"[*] {ok} artifacts collected, {fail} failed. Manifest sha256={mh}")
    print(f"[*] Chain of custody appended to {EVID}/custody.log")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
