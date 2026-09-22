"""Verified HTTPS with bundled roots, including on standalone macOS builds."""
import json
import ssl
import urllib.request

import certifi


def tls_context():
    # Keep OS/custom roots where available and add a relocatable public CA bundle.
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


def fetch_latest_release(repository, version):
    request = urllib.request.Request(
        f'https://api.github.com/repos/{repository}/releases/latest',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'AsterPDF/' + version})
    with urllib.request.urlopen(request, timeout=15, context=tls_context()) as response:
        return json.loads(response.read(2_000_000))
