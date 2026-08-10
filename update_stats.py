import os
import re
import sys
import urllib.request
import json

USERNAME = os.environ.get("GH_USERNAME")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
SVG_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "stats.svg")


def api_request(url, token, graphql_query=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-stats-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if graphql_query is not None:
        req = urllib.request.Request(
            url,
            data=json.dumps({"query": graphql_query}).encode(),
            headers=headers,
            method="POST",
        )
    else:
        req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def fetch_repo_and_follower_counts(username, token):
    data = api_request(f"https://api.github.com/users/{username}", token)
    return data["public_repos"], data["followers"]


def fetch_total_contributions(username, token):
    if not token:
        # The contribution calendar is only exposed via GraphQL, which
        # requires an authenticated request even for public data.
        return None
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """.replace("$login: String!", "").replace("$login", f'"{username}"')
    data = api_request("https://api.github.com/graphql", token, graphql_query=query)
    try:
        return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    except (KeyError, TypeError):
        print("Warning: could not read contributions from GraphQL response:", data, file=sys.stderr)
        return None


def humanize(n):
    if n is None:
        return None
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def set_text(svg_text, node_id, value):
    if value is None:
        return svg_text
    pattern = re.compile(rf'(id="{node_id}"[^>]*>)([^<]*)(</text>)')
    new_text, count = pattern.subn(rf"\g<1>{value}\g<3>", svg_text)
    if count == 0:
        print(f"Warning: no node with id={node_id} found in stats.svg", file=sys.stderr)
    return new_text


def main():
    if not USERNAME:
        print("Set GH_USERNAME to your GitHub username.", file=sys.stderr)
        sys.exit(1)

    repos, followers = fetch_repo_and_follower_counts(USERNAME, TOKEN)
    contributions = fetch_total_contributions(USERNAME, TOKEN)

    with open(SVG_PATH, "r", encoding="utf-8") as f:
        svg = f.read()

    svg = set_text(svg, "stat-repos", humanize(repos))
    svg = set_text(svg, "stat-followers", humanize(followers))
    svg = set_text(svg, "stat-contribs", humanize(contributions))

    with open(SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"repos={repos} followers={followers} contributions={contributions}")


if __name__ == "__main__":
    main()
