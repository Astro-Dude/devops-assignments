# Ubuntu 22.04 image with systemd enabled so that `journalctl` (Task 3)
# can be practised with a real systemd-journald instance.
#
# Build : docker build -t linux-practice 01-linux-fundamentals
# Run   : docker run -d --name linux-practice --privileged --cgroupns=host \
#           -v /sys/fs/cgroup:/sys/fs/cgroup:rw linux-practice
# Enter : docker exec -it linux-practice bash
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV container=docker

RUN apt-get update && apt-get install -y --no-install-recommends \
        systemd systemd-sysv \
        adduser passwd \
        nginx \
        vim less tree curl iproute2 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Remove units that are meaningless inside a container
RUN find /etc/systemd/system /lib/systemd/system \
        -path '*.wants/*' \
        \( -name '*udev*' -o -name '*getty*' -o -name '*mount*' \) \
        -exec rm -f {} + 2>/dev/null || true

STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
