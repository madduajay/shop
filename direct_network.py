"""Thread3-only loopback resolver; no system DNS or trust changes."""
import ipaddress
from personal_agent_protocol.reactor import resolve_addresses
from personal_agent_protocol.errors import DiscoveryError
DOMAINS=frozenset({'atlas.localhost','jacket.localhost'})
async def local_addresses(host):
    if host not in DOMAINS:
        raise DiscoveryError('unsafe_url','Host outside Thread3 fixture')
    addresses=await resolve_addresses(host)
    if not addresses or any(not ipaddress.ip_address(a).is_loopback for a in addresses):
        raise DiscoveryError('unsafe_address','Host must resolve natively to loopback')
    return addresses
