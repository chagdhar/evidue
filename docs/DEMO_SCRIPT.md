# YC demo script

Target narration: approximately 100 seconds.

1. Open `/demo`.

   “Outcome-priced AI vendors send an invoice, but the customer still has to
   prove which outcomes deserve payment. This is Evidue, using synthetic,
   deterministic operational data for Acme Commerce and Nova Support AI.”

2. Point to the submitted invoice, rules, and evidence sources.

   “Nova submitted 10,000 resolved outcomes for $15,000. Before any money is
   calculated, Evidue makes the contract executable: seven-day recontacts,
   24-hour human corrections, two-hour downstream completion, duplicate
   attribution, account matching, billing period, and minimum evidence. The
   evidence comes from customer-controlled support, payment, billing, and
   product systems.”

3. Click **Run reconciliation**.

   “This invokes the backend reconciliation engine. It evaluates every stored
   claim and persists the contract rule and evidence behind each result.”

4. Point to the result.

   “The defensible payable amount is $12,480. Evidue recommends deducting $2,520
   across 1,680 disputed outcomes. Every dollar comes from deterministic rules,
   not a model’s guess.”

5. Filter status to **Disputed**, enter `OUT-004821`, and open it.

   “Here is a vendor-claimed resolution. The AI initiated a refund, the payment
   processor rejected it, the contractual two-hour window expired, and a human
   completed it later. The $1.50 line is therefore payable at zero, with the
   clause, rule, source records, timestamps, and engine version attached.”

6. Close the detail and point to the export buttons.

   “Finance can download the disputed lines, complete evidence package, and
   reconciliation summary. One invoice enters; one defensible payable amount
   leaves.”
