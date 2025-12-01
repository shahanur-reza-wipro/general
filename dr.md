
# Disaster Recovery (DR) Plan – EKS-Based Application (AWS)

## 1. Document Overview

### 1.1 Purpose
This Disaster Recovery Plan outlines strategies, procedures, and responsibilities to restore the production application deployed in **Amazon EKS**, along with dependent AWS services such as **RDS, S3, SQS, ElastiCache, Route 53, and IAM**.

### 1.2 Scope
- **In Scope:** Production EKS workloads, platform services, AWS-managed databases, message queues, object storage, internal APIs.
- **Out of Scope:** End-user devices, office networks, on-prem systems.

### 1.3 Audience
Cloud Engineering, SRE, DevOps, Application Engineering, Incident Response, and Security teams.

### 1.4 Ownership
- **Owner:** Cloud Platform Team  
- **Review Frequency:** Every 6 months or after major infrastructure change.

---

## 2. System Overview

### 2.1 High-Level Architecture Diagram (Mermaid)

```mermaid
flowchart LR
    Users((Users)) --> CDN[CloudFront / Route 53]
    CDN --> ALB[ALB Ingress Controller]

    subgraph EKS Cluster (prod-eks-eu-west-2)
        API[Web API Deployment]
        Worker[Worker Deployment]
        ESO[External Secrets Operator]
        Ingress[Ingress Controller]
    end

    ALB --> API
    API --> RDS[(Aurora PostgreSQL - Multi-AZ)]
    API --> Redis[(ElastiCache Redis)]
    Worker --> SQS[(SQS Queue + DLQ)]
    API --> S3[(S3 Bucket with Versioning)]
```

### 2.2 Component Inventory

| Component | Type | AWS Service | Region | Criticality | Notes |
|----------|------|-------------|--------|-------------|-------|
| EKS Cluster | Stateless | Amazon EKS | eu-west-2 | Critical | Cluster name: `prod-eks-eu-west-2` |
| Web API | Stateless | Deployment on EKS | eu-west-2 | High | 4 replicas, HPA enabled |
| Worker Service | Stateless | Deployment on EKS | eu-west-2 | High | SQS consumer |
| Database | Stateful | Aurora PostgreSQL | eu-west-2 | Critical | PITR + Multi-AZ |
| Cache | Stateful (volatile) | ElastiCache Redis | eu-west-2 | Medium | Recreated in DR |
| Message Queue | Stateful-ish | SQS | eu-west-2 | High | DLQ configured |
| Object Storage | Stateful | S3 | eu-west-2 | Medium | Bucket: `prod-app-data` |
| Secrets | N/A | Secrets Manager | eu-west-2 | High | ESO syncs to K8s |

---

## 3. DR Objectives

### 3.1 Business Impact
The application supports operational and customer-facing workflows. Downtime > 4 hours severely affects operations and revenue.

### 3.2 RTO & RPO

| Component | RTO | RPO | Notes |
|----------|-----|-----|-------|
| Full System | 4 hours | 15 minutes | Business requirement |
| Aurora DB | 4 hours | 5 minutes | PITR enabled |
| EKS Workloads | 2 hours | N/A | Stateless |
| S3 | 24 hours | 1 hour | Versioning |
| SQS | 4 hours | 0 minutes | DLQ for replay |

---

## 4. DR Strategy

### 4.1 Regions
- **Primary:** eu-west-2 (London)  
- **DR:** eu-west-1 (Ireland)  

### 4.2 EKS Strategy
- EKS cluster recreated in DR from Terraform.
- Node groups use identical instance types.
- Images stored in ECR with cross-region replication enabled.

### 4.3 Data Strategy
- **Aurora:** Cross-region manual snapshot restore during DR.
- **S3:** Optional CRR to DR bucket.
- **SQS:** Rehydration possible from DLQ.
- **Redis:** Recreated on failover.

### 4.4 Secrets & Configuration
- All secrets in Secrets Manager using KMS.
- DR region has identical secrets replicated via IaC.
- External Secrets Operator syncs into EKS DR cluster.

### 4.5 DNS & Networking
- Route 53 failover routing.
- DR ALB registered as failover target.

---

## 5. Recovery Scenarios & Procedures

### 5.1 Single AZ Failure
- Workloads automatically rescheduled.
- RDS Multi-AZ failover handled by AWS.
- No human action required unless alerts escalate.

---

### 5.2 EKS Cluster Failure (Primary Region Healthy)

Steps:
1. Rebuild cluster via Terraform: `terraform apply -target=module.eks`
2. Recreate node groups.
3. Deploy platform add-ons:  
   - AWS CNI  
   - ALB ingress controller  
   - ESO  
   - Cluster Autoscaler  
4. Deploy workloads via Helm or ArgoCD.
5. Validate service availability.

---

### 5.3 Region Failure – DR Region Activation

Steps:
1. Declare DR incident.
2. Promote DR Aurora from snapshot / cross-region replica.
3. Provision DR EKS using Terraform.
4. Deploy secrets via ESO.
5. Deploy workloads via CI/CD or GitOps.
6. Validate application endpoints.
7. Switch Route 53 DNS to DR ALB.
8. Notify stakeholders.

---

### 5.4 Data Corruption

Steps:
1. Freeze writes / enable maintenance mode.
2. Identify corruption timestamp.
3. Restore Aurora to new instance using PITR.
4. Update application connection strings.
5. Validate data and restart traffic.

---

## 6. Runbooks

### 6.1 DR Failover to eu-west-1

1. Validate outage via CloudWatch, AWS Health Dashboard.
2. Promote DR DB.
3. Deploy DR EKS cluster via Terraform.
4. Deploy platform-level components.
5. Deploy microservices.
6. Switch DNS.
7. Confirm with smoke tests.

---

## 7. Responsibilities

| Role | Person/Team | Description |
|------|--------------|-------------|
| Incident Commander | SRE Lead | Owns DR event |
| Cloud Engineer | Platform Team | Infra rebuild |
| DB Engineer | Data Team | Aurora restore/promotion |
| App Owner | Engineering | Functional validation |
| Comms Lead | Business | Stakeholder communication |

---

## 8. DR Testing

### 8.1 Types
- Tabletop simulation  
- DB restore test  
- Full DR region failover (annual)

### 8.2 Evidence
Each DR test recorded with:
- Date  
- Duration  
- Actual RTO/RPO  
- Failures & follow-ups  

---

## 9. Risks & Limitations

- Third-party integrations may not support multi-region.
- DR region may have reduced instance availability.
- Some non-critical services not replicated.

---

## 10. Appendices

### 10.1 Latest Architecture Diagram
See Section 2.1.

### 10.2 AWS Resource Inventory
Export available via IaC state files and AWS Config.

---

