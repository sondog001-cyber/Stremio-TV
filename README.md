# NexoTV — US National + Philadelphia Local

This repository automatically merges:

- US national IPTV-org playlist
- Philadelphia local IPTV-org playlist

It refreshes every 6 hours and writes `combined.m3u`.

## NexoTV Playlist URL

After uploading this repo to GitHub, use:

`https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/combined.m3u`

## EPG URL

`https://vcicio.github.io/US-EPG/states/PA.xml.gz`

Recommended NexoTV settings:

- Enable EPG: ON
- Reformat Logos: OFF
- Global User-Agent: blank
- Catalog Name: `US + Philadelphia TV`

## First run

1. Open GitHub repo → Actions.
2. Open `Update combined IPTV playlist`.
3. Click `Run workflow`.
4. Wait for `combined.m3u` to appear in the repo.
