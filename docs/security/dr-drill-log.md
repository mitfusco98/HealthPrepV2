# HealthPrep Disaster Recovery Drill Log

**Document Purpose:** Record all DR test executions with dates, results, and lessons learned for HITRUST compliance evidence.

**Related Document:** `/docs/BUSINESS_CONTINUITY_PLAN.md` Section 6

---

## Drill Log

### Monthly Backup Verification

| Date | Performed By | Result | Notes | Issues Found |
|------|--------------|--------|-------|--------------|
| 2026-02-03 | Mitchell Fusillo | PASS | 7 daily snapshots verified (Jan 29 - Feb 3), all status "available" | None |

**February 2026 Drill Details:**
- **Snapshots Verified:**
  - rds:healthprep-db-2026-01-29-01-17 (available)
  - rds:healthprep-db-2026-01-29-08-23 (available)
  - rds:healthprep-db-2026-01-30-08-23 (available)
  - rds:healthprep-db-2026-01-31-08-23 (available)
  - rds:healthprep-db-2026-02-01-08-23 (available)
  - rds:healthprep-db-2026-02-02-08-23 (available)
  - rds:healthprep-db-2026-02-03-08-23 (available)
- **Backup Schedule:** Daily at ~08:23 UTC
- **Retention:** 7 days confirmed

**Verification Checklist:**
- [x] Confirmed automated RDS snapshots are completing
- [ ] Verified snapshot integrity via test restore to non-production
- [ ] Checked backup metrics in CloudWatch
- [x] Reviewed backup failure alerts (none expected)
- [ ] Documented restore time

---

### Quarterly Database Restore Drill

| Date | Performed By | Restore Time | RTO Target | Result | Notes |
|------|--------------|--------------|------------|--------|-------|
| | | | 4 hours | | |

**Drill Procedure:**
1. Select RDS snapshot from last 7 days
2. Restore to test environment using AWS CLI or Console
3. Measure time from restore initiation to application connectivity
4. Verify data integrity:
   - [ ] Patient record counts match
   - [ ] Recent audit logs present
   - [ ] Organization data intact
5. Test application against restored database
6. Delete test resources after verification
7. Document results in this log

**AWS CLI Command Reference:**
```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier healthprep-db \
  --target-db-instance-identifier healthprep-dr-test \
  --restore-time "YYYY-MM-DDTHH:MM:SSZ"
```

---

### Semi-Annual Application Failover Test

| Date | Performed By | Failover Time | RTO Target | Result | Notes |
|------|--------------|---------------|------------|--------|-------|
| | | | 4 hours | | |

**Drill Procedure:**
1. Deploy previous task definition revision to verify rollback capability
2. Verify ECS service stability after rollback
3. Test all critical endpoints:
   - [ ] Authentication
   - [ ] Patient data access
   - [ ] Document processing
   - [ ] Epic FHIR sync (sandbox)
4. Document failover duration
5. Restore current version after test

**AWS CLI Command Reference:**
```bash
aws ecs update-service \
  --cluster healthprep-service \
  --service healthprep-api \
  --task-definition healthprep-api:PREVIOUS_REVISION
```

---

### Annual Full DR Simulation

| Date | Performed By | Total Recovery Time | RTO Target | Result | Notes |
|------|--------------|---------------------|------------|--------|-------|
| | | | 4 hours | | |

**Drill Procedure:**
1. Simulate primary region failure scenario
2. Execute full recovery procedure:
   - [ ] Database restore from snapshot
   - [ ] Application redeployment
   - [ ] Configuration verification
   - [ ] Secrets Manager access verification
3. Verify all services operational
4. Document total recovery time
5. Conduct post-drill review meeting
6. Update BCP based on lessons learned

---

## Lessons Learned

### [Date] - [Drill Type]
**Issue:** 
**Root Cause:** 
**Remediation:** 
**Status:** 

---

## Next Scheduled Drills

| Drill Type | Scheduled Date | Responsible Party | Status |
|------------|----------------|-------------------|--------|
| Monthly Backup Verification | February 2026 | Mitchell Fusillo | Complete |
| Monthly Backup Verification | March 2026 | Mitchell Fusillo | Pending |
| Quarterly Database Restore | March 2026 (Q1) | Mitchell Fusillo | Pending |
| Semi-Annual Failover | June 2026 (Q2) | Mitchell Fusillo | Pending |
| Annual Full DR Simulation | Q4 2026 | Mitchell Fusillo | Pending |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | February 2026 | HealthPrep Operations | Initial template |
| 1.1 | 2026-02-03 | Mitchell Fusillo | Recorded first monthly backup verification drill |
