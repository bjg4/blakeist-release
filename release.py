#!/usr/bin/env python3
"""Build, inspect, package and verify a Blakeist macOS release (stdlib only)."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import urllib.request

STANDARD_VERSION = 1
REQUIRED_ACCEPTANCE = ("cleanInstall", "coreWorkflow", "permissionRecovery", "terminationRecovery")


def run(*args, cwd=None):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed ({result.returncode}): {(result.stderr or result.stdout).strip()}")
    return result.stdout.strip() or result.stderr.strip()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def validate_config(config):
    for field in ("id", "name", "bundleId", "appPath", "minimumSystemVersion", "architectures", "build"):
        if not config.get(field):
            raise ValueError(f"Missing {field}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", config["id"]):
        raise ValueError("Invalid product id")
    if not set(config["architectures"]) <= {"arm64", "x86_64"}:
        raise ValueError("Unsupported architecture")
    if not isinstance(config["build"], list) or not all(isinstance(s, str) for s in config["build"]):
        raise ValueError("build must be an argument array")
    return config


def public_errors(manifest):
    errors = []
    if manifest.get("standardVersion") != STANDARD_VERSION:
        errors.append("unsupported standardVersion")
    if manifest.get("channel") not in ("firstdrop", "release"):
        errors.append("public channel must be firstdrop or release")
    source = manifest.get("source", {})
    if not re.fullmatch(r"[a-f0-9]{40}", source.get("commit", "")) or source.get("dirty") is not False:
        errors.append("release must identify a clean source commit")
    checks = manifest.get("verification", {})
    for check in ("signature", "notarization", "gatekeeper", "roundTrip"):
        if checks.get(check) is not True:
            errors.append(f"{check} has not passed")
    acceptance = manifest.get("acceptance", {})
    if acceptance.get("commit") != source.get("commit"):
        errors.append("acceptance must refer to the release source commit")
    if not acceptance.get("testedBy") or not acceptance.get("testedAt") or not acceptance.get("configurations"):
        errors.append("acceptance needs tester, date, and tested configurations")
    for name in (*REQUIRED_ACCEPTANCE, *(("upgrade",) if manifest.get("channel") == "release" else ())):
        result = acceptance.get("checks", {}).get(name, {})
        if result.get("status") not in ("passed", "not-applicable") or not result.get("evidence"):
            errors.append(f"acceptance {name} needs a result and evidence")
        if name in ("cleanInstall", "coreWorkflow", "terminationRecovery") and result.get("status") == "not-applicable":
            errors.append(f"acceptance {name} cannot be waived")
    artifacts = manifest.get("artifacts", [])
    if not artifacts:
        errors.append("no release artifacts")
    for artifact in artifacts:
        if not re.fullmatch(r"[a-f0-9]{64}", artifact.get("sha256", "")) or artifact.get("bytes", 0) <= 0:
            errors.append("artifact needs SHA-256 and size")
        if not artifact.get("url", "").startswith("https://"):
            errors.append("artifact needs a public HTTPS URL")
    if {a.get("kind") for a in artifacts} != {"dmg", "zip"}:
        errors.append("release needs both a DMG and an app-only ZIP")
    if acceptance.get("artifactHashes") != {a.get("name"): a.get("sha256") for a in artifacts}:
        errors.append("acceptance must identify the exact artifact hashes")
    return errors


def inspect_app(app, config):
    plist = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    executable = app / "Contents/MacOS" / plist["CFBundleExecutable"]
    architectures = sorted(run("lipo", "-archs", str(executable)).split())
    if architectures != sorted(config["architectures"]):
        raise ValueError(f"Expected {config['architectures']}, executable contains {architectures}")
    if plist.get("CFBundleIdentifier") != config["bundleId"]:
        raise ValueError("Bundle identity differs from release configuration")
    if plist.get("LSMinimumSystemVersion") != config["minimumSystemVersion"]:
        raise ValueError("Minimum OS differs from release configuration")
    icon = plist.get("CFBundleIconFile")
    if not icon or not (app / "Contents/Resources" / (icon if icon.endswith(".icns") else icon + ".icns")).is_file():
        raise ValueError("Release app needs a bundled icon")
    # Inspect every Mach-O slice, not only Info.plist's compatibility claim.
    versions = re.findall(r"minos\s+([0-9.]+)", run("otool", "-l", str(executable)))
    def os_version(value):
        parts = tuple(map(int, value.split(".")))
        return parts + (0,) * (3 - len(parts))
    expected = os_version(config["minimumSystemVersion"])
    if not versions:
        raise ValueError("Cannot determine executable deployment targets")
    for version in versions:
        actual = os_version(version)
        if actual > expected:
            raise ValueError(f"Executable requires macOS {version}, above advertised minimum")
    return {"version": plist["CFBundleShortVersionString"], "build": plist["CFBundleVersion"],
            "bundleId": plist["CFBundleIdentifier"], "architectures": architectures,
            "minimumSystemVersion": plist["LSMinimumSystemVersion"]}


def sign_app(app, identity, entitlements):
    # Clean staging metadata before signing. Preserve framework symlinks.
    run("xattr", "-cr", str(app))
    for item in app.rglob("._*"):
        if item.is_file():
            item.unlink()
    nested = []
    for item in app.rglob("*"):
        if item.is_symlink():
            continue
        if item.is_dir() and item.suffix in (".framework", ".app", ".xpc", ".bundle"):
            nested.append(item)
        elif item.is_file() and "Mach-O" in run("file", "-b", str(item)):
            nested.append(item)
    for item in sorted(nested, key=lambda p: len(p.parts), reverse=True):
        run("codesign", "--force", "--options", "runtime", "--timestamp", "--sign", identity, str(item))
    args = ["codesign", "--force", "--options", "runtime", "--timestamp", "--sign", identity]
    if entitlements:
        args += ["--entitlements", str(entitlements)]
    run(*args, str(app))
    run("codesign", "--verify", "--deep", "--strict", str(app))


def notarize(path, profile):
    response = json.loads(run("xcrun", "notarytool", "submit", str(path), "--keychain-profile", profile,
                              "--wait", "--output-format", "json"))
    if response.get("status") != "Accepted":
        raise RuntimeError(f"Notarization did not pass: {response.get('status')}")


def build_release(args):
    config_path = Path(args.config).resolve()
    root = config_path.parent
    config = validate_config(read_json(config_path))
    source = {"repository": run("git", "config", "--get", "remote.origin.url", cwd=root),
              "commit": run("git", "rev-parse", "HEAD", cwd=root),
              "dirty": bool(run("git", "status", "--porcelain", "--untracked-files=normal", cwd=root))}
    if not args.preview and source["dirty"]:
        raise ValueError("Commit the release source before packaging a public candidate")
    run(*config["build"], cwd=root)
    built_app = root / config["appPath"]
    metadata = inspect_app(built_app, config)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Output directory must be empty; release artifacts are immutable")
    verification = {key: False for key in ("signature", "notarization", "gatekeeper", "roundTrip")}
    with tempfile.TemporaryDirectory(prefix="blakeist-package-") as temp:
        stage = Path(temp)
        app = stage / built_app.name
        run("ditto", "--norsrc", "--noextattr", str(built_app), str(app))
        if not args.preview:
            identity = os.environ.get("MACOS_SIGN_IDENTITY")
            profile = os.environ.get("MACOS_NOTARY_PROFILE")
            if not identity or not profile:
                raise ValueError("MACOS_SIGN_IDENTITY and MACOS_NOTARY_PROFILE are required")
            entitlements = root / config["entitlements"] if config.get("entitlements") else None
            sign_app(app, identity, entitlements)
            verification["signature"] = True
            notarization_zip = stage / "notarization.zip"
            run("ditto", "-c", "-k", "--keepParent", str(app), str(notarization_zip))
            notarize(notarization_zip, profile)
            run("xcrun", "stapler", "staple", str(app))
            run("xcrun", "stapler", "validate", str(app))
            run("spctl", "--assess", "--type", "execute", "--verbose=2", str(app))
            verification["notarization"] = verification["gatekeeper"] = True
        zip_path = output / f"{config['id']}-{metadata['version']}.zip"
        dmg_path = output / f"{config['id']}-{metadata['version']}.dmg"
        run("ditto", "-c", "-k", "--keepParent", str(app), str(zip_path))
        dmg_root = stage / "disk-image"
        dmg_root.mkdir()
        run("ditto", str(app), str(dmg_root / app.name))
        (dmg_root / "Applications").symlink_to("/Applications")
        run("hdiutil", "create", "-volname", config["name"], "-srcfolder", str(dmg_root),
            "-format", "UDZO", str(dmg_path))
        if not args.preview:
            run("codesign", "--timestamp", "--sign", identity, str(dmg_path))
            notarize(dmg_path, profile)
            run("xcrun", "stapler", "staple", str(dmg_path))
            run("xcrun", "stapler", "validate", str(dmg_path))
    manifest = {"standardVersion": STANDARD_VERSION, "id": config["id"], "name": config["name"],
                "channel": "private-alpha" if args.preview else args.channel, **metadata, "source": source,
                "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(), "verification": verification,
                "acceptance": read_json(args.acceptance) if args.acceptance else {},
                "artifacts": [{"name": path.name, "kind": path.suffix[1:], "bytes": path.stat().st_size,
                               "sha256": sha256(path), "url": ""} for path in (dmg_path, zip_path)]}
    write_json(output / "release.json", manifest)
    (output / "SHA256SUMS.txt").write_text("".join(f"{a['sha256']}  {a['name']}\n" for a in manifest["artifacts"]))
    print(json.dumps({"output": str(output), "publicReady": False, "next": "Upload candidates, then verify-download before promotion"}))


def verify_download(args):
    manifest = read_json(args.manifest)
    if args.acceptance:
        manifest["acceptance"] = read_json(args.acceptance)
    base = args.base_url.rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("An HTTPS artifact base URL is required")
    with tempfile.TemporaryDirectory(prefix="blakeist-download-") as temp:
        root = Path(temp)
        for artifact in manifest["artifacts"]:
            if Path(artifact["name"]).name != artifact["name"]:
                raise ValueError("Unsafe artifact filename")
            artifact["url"] = f"{base}/{artifact['name']}"
            downloaded = root / artifact["name"]
            with urllib.request.urlopen(artifact["url"], timeout=120) as response, downloaded.open("wb") as stream:
                if not response.url.startswith("https://"):
                    raise ValueError("Download redirected away from HTTPS")
                shutil.copyfileobj(response, stream)
            if sha256(downloaded) != artifact["sha256"] or downloaded.stat().st_size != artifact["bytes"]:
                raise ValueError("Published artifact differs from the inspected candidate")
            mount = root / artifact["kind"]
            if artifact["kind"] == "dmg":
                run("hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mount), str(downloaded))
            else:
                run("ditto", "-x", "-k", str(downloaded), str(mount))
            try:
                apps = list(mount.glob("*.app"))
                if len(apps) != 1:
                    raise ValueError("Expected exactly one app in the release package")
                app = apps[0]
                actual = inspect_app(app, manifest)
                for field in ("version", "build", "bundleId", "minimumSystemVersion", "architectures"):
                    if actual[field] != manifest[field]:
                        raise ValueError(f"Downloaded app differs: {field}")
                run("codesign", "--verify", "--deep", "--strict", str(app))
                run("xcrun", "stapler", "validate", str(app))
                run("spctl", "--assess", "--type", "execute", "--verbose=2", str(app))
            finally:
                if artifact["kind"] == "dmg":
                    run("hdiutil", "detach", str(mount))
    manifest["verification"] = {key: True for key in ("signature", "notarization", "gatekeeper", "roundTrip")}
    errors = public_errors(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    write_json(args.manifest, manifest)
    print("Release qualifies for public promotion.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--config", default="release.config.json")
    build.add_argument("--output", required=True)
    build.add_argument("--preview", action="store_true", help="Unsigned local/CI artifact, never publicly eligible")
    build.add_argument("--channel", choices=("firstdrop", "release"), default="firstdrop")
    build.add_argument("--acceptance")
    build.set_defaults(func=build_release)
    verify = commands.add_parser("verify-download")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--base-url", required=True)
    verify.add_argument("--acceptance")
    verify.set_defaults(func=verify_download)
    validate = commands.add_parser("validate")
    validate.add_argument("manifest")
    def validate_manifest(args):
        errors = public_errors(read_json(args.manifest))
        if errors:
            raise ValueError("; ".join(errors))
        print("Release qualifies for public promotion.")
    validate.set_defaults(func=validate_manifest)
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"Release blocked: {error}\n")


if __name__ == "__main__":
    main()
