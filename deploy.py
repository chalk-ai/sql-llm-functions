#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["chalkcompute==2.13.5"]
# ///
"""Deploy the LLM-functions-in-ChalkSQL demo as a ScalingGroup.

The replica runs ChalkSQL with its own workload identity (`chalk_identity=True`), so it carries
no client secret. The queries call OpenAI models through the Chalk model gateway, whose API key
comes from a Chalk secret:

    chalk router api-key create            # once; store the key as a secret
    chalk secrets set CHALK_ROUTER_API_KEY=<key>

Credentials for the deploy itself come from your existing `chalk login` (or the CHALK_* env vars):

    ./deploy.py [--env-id <environment>] [--name sql-llm-functions]
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_FILES = ["server.py", "queries.py", "data.py", "index.html"]


def configure_chalk(env_id: str | None) -> None:
    """Resolve deployment routing settings using the SDK's ambient login."""
    from chalkcompute import ConnectClient

    if env_id:
        os.environ["CHALK_ENVIRONMENT"] = env_id
    client = ConnectClient()
    try:
        client._ensure_auth()
        # Only routing settings are needed by the deployed app; credentials stay in the SDK.
        os.environ["CHALK_API_SERVER"] = client._api_server
        os.environ["CHALK_ENVIRONMENT_ID"] = client._env_id
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="sql-llm-functions")
    parser.add_argument(
        "--env-id", default=None, help="defaults to the environment in your existing `chalk login`"
    )
    parser.add_argument("--key-secret", default="CHALK_ROUTER_API_KEY")
    parser.add_argument("--ready-timeout", type=float, default=900.0)
    args = parser.parse_args()

    configure_chalk(args.env_id)
    from chalkcompute import Image, ReadinessProbe, ScalingGroup, Secret

    image = Image.debian_slim(python_version="3.12").pip_install(
        [
            "chalkcompute==2.13.5",
            "fastapi==0.116.1",
            "uvicorn[standard]==0.35.0",
            "pyarrow==21.0.0",
        ]
    )
    # The app files exceed the 32 KiB inline `copy` budget, so they ride a volume mounted at /app.
    for name in APP_FILES:
        image = image.add_local_file(
            str(HERE / name), f"/app/{name}", strategy="volume"
        )
    image = image.workdir("/app")

    sg = ScalingGroup(
        image=image,
        name=args.name,
        cpu="500m",
        memory="1Gi",
        env={
            # Not secrets: where ChalkSQL and the model gateway live.
            "CHALK_API_SERVER": os.environ["CHALK_API_SERVER"],
            "CHALK_ENVIRONMENT_ID": os.environ["CHALK_ENVIRONMENT_ID"],
            "PORT": "8080",
            "ROUTER_API_KEY": Secret.from_chalk_env(args.key_secret),
        },
        entrypoint=["python", "/app/server.py"],
        port=8080,
        readiness_probe=ReadinessProbe.http("/api/config"),
        chalk_identity=True,
        # The result cache and rate limits live in the replica's memory.
        min_replicas=1,
        max_replicas=1,
    )
    t0 = time.monotonic()
    try:
        sg.deploy(build_timeout=1200.0, ready_timeout=args.ready_timeout)
    finally:
        print(f"deploy returned after {time.monotonic() - t0:.0f}s")
    print("web_url:", sg.web_url)


if __name__ == "__main__":
    main()
