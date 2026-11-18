import socket
from typing import Dict, Any, List


class DNSAdvisor:
    """Provides DNS configuration standards and diagnostics for devengers.org on Spaceship + Zoho."""

    DOMAIN = "devengers.org"

    @classmethod
    def get_spaceship_records_guide(cls) -> Dict[str, Any]:
        """
        Returns exact DNS records that must be present in Spaceship Advanced DNS
        for Zoho Mail to achieve 100% Gmail and Yahoo deliverability without spam folder diversion.
        """
        return {
            "domain": cls.DOMAIN,
            "instructions": [
                "1. Log in to your Spaceship account dashboard.",
                "2. Go to Domains -> Manage devengers.org -> Advanced DNS.",
                "3. Add the MX records, SPF TXT record, DKIM TXT record, and DMARC TXT record shown below.",
                "4. In Zoho Mail Admin Console -> Domains -> devengers.org, click 'Verify' on SPF and DKIM.",
            ],
            "records": [
                {
                    "type": "MX",
                    "host": "@",
                    "value": "mx.zoho.com (or mx.zoho.in if India region)",
                    "priority": 10,
                    "ttl": "Automatic / 3600",
                    "purpose": "Primary mail exchange route to Zoho",
                },
                {
                    "type": "MX",
                    "host": "@",
                    "value": "mx2.zoho.com (or mx2.zoho.in)",
                    "priority": 20,
                    "ttl": "Automatic / 3600",
                    "purpose": "Secondary mail exchange backup",
                },
                {
                    "type": "MX",
                    "host": "@",
                    "value": "mx3.zoho.com (or mx3.zoho.in)",
                    "priority": 50,
                    "ttl": "Automatic / 3600",
                    "purpose": "Tertiary mail exchange backup",
                },
                {
                    "type": "TXT (SPF)",
                    "host": "@",
                    "value": "v=spf1 include:zoho.com ~all",
                    "purpose": "Crucial: Authorizes Zoho servers to send from @devengers.org without triggering Gmail SPF failure",
                },
                {
                    "type": "TXT (DKIM)",
                    "host": "zoho._domainkey",
                    "value": "(Obtain public key string from Zoho Mail Admin -> Email Configuration -> DKIM)",
                    "purpose": "Crucial: Cryptographically signs emails to guarantee authenticity to Gmail & Outlook",
                },
                {
                    "type": "TXT (DMARC)",
                    "host": "_dmarc",
                    "value": "v=DMARC1; p=none; rua=mailto:support@devengers.org; ruf=mailto:support@devengers.org; sp=none; adkim=r; aspf=r",
                    "purpose": "Enforces 2024+ Gmail & Yahoo bulk sender authentication requirement",
                },
            ],
            "deliverability_tips": [
                "Warm-up: Send to small batches first before reaching full 300/day.",
                "Always keep bounce rates below 2% by cleaning uploaded lists.",
                "Include a valid List-Unsubscribe header and clean plain-text alternative on every email.",
                "Ensure sender 'event@devengers.org' matches the authenticated SMTP user.",
            ],
        }

    @classmethod
    def test_domain_connectivity(cls) -> Dict[str, Any]:
        """Performs basic network diagnostics to verify devengers.org resolves."""
        results = {"domain": cls.DOMAIN, "resolves": False, "ip_addresses": [], "notes": []}
        try:
            addr_info = socket.getaddrinfo(cls.DOMAIN, None)
            ips = list(set(item[4][0] for item in addr_info))
            results["resolves"] = bool(ips)
            results["ip_addresses"] = ips
            results["notes"].append("Domain successfully resolves via DNS.")
        except Exception as e:
            results["notes"].append(f"DNS lookup note: {str(e)}")
        return results
