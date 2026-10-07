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
| 10a | `ps` output stored with a plain `>` | `ps aux > demo_dir/processes.log`, shown in [Every listed command, run individually](#every-listed-command-run-individually) | — |

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

## Every listed command, run individually

The script output above shows every command working together. The submission
also asks for a README "with all commands output", so each command from the
**Commands to Use** list was also run on its own, in a fresh `ubuntu:22.04`
container (same kind of environment as the runs above), with its output
captured. This block also contains the plain `ps aux > file` redirection — in
the script itself the report header is written with `>` and the process list is
then appended with `>>`.

Raw transcript: [`evidence/commands-individually.txt`](evidence/commands-individually.txt).

```console
########## VARIABLES AND COMMAND SUBSTITUTION ##########
$ NAME="Shaurya Verma"
$ ROLL=24BCS10151
$ TODAY=$(date +%F)
$ HOST=$(hostname)
$ echo "Name=$NAME Roll=$ROLL Date=$TODAY Host=$HOST"
Name=Shaurya Verma Roll=24BCS10151 Date=2026-10-07 Host=21b56a42a55a

$ echo "User: $(whoami), shell: $SHELL"
User: root, shell: /bin/bash

########## echo ##########
$ echo "Hello from echo"
Hello from echo
$ echo -e "line1\nline2"
line1
line2
$ echo -n "no newline"; echo " <- same line"
no newline <- same line

########## mkdir ##########
$ mkdir demo_dir
$ mkdir -p demo_dir/logs/2026
$ ls -ld demo_dir demo_dir/logs demo_dir/logs/2026
drwxr-xr-x 3 root root 4096 Oct  7 13:06 demo_dir
drwxr-xr-x 3 root root 4096 Oct  7 13:06 demo_dir/logs
drwxr-xr-x 2 root root 4096 Oct  7 13:06 demo_dir/logs/2026

########## touch ##########
$ touch demo_dir/notes.txt
$ ls -l demo_dir/notes.txt
-rw-r--r-- 1 root root 0 Oct  7 13:06 demo_dir/notes.txt
$ sleep 2; touch demo_dir/notes.txt   # touching again only updates the timestamp
$ ls -l --time-style=full-iso demo_dir/notes.txt
-rw-r--r-- 1 root root 0 2026-10-07 13:06:36.719741009 +0000 demo_dir/notes.txt

########## df ##########
$ df -h
Filesystem      Size  Used Avail Use% Mounted on
overlay         911G  192G  673G  23% /
tmpfs            64M     0   64M   0% /dev
shm              64M     0   64M   0% /dev/shm
/dev/vda1       911G  192G  673G  23% /etc/hosts
tmpfs           4.0K     0  4.0K   0% /proc/scsi

$ df -h / --output=source,size,used,avail,pcent
Filesystem      Size  Used Avail Use%
overlay         911G  192G  673G  23%

########## ps ##########
$ ps
    PID TTY          TIME CMD
      1 ?        00:00:00 sleep
    287 ?        00:00:00 bash
    293 ?        00:00:00 bash
    294 ?        00:00:00 sleep
    295 ?        00:00:00 tail
    309 ?        00:00:00 ps

$ ps aux | head -n 6
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root           1  0.0  0.0   2236  1112 ?        Ss   13:06   0:00 sleep 900
root         287  0.0  0.0   3888  2780 ?        Ss   13:06   0:00 bash -c bash /tmp/run.sh; echo; echo "########## read -p (driven through a pseudo-terminal so the prompt is shown) ##########"; echo "\$ read -p \"Enter your name: \" NAME; read -p \"Enter your roll number: \" ROLL; echo \"Hello \$NAME (\$ROLL)\""; expect -f /tmp/drive.exp | tail -n +2
root         293  0.0  0.0   3888  2868 ?        S    13:06   0:00 bash /tmp/run.sh
root         294  0.0  0.0   2236  1112 ?        S    13:06   0:00 sleep 600
root         295  0.0  0.0   2268  1092 ?        S    13:06   0:00 tail -f /dev/null

########## > OUTPUT REDIRECTION: running processes into a file ##########
$ ps aux > demo_dir/processes.log
$ wc -l demo_dir/processes.log
7 demo_dir/processes.log
$ head -n 5 demo_dir/processes.log
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root           1  0.0  0.0   2236  1112 ?        Ss   13:06   0:00 sleep 900
root         287  0.0  0.0   3888  2780 ?        Ss   13:06   0:00 bash -c bash /tmp/run.sh; echo; echo "########## read -p (driven through a pseudo-terminal so the prompt is shown) ##########"; echo "\$ read -p \"Enter your name: \" NAME; read -p \"Enter your roll number: \" ROLL; echo \"Hello \$NAME (\$ROLL)\""; expect -f /tmp/drive.exp | tail -n +2
root         293  0.0  0.0   3888  2868 ?        S    13:06   0:00 bash /tmp/run.sh
root         294  0.0  0.0   2236  1112 ?        S    13:06   0:00 sleep 600

########## > TRUNCATES, >> APPENDS ##########
$ echo "first"  > demo_dir/redirect.txt
$ echo "second" > demo_dir/redirect.txt
$ cat demo_dir/redirect.txt
second
$ echo "third" >> demo_dir/redirect.txt
$ cat demo_dir/redirect.txt
second
third

$ ls -la demo_dir
total 20
drwxr-xr-x 3 root root 4096 Oct  7 13:06 .
drwx------ 1 root root 4096 Oct  7 13:06 ..
drwxr-xr-x 3 root root 4096 Oct  7 13:06 logs
-rw-r--r-- 1 root root    0 Oct  7 13:06 notes.txt
-rw-r--r-- 1 root root  826 Oct  7 13:06 processes.log
-rw-r--r-- 1 root root   13 Oct  7 13:06 redirect.txt

########## read -p (driven through a pseudo-terminal so the prompt is shown) ##########
$ read -p "Enter your name: " NAME; read -p "Enter your roll number: " ROLL; echo "Hello $NAME ($ROLL)"
Enter your name: Shaurya Verma
Enter your roll number: 24BCS10151
Hello Shaurya Verma (24BCS10151)
```

### What each block shows

| Command | What the output shows |
|---|---|
| Variables | `NAME=...` stores a literal string; `TODAY=$(date +%F)` and `HOST=$(hostname)` store the **output of a command** (command substitution). `$NAME` reads it back. |
| `echo` | Prints text. `-e` turns `\n` into a real newline; `-n` leaves out the trailing newline, so the next `echo` carries on on the same line. |
| `mkdir` | `mkdir demo_dir` creates a single directory; `mkdir -p` creates the whole `logs/2026` chain in one go. `ls -ld` lists the directories themselves rather than what is inside them. |
| `touch` | Creates an empty (0-byte) file. Running it again on a file that already exists only updates the timestamp (`13:06:36.719…`). The contents are left alone. |
| `df -h` | Disk usage per mounted filesystem in human-readable units; `--output=` picks just the columns you need. |
| `ps` / `ps aux` | `ps` only lists processes for the current session; `ps aux` lists every process on the system with user, CPU, memory and full command line. The `sleep 600` and `tail -f /dev/null` processes were started in the background so the list has something in it besides the shell. |
| `ps aux > file` | The process list goes into `processes.log` instead of the screen, and nothing is printed. `wc -l` reports 7 lines: the header plus 6 processes (`sleep 900`, the two `bash` shells, `sleep 600`, `tail`, and `ps aux` itself, which is running while it takes the snapshot). |
| `>` vs `>>` | `"first"` was overwritten by `"second"` because `>` truncates the file; `>>` added `"third"` underneath without removing anything. |
| `read -p` | The prompt `Enter your name: ` is printed, the typed reply is stored in `NAME`, and the next command uses it. It was driven through a pseudo-terminal with `expect`, because `read -p` only shows its prompt when input comes from a terminal. |

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
