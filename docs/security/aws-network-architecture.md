# AWS Network Architecture

**Document Purpose:** Technical network architecture documentation for HealthPrep's AWS ECS Fargate deployment, providing HITRUST i1 evidence for network security controls and data flow isolation.

**Related Documents:**
- `/docs/HITRUST_READINESS.md` - HITRUST readiness checklist
- `/docs/BUSINESS_CONTINUITY_PLAN.md` - DR procedures and AWS resource ARNs
- `/docs/security/hitrust-shared-responsibility-matrix.md` - Shared responsibility mapping
- `/docs/DEPLOYMENT_READINESS.md` - Pre-deployment verification

---

## Architecture Overview

HealthPrep uses a multi-tier VPC architecture with public, private, and isolated subnets across two Availability Zones for high availability. All PHI processing occurs in private subnets with no direct internet access.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AWS Region: us-east-2                               │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                        VPC: healthprep-prod-vpc                            │  │
│  │                        CIDR: 10.0.0.0/16                                   │  │
│  │                                                                            │  │
│  │  ┌─────────────────────────────┐  ┌─────────────────────────────┐         │  │
│  │  │   Availability Zone A       │  │   Availability Zone B       │         │  │
│  │  │   (us-east-2a)              │  │   (us-east-2b)              │         │  │
│  │  │                             │  │                             │         │  │
│  │  │  ┌───────────────────────┐  │  │  ┌───────────────────────┐  │         │  │
│  │  │  │ PUBLIC SUBNET         │  │  │  │ PUBLIC SUBNET         │  │         │  │
│  │  │  │ 10.0.1.0/24           │  │  │  │ 10.0.2.0/24           │  │         │  │
│  │  │  │                       │  │  │  │                       │  │         │  │
│  │  │  │  ┌─────────────────┐  │  │  │  │  ┌─────────────────┐  │  │         │  │
│  │  │  │  │   ALB Node      │  │  │  │  │  │   ALB Node      │  │  │         │  │
│  │  │  │  │   (TLS 1.2+)    │  │  │  │  │  │   (TLS 1.2+)    │  │  │         │  │
│  │  │  │  └─────────────────┘  │  │  │  │  └─────────────────┘  │  │         │  │
│  │  │  │                       │  │  │  │                       │  │         │  │
│  │  │  │  ┌─────────────────┐  │  │  │  │                       │  │         │  │
│  │  │  │  │   NAT Gateway   │  │  │  │  │                       │  │         │  │
│  │  │  │  │   (Outbound)    │  │  │  │  │                       │  │         │  │
│  │  │  │  └─────────────────┘  │  │  │  │                       │  │         │  │
│  │  │  └───────────────────────┘  │  │  └───────────────────────┘  │         │  │
│  │  │                             │  │                             │         │  │
│  │  │  ┌───────────────────────┐  │  │  ┌───────────────────────┐  │         │  │
│  │  │  │ PRIVATE SUBNET        │  │  │  │ PRIVATE SUBNET        │  │         │  │
│  │  │  │ 10.0.10.0/24          │  │  │  │ 10.0.20.0/24          │  │         │  │
│  │  │  │                       │  │  │  │                       │  │         │  │
│  │  │  │  ┌─────────────────┐  │  │  │  │  ┌─────────────────┐  │  │         │  │
│  │  │  │  │  ECS Fargate    │  │  │  │  │  │  ECS Fargate    │  │  │         │  │
│  │  │  │  │  Task (App)     │  │  │  │  │  │  Task (App)     │  │  │         │  │
│  │  │  │  │  ┌───────────┐  │  │  │  │  │  │  ┌───────────┐  │  │  │         │  │
│  │  │  │  │  │HealthPrep │  │  │  │  │  │  │  │HealthPrep │  │  │  │         │  │
│  │  │  │  │  │ Container │  │  │  │  │  │  │  │ Container │  │  │  │         │  │
│  │  │  │  │  └───────────┘  │  │  │  │  │  │  └───────────┘  │  │  │         │  │
│  │  │  │  └─────────────────┘  │  │  │  │  └─────────────────┘  │  │         │  │
│  │  │  └───────────────────────┘  │  │  └───────────────────────┘  │         │  │
│  │  │                             │  │                             │         │  │
│  │  │  ┌───────────────────────┐  │  │  ┌───────────────────────┐  │         │  │
│  │  │  │ ISOLATED SUBNET       │  │  │  │ ISOLATED SUBNET       │  │         │  │
│  │  │  │ 10.0.100.0/24         │  │  │  │ 10.0.200.0/24         │  │         │  │
│  │  │  │                       │  │  │  │                       │  │         │  │
│  │  │  │  ┌─────────────────┐  │  │  │  │  ┌─────────────────┐  │  │         │  │
│  │  │  │  │  RDS Primary    │  │  │  │  │  │  RDS Standby    │  │  │         │  │
│  │  │  │  │  PostgreSQL     │  │  │  │  │  │  PostgreSQL     │  │  │         │  │
│  │  │  │  │  (Encrypted)    │  │  │  │  │  │  (Encrypted)    │  │  │         │  │
│  │  │  │  └─────────────────┘  │  │  │  │  └─────────────────┘  │  │         │  │
│  │  │  └───────────────────────┘  │  │  └───────────────────────┘  │         │  │
│  │  │                             │  │                             │         │  │
│  │  └─────────────────────────────┘  └─────────────────────────────┘         │  │
│  │                                                                            │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐   │  │
│  │  │                     VPC Endpoints (Private Link)                    │   │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │  │
│  │  │  │   ECR    │ │   S3     │ │ Secrets  │ │CloudWatch│ │   KMS    │  │   │  │
│  │  │  │          │ │ Gateway  │ │ Manager  │ │  Logs    │ │          │  │   │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │  │
│  │  └────────────────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Network Components

### VPC Configuration

| Parameter | Value |
|-----------|-------|
| VPC Name | healthprep-prod-vpc |
| Region | us-east-2 |
| CIDR Block | 10.0.0.0/16 |
| DNS Hostnames | Enabled |
| DNS Resolution | Enabled |
| Tenancy | Default |

### Subnet Design

| Subnet Type | AZ-A CIDR | AZ-B CIDR | Route Table | Purpose |
|-------------|-----------|-----------|-------------|---------|
| Public | 10.0.1.0/24 | 10.0.2.0/24 | Public RT (IGW) | ALB, NAT Gateway |
| Private | 10.0.10.0/24 | 10.0.20.0/24 | Private RT (NAT) | ECS Fargate tasks |
| Isolated | 10.0.100.0/24 | 10.0.200.0/24 | Isolated RT (none) | RDS PostgreSQL |

### Availability Zones

| Zone | Identifier | Services |
|------|------------|----------|
| AZ-A | us-east-2a | ALB node, NAT Gateway, ECS tasks, RDS primary |
| AZ-B | us-east-2b | ALB node, ECS tasks, RDS standby |

---

## Traffic Flow Diagram

```
                                    INTERNET
                                        │
                                        ▼
                              ┌─────────────────┐
                              │  AWS WAF        │
                              │  (Managed Rules)│
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  Internet       │
                              │  Gateway        │
                              └────────┬────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │           PUBLIC SUBNETS             │
                    │                                      │
                    │  ┌────────────────────────────────┐  │
                    │  │     Application Load Balancer  │  │
                    │  │     - TLS 1.2+ termination     │  │
                    │  │     - HTTPS:443 → HTTP:5000    │  │
                    │  │     - Health checks /health    │  │
                    │  └────────────────┬───────────────┘  │
                    │                   │                  │
                    │  ┌────────────────┴───────────────┐  │
                    │  │     NAT Gateway (Outbound)     │  │
                    │  │     - Epic FHIR API calls      │  │
                    │  │     - Email (Resend API)       │  │
                    │  │     - Payment (Stripe API)     │  │
                    │  └────────────────┬───────────────┘  │
                    └───────────────────│──────────────────┘
                                        │
                    ┌───────────────────┴──────────────────┐
                    │          PRIVATE SUBNETS              │
                    │                                       │
                    │  ┌─────────────────────────────────┐  │
                    │  │      ECS Fargate Service        │  │
                    │  │      - HealthPrep containers    │  │
                    │  │      - Non-root execution       │  │
                    │  │      - Read-only filesystem     │  │
                    │  │      - Port 5000 (Gunicorn)     │  │
                    │  └─────────────────┬───────────────┘  │
                    │                    │                  │
                    │         VPC Endpoints (PrivateLink)   │
                    │  ┌─────┬─────┬─────┬─────┬─────┐      │
                    │  │ ECR │ S3  │Secr │ CW  │ KMS │      │
                    │  └─────┴─────┴─────┴─────┴─────┘      │
                    └────────────────────┬─────────────────-┘
                                         │
                    ┌────────────────────┴─────────────────┐
                    │          ISOLATED SUBNETS             │
                    │                                       │
                    │  ┌─────────────────────────────────┐  │
                    │  │      RDS PostgreSQL             │  │
                    │  │      - Multi-AZ deployment      │  │
                    │  │      - Encryption at rest       │  │
                    │  │      - Port 5432                │  │
                    │  │      - No internet access       │  │
                    │  └─────────────────────────────────┘  │
                    └──────────────────────────────────────┘
```

---

## Security Groups

### ALB Security Group (sg-alb-healthprep)

| Rule Type | Protocol | Port | Source/Destination | Description |
|-----------|----------|------|---------------------|-------------|
| Inbound | HTTPS | 443 | 0.0.0.0/0 | Public HTTPS access |
| Inbound | HTTP | 80 | 0.0.0.0/0 | Redirect to HTTPS |
| Outbound | TCP | 5000 | sg-ecs-healthprep | Forward to ECS tasks |

### ECS Security Group (sg-ecs-healthprep)

| Rule Type | Protocol | Port | Source/Destination | Description |
|-----------|----------|------|---------------------|-------------|
| Inbound | TCP | 5000 | sg-alb-healthprep | ALB health checks and traffic |
| Outbound | TCP | 5432 | sg-rds-healthprep | Database connections |
| Outbound | TCP | 443 | 0.0.0.0/0 | External API calls (Epic, Stripe, Resend) |
| Outbound | TCP | 443 | VPC Endpoints | AWS service access |

### RDS Security Group (sg-rds-healthprep)

| Rule Type | Protocol | Port | Source/Destination | Description |
|-----------|----------|------|---------------------|-------------|
| Inbound | TCP | 5432 | sg-ecs-healthprep | ECS task connections only |
| Outbound | None | - | - | No outbound required |

### VPC Endpoints Security Group (sg-vpce-healthprep)

| Rule Type | Protocol | Port | Source/Destination | Description |
|-----------|----------|------|---------------------|-------------|
| Inbound | TCP | 443 | 10.0.0.0/16 | VPC CIDR access to endpoints |

---

## VPC Endpoints

VPC endpoints ensure AWS service traffic stays within the AWS network, never traversing the public internet.

| Service | Endpoint Type | Purpose |
|---------|---------------|---------|
| com.amazonaws.us-east-2.ecr.api | Interface | ECR API calls |
| com.amazonaws.us-east-2.ecr.dkr | Interface | Docker image pulls |
| com.amazonaws.us-east-2.s3 | Gateway | S3 access (ECR layers, document storage) |
| com.amazonaws.us-east-2.secretsmanager | Interface | Secret retrieval |
| com.amazonaws.us-east-2.logs | Interface | CloudWatch Logs |
| com.amazonaws.us-east-2.kms | Interface | KMS encryption operations |

---

## Network ACLs

### Public Subnet NACL

| Rule # | Type | Protocol | Port Range | Source/Dest | Action |
|--------|------|----------|------------|-------------|--------|
| 100 | Inbound | TCP | 443 | 0.0.0.0/0 | ALLOW |
| 110 | Inbound | TCP | 80 | 0.0.0.0/0 | ALLOW |
| 120 | Inbound | TCP | 1024-65535 | 0.0.0.0/0 | ALLOW |
| * | Inbound | ALL | ALL | 0.0.0.0/0 | DENY |
| 100 | Outbound | TCP | 1024-65535 | 0.0.0.0/0 | ALLOW |
| 110 | Outbound | TCP | 443 | 0.0.0.0/0 | ALLOW |
| * | Outbound | ALL | ALL | 0.0.0.0/0 | DENY |

### Private Subnet NACL

| Rule # | Type | Protocol | Port Range | Source/Dest | Action |
|--------|------|----------|------------|-------------|--------|
| 100 | Inbound | TCP | 5000 | 10.0.1.0/24, 10.0.2.0/24 | ALLOW |
| 110 | Inbound | TCP | 1024-65535 | 0.0.0.0/0 | ALLOW |
| * | Inbound | ALL | ALL | 0.0.0.0/0 | DENY |
| 100 | Outbound | TCP | 443 | 0.0.0.0/0 | ALLOW |
| 110 | Outbound | TCP | 5432 | 10.0.100.0/24, 10.0.200.0/24 | ALLOW |
| 120 | Outbound | TCP | 1024-65535 | 0.0.0.0/0 | ALLOW |
| * | Outbound | ALL | ALL | 0.0.0.0/0 | DENY |

### Isolated Subnet NACL

| Rule # | Type | Protocol | Port Range | Source/Dest | Action |
|--------|------|----------|------------|-------------|--------|
| 100 | Inbound | TCP | 5432 | 10.0.10.0/24, 10.0.20.0/24 | ALLOW |
| * | Inbound | ALL | ALL | 0.0.0.0/0 | DENY |
| 100 | Outbound | TCP | 1024-65535 | 10.0.10.0/24, 10.0.20.0/24 | ALLOW |
| * | Outbound | ALL | ALL | 0.0.0.0/0 | DENY |

---

## Data Flow Paths

### Inbound (User Request)

```
User Browser
    │
    ▼ HTTPS (TLS 1.2+)
AWS WAF ──────────────────────────────► Block malicious requests
    │
    ▼
Internet Gateway
    │
    ▼
Application Load Balancer
    │ TLS terminated, HTTP to target
    ▼
ECS Fargate Task (Port 5000)
    │
    ▼
Gunicorn → Flask Application
    │
    ▼
PostgreSQL (RDS)
```

### Outbound (Epic FHIR Integration)

```
Flask Application
    │
    ▼
ECS ENI (Private Subnet)
    │
    ▼ Route to NAT Gateway
NAT Gateway (Public Subnet)
    │
    ▼ HTTPS
Internet Gateway
    │
    ▼
Epic FHIR API (fhir.epic.com)
```

### Internal (AWS Services)

```
ECS Fargate Task
    │
    ▼ PrivateLink (never leaves AWS)
VPC Endpoint
    │
    ▼
AWS Service (S3, Secrets Manager, KMS, etc.)
```

---

## PHI Data Flow

All Protected Health Information (PHI) follows these isolation rules:

| Data Type | Source | Destination | Encryption | Path |
|-----------|--------|-------------|------------|------|
| Patient Demographics | Epic FHIR | RDS | TLS in-transit, AES-256 at-rest | NAT → Private → Isolated |
| Clinical Documents | Epic FHIR | S3 | TLS in-transit, SSE-S3 at-rest | NAT → Private → VPC Endpoint → S3 |
| Prep Sheets | RDS/Processing | Epic FHIR | TLS in-transit | Private → NAT → Epic |
| Audit Logs | Application | CloudWatch | TLS in-transit, encrypted at-rest | Private → VPC Endpoint → CloudWatch |

**PHI Never Traverses:**
- Public subnets (except encrypted through ALB)
- Internet directly (always via NAT for outbound)
- Unencrypted channels

---

## HITRUST Control Mapping

| HITRUST Control | Implementation | Evidence |
|-----------------|----------------|----------|
| 01.m Network Controls | VPC with security groups, NACLs | This document, AWS Console |
| 01.n Network Segregation | Public/Private/Isolated subnets | Subnet configuration |
| 01.o Network Connection Control | Security groups, NACLs | Security group rules |
| 05.j Network Services | WAF, ALB TLS termination | ALB/WAF configuration |
| 09.m Network Monitoring | VPC Flow Logs, CloudWatch | CloudWatch Logs |
| 10.j Network Encryption | TLS 1.2+ for all external traffic | ALB listener configuration |

---

## Monitoring and Logging

### VPC Flow Logs

| Configuration | Value |
|---------------|-------|
| Destination | CloudWatch Logs |
| Log Group | /aws/vpc/healthprep-prod-vpc |
| Traffic Type | ALL (Accept + Reject) |
| Retention | 365 days |
| Format | Default |

### CloudWatch Alarms

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| High NAT Gateway Errors | ErrorPortAllocation | > 0 | SNS notification |
| Unusual Outbound Traffic | BytesOutToDestination | > 1GB/hour | SNS notification |
| ALB 5xx Errors | HTTPCode_Target_5XX_Count | > 10/min | SNS notification |
| RDS Connection Spike | DatabaseConnections | > 80% max | SNS notification |

---

## Disaster Recovery Network Considerations

### Multi-AZ Design

- ALB spans both AZs for automatic failover
- ECS tasks distributed across AZs
- RDS Multi-AZ with automatic failover
- NAT Gateway in single AZ (cost optimization) with failover plan

### Cross-Region DR (Future)

For cross-region DR, the following would be replicated:
- VPC with identical CIDR structure in us-west-2
- RDS cross-region read replica
- S3 cross-region replication
- Route 53 health checks with failover routing

---

## Compliance Verification Checklist

- [x] All PHI processing in private subnets
- [x] Database in isolated subnets with no internet route
- [x] TLS 1.2+ enforced at ALB
- [x] Security groups follow least-privilege
- [x] VPC Flow Logs enabled
- [x] WAF protecting ALB
- [x] VPC endpoints for AWS service traffic
- [x] Multi-AZ deployment for high availability
- [ ] AWS BAA executed (pending)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-04 | Mitchell Fusillo | Initial network architecture documentation for HITRUST evidence |
