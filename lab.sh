#!/usr/bin/env bash
# Exercise 5.1 lab helper
set -euo pipefail
cd "$(dirname "$0")"
DC="docker compose"
ASSETS="ot-fw eng-ws historian plc-gw vendor-ra grc-docs"

# Seed each asset folder that is missing or empty (Docker creates empty dirs for
# bind mounts if 'docker compose up' runs before seeding). Never overwrites remediations.
seed_assets() {
  [ -d seed/assets ] || { echo "[!] seed/assets not found - run from the lab folder"; exit 1; }
  for a in $ASSETS; do
    mkdir -p "range/assets/$a"
    if [ -z "$(ls -A "range/assets/$a" 2>/dev/null)" ]; then
      cp -r "seed/assets/$a/." "range/assets/$a/"
      echo "[*] Seeded range/assets/$a"
    fi
  done
  chmod -R a+rX range/assets
}

doctor() {
  local bad=0
  for a in $ASSETS; do
    n=$(ls -A "range/assets/$a" 2>/dev/null | wc -l)
    if [ "$n" -eq 0 ]; then echo "  [FAIL] range/assets/$a is empty or missing"; bad=1
    else
      seen=$($DC exec -T "$a" sh -c 'ls /asset | wc -l' 2>/dev/null || echo 0)
      if [ "${seen:-0}" -eq 0 ]; then echo "  [FAIL] $a container sees no files in /asset (container down or mount stale - try ./lab.sh restart)"; bad=1
      else echo "  [ OK ] $a  host files=$n  container files=$seen"; fi
    fi
  done
  [ $bad -eq 0 ] && echo "[*] Range healthy" || echo "[!] Fix: ./lab.sh seed && ./lab.sh restart"
}

case "${1:-help}" in
  up)       seed_assets; $DC up -d --build
            # remove nginx default pages copied into the evidence volume by older lab versions
            $DC exec -T auditor rm -f /evidence/index.html /evidence/50x.html 2>/dev/null || true
            echo; echo "  Portal:              http://localhost:8080"
            echo "  Evidence repository: http://localhost:8081"
            echo "  Auditor shell:       ./lab.sh shell" ;;
  seed)     seed_assets ;;
  doctor)   doctor ;;
  restart)  seed_assets; $DC up -d --force-recreate ot-fw eng-ws historian plc-gw vendor-ra grc-docs ;;
  collect)  seed_assets; $DC exec auditor collect ;;
  analyze)  $DC exec auditor analyze ;;
  audit)    seed_assets; $DC exec auditor audit ;;
  shell)    $DC exec auditor bash ;;
  status)   $DC ps ;;
  logs)     $DC logs -f --tail=50 "${2:-portal}" ;;
  down)     $DC down ;;
  reset)    $DC down -v; rm -rf range/assets; seed_assets; echo "[*] Range reset to initial (vulnerable) state. Run ./lab.sh up" ;;
  *) cat <<USAGE
Usage: ./lab.sh <command>
  up        build + start the range (seeds range/assets automatically)
  collect   pull configuration artifacts into the evidence repository
  analyze   run automated gap analysis and update the portal / CAP
  audit     collect + analyze (use after every remediation to verify)
  shell     open a shell in the auditor container (bridges IT and OT networks)
  doctor    check every asset folder is seeded and visible inside its container
  seed      re-seed any empty asset folder (keeps your remediations)
  restart   re-seed and recreate the asset containers
  status    show containers        logs [svc]  follow service logs
  down      stop the range         reset       wipe evidence, portal DB and remediations
USAGE
  ;;
esac
