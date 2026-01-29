# HealthPrep Incident Response Plan

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | HealthPrep Security Team | Initial release |

**Classification**: Internal Use Only
**Review Frequency**: Annual or after any significant incident
**Next Review**: January 2027

---

## 1. Purpose and Scope

### 1.1 Purpose

This Incident Response Plan (IRP) establishes procedures for detecting, responding to, and recovering from security incidents affecting HealthPrep and its protected health information (PHI). It ensures compliance with HIPAA Security Rule requirements (45 CFR 164.308(a)(6)) and HITRUST CSF domain 09.1.

### 1.2 Scope

This plan applies to:
- All HealthPrep system components and data
- All personnel with access to HealthPrep systems
- All organizations using the HealthPrep platform
- Third-party integrations (Epic FHIR, AWS, Stripe)

### 1.3 Related Documents

| Document | Location |
|----------|----------|
| Security Whitepaper | `/docs/SECURITY_WHITEPAPER.md` |
| HITRUST Readiness | `/docs/HITRUST_READINESS.md` |
| NIST Risk Register | `/docs/NIST_800_30_RISK_REGISTER.md` |

---

## 2. Incident Classification

### 2.1 Severity Levels

| Level | Name | Description | Response Time | Examples |
|-------|------|-------------|---------------|----------|
| **P1** | Critical | Active breach, PHI exposed, system compromised | < 15 minutes | Database breach, active intrusion, ransomware |
| **P2** | High | Potential breach, security control failure | < 1 hour | Brute force attack, PHI filter failure, credential compromise |
| **P3** | Medium | Security anomaly, policy violation | < 4 hours | Account lockout patterns, unauthorized access attempt |
| **P4** | Low | Minor security event, informational | < 24 hours | Failed login attempts, configuration changes |

### 2.2 Incident Categories

| Category | AdminLog Event Types | Auto-Alert |
|----------|---------------------|------------|
| **Authentication Attack** | `login_failed`, `security_brute_force` | Yes (10+ attempts) |
| **Account Compromise** | `security_account_lockout`, `security_password_reset` | Yes |
| **PHI Exposure** | `phi_filter_failed`, `phi_redacted` anomalies | Yes |
| **Unauthorized Access** | `patient_view`, `document_view` (unusual patterns) | Manual review |
| **System Compromise** | `security_*` with critical indicators | Yes |
| **Data Exfiltration** | `patient_data_export`, unusual volume | Manual review |

---

## 3. Incident Response Team

### 3.1 Roles and Responsibilities

| Role | Responsibilities | Contact Method |
|------|------------------|----------------|
| **Incident Commander** | Overall incident coordination, external communication | Primary on-call |
| **Security Lead** | Technical investigation, containment decisions | Security team |
| **System Administrator** | System access, log collection, technical remediation | Operations team |
| **Privacy Officer** | HIPAA compliance, breach determination, notifications | Compliance team |
| **Legal Counsel** | Legal guidance, regulatory communication | As needed |
| **Communications Lead** | Customer and public communications | As needed |

### 3.2 Escalation Matrix

```
P4 (Low)     → Security Lead → Review within 24 hours
P3 (Medium)  → Security Lead → Incident Commander notification
P2 (High)    → Incident Commander → Full IRT activation
P1 (Critical) → Incident Commander → Executive notification, all hands
```

---

## 4. Detection and Analysis

### 4.1 Automated Detection Sources

HealthPrep automatically detects and alerts on these security events via `services/security_alerts.py`:

| Detection | Threshold | AdminLog Event | Alert Recipients |
|-----------|-----------|----------------|------------------|
| Account Lockout | 5 failed attempts | `security_account_lockout` | Org admins |
| Brute Force Attack | 10 attempts / 5 min | `security_brute_force` | Org admins, Root admin |
| PHI Filter Failure | Any failure | `security_phi_filter_failure` | Org admins, Root admin |

### 4.2 Log Investigation Procedures

#### Organization Admin Investigation (`/admin/logs`)

1. Navigate to **Admin Dashboard → Activity Logs**
2. Filter by event type:
   - `login_failed` - Authentication failures
   - `security_*` - All security events
   - `patient_*` - Patient data access
   - `document_*` - Document access patterns
3. Export logs for offline analysis (CSV with PHI redaction option)

#### Root Admin Investigation (`/root-admin/system/logs`)

1. Navigate to **System Administration → System Logs**
2. Cross-organization filtering available:
   - Filter by organization to isolate affected tenant
   - Filter by event type for pattern analysis
   - Filter by date range for timeline reconstruction
3. Export capabilities for compliance evidence

### 4.3 Investigation Queries

**Identify brute force sources:**
```sql
SELECT ip_address, COUNT(*) as attempts, 
       array_agg(DISTINCT data->>'username') as usernames
FROM admin_logs 
WHERE event_type = 'login_failed' 
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY ip_address 
HAVING COUNT(*) > 5
ORDER BY attempts DESC;
```

**Track user session activity:**
```sql
SELECT timestamp, event_type, action_details, ip_address
FROM admin_logs
WHERE user_id = :user_id
  AND timestamp BETWEEN :start_date AND :end_date
ORDER BY timestamp;
```

**Identify PHI access patterns:**
```sql
SELECT user_id, patient_id, COUNT(*) as access_count
FROM admin_logs
WHERE event_type IN ('patient_view', 'document_view')
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY user_id, patient_id
HAVING COUNT(*) > 50  -- Unusual volume threshold
ORDER BY access_count DESC;
```

---

## 5. Containment Procedures

### 5.1 Immediate Actions by Severity

#### P1 Critical - Active Breach

1. **Log incident start**: Use `IncidentLogger.log_incident_detected()` (see Section 9)
2. **Isolate affected systems**: Disable compromised accounts immediately
3. **Preserve evidence**: Export relevant logs before any remediation
4. **Notify Incident Commander**: Escalate immediately
5. **Engage legal counsel**: For breach determination

#### P2 High - Potential Breach

1. **Log incident**: Use `IncidentLogger.log_incident_detected()` (see Section 9)
2. **Disable affected accounts**: Prevent further unauthorized access
3. **Review access logs**: Identify scope of potential exposure
4. **Escalate to Incident Commander**: Within 1 hour

#### P3/P4 Medium/Low

1. **Log incident**: Use `IncidentLogger.log_incident_detected()` (see Section 9)
2. **Document findings**: Record in incident log
3. **Schedule review**: Add to security review queue

### 5.2 Account Containment

```python
from services.security_alerts import IncidentLogger

# Disable user account via /admin/users or database
user.is_account_locked = True
user.lockout_until = datetime.utcnow() + timedelta(days=365)  # Extended lockout
db.session.commit()

# Log containment action
IncidentLogger.log_incident_contained(
    org_id=user.org_id,
    incident_id=incident_id,
    actions_taken=['account_disabled', 'extended_lockout'],
    user_id=current_user.id
)
```

### 5.3 Epic Integration Containment

If Epic credentials are suspected compromised:

1. Revoke OAuth tokens in HealthPrep database
2. Contact Epic administrator to revoke SMART on FHIR credentials
3. Disable Epic sync for affected organization
4. Log containment:

```python
IncidentLogger.log_incident_contained(
    org_id=org_id,
    incident_id=incident_id,
    actions_taken=['oauth_tokens_revoked', 'epic_sync_disabled', 'epic_admin_notified'],
    user_id=current_user.id
)
```

---

## 6. Eradication and Recovery

### 6.1 Eradication Steps

1. **Remove threat access**: Delete compromised credentials, revoke sessions
2. **Patch vulnerabilities**: Apply security updates if applicable
3. **Reset credentials**: Force password resets for affected users
4. **Verify PHI integrity**: Confirm no unauthorized modifications

### 6.2 Recovery Steps

1. **Restore from backup** (if needed): Use AWS RDS PITR
2. **Re-enable accounts**: After credential reset verification
3. **Resume Epic sync**: After Epic administrator confirmation
4. **Monitor closely**: Enhanced logging for 30 days post-incident

### 6.3 Recovery Validation

- [ ] All compromised accounts re-secured
- [ ] No unauthorized access in last 24 hours
- [ ] PHI integrity verified
- [ ] Epic integration tested
- [ ] Enhanced monitoring active

---

## 7. HIPAA Breach Notification

### 7.1 Breach Determination

A breach is the acquisition, access, use, or disclosure of PHI in a manner not permitted by the HIPAA Privacy Rule which compromises the security or privacy of the PHI.

**Presumption of Breach**: Unless the covered entity demonstrates there is a low probability that PHI has been compromised based on a risk assessment of at least the following factors:

1. Nature and extent of PHI involved
2. Unauthorized person who used or received the PHI
3. Whether PHI was actually acquired or viewed
4. Extent to which risk has been mitigated

### 7.2 Notification Timeline (HIPAA Requirements)

| Notification | Deadline | Recipient |
|--------------|----------|-----------|
| **Individual Notice** | 60 days from discovery | Affected individuals |
| **Media Notice** | 60 days (if >500 in state) | Prominent media outlets |
| **HHS Notice** | 60 days (if >500) or annual (if <500) | HHS Secretary |

### 7.3 Breach Notification Content

Required elements for individual notification:

1. Description of what happened (date, nature)
2. Types of PHI involved
3. Steps individuals should take to protect themselves
4. What the organization is doing to investigate and mitigate
5. Contact information for questions

### 7.4 Notification Logging

All breach notifications must be logged in AdminLog:

```python
from services.security_alerts import IncidentLogger

IncidentLogger.log_breach_notification(
    org_id=org_id,
    notification_type='individual',  # or 'media', 'hhs'
    recipient_count=count,
    phi_types=['names', 'dates_of_service', 'mrn'],
    incident_id=incident_id,
    user_id=current_user.id
)
```

---

## 8. Post-Incident Activities

### 8.1 Incident Documentation

Complete incident report within 7 days containing:

1. **Timeline**: Detection to resolution
2. **Root cause analysis**: How the incident occurred
3. **Impact assessment**: Data/systems/individuals affected
4. **Response effectiveness**: What worked, what didn't
5. **Lessons learned**: Improvements identified
6. **Action items**: Remediation tasks with owners and deadlines

### 8.2 Lessons Learned Meeting

Hold within 14 days of incident resolution:

- Review incident timeline and response
- Identify process improvements
- Update IRP as needed
- Assign action items

### 8.3 Evidence Retention

| Evidence Type | Retention Period | Storage Location |
|---------------|------------------|------------------|
| AdminLog entries | 7 years (HIPAA) | Database (production) |
| Incident reports | 7 years | Secure document storage |
| Communication records | 7 years | Email archive |
| Forensic images | 7 years or case resolution | Encrypted offline storage |

---

## 9. Incident Event Types for AdminLog

The following event types are used for incident lifecycle tracking:

| Event Type | Description | When Logged |
|------------|-------------|-------------|
| `incident_detected` | New security incident identified | Incident discovery |
| `incident_escalated` | Incident escalated to higher severity | Severity increase |
| `incident_contained` | Threat access removed | Containment complete |
| `incident_resolved` | Incident fully remediated | Resolution |
| `incident_closed` | Post-incident activities complete | Final closure |
| `breach_investigation_started` | Formal breach assessment begun | Breach determination |
| `breach_confirmed` | PHI breach confirmed | After risk assessment |
| `breach_notification_sent` | Notification dispatched | Each notification |

### 9.1 Logging Implementation

Use `services/security_alerts.py` functions:

```python
from services.security_alerts import IncidentLogger

# Log incident detection
IncidentLogger.log_incident_detected(
    org_id=org_id,
    severity='P2',
    category='authentication_attack',
    description='Brute force attack detected from IP 192.168.1.100',
    details={'ip_address': '192.168.1.100', 'attempt_count': 15}
)

# Log containment
IncidentLogger.log_incident_contained(
    org_id=org_id,
    incident_id=incident_id,
    actions_taken=['account_locked', 'ip_blocked']
)

# Log breach notification
IncidentLogger.log_breach_notification(
    org_id=org_id,
    notification_type='individual',
    recipient_count=150,
    phi_types=['names', 'dates_of_service']
)
```

---

## 10. Testing and Maintenance

### 10.1 Tabletop Exercises

Conduct tabletop exercises annually covering:

- [ ] Database breach scenario
- [ ] Ransomware attack scenario
- [ ] Insider threat scenario
- [ ] Third-party compromise scenario

Document exercise results and update IRP accordingly.

### 10.2 Plan Maintenance

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Full plan review | Annual | Security Lead |
| Contact information update | Quarterly | Operations |
| Tabletop exercise | Annual | Incident Commander |
| Post-incident update | After each P1/P2 | Security Lead |

---

## 11. Quick Reference Card

### Immediate Response Checklist

- [ ] Assess severity level (P1-P4)
- [ ] Log `incident_detected` event
- [ ] Notify appropriate personnel per escalation matrix
- [ ] Preserve evidence (export logs)
- [ ] Contain threat (disable accounts, revoke access)
- [ ] Document all actions taken

### Key Contacts

| Role | Primary | Backup |
|------|---------|--------|
| Incident Commander | [TBD] | [TBD] |
| Security Lead | [TBD] | [TBD] |
| Privacy Officer | [TBD] | [TBD] |
| Legal Counsel | [TBD] | [TBD] |

### Log Access Points

| Interface | URL | Access Level |
|-----------|-----|--------------|
| Org Admin Logs | `/admin/logs` | Organization admins |
| System Logs | `/root-admin/system/logs` | Root admins only |
| Log Export | `/admin/logs/export` | Organization admins |

---

## Appendix A: Incident Report Template

```
INCIDENT REPORT

Incident ID: INC-YYYY-###
Severity: P1 / P2 / P3 / P4
Status: Open / Contained / Resolved / Closed

TIMELINE
- Detection: [Date/Time] - [How detected]
- Containment: [Date/Time] - [Actions taken]
- Eradication: [Date/Time] - [Actions taken]
- Recovery: [Date/Time] - [Actions taken]
- Closure: [Date/Time]

IMPACT
- Organizations affected: [List]
- Patients affected: [Count]
- PHI types exposed: [List]
- Systems affected: [List]

ROOT CAUSE
[Description of how the incident occurred]

RESPONSE ACTIONS
1. [Action] - [Owner] - [Status]
2. [Action] - [Owner] - [Status]

LESSONS LEARNED
- [Improvement identified]
- [Process change recommended]

ACTION ITEMS
- [ ] [Task] - [Owner] - [Due date]
```

---

## Appendix B: Breach Risk Assessment Worksheet

Use this worksheet to determine if unauthorized PHI access constitutes a reportable breach:

**Factor 1: Nature and Extent of PHI**
- [ ] Limited to demographic information only (lower risk)
- [ ] Includes clinical information (higher risk)
- [ ] Includes financial information (higher risk)
- [ ] Includes SSN or other government IDs (highest risk)

**Factor 2: Unauthorized Recipient**
- [ ] Another covered entity or business associate (lower risk)
- [ ] Unknown external party (higher risk)
- [ ] Known malicious actor (highest risk)

**Factor 3: Actual Acquisition or Viewing**
- [ ] No evidence PHI was actually viewed (lower risk)
- [ ] Evidence suggests PHI was viewed (higher risk)
- [ ] Confirmed PHI was copied/downloaded (highest risk)

**Factor 4: Mitigation**
- [ ] PHI returned/destroyed before use (mitigates risk)
- [ ] Recipient signed confidentiality agreement (mitigates risk)
- [ ] No mitigation possible (does not mitigate)

**Determination**: Based on above factors, probability of PHI compromise is:
- [ ] LOW - Not a reportable breach
- [ ] NOT LOW - Reportable breach, proceed with notifications

---

## Appendix C: Incident Response Testing Plan

### Purpose

Regular testing of incident response procedures ensures the team is prepared for real security events. HITRUST CSF requires documented evidence of IR plan testing (Domain 09.1). These exercises validate that:
1. Detection mechanisms trigger correctly
2. Alert notifications reach appropriate personnel
3. Response procedures are understood and executable
4. Documentation and logging capture necessary information

### Testing Schedule

| Exercise Type | Frequency | Last Performed | Next Due |
|--------------|-----------|----------------|----------|
| Tabletop Exercise | Quarterly | [TBD] | [TBD] |
| Full Simulation | Annually | [TBD] | [TBD] |

---

### Test Scenario 1: Account Lockout (P3 - Medium)

**Objective**: Verify that 5 failed login attempts trigger account lockout and admin notification.

**Prerequisites**:
- Test user account (not production)
- Admin email configured in organization settings

**Test Steps**:
1. Navigate to login page
2. Enter valid username with incorrect password - repeat 5 times
3. Verify account lockout message appears on 6th attempt

**Expected Outcomes**:
| Check | Expected Result | Pass/Fail |
|-------|-----------------|-----------|
| Account locked | User sees "Account locked" message | [ ] |
| AdminLog entry | `security_account_lockout` event logged with IP, username | [ ] |
| Email alert | Admin receives lockout notification email | [ ] |
| Lockout duration | Account remains locked for 30 minutes | [ ] |

**Response Validation**:
- [ ] Admin can view lockout in `/admin/logs`
- [ ] Admin can manually unlock account if legitimate user
- [ ] Incident documented per IRP Section 5

---

### Test Scenario 2: Brute Force Detection (P2 - High)

**Objective**: Verify that 10+ failed logins from same IP trigger brute force alert.

**Prerequisites**:
- Multiple test user accounts
- Admin email configured

**Test Steps**:
1. From same IP, attempt failed logins against 10+ different usernames within 5 minutes
2. Verify brute force alert is triggered

**Expected Outcomes**:
| Check | Expected Result | Pass/Fail |
|-------|-----------------|-----------|
| Alert triggered | `security_brute_force` event logged | [ ] |
| Email alert | Security contacts receive brute force notification | [ ] |
| Alert details | Email includes IP address, attempt count, usernames targeted | [ ] |
| Rate limiting | Further attempts from IP are throttled | [ ] |

**Response Validation**:
- [ ] Security team can identify attacking IP from logs
- [ ] IP can be blocked at infrastructure level if needed
- [ ] Affected users can be notified if accounts were real targets

---

### Test Scenario 3: Unauthorized Admin Access (P3 - Medium)

**Objective**: Verify that non-admin users cannot access admin routes.

**Prerequisites**:
- Standard user account (non-admin role)
- Admin route URLs

**Test Steps**:
1. Log in as standard user
2. Attempt to navigate directly to `/admin/dashboard`
3. Attempt to navigate to `/admin/users`
4. Attempt to navigate to `/root-admin/system`

**Expected Outcomes**:
| Check | Expected Result | Pass/Fail |
|-------|-----------------|-----------|
| Access denied | User redirected to user dashboard | [ ] |
| No admin UI | Admin navigation not visible | [ ] |
| Audit log | Access attempt logged (if enabled) | [ ] |
| No data leak | No admin data visible in response | [ ] |

**Response Validation**:
- [ ] RBAC enforcement is functioning
- [ ] No privilege escalation possible via URL manipulation

---

### Test Scenario 4: PHI Filter Failure (P2 - High)

**Objective**: Verify that PHI filter failures are detected and alerted.

**Prerequisites**:
- Test document with known PHI patterns
- PHI filter logging enabled

**Test Steps**:
1. Upload a test document containing SSN, phone, email patterns
2. Verify PHI filter processes and redacts content
3. Intentionally trigger a filter failure scenario (if testable)

**Expected Outcomes**:
| Check | Expected Result | Pass/Fail |
|-------|-----------------|-----------|
| PHI redacted | SSN shows as `[SSN REDACTED]` | [ ] |
| Phone redacted | Phone shows as `[PHONE REDACTED]` | [ ] |
| Audit log | `phi_redacted` event logged with counts | [ ] |
| On failure | `security_phi_filter_failure` alert sent | [ ] |

**Response Validation**:
- [ ] PHI filter catches standard identifier patterns
- [ ] Failures trigger immediate alert to security team
- [ ] Failed documents are quarantined for manual review

---

### Test Scenario 5: Suspicious Access Pattern (P3 - Medium)

**Objective**: Verify audit trail captures access patterns for manual review.

**Prerequisites**:
- User account with patient access
- Multiple patient records in test environment

**Test Steps**:
1. Log in as test user
2. Access 10+ different patient records within 5 minutes
3. Review audit logs for access pattern

**Expected Outcomes**:
| Check | Expected Result | Pass/Fail |
|-------|-----------------|-----------|
| Access logged | Each `patient_view` event logged with timestamp | [ ] |
| User identified | Logs show user_id, session_id, IP | [ ] |
| Pattern visible | Log review shows rapid access pattern | [ ] |
| Export available | Logs can be exported for analysis | [ ] |

**Response Validation**:
- [ ] Audit trail sufficient to identify unusual access
- [ ] Security team knows how to query for access patterns
- [ ] Escalation path clear for confirmed snooping

---

### Test Scenario 6: Password Reset Abuse (P4 - Low)

**Objective**: Verify rate limiting prevents password reset abuse.

**Prerequisites**:
- Test user account
- Email access

**Test Steps**:
1. Navigate to password reset page
2. Request password reset for same email 5+ times rapidly
3. Verify rate limit triggers

**Expected Outcomes**:
| Check | Expected Result | Pass/Fail |
|-------|-----------------|-----------|
| Rate limited | "Too many attempts" message after 5 requests | [ ] |
| Tokens invalidated | Previous reset tokens invalidated on new request | [ ] |
| Audit log | `security_password_reset` events logged | [ ] |
| Lockout period | Must wait before additional reset requests | [ ] |

**Response Validation**:
- [ ] Cannot flood user with reset emails
- [ ] Previous tokens don't remain valid (single-use)
- [ ] Rate limit window appropriate (5 min)

---

### Test Scenario 7: Epic OAuth Failure (P3 - Medium)

**Objective**: Verify Epic integration failures are handled gracefully with logging.

**Prerequisites**:
- Epic sandbox credentials
- Test organization with Epic configured

**Test Steps**:
1. Initiate Epic sync with invalid/expired token
2. Verify error handling and logging
3. Check user sees appropriate error message

**Expected Outcomes**:
| Check | Expected Result | Pass/Fail |
|-------|-----------------|-----------|
| Graceful failure | User sees friendly error, not stack trace | [ ] |
| Error logged | `epic_sync_failed` or similar event logged | [ ] |
| No PHI in error | Error message doesn't contain patient data | [ ] |
| Retry guidance | User informed how to re-authenticate | [ ] |

**Response Validation**:
- [ ] Epic failures don't crash the application
- [ ] Token refresh attempted before failure
- [ ] User can re-initiate OAuth flow

---

### Test Execution Record

| Date | Scenario | Tester | Result | Notes |
|------|----------|--------|--------|-------|
| | | | | |
| | | | | |
| | | | | |

### Post-Test Actions

After completing IR testing:
1. [ ] Document all pass/fail results in table above
2. [ ] Create remediation tasks for any failures
3. [ ] Update this document with lessons learned
4. [ ] Schedule next quarterly test
5. [ ] File test evidence for HITRUST audit
