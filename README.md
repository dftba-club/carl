# DFTBA.CLUB Mastodon Bot

This is a simple Mastodon Bot written in Python for the [DFTBA.Club Mastodon Server](https://dftba.club).
It uses env variables so it can certainly be deployed on any other instance but the features are centered around monitoring
for relevant podcast and YouTube channel updates for the community.


# Container image

Images are built and published to [GitHub Container Registry](https://ghcr.io) by
[`.github/workflows/publish.yml`](.github/workflows/publish.yml) on every push to `main`, for
both `linux/amd64` and `linux/arm64`:

```
docker pull ghcr.io/dftba-club/carl:latest
```

Each build also publishes an immutable `sha-<short-commit>` tag if you want to pin a specific
version instead of `latest`.


# Command trust model

Every mention is classified as one of `OWNER`, `STAFF`, `LOCAL`, or `PUBLIC`, based on the
account that sent it (see `role_for` in `bot.py`):

- **OWNER** — the account configured as `OWNER`. Can use every command, including `say`
  (post arbitrary text as the bot) and `ping`.
- **STAFF** — accounts listed in `STAFF`. Same reach as OWNER today (no command is
  STAFF-only yet).
- **LOCAL** — *any* account registered on this instance, i.e. `acct` with no `@domain`
  suffix. Can use `lastvideo`, `lastpod`, `searchvideo`, `searchpod`.
- **PUBLIC** — everyone else (remote accounts). Can't use any command.

`LOCAL` trust is granted purely by "having an account on this instance" — the bot has no
separate notion of a trusted user. That means the blast radius of anything reachable by
`LOCAL` (currently: making the bot post an unlisted reply containing attacker-chosen search
text, rate-limited to one request per minute per account) is exactly **whoever can register
an account here**. If this instance ever opens public registration, treat those four
commands as effectively public and re-evaluate whether they should stay LOCAL-accessible.


# License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.