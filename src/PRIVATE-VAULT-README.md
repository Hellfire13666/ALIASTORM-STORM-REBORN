# ALIASTORM // Private Research Vault 🔐

Your live reports belong on your own computer, not in the public repository. The website shows artwork and an offline command preview only.

Optional initialization:

```bash
bash INIT-PRIVATE-VAULT.sh
```

This creates `$HOME/.local/share/aliastorm-storm-reborn-vault/{reports,notes,backups}` with private directory permissions. It never scans your computer, moves files, or uploads anything.

After you have personally reviewed your local reports, you can optionally **copy** the tool's current reports to that vault:

```bash
bash COPY-REPORTS-TO-VAULT.sh
```

The copier does not overwrite previously backed-up file names; it skips duplicates, and it does not delete the original files. The vault resides outside this repository by default. Protect your device/backups and avoid committing any real reports, credentials, or personal notes.
