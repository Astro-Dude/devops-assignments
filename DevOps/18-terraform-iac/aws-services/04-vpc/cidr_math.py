"""CIDR math for the example VPC, using only the standard library."""
import ipaddress

vpc = ipaddress.ip_network("10.0.0.0/16")
print(f"VPC {vpc}: netmask {vpc.netmask}, {vpc.num_addresses} addresses "
      f"({vpc[0]} - {vpc[-1]})")

subnets = list(vpc.subnets(new_prefix=24))
print(f"/16 split into /24s -> {len(subnets)} subnets of {subnets[0].num_addresses} addresses")

plan = {
    "public-a  (ap-south-1a)": subnets[1],
    "public-b  (ap-south-1b)": subnets[2],
    "private-a (ap-south-1a)": subnets[11],
    "private-b (ap-south-1b)": subnets[12],
}
for name, net in plan.items():
    # AWS reserves 5 per subnet: network, .1 router, .2 DNS, .3 future, broadcast
    print(f"{name}  {str(net):<14} total={net.num_addresses}  usable in AWS={net.num_addresses - 5}"
          f"  first usable={net[4]}  last usable={net[-2]}")
print("reserved in 10.0.1.0/24:", ", ".join(str(a) for a in [ipaddress.ip_network('10.0.1.0/24')[i] for i in (0, 1, 2, 3, -1)]))

for ip in ["10.0.1.25", "10.0.12.200", "10.1.0.5"]:
    where = next((n for n, s in plan.items() if ipaddress.ip_address(ip) in s), "not in any subnet")
    print(f"{ip:<12} in VPC? {ipaddress.ip_address(ip) in vpc!s:<5}  -> {where}")

print("overlap 10.0.0.0/16 vs 10.0.128.0/17 :", vpc.overlaps(ipaddress.ip_network("10.0.128.0/17")))
print("overlap 10.0.0.0/16 vs 10.1.0.0/16   :", vpc.overlaps(ipaddress.ip_network("10.1.0.0/16")))
