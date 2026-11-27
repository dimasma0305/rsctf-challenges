# A&D starter packages

All three packages include an HTTP service, Dockerfile, editable `banner.txt`, and
Python checker. Use them to rehearse how teams patch before substituting your
competition service. The checker verifies the public banner and the current round's
flag through a keyed proof. The health check works before the first flag arrives.

| How teams patch | Starter package | Where teams edit |
| --- | --- | --- |
| BYOC + SSH | [Self-hosted service](../.templates/challenges/AD/Web/self-hosted-service) | SSH to their own Docker host, then edit the service container |
| Hosted + SSH | [Hosted service](../.templates/challenges/AD/Pwn/attack-defense-service) | Open the team container through RSCTF's SSH bastion |
| Hosted + ZIP | [Hosted ZIP service](../.templates/challenges/AD/Pwn/hosted-zip) | Download the source, edit `banner.txt`, and upload the revised archive |

## Copy a package

Run this from the repository root. Choose a source from the table and a unique
destination in the same category. Fill in the manifest and organizer solution.

```sh
source=.templates/challenges/AD/Pwn/attack-defense-service
package=challenges/AD/Pwn/my-ad-challenge
cp -R "$source" "$package"
mv "$package/challenge.yaml.example" "$package/challenge.yaml"
mkdir -p "$package/solution"
cp .templates/solution/README.md .templates/solution/solve.py "$package/solution/"
make validate
```

Import through **Admin → Repository Bindings** and rehearse in a hidden event.
All three are `AttackDefense` manifests. The BYOC package sets
`ad.selfHosted: true` and reads the flag at `/shared/flag` when launched by
the generated bundle. The hosted packages use `/flag`.

## BYOC + SSH

Download and run the team-specific BYOC setup from **A&D Toolkit** on the team's
Docker host. SSH into that host with the team's own account. From the generated
Compose directory, use `docker compose exec service sh` to open the shell. Edit
`/app/banner.txt` and refresh the service. See the [BYOC player guide](https://github.com/dimasma0305/rsctf/blob/4c877bdadb4b020702585c59038273a8eeb95ec4/docs/players/attack-defense.md#d1-bring-your-own-container-byoc-challenges)
for setup and the platform's optional BYOC shell.

## Hosted + SSH

Register your SSH public key in **A&D Toolkit** and use the displayed command for
the team's hosted service. Edit `/app/banner.txt` and refresh the page. The
service reads it on each request, so you can see the change immediately.

```sh
printf 'Our team is ready.\n' > /app/banner.txt
```

## Hosted + ZIP

The ZIP package uses `FROM rsctf-starter` so the isolated worker can use the same
approved offline base as the original image. For a local organizer build, supply
the pinned Python base through a named Docker Buildx context from the new package:

```sh
base=python:3.12-alpine@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89
docker buildx build --platform linux/amd64 --load --tag ad-zip-starter:local \
  --build-context "rsctf-starter=docker-image://docker.io/library/$base" src
```

Build and publish the original image from this same context for RSCTF, and set
`container.containerImage` to its immutable registry reference. Configure the
ZIP build worker with the matching approved OCI base. Then follow the
[starter ZIP upload and team revision steps](hosted-ad-zip.md). Edit `banner.txt`
in the downloaded starter to check that the uploaded revision changes the banner
after the new image is deployed.
