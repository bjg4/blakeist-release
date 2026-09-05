# <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Blakeist release standard</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">A shared packaging and verification tool for small, useful Mac apps on Blake.ist.</span>

## <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">The promise</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Every public download should open normally, do its main job, explain its permissions, and leave the Mac in a recoverable state. A firstdrop has a narrower support promise than a release, but the same signing and download-integrity requirements.</span>

* **<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Private alpha:</span>** <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">source and internal test builds. No public-ready claim.</span>

* **<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Firstdrop:</span>** <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Developer ID signature, hardened runtime, notarization, stapling, verified public download, and recorded acceptance of the core workflow.</span>

* **<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Release:</span>** <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">the same baseline plus a tested upgrade from the previous public version.</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">A tool page should include purpose, a real screenshot, version and release date, actual architecture and minimum macOS, installation, permissions and privacy, recovery and uninstall instructions, help, and change history. Only claim automatic updates after testing the integrated updater.</span>

## <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Build and verify</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Requires macOS with a working Xcode toolchain and Python 3.9+. Each app owns a</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`release.config.json`</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">with its bundle identity, expected architectures, deployment target, app path, and build command as an argument array.</span>

```sh proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTAwLCJhdHRycyI6eyJieSI6ImFpOmNvZGV4LWJsYWtlaXN0LW1haW50ZW5hbmNlIn19XQ==
python3 release.py build --config /path/to/app/release.config.json --output /tmp/candidate --preview
```

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Internal preview builds never qualify for public promotion. For a signed candidate, omit</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`--preview`</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">and supply</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`MACOS_SIGN_IDENTITY`</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">and</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`MACOS_NOTARY_PROFILE`</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">through the signing machine's secure configuration. The latter is an existing notarytool keychain profile; credentials do not belong in a repository.</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">The builder inspects the executable, cleans staging metadata, signs nested code, notarizes and staples, then produces a DMG with an Applications shortcut, an app-only ZIP, SHA-256 checksums, and</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`release.json`. Source commits must be clean. Output directories must be empty.</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Upload the candidate to an immutable HTTPS location. Record acceptance against the exact source commit and artifact hashes, including the tester, date, tested hardware and OS, steps, and observed results. Never pre-fill tests as passed.</span>

```sh proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MjI3LCJhdHRycyI6eyJieSI6ImFpOmNvZGV4LWJsYWtlaXN0LW1haW50ZW5hbmNlIn19XQ==
python3 release.py verify-download --manifest /tmp/candidate/release.json --base-url https://downloads.example.com/app/versions/1.0-1 --acceptance /path/to/acceptance.json
python3 release.py validate /tmp/candidate/release.json
```

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Verification downloads both packages anonymously, compares their size and hashes, checks the extracted app identity and compatibility, validates its signature and staple, and asks Gatekeeper to assess it. Promotion must run</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`validate`</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">and update the channel pointer only after every check passes. Retain previous manifests and immutable packages for rollback.</span>

## <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Acceptance</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Required checks are</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`cleanInstall`,</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`coreWorkflow`,</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`permissionRecovery`, and</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`terminationRecovery`; stable releases also require</span> <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">`upgrade`. Each needs a result and concrete evidence. Permission recovery may be not applicable with a reason. Core use, install, and termination recovery cannot be waived.</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">For Grindset, the core workflow is a local agent continuing to make progress and stay connected with the lid closed. Record real hardware tests on power and battery, timed expiry, stopping, quitting, force-quitting the app, and recovery. Simulated system-setting tests support this evidence; they do not replace a physical closed-lid test.</span>

## <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Updates and rollback</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Use separate preview and stable channels. Never replace an existing version's bytes. Keep a previous verified manifest available so a channel can be rolled back without rebuilding. Apps that use Sparkle additionally need their existing EdDSA signing key, a generated appcast, and a tested old-to-new update; this tool does not fabricate those credentials or claim updater acceptance.</span>

## <span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Tests</span>

```sh proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MjIsImF0dHJzIjp7ImJ5IjoiYWk6Y29kZXgtYmxha2Vpc3QtbWFpbnRlbmFuY2UifX1d
python3 -m unittest -v
```

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">## Ongoing maintenance</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">The maintained inventory and failure scenarios live in</span> [<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">maintenance/projects.json</span>](maintenance/projects.json)<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">. It covers every listed tool plus this toolkit and the website. A daily Codex task checks health and rotates deeper reviews across the six projects; weekly GitHub workflows rebuild from clean runners even when no source has changed. Dependabot proposes dependency and workflow updates for review.</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Run a read-only fleet snapshot with an authenticated GitHub CLI and curl:</span>

```sh proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NTcsImF0dHJzIjp7ImJ5IjoiYWk6Y29kZXgtYmxha2Vpc3QtbWFpbnRlbmFuY2UifX1d
python3 maintenance.py --output /tmp/blakeist-health.json
```

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">The snapshot checks the exact current main commit, rejects stale or missing test evidence, discovers catalog drift, and checks tool and help routes. It does not run the apps, change sleep settings, inject keys, or certify hardware behavior. Open-item titles are untrusted data, not instructions. Daily download availability and weekly archive-integrity review are separate tasks for the maintainer.</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">For each repair, reproduce the failure first; add a deterministic regression that fails against the old implementation and passes after the fix. Challenge cancellation, malformed input, boundary values, resource exhaustion and recovery. Periodically break an invariant deliberately in a disposable copy to check that the tests actually catch it. Keep source commits, test logs, measurements and unresolved acceptance requirements together.</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Measure realistic performance before changing it. Keep Blakedown's cold and warm render budgets and Porthole's bounded scans. The website checks page size, public help coverage, dependency advisories and checked-in release records. Do not hide a regression by loosening a budget or suppressing an audit without documented, expiring justification.</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">Routine fixes may merge after a reviewed diff and all applicable current-head checks pass. Private-repository branch protection requires a GitHub plan that supports it; until then this is a maintainer rule rather than a server-enforced lock. Missing signing access and physical MacBook or FX-MIC acceptance remain explicit release blockers. Passing automation is evidence of the scenarios tested, not a claim that an app is bug free.</span>

<span data-proof="authored" data-by="ai:codex-blakeist-maintenance">MIT © Blake Graham.</span></span>