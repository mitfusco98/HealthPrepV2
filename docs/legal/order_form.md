# HealthPrep Order Form

**Version:** 1.1  
**Last Updated:** {{EFFECTIVE_DATE}}  
**Document ID:** ORD-2024-001

---

This Order Form is incorporated into and made part of the applicable Service Agreement ("Agreement") between **Fusco Digital Solutions LLC** ("Company") and the subscribing Provider or Organization identified below. All payment terms, fees, and schedules referenced in the Agreement are defined herein.

---

## 1. Customer Information

| Field | Value |
|-------|-------|
| **Customer Name** | {{CUSTOMER_NAME}} |
| **Customer Type** | [ ] Standalone Provider  [ ] Organization (Multi-Provider) |
| **Contact Name** | {{CONTACT_NAME}} |
| **Contact Email** | {{CONTACT_EMAIL}} |
| **Contact Phone** | {{CONTACT_PHONE}} |
| **Billing Address** | {{BILLING_ADDRESS}} |
| **NPI Number(s)** | {{NPI_NUMBER}} |

### For Multi-Provider Agreements Only

| Field | Value |
|-------|-------|
| **Number of Covered Providers** | {{PROVIDER_COUNT}} |
| **Provider List Attached** | [ ] Yes |

---

## 2. Subscription Term

| Field | Value |
|-------|-------|
| **Effective Date** | {{EFFECTIVE_DATE}} |
| **Term Length** | 12 months |
| **Term End Date** | {{TERM_END_DATE}} |
| **Automatic Renewal** | No |

---

## 3. Subscription Pricing

### Per-Provider Fee

| Description | Amount |
|-------------|--------|
| **Monthly Rate per Provider** | {{MONTHLY_RATE_PER_PROVIDER}} |

### Total Annual Commitment

| Description | Calculation | Amount |
|-------------|-------------|--------|
| Number of Providers | | {{PROVIDER_COUNT}} |
| Monthly Rate per Provider | | {{MONTHLY_RATE_PER_PROVIDER}} |
| **Monthly Subscription Total** | {{PROVIDER_COUNT}} × {{MONTHLY_RATE_PER_PROVIDER}} | **{{MONTHLY_TOTAL}}** |
| **Annual Commitment (12 months)** | {{MONTHLY_TOTAL}} × 12 | **{{ANNUAL_COMMITMENT}}** |

### One-Time Fees (if applicable)

| Description | Amount |
|-------------|--------|
| Implementation/Setup Fee | {{SETUP_FEE}} |
| Training Fee | {{TRAINING_FEE}} |
| **Total One-Time Fees** | **{{TOTAL_ONETIME_FEES}}** |

---

## 4. Payment Schedule

### Selected Payment Frequency

Check one payment option:

- [ ] **Monthly Payments** – 12 equal installments
- [ ] **Quarterly Payments** – 4 equal installments
- [ ] **Semi-Annual Payments** – 2 equal installments
- [ ] **Annual Prepayment** – 1 payment at contract signing

### Payment Amount per Period

| Payment Frequency | Installment Amount | Number of Payments |
|-------------------|--------------------|--------------------|
| Monthly | {{MONTHLY_TOTAL}} | 12 |
| Quarterly | {{QUARTERLY_AMOUNT}} | 4 |
| Semi-Annual | {{SEMIANNUAL_AMOUNT}} | 2 |
| Annual | {{ANNUAL_COMMITMENT}} | 1 |

### Payment Timeline

The following table shows the payment schedule for the selected payment frequency. All payments are due on or before the due date listed.

#### Monthly Payment Schedule (if selected)

| Payment # | Period Covered | Invoice Date | Due Date | Amount |
|-----------|----------------|--------------|----------|--------|
| 1 | Month 1 | {{EFFECTIVE_DATE}} | {{PAYMENT_1_DUE}} | {{MONTHLY_TOTAL}} |
| 2 | Month 2 | {{MONTH_2_INVOICE}} | {{PAYMENT_2_DUE}} | {{MONTHLY_TOTAL}} |
| 3 | Month 3 | {{MONTH_3_INVOICE}} | {{PAYMENT_3_DUE}} | {{MONTHLY_TOTAL}} |
| 4 | Month 4 | {{MONTH_4_INVOICE}} | {{PAYMENT_4_DUE}} | {{MONTHLY_TOTAL}} |
| 5 | Month 5 | {{MONTH_5_INVOICE}} | {{PAYMENT_5_DUE}} | {{MONTHLY_TOTAL}} |
| 6 | Month 6 | {{MONTH_6_INVOICE}} | {{PAYMENT_6_DUE}} | {{MONTHLY_TOTAL}} |
| 7 | Month 7 | {{MONTH_7_INVOICE}} | {{PAYMENT_7_DUE}} | {{MONTHLY_TOTAL}} |
| 8 | Month 8 | {{MONTH_8_INVOICE}} | {{PAYMENT_8_DUE}} | {{MONTHLY_TOTAL}} |
| 9 | Month 9 | {{MONTH_9_INVOICE}} | {{PAYMENT_9_DUE}} | {{MONTHLY_TOTAL}} |
| 10 | Month 10 | {{MONTH_10_INVOICE}} | {{PAYMENT_10_DUE}} | {{MONTHLY_TOTAL}} |
| 11 | Month 11 | {{MONTH_11_INVOICE}} | {{PAYMENT_11_DUE}} | {{MONTHLY_TOTAL}} |
| 12 | Month 12 | {{MONTH_12_INVOICE}} | {{PAYMENT_12_DUE}} | {{MONTHLY_TOTAL}} |
| | | | **Total:** | **{{ANNUAL_COMMITMENT}}** |

#### Quarterly Payment Schedule (if selected)

| Payment # | Period Covered | Invoice Date | Due Date | Amount |
|-----------|----------------|--------------|----------|--------|
| 1 | Months 1-3 | {{EFFECTIVE_DATE}} | {{Q1_DUE}} | {{QUARTERLY_AMOUNT}} |
| 2 | Months 4-6 | {{Q2_INVOICE}} | {{Q2_DUE}} | {{QUARTERLY_AMOUNT}} |
| 3 | Months 7-9 | {{Q3_INVOICE}} | {{Q3_DUE}} | {{QUARTERLY_AMOUNT}} |
| 4 | Months 10-12 | {{Q4_INVOICE}} | {{Q4_DUE}} | {{QUARTERLY_AMOUNT}} |
| | | | **Total:** | **{{ANNUAL_COMMITMENT}}** |

#### Semi-Annual Payment Schedule (if selected)

| Payment # | Period Covered | Invoice Date | Due Date | Amount |
|-----------|----------------|--------------|----------|--------|
| 1 | Months 1-6 | {{EFFECTIVE_DATE}} | {{H1_DUE}} | {{SEMIANNUAL_AMOUNT}} |
| 2 | Months 7-12 | {{H2_INVOICE}} | {{H2_DUE}} | {{SEMIANNUAL_AMOUNT}} |
| | | | **Total:** | **{{ANNUAL_COMMITMENT}}** |

#### Annual Payment Schedule (if selected)

| Payment # | Period Covered | Invoice Date | Due Date | Amount |
|-----------|----------------|--------------|----------|--------|
| 1 | Months 1-12 | {{EFFECTIVE_DATE}} | {{ANNUAL_DUE}} | {{ANNUAL_COMMITMENT}} |

---

## 5. Payment Terms

### Payment Due Date

All invoices are due within **{{PAYMENT_DUE_DAYS}}** days of the invoice date.

| Field | Value |
|-------|-------|
| **Payment Due Days** | {{PAYMENT_DUE_DAYS}} days from invoice date |
| **Accepted Payment Methods** | {{PAYMENT_METHODS}} |

### Late Payment Terms

Late payment interest applies universally to any overdue payment amount, regardless of payment frequency:

| Term | Value |
|------|-------|
| **Late Payment Interest Rate** | {{LATE_PAYMENT_RATE}} per week |
| **Interest Calculation** | Compounding weekly on unpaid balance |
| **Effective Annual Rate** | Approximately 52% (or maximum permitted by law) |

**Late Fee Calculation Example:**

If a payment of $900 (quarterly) is 3 weeks overdue at 1% weekly:
- Week 1: $900 × 1.01 = $909.00
- Week 2: $909 × 1.01 = $918.09
- Week 3: $918.09 × 1.01 = $927.27
- **Total owed after 3 weeks: $927.27** (late fees: $27.27)

### Service Suspension

| Term | Value |
|------|-------|
| **Suspension Grace Period** | {{SUSPENSION_GRACE_DAYS}} days past due date |
| **Suspension Notice** | Written notice provided before suspension |
| **Reinstatement** | Upon payment of all overdue amounts plus accrued interest |

If any payment remains unpaid for more than **{{SUSPENSION_GRACE_DAYS}}** days beyond its due date, the Company may suspend access to the Software until all amounts owed (including accrued late fees) are paid in full. Suspension does not relieve the Customer of obligation to pay remaining fees under this Order Form.

### Non-Refundable Commitment

All fees are **non-cancellable and non-refundable** once paid. The Customer commits to the full 12-month Term and is liable for all scheduled payments regardless of actual usage.

---

## 6. Add-On Services (Optional)

| Service | Description | Price | Selected |
|---------|-------------|-------|----------|
| Epic FHIR Integration Setup | Professional services for EMR integration | {{INTEGRATION_FEE}} | [ ] |
| Additional User Training | 2-hour remote training session | {{TRAINING_SESSION_FEE}} | [ ] |
| Priority Support | 24/7 phone support with 1-hour SLA | {{PRIORITY_SUPPORT_FEE}}/month | [ ] |
| Custom Screening Templates | Custom prep sheet template development | {{CUSTOM_TEMPLATE_FEE}} | [ ] |

---

## 7. Taxes

All fees listed are exclusive of applicable taxes. Customer is responsible for all taxes, levies, or duties imposed by taxing authorities (excluding taxes on Company's income). If Company is required to collect taxes, Customer will be billed accordingly unless valid tax exemption documentation is provided.

---

## 8. Special Terms

{{SPECIAL_TERMS}}

*(Leave blank if none)*

---

## 9. Signatures

By signing below, the Customer agrees to the pricing, payment schedule, and terms specified in this Order Form. This Order Form is subject to and governed by the applicable Service Agreement (Standalone Provider Service Agreement or Multi-Provider Service Agreement).

**Fusco Digital Solutions LLC (Company)**

By: _____________________________ Date: ______________  
Name: ___________________________  
Title: ___________________________

**Customer**

By: _____________________________ Date: ______________  
Name: ___________________________  
Title: ___________________________

---

## For Internal Use Only

| Field | Value |
|-------|-------|
| Sales Representative | {{SALES_REP}} |
| Account ID | {{ACCOUNT_ID}} |
| Contract ID | {{CONTRACT_ID}} |
| CRM Opportunity ID | {{CRM_ID}} |
| Agreement Type | [ ] SPA-2024-001 (Standalone)  [ ] MPA-2024-001 (Multi-Provider) |

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | {{INITIAL_DATE}} | Fusco Digital Solutions LLC | Initial template |
| 1.1 | {{EFFECTIVE_DATE}} | Fusco Digital Solutions LLC | Added flexible payment periods, payment timeline, universal late fee structure |

---

*Fusco Digital Solutions LLC*  
*418 Broadway St, Albany, NY 12207*
