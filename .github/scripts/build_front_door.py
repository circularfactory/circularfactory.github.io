#!/usr/bin/env python3
"""
Build the Circular Factory front door page from repository metadata.

This script reads repository information from the GitHub API (or a JSON snapshot),
filters and classifies repositories by their topics, and generates an HTML page
listing tools and ontologies published by the organisation.
"""

import argparse
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build the Circular Factory front door page."
    )
    parser.add_argument(
        "--org",
        default="circularfactory",
        help="Organisation to read. Default: circularfactory"
    )
    parser.add_argument(
        "--out",
        default="index.html",
        help="File to write. Default: index.html. Use '-' for stdout."
    )
    parser.add_argument(
        "--repos-json",
        help="Read repository list from a JSON file instead of the API."
    )
    parser.add_argument(
        "--assume",
        action="append",
        default=[],
        metavar="TOPIC:REPO[,REPO...]",
        help="Treat named repositories as if they carry TOPIC. Repeatable."
    )
    parser.add_argument(
        "--banner",
        help="Optional notice band text above the page heading."
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help=(
            "Write the page even when no repository is registered. Without "
            "this flag an empty page is treated as an error and nothing is "
            "written, so a metadata mishap cannot blank the site."
        )
    )
    return parser.parse_args()


def fetch_repos(org: str) -> List[Dict[str, Any]]:
    """Fetch public repositories from GitHub API."""
    url = f"https://api.github.com/orgs/{org}/repos?per_page=100&type=public"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "circularfactory-front-door-builder"
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    repos: List[Dict[str, Any]] = []
    while url:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            repos.extend(data)
            # Check for next page via Link header
            link_header = response.headers.get("Link", "")
            next_url = None
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
                    break
            url = next_url
    return repos


def load_repos_json(path: str) -> List[Dict[str, Any]]:
    """Load repositories from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_assume_specs(specs: List[str]) -> Dict[str, List[str]]:
    """Parse --assume arguments into a topic -> [repo names] mapping."""
    assume_map: Dict[str, List[str]] = {}
    for spec in specs:
        if ":" not in spec:
            raise ValueError(
                f"--assume expects TOPIC:REPO[,REPO...], got {spec!r}"
            )
        topic, repos_str = spec.split(":", 1)
        repos = [r.strip() for r in repos_str.split(",") if r.strip()]
        if not topic.strip() or not repos:
            raise ValueError(
                f"--assume expects TOPIC:REPO[,REPO...], got {spec!r}"
            )
        assume_map.setdefault(topic.strip(), []).extend(repos)
    return assume_map


def select_and_classify(
    repos: List[Dict[str, Any]],
    org: str,
    assume_map: Dict[str, List[str]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Filter and classify repositories.

    Returns: (tools, ontologies, warnings)
    """
    tools: List[Dict[str, Any]] = []
    ontologies: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for repo in repos:
        name = repo["name"]

        # Drop private, archived, forks
        if repo.get("private") or repo.get("archived") or repo.get("fork"):
            continue

        # Drop the host repository itself
        if name == f"{org}.github.io":
            continue

        # Start with actual topics
        topics = list(repo.get("topics", []))

        # Merge in --assume
        for topic, repo_names in assume_map.items():
            if name in repo_names:
                if topic not in topics:
                    topics.append(topic)

        has_tool = "cf-tool" in topics
        has_ontology = "cf-ontology" in topics

        # If both: warn and place under Tools
        if has_tool and has_ontology:
            warnings.append(
                f"::warning title=Duplicate topic::{name} carries both cf-tool and cf-ontology; placing under Tools."
            )
            has_ontology = False

        if has_tool:
            tools.append(repo)
        elif has_ontology:
            ontologies.append(repo)
        else:
            # Unregistered: warn only if has_pages is true
            if repo.get("has_pages"):
                warnings.append(
                    f"::warning title=Unregistered repository::{name} has Pages published but carries neither cf-tool nor cf-ontology, so it is not listed on the front door."
                )

    # Sort each section by name, case-insensitively
    tools.sort(key=lambda r: r["name"].lower())
    ontologies.sort(key=lambda r: r["name"].lower())

    return tools, ontologies, warnings


def make_primary_link(repo: Dict[str, Any], org: str) -> str:
    """Determine the primary link for a repository entry."""
    homepage = repo.get("homepage")
    if homepage:
        try:
            parsed = urllib.parse.urlparse(homepage)
            if parsed.scheme in ("http", "https"):
                return html.escape(homepage, quote=True)
        except Exception:
            pass
    # Fallback
    name = repo["name"]
    return f"https://{org}.github.io/{html.escape(name, quote=True)}/latest/"


def make_permanent_link_line(repo: Dict[str, Any], org: str, is_ontology: bool) -> str:
    """Create the permanent-link line for an entry."""
    name = repo["name"]
    escaped_name = html.escape(name)
    escaped_org = html.escape(org)

    if is_ontology:
        return (
            f"Cite a version: "
            f"<code>https://w3id.org/{escaped_org}/{escaped_name}/&lt;version&gt;</code>"
        )
    else:
        pypi_name = html.escape(name.replace("_", "-"))
        return (
            f"Cite a version: "
            f"<code>https://{escaped_org}.github.io/{escaped_name}/v/&lt;version&gt;/</code>"
            f" &middot; "
            f"<code>pip install {pypi_name}==&lt;version&gt;</code>"
        )


def render_entry(repo: Dict[str, Any], org: str, is_ontology: bool) -> str:
    """Render a single repository entry as HTML."""
    name = repo["name"]
    escaped_name = html.escape(name)
    primary_link = make_primary_link(repo, org)
    description = repo.get("description")
    html_url = repo["html_url"]

    lines: List[str] = []
    lines.append(f'<div class="entry">')
    lines.append(f'  <h3><a href="{primary_link}">{escaped_name}</a></h3>')

    if description:
        escaped_desc = html.escape(description)
        lines.append(f'  <p class="description">{escaped_desc}</p>')

    perm_link = make_permanent_link_line(repo, org, is_ontology)
    lines.append(f'  <p class="perm-link">{perm_link}</p>')

    lines.append(
        f'  <p class="source">'
        f'<a href="{html.escape(html_url, quote=True)}">repository</a>'
        f"</p>"
    )
    lines.append(f"</div>")

    return "\n".join(lines)


def render_section(
    entries: List[Dict[str, Any]],
    org: str,
    section_title: str,
    section_intro: str,
    is_ontology: bool
) -> str:
    """Render a section (Tools or Ontologies) with its entries."""
    lines: List[str] = []
    lines.append(f"<h2>{section_title}</h2>")
    lines.append(f"<p>{section_intro}</p>")

    if entries:
        for repo in entries:
            lines.append(render_entry(repo, org, is_ontology))
    else:
        lines.append('<p class="empty">Nothing has registered here yet.</p>')

    return "\n".join(lines)


def render(
    tools: List[Dict[str, Any]],
    ontologies: List[Dict[str, Any]],
    org: str,
    banner: Optional[str]
) -> str:
    """Render the complete HTML page."""

    banner_html = ""
    if banner:
        escaped_banner = html.escape(banner)
        banner_html = f'<div class="banner">{escaped_banner}</div>\n'

    tools_section = render_section(
        tools, org,
        "Tools",
        "Libraries and services. Each link goes to the current documentation, which carries a version switcher for earlier releases.",
        is_ontology=False
    )

    ontologies_section = render_section(
        ontologies, org,
        "Ontologies",
        "Each link goes to the current version of that ontology. The overview of the whole suite is at <a href=\"https://w3id.org/circularfactory\">w3id.org/circularfactory</a>.",
        is_ontology=True
    )

    html_content = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Circular Factory</title>
<style>
:root {{
  --bg: #ffffff;
  --fg: #1a1a1a;
  --muted: #666666;
  --link: #0066cc;
  --border: #dddddd;
  --banner-bg: #fff3cd;
  --banner-border: #ffc107;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #1a1a1a;
    --fg: #f0f0f0;
    --muted: #aaaaaa;
    --link: #66b3ff;
    --border: #444444;
    --banner-bg: #4d3d00;
    --banner-border: #ffc107;
  }}
}}
* {{
  box-sizing: border-box;
}}
body {{
  margin: 0;
  padding: 2rem;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.6;
  max-width: 46rem;
  margin-left: auto;
  margin-right: auto;
}}
h1 {{
  margin-top: 0;
}}
h2 {{
  margin-top: 2rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.5rem;
}}
h3 {{
  margin: 0 0 0.25rem 0;
  font-size: 1.1rem;
}}
a {{
  color: var(--link);
  text-decoration: none;
}}
a:hover {{
  text-decoration: underline;
}}
.entry {{
  margin: 1.5rem 0;
}}
.description {{
  margin: 0.5rem 0;
}}
.perm-link, .source {{
  margin: 0.25rem 0;
  font-size: 0.9rem;
  color: var(--muted);
}}
code {{
  background: var(--border);
  padding: 0.1rem 0.3rem;
  border-radius: 0.2rem;
  font-size: 0.85rem;
}}
.empty {{
  color: var(--muted);
  font-style: italic;
}}
.banner {{
  background: var(--banner-bg);
  border-left: 4px solid var(--banner-border);
  padding: 1rem;
  margin: 0 0 1.5rem 0;
}}
footer {{
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  font-size: 0.9rem;
  color: var(--muted);
}}
</style>
</head>
<body>
{banner_html}<h1>Circular Factory</h1>
<p>Circular Factory publishes software tools and ontologies. Each one has its own documentation site, and this page links them. Every entry below is generated from that repository's own description, homepage and topics on GitHub. For the research project itself, see <a href="https://www.sfb1574.kit.edu/">sfb1574.kit.edu</a>.</p>
{tools_section}
{ontologies_section}
<footer>
<p>This page is generated from repository metadata in the circularfactory organisation on GitHub. A repository is listed here when it carries the topic cf-tool or cf-ontology. To change what an entry says, edit that repository's description and homepage.</p>
</footer>
</body>
</html>
'''

    return html_content


def main() -> int:
    """Main entry point."""
    args = parse_args()

    try:
        # Load repositories
        if args.repos_json:
            repos = load_repos_json(args.repos_json)
        else:
            repos = fetch_repos(args.org)

        # Parse --assume
        assume_map = parse_assume_specs(args.assume)

        # Select and classify
        tools, ontologies, warnings = select_and_classify(repos, args.org, assume_map)

        # Emit warnings to stderr
        for warning in warnings:
            print(warning, file=sys.stderr)

        # Refuse to publish a page that lists nothing. Every entry comes from a
        # topic on someone else's repository, so a permissions change, an API
        # hiccup or a mass un-tagging would otherwise silently replace the
        # site with an empty page.
        if not tools and not ontologies and not args.allow_empty:
            print(
                "Error: no repository carries cf-tool or cf-ontology, so the "
                "page would list nothing. Refusing to write it. Pass "
                "--allow-empty to override.",
                file=sys.stderr
            )
            return 1

        # Render
        html_content = render(tools, ontologies, args.org, args.banner)

        # Write output
        if args.out == "-":
            sys.stdout.write(html_content)
        else:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(html_content)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
