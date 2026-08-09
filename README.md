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


# License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.