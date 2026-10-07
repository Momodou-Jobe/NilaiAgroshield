# AgroShield AI — Presentation Kit

Speaker notes, pitch, closing points, and readiness prep for presenting
AgroShield AI. Everything here reflects the app as actually built.

---

## Elevator pitch (30 seconds)

AgroShield AI is an intelligent farming companion for smallholder farmers. A
farmer describes their crop and symptoms, optionally uploads a photo, and our AI
agricultural assistant streams back a clear diagnosis with organic and chemical
treatment options and prevention tips — in plain language, in English or Bahasa
Melayu. It turns days of guesswork and waiting for an extension officer into
minutes of actionable advice, right from the field.

---

## Final slide title options

- "AgroShield AI — An agronomist in every farmer's pocket."
- "From guesswork to a saved harvest — in minutes, in their language."
- "AgroShield AI: intelligent crop diagnosis for every smallholder farmer."

---

## Closing points (how to end strong)

1. **Restate the problem and the human impact.** Smallholder farmers face crop
   disease with guesswork, delay, and a language barrier — a wrong guess can
   cost an entire harvest. AgroShield turns days of uncertainty into minutes of
   clear, actionable advice.
2. **Value in one sentence.** AgroShield AI diagnoses crop disease from a
   farmer's own description and photo, and delivers tailored treatment advice in
   plain language, in English or Bahasa Melayu.
3. **Why AI, not a form or search.** It reasons over free-text symptoms,
   weather, crop stage, location, and a photo together to generate new,
   personalised advice. A form only collects; search only retrieves. This is a
   reasoning-and-generation problem — what only AI solves.
4. **Credible engineering, not just a demo.** Serverless AWS (S3, Lambda with
   streaming Function URLs, Amazon Bedrock / Claude Haiku 4.5, least-privilege
   IAM); infrastructure as code with AWS SAM; one-push CI/CD via GitHub Actions;
   guardrails for photo and location validation; live bilingual translation.
5. **Honesty builds trust.** AgroShield is decision support, not a lab-certified
   diagnosis. It always advises confirming with a local agricultural extension
   officer before applying chemicals. It empowers farmers and extension
   services — it does not replace them.
6. **Forward look.** It is live, deployable, and extensible — a foundation, not
   a finished experiment.
7. **Final line.** "AgroShield AI puts an agronomist in every farmer's pocket,
   in their own language — turning a likely crop loss into a saved harvest."

---

## Speaker notes (one slide's worth)

> Open with the farmer, not the tech. "Meet Rahman, a chilli farmer in Nilai.
> Three weeks before harvest he spots dark, sunken lesions spreading after the
> rains. He doesn't know if it's fungus, pests, or nutrients — and the nearest
> extension officer is days away."
>
> Then the turn: "Before, he guessed, sprayed the wrong thing, and lost part of
> his crop. With AgroShield, he opens the app, switches to Bahasa Melayu,
> describes what he sees, uploads a photo, and in minutes gets a clear diagnosis
> and a treatment plan he understands."
>
> Then the substance: "Behind that simplicity is real engineering — a
> serverless AWS architecture, a vision-capable AI model, and validation
> guardrails that reject bad photos and impossible locations."
>
> Close on trust: "It's decision support, not a replacement for experts — so it
> always points farmers back to their local extension officer. AgroShield puts
> an agronomist in every farmer's pocket, in their own language."

---

## Readiness prep

### Demo, de-risked
- Open the deployed S3 URL beforehand and confirm it loads.
- Remember the S3 website endpoint is HTTP only — do not let the browser force
  HTTPS on stage.
- Pre-test one clean run (real crop, symptoms, weather, location, good photo)
  so you know it streams a result.
- Have a backup: a screen recording or screenshots in case venue Wi-Fi or
  Bedrock throttling interrupts the live demo.

### Know the stack cold
- One AI model: Claude Haiku 4.5 via Amazon Bedrock — chosen for vision support,
  speed, and cost efficiency.
- Stack: S3 (static site) + Lambda (Flask via Lambda Web Adapter, streaming
  Function URL) + Amazon Bedrock + IAM; deployed by AWS SAM + GitHub Actions to
  ap-southeast-1.
- Each diagnosis = up to 3 model calls: location validation, photo validation,
  and the diagnosis stream. Language toggle triggers additional translate calls.

### Match the message to the audience
- Technical panel: architecture, streaming, guardrails, scaling limits.
- Business/impact panel: the persona, time-and-cost savings, language
  accessibility, reach.

### Timing
- Rehearse to fit the slot with the demo included.
- Keep a 30-second version of the pitch ready in case time is cut.

---

## Anticipated Q&A

**Why AI over a decision tree or FAQ?**
Free-text symptoms, multimodal photo input, contextual reasoning over many
signals, generated (not retrieved) advice, and live bilingual output. A decision
tree would need an unmanageable branch for every crop x symptom x weather x
region and still could not read a photo or write fluent advice.

**What breaks at 100,000 users?**
Bedrock throughput quotas (TPM/RPM) break first — each diagnosis is 3+ large
calls, so the token limit is hit fast and users get throttling errors. Next,
Lambda concurrency (1,000 default) — long streaming invocations hold slots.
Then cost, because the Function URL is public with no rate limiting. S3 frontend
does not break. Fixes: add auth/rate limiting (API Gateway/WAF), request Bedrock
and Lambda quota increases, reduce calls per diagnosis, cap/compress images, and
add retry-with-backoff on throttling.

**Is it production-ready / secure?**
Be upfront: the Function URL is currently public with no auth or rate limiting,
and the S3 site is HTTP only. Hardening is the clear next step — API Gateway
throttling or WAF for the backend, and CloudFront for HTTPS and caching on the
frontend.

**How accurate is it?**
Decision support, not a certified diagnosis. Accuracy improves with a clear
photo. It always advises confirming with a local extension officer before
applying chemicals.

**Data privacy?**
Stateless — there is no database and nothing is stored, so farmer inputs and
photos are not retained.

---

## Next steps (roadmap slide)

- Add authentication and rate limiting to the public endpoint.
- Put CloudFront in front of S3 for HTTPS, caching, and a friendly domain.
- Reduce model calls per diagnosis and add throttling-aware retries.
- Client-side image compression and size caps.
- Native-speaker review of Bahasa Melayu copy; add more languages.
- Optional: usage analytics and a feedback loop to improve advice quality.
