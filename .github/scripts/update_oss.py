#!/usr/bin/env python3
"""Rebuild the Open Source section of README.md from my merged pull requests.

Finds every merged pull request I authored in someone else's public repository,
groups them by repository (most recently merged first) and writes one card per
repository between the OSS:START and OSS:END markers. oss.json can override a
card's name, icon, tagline, summary and language; without an entry a card uses
the owner's avatar, the repository's description and the latest pull request's
title.
"""
import html
import json
import os
import sys
import urllib.parse
import urllib.request

USER = "itssali"
# My own repositories, and work repositories that must never be listed.
EXCLUDED_OWNERS = ["itssali", "edi2xml"]
README = "README.md"
OVERRIDES = "oss.json"
START, END = "<!-- OSS:START -->", "<!-- OSS:END -->"
RAW = "https://raw.githubusercontent.com/itssali/itssali/main/"
ACCENT, DARK = "D98A66", "35322D"
PER_ROW = 3
ROW_WIDTH = 1600  # Spacer width per row, as in the other boxes.


def api(path):
    request = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER},
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def merged_pull_requests():
    query = f"is:pr is:merged author:{USER} " + " ".join(f"-user:{owner}" for owner in EXCLUDED_OWNERS)
    items = api("/search/issues?per_page=100&sort=updated&q=" + urllib.parse.quote(query))["items"]
    repos = {}
    for item in items:
        full_name = item["repository_url"].split("/repos/", 1)[1]
        repos.setdefault(full_name, []).append({
            "number": item["number"],
            "title": item["title"],
            "url": item["html_url"],
            "merged_at": item["pull_request"]["merged_at"],
        })
    return repos


def card(full_name, info, prs, override, width):
    e = html.escape  # Attributes.
    t = lambda s: html.escape(s, quote=False)  # Text.
    owner = full_name.split("/")[0]
    icon = override.get("icon")
    icon = RAW + icon if icon else f"https://github.com/{owner}.png?size=128"
    name = override.get("name") or info["name"]
    tagline = override.get("tagline") or (info.get("description") or "").strip()
    summary = override.get("summary") or prs[0]["title"]
    language = override.get("language") or info.get("language")
    badges = "\n".join(
        f'<a href="{e(pr["url"])}"><img alt="Pull request {pr["number"]}, merged" '
        f'src="https://img.shields.io/badge/PR%20%23{pr["number"]}-merged-{ACCENT}'
        f'?style=flat-square&logo=github&logoColor=white&labelColor={DARK}"/></a>'
        for pr in prs
    )
    lines = [
        '<td width="{}%" align="center" valign="top">'.format(100 // PER_ROW),
        f'<img alt="" height="1" width="{width}" src="{RAW}assets/spacer.png"/>',
        "",
        "<br/>",
        f'<a href="{e(info["html_url"])}"><img alt="The {e(name)} icon" src="{e(icon)}" width="64"/></a>',
        f'<h3 align="center">{t(name)}</h3>',
    ]
    if tagline:
        lines.append(f'<p align="center"><em>{t(tagline)}</em></p>')
    lines.append(f'<p align="center">\n{t(summary)}\n</p>')
    if language:
        lines.append(f'<p align="center"><code>{t(language)}</code></p>')
    lines += [
        '<p align="center">',
        badges,
        f'<a href="{e(info["html_url"])}"><img alt="Stars on {e(name)}" '
        f'src="https://img.shields.io/github/stars/{full_name}?style=flat-square&label=stars'
        f'&color={ACCENT}&labelColor={DARK}"/></a>',
        "</p>",
        "<br/>",
        "</td>",
    ]
    return "\n".join(lines)


def main():
    with open(OVERRIDES, encoding="utf-8") as f:
        overrides = json.load(f)
    cards = []
    repos = merged_pull_requests()
    for full_name, prs in repos.items():
        info = api(f"/repos/{full_name}")
        if info.get("private"):
            continue
        prs.sort(key=lambda pr: pr["merged_at"], reverse=True)
        cards.append((prs[0]["merged_at"], full_name, info, prs))
    if not cards:
        # Never wipe the section because a search came back empty.
        print("No merged pull requests found; leaving README.md as it is.")
        return 0
    cards.sort(key=lambda c: c[0], reverse=True)

    rows = []
    for i in range(0, len(cards), PER_ROW):
        row = cards[i:i + PER_ROW]
        width = ROW_WIDTH // len(row)
        cells = "\n".join(card(name, info, prs, overrides.get(name, {}), width) for _, name, info, prs in row)
        rows.append(f'<table align="center">\n<tr>\n{cells}\n</tr>\n</table>')
    section = f"{START}\n" + "\n\n".join(rows) + f"\n{END}"

    with open(README, encoding="utf-8") as f:
        readme = f.read()
    if START not in readme or END not in readme:
        print(f"{README} has no {START} … {END} markers.", file=sys.stderr)
        return 1
    before, rest = readme.split(START, 1)
    after = rest.split(END, 1)[1]
    with open(README, "w", encoding="utf-8") as f:
        f.write(before + section + after)
    print(f"Wrote {len(cards)} card(s): " + ", ".join(name for _, name, _, _ in cards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
