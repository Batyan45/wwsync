# wwsync

A simple, interactive wrapper around `rsync` designed for developers who code locally but run on a remote server. It manages configurations automatically and prevents accidental data loss on the server.

## Features

- **Zero-Config Start:** Just run `wwsync <server> -s` in your project folder. It will ask for details once and remember them.
- **Multiple Servers:** Support for distinct configurations (e.g., `production`, `staging`, `dev-server`).
- **Safe Mode (`-s` / `--safe`):** Standard execution uploads files but **never deletes** anything on the server (preserving logs, build artifacts, etc.).
- **Interactive Full Sync (`-f` / `--full`):** The `-f` flag mirrors the local directory. It performs a "dry run" first, shows you exactly which files will be deleted, and asks for confirmation.
- **Sync All (`-a` / `--all`):** Syncs all mappings across all servers in one command. Requires `--safe` or `--full`. Asks for confirmation before each mapping.
- **Auto Accept (`--auto_accept`):** Skips all confirmations in `--full` and `--all` modes.
- **Remote Run (`-r`):** Automatically SSH into the server, cd to the project folder, and optionally execute a startup command (e.g. `conda activate`).
- **Exclusions:** Easy management of ignored files (`node_modules`, `.git`, `.env`).

## Installation

1. Download the script:
```bash
curl -o wwsync -L https://github.com/Batyan45/wwsync/releases/latest/download/wwsync
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
wwsync my-server -s
```

* If this is your first time, it will ask for the `user@ip` and the `remote path`.
* It will sync changes to the server.
* **It will NOT delete files on the server** that are missing locally.

### 2. Full Sync (Mirroring)

If you renamed files or cleaned up your local folder and want the server to match exactly:

```bash
wwsync my-server -f
```

* It calculates differences.
* It displays a list of files to be deleted (e.g., `deleting logs/old.log`).
* It asks for `y/n` confirmation before deleting anything.

### 3. Remote Run

To jump into the remote server directory (and optionally run a command):

```bash
wwsync my-server -r
```

* Connects via SSH and `cd`s to the configured remote path.
* If a `run_command` is configured (e.g. `source .env`), it executes it first.
* Leaves you in an interactive shell.

**Combine with sync:**
```bash
wwsync my-server -s -r
```

### 4. Sync All Mappings

To sync all configured mappings across all servers:

```bash
# Safe sync all
wwsync -a -s

# Full sync all (with confirmations)
wwsync -a -f

# Full sync all without confirmations
wwsync -a -f --auto_accept
```
1. Syncs files (Safe mode).
2. Starts remote session.

## Configuration

The configuration is stored in `~/.wwsync` in JSON format. You can edit it manually if needed.

**Example structure:**

```json
{
    "servers": {
        "production": {
            "host": "root@192.168.1.50",
            "shell": "zsh",
            "mappings": [
                {
                    "local": "/Users/dev/my-project",
                    "remote": "/var/www/html/api",
                    "excludes": [".git", "node_modules", ".env"],
                    "run_command": "source .env; conda activate myenv"
                }
            ]
        }
    }
}
```

## Requirements

* Python 3+
* `rsync` installed on both local machine and remote server.
* SSH access to the remote server.