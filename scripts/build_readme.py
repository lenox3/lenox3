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


def build():
    repo_list = repos()
    langs = languages(repo_list)
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
  <img height="165" alt="GitHub stats" src="https://github-readme-stats.vercel.app/api?username={USER}&show_icons=true&hide_border=true&bg_color=0F1012&title_color=E8E9EC&text_color=A5A8B1&icon_color=4C8DFF&hide_title=true&rank_icon=github">
  <img height="165" alt="Top languages" src="https://github-readme-stats.vercel.app/api/top-langs/?username={USER}&layout=compact&hide_border=true&bg_color=0F1012&title_color=E8E9EC&text_color=A5A8B1&langs_count=6">
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
