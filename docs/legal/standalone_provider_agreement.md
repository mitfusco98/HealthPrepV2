# Standalone Provider Service Agreement (12-Month Term)

**Version:** 1.0  
**Last Updated:** {{EFFECTIVE_DATE}}  
**Document ID:** SPA-2024-001

---

## Parties

This Standalone Provider Service Agreement (the "Agreement") is entered into between **Fusco Digital Solutions LLC**, a New York limited liability company, with its principal place of business at 418 Broadway St, Albany, NY 12207 (the "Company"), and the subscribing healthcare provider or entity ("Provider"). The Agreement outlines the terms under which the Provider leases access to the Company's software and services for a fixed 12-month term (the "Term"), excluding any month-to-month arrangements.

---

## 1. Term and Renewal

**Term Length:** The Term of this Agreement is twelve (12) months from the effective date. Month-to-month or short-term plans are not available under this Agreement – the Provider commits to the full 12-month period.

**No Automatic Renewal:** This Agreement does not automatically renew at the end of the 12-month Term. Continuation beyond the initial Term requires a new agreement or an explicit renewal in writing by both parties. If the parties wish to renew, they must mutually agree prior to the end of the Term; otherwise, the Agreement will expire at the 12-month mark. There is no month-to-month rollover, ensuring that services are only provided on an annual subscription basis.

**Early Termination:** Except as provided in this Agreement (e.g. for material breach or as otherwise specified), neither party may terminate this Agreement for convenience before the 12-month Term ends. The Provider is responsible for the full Term's obligations and fees even if the Provider stops using the service prior to the end of the Term (no pro-rated refunds for early cancellation). The Company may terminate for cause if the Provider materially breaches the Agreement and fails to cure such breach after notice, as detailed in Section 6.

---

## 2. Payment Terms

> **Note:** Specific fees and billing schedules are defined in the attached Order Form. The following are general payment terms.

**Fees and Billing:** The Provider agrees to pay the subscription fees for the entire 12-month Term as per the rate and schedule set forth in the Order Form or invoice. Subscription fees are typically billed in advance on a periodic schedule (e.g. monthly or quarterly) even though the commitment is annual. All payments shall be made in U.S. dollars via the payment method designated (e.g. credit card or ACH).

### Payment Schedule Variables

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `{{SUBSCRIPTION_FEE_MONTHLY}}` | Monthly subscription fee per provider | See Order Form |
| `{{BILLING_FREQUENCY}}` | How often invoices are issued | Monthly |
| `{{PAYMENT_DUE_DAYS}}` | Days after invoice until payment is due | 30 days |
| `{{LATE_PAYMENT_RATE}}` | Interest rate on late payments (per week) | 1% |
| `{{SUSPENSION_GRACE_DAYS}}` | Days past due before account suspension | 15 days |

**Non-Refundable Commitment:** This 12-month subscription is a commitment for the full term. **Fees are non-cancellable and non-refundable once paid**, except as otherwise explicitly stated in this Agreement. The Provider is liable for the entire year's fees regardless of actual usage, subject to any early termination provisions herein.

**Late Payment and Interest:** If the Provider fails to pay any invoice or installment by its due date, the unpaid amount will accrue late interest at the rate of **{{LATE_PAYMENT_RATE}} per week** (or the maximum rate permitted by law, if lower) from the due date until paid. Interest is charged to compensate for the delay in payment and encourage timely remittance. The Provider shall also be responsible for any costs of collection on overdue amounts, including reasonable attorneys' fees and court costs, if applicable.

**Taxes:** All fees are exclusive of applicable taxes. The Provider is responsible for all taxes, levies, or duties imposed by taxing authorities on the services (excluding taxes on the Company's income). If the Company is required to collect or pay taxes on the Provider's behalf, the Provider will be billed for such amounts unless the Provider provides valid proof of tax exemption.

---

## 3. Suspension of Services for Non-Payment

The Company reserves the explicit right to suspend (freeze) the Provider's account and access to the software if any payment is failed or excessively delayed. If any fee is past due and outstanding for more than **{{SUSPENSION_GRACE_DAYS}}** beyond its due date, the Company may suspend the Provider's access to the software and all associated services until all overdue amounts (including any accrued interest) are paid in full. Suspension means the Provider will not be able to log in or use the services during the suspension period.

During the suspension, the Provider remains responsible for any accrued charges and the obligation to pay fees continues during the suspension period. The Company's right to suspend services is a remedial measure and does not waive the Provider's obligation to pay fees for the full Term. If the Provider remedies the payment default (by paying all amounts due), the Company will promptly restore access. However, if the Provider fails to cure the payment default within a reasonable time (for example, 30 days after suspension), the Company may treat it as a material breach and terminate the Agreement for cause (see Section 6). The Provider acknowledges that this suspension remedy is critical for the Company to protect itself from non-payment situations and is standard for SaaS agreements.

---

## 4. Clinical Use Disclaimers and Software Limitations

The Provider acknowledges the following important limitations of the software and disclaimers regarding its use in clinical or healthcare settings:

- **Not a Replacement for Professional Judgment:** The Company's software is intended as a decision-support and informational tool only. **It is not a licensed medical device or a provider of medical care, and it is not intended to replace professional medical advice, diagnosis, or the independent judgment of a qualified healthcare practitioner.** Any suggestions, recommendations, or matches provided by the software are supplementary and must be critically evaluated by the Provider. The Provider is solely responsible for all clinical decisions and patient care. The software's outputs should never be followed blindly or used as the sole basis for any diagnosis or treatment plan.

- **Limited Contextual Awareness:** The Provider understands that the software operates based on the data and inputs available to it, which may be limited. The software does not have complete context about each patient's unique situation or comprehensive medical history. Consequently, its recommendations or matching results may not account for certain factors that a human provider would consider. The Provider must use professional judgment to interpret and, where appropriate, override or disregard the software's outputs if they do not fit the patient's needs or circumstances.

- **Match Accuracy and Guidance Only:** Any patient-provider matching, diagnostic suggestion, or other guidance provided by the software is offered on an "as-is" informational basis, **with no guarantee of accuracy or suitability for a particular situation**. While the software may use advanced algorithms to provide recommendations, accuracy is not assured, and errors or mismatches are possible. The Provider should verify and validate any match or recommendation. All outputs from the software should be treated as hypotheses or prompts for further investigation, not definitive conclusions.

- **Not a Guaranteed Outcome:** The software cannot and does not guarantee any particular health outcome or improvement. Use of the software is at the Provider's and patient's own risk and discretion. Any information, data analysis, or predictions generated by the software come with inherent uncertainties. The Company makes no warranty that using the software will lead to better clinical decisions or outcomes. No results are assured, and the Provider should not rely on the software as a sole source of truth. The Provider remains responsible for following up on any issues, performing necessary tests, and exercising standard care regardless of software inputs.

- **Regulatory Non-Compliant Use:** The software is not intended to be used in any manner that would violate healthcare regulations or standards. It is not certified as a medical device. The Provider agrees not to use the software as a substitute for any required medical equipment or procedures. All regulatory compliance (such as HIPAA, patient consent for telehealth, etc.) remains the Provider's responsibility when using the software.

**By signing this Agreement, the Provider explicitly acknowledges these limitations and disclaimers.** The Provider agrees to inform all relevant staff and practitioners of the above limitations, ensuring that anyone using or relying on the software's output is aware that it is a supportive tool and not a replacement for professional medical judgment. The Provider shall use the software consistent with these disclaimers and in conjunction with appropriate human oversight and clinical decision-making.

---

## 5. Limitation of Liability

To the maximum extent permitted by law, the Company's liability to the Provider under this Agreement is strictly limited:

- **No Indirect or Consequential Damages:** In no event will the Company be liable for any indirect, incidental, consequential, special, or punitive damages arising out of or relating to this Agreement or the Provider's use of the software and services. This includes, without limitation, any loss of profits, loss of data, business interruption, damage to reputation, or the claims of third parties, even if the Company has been advised of the possibility of such damages. The Provider acknowledges that this limitation is a bargained-for part of the agreement and that the pricing of the service reflects this allocation of risk.

- **Limit on Direct Damages:** The Company's total cumulative liability for any and all claims arising from or related to this Agreement (whether in contract, tort, or otherwise) **shall not exceed the total fees paid by the Provider to the Company under this Agreement in the 12 months preceding the event giving rise to the liability**. If the event occurs before 12 months of service have elapsed, the liability shall be capped at the amount the Provider has paid up to the date of the claim. This cap on liability is an essential element of the bargain and reflects the agreed allocation of risk between the parties.

- **No Warranty & As-Is Service:** The software and services are provided "as is" and "as available," without any warranties of any kind, either express or implied. The Company disclaims any implied warranties, including but not limited to merchantability, fitness for a particular purpose, and non-infringement. The Company does not warrant that the software will function error-free or uninterrupted, or that it will meet all of the Provider's requirements. The Provider assumes all responsibility for selecting the software to achieve its intended results and for the use of the software. The Provider acknowledges that no software is perfect or entirely free of errors, and agrees that mere existence of any software error or bug shall not be deemed a breach of this Agreement by the Company, provided that the Company makes commercially reasonable efforts to correct reported substantial defects in a timely manner.

- **Clinical Outcomes:** The Company shall not be liable for any medical malpractice or negligence claims that arise from the Provider's use or misuse of the software. The Provider is solely responsible for how the software's outputs are interpreted and applied in a clinical setting. The Provider agrees that no patient care decisions should be made solely on software output and that the Provider's professional judgment supersedes any suggestion from the software. Accordingly, the Company will not be held liable for injuries, damages, or losses to any person or property arising from any treatment decision or other action taken (or not taken) in reliance on the software.

Some jurisdictions may not allow the exclusion of certain warranties or the limitation/exclusion of liability for certain types of damages. If applicable law prohibits certain limitations outlined above, those limitations will apply to the minimum extent permitted, and the Agreement shall be interpreted to give effect to the limitations and exclusions stated to the fullest extent possible.

---

## 6. Indemnification

**Provider's Indemnity:** The Provider agrees to indemnify, defend, and hold harmless the Company and its affiliates, officers, directors, employees, and agents from and against any and all claims, liabilities, losses, damages, judgments, or expenses (including reasonable attorneys' fees and costs) arising out of or related to: (a) the Provider's use of the software or services in violation of this Agreement or applicable law; (b) any breach of this Agreement by the Provider (including any misuse of patient data or violation of privacy laws); or (c) any allegation that the Provider's use of the software contributed to or caused harm or injury (of any nature, including personal injury, death, or property damage) to a patient or any third party. This indemnification obligation includes, for example, claims by patients or others that the Provider's reliance on or use of the software's recommendations resulted in incorrect treatment or a missed diagnosis. The Provider will control the defense of any such claim, but the Company reserves the right to participate (at its own cost) in the defense of any claim for which it seeks indemnification.

**Company's Indemnity (Limited):** The Company will indemnify and hold the Provider harmless against third-party claims that the software, as provided by the Company and used in accordance with this Agreement, directly infringes a U.S. patent or copyright or misappropriates a third party's trade secrets. If such an intellectual property infringement claim arises, the Company may at its discretion: (i) modify the software to be non-infringing, (ii) obtain a license for the Provider to continue using the software, or (iii) if neither (i) nor (ii) is feasible, terminate this Agreement and refund any pre-paid fees for the remaining unused Term. The Company's indemnification obligations do not apply to claims arising from any misuse of the software, use of the software in combination with other products not provided by the Company, or modifications made by the Provider. This Section 6(b) states the Company's entire liability and the Provider's exclusive remedy for any intellectual property infringement by the software.

**Indemnification Procedures:** A party seeking indemnification (the "Indemnitee") shall promptly notify the other party (the "Indemnitor") in writing of any claim for which it seeks indemnity. Failure to provide prompt notice will not relieve the Indemnitor of its obligations except to the extent materially prejudiced by the delay. The Indemnitor shall have the right to assume the defense of the claim with counsel of its choosing. The Indemnitee shall provide reasonable cooperation in the defense at the Indemnitor's expense. The Indemnitor shall not settle any claim without the Indemnitee's prior written consent if the settlement imposes any liability or admission of fault on the Indemnitee; such consent shall not be unreasonably withheld. The Indemnitee may participate in the defense with its own counsel at its own expense.

---

## 7. Miscellaneous Provisions

**7.1 Governing Law:** This Agreement shall be governed by and construed in accordance with the laws of the State of New York, without regard to its conflict of laws principles. The parties agree that the United Nations Convention on Contracts for the International Sale of Goods does not apply to this Agreement.

**7.2 Dispute Resolution:** In order to prevent lawsuits and resolve disputes efficiently, the parties agree to attempt in good faith to resolve any dispute arising out of or relating to this Agreement through informal negotiations. If a dispute cannot be resolved amicably, it shall be submitted to binding arbitration as the exclusive means of resolving the controversy, except that either party may seek temporary injunctive relief in a court of competent jurisdiction to prevent immediate and irreparable harm. The arbitration will be administered by a reputable arbitration organization (e.g., the American Arbitration Association) and conducted by a single arbitrator. The arbitration shall take place in Albany, New York, and be conducted in English. **Each party waives the right to a trial by jury or to participate in a class action for disputes under this Agreement.** The arbitrator shall have authority to award any remedies that a court could award, including injunctive relief if warranted, but may not award damages or remedies inconsistent with the limitations and exclusions in this Agreement. Judgment on the arbitration award may be entered in any court having jurisdiction.

**7.3 Notices:** All legal notices or communications required under this Agreement shall be in writing and shall be deemed given: (a) if delivered personally, upon receipt; (b) if sent by certified mail or courier, upon confirmation of delivery; or (c) if sent by email, when sent via email with confirmation of successful transmission, provided that a copy is also sent by one of the preceding methods. For purposes of notice, the Company's contact is legal@fuscodigital.com, and the Provider's contact is the email and/or address provided at registration. Either party may update its notice contact information by notifying the other in accordance with this Section. Email is an acceptable method for routine communications and notices under this Agreement.

**7.4 No Assignment:** The Provider may not assign or transfer this Agreement or any of its rights or obligations hereunder without the prior written consent of the Company. Any attempted assignment in violation of this clause is null and void. The Company may assign this Agreement to a successor in interest (for example, in the event of a merger or acquisition) or to an affiliate as long as such assignment does not reduce the Provider's rights under this Agreement.

**7.5 Entire Agreement:** This Agreement (including any exhibits or order forms incorporated by reference) constitutes the entire agreement between the parties with respect to the subject matter and supersedes all prior or contemporaneous understandings or agreements, whether written or oral. Each party acknowledges that in entering into this Agreement it has not relied on any representations not expressly contained herein.

**7.6 Amendment and Waiver:** No amendment or modification of this Agreement will be valid unless in writing and signed by both parties. No waiver of any breach or default will constitute a waiver of any other right hereunder or of any subsequent breach or default. Failure or delay by either party to enforce any provision of this Agreement will not be deemed a waiver.

**7.7 Severability:** If any provision of this Agreement is held to be invalid, illegal, or unenforceable by an arbitrator or court of competent jurisdiction, that provision shall be enforced to the maximum extent permissible, and the remaining provisions of this Agreement will remain in full force and effect. The parties will negotiate in good faith a valid, legal, and enforceable substitute provision that most nearly reflects the original intent of the unenforceable provision.

**7.8 Limitation of Liability & Remedies Acknowledgement:** The Provider acknowledges that the disclaimers of warranties, limitations of liability, and indemnities set forth in this Agreement are fair and reasonable and have been taken into account in establishing the fees and conditions of this Agreement. The Provider has read and understood these clauses, and by entering into this Agreement, agrees to be bound by them. These provisions will survive the termination or expiration of this Agreement.

**7.9 Right to Seek Injunction:** Notwithstanding the arbitration clause above, the Provider acknowledges that unauthorized use or disclosure of the Company's software, intellectual property, or Confidential Information may cause irreparable harm to the Company for which monetary damages would be inadequate. In addition to any other remedies available, the Company shall have the right to seek immediate injunctive relief in any court of competent jurisdiction to prevent any actual or threatened violation of confidentiality or intellectual property rights, without having to post a bond or prove actual damages.

**7.10 Freezing Account Access on Payment Default:** The Provider explicitly agrees that the Company's act of freezing or suspending account access due to non-payment as described in Section 3 is a legitimate and contractually agreed remedy, and the Provider will not challenge such suspension as long as it is carried out in accordance with the terms of this Agreement. The Provider waives any claims against the Company arising from the suspension of services for non-payment, and acknowledges that the risk of a freeze due to non-payment is solely within the Provider's control (by paying on time). This provision is intended to further underscore the parties' understanding that timely payment is a material obligation under this Agreement.

---

## Signatures

**By entering into this 12-month Provider Service Agreement, the Provider confirms that they have read this Agreement in its entirety, understand its provisions (including the important disclaimers and liability limitations), and agree to be bound by all the terms and conditions set forth above.** The individual accepting this Agreement on behalf of the Provider represents that they have the authority to do so.

**Fusco Digital Solutions LLC (Company)**

By: _____________________________ Date: ______________  
Name: ___________________________  
Title: ___________________________

**Provider**

By: _____________________________ Date: ______________  
Name: ___________________________  
Title: ___________________________

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | {{EFFECTIVE_DATE}} | Fusco Digital Solutions LLC | Initial HITRUST i1 submission version |

---

## Appendix: Order Form Template

See [Order Form](./order_form.md) for specific pricing and billing details.

---

*Fusco Digital Solutions LLC*  
*418 Broadway St, Albany, NY 12207*
