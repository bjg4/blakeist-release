#!/usr/bin/env python3
"""Upload immutable candidates or promote a verified manifest in Cloudflare R2.

Requires boto3. Credentials use the standard AWS environment variables and
R2_ENDPOINT_URL. Uploading does not promote a candidate to a public channel.
"""
import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re

from release import public_errors, read_json, sha256


def immutable_put(client, bucket, key, data, content_type):
    """A retry may reuse identical bytes, but never replace an existing release."""
    try:
        client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type,
                          CacheControl="public, max-age=31536000, immutable", IfNoneMatch="*")
    except Exception as error:
        code = getattr(error, "response", {}).get("Error", {}).get("Code")
        if code not in ("PreconditionFailed", "412"):
            raise
        previous = client.get_object(Bucket=bucket, Key=key)["Body"].read()
        if hashlib.sha256(previous).digest() != hashlib.sha256(data).digest():
            raise ValueError(f"Refusing to replace immutable object {key}") from error


def candidate_prefix(manifest):
    components = [manifest["id"], manifest["version"], manifest["build"]]
    if not all(isinstance(s, str) and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", s) for s in components):
        raise ValueError("Unsafe product, version, or build name")
    return f"{components[0]}/versions/{components[1]}-{components[2]}"


def upload(client, bucket, path):
    manifest = read_json(path)
    if manifest.get("channel") not in ("firstdrop", "release"):
        raise ValueError("Internal test builds cannot be uploaded for public distribution")
    if not all(manifest.get("verification", {}).get(k) is True for k in ("signature", "notarization", "gatekeeper")):
        raise ValueError("Sign and notarize before uploading a public candidate")
    prefix = candidate_prefix(manifest)
    for artifact in manifest["artifacts"]:
        name = artifact["name"]
        if Path(name).name != name:
            raise ValueError("Unsafe artifact filename")
        local = Path(path).parent / name
        if sha256(local) != artifact["sha256"] or local.stat().st_size != artifact["bytes"]:
            raise ValueError("Local artifact changed after packaging")
        immutable_put(client, bucket, f"{prefix}/{name}", local.read_bytes(),
                      mimetypes.guess_type(name)[0] or "application/octet-stream")
    checksums = "".join(f"{a['sha256']}  {a['name']}\n" for a in manifest["artifacts"])
    immutable_put(client, bucket, f"{prefix}/SHA256SUMS.txt", checksums.encode(), "text/plain")
    print(f"Candidate uploaded at {prefix}. Run verify-download before promotion.")


def promote(client, bucket, path, expected_etag):
    manifest = read_json(path)
    errors = public_errors(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    prefix = candidate_prefix(manifest)
    for artifact in manifest["artifacts"]:
        remote = client.get_object(Bucket=bucket, Key=f"{prefix}/{artifact['name']}")["Body"].read()
        if len(remote) != artifact["bytes"] or hashlib.sha256(remote).hexdigest() != artifact["sha256"]:
            raise ValueError("Stored artifact differs from verified download")
    data = (json.dumps(manifest, indent=2) + "\n").encode()
    immutable_put(client, bucket, f"{prefix}/release.json", data, "application/json")
    # One pointer is the transaction boundary. ETag comparison prevents concurrent
    # releases (or a rollback) from silently overwriting one another.
    condition = {"IfNoneMatch": "*"} if expected_etag == "new" else {"IfMatch": expected_etag}
    result = client.put_object(Bucket=bucket, Key=f"{manifest['id']}/{manifest['channel']}/release.json",
                              Body=data, ContentType="application/json", CacheControl="no-cache", **condition)
    print(json.dumps({"channel": manifest["channel"], "etag": result.get("ETag"), "version": manifest["version"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("upload", "promote"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--expected-etag", help="Current channel ETag, or 'new' for its first publication")
    args = parser.parse_args()
    if args.command == "promote" and not args.expected_etag:
        parser.error("Promotion requires --expected-etag; use a previous verified manifest to roll back")
    import boto3
    client = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT_URL"], region_name="auto")
    if args.command == "upload":
        upload(client, args.bucket, args.manifest)
    else:
        promote(client, args.bucket, args.manifest, args.expected_etag)


if __name__ == "__main__":
    main()
