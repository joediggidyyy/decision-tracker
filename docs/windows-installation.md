# Windows installation

[Home](../README.md) · [Packaging](packaging.md) · [Operations](operations.md)

## Before installing

This unsigned alpha targets **Windows 11 x64**, under your own Windows account. Other operating systems and processor types are not qualified. The package includes Python 3.14.8 and runtime dependencies. Installation and normal launch need no separate Python, pip or terminal setup, and installation does not download dependencies.

Use the named GitHub prerelease assets when published. Compare the downloaded EXE with `SHA256SUMS.txt`; hashes detect changed bytes and do not establish publisher identity. In PowerShell, `Get-FileHash .\DecisionTracker-0.1.0a1-windows-x64-setup.exe -Algorithm SHA256` displays the hash. Do not use files from an unexpected source.

The installer is unsigned. Windows may show an unknown-publisher or SmartScreen warning. If your device policy prevents installation, retain the message and ask the device administrator; do not disable protection. Broader distribution and signing remain separate from this limited test release.

## Install and launch

1. Run Setup as your ordinary Windows user. Choose a local, nonsynchronized application folder.
2. Use the Start menu entry. Setup offers an optional desktop shortcut and a Launch checkbox at completion.
3. On first launch, click OK to copy a temporary setup code and open the browser. Paste the code into the setup form and choose your private password. Cancel leaves setup unfinished. The code expires after 15 minutes.
4. Sign in. Create a project or save a reusable decision in Library. A fresh deployment contains no projects, saved decisions, groups or organization seeds.

Keep codes, passwords and tokens private. The helper puts the code on the clipboard only after your explicit OK; it does not print it or include it in a URL. Existing users go directly to the browser sign-in flow. Password recovery remains an owner-only private CLI operation.

Application files default to `%LOCALAPPDATA%\Programs\DecisionTracker`. User data defaults to `%LOCALAPPDATA%\DecisionTracker`: deployment configuration and credentials in `deployment`, project/catalog/Library storage in `data`. These locations are independent. Do not move credentials between Windows accounts or place active storage in OneDrive. Setup installs no startup task, PATH change or automatic updater.

The installed owner command is `%LOCALAPPDATA%\Programs\DecisionTracker\decision-tracker.cmd`. Agent access and optional URI registration use the existing supported CLI; see [Operations](operations.md). A separate custom deployment requires explicit `--deployment FILE` when using the CLI.

## Update, repair and uninstall

Keep checked project, catalog and Library backups. Run the matching Setup to repair application files. Setup stops an owned service through its supported owner channel; it refuses to force-stop busy drafts. Close drafts and retry. It preserves deployment identity, credentials, project identities and Library. Installing application files does not authorize a database migration or downgrade.

Before repair or reinstall, confirm that the selected Setup contains a runtime capable of reading the live history. The previously qualified Setup predates `deprecation_approval_v1`; it is not qualified as recovery media after new deprecation approval writes. Keep the capable qualified environment and checked backups until matching Setup is built and qualified. SQL schema and package version alone do not establish compatibility. See [Packaging](packaging.md#upgrade-and-recovery).

Uninstall through Windows Installed apps. It removes owned application files and shortcuts, and removes an optional URI handler only when its recorded ownership still matches. It retains user data and the ownership receipt. Reinstall restores the owned application binding and retains that data. No delete-user-data option is provided.

| Symptom | Safe action and verification |
|---|---|
| Setup cannot stop safely | Close unsaved drafts and other active work. Retry Setup. Verify that the existing project and Library are still available afterward. Do not force-kill the service. |
| Application file is missing or changed | Use Setup qualified for the live history and installed binding. It verifies the installed inventory before activation. Launch and check the version and existing content. |
| Incomplete Setup or launch reports `INSTALLATION_MAINTENANCE` | Use Setup qualified for the live history and installed binding to finish or repair. Do not remove the marker manually. Verify launch and retained content after repair. |
| Existing manual Python deployment or changed binding | Setup preserves it and refuses adoption. Keep the existing environment and data. Use a separate explicitly configured deployment, or arrange a reviewed migration. |
| Missing credentials or damaged deployment information | Preserve all files. Record the nonsecret fault and use the support route. Do not initialize replacement credentials or delete state to make Setup pass. |
| Interrupted first installation left partial setup files | Preserve the partial deployment and installer log for review. A new unrelated deployment may be configured separately; partial state is not automatically discarded or adopted. |
| Missing runtime prevents uninstall | Reinstall matching application files first, then retry uninstall. User data remains separate. |
| Clipboard is busy | Close the competing clipboard action and launch again. Request a fresh setup code; do not ask an agent to read it. |
| Port occupied or service identity mismatch | Keep the deployment and fault code. Follow existing service diagnostics and verify the configured listener. Do not repoint to an unknown service. |

For unresolved faults, retain version, installer hash, nonsecret error and Setup log. Do not include private records or credentials in a public issue. Follow [Security](../SECURITY.md) for private security reports.

## Test status

The current source includes deprecation approval. Native focused/integration evidence qualifies its source, wheel and source archive. Compiled-Setup qualification below belongs to an earlier source snapshot and has not been repeated for this update. No current Setup release is claimed. Select archives by retained source manifest/hash and runtime capabilities, rather than the shared `0.1.0a1` label. The health endpoint still reports the older `0.1.0.dev0` string; use authenticated schema discovery and source/asset correspondence for capability checks.

Native compiled-Setup qualification exercises silent installation, managed service reuse/stop, repair, retained data and reinstall in disposable local folders. These checks do not prove interactive wizard acceptance, installation on a second machine, code signing or production readiness. See [Verification](verification.md) for actual evidence.
