# ZIP patches for hosted A&D

Use the [hosted ZIP starter package](../.templates/challenges/AD/Pwn/hosted-zip).
See [Hosted + ZIP](ad-templates.md#hosted--zip) for building its original service image.
ZIP patching uses `type: AttackDefense` and `ad.selfHosted: false`.
BYOC teams apply patches on their own hosts.

## Register from YAML

On an RSCTF version that supports `ad.starterZip`, archive the committed service
context next to its manifest and add the filename:

```sh
package=challenges/AD/Pwn/your-challenge
git archive --format=zip --output="$package/starter.zip" "HEAD:$package/src"
```

```yaml
ad:
  selfHosted: false
  starterZip: starter.zip
```

Commit the ZIP and manifest together, then scan the trusted Repository Binding
before kickoff. The importer registers the starter and pairs it with the original
build. To replace a saved starter before kickoff, use **Team patching**.

On earlier RSCTF versions, use the challenge editor to register the archive.

## Prepare the starter ZIP

1. Import the challenge and build its service image from the source you intend to
   give teams.
2. Archive the files from that same service build context. The ZIP needs a
   `Dockerfile` at its root, alongside the files it builds. Include only files you
   intend to distribute to teams.
3. In **Admin → Games → Challenges → Team patching**, choose **Starter ZIP for team
   patches**, upload the ZIP, and click **Save starter ZIP** before kickoff. Verify
   the starter is paired with the correct original image.

For example, from the repository root you can archive a reviewed, committed
`src/` directory directly. Set the path to your challenge and use the revision
from which its original image was built.

```sh
service=challenges/AD/Pwn/your-challenge/src
revision=HEAD
git archive --format=zip --output=starter.zip "$revision:$service"
```

## Optional ZIP metadata

| Template | When to use it |
| --- | --- |
| [`.rsctf-ssh.json.example`](../.templates/ad-patch/.rsctf-ssh.json.example) | Register source paths for hosted Docker SSH edit history. Copy it to the ZIP root as `.rsctf-ssh.json` and match each source path to the corresponding file in your service image. |
| [`.rsctf-data-dir.example`](../.templates/ad-patch/.rsctf-data-dir.example) | Use a persistent data directory for hosted Kubernetes. Copy it to the ZIP root as `.rsctf-data-dir`, put your service's data path on its single line, then save the starter before provisioning. |

## Rehearse the team flow

In a hidden event, sign in as a team member and open **A&D Toolkit → Patch your
service**. Download the starter, edit a file, then upload the revised ZIP and use
**Compare files**. **Save private revision** records the source. Deployment is a
separate step that uses a built revision.

Use `rsctf challenge patch-preview starter.zip candidate.zip` to review paths and
permission changes locally. See the [RSCTF organizer guide](https://github.com/dimasma0305/rsctf/blob/4c877bdadb4b020702585c59038273a8eeb95ec4/docs/organizers/challenges.md#compare-two-ad-source-zips)
for builds, deployment, rollback, and storage.
