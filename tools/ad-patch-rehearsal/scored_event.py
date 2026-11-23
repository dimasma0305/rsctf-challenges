"""Run the generated event in the RSCTF server on a disposable native Linux runner."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

import psycopg

from event_clients import enroll, sample, start_client
from generate import generate


def command(*args, timeout=180):
    return subprocess.check_output(args, text=True, timeout=timeout).strip()


def wait_for(check, seconds, what):
    deadline = time.monotonic() + seconds
    while True:
        result = check()
        if result:
            return result
        if time.monotonic() >= deadline:
            raise TimeoutError(what)
        time.sleep(2)


def prepare(root, report):
    event = root / "event"
    generate(event)
    packages = sorted((event / "repository/challenges/AD/Web").iterdir())
    if len(packages) != 5:
        raise ValueError("expected five generated challenges")
    images = {}
    for pkg in packages:
        start = time.monotonic()
        image = command("docker", "build", "--quiet", "-t", f"rsctf-event/{pkg.name}", str(pkg / "src"))
        report["buildSeconds"][pkg.name] = round(time.monotonic() - start, 2)
        checker = root / "checkers" / pkg.name
        shutil.copytree(pkg / "checker", checker / "src")
        (checker / "venv/bin").mkdir(parents=True)
        (checker / "venv/bin/python3").symlink_to("/usr/bin/python3")
        images[pkg.name] = image, str(checker)
    return images


def seed(db, images):
    # The database and daemon are local to this job. Only organizer-authored
    # fields are seeded. The running platform admits players and creates the services.
    with db.transaction():
        gid = db.execute('''INSERT INTO "Games"
            (title,public_key,private_key,hidden,practice_mode,summary,content,
             accept_without_review,allow_user_submissions,writeup_required,
             team_member_count_limit,container_count_limit,start_time_utc,end_time_utc,
             writeup_deadline,writeup_note,blood_bonus_value,ad_allow_snapshot_download,
             ad_scoring_paused,ad_warmup_seconds,ad_tick_seconds,ad_epoch_ticks)
            VALUES ('Scored fixture',%s,%s,false,false,'','',true,false,false,4,5,
            now()+interval '15 minutes',now()+interval '6 hours',now()+interval '6 hours',
            '',0,true,false,0,120,2) RETURNING id''',
            (secrets.token_hex(32), secrets.token_hex(32))).fetchone()[0]
        for name, (image, checker) in images.items():
            db.execute('''INSERT INTO "GameChallenges"
                (game_id,title,content,category,"Type",is_enabled,submission_limit,
                 accepted_count,submission_count,review_status,build_status,original_score,
                 min_score_rate,difficulty,score_curve,network_mode,enable_traffic_capture,
                 enable_shared_container,disable_blood_bonus,ad_allow_egress,ad_allow_self_reset,
                 ad_ssh_requires_flag,ad_self_hosted,container_image,build_image_digest,
                 ad_checker_image,expose_port,memory_limit,cpu_count,storage_limit)
                VALUES (%s,%s,'',0,4,true,0,0,0,0,1,100,0.25,5,0,0,false,false,true,
                false,true,false,false,%s,%s,%s,8080,64,1,128)''', (gid, name, image, image, checker))
    return gid


def endpoints(db, gid):
    rows = db.execute('''SELECT p.team_id,s.host,s.port FROM "AdTeamServices" s
        JOIN "Participations" p ON p.id=s.participation_id WHERE s.game_id=%s
        AND s.container_id IS NOT NULL AND s.host<>'' AND s.port>0
        ORDER BY p.team_id,s.challenge_id''', (gid,)).fetchall()
    result = {}
    for team, host, port in rows:
        result.setdefault(team, []).append((host, port))
    return result if len(result) == 5 and all(len(e) == 5 for e in result.values()) else None


def score(db, gid):
    return db.execute('''SELECT r.number,
               (SELECT count(*) FROM "AdFlagDeliveryResults" d WHERE d.round_id=r.id AND d.delivered),
               (SELECT count(*) FROM "AdCheckResults" c WHERE c.round_id=r.id AND c.status=0
                    AND c.flag_verified AND c.sla_credit=1.0)
        FROM "AdRounds" r WHERE r.game_id=%s AND r.finalized AND r.pipeline_completed_at IS NOT NULL
        ORDER BY r.number''', (gid,)).fetchall()


def rehearse(mode, report, output, root, cleanup):
    private = root / "private"
    private.mkdir(mode=0o700)
    images = prepare(root, report)
    password = secrets.token_hex(28)
    db_container = subprocess.check_output(
        ["docker", "run", "--rm", "-d", "-p", "127.0.0.1::5432", "-e", "POSTGRES_DB=scored_event",
         "-e", "POSTGRES_PASSWORD", "postgres:18.4-alpine3.24"], text=True, timeout=180,
        env={**os.environ, "POSTGRES_PASSWORD": password}).strip()
    cleanup.callback(subprocess.run, ["docker", "stop", "-t", "2", db_container], capture_output=True)
    port = command("docker", "port", db_container, "5432/tcp").split(":")[-1]
    url = f"postgresql://postgres:{password}@127.0.0.1:{port}/scored_event"
    wait_for(lambda: subprocess.run(["docker", "exec", db_container, "pg_isready", "-h", "127.0.0.1"],
                                     capture_output=True).returncode == 0, 60, "PostgreSQL startup")
    bootstrap = secrets.token_hex(32)
    env = dict(PATH=os.environ["PATH"], RSCTF_DATABASE_URL=url, RSCTF_JWT_SECRET=secrets.token_hex(32),
               RSCTF_IDENTITY_HASH_KEY=secrets.token_hex(32), RSCTF_BOOTSTRAP_TOKEN=bootstrap,
               RSCTF_EVENT_VPN_CREDENTIAL_KEY=secrets.token_hex(32), RSCTF_AD_VPN_ENABLED="true",
               RSCTF_AD_VPN_CLIENT_CIDR="10.213.0.0/24", RSCTF_AD_VPN_SERVICES_CIDR="10.214.0.0/24",
               RSCTF_EVENT_VPN_HUB_ADDRESS="10.213.0.1", RSCTF_EVENT_VPN_INGRESS_IP="10.214.0.253",
               RSCTF_AD_VPN_SERVER_ENDPOINT="127.0.0.1:51822", RSCTF_AD_VPN_LISTEN_PORT="51822",
               RSCTF_EVENT_VPN_PROOF_URL="https://rehearsal.invalid", RSCTF_COOKIE_SECURE="false",
               RSCTF_PUBLIC_URL="http://127.0.0.1:18080", RSCTF_BIND="127.0.0.1:18080",
               RSCTF_DOCKER_SCOPE="scored-event", RSCTF_CONTAINER_BACKEND="docker",
               RSCTF_DOCKER_ALLOW_UNBOUNDED_STORAGE="true", RSCTF_STORAGE_ROOT=str(private / "storage"))
    binary = "/usr/local/bin/rsctf-event"
    subprocess.run([binary], env={**env, "RSCTF_ROLE": "migrate"}, check=True, stdout=subprocess.DEVNULL)
    db = cleanup.enter_context(psycopg.connect(url, autocommit=True))
    gid = seed(db, images)
    log = cleanup.enter_context((private / "server.log").open("w"))
    server = subprocess.Popen([binary], env={**env, "RSCTF_ROLE": "all"}, stdout=log, stderr=log)
    def stop():
        server.terminate()
        try:
            server.wait(15)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
    cleanup.callback(stop)
    def ready():
        if server.poll() is not None:
            raise RuntimeError(f"server exited with status {server.returncode}")
        try:
            with urlopen("http://127.0.0.1:18080/healthz", timeout=2) as res:
                return res.read(16) == b"ok"
        except (URLError, TimeoutError):
            return False
    wait_for(ready, 90, "platform startup")
    teams = enroll(gid, bootstrap)
    addresses = {start_client(p, gid, private, cleanup) for players in teams.values() for p in players}
    if len(addresses) != 20:
        raise ValueError("expected 20 personal VPN addresses")
    report["personalVpnProfiles"] = len(addresses)
    duration = 14400 if mode == "four-hours" else 360
    # Keep the official scheduler active while the last observed round settles.
    db.execute('''UPDATE "Games" SET start_time_utc=clock_timestamp(),
        end_time_utc=clock_timestamp()+(%s * interval '1 second') WHERE id=%s''', (duration + 360, gid))
    routes = wait_for(lambda: endpoints(db, gid), 180, "25 published managed services")
    baseline = sample(teams, routes)
    started = time.monotonic()
    baseline_round = db.execute('''SELECT coalesce(max(number),0) FROM "AdRounds" WHERE game_id=%s''',
                                (gid,)).fetchone()[0]
    report.update(baselineRound=baseline_round, teams=len(teams), services=sum(map(len, baseline.values())))
    while True:
        elapsed = time.monotonic() - started
        if sample(teams, routes) != baseline:
            raise ValueError("installation identity changed")
        handshakes = command("wg", "show", "wg0", "latest-handshakes").splitlines()
        if sum(time.time() - int(row.split()[1]) < 210 for row in handshakes) != 20:
            raise ValueError("expected 20 recent handshakes")
        rounds = [r for r in score(db, gid) if r[0] > baseline_round]
        report.update(elapsedSeconds=round(elapsed, 2), verifiedVpnRequests=report.get("verifiedVpnRequests", 0)+100,
                      peakDiskUsedBytes=max(report.get("peakDiskUsedBytes", 0), shutil.disk_usage("/var/lib/docker").used),
                      scoredRounds=rounds)
        output.write_text(json.dumps(report, indent=2)+"\n")
        if any((delivered, healthy) != (25, 25) for _, delivered, healthy in rounds):
            raise RuntimeError("official flag delivery or checker scoring failed")
        if elapsed >= duration:
            if len(rounds) < duration // 120 - 1 or any(b[0] != a[0]+1 for a,b in zip(rounds,rounds[1:])):
                raise RuntimeError("insufficient consecutive settled rounds")
            break
        time.sleep(min(30, duration-elapsed))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "four-hours"))
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0 or not Path("/usr/local/bin/rsctf-event").is_file():
        raise SystemExit("requires a disposable root runner with the CI server installed")
    report = {"mode": args.mode, "passed": False, "buildSeconds": {}}
    try:
        with tempfile.TemporaryDirectory(prefix="rsctf-event-") as tmp, ExitStack() as cleanup:
            root = Path(tmp)
            root.chmod(0o755)
            rehearse(args.mode, report, args.result, root, cleanup)
        report["passed"] = True
    finally:
        args.result.write_text(json.dumps(report, indent=2)+"\n")
