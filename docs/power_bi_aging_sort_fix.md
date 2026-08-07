# Power BI AR Aging Sort Fix

Power BI can raise a circular-dependency error when `fact_invoice[aging_bucket]` is sorted by a DAX calculated column that itself depends on `fact_invoice[aging_bucket]`.

Use the dedicated imported dimension instead:

1. Import `powerbi/dim_aging_bucket.csv`.
2. Create an active single-direction relationship:
   `dim_aging_bucket[aging_bucket]` 1 → * `fact_invoice[aging_bucket]`.
3. In Data view select `dim_aging_bucket[aging_bucket]`, then choose **Column tools > Sort by column > aging_bucket_sort**.
4. In AR Aging visuals use `dim_aging_bucket[aging_bucket]` on the axis, not `fact_invoice[aging_bucket]`.
5. Exclude `CLOSED_OR_CREDIT` from the visual if the chart is intended to show only positive receivables aging.

Expected order:

- CURRENT
- 1-30
- 31-60
- 61-90
- 90+
- CLOSED_OR_CREDIT
