# Shell Scripting — Homework

## Task: System Information Script

**Script:** [`system_info.sh`](system_info.sh)

A Bash script that reports the current date, hostname, username, disk usage and
running processes, then asks the user where to save a report, creates that
directory and file, and writes the process list into it using output
redirection.

### Requirements checklist

| # | Requirement | How it is met | Line |
|---|---|---|---|
| 1 | Prints the current date | `CURRENT_DATE=$(date)` then echoed | 17, 21 |
| 2 | Prints the hostname | `HOST_NAME=$(hostname)` then echoed | 18, 22 |
| 3 | Prints the username | `USER_NAME=$(whoami)` then echoed | 19, 23 |
| 4 | Prints the disk usage | `df -h` | 29 |
| 5 | Prints the running processes | `ps aux --sort=-%cpu` | 35 |
| 6 | Uses variables | 6 variables: `CURRENT_DATE`, `HOST_NAME`, `USER_NAME`, `DIR_NAME`, `FILE_NAME`, `REPORT_FILE` | throughout |
| 7 | Takes user input with `read -p` | two prompts for directory and file name | 39, 40 |
| 8 | Creates a directory with `mkdir` | `mkdir -p "$DIR_NAME"` | 49 |
| 9 | Creates a file with `touch` | `touch "$REPORT_FILE"` | 52 |
| 10 | Stores processes in the file with `>` | `echo ... > "$REPORT_FILE"` then `ps aux >> ...` | 57, 66 |

### Commands used

`mkdir` · `touch` · `echo` · `df` · `ps` · `read -p` · variables · `>` and `>>` redirection
· plus `date`, `whoami`, `hostname`, `du`, `head`, `cut`

### How to run

```bash
chmod +x system_info.sh
./system_info.sh
```

---

## Output

### Run 1 — entering custom values

The two `read -p` prompts were answered with `devops_report` and `process_list`.

```console
$ ./system_info.sh
===============================================
           SYSTEM INFORMATION SCRIPT           
===============================================

1. Current Date : Thu Sep  3 16:40:53 UTC 2026
2. Hostname     : c071b53e37c7
3. Username     : root

4. Disk Usage (df -h)
-----------------------------------------------
Filesystem      Size  Used Avail Use% Mounted on
overlay         453G   63G  367G  15% /
tmpfs            64M     0   64M   0% /dev
shm              64M     0   64M   0% /dev/shm
/dev/vda1       453G   63G  367G  15% /etc/hosts
tmpfs           3.0G   28K  3.0G   1% /run
tmpfs           5.0M     0  5.0M   0% /run/lock

5. Running Processes (top 10 by CPU)
-----------------------------------------------
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root           1  0.0  0.0 165204  9696 ?        Ss   16:34   0:00 /sbin/init
root          26  0.0  0.0  31624 10828 ?        S<s  16:34   0:00 /lib/systemd/systemd-journald
systemd+      36  0.0  0.0  22264  9012 ?        Ss   16:34   0:00 /lib/systemd/systemd-resolved
root         736  0.0  0.0  55068  2248 ?        Ss   16:36   0:00 nginx: master process /usr/sbin/nginx -g daemon on; master_process on;
www-data     737  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     738  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     740  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     741  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     742  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     743  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process

Enter a name for the report directory: devops_report
Enter a name for the report file (without .txt): process_list
Created directory : devops_report
Created file      : devops_report/process_list.txt

Running processes saved to: devops_report/process_list.txt
File size: 4.0K

----- First 15 lines of devops_report/process_list.txt -----
===== SYSTEM REPORT =====
Date     : Thu Sep  3 16:40:53 UTC 2026
Hostname : c071b53e37c7
User     : root

===== DISK USAGE =====
Filesystem      Size  Used Avail Use% Mounted on
overlay         453G   63G  367G  15% /
tmpfs            64M     0   64M   0% /dev
shm              64M     0   64M   0% /dev/shm
/dev/vda1       453G   63G  367G  15% /etc/hosts
tmpfs           3.0G   28K  3.0G   1% /run
tmpfs           5.0M     0  5.0M   0% /run/lock

===== RUNNING PROCESSES =====
...

Script finished successfully.
```

### Verifying what the script created

```console
########## VERIFY WHAT THE SCRIPT CREATED ##########
$ ls -la devops_report
total 12
drwxr-xr-x 2 root root 4096 Sep  3 16:40 .
drwx------ 1 root root 4096 Sep  3 16:40 ..
-rw-r--r-- 1 root root 2297 Sep  3 16:40 process_list.txt

$ tree devops_report
devops_report
`-- process_list.txt

0 directories, 1 file

$ wc -l devops_report/process_list.txt
35 devops_report/process_list.txt

########## THE FULL GENERATED REPORT FILE ##########
$ cat devops_report/process_list.txt
===== SYSTEM REPORT =====
Date     : Thu Sep  3 16:40:53 UTC 2026
Hostname : c071b53e37c7
User     : root

===== DISK USAGE =====
Filesystem      Size  Used Avail Use% Mounted on
overlay         453G   63G  367G  15% /
tmpfs            64M     0   64M   0% /dev
shm              64M     0   64M   0% /dev/shm
/dev/vda1       453G   63G  367G  15% /etc/hosts
tmpfs           3.0G   28K  3.0G   1% /run
tmpfs           5.0M     0  5.0M   0% /run/lock

===== RUNNING PROCESSES =====
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root           1  0.0  0.0 165204  9696 ?        Ss   16:34   0:00 /sbin/init
root          26  0.0  0.0  31624 10828 ?        S<s  16:34   0:00 /lib/systemd/systemd-journald
systemd+      36  0.0  0.0  22264  9012 ?        Ss   16:34   0:00 /lib/systemd/systemd-resolved
root         736  0.0  0.0  55068  2248 ?        Ss   16:36   0:00 nginx: master process /usr/sbin/nginx -g daemon on; master_process on;
www-data     737  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     738  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     740  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     741  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     742  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     743  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     744  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     745  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     746  0.0  0.0  55396  3212 ?        S    16:36   0:00 nginx: worker process
www-data     747  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     749  0.0  0.0  55396  3212 ?        S    16:36   0:00 nginx: worker process
www-data     750  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
root        1049  0.0  0.0  13908  4056 ?        Ssl  16:40   0:00 expect -f /tmp/drive.exp
root        1056  0.0  0.0   3880  2804 pts/0    Ss+  16:40   0:00 /bin/bash /root/system_info.sh
root        1069  0.0  0.0   6448  2488 pts/0    R+   16:40   0:00 ps aux

```

### Run 2 — pressing Enter to accept the defaults

The script falls back to `system_report` and `processes` using Bash default
parameter expansion, `DIR_NAME=${DIR_NAME:-system_report}`, so it never creates
a file called `.txt` if the user just hits Enter.

```console
$ ./system_info.sh
Enter a name for the report directory: 
Enter a name for the report file (without .txt): 
Created directory : system_report
Created file      : system_report/processes.txt

Running processes saved to: system_report/processes.txt
File size: 4.0K

----- First 15 lines of system_report/processes.txt -----
===== SYSTEM REPORT =====
Date     : Thu Sep  3 16:41:04 UTC 2026
Hostname : c071b53e37c7
User     : root

===== DISK USAGE =====
Filesystem      Size  Used Avail Use% Mounted on
overlay         453G   63G  367G  15% /
tmpfs            64M     0   64M   0% /dev
shm              64M     0   64M   0% /dev/shm
/dev/vda1       453G   63G  367G  15% /etc/hosts
tmpfs           3.0G   28K  3.0G   1% /run
tmpfs           5.0M     0  5.0M   0% /run/lock

===== RUNNING PROCESSES =====
...

Script finished successfully.
```

---

## Notes on the shell concepts used

**Variables and command substitution.** `CURRENT_DATE=$(date)` runs `date` and
stores its *output*. No spaces are allowed around the `=`. Variables are read
back with `$CURRENT_DATE`, and are always wrapped in double quotes when used as
arguments — `mkdir -p "$DIR_NAME"` — so a name containing a space is treated as
one argument rather than two.

**`read -p`.** Prints a prompt and stores the typed line into a variable:
`read -p "Enter a name: " DIR_NAME`. The prompt only appears when input comes
from a terminal, which is why the transcripts above were captured through a
pseudo-terminal rather than a plain pipe.

**Default values.** `${DIR_NAME:-system_report}` evaluates to `$DIR_NAME` if it
is set and non-empty, otherwise to `system_report`. This is what makes Run 2
work.

**`>` vs `>>`.** `>` **truncates** the file and writes from the top; `>>`
**appends** to the end. The script deliberately uses `>` for the very first
line so that re-running it produces a fresh report, then `>>` for every
subsequent block so nothing is lost.

**`mkdir -p`.** The `-p` flag creates parent directories as needed *and* exits
successfully if the directory already exists, so re-running the script is safe.

**`ps aux --sort=-%cpu`.** Sorts by CPU descending; the leading `-` means
descending. `head -n 11` keeps the header row plus the top 10 processes. The
script falls back to plain `ps aux` because `--sort` is a GNU/Linux extension
that BSD `ps` (macOS) does not support.
