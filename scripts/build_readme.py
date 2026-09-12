"""Regenerates README.md from the account's public repositories.

Runs on a schedule in GitHub Actions (see .github/workflows/update-readme.yml) and locally with
`GITHUB_TOKEN=$(gh auth token) python scripts/build_readme.py`.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("PROFILE_USER", "lenox3")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BADGE_LOGOS = {
    "C#": "csharp", "JavaScript": "javascript", "TypeScript": "typescript", "Lua": "lua", "CSS": "css3", "HTML": "html5",
    "Python": "python", "Rust": "rust", "Go": "go", "C++": "cplusplus", "C": "c", "Shell": "gnubash", "PowerShell": "powershell",
    "Java": "openjdk", "Kotlin": "kotlin", "Swift": "swift", "Dart": "dart", "PHP": "php", "Ruby": "ruby", "Vue": "vuedotjs", "SCSS": "sass",
}


def api(path):
    req = urllib.request.Request("https://api.github.com" + path, headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-readme"})
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def repos():
    out = []
    page = 1
    while True:
        batch = api(f"/users/{USER}/repos?per_page=100&sort=updated&page={page}")
        if not batch:
            break
        out.extend(batch)
        page += 1
    out = [r for r in out if not r["fork"] and not r["archived"] and r["name"].lower() != USER.lower()]
    # Stars first, then most recently pushed.
    out.sort(key=lambda r: (-r["stargazers_count"], r["pushed_at"]), reverse=False)
    out.sort(key=lambda r: r["pushed_at"], reverse=True)
    out.sort(key=lambda r: r["stargazers_count"], reverse=True)
    return out


def languages(repo_list):
    totals = {}
    for r in repo_list:
        try:
            for lang, size in api(f"/repos/{USER}/{r['name']}/languages").items():
                totals[lang] = totals.get(lang, 0) + size
        except Exception:
            pass
    return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)


def card(r):
    lang = r["language"] or ""
    stars = r["stargazers_count"]
    updated = datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")).strftime("%b %Y")
    meta = " · ".join(x for x in [f"<code>{esc(lang)}</code>" if lang else "", f"★ {stars}" if stars else "", f"updated {updated}"] if x)
    desc = esc(r["description"]) or "<em>No description yet.</em>"
    return (
        f'<td width="50%" valign="top">\n'
        f'  <h3><a href="{r["html_url"]}">{esc(r["name"])}</a></h3>\n'
        f'  <p>{desc}</p>\n'
        f'  <p><sub>{meta}</sub></p>\n'
        f'</td>'
    )


LANG_COLORS = {
    "C#": "#4C8DFF", "JavaScript": "#F0B35B", "TypeScript": "#3B82F6", "Lua": "#8A8FF0", "CSS": "#D8506A", "HTML": "#E0813E",
    "Python": "#3DB8A5", "Rust": "#D9775F", "Go": "#5FC9E3", "C++": "#F27B9B", "PowerShell": "#7CA9F5", "Shell": "#9BD16F", "Inno Setup": "#B58CF0",
}
PALETTE = ["#4C8DFF", "#3DB8A5", "#F0B35B", "#D8506A", "#8A8FF0", "#E0813E", "#7CA9F5", "#9BD16F"]


def svg_card(width, height, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="Inter, \'Segoe UI\', Helvetica, Arial, sans-serif">\n'
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" fill="#0F1012" stroke="#FFFFFF" stroke-opacity="0.09"/>\n'
        f"{body}\n</svg>\n"
    )


def stats_svg(user, repo_list):
    info = api(f"/users/{user}")
    stars = sum(r["stargazers_count"] for r in repo_list)
    forks = sum(r["forks_count"] for r in repo_list)
    try:
        commits = api(f"/search/commits?q=author:{user}&per_page=1")["total_count"]
    except Exception:
        commits = None
    items = [("Public repositories", len(repo_list)), ("Stars earned", stars), ("Forks", forks), ("Followers", info.get("followers", 0))]
    if commits is not None:
        items.insert(1, ("Commits", commits))
    body = [f'<text x="24" y="36" font-size="15" font-weight="600" fill="#E8E9EC">{esc(info.get("name") or user)} on GitHub</text>']
    y = 70
    for label, value in items:
        body.append(f'<text x="24" y="{y}" font-size="13" fill="#A5A8B1">{esc(label)}</text>')
        body.append(f'<text x="336" y="{y}" font-size="13" font-weight="600" fill="#E8E9EC" text-anchor="end">{value:,}</text>')
        y += 26
    body.append('<rect x="24" y="52" width="312" height="1" fill="#FFFFFF" fill-opacity="0.08"/>')
    return svg_card(360, y - 4, "\n".join(body))


def languages_svg(langs):
    total = sum(s for _, s in langs) or 1
    top = langs[:6]
    body = ['<text x="24" y="36" font-size="15" font-weight="600" fill="#E8E9EC">Languages</text>']
    # stacked bar
    x = 24.0
    for i, (lang, size) in enumerate(top):
        w = 312 * size / total
        color = LANG_COLORS.get(lang, PALETTE[i % len(PALETTE)])
        body.append(f'<rect x="{x:.1f}" y="52" width="{max(w - 2, 1):.1f}" height="8" rx="3" fill="{color}"/>')
        x += w
    y = 88
    for i, (lang, size) in enumerate(top):
        color = LANG_COLORS.get(lang, PALETTE[i % len(PALETTE)])
        pct = 100 * size / total
        col = 24 if i % 2 == 0 else 190
        body.append(f'<circle cx="{col + 5}" cy="{y - 4}" r="5" fill="{color}"/>')
        body.append(f'<text x="{col + 17}" y="{y}" font-size="13" fill="#E8E9EC">{esc(lang)} <tspan fill="#A5A8B1">{pct:.1f}%</tspan></text>')
        if i % 2 == 1:
            y += 24
    if len(top) % 2 == 1:
        y += 24
    return svg_card(360, y + 2, "\n".join(body))


def build():
    repo_list = repos()
    langs = languages(repo_list)
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    open(os.path.join(ROOT, "assets", "stats.svg"), "w", encoding="utf-8", newline="\n").write(stats_svg(USER, repo_list))
    open(os.path.join(ROOT, "assets", "languages.svg"), "w", encoding="utf-8", newline="\n").write(languages_svg(langs))
    badges = " ".join(
        f'<img alt="{esc(l)}" src="https://img.shields.io/badge/{urllib.request.quote(l).replace("-", "--").replace("_", "__")}-1B1D21?style=flat-square'
        + (f'&logo={BADGE_LOGOS[l]}&logoColor=E8E9EC' if l in BADGE_LOGOS else "&logoColor=E8E9EC") + '">'
        for l, _ in langs[:10]
    )
    rows = []
    for i in range(0, len(repo_list), 2):
        cells = "\n".join(card(r) for r in repo_list[i:i + 2])
        rows.append(f"<tr>\n{cells}\n</tr>")
    table = "<table>\n" + "\n".join(rows) + "\n</table>" if rows else "<p><em>Nothing public yet.</em></p>"
    n = len(repo_list)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<p align="center">
  <img src="assets/header.svg" alt="Lenox — vibecoder" width="100%">
</p>

<br>

I'm a **vibecoder**. I describe what I want, iterate with AI in the loop, test it against reality, and ship it. Most of what lands here is Windows desktop software and FiveM scripts, and all of it is meant to feel instant.

<br>

## Projects

<sub>{n} public {"repository" if n == 1 else "repositories"}, listed by stars and recent activity. This page rebuilds itself from GitHub every few hours.</sub>

{table}

## Languages across my repos

<p>{badges}</p>

## Activity

<p>
  <img alt="GitHub stats" src="assets/stats.svg" width="360">
  <img alt="Languages" src="assets/languages.svg" width="360">
</p>

<p align="center"><sub>Generated {stamp} by <a href="scripts/build_readme.py">scripts/build_readme.py</a>.</sub></p>
"""


if __name__ == "__main__":
    content = build()
    path = os.path.join(ROOT, "README.md")
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    # Ignore the timestamp line when deciding whether anything changed, so the bot does not commit every run.
    strip = lambda s: "\n".join(l for l in s.splitlines() if not l.startswith('<p align="center"><sub>Generated'))
    if strip(old) == strip(content):
        print("README unchanged")
        sys.exit(0)
    open(path, "w", encoding="utf-8", newline="\n").write(content)
    print("README updated")
