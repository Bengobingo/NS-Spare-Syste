"""Configure a local administrator without storing credentials in Git."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
import tempfile

from werkzeug.security import generate_password_hash


def main(rotate_session_key=False):
    username = input("Administrator username: ").strip()
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if not username or not password:
        raise SystemExit("Username and password are required.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    destination = Path(__file__).resolve().parent / "local_settings.json"
    settings = {}
    if destination.exists():
        settings = json.loads(destination.read_text(encoding="utf-8"))
    if rotate_session_key or not settings.get("secret_key"):
        settings["secret_key"] = secrets.token_hex(32)
    settings.setdefault("admin_users", {})[username] = generate_password_hash(password)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent,
        prefix="local_settings.json.", suffix=".tmp", delete=False,
    ) as temporary:
        temporary.write(json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
        temporary_path = Path(temporary.name)
    try:
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    print("Local administrator configured.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rotate-session-key", action="store_true",
        help="Replace the session key and invalidate existing sessions.",
    )
    main(rotate_session_key=parser.parse_args().rotate_session_key)
