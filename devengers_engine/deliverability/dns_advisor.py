import socket
from typing import Dict, Any, List


class DNSAdvisor:
    """Provides DNS configuration standards and diagnostics for devengers.org on Spaceship + Brevo (300/day) + Zoho Mail."""

    DOMAIN = "devengers.org"

    @classmethod
    def get_spaceship_records_guide(cls) -> Dict[str, Any]:
        """
        Returns exact DNS records that must be present in Spaceship Advanced DNS:
        - Incoming Mail & Inboxes: Zoho Mail (Free Tier)
        - Outgoing 300/day Automation: Brevo SMTP Relay (Free Forever Tier)
        """
        return {
            "domain": cls.DOMAIN,
            "architecture": "Incoming Webmail hosted on Zoho Mail + Outgoing 300/day automated dispatch via Brevo SMTP",
            "instructions": [
                "1. Log in to your Spaceship account dashboard.",
                "2. Go to Domains -> Manage devengers.org -> Advanced DNS.",
                "3. Ensure the Zoho MX records are added so you receive replies at support@devengers.org.",
                "4. Add the combined SPF record below so Gmail recognizes both Brevo and Zoho.",
                "5. In Brevo (Senders & Domains), copy the DKIM record and add it to Spaceship.",
                "6. Add the DMARC TXT record for 100% Gmail and Yahoo deliverability compliance.",
            ],
            "records": [
                {
                    "type": "MX",
                    "host": "@",
                    "value": "mx.zoho.com (or mx.zoho.in if India region)",
                    "priority": 10,
                    "purpose": "Primary incoming route: Delivers replies to support@devengers.org into Zoho Webmail",
                },
                {
                    "type": "MX",
                    "host": "@",
                    "value": "mx2.zoho.com (or mx2.zoho.in)",
                    "priority": 20,
                    "purpose": "Secondary Zoho MX backup",
                },
                {
                    "type": "MX",
                    "host": "@",
                    "value": "mx3.zoho.com (or mx3.zoho.in)",
                    "priority": 50,
                    "purpose": "Tertiary Zoho MX backup",
                },
                {
                    "type": "TXT (SPF)",
                    "host": "@",
                    "value": "v=spf1 include:spf.brevo.com include:zoho.com ~all",
                    "purpose": "Crucial: Authorizes both Brevo (300/day outgoing) & Zoho without triggering Gmail SPF failure",
                },
                {
                    "type": "TXT (DKIM - Brevo)",
                    "host": "mail._domainkey",
                    "value": "(Obtain DKIM TXT value from Brevo Dashboard -> Senders & Domains -> Authenticate Domain)",
                    "purpose": "Crucial: Cryptographically signs outgoing emails from Brevo to ensure direct Inbox delivery",
                },
                {
                    "type": "TXT (DKIM - Zoho)",
                    "host": "zoho._domainkey",
                    "value": "(Optional: DKIM key from Zoho Mail Admin for direct webmail replies)",
                    "purpose": "Authenticates replies sent directly through Zoho Webmail",
                },
                {
                    "type": "TXT (DMARC)",
                    "host": "_dmarc",
                    "value": "v=DMARC1; p=none; rua=mailto:support@devengers.org; sp=none; adkim=r; aspf=r",
                    "purpose": "Enforces 2024+ Gmail & Yahoo bulk sender authentication requirement",
                },
            ],
            "deliverability_tips": [
                "Verify devengers.org inside Brevo (Senders & IP -> Domains) to achieve 100% inbox placement.",
                "Always keep bounce rates below 2% by cleaning uploaded member lists.",
                "The engine automatically attaches List-Unsubscribe and clean RFC plain-text alternatives.",
                "Replies sent to support@devengers.org land directly in your free Zoho webmail inbox.",
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
