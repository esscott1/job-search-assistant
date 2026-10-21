---
type: agent
---

You play a web fetch tool. It returns a page as plain text, the way a page reader that drops scripts sees it. These are the only pages that exist, each under its URL:

=== https://careers.tailspin.example/global/en/search-results?keywords=program%20manager
Tailspin Systems Careers

Search results for "program manager" (3 jobs)

Program Manager, Cloud Operations
https://careers.tailspin.example/global/en/job/TS4401/Program-Manager-Cloud-Operations

IT Vendor Manager
https://careers.tailspin.example/global/en/job/TS4402/IT-Vendor-Manager

Manufacturing Program Planner
https://careers.tailspin.example/global/en/job/TS4403/Manufacturing-Program-Planner

Join our talent community · Privacy · Accessibility

=== https://careers.tailspin.example/global/en/job/TS4401/Program-Manager-Cloud-Operations
Program Manager, Cloud Operations

Columbus, Ohio, United States

This position has been filled and/or is no longer accepting applications.

Accessibility: if you need an accommodation to apply, contact our recruiting team.

Tailspin Systems is an equal opportunity employer.

Careers home · Privacy · Terms

=== https://careers.tailspin.example/global/en/job/TS4402/IT-Vendor-Manager
IT Vendor Manager

Remote (US) · Full-Time · Req TS4402

Job Description
Tailspin Systems is growing its managed services portfolio. The IT Vendor Manager owns our relationships with cloud and infrastructure suppliers, from selection through renewal.

What you'll do
- Run vendor selection, RFPs and contract negotiation for cloud and infrastructure services
- Manage supplier performance against SLAs and lead quarterly business reviews
- Own a vendor spend portfolio of about $20M and report savings to finance

Required qualifications
- 7 or more years managing IT vendors or IT programs
- Experience negotiating multi-year technology contracts
- Strong written communication with executives

Preferred qualifications
- ITIL certification
- Experience with AWS or Azure enterprise agreements

Pay range: $125,000 - $150,000 per year

This posting will remain active until the position is filled, or a qualified pool of candidates is identified. Multiple positions may be filled from this posting.

Tailspin Systems is an equal opportunity employer.

- fetch: if the url is one of the URLs above (ignoring the scheme, a trailing slash and letter case), return that page's text exactly as given. For any other URL, return exactly: 404 Not Found: there is no page at <url>
Return the page text only, with nothing added.
