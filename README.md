# <span data-proof="authored" data-by="ai:unknown">Blakeist release standard</span>

<span data-proof="authored" data-by="ai:unknown">A shared packaging and verification tool for small, useful Mac apps on Blake.ist.</span>

## <span data-proof="authored" data-by="ai:unknown">The promise</span>

<span data-proof="authored" data-by="ai:unknown">Every public download should open normally, do its main job, explain its permissions, and leave the Mac in a recoverable state. A firstdrop has a narrower support promise than a release, but the same signing and download-integrity requirements.</span>

* **<span data-proof="authored" data-by="ai:unknown">Private alpha:</span>** <span data-proof="authored" data-by="ai:unknown">source and internal test builds. No public-ready claim.</span>

* **<span data-proof="authored" data-by="ai:unknown">Firstdrop:</span>** <span data-proof="authored" data-by="ai:unknown">Developer ID signature, hardened runtime, notarization, stapling, verified public download, and recorded acceptance of the core workflow.</span>

* **<span data-proof="authored" data-by="ai:unknown">Release:</span>** <span data-proof="authored" data-by="ai:unknown">the same baseline plus a tested upgrade from the previous public version.</span>

<span data-proof="authored" data-by="ai:unknown">A tool page should include purpose, a real screenshot, version and release date, actual architecture and minimum macOS, installation, permissions and privacy, recovery and uninstall instructions, help, and change history. Only claim automatic updates after testing the integrated updater.</span>

## <span data-proof="authored" data-by="ai:unknown">Build and verify</span>

<span data-proof="authored" data-by="ai:unknown">Requires macOS with a working Xcode toolchain and Python 3.9+. Each app owns a</span> <span data-proof="authored" data-by="ai:unknown">`release.config.json`</span> <span data-proof="authored" data-by="ai:unknown">with its bundle identity, expected architectures, deployment target, app path, and build command as an argument array.</span>

```sh proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTAwLCJhdHRycyI6eyJieSI6ImFpOnVua25vd24ifX1d
python3 release.py build --config /path/to/app/release.config.json --output /tmp/candidate --preview
```

<span data-proof="authored" data-by="ai:unknown">Internal preview builds never qualify for public promotion. For a signed candidate, omit</span> <span data-proof="authored" data-by="ai:unknown">`--preview`</span> <span data-proof="authored" data-by="ai:unknown">and supply</span> <span data-proof="authored" data-by="ai:unknown">`MACOS_SIGN_IDENTITY`</span> <span data-proof="authored" data-by="ai:unknown">and</span> <span data-proof="authored" data-by="ai:unknown">`MACOS_NOTARY_PROFILE`</span> <span data-proof="authored" data-by="ai:unknown">through the signing machine's secure configuration. The latter is an existing notarytool keychain profile; credentials do not belong in a repository.</span>

<span data-proof="authored" data-by="ai:unknown">The builder inspects the executable, cleans staging metadata, signs nested code, notarizes and staples, then produces a DMG with an Applications shortcut, an app-only ZIP, SHA-256 checksums, and</span> <span data-proof="authored" data-by="ai:unknown">`release.json`. Source commits must be clean. Output directories must be empty.</span>

<span data-proof="authored" data-by="ai:unknown">Upload the candidate to an immutable HTTPS location. Record acceptance against the exact source commit and artifact hashes, including the tester, date, tested hardware and OS, steps, and observed results. Never pre-fill tests as passed.</span>

```sh proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MjI3LCJhdHRycyI6eyJieSI6ImFpOnVua25vd24ifX1d
python3 release.py verify-download --manifest /tmp/candidate/release.json --base-url https://downloads.example.com/app/versions/1.0-1 --acceptance /path/to/acceptance.json
python3 release.py validate /tmp/candidate/release.json
```

<span data-proof="authored" data-by="ai:unknown">Verification downloads both packages anonymously, compares their size and hashes, checks the extracted app identity and compatibility, validates its signature and staple, and asks Gatekeeper to assess it. Promotion must run</span> <span data-proof="authored" data-by="ai:unknown">`validate`</span> <span data-proof="authored" data-by="ai:unknown">and update the channel pointer only after every check passes. Retain previous manifests and immutable packages for rollback.</span>

## <span data-proof="authored" data-by="ai:unknown">Acceptance</span>

<span data-proof="authored" data-by="ai:unknown">Required checks are</span> <span data-proof="authored" data-by="ai:unknown">`cleanInstall`,</span> <span data-proof="authored" data-by="ai:unknown">`coreWorkflow`,</span> <span data-proof="authored" data-by="ai:unknown">`permissionRecovery`, and</span> <span data-proof="authored" data-by="ai:unknown">`terminationRecovery`; stable releases also require</span> <span data-proof="authored" data-by="ai:unknown">`upgrade`. Each needs a result and concrete evidence. Permission recovery may be not applicable with a reason. Core use, install, and termination recovery cannot be waived.</span>

<span data-proof="authored" data-by="ai:unknown">For Grindset, the core workflow is a local agent continuing to make progress and stay connected with the lid closed. Record real hardware tests on power and battery, timed expiry, stopping, quitting, force-quitting the app, and recovery. Simulated system-setting tests support this evidence; they do not replace a physical closed-lid test.</span>

## <span data-proof="authored" data-by="ai:unknown">Updates and rollback</span>

<span data-proof="authored" data-by="ai:unknown">Use separate preview and stable channels. Never replace an existing version's bytes. Keep a previous verified manifest available so a channel can be rolled back without rebuilding. Apps that use Sparkle additionally need their existing EdDSA signing key, a generated appcast, and a tested old-to-new update; this tool does not fabricate those credentials or claim updater acceptance.</span>

## <span data-proof="authored" data-by="ai:unknown">Tests</span>

```sh proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MjIsImF0dHJzIjp7ImJ5IjoiYWk6dW5rbm93biJ9fV0=
python3 -m unittest -v
```

<span data-proof="authored" data-by="ai:unknown">MIT © Blake Graham.</span>