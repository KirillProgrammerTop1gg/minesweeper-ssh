from __future__ import annotations

import hashlib
import os
from pathlib import Path


def get_client_fingerprint() -> tuple[str, str]:
    override_tag = os.environ.get("MINESWEEPER_TAG")
    if override_tag:
        return "override", override_tag.strip()

    ssh_client = os.environ.get("SSH_CLIENT", "")
    if ssh_client:
        client_ip = ssh_client.split()[0]
    else:
        client_ip = os.environ.get("REMOTE_ADDR", "")

    if not client_ip or client_ip in ("127.0.0.1", "localhost", "::1"):
        try:
            mid = Path("/etc/machine-id").read_text().strip()
        except Exception:
            mid = os.environ.get("USER", "local")
        raw = f"local:{mid}"
        client_ip = "127.0.0.1"
    else:
        raw = f"ip:{client_ip}"

    tag_hex = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:4].upper()
    tag = f"#{tag_hex}"

    return client_ip, tag
