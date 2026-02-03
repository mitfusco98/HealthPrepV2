# HealthPrep Business Continuity & Disaster Recovery Plan

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | HealthPrep Operations | Initial release |

**Classification**: Internal Use Only
**Review Frequency**: Annual or after significant infrastructure changes
**Next Review**: January 2027

---

## 1. Purpose and Scope

### 1.1 Purpose

This Business Continuity Plan (BCP) and Disaster Recovery Plan (DRP) establishes procedures for maintaining critical operations and recovering from disruptions to HealthPrep services. It ensures compliance with HIPAA Security Rule (45 CFR 164.308(a)(7)) and HITRUST CSF requirements for contingency planning.

### 1.2 Scope

This plan covers:
- HealthPrep application and infrastructure
- PostgreSQL database containing patient data
- Epic FHIR integration services
- Document processing and OCR services
- All hosted environments (development, staging, production)

### 1.3 Related Documents

| Document | Location |
|----------|----------|
| Incident Response Plan | `/docs/INCIDENT_RESPONSE_PLAN.md` |
| Security Whitepaper | `/docs/SECURITY_WHITEPAPER.md` |
| Deployment Readiness | `/DEPLOYMENT_READINESS.md` |

---

## 2. Recovery Objectives

### 2.1 Recovery Time Objective (RTO)

| Service Tier | RTO | Description |
|--------------|-----|-------------|
| **Critical** | 4 hours | Core application, authentication, patient data access |
| **High** | 8 hours | Epic sync, document processing |
| **Medium** | 24 hours | Reporting, analytics, batch operations |
| **Low** | 72 hours | Non-critical integrations, marketing site |

### 2.2 Recovery Point Objective (RPO)

| Data Type | RPO | Backup Method |
|-----------|-----|---------------|
| Patient data | 1 hour | Continuous replication + hourly snapshots |
| Documents | 4 hours | Periodic backup to S3 |
| Audit logs | 15 minutes | Real-time streaming to backup |
| Configuration | 24 hours | Version control (Git) |

---

## 3. Risk Assessment Summary

### 3.1 Threat Categories

| Threat | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Data center outage | Low | Critical | Multi-AZ deployment |
| Database corruption | Low | Critical | Point-in-time recovery |
| Ransomware attack | Medium | Critical | Immutable backups, IR plan |
| Epic API outage | Medium | High | Graceful degradation, caching |
| DDoS attack | Medium | Medium | WAF, rate limiting |
| Key personnel unavailable | Medium | Medium | Documentation, cross-training |

---

## 4. Backup Strategy

### 4.1 Database Backups

**AWS RDS PostgreSQL**:
- Automated daily snapshots retained for 35 days
- Point-in-Time Recovery (PITR) enabled with 5-minute granularity
- Cross-region replication to secondary region (recommended)
- Snapshots encrypted with KMS

**Configuration**:
```terraform
resource "aws_db_instance" "healthprep" {
  backup_retention_period    = 35
  backup_window             = "03:00-04:00"  # UTC
  delete_automated_backups  = false
  storage_encrypted         = true
  kms_key_id               = aws_kms_key.healthprep.arn
}
```

### 4.2 Application Backups

| Component | Backup Method | Frequency | Retention |
|-----------|---------------|-----------|-----------|
| Application code | Git repository | Continuous | Indefinite |
| Environment config | AWS Secrets Manager | On change | Version history |
| Docker images | ECR with immutable tags | Per deploy | 90 days |
| Infrastructure | Terraform state in S3 | On change | Version history |

### 4.3 Document Storage

**S3 Configuration**:
- Versioning enabled for all document buckets
- Cross-region replication to secondary region
- Lifecycle policy: 7-year retention for compliance
- Server-side encryption with KMS

---

## 5. Disaster Recovery Procedures

### 5.1 Database Recovery

**Scenario: Database corruption or accidental data loss**

1. **Assess Scope**
   - Identify affected tables/records
   - Determine point of corruption
   - Check audit logs for root cause

2. **Point-in-Time Recovery**
   ```bash
   # AWS CLI example
   aws rds restore-db-instance-to-point-in-time \
     --source-db-instance-identifier healthprep-prod \
     --target-db-instance-identifier healthprep-restored \
     --restore-time "2026-01-15T12:00:00Z"
   ```

3. **Validate Restored Data**
   - Run data integrity checks
   - Verify patient record counts
   - Test application connectivity

4. **Cutover**
   - Update application database URL
   - Verify all services operational
   - Monitor for issues

### 5.2 Application Recovery

**Scenario: Application failure or deployment issue**

1. **Rollback to Previous Version**
   ```bash
   # ECS rollback to previous task definition
   aws ecs update-service \
     --cluster healthprep-prod \
     --service healthprep-api \
     --task-definition healthprep-api:PREVIOUS_VERSION
   ```

2. **If Infrastructure Damage**
   - Run Terraform apply with last known good state
   - Restore secrets from Secrets Manager
   - Redeploy application containers

### 5.3 Complete Infrastructure Recovery

**Scenario: Total loss of primary region**

1. **Activate Secondary Region**
   - DNS failover to secondary region (Route 53)
   - Promote RDS read replica to primary
   - Update application configuration

2. **Verify Services**
   - Confirm database connectivity
   - Test Epic API integration
   - Verify all patient data accessible

3. **Communication**
   - Notify affected organizations
   - Update status page
   - Document incident timeline

---

## 6. Testing Requirements

### 6.1 Test Schedule

| Test Type | Frequency | Last Performed | Next Due |
|-----------|-----------|----------------|----------|
| Backup verification | Monthly | Not yet performed | February 2026 |
| Database restore drill | Quarterly | Not yet performed | Q1 2026 (March) |
| Application failover | Semi-annually | Not yet performed | Q2 2026 (June) |
| Full DR simulation | Annually | Not yet performed | Q4 2026 |

**Note:** Test results are recorded in `/docs/security/dr-drill-log.md`

### 6.2 Test Procedures

**Monthly Backup Verification**:
- [ ] Confirm automated snapshots are completing
- [ ] Verify snapshot integrity via test restore
- [ ] Check backup metrics in CloudWatch
- [ ] Review backup failure alerts

**Quarterly Database Restore Drill**:
- [ ] Restore database to test environment
- [ ] Verify data integrity and record counts
- [ ] Test application against restored database
- [ ] Document restore time (measure against RTO)
- [ ] Delete test resources

---

## 7. Roles and Responsibilities

| Role | Responsibility | Contact |
|------|----------------|---------|
| **Operations Lead** | Execute recovery procedures | Mitchell Fusillo (mitch@fuscodigital.com, 716-909-8567) |
| **Database Administrator** | Database backup/restore | Mitchell Fusillo (mitch@fuscodigital.com, 716-909-8567) |
| **Security Lead** | Incident coordination, compliance | Mitchell Fusillo (mitch@fuscodigital.com, 716-909-8567) |
| **Communications Lead** | Customer and stakeholder updates | Mitchell Fusillo (mitch@fuscodigital.com, 716-909-8567) |

---

## 8. Communication Plan

### 8.1 Internal Escalation

```
Incident Detected → Operations Lead → Security Lead → Executive Team
                                    ↓
                              Communications Lead → Customer Notification
```

### 8.2 External Communication

| Stakeholder | Channel | Timing |
|-------------|---------|--------|
| Affected organizations | Email + In-app banner | Within 1 hour of confirmed outage |
| All customers | Status page update | Within 2 hours |
| Regulators (if breach) | Per HIPAA requirements | Within 60 days |

---

## 9. Vendor Dependencies

### 9.1 Critical Vendors

| Vendor | Service | Backup Plan |
|--------|---------|-------------|
| AWS | Infrastructure hosting | Multi-region architecture |
| Epic | FHIR API | Graceful degradation, cached data |
| Resend | Email delivery | Queue emails, retry on recovery |
| Stripe | Payment processing | Queue transactions, reconcile |

### 9.2 Vendor Contact Information

| Vendor | Support Level | Contact |
|--------|---------------|---------|
| AWS | Standard Support | via AWS Console |
| Epic | App Orchard Support | appmarket@epic.com |

---

## 10. Plan Maintenance

### 10.1 Review Triggers

This plan must be reviewed when:
- Infrastructure changes occur
- New critical services are added
- After any DR test or real incident
- Annually at minimum

### 10.2 Version History

| Version | Date | Changes | Approved By |
|---------|------|---------|-------------|
| 1.0 | January 2026 | Initial release | Mitchell Fusillo |
| 1.1 | February 2026 | Added AWS resource ARNs, contact information, test schedule dates | Mitchell Fusillo |

---

## Appendix A: Quick Reference Card

### Emergency Contacts
| Role | Name | Phone | Email |
|------|------|-------|-------|
| Operations Lead | Mitchell Fusillo | 716-909-8567 | mitch@fuscodigital.com |
| Security Lead | Mitchell Fusillo | 716-909-8567 | mitch@fuscodigital.com |
| AWS Support | - | - | via Console |

### Key AWS Resources
| Resource | ARN/ID | Region |
|----------|--------|--------|
| Production RDS | `arn:aws:rds:us-east-2:179678238031:db:healthprep-db` | us-east-2 |
| Production ECS Cluster | `arn:aws:ecs:us-east-2:179678238031:cluster/healthprep-service` | us-east-2 |
| DR RDS Replica | Not configured (recommended for production) | - |
| S3 Document Bucket | `health-prep-document-1771` | us-east-2 |

### Secrets Manager Resources
| Secret | ARN |
|--------|-----|
| DATABASE_URL | `arn:aws:secretsmanager:us-east-2:179678238031:secret:healthprep/DATABASE_URL-sy5E8L` |
| SESSION_SECRET | `arn:aws:secretsmanager:us-east-2:179678238031:secret:healthprep/SESSION_SECRET-RDk8Fq` |
| ENCRYPTION_KEY | `arn:aws:secretsmanager:us-east-2:179678238031:secret:healthprep/ENCRYPTION_KEY-l0r48U` |
| SECRET_KEY | `arn:aws:secretsmanager:us-east-2:179678238031:secret:healthprep/SECRET_KEY-c3bm7T` |
| FROM_EMAIL | `arn:aws:secretsmanager:us-east-2:179678238031:secret:healthprep/FROM_EMAIL-5liQCf` |
| STRIPE_SECRET_KEY | `arn:aws:secretsmanager:us-east-2:179678238031:secret:healthprep/STRIPE_SECRET_KEY-nQlPex` |
| RESEND_API_KEY | `arn:aws:secretsmanager:us-east-2:179678238031:secret:healthprep/RESEND_API_KEY-yp5Uf6` |
| P_KEY_2025_08_A | `arn:aws:secretsmanager:us-east-2:179678238031:secret:healthprep/P_KEY_2025_08_A-eQ5zxs` |
| NP_KEY_2025_08_A | `arn:aws:secretsmanager:us-east-2:179678238031:secret:healthprep/NP_KEY_2025_08_A-GevpZ3` |

### Recovery Runbook Links
- [Database Recovery Runbook]
- [Application Failover Runbook]
- [Full DR Activation Runbook]
