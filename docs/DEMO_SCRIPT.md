# YC demo script

Target narration: approximately 100 seconds.

1. Run `./scripts/demo-reset.sh` and open `/demo`.

   “Outcome-priced AI vendors send an invoice, but the customer still has to
   prove which outcomes deserve payment. This is Evidue, using synthetic,
   deterministic operational data for Acme Commerce and Nova Support AI.”

2. Point to the submitted invoice, workflow, compact contract terms, and
   evidence readiness.

   “Nova submitted 10,000 resolved outcomes for $15,000. Before any money is
   calculated, Evidue makes the contract executable: seven-day recontacts,
   24-hour human corrections, two-hour downstream completion, duplicate
   attribution, account matching, billing period, and minimum evidence. The
   evidence comes from the listed support, payment, billing, and product
   systems. No connection or record count is invented.”

3. Click **Run reconciliation**.

   “This invokes the backend reconciliation engine. It evaluates every stored
   claim and persists the contract rule and evidence behind each result.”

4. Point to the payment recommendation and subtraction bridge.

   “The defensible payable amount is $12,480. Evidue recommends deducting $2,520
   across 1,680 disputed outcomes. The bridge reproduces that decision category
   by category. Every dollar comes from deterministic rules, not a model’s
   guess.”

5. Select **Failed downstream actions**, expand **Advanced filters**, enter
   `OUT-004821`, and open the highlighted **Demo example**.

   “Here is a vendor-claimed resolution. The AI initiated a refund, the payment
   processor rejected it, the contractual two-hour window expired, and a human
   completed it later. The $1.50 line is therefore payable at zero, with the
   vendor claim, contract obligation, determination, source records, timestamps,
   and engine version shown together.”

6. Close the inspector and point to **Prepare vendor dispute**, then click
   **Download dispute package**.

   “Finance receives a complete evidence package and can separately download
   disputed-line CSV or JSON summaries. One invoice enters; one defensible
   payable amount leaves.”

## Focused follow-up cases

Open `/demo/lab` and use **Synthetic data set** to switch cases. Each switch
returns the product to the unreconciled state so the audience sees the decision
being recomputed. Do not use this route in the submitted YC recording.

- **Contradictory evidence**: run the two-line fixture and point out that
  success and failure records for the same claim produce `needs_review`.
  Submitted is $3.00, confirmed payable is $1.50, recommended deduction is
  $0.00, and $1.50 is held for review.
- **Failed action, valid follow-up**: run the two-line fixture and show that the
  failed first outcome is R3 while the later valid outcome remains payable. An
  invalid claim cannot become a duplicate winner.
- **Duplicate attribution window**: run the three-line fixture and show that
  the earliest otherwise-payable claim wins; the later two claims inside 24
  hours are disputed under R4.

Return to `/demo` for the headline close. The lab descriptions identify the
case but never preview a financial result; all money appears only after the
backend reconciliation runs.
