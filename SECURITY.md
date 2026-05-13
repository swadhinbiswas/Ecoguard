# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.3.x   | :white_check_mark: |
| 0.2.x   | :x:                |
| < 0.2   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue in Eco-Guard, please report it responsibly.

**Do not open a public GitHub issue.** Instead, email:

**security@ecoguard.dev**

You will receive an acknowledgment within 48 hours. We will keep you updated on the progress toward a fix and public disclosure.

### What to Include

- A detailed description of the vulnerability
- Steps to reproduce the issue
- Affected versions
- Any potential mitigations you've identified

### Disclosure Timeline

1. Report received → Acknowledgment within 48 hours
2. Investigation → Confirmation within 5 business days
3. Fix development → Patch prepared within 14 days
4. Coordinated disclosure → Public advisory published after fix is released

### Scope

The following are considered in-scope for our security program:

- Authentication bypass or privilege escalation
- Data exposure (API keys, user data, model outputs)
- Remote code execution
- Server-side request forgery (SSRF)
- Injection attacks (prompt injection, SQL injection)
- Denial of service vulnerabilities
- Cryptographic weaknesses
- Cross-site scripting (XSS) in the dashboard

### Out of Scope

- Issues in third-party dependencies (report to the dependency maintainer)
- Theoretical vulnerabilities without a working proof of concept
- Missing security headers that don't lead to exploitable conditions
- Social engineering attacks
- Physical security

## Security Best Practices

When deploying Eco-Guard in production, we recommend:

1. **Always set `ENVIRONMENT=production`** — Enables HSTS, disables API docs, validates configuration
2. **Use a unique `JWT_SECRET`** of at least 32 random characters
3. **Set strong `ADMIN_PASSWORD`** — Minimum 16 characters recommended
4. **Restrict `CORS_ORIGINS`** to your specific domain
5. **Deploy behind a reverse proxy** (nginx, Caddy) with TLS termination
6. **Enable Redis** for shared state in multi-worker deployments
7. **Configure `IP_ALLOWLIST`** for administrative endpoints if applicable
8. **Enable `GUARDRAILS_ENABLED=true`** for prompt injection and PII protection
9. **Regularly rotate API keys** — Keys can be revoked via the API or dashboard
10. **Enable audit logging** — Monitor the audit trail for suspicious activity

## Vulnerability Hall of Fame

We appreciate the security community's contributions. Responsible disclosure reporters will be acknowledged here (with permission).
