"""Exercise only the five generated services assigned to each test team."""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.cookies import SimpleCookie
import ipaddress
import json
import re
import secrets
import subprocess
import sys
import uuid


class Player:
    def __init__(self, index):
        self.index = index
        self.token = ""
        self.fingerprint = secrets.token_hex(32)

    def api(self, path, body=None, *, config=False):
        conn = HTTPConnection("127.0.0.1", 18080, timeout=20,
                              source_address=(f"127.10.{self.index}.1", 0))
        headers = {"Origin": "http://127.0.0.1:18080", "Content-Type": "application/json"}
        if body is not None:
            headers["Idempotency-Key"] = str(uuid.uuid4())
        if self.token:
            headers["Cookie"] = f"RSCTF_Token={self.token}"
        try:
            conn.request("GET" if body is None else "POST", path,
                         None if body is None else json.dumps(body), headers)
            response = conn.getresponse()
            data = response.read(65537)
            if response.status != 200 or len(data) > 65536:
                # Configs, response bodies and cookies may carry private credentials.
                raise RuntimeError(f"player {self.index}: {path} returned HTTP {response.status}")
            for key, value in response.getheaders():
                if key.lower() == "set-cookie":
                    cookie = SimpleCookie(value)
                    if "RSCTF_Token" in cookie:
                        self.token = cookie["RSCTF_Token"].value
            if config:
                return data.decode()
            obj = json.loads(data) if data else None
            return obj.get("data", obj) if isinstance(obj, dict) else obj
        finally:
            conn.close()

    def register(self, bootstrap=None):
        name = f"event{self.index:02d}"
        body = {"userName": name, "email": f"{name}@example.test",
                "password": secrets.token_urlsafe(24), "operationId": str(uuid.uuid4()),
                "fingerprint": self.fingerprint}
        if bootstrap:
            body["bootstrapToken"] = bootstrap
        self.api("/api/account/register", body)
        if not self.token:
            raise RuntimeError("registration did not issue the test account a session")


def enroll(game, bootstrap):
    Player(0).register(bootstrap)
    teams = {}
    for team in range(5):
        players = [Player(team * 4 + n + 1) for n in range(4)]
        for player in players:
            player.register()
        captain = players[0]
        team_id = captain.api("/api/team", {"name": f"Rehearsal {team + 1}"})["id"]
        invite = captain.api(f"/api/team/{team_id}/invite")["code"]
        for player in players[1:]:
            player.api("/api/team/accept", {"code": invite, "fingerprint": player.fingerprint})
        for player in players:
            player.api(f"/api/game/{game}", {"teamId": team_id, "fingerprint": player.fingerprint})
        teams[team_id] = players
    return teams


def start_client(player, game, private, cleanup):
    profile = player.api(f"/api/Game/{game}/Ad/Vpn/Config", config=True)
    values = dict(line.split(" = ", 1) for line in profile.splitlines() if " = " in line)
    address = str(ipaddress.ip_interface(values["Address"]))
    routes = [str(ipaddress.ip_network(r.strip())) for r in values["AllowedIPs"].split(",")]
    name = f"rsc{player.index}"
    def run(*args):
        subprocess.run(args, check=True, capture_output=True, timeout=10)
    file = private / (name + ".conf")
    file.write_text("\n".join(line for line in profile.splitlines()
                              if not line.startswith(("Address = ", "DNS = "))) + "\n")
    file.chmod(0o600)
    run("ip", "netns", "add", name)
    cleanup.callback(subprocess.run, ["ip", "netns", "del", name], capture_output=True)
    run("ip", "link", "add", name, "type", "wireguard")
    cleanup.callback(subprocess.run, ["ip", "link", "del", name], capture_output=True)
    run("wg", "setconf", name, str(file))
    run("ip", "link", "set", name, "netns", name)
    run("ip", "-n", name, "addr", "add", address, "dev", name)
    run("ip", "-n", name, "link", "set", "lo", "up")
    run("ip", "-n", name, "link", "set", name, "up")
    for route in routes:
        run("ip", "-n", name, "route", "replace", route, "dev", name)
    return address


def probe(endpoint):
    host, port = endpoint
    if ipaddress.ip_address(host) not in ipaddress.ip_network("10.214.0.0/24"):
        raise ValueError("service outside the rehearsal network")
    conn = HTTPConnection(host, port, timeout=4)
    try:
        conn.request("GET", "/installation")
        response = conn.getresponse()
        value = response.read(33)
        if response.status != 200 or not re.fullmatch(b"[0-9a-f]{32}", value):
            raise ValueError("invalid installation marker")
        return value.decode()
    finally:
        conn.close()


def sample(teams, endpoints):
    def check(item):
        team_id, player = item
        result = subprocess.check_output(["ip", "netns", "exec", f"rsc{player.index}",
                                          sys.executable, __file__, json.dumps(endpoints[team_id])],
                                         timeout=30)
        return team_id, json.loads(result)
    markers = {}
    with ThreadPoolExecutor(max_workers=5) as workers:
        for team, seen in workers.map(check, [(t, p) for t, players in teams.items() for p in players]):
            if len(seen) != 5 or markers.setdefault(team, seen) != seen:
                raise ValueError("teammates reached different installations")
    if len({m for values in markers.values() for m in values}) != 25:
        raise ValueError("expected 25 distinct service installations")
    return markers


if __name__ == "__main__":
    print(json.dumps([probe(endpoint) for endpoint in json.loads(sys.argv[1])]))
