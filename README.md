# wwsync

A simple, interactive wrapper around `rsync` designed for developers who code locally but run on a remote server. It manages configurations automatically and prevents accidental data loss on the server.

## Features

- **Zero-Config Start:** Just run `wwsync <server>` in your project folder. It will ask for details once and remember them.
- **Multiple Servers:** Support for distinct configurations (e.g., `production`, `staging`, `dev-server`).
- **Safe Mode by Default:** Standard execution uploads files but **never deletes** anything on the server (preserving logs, build artifacts, etc.).
- **Interactive Full Sync:** The `--full` flag mirrors the local directory. It performs a "dry run" first, shows you exactly which files will be deleted, and asks for confirmation.
- **Exclusions:** Easy management of ignored files (`node_modules`, `.git`, `.env`).

## Installation

1. Download the script:
```bash
curl -o wwsync https://raw.githubusercontent.com/Batyan45/wwsync/refs/heads/main/wwsync
# OR just copy the python code into a file named 'wwsync'
```

2. Make it executable:
```bash
chmod +x wwsync
```


3. Move it to your path:
```bash
sudo mv wwsync /usr/local/bin/
```



## Usage

### 1. Basic Sync (Safe Mode)

Run this command inside your project folder:

```bash
wwsync my-server
```

* If this is your first time, it will ask for the `user@ip` and the `remote path`.
* It will sync changes to the server.
* **It will NOT delete files on the server** that are missing locally.

### 2. Full Sync (Mirroring)

If you renamed files or cleaned up your local folder and want the server to match exactly:

```bash
wwsync my-server --full
```

* It calculates differences.
* It displays a list of files to be deleted (e.g., `deleting logs/old.log`).
* It asks for `y/n` confirmation before deleting anything.

## Configuration

The configuration is stored in `~/.wwsync` in JSON format. You can edit it manually if needed.

**Example structure:**

```json
{
    "servers": {
        "production": {
            "host": "root@192.168.1.50",
            "mappings": [
                {
                    "local": "/Users/dev/my-project",
                    "remote": "/var/www/html/api",
                    "excludes": [".git", "node_modules", ".env"]
                }
            ]
        }
    }
}
```

## Requirements

* Python 3+
* `rsync` installed on both local machine and remote server.