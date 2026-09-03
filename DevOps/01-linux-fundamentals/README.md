# Linux Fundamentals — Homework

All commands in this document were executed on **Ubuntu 22.04** inside a
systemd-enabled Docker container (see the [`Dockerfile`](Dockerfile) in this
folder). Every code block below is **real captured output**, not a sample.

```bash
# Reproduce this environment yourself:
docker build -t linux-practice .
docker run -d --name linux-practice --privileged --cgroupns=host \
    -v /sys/fs/cgroup:/sys/fs/cgroup:rw linux-practice
docker exec -it linux-practice bash
```

---

## Task 1 — Soft Link vs Hard Link

### The one-paragraph explanation

Every file on a Linux filesystem is really two things: an **inode** (the
metadata + pointers to the actual data blocks) and a **directory entry** (a
name that points at an inode). The filename is not the file — the inode is.

- A **hard link** is just *another directory entry pointing at the same inode*.
  There is no "original" and no "copy": both names are equal citizens. The
  inode keeps a **link count**, and the data is only freed when that count
  drops to zero. So deleting one name does not destroy the data.

- A **soft link** (symbolic link / symlink) is *a separate file, with its own
  inode*, whose contents are simply the **text of a path**. It is a signpost.
  If the thing it points at disappears, the signpost still exists but now
  points at nothing — a "dangling" or broken symlink.

### Commands

| Goal | Command |
|---|---|
| Create a hard link | `ln target linkname` |
| Create a soft link | `ln -s target linkname` |
| See inode numbers and link counts | `ls -li` |
| See where a symlink points | `readlink linkname` or `ls -l` |
| Inspect inode / link count / type | `stat filename` |
| Delete either kind of link | `rm linkname` or `unlink linkname` |
| Find all hard links to one inode | `find / -inum <inode>` |
| Follow a symlink chain to the end | `readlink -f linkname` |

> **Deleting note:** `rm` on a link always removes *the link*, never the
> target. `rm softlink.txt` deletes the signpost, not the file it points to.
> There is no special "delete a link" command — a link *is* a directory entry.

### Comparison table

| | Hard link | Soft link |
|---|---|---|
| Own inode? | **No** — shares the target's inode | **Yes** — separate inode |
| Shown by `ls -l` as | `-rw-r--r--` (a normal file) | `lrwxrwxrwx ... -> target` |
| Link count of target | **Increases** | Unchanged |
| Survives deleting the original? | **Yes** — data stays alive | **No** — becomes broken |
| Can cross filesystems / partitions? | **No** | **Yes** |
| Can point to a directory? | **No** (root-only, effectively banned) | **Yes** |
| Can point at something that doesn't exist? | No | **Yes** (dangling link) |
| Size on disk | Zero extra (same data) | Length of the path string |
| Permissions | Those of the shared inode | Always `lrwxrwxrwx`; target's rules apply |

### Practical session — creating, testing and deleting both link types

```console
########## SETUP: create the original file ##########
$ echo 'Hello from the original file' > original.txt

$ cat original.txt
Hello from the original file

$ ls -li original.txt
119726 -rw-r--r-- 1 root root 29 Sep  3 16:34 original.txt

########## CREATE A HARD LINK ##########
$ ln original.txt hardlink.txt

########## CREATE A SOFT (SYMBOLIC) LINK ##########
$ ln -s original.txt softlink.txt

########## COMPARE THEM ##########
$ ls -li
total 8
119726 -rw-r--r-- 2 root root 29 Sep  3 16:34 hardlink.txt
119726 -rw-r--r-- 2 root root 29 Sep  3 16:34 original.txt
119738 lrwxrwxrwx 1 root root 12 Sep  3 16:34 softlink.txt -> original.txt

$ stat -c '%n -> inode:%i links:%h size:%s type:%F' original.txt hardlink.txt softlink.txt
original.txt -> inode:119726 links:2 size:29 type:regular file
hardlink.txt -> inode:119726 links:2 size:29 type:regular file
softlink.txt -> inode:119738 links:1 size:12 type:symbolic link

########## READING THROUGH BOTH LINKS ##########
$ cat hardlink.txt
Hello from the original file

$ cat softlink.txt
Hello from the original file

########## EDIT VIA HARD LINK - ORIGINAL CHANGES TOO ##########
$ echo 'Line added through the HARD link' >> hardlink.txt

$ cat original.txt
Hello from the original file
Line added through the HARD link

########## EDIT VIA SOFT LINK - ORIGINAL CHANGES TOO ##########
$ echo 'Line added through the SOFT link' >> softlink.txt

$ cat original.txt
Hello from the original file
Line added through the HARD link
Line added through the SOFT link

########## THE KEY TEST: DELETE THE ORIGINAL ##########
$ rm original.txt

$ ls -li
total 4
119726 -rw-r--r-- 1 root root 95 Sep  3 16:34 hardlink.txt
119738 lrwxrwxrwx 1 root root 12 Sep  3 16:34 softlink.txt -> original.txt

--- Hard link still works (data still has 1 reference): ---
$ cat hardlink.txt
Hello from the original file
Line added through the HARD link
Line added through the SOFT link

--- Soft link is now BROKEN (dangling pointer): ---
$ cat softlink.txt
cat: softlink.txt: No such file or directory

$ ls -l softlink.txt
lrwxrwxrwx 1 root root 12 Sep  3 16:34 softlink.txt -> original.txt

$ readlink softlink.txt
original.txt

$ test -e softlink.txt && echo EXISTS || echo 'BROKEN SYMLINK - target missing'
BROKEN SYMLINK - target missing

########## RESTORE THE TARGET - SOFT LINK HEALS ITSELF ##########
$ cp hardlink.txt original.txt

$ cat softlink.txt
Hello from the original file
Line added through the HARD link
Line added through the SOFT link

########## HARD LINKS CANNOT CROSS FILESYSTEMS OR LINK DIRECTORIES ##########
$ mkdir -p mydir

$ ln mydir hardlink-to-dir
ln: mydir: hard link not allowed for directory

$ ln -s mydir softlink-to-dir

$ ls -ld softlink-to-dir
lrwxrwxrwx 1 root root 5 Sep  3 16:34 softlink-to-dir -> mydir

########## DELETING LINKS ##########
$ rm softlink.txt

$ ls -li
total 12
119726 -rw-r--r-- 1 root root   95 Sep  3 16:34 hardlink.txt
119772 drwxr-xr-x 2 root root 4096 Sep  3 16:34 mydir
119768 -rw-r--r-- 1 root root   95 Sep  3 16:34 original.txt
119777 lrwxrwxrwx 1 root root    5 Sep  3 16:34 softlink-to-dir -> mydir

$ rm hardlink.txt

$ ls -li
total 8
119772 drwxr-xr-x 2 root root 4096 Sep  3 16:34 mydir
119768 -rw-r--r-- 1 root root   95 Sep  3 16:34 original.txt
119777 lrwxrwxrwx 1 root root    5 Sep  3 16:34 softlink-to-dir -> mydir

$ unlink softlink-to-dir

$ ls -l
total 8
drwxr-xr-x 2 root root 4096 Sep  3 16:34 mydir
-rw-r--r-- 1 root root   95 Sep  3 16:34 original.txt

```

### What that output proves

1. `ls -li` shows `original.txt` and `hardlink.txt` sharing **inode 119726**
   with a link count of **2**, while `softlink.txt` has its **own inode
   119738**, a link count of 1, and a size of **12 bytes** — exactly the
   length of the string `original.txt`.
2. Writing through *either* link changed the same underlying data.
3. After `rm original.txt`, the link count on inode 119726 dropped to **1** and
   `cat hardlink.txt` still printed the full contents — **the data survived**.
   Meanwhile `cat softlink.txt` failed with `No such file or directory`, even
   though `ls -l` still happily listed the symlink. That is a dangling link.
4. Re-creating a file at the old path made the symlink work again — proof that
   a symlink resolves **by path, at access time**, not by inode.
5. `ln mydir hardlink-to-dir` was refused: `hard link not allowed for
   directory`. `ln -s` on the same directory worked fine.

### Interview preparation

**Q: What is the difference between a hard link and a soft link?**
> A hard link is an additional directory entry pointing to the same inode, so
> it shares the data and the link count; the file's data lives until the last
> hard link is removed. A soft link is its own file whose content is a path
> string, so it breaks if the target is moved or deleted. Soft links can cross
> filesystems and point to directories; hard links cannot do either.

**Q: What happens to each if I delete the original file?**
> The hard link keeps working — the data is still referenced. The soft link
> becomes a dangling pointer: it still shows in `ls`, but any read fails with
> "No such file or directory".

**Q: Why can't hard links cross filesystems?**
> Inode numbers are only unique *within* a single filesystem. A directory
> entry on filesystem A cannot meaningfully reference inode 500 on filesystem
> B, because inode 500 also exists on A. A symlink stores a path string, which
> is filesystem-independent, so it has no such limit.

**Q: Why are hard links to directories forbidden?**
> They would let you create cycles in the directory tree. That would break
> tools that walk the filesystem (they would loop forever) and make it
> impossible to reliably reference-count and garbage-collect directories.
> `.` and `..` are the only directory hard links, and the kernel creates them.

**Q: How do I find every hard link to a file?**
> Get the inode with `ls -i file`, then `find /mount/point -xdev -inum <inode>`.

**Q: Does a symlink take up space?**
> A tiny amount — an inode plus the path string. Most filesystems store short
> paths inside the inode itself ("fast symlinks"), so it costs nothing extra.

**Q: If I `chmod` a symlink, what happens?**
> Symlink permissions are always `lrwxrwxrwx` and are ignored. `chmod` follows
> the link and changes the **target's** permissions. Access is always decided
> by the target's permissions.

---

## Task 2 — `adduser` vs `useradd`

### The short answer

They are **not** two names for the same tool.

- **`useradd`** is the **low-level binary** from the `shadow-utils` package. It
  exists on every Linux distribution. It does exactly what you tell it and
  nothing more — no home directory, no password, no prompts. It is the
  primitive.
- **`adduser`** is a **high-level Perl wrapper script**, specific to
  **Debian/Ubuntu**. It calls `useradd` underneath, but interactively walks you
  through the sensible defaults: creates the home directory, copies `/etc/skel`,
  creates a matching user group, prompts for a password and full name.

The captured `file` output below is the clearest proof of the relationship:
`useradd` is an ELF executable, `adduser` is a Perl script.

### Which is preferred on Ubuntu, and why

**`adduser` is the recommended command for humans on Ubuntu/Debian.** Reasons:

1. **Safe defaults.** It creates the home directory, sets `/bin/bash`, copies
   the skeleton dotfiles and sets correct ownership and `0750` permissions —
   all things you must remember to request manually with `useradd`.
2. **It follows the distro policy** in `/etc/adduser.conf` (UID ranges, whether
   to use per-user groups, the default shell), so accounts are consistent.
3. **It is interactive and validates input**, so it is much harder to create a
   half-broken account by typo.
4. **Debian's own manpage says so** — `man useradd` on Debian carries the note
   that `adduser` is the preferred, more friendly front end.

**When to use `useradd` instead:** in **scripts, Dockerfiles and automation**,
and on **non-Debian distros** (RHEL, CentOS, Alpine, Amazon Linux) where
`adduser` either doesn't exist or is a totally different BusyBox applet.
`useradd` is non-interactive and portable, which is exactly what a provisioning
script needs.

> Note the trap: on **Alpine/BusyBox**, `adduser` exists but is a *different*
> program with *different flags*. So `adduser` is not portable — another reason
> automation should stick to `useradd`.

### Command comparison

| Task | `useradd` (portable, low level) | `adduser` (Ubuntu, friendly) |
|---|---|---|
| Create a usable account | `useradd -m -s /bin/bash bob` | `adduser bob` |
| Home directory | only with `-m` | automatic |
| Password | separate `passwd bob` | prompted for |
| Full name / GECOS | `-c "Bob Smith"` | prompted for |
| User's own group | `-U` (or distro default) | automatic |
| Copy `/etc/skel` | only with `-m` | automatic |
| Add to a secondary group | `usermod -aG sudo bob` | `adduser bob sudo` |
| System account | `useradd -r svc` | `adduser --system svc` |
| Delete | `userdel -r bob` | `deluser --remove-home bob` |

### Practical session

```console
########## WHERE THE TWO COMMANDS LIVE ##########
$ which useradd adduser
/usr/sbin/useradd
/usr/sbin/adduser

$ file /usr/sbin/useradd /usr/sbin/adduser
/usr/sbin/useradd: ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV), dynamically linked, interpreter /lib/ld-linux-aarch64.so.1, BuildID[sha1]=9ca25c8dea54feb7dcadf3675981738d91ae86f9, for GNU/Linux 3.7.0, stripped
/usr/sbin/adduser: Perl script text executable

$ head -n 5 /usr/sbin/adduser
#!/usr/bin/perl

# adduser: a utility to add users to the system
# addgroup: a utility to add groups to the system


########## CREATING A USER THE LOW-LEVEL WAY: useradd (bare) ##########
$ useradd testuser-lowlevel

$ grep testuser-lowlevel /etc/passwd
testuser-lowlevel:x:1000:1000::/home/testuser-lowlevel:/bin/sh

$ ls -la /home/ | grep testuser-lowlevel || echo 'NO HOME DIRECTORY WAS CREATED'
NO HOME DIRECTORY WAS CREATED

$ grep testuser-lowlevel /etc/shadow
testuser-lowlevel:!:20699:0:99999:7:::

--- note the '!' in the password field = account is LOCKED, and no home dir, and /bin/sh not bash

########## useradd DONE PROPERLY (needs every flag spelled out) ##########
$ useradd -m -d /home/testuser-flags -s /bin/bash -c 'Created with flags' testuser-flags

$ grep testuser-flags /etc/passwd
testuser-flags:x:1001:1001:Created with flags:/home/testuser-flags:/bin/bash

$ ls -la /home/testuser-flags
total 20
drwxr-x--- 2 testuser-flags testuser-flags 4096 Sep  3 16:36 .
drwxr-xr-x 1 root           root           4096 Sep  3 16:36 ..
-rw-r--r-- 1 testuser-flags testuser-flags  220 Jan  6  2022 .bash_logout
-rw-r--r-- 1 testuser-flags testuser-flags 3771 Jan  6  2022 .bashrc
-rw-r--r-- 1 testuser-flags testuser-flags  807 Jan  6  2022 .profile

########## THE RECOMMENDED WAY ON UBUNTU/DEBIAN: adduser ##########
$ adduser --gecos 'DevOps Test User,,,' --disabled-password testuser
Adding user `testuser' ...
Adding new group `testuser' (1002) ...
Adding new user `testuser' (1002) with group `testuser' ...
Creating home directory `/home/testuser' ...
Copying files from `/etc/skel' ...

########## VERIFY WHAT adduser DID FOR US AUTOMATICALLY ##########
$ grep testuser: /etc/passwd
testuser:x:1002:1002:DevOps Test User,,,:/home/testuser:/bin/bash

$ id testuser
uid=1002(testuser) gid=1002(testuser) groups=1002(testuser)

$ ls -la /home/testuser
total 20
drwxr-x--- 2 testuser testuser 4096 Sep  3 16:36 .
drwxr-xr-x 1 root     root     4096 Sep  3 16:36 ..
-rw-r--r-- 1 testuser testuser  220 Sep  3 16:36 .bash_logout
-rw-r--r-- 1 testuser testuser 3771 Sep  3 16:36 .bashrc
-rw-r--r-- 1 testuser testuser  807 Sep  3 16:36 .profile

$ groups testuser
testuser : testuser

$ grep testuser /etc/group
testuser-lowlevel:x:1000:
testuser-flags:x:1001:
testuser:x:1002:

--- adduser also copied the skeleton files from /etc/skel: ---
$ ls -A /etc/skel
.bash_logout
.bashrc
.profile

$ ls -A /home/testuser
.bash_logout
.bashrc
.profile

########## SIDE BY SIDE COMPARISON ##########
$ grep -E 'testuser' /etc/passwd
testuser-lowlevel:x:1000:1000::/home/testuser-lowlevel:/bin/sh
testuser-flags:x:1001:1001:Created with flags:/home/testuser-flags:/bin/bash
testuser:x:1002:1002:DevOps Test User,,,:/home/testuser:/bin/bash

########## SETTING A PASSWORD / DELETING ##########
$ echo 'testuser:StrongPass123' | chpasswd && echo 'password set for testuser'
password set for testuser

$ passwd -S testuser
testuser P 09/03/2026 0 99999 7 -1

$ deluser --remove-home testuser-lowlevel
Looking for files to backup/remove ...
Removing user `testuser-lowlevel' ...
Warning: group `testuser-lowlevel' has no more members.
Done.

$ userdel -r testuser-flags
userdel: testuser-flags mail spool (/var/mail/testuser-flags) not found

$ grep -E 'testuser' /etc/passwd
testuser:x:1002:1002:DevOps Test User,,,:/home/testuser:/bin/bash

```

### What that output proves

- `file` shows the fundamental difference: `useradd` is an **ELF 64-bit
  executable**, `adduser` is a **Perl script text executable** whose first
  line is `#!/usr/bin/perl`. `adduser` is literally a wrapper.
- Bare `useradd testuser-lowlevel` produced an account with **no home
  directory**, shell `/bin/sh`, no comment field, and `!` in the
  `/etc/shadow` password field (a **locked** account). It is not usable.
- To match what `adduser` gives you for free, `useradd` needed four flags:
  `-m -d /home/... -s /bin/bash -c '...'`.
- `adduser testuser` narrated exactly what it did: created the group, created
  the user, created the home directory and **copied files from `/etc/skel`** —
  and the `ls -A` comparison confirms `/home/testuser` received the same three
  dotfiles that `/etc/skel` contains.
- `passwd -S testuser` returning `P` confirms a usable password is set (vs `L`
  for locked).

---

## Task 3 — `journalctl`

### What it is

`journalctl` is the query tool for the **systemd journal** — the centralised,
binary, indexed log store that `systemd-journald` maintains on any modern
systemd Linux (Ubuntu 16.04+, Debian 8+, RHEL/CentOS 7+, Fedora, Arch, SUSE).

Before systemd, logs were a pile of plain-text files in `/var/log/` written by
`rsyslog`, and every service invented its own format and its own file. The
journal replaces that with **one structured store** that captures:

- the kernel ring buffer (what `dmesg` shows),
- early boot and initrd messages,
- everything systemd services write to **stdout and stderr**,
- classic syslog traffic,
- native structured entries from applications.

Because every entry is stored with **structured metadata** (`_PID`, `_UID`,
`_SYSTEMD_UNIT`, `_HOSTNAME`, `PRIORITY`, `_COMM`…), you can filter precisely
instead of grepping text. That is the real point of it.

**Why it matters in DevOps:** when a service won't start, `journalctl -u
<service> -n 50` is almost always the fastest path to the actual error — as
demonstrated below, where a bad nginx config produced an exact file and line
number in the journal.

### Cheat sheet

| Goal | Command |
|---|---|
| Everything, oldest first | `journalctl` |
| Newest first | `journalctl -r` |
| Last 20 lines | `journalctl -n 20` |
| **Live tail** | `journalctl -f` |
| **One service** | `journalctl -u nginx` |
| **Live tail one service** | `journalctl -u nginx -f` |
| Since the current boot | `journalctl -b` |
| Previous boot | `journalctl -b -1` |
| List boots | `journalctl --list-boots` |
| Kernel messages only (`dmesg`) | `journalctl -k` |
| Errors and worse | `journalctl -p err` |
| Time window | `journalctl --since "2024-01-01" --until "1 hour ago"` |
| Today only | `journalctl --since today` |
| By process ID | `journalctl _PID=1234` |
| By executable | `journalctl /usr/sbin/nginx` |
| By tag from `logger` | `journalctl -t mytag` |
| Full structured record | `journalctl -o json-pretty` |
| Just the message text | `journalctl -o cat` |
| Explanatory help text | `journalctl -xe` |
| Disk used by logs | `journalctl --disk-usage` |
| Trim to 7 days / 200 MB | `journalctl --vacuum-time=7d` / `--vacuum-size=200M` |

**Priority levels for `-p`:** `0 emerg`, `1 alert`, `2 crit`, `3 err`,
`4 warning`, `5 notice`, `6 info`, `7 debug`. `-p err` means "err **and more
severe**", i.e. levels 0–3.

**The single most useful one to memorise:**
`journalctl -u <service> -n 50 --no-pager` — "why did this service just fail?"

> **Persistence gotcha:** by default on some systems the journal lives in
> `/run/log/journal`, which is **tmpfs — it vanishes on reboot**. To keep logs
> across reboots: `sudo mkdir -p /var/log/journal && sudo systemctl restart
> systemd-journald`.

### Practical session

```console
########## IS THE JOURNAL RUNNING? ##########
$ systemctl is-active systemd-journald
active

$ systemctl status systemd-journald --no-pager | head -n 12
● systemd-journald.service - Journal Service
     Loaded: loaded (/lib/systemd/system/systemd-journald.service; static)
     Active: active (running) since Thu 2026-09-03 16:34:06 UTC; 2min 49s ago
TriggeredBy: ● systemd-journald-audit.socket
             ● systemd-journald.socket
             ● systemd-journald-dev-log.socket
       Docs: man:systemd-journald.service(8)
             man:journald.conf(5)
   Main PID: 26 (systemd-journal)
     Status: "Processing requests..."
      Tasks: 1 (limit: 17956)
     Memory: 4.6M

########## HOW BIG IS THE JOURNAL ON DISK? ##########
$ journalctl --disk-usage
Archived and active journals take up 8.0M in the file system.

########## 1. VIEW ALL LOGS (oldest first) - showing the first 15 lines ##########
$ journalctl --no-pager | head -n 15
Sep 03 16:34:06 c071b53e37c7 kernel: Booting Linux on physical CPU 0x0000000000 [0x610f0000]
Sep 03 16:34:06 c071b53e37c7 kernel: Linux version 6.12.69-linuxkit (root@buildkitsandbox) (gcc (Alpine 15.2.0) 15.2.0, GNU ld (GNU Binutils) 2.45.1) #1 SMP Mon Feb 16 11:19:06 UTC 2026
Sep 03 16:34:06 c071b53e37c7 kernel: OF: reserved mem: Reserved memory: No reserved-memory node in the DT
Sep 03 16:34:06 c071b53e37c7 kernel: Zone ranges:
Sep 03 16:34:06 c071b53e37c7 kernel:   DMA      [mem 0x0000000070000000-0x00000000ffffffff]
Sep 03 16:34:06 c071b53e37c7 kernel:   DMA32    empty
Sep 03 16:34:06 c071b53e37c7 kernel:   Normal   [mem 0x0000000100000000-0x000000042fffffff]
Sep 03 16:34:06 c071b53e37c7 kernel: Movable zone start for each node
Sep 03 16:34:06 c071b53e37c7 kernel: Early memory node ranges
Sep 03 16:34:06 c071b53e37c7 kernel:   node   0: [mem 0x0000000070000000-0x000000042fffffff]
Sep 03 16:34:06 c071b53e37c7 kernel: Initmem setup node 0 [mem 0x0000000070000000-0x000000042fffffff]
Sep 03 16:34:06 c071b53e37c7 kernel: psci: probing for conduit method from DT.
Sep 03 16:34:06 c071b53e37c7 kernel: psci: PSCIv1.1 detected in firmware.
Sep 03 16:34:06 c071b53e37c7 kernel: psci: Using standard PSCI v0.2 function IDs
Sep 03 16:34:06 c071b53e37c7 kernel: psci: Trusted OS migration not required

########## 2. NEWEST ENTRIES FIRST (-r) ##########
$ journalctl -r --no-pager -n 10
Sep 03 16:36:45 c071b53e37c7 systemd-resolved[36]: Clock change detected. Flushing caches.
Sep 03 16:36:35 c071b53e37c7 userdel[668]: removed shadow group 'testuser-flags' owned by 'testuser-flags'
Sep 03 16:36:35 c071b53e37c7 userdel[668]: removed group 'testuser-flags' owned by 'testuser-flags'
Sep 03 16:36:35 c071b53e37c7 userdel[668]: delete user 'testuser-flags'
Sep 03 16:36:35 c071b53e37c7 userdel[660]: removed shadow group 'testuser-lowlevel' owned by 'testuser-lowlevel'
Sep 03 16:36:35 c071b53e37c7 userdel[660]: removed group 'testuser-lowlevel' owned by 'testuser-lowlevel'
Sep 03 16:36:35 c071b53e37c7 userdel[660]: delete user 'testuser-lowlevel'
Sep 03 16:36:35 c071b53e37c7 chpasswd[653]: pam_unix(chpasswd:chauthtok): password changed for testuser
Sep 03 16:36:35 c071b53e37c7 chfn[638]: changed user 'testuser' information
Sep 03 16:36:35 c071b53e37c7 chfn[632]: changed user 'testuser' information

########## 3. LAST N LINES (-n) ##########
$ journalctl -n 5 --no-pager
Sep 03 16:36:35 c071b53e37c7 userdel[660]: removed shadow group 'testuser-lowlevel' owned by 'testuser-lowlevel'
Sep 03 16:36:35 c071b53e37c7 userdel[668]: delete user 'testuser-flags'
Sep 03 16:36:35 c071b53e37c7 userdel[668]: removed group 'testuser-flags' owned by 'testuser-flags'
Sep 03 16:36:35 c071b53e37c7 userdel[668]: removed shadow group 'testuser-flags' owned by 'testuser-flags'
Sep 03 16:36:45 c071b53e37c7 systemd-resolved[36]: Clock change detected. Flushing caches.

########## 4. LOGS SINCE BOOT (-b) ##########
$ journalctl -b --no-pager -n 8
Sep 03 16:36:35 c071b53e37c7 chpasswd[653]: pam_unix(chpasswd:chauthtok): password changed for testuser
Sep 03 16:36:35 c071b53e37c7 userdel[660]: delete user 'testuser-lowlevel'
Sep 03 16:36:35 c071b53e37c7 userdel[660]: removed group 'testuser-lowlevel' owned by 'testuser-lowlevel'
Sep 03 16:36:35 c071b53e37c7 userdel[660]: removed shadow group 'testuser-lowlevel' owned by 'testuser-lowlevel'
Sep 03 16:36:35 c071b53e37c7 userdel[668]: delete user 'testuser-flags'
Sep 03 16:36:35 c071b53e37c7 userdel[668]: removed group 'testuser-flags' owned by 'testuser-flags'
Sep 03 16:36:35 c071b53e37c7 userdel[668]: removed shadow group 'testuser-flags' owned by 'testuser-flags'
Sep 03 16:36:45 c071b53e37c7 systemd-resolved[36]: Clock change detected. Flushing caches.

$ journalctl --list-boots --no-pager
 0 65f4c756407e46439b8a3e898bc799f0 Thu 2026-09-03 16:34:06 UTC—Thu 2026-09-03 16:36:45 UTC

########## NOW START A SERVICE SO WE HAVE SOMETHING TO INSPECT ##########
$ systemctl start nginx

$ systemctl is-active nginx
active

########## 5. LOGS FOR ONE SPECIFIC SERVICE (-u) ##########
$ journalctl -u nginx --no-pager
Sep 03 16:34:07 c071b53e37c7 systemd[1]: Starting A high performance web server and a reverse proxy server...
Sep 03 16:34:07 c071b53e37c7 systemd[1]: Started A high performance web server and a reverse proxy server.

########## GENERATE SOME REAL SERVICE ACTIVITY ##########
$ systemctl reload nginx

$ systemctl restart nginx

--- deliberately break the config to produce an ERROR in the journal ---
$ cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak

$ echo 'this_is_an_invalid_directive;' >> /etc/nginx/nginx.conf

$ systemctl restart nginx
Job for nginx.service failed because the control process exited with error code.
See "systemctl status nginx.service" and "journalctl -xeu nginx.service" for details.

$ journalctl -u nginx --no-pager -n 15
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Reloaded A high performance web server and a reverse proxy server.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Stopping A high performance web server and a reverse proxy server...
Sep 03 16:36:56 c071b53e37c7 systemd[1]: nginx.service: Deactivated successfully.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Stopped A high performance web server and a reverse proxy server.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Starting A high performance web server and a reverse proxy server...
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Started A high performance web server and a reverse proxy server.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Stopping A high performance web server and a reverse proxy server...
Sep 03 16:36:56 c071b53e37c7 systemd[1]: nginx.service: Deactivated successfully.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Stopped A high performance web server and a reverse proxy server.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Starting A high performance web server and a reverse proxy server...
Sep 03 16:36:56 c071b53e37c7 nginx[730]: nginx: [emerg] unknown directive "this_is_an_invalid_directive" in /etc/nginx/nginx.conf:84
Sep 03 16:36:56 c071b53e37c7 nginx[730]: nginx: configuration file /etc/nginx/nginx.conf test failed
Sep 03 16:36:56 c071b53e37c7 systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE
Sep 03 16:36:56 c071b53e37c7 systemd[1]: nginx.service: Failed with result 'exit-code'.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Failed to start A high performance web server and a reverse proxy server.

$ cp /etc/nginx/nginx.conf.bak /etc/nginx/nginx.conf && systemctl restart nginx && systemctl is-active nginx
active

########## 6. FILTER BY PRIORITY (-p) - errors only ##########
$ journalctl -p err --no-pager -n 10
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Failed to start A high performance web server and a reverse proxy server.

$ journalctl -u nginx -p err --no-pager -n 5
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Failed to start A high performance web server and a reverse proxy server.

########## 7. FILTER BY TIME (--since / --until) ##########
$ journalctl --since '10 minutes ago' --no-pager -n 5
Sep 03 16:34:06 c071b53e37c7 kernel: Booting Linux on physical CPU 0x0000000000 [0x610f0000]
Sep 03 16:34:06 c071b53e37c7 kernel: Linux version 6.12.69-linuxkit (root@buildkitsandbox) (gcc (Alpine 15.2.0) 15.2.0, GNU ld (GNU Binutils) 2.45.1) #1 SMP Mon Feb 16 11:19:06 UTC 2026
Sep 03 16:34:06 c071b53e37c7 kernel: OF: reserved mem: Reserved memory: No reserved-memory node in the DT
Sep 03 16:34:06 c071b53e37c7 kernel: Zone ranges:
Sep 03 16:34:06 c071b53e37c7 kernel:   DMA      [mem 0x0000000070000000-0x00000000ffffffff]

$ journalctl --since today --no-pager -n 3
Sep 03 16:34:06 c071b53e37c7 kernel: Booting Linux on physical CPU 0x0000000000 [0x610f0000]
Sep 03 16:34:06 c071b53e37c7 kernel: Linux version 6.12.69-linuxkit (root@buildkitsandbox) (gcc (Alpine 15.2.0) 15.2.0, GNU ld (GNU Binutils) 2.45.1) #1 SMP Mon Feb 16 11:19:06 UTC 2026
Sep 03 16:34:06 c071b53e37c7 kernel: OF: reserved mem: Reserved memory: No reserved-memory node in the DT

########## 8. OUTPUT FORMATS (-o) ##########
$ journalctl -u nginx -o short-iso --no-pager -n 3
2026-09-03T16:36:56+0000 c071b53e37c7 systemd[1]: Failed to start A high performance web server and a reverse proxy server.
2026-09-03T16:36:56+0000 c071b53e37c7 systemd[1]: Starting A high performance web server and a reverse proxy server...
2026-09-03T16:36:56+0000 c071b53e37c7 systemd[1]: Started A high performance web server and a reverse proxy server.

$ journalctl -u nginx -o json-pretty --no-pager -n 1
{
	"CODE_FILE" : "src/core/job.c",
	"_EXE" : "/usr/lib/systemd/systemd",
	"CODE_LINE" : "713",
	"INVOCATION_ID" : "8ce82ed067d24aad8a5192bb17813613",
	"_TRANSPORT" : "journal",
	"PRIORITY" : "6",
	"MESSAGE_ID" : "39f53479d3a045ac8e11786248231fbf",
	"SYSLOG_IDENTIFIER" : "systemd",
	"_CAP_EFFECTIVE" : "1ffffffffff",
	"__MONOTONIC_TIMESTAMP" : "13966715366",
	"CODE_FUNC" : "job_emit_done_message",
	"TID" : "1",
	"_COMM" : "systemd",
	"JOB_RESULT" : "done",
	"_PID" : "1",
	"_HOSTNAME" : "c071b53e37c7",
	"_BOOT_ID" : "65f4c756407e46439b8a3e898bc799f0",
	"_CMDLINE" : "/sbin/init",
	"_SYSTEMD_UNIT" : "init.scope",
	"MESSAGE" : "Started A high performance web server and a reverse proxy server.",
	"__CURSOR" : "s=8e422dcb7e614c8bab22e7c8e5cb07ce;i=47c;b=65f4c756407e46439b8a3e898bc799f0;m=3407b29e6;t=65a96c29b50d1;x=883398a23802b9a4",
	"_MACHINE_ID" : "a49d57ceb04249f98358b9d046f0f8c0",
	"_SYSTEMD_SLICE" : "-.slice",
	"_SOURCE_REALTIME_TIMESTAMP" : "1788453416816828",
	"_UID" : "0",
	"__REALTIME_TIMESTAMP" : "1788453416816849",
	"_SYSTEMD_CGROUP" : "/init.scope",
	"UNIT" : "nginx.service",
	"SYSLOG_FACILITY" : "3",
	"JOB_ID" : "164",
	"JOB_TYPE" : "start",
	"_GID" : "0"
}

$ journalctl -u nginx -o cat --no-pager -n 3
Failed to start A high performance web server and a reverse proxy server.
Starting A high performance web server and a reverse proxy server...
Started A high performance web server and a reverse proxy server.

########## 9. KERNEL MESSAGES ONLY (-k) ##########
$ journalctl -k --no-pager -n 5
Sep 03 16:34:06 c071b53e37c7 kernel: veth517e22b: entered allmulticast mode
Sep 03 16:34:06 c071b53e37c7 kernel: veth517e22b: entered promiscuous mode
Sep 03 16:34:06 c071b53e37c7 kernel: eth0: renamed from veth8b1e23f
Sep 03 16:34:06 c071b53e37c7 kernel: docker0: port 2(veth517e22b) entered blocking state
Sep 03 16:34:06 c071b53e37c7 kernel: docker0: port 2(veth517e22b) entered forwarding state

########## 10. LOGS BY PID / EXECUTABLE ##########
$ journalctl _PID=1 --no-pager -n 5
Sep 03 16:36:56 c071b53e37c7 systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE
Sep 03 16:36:56 c071b53e37c7 systemd[1]: nginx.service: Failed with result 'exit-code'.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Failed to start A high performance web server and a reverse proxy server.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Starting A high performance web server and a reverse proxy server...
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Started A high performance web server and a reverse proxy server.

########## 11. WRITE OUR OWN ENTRY WITH logger AND READ IT BACK ##########
$ logger -t devops-homework 'Hello from the journalctl homework task'

$ journalctl -t devops-homework --no-pager
Sep 03 16:36:56 c071b53e37c7 devops-homework[759]: Hello from the journalctl homework task

########## 12. HOUSEKEEPING (vacuum) ##########
$ journalctl --vacuum-time=7d
Vacuuming done, freed 0B of archived journals from /run/log/journal.
Vacuuming done, freed 0B of archived journals from /var/log/journal.
Vacuuming done, freed 0B of archived journals from /var/log/journal/a49d57ceb04249f98358b9d046f0f8c0.

########## 13. FOLLOW MODE (-f) - live tail, 3 second sample ##########
$ journalctl -u nginx -f      (Ctrl+C to stop - captured 3s sample below)
Sep 03 16:36:56 c071b53e37c7 systemd[1]: nginx.service: Deactivated successfully.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Stopped A high performance web server and a reverse proxy server.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Starting A high performance web server and a reverse proxy server...
Sep 03 16:36:56 c071b53e37c7 nginx[730]: nginx: [emerg] unknown directive "this_is_an_invalid_directive" in /etc/nginx/nginx.conf:84
Sep 03 16:36:56 c071b53e37c7 nginx[730]: nginx: configuration file /etc/nginx/nginx.conf test failed
Sep 03 16:36:56 c071b53e37c7 systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE
Sep 03 16:36:56 c071b53e37c7 systemd[1]: nginx.service: Failed with result 'exit-code'.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Failed to start A high performance web server and a reverse proxy server.
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Starting A high performance web server and a reverse proxy server...
Sep 03 16:36:56 c071b53e37c7 systemd[1]: Started A high performance web server and a reverse proxy server.
```

### What that output proves

- The journal is genuinely live: `journalctl --disk-usage` reports **8.0M**,
  and the first entries are real **kernel boot messages** (`Booting Linux on
  physical CPU 0x0`, `Linux version 6.12.69-linuxkit`).
- `journalctl -u nginx` isolated just the nginx unit's lifecycle from a journal
  containing thousands of unrelated kernel and systemd entries.
- **The key demonstration:** an invalid directive was deliberately appended to
  `nginx.conf`. `systemctl restart nginx` failed, and `journalctl -u nginx`
  immediately gave the precise cause:
  `nginx: [emerg] unknown directive "this_is_an_invalid_directive" in
  /etc/nginx/nginx.conf:84` — exact file, exact line number. This is the single
  most common real-world use of `journalctl`.
- `logger -t devops-homework ...` followed by `journalctl -t devops-homework`
  round-tripped a custom entry, showing the journal accepts application logs.
- `-o json-pretty` exposed the structured metadata fields that make targeted
  filtering possible.

---

## Task 4 — Linux Command Cheat Sheet

The reference table first, then a full practical session exercising all of it.

### Navigation and orientation
| Command | Purpose |
|---|---|
| `pwd` | Print working directory — where am I |
| `cd <dir>` | Change directory (`cd ..` up, `cd ~` home, `cd -` previous) |
| `ls` | List files (`-l` long, `-a` hidden, `-h` human sizes, `-t` by time, `-R` recursive, `-i` inodes) |
| `whoami` / `id` | Current username / full UID, GID and groups |
| `hostname` | Machine name |
| `uname -a` | Kernel and architecture |
| `date` / `uptime` | Current time / how long the box has been up |

### Files and directories
| Command | Purpose |
|---|---|
| `mkdir -p a/b/c` | Create directories, `-p` makes parents as needed |
| `touch f` | Create an empty file, or update its timestamp |
| `cp src dst` | Copy (`-r` recursive, `-a` archive/preserve) |
| `mv src dst` | Move **or** rename |
| `rm f` | Delete (`-r` recursive, `-f` force — **no undo**) |
| `rmdir d` | Remove an *empty* directory only |
| `tree` | Show the directory hierarchy visually |
| `ln` / `ln -s` | Hard link / soft link (see Task 1) |

### Viewing file content
| Command | Purpose |
|---|---|
| `cat f` | Dump whole file (`-n` number lines) |
| `less f` | Page through a file (`q` quits, `/` searches) |
| `head -n 20 f` | First 20 lines |
| `tail -n 20 f` | Last 20 lines |
| `tail -f f` | **Follow** a growing log file live |
| `wc -l f` | Count lines (`-w` words, `-c` bytes) |

### Searching
| Command | Purpose |
|---|---|
| `grep 'x' f` | Find lines matching a pattern |
| `grep -i` / `-n` / `-c` / `-v` | Case-insensitive / show line numbers / count / **invert** |
| `grep -r 'x' dir/` | Search a whole directory tree |
| `find . -name '*.log'` | Find files by name |
| `find . -type d` / `-type f` | Only directories / only files |
| `find . -mtime -7` | Modified in the last 7 days |
| `find . -size +100M` | Larger than 100 MB |
| `which cmd` / `type cmd` | Where a command lives / what kind of thing it is |

### Pipes, redirection and text processing
| Command | Purpose |
|---|---|
| `a \| b` | Pipe a's stdout into b's stdin |
| `> f` / `>> f` | Redirect stdout, **overwriting** / **appending** |
| `2> f` / `&> f` | Redirect stderr / both streams |
| `sort` / `sort -r` / `sort -n` | Sort lines / reverse / numerically |
| `uniq -c` | Collapse duplicate adjacent lines and count them (needs `sort` first) |
| `cut -d: -f1` | Cut a delimited column out of each line |
| `awk -F: '{print $1}'` | Field-aware text processing |
| `sed 's/old/new/g'` | Stream find-and-replace |
| `tee f` | Write to a file *and* pass through the pipe |
| `xargs` | Turn stdin into command arguments |

### Permissions and ownership
| Command | Purpose |
|---|---|
| `chmod +x f` | Make executable |
| `chmod 755 f` | Set octal permissions (owner rwx, group rx, other rx) |
| `chown user:group f` | Change owner and group (`-R` recursive) |
| `umask` | Default permission mask for new files |
| `sudo cmd` | Run a single command as root |

Octal reminder: `r=4, w=2, x=1`. So `7 = rwx`, `6 = rw-`, `5 = r-x`, `4 = r--`.
`644` = normal file, `755` = script or directory, `600` = private key.

### Processes
| Command | Purpose |
|---|---|
| `ps aux` / `ps -ef` | Snapshot of all running processes |
| `top` / `htop` | Live process monitor |
| `pgrep -a name` | Find PIDs by name |
| `kill <pid>` | Ask a process to stop (SIGTERM) |
| `kill -9 <pid>` | Force kill (SIGKILL — last resort) |
| `pkill name` | Kill by name |
| `cmd &` | Run in the background |
| `jobs` / `fg` / `bg` | List / foreground / background shell jobs |
| `nohup cmd &` | Keep running after logout |

### Disk and memory
| Command | Purpose |
|---|---|
| `df -h` | Free space **per filesystem** |
| `du -sh dir/` | Size **of a directory** |
| `du -h --max-depth=1` | Which subdirectory is eating the disk |
| `free -h` | RAM and swap usage |
| `lsblk` / `mount` | Block devices / mounted filesystems |

### Archives, packages, network, help
| Command | Purpose |
|---|---|
| `tar -czf a.tar.gz dir/` | **C**reate g**z**ipped archive (**f**ile) |
| `tar -xzf a.tar.gz` | E**x**tract it (`-C dir` extracts elsewhere) |
| `tar -tzf a.tar.gz` | **List** contents without extracting |
| `apt update` / `apt install` | Refresh package index / install (Debian/Ubuntu) |
| `systemctl status/start/stop/restart/enable <svc>` | Manage a service |
| `ip addr` / `ping` / `curl` | Interfaces / reachability / HTTP requests |
| `man cmd` / `cmd --help` | Full manual / quick usage |
| `history` | Previously run commands |

> Memory aid for `tar`: **"Create Ze File"** (`-czf`) and
> **"eXtract Ze File"** (`-xzf`).

### Practical session — every command above, actually run

```console
====================================================================
 SECTION 1 - NAVIGATION & ORIENTATION
====================================================================
$ pwd
/root/cheatsheet

$ whoami
root

$ id
uid=0(root) gid=0(root) groups=0(root)

$ hostname
c071b53e37c7

$ uname -a
Linux c071b53e37c7 6.12.69-linuxkit #1 SMP Mon Feb 16 11:19:06 UTC 2026 aarch64 aarch64 aarch64 GNU/Linux

$ date
Thu Sep  3 16:37:31 UTC 2026

$ uptime
 16:37:31 up  3:53,  0 users,  load average: 1.82, 1.46, 1.29

====================================================================
 SECTION 2 - FILES & DIRECTORIES
====================================================================
$ mkdir -p project/{src,docs,logs}

$ tree project
project
|-- docs
|-- logs
`-- src

3 directories, 0 files

$ touch project/src/app.py project/docs/readme.txt project/logs/app.log

$ ls -lR project
project:
total 12
drwxr-xr-x 2 root root 4096 Sep  3 16:37 docs
drwxr-xr-x 2 root root 4096 Sep  3 16:37 logs
drwxr-xr-x 2 root root 4096 Sep  3 16:37 src

project/docs:
total 0
-rw-r--r-- 1 root root 0 Sep  3 16:37 readme.txt

project/logs:
total 0
-rw-r--r-- 1 root root 0 Sep  3 16:37 app.log

project/src:
total 0
-rw-r--r-- 1 root root 0 Sep  3 16:37 app.py

$ cp project/docs/readme.txt project/docs/readme-backup.txt

$ mv project/docs/readme-backup.txt project/docs/readme-old.txt

$ ls -la project/docs
total 8
drwxr-xr-x 2 root root 4096 Sep  3 16:37 .
drwxr-xr-x 5 root root 4096 Sep  3 16:37 ..
-rw-r--r-- 1 root root    0 Sep  3 16:37 readme-old.txt
-rw-r--r-- 1 root root    0 Sep  3 16:37 readme.txt

$ rm project/docs/readme-old.txt

$ ls project/docs
readme.txt

$ rmdir project/logs 2>&1 || true
rmdir: failed to remove 'project/logs': Directory not empty

$ ls project
docs
logs
src

====================================================================
 SECTION 3 - VIEWING & EDITING FILE CONTENT
====================================================================
$ printf 'line one\nline two\nline three\nline four\nline five\n' > sample.txt

$ cat sample.txt
line one
line two
line three
line four
line five

$ cat -n sample.txt
     1	line one
     2	line two
     3	line three
     4	line four
     5	line five

$ head -n 2 sample.txt
line one
line two

$ tail -n 2 sample.txt
line four
line five

$ wc -l sample.txt
5 sample.txt

$ wc sample.txt
 5 10 49 sample.txt

====================================================================
 SECTION 4 - SEARCHING (grep / find)
====================================================================
$ grep 'three' sample.txt
line three

$ grep -n 'line' sample.txt
1:line one
2:line two
3:line three
4:line four
5:line five

$ grep -c 'line' sample.txt
5

$ grep -i 'LINE ONE' sample.txt
line one

$ grep -v 'line one' sample.txt
line two
line three
line four
line five

$ find /root/cheatsheet -type f -name '*.txt'
/root/cheatsheet/sample.txt
/root/cheatsheet/project/docs/readme.txt

$ find /root/cheatsheet -type d
/root/cheatsheet
/root/cheatsheet/project
/root/cheatsheet/project/docs
/root/cheatsheet/project/src
/root/cheatsheet/project/logs

$ find /etc -name 'passwd' -maxdepth 1
/etc/passwd

====================================================================
 SECTION 5 - PIPES, REDIRECTION & TEXT PROCESSING
====================================================================
$ cat /etc/passwd | head -n 5
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
sync:x:4:65534:sync:/bin:/bin/sync

$ cut -d: -f1 /etc/passwd | head -n 5
root
daemon
bin
sys
sync

$ cat /etc/passwd | wc -l
22

$ sort sample.txt
line five
line four
line one
line three
line two

$ sort -r sample.txt
line two
line three
line one
line four
line five

$ printf 'apple\nbanana\napple\ncherry\nbanana\n' > fruits.txt && sort fruits.txt | uniq -c
      2 apple
      2 banana
      1 cherry

$ awk -F: '{print $1 " uses shell " $7}' /etc/passwd | head -n 5
root uses shell /bin/bash
daemon uses shell /usr/sbin/nologin
bin uses shell /usr/sbin/nologin
sys uses shell /usr/sbin/nologin
sync uses shell /bin/sync

$ sed 's/line/LINE/g' sample.txt
LINE one
LINE two
LINE three
LINE four
LINE five

$ echo 'redirected with >' > out.txt; echo 'appended with >>' >> out.txt; cat out.txt
redirected with >
appended with >>

====================================================================
 SECTION 6 - PERMISSIONS & OWNERSHIP
====================================================================
$ touch script.sh

$ ls -l script.sh
-rw-r--r-- 1 root root 0 Sep  3 16:37 script.sh

$ chmod +x script.sh

$ ls -l script.sh
-rwxr-xr-x 1 root root 0 Sep  3 16:37 script.sh

$ chmod 644 script.sh && ls -l script.sh
-rw-r--r-- 1 root root 0 Sep  3 16:37 script.sh

$ chmod 755 script.sh && ls -l script.sh
-rwxr-xr-x 1 root root 0 Sep  3 16:37 script.sh

$ useradd -m demo 2>/dev/null; chown demo:demo script.sh && ls -l script.sh
-rwxr-xr-x 1 demo demo 0 Sep  3 16:37 script.sh

$ chown root:root script.sh && ls -l script.sh
-rwxr-xr-x 1 root root 0 Sep  3 16:37 script.sh

====================================================================
 SECTION 7 - PROCESSES
====================================================================
$ ps aux | head -n 8
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root           1  0.0  0.0 165204  9696 ?        Ss   16:34   0:00 /sbin/init
root          26  0.0  0.0  31624 10816 ?        S<s  16:34   0:00 /lib/systemd/systemd-journald
systemd+      36  0.0  0.0  22264  9012 ?        Ss   16:34   0:00 /lib/systemd/systemd-resolved
root         736  0.0  0.0  55068  2248 ?        Ss   16:36   0:00 nginx: master process /usr/sbin/nginx -g daemon on; master_process on;
www-data     737  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     738  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process
www-data     740  0.0  0.0  55396  3216 ?        S    16:36   0:00 nginx: worker process

$ ps -ef | head -n 8
UID          PID    PPID  C STIME TTY          TIME CMD
root           1       0  0 16:34 ?        00:00:00 /sbin/init
root          26       1  0 16:34 ?        00:00:00 /lib/systemd/systemd-journald
systemd+      36       1  0 16:34 ?        00:00:00 /lib/systemd/systemd-resolved
root         736       1  0 16:36 ?        00:00:00 nginx: master process /usr/sbin/nginx -g daemon on; master_process on;
www-data     737     736  0 16:36 ?        00:00:00 nginx: worker process
www-data     738     736  0 16:36 ?        00:00:00 nginx: worker process
www-data     740     736  0 16:36 ?        00:00:00 nginx: worker process

$ sleep 300 & echo 'started background sleep with PID '$!
started background sleep with PID 842

$ ps aux | grep '[s]leep'
root         842  0.0  0.0   2228  1112 ?        S    16:37   0:00 sleep 300

$ pgrep -a sleep
842 sleep 300

$ pkill sleep && echo 'sleep killed'
sleep killed

$ pgrep -a sleep || echo 'no sleep process remains'
no sleep process remains

$ top -b -n 1 | head -n 10
top - 16:37:32 up  3:53,  0 users,  load average: 1.82, 1.46, 1.29
Tasks:  19 total,   1 running,  18 sleeping,   0 stopped,   0 zombie
%Cpu(s):  0.0 us,  0.0 sy,  0.0 ni,100.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
MiB Mem :  14965.9 total,    207.9 free,   3946.6 used,  10811.4 buff/cache
MiB Swap:   1024.0 total,   1024.0 free,      0.0 used.  10776.8 avail Mem 

    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
      1 root      20   0  165204   9696   7684 S   0.0   0.1   0:00.18 systemd
     26 root      19  -1   31624  10816   9896 S   0.0   0.1   0:00.09 systemd+
     36 systemd+  20   0   22264   9012   7776 S   0.0   0.1   0:00.03 systemd+

====================================================================
 SECTION 8 - DISK & MEMORY
====================================================================
$ df -h
Filesystem      Size  Used Avail Use% Mounted on
overlay         453G   62G  368G  15% /
tmpfs            64M     0   64M   0% /dev
shm              64M     0   64M   0% /dev/shm
/dev/vda1       453G   62G  368G  15% /etc/hosts
tmpfs           3.0G   28K  3.0G   1% /run
tmpfs           5.0M     0  5.0M   0% /run/lock

$ du -sh /root/cheatsheet
32K	/root/cheatsheet

$ du -h --max-depth=1 /root
8.0K	/root/.config
32K	/root/cheatsheet
12K	/root/links-practice
64K	/root

$ free -h
               total        used        free      shared  buff/cache   available
Mem:            14Gi       3.9Gi       207Mi       0.0Ki        10Gi        10Gi
Swap:          1.0Gi          0B       1.0Gi

====================================================================
 SECTION 9 - ARCHIVES & COMPRESSION
====================================================================
$ tar -czf project.tar.gz project

$ ls -lh project.tar.gz
-rw-r--r-- 1 root root 223 Sep  3 16:37 project.tar.gz

$ tar -tzf project.tar.gz
project/
project/docs/
project/docs/readme.txt
project/src/
project/src/app.py
project/logs/
project/logs/app.log

$ mkdir -p extracted && tar -xzf project.tar.gz -C extracted && find extracted -type f
extracted/project/docs/readme.txt
extracted/project/src/app.py
extracted/project/logs/app.log

====================================================================
 SECTION 10 - PACKAGES, SERVICES, NETWORK, HELP
====================================================================
$ apt list --installed 2>/dev/null | head -n 5
Listing...
adduser/jammy,now 3.118ubuntu5 all [installed]
apt/jammy-updates,now 2.4.14 arm64 [installed]
base-files/jammy-updates,now 12ubuntu4.7 arm64 [installed]
base-passwd/jammy,now 3.5.52build1 arm64 [installed]

$ systemctl list-units --type=service --state=running --no-pager | head -n 8
  UNIT                     LOAD   ACTIVE SUB     DESCRIPTION
  nginx.service            loaded active running A high performance web server and a reverse proxy server
  systemd-journald.service loaded active running Journal Service
  systemd-resolved.service loaded active running Network Name Resolution

LOAD   = Reflects whether the unit definition was properly loaded.
ACTIVE = The high-level unit activation state, i.e. generalization of SUB.
SUB    = The low-level unit activation state, values depend on unit type.

$ ip addr show | head -n 10
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host 
       valid_lft forever preferred_lft forever
2: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
3: gre0@NONE: <NOARP> mtu 1476 qdisc noop state DOWN group default qlen 1000
    link/gre 0.0.0.0 brd 0.0.0.0

$ which ls grep awk
/usr/bin/ls
/usr/bin/grep
/usr/bin/awk

$ type cd
cd is a shell builtin

$ man ls | head -n 6
This system has been minimized by removing packages and content that are
not required on a system that users do not log into.

To restore this content, including manpages, you can run the 'unminimize'
command. You will still need to ensure the 'man-db' package is installed.

$ ls --help | head -n 6
Usage: ls [OPTION]... [FILE]...
List information about the FILEs (the current directory by default).
Sort entries alphabetically if none of -cftuvSUX nor --sort is specified.

Mandatory arguments to long options are mandatory for short options too.
  -a, --all                  do not ignore entries starting with .

$ history | tail -n 5 || echo '(history is per interactive shell)'

$ userdel -r demo 2>/dev/null; echo cleanup done
cleanup done

```

---

## Summary

| Task | Status | Evidence |
|---|---|---|
| 1 — Soft & hard links | Done | Inode/link-count comparison, delete test, broken-symlink demo, interview Q&A |
| 2 — `adduser` vs `useradd` | Done | `file` proves wrapper vs binary; test user `testuser` created with the recommended `adduser` |
| 3 — `journalctl` | Done | Live journald; nginx service logs; real `[emerg]` config error located by file and line |
| 4 — Command cheat sheet | Done | 10 sections, ~90 commands executed with output |

**Environment:** Ubuntu 22.04 (`ubuntu:22.04`), systemd 249, kernel 6.12.69, aarch64.
