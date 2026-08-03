# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ |
| < 0.1   | ❌ |

## Reporting a Vulnerability

**Do not open a public issue.** Email security@sahajtech.com with:

- Detailed description of the vulnerability
- Steps to reproduce
- Affected versions
- Suggested fix (if any)

We aim to respond within 48 hours and patch within 7 days.

## Scope

Fixate handles user-uploaded documents (PDF, EPUB) and reading behavior data. Security-sensitive areas:

- **Document upload pipeline** — file type validation, path traversal, zip bombs (for EPUB)
- **OCR backend** — Tesseract CLI escaping, Textract credentials
- **WebSocket layer** — room authentication, message injection
- **Desktop Tauri shell** — backend process isolation, IPC boundaries
- **Client-side storage** — localStorage XSS, session hijacking

## Disclosure Policy

We follow coordinated disclosure. After a patch is released, we'll publish a security advisory crediting the reporter (unless anonymity is requested).
