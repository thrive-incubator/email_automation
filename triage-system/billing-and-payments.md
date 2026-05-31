# Knowledge file: billing-and-payments

Reference facts for replying to candidates and their finance/AP staff about invoices, W9s, tax-exempt forms, and payment methods. Used by the "Cohort billing / invoice / W9 / payment" rule.

> ⚠️ Money is high-stakes. The default for billing replies is **acknowledge + route to billing@attunify.co**, NOT to resolve the money question ourselves. Never fabricate an invoice number, amount, W9, EIN, or payment confirmation. When in doubt, hand to a human / billing. ⚠️ marks things Shai should confirm.

---

## Who handles billing

- **Billing contact / system of record:** **billing@attunify.co**. This is the established escalation path for resending invoices, W9, EIN, tax-exempt forms, AP routing, and payment-method questions. **CC billing@attunify.co** on billing replies.
- **Operations escalation for complex cases** (split payments, unusual AP requirements): **Christine Vida, Head of Operations — christine@attunify.co.** ⚠️ Confirm whether Christine should be CC'd by default or only on complex cases (current assumption: complex cases only).
- **Bookkeeper/accountant:** Scott Brooks (srbrooks.com) — internal only; never expose to candidates.

## Billing entity & invoicing

- Invoices are issued via **Stripe**, from **"Attunify by Thrive Center"** (legal entity **Attunify, Inc.**). Subject line pattern seen: *"Invoice for IECMH Consultation Certificate from Attunify By Thrive Center."*
- The billing-details intake is collected via a **Google Form** ("TIME SENSITIVE: Billing Details for Georgetown IECMHC Program"). Candidates complete the form, then an invoice is sent.
- ⚠️ We don't have the W9, EIN, or the billing-form URL captured here. **Do not paste a W9, EIN number, or form link** — say billing will send it. Shai: if you want auto-replies to include the billing-form link or the W9 as an attachment, add them here and tell me.

## Payment methods (verbatim-grounded)

- **Preferred:** **ACH and wire.** ("ACH and wire are preferred.")
- **Credit card:** available — candidate uses their **unique payment link and selects the card option.**
- **Installment plan:** **4 equal payments via credit card.**
- **Checks / direct deposit forms / AP packets:** some orgs require a signed W9 + a direct-deposit form and pay via their AP department. Route all of this to billing@attunify.co.
- ⚠️ Confirm whether checks are accepted. One org wrote "we require a direct deposit versus sending a check" (that's THEIR policy). We haven't stated our own check policy — don't assert we do or don't take checks; let billing handle.

## Pricing (cross-reference enrollment-and-pricing.md)

- June 2026 **founding cohort: $2,500.** Later cohorts (e.g. October, ⚠️ February): **$3,000.** 4-payment CC installment available.
- ⚠️ Always tie price to a named cohort. Don't quote a number without the cohort.

## Tax-exempt / nonprofit orgs

- Many enrollees are nonprofits / public agencies (Head Start, school districts, ESCs, state/tribal agencies) and will submit **tax-exempt forms** and need a **W9**. Route these to billing@attunify.co — they handle the exempt paperwork and issue a compliant invoice.

---

## Worked examples (question → model reply)

**Q1 — "I can't find the invoice. Can you resend it?"**
> Hi [Name] — sorry that's been hard to track down. I've asked our billing team (billing@attunify.co, CC'd here) to resend your invoice today. If it's easier to send it straight to your AP office, just reply with that address and they'll route it there.

**Q2 — "I need a W9." / "I received the invoice but not the W9."**
> Hi [Name] — happy to help. Our billing team (CC'd, billing@attunify.co) will send the signed W9 right over so you can submit the invoice for payment. Let me know if your AP team needs anything else alongside it.

**Q3 — "We want to pay by credit card for [enrollee]. What's the best way?"**
> Hi [Name] — you can pay by card using the unique payment link on the invoice: just choose the card option at checkout. If you'd prefer to split it, there's a 4-payment installment plan on card too. Our billing team (CC'd) can resend the link or set up the installments — just say the word.

**Q4 — "Do I pay via wire, Attunify, or ACH transfer?"**
> Hi [Name] — great question. ACH and wire are both preferred and go to Attunify (our billing entity, "Attunify by Thrive Center"). Card is also fine via the link on your invoice. I've CC'd billing@attunify.co so they can send the exact ACH/wire details for your finance team.

**Q5 — "We need a W9 and a direct-deposit form for our AP records; we pay by direct deposit, not check."**
> Hi [Name] — understood, that's no problem. I've looped in our billing team (billing@attunify.co, CC'd) to send a signed W9 and complete your direct-deposit form so your AP department has everything on file. They'll follow up shortly.

**Q6 — "I'm waiting on HR to approve payment. Is it OK to pay Monday?"**
> Hi [Name] — totally fine, thanks for the heads-up. Your spot is secure while approval goes through. When you're ready, our billing team (CC'd) can take payment by ACH, wire, or card. Just reply here if anything comes up with HR.

**Q7 — "Have you received our payment?" (payment-status check)**
> Hi [Name] — let me confirm that for you. I've asked our billing team (CC'd, billing@attunify.co) to check the status and reply with where things stand. *(Do NOT assert payment was or wasn't received — billing confirms from Stripe.)*

**Q8 — "I completed the billing form but the invoice may have gone to our AP department — I need a copy."**
> Hi [Name] — thanks for completing the form. I've asked billing (CC'd) to send you a copy of the invoice directly, and to confirm whether one already went to your AP office so you're not double-billed.

---

## Edge cases

- **Split payment / multiple enrollees on one invoice:** acknowledge, route to billing AND note Christine (christine@attunify.co) for complex splits. Don't try to math out a split in the reply.
- **Purchase order required first:** acknowledge, ask them to send the PO requirements to billing, let billing issue against the PO.
- **"Is it too late and how do I pay?" from a non-enrolled lead:** that's primarily an enrollment question — the enrollee rule (priority 7) should handle the enrollment/pricing, and only the payment-mechanics part routes to billing.
- **Refund / cancellation request:** ⚠️ no refund policy is documented in the inbox. Do NOT state a refund policy. Flag to a human / route to billing+Christine and say someone will follow up.

## Newly found recurring asks (v2 — from full Nov 2025–May 2026 scan)

**Scholarships / group rates / discounted seats.** ⚠️ Recurs across the inbox ("scholarships", "Group rates", "Discounted seats"). No discount/scholarship policy is documented. **Never promise, deny, or quote a discount.** Acknowledge and route: "Let me check what's available for your situation and have the team follow up." Hand to billing@attunify.co (and Christine for group/team pricing). **Shai: confirm whether scholarships and group rates exist and at what thresholds.**

**Payment-timing questions are very common.** Examples seen verbatim: "Would it be ok if we sent the invoice by May 15th?"; "I am waiting on HR to approve payment — is it ok to pay Monday?"; "I have put in a request for payment with my company and it needs to be approved before I start — what is the timeline?"; "Another question — when can I expect an invoice?". Standard response: reassure the seat is held while approval/PO processes, and let billing confirm exact timing. Don't impose a hard deadline we haven't set.

**Employer/sponsor-pays.** Verbatim: "I just got my participation approved by my employer, and they will pay the $2500 fee for me. How do I go about processing that payment? Or is it not due yet?" → Affirm warmly, route to billing to invoice the employer directly or accept a PO. Confirm the $2,500 figure only for the June founding cohort (later cohorts $3,000).

**"Do I need my program director to fill out the form for me?"** ⚠️ Process detail not fully documented. Acknowledge and say either they or their director can complete the billing/enrollment form; if their org requires the director, that's fine — billing can work with whoever holds the budget. Don't over-specify.

## Hard "do nots"

- ❌ Never promise, deny, or quote a scholarship, group rate, or discount.
- ❌ Never state an invoice was paid / received unless billing confirmed it.
- ❌ Never paste a W9, EIN, or bank/ACH/wire details — billing sends those.
- ❌ Never quote a refund or cancellation policy.
- ❌ Never quote a price without naming the cohort.
- ❌ Don't promise a date the invoice/W9 "will" arrive — say billing will send it promptly.
