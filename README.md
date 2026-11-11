# 🌈 ALIASTORM // STORM REBORN

**GlitchByte Phantom Labs** | Rainbow terminal • public username-page research • local-first reports

![Storm Reborn artwork](docs/assets/storm-enchanted.webp)

### What this is

A distinct GlitchByte implementation of a public username research workflow. It uses an attributed, MIT-licensed upstream public URL catalog. The tool checks up to 154 unique public-source patterns, labels uncertain evidence conservatively, and saves results locally. No results or private information are part of the public site.

### 🚀 Publish your own GitHub repo

Create a new **empty public** repository named `ALIASTORM-STORM-REBORN` under `Hellfire13666` at <https://github.com/new>. Leave the GitHub auto-README/license options **unchecked**. From the extracted release folder, run `bash PUBLISH-TO-GITHUB.sh`. The script asks for confirmation and stages only allowlisted public files, with commit author set locally to `Hellfire13666`. Then enable **Settings → Pages → main → /docs**. See [Publication checklist](PUBLICATION-CHECKLIST.md).

This does not use or modify `AliaStorm-Favorite`, your installed tool, or private reports.

### 🌈 Showcase

This repository's GitHub Pages site is in `docs/`. It includes our original art gallery and an **offline, non-scanning command preview**. Once GitHub Pages is enabled from `main` → `/docs`, the intended site address is:

`https://hellfire13666.github.io/ALIASTORM-STORM-REBORN/`

That URL **will not work until the repository is created and Pages has been enabled**.

### Terminal launch

Use Python 3. Extract/download this repository and run inside the project folder:

```bash
bash RUN-ALIASTORM.sh --color always
```

From the interactive menu: [1] USERNAME STORM, [2] SITE INTEL EXTRA, and [4] HTML RESULTS VIEWER. The tool prints results in your terminal; a browser opens only if you explicitly choose a saved HTML report.

Direct scan:

```bash
python3 aliastorm.py ExampleName --color always
```

Run included offline tests:

```bash
python3 -m unittest discover -s tests -q
```

### 🔐 Private vault

Real results stay in `local-reports/`, ignored by Git. You can use the optional **separate** private archive helper:

```bash
bash INIT-PRIVATE-VAULT.sh
bash COPY-REPORTS-TO-VAULT.sh
```

The scripts only initialize directories and optionally copy current reports; no uploads, deletions, or changes to earlier tool installations. Read [`PRIVATE-VAULT-README.md`](PRIVATE-VAULT-README.md).

### 💜 Credits

Special thanks to **AnonCatalyst** for the inspiration and the original site URL catalog. Its full MIT copyright/license notice is retained as [`LICENSE-ORIGINAL-ALIASTORM.txt`](LICENSE-ORIGINAL-ALIASTORM.txt). See [`ATTRIBUTION.md`](ATTRIBUTION.md). The GlitchByte interface and artwork are separate. This is not an official continuation or endorsement of any other creator's project.

### Evidence and responsible use

A username match, HTTP success status, or public mention does not establish identity or ownership. Honor website access limits, review sources carefully, and keep identifiable/private research out of public GitHub commits.

The repository is a prepared project bundle; its presence here does **not** mean any GitHub repository or site has been published yet.
