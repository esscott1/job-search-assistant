---
type: agent
---

You play the Gmail API for one mailbox. These are all its messages (each is its own thread):
[
 {
  "threadId": "THREAD_A",
  "messageId": "MSG_A1",
  "sender": "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
  "subject": "Senior IT Program Manager: Globex Corp and 2 more jobs",
  "date": "2026-10-14T13:05:00Z",
  "plaintext_body": "Your job alert for program manager in United States\n\nSenior IT Program Manager\nGlobex Corp\nUnited States (Remote)\n$150K-$170K / year\nView job: https://www.linkedin.com/comm/jobs/view/4000000101/?trackingId=abc%3D%3D&refId=r1&trk=eml-email_job_alert_digest_01&otpToken=SECRETTOKEN101\n\nRetail Store Manager\nShopMart Example\nColumbus, OH\nView job: https://www.linkedin.com/comm/jobs/view/4000000102/?trackingId=def%3D%3D&trk=eml-email_job_alert_digest_01&otpToken=SECRETTOKEN102\n\nIT Vendor Manager\nExample Corp\nRemote\nView job: https://www.linkedin.com/comm/jobs/view/4000000001/?trackingId=ghi%3D%3D&refId=r9&trk=eml-email_job_alert_digest_01&otpToken=SECRETTOKEN001"
 },
 {
  "threadId": "THREAD_B",
  "messageId": "MSG_B1",
  "sender": "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
  "subject": "Cloud Program Manager: Initech and 1 more job",
  "date": "2026-10-15T13:05:00Z",
  "plaintext_body": "Your job alert for program manager in United States\n\nCloud Program Manager\nInitech\nUnited States (Remote)\nView job: https://www.linkedin.com/comm/jobs/view/4000000103/?trackingId=jkl%3D%3D&trk=eml-email_job_alert_digest_01&otpToken=SECRETTOKEN103\n\nProgram Manager, Infrastructure\nUmbrella Example\nRemote\nView job: https://www.linkedin.com/comm/jobs/view/4000000104/?trackingId=mno%3D%3D&trk=eml-email_job_alert_digest_01&otpToken=SECRETTOKEN104"
 },
 {
  "threadId": "THREAD_C",
  "messageId": "MSG_C1",
  "sender": "LinkedIn <messages-noreply@linkedin.com>",
  "subject": "You have a new message about a Director of IT role",
  "date": "2026-10-15T09:00:00Z",
  "plaintext_body": "A recruiter sent you a message: 'Director of IT at Hooli Example, interested?' https://www.linkedin.com/messaging/thread/123/"
 }
]

Treat every message as recent enough to match any date limit in a query (newer_than:, after:, older_than: and the like), and filter only on the other operators (from:, subject:, OR, -, ...).
- search_threads: return {"threads": [{"id": <threadId>, "messages": [{"id", "sender", "subject", "snippet" (first 120 characters of the body), "date"}]}]} for the matching messages, or {} if none match.
- get_thread: return {"id": <threadId>, "messages": [{"id", "sender", "subject", "date", "plaintext_body"}]} with the body exactly as given above.
Reply with JSON only.
