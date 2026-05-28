# CBIF-DSS-APP High Level Design (HLD)

## 1. Purpose
This document describes the high level design of the DSS application under src. It provides a clear view of architecture, component responsibilities, integration boundaries, runtime data flow, and non-functional design expectations.

## 2. Scope
In scope:
- File ingestion and validation for debtor and transaction extract files
- Statement, assignment letter, and dunning letter orchestration
- OpenText request submission and response update processing
- Reporting and notification workflows
- Core data persistence and repository interactions

Out of scope:
- Detailed low-level class design and per-method behavior
- Infrastructure-as-code implementation details outside current deployment configs
- UI concerns (service is backend/event driven)

## 3. Architecture Style
The solution follows a layered, event-driven architecture:
- Event sources: S3 object events and EventBridge schedules
- Compute: AWS Lambda handlers
- Domain layer: services and handler chains
- Data access: repositories and SQLAlchemy database abstraction
- Messaging: SQS queues for asynchronous pipeline stages
- Integrations: OpenText APIs, Secrets Manager, SES, SNS

## 4. System Context
```mermaid
%%{init: {'theme': 'base', 'themeVariables': {
'primaryColor': '#e8f1ff',
'primaryTextColor': '#0b1f3a',
'primaryBorderColor': '#3b82f6',
'lineColor': '#5b6b81',
'secondaryColor': '#e6fffb',
'tertiaryColor': '#fff4e6',
'fontFamily': 'Segoe UI'
}}}%%
flowchart LR
    S3[(Amazon S3 Extract Files)] --> L1[Lambda filedataingestor]
  L1 --> SNS1[SNS File Received Notification]
    L1 --> FS[DebtorService and TransactionService]
    FS --> RV[Record-level validation complete]
    RV --> DB[(PostgreSQL)]
    RV --> FPS[FileProcessedService]
    FPS --> SNS2[SNS Files Processing Notification]
    FPS --> SCH[EventBridge Schedule Creation]

    FPS --> Q1[(SQS Orchestrator Queue)]
    Q1 --> L2[Lambda statementvalidator]
    L2 --> SV[StatementValidationService]
    SV --> DB
    SV --> Q2[(SQS Requests Queue)]
    Q2 --> L3[Lambda statementrequestsubmitter]
    L3 --> SS[StatementRequestSubmissionService]
    SS --> OT[(OpenText APIs)]
    SS --> DB

    FPS --> QA1[(SQS Assignment Orchestrator Queue)]
    QA1 --> LA1[Lambda assignmentlettervalidator]
    LA1 --> ASV[AssignmentLetterValidationService]
    ASV --> DB
    ASV --> QA2[(SQS Assignment Requests Queue)]
    QA2 --> LA2[Lambda assignmentletterrequestsubmitter]
    LA2 --> ASS[AssignmentLetterSubmissionService]
    ASS --> OT
    ASS --> DB

    FPS --> QD1[(SQS Dunning Orchestrator Queue)]
    QD1 --> LD1[Lambda dunninglettervalidator]
    LD1 --> DSV[DunningLetterValidationService]
    DSV --> DB
    DSV --> QD2[(SQS Dunning Requests Queue)]
    QD2 --> LD2[Lambda dunningletterrequestsubmitter]
    LD2 --> DSS[DunningLetterSubmissionService]
    DSS --> OT
    DSS --> DB

    SCH --> EB[(EventBridge)]
    EB --> L4[Lambda filesprocessedreportgenerator]
    EB --> L5[Lambda filessummaryreportgenerator]
    L4 --> RPT1[FilesProcessingStatusReportService]
    L5 --> RPT2[FilesProcessingSummaryReportService]
    RPT2 --> Q3[(SQS Statements Queue)]
    RPT2 --> Q4[(SQS Assignments Queue)]
    RPT2 --> Q5[(SQS Dunnings Queue)]
    Q3 --> L6[Lambda opentextresponseupdater]
    Q4 --> L6
    Q5 --> L6
    L6 --> RS[Response Services<br/>StatementResponseService<br/>AssignmentLetterResponseService<br/>DunningLetterResponseService]
    RS --> DB
    RPT1 --> SES[(SES)]
    RPT2 --> SES

    classDef ingest fill:#e8f1ff,stroke:#3b82f6,color:#0b1f3a,stroke-width:1.5px;
    classDef service fill:#e6fffb,stroke:#14b8a6,color:#0b3b35,stroke-width:1.5px;
    classDef queue fill:#fff4e6,stroke:#f59e0b,color:#4a3412,stroke-width:1.5px;
    classDef data fill:#ecfdf3,stroke:#22c55e,color:#0f3d23,stroke-width:1.5px;
    classDef integration fill:#fdf2f8,stroke:#ec4899,color:#4a1330,stroke-width:1.5px;

    class L1,L2,L3,LA1,LA2,LD1,LD2,L4,L5,L6 ingest;
    class FS,RV,FPS,SCH,SV,SS,ASV,ASS,DSV,DSS,RPT1,RPT2,RS service;
    class Q1,Q2,QA1,QA2,QD1,QD2,Q3,Q4,Q5 queue;
    class DB data;
    class S3,OT,EB,SES,SNS1,SNS2 integration;
```

## 5. Logical Component View
```mermaid
%%{init: {'theme': 'base', 'themeVariables': {
'primaryColor': '#e8f1ff',
'primaryTextColor': '#0b1f3a',
'primaryBorderColor': '#3b82f6',
'lineColor': '#5b6b81',
'secondaryColor': '#e6fffb',
'tertiaryColor': '#fff4e6',
'fontFamily': 'Segoe UI'
}}}%%
flowchart TB
    subgraph E[Lambda Entrypoints]
      L1[filedataingestor]
      L2[statementvalidator]
      L3[statementrequestsubmitter]
      L4[assignmentlettervalidator]
      L5[assignmentletterrequestsubmitter]
      L6[dunninglettervalidator]
      L7[dunningletterrequestsubmitter]
      L8[opentextresponseupdater]
      L9[filesprocessedreportgenerator]
      L10[filessummaryreportgenerator]
      L11[sftpoperation]
      L12[dssdboperation]
    end

    subgraph S[Services]
      S1[FileReceiptService]
      S2[FileValidationService]
      S3[RecordValidationService]
      S4[DebtorService]
      S5[TransactionService]
      S6[FileProcessedService]
      S7[StatementOrchestrationService]
      S8[AssignmentLetterOrchestrationService]
      S9[DunningLetterOrchestrationService]
      S10[StatementValidationService]
      S11[AssignmentLetterValidationService]
      S12[DunningLetterValidationService]
      S13[StatementRequestSubmissionService]
      S14[AssignmentLetterSubmissionService]
      S15[DunningLetterSubmissionService]
      S16[StatementResponseService]
      S17[AssignmentLetterResponseService]
      S18[DunningLetterResponseService]
      S19[FilesProcessingStatusReportService]
      S20[FilesProcessingSummaryReportService]
      S21[NotificationService]
      S22[FilesProcessingStatusReportSchedulerService]
    end

    subgraph Q[Queues]
      Q1[Statement Orchestrator Queue]
      Q2[Assignment Orchestrator Queue]
      Q3[Dunning Orchestrator Queue]
      Q4[Statement Requests Queue]
      Q5[Assignment Requests Queue]
      Q6[Dunning Requests Queue]
      Q7[Statements Queue]
      Q8[Assignments Queue]
      Q9[Dunnings Queue]
    end

    subgraph R[Repositories]
      R1[RunControlRepository]
      R2[RunBatchRepository]
      R3[DebtorRepository]
      R4[TransactionRepository]
      R5[StatementRepository]
      R6[StatementRequestRepository]
      R7[AssignmentLetterRepository]
      R8[AssignmentLetterRequestRepository]
      R9[DunningLetterRepository]
      R10[DunningLetterRequestRepository]
    end

    subgraph D[Data Layer]
      D1[Database Engine and Session]
      D2[ORM Models]
    end

    subgraph U[Utilities and Integrations]
      U1[Configuration]
      U2[SecretManager]
      U3[SQS and SNS and SES Helpers]
      U4[SchemaManager and FixedLengthFileReader]
      U5[EventBridge]
      U6[OpenText APIs]
      U7[Amazon S3]
    end

    U7 --> L1
    L11 --> U7
    L1 --> S1 --> S4
    L1 --> S1 --> S5
    S4 --> S2
    S4 --> S3
    S5 --> S2
    S5 --> S3
    S4 --> S6
    S5 --> S6

    S6 --> S7 --> Q1 --> L2 --> S10 --> Q4 --> L3 --> S13 --> U6
    S6 --> S8 --> Q2 --> L4 --> S11 --> Q5 --> L5 --> S14 --> U6
    S6 --> S9 --> Q3 --> L6 --> S12 --> Q6 --> L7 --> S15 --> U6

    S20 --> Q7
    S20 --> Q8
    S20 --> Q9
    Q7 --> L8 --> S16
    Q8 --> L8 --> S17
    Q9 --> L8 --> S18

    L9 --> S19 --> S21
    L10 --> S20 --> S21
    S6 --> S22 --> U5

    S4 --> R3
    S5 --> R4
    S6 --> R1
    S6 --> R2
    S10 --> R5
    S10 --> R6
    S11 --> R7
    S11 --> R8
    S12 --> R9
    S12 --> R10
    S13 --> R5
    S13 --> R6
    S14 --> R7
    S14 --> R8
    S15 --> R9
    S15 --> R10
    S16 --> R5
    S17 --> R7
    S18 --> R9
    S19 --> R5
    S20 --> R5

    R1 --> D1
    R2 --> D1
    R3 --> D1
    R4 --> D1
    R5 --> D1
    R6 --> D1
    R7 --> D1
    R8 --> D1
    R9 --> D1
    R10 --> D1
    D1 --> D2
    L12 --> D1

    S2 --> U4
    S3 --> U4
    S6 --> U3
    S13 --> U2
    S14 --> U2
    S15 --> U2
    S19 --> U2
    S20 --> U2
    S21 --> U3
    S22 --> U1

    classDef entry fill:#e8f1ff,stroke:#3b82f6,color:#0b1f3a,stroke-width:1.3px;
    classDef svc fill:#e6fffb,stroke:#14b8a6,color:#0b3b35,stroke-width:1.3px;
    classDef queue fill:#fff4e6,stroke:#f59e0b,color:#4a3412,stroke-width:1.3px;
    classDef repo fill:#fff4e6,stroke:#f59e0b,color:#4a3412,stroke-width:1.3px;
    classDef data fill:#ecfdf3,stroke:#22c55e,color:#0f3d23,stroke-width:1.3px;
    classDef util fill:#fdf2f8,stroke:#ec4899,color:#4a1330,stroke-width:1.3px;

    class L1,L2,L3,L4,L5,L6,L7,L8,L9,L10,L11,L12 entry;
    class S1,S2,S3,S4,S5,S6,S7,S8,S9,S10,S11,S12,S13,S14,S15,S16,S17,S18,S19,S20,S21,S22 svc;
    class Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9 queue;
    class R1,R2,R3,R4,R5,R6,R7,R8,R9,R10 repo;
    class D1,D2 data;
    class U1,U2,U3,U4,U5,U6,U7 util;
```

- Lambda entrypoints:
  - filedataingestor, statementvalidator, statementrequestsubmitter
  - assignment and dunning validator/submitter lambdas
  - filesprocessedreportgenerator, filessummaryreportgenerator, opentextresponseupdater
- Services:
  - FileReceiptService, FileValidationService, RecordValidationService
  - DebtorService, TransactionService
  - StatementValidationService, StatementRequestSubmissionService
  - StatementResponseService, AssignmentLetterResponseService, DunningLetterResponseService
  - Assignment and dunning orchestration/validation/submission services
  - Reporting and notification services
- Repositories:
  - Entity-specific repositories abstract DB operations
  - Run control and run batch repositories coordinate process state
- Data layer:
  - SQLAlchemy engine/session management
  - ORM models for debtor, transaction, statement, request, validations, and run metadata
- Utilities:
  - Configuration, secret manager, queue/email helpers, schema manager, common utility functions

## 6. Primary Runtime Flow (Statement, Assignment, and Dunning)
```mermaid
%%{init: {'theme': 'base', 'themeVariables': {
'fontFamily': 'Segoe UI',
'primaryColor': '#eef4ff',
'primaryTextColor': '#0f172a',
'primaryBorderColor': '#4f46e5',
'secondaryColor': '#ecfeff',
'secondaryTextColor': '#0f172a',
'secondaryBorderColor': '#06b6d4',
'tertiaryColor': '#f0fdf4',
'tertiaryTextColor': '#0f172a',
'tertiaryBorderColor': '#22c55e',
'lineColor': '#64748b',
'signalColor': '#334155',
'signalTextColor': '#0f172a',
'labelBoxBkgColor': '#e2e8f0',
'labelBoxBorderColor': '#94a3b8',
'labelTextColor': '#0f172a',
'actorBkg': '#e0e7ff',
'actorBorder': '#4f46e5',
'actorTextColor': '#0f172a',
'activationBorderColor': '#14b8a6',
'activationBkgColor': '#ccfbf1',
'noteBkgColor': '#fff7ed',
'noteBorderColor': '#fb923c'
}}}%%
sequenceDiagram
    participant S3 as S3
    participant Ingest as filedataingestor
    participant Core as DebtorService and TransactionService
    participant SNS as SNS
    participant EB as EventBridge
  participant FPS as FileProcessedService
    participant DB as PostgreSQL
  participant QSO as Statement Orchestrator Queue
  participant QSVal as statementvalidator
  participant SVal as StatementValidationService
  participant QSR as Statement Requests Queue
  participant SSubmit as statementrequestsubmitter
  participant QAO as Assignment Orchestrator Queue
  participant QAVal as assignmentlettervalidator
  participant AVal as AssignmentLetterValidationService
  participant QAR as Assignment Requests Queue
  participant ASubmit as assignmentletterrequestsubmitter
  participant QDO as Dunning Orchestrator Queue
  participant QDVal as dunninglettervalidator
  participant DVal as DunningLetterValidationService
  participant QDR as Dunning Requests Queue
  participant DSubmit as dunningletterrequestsubmitter
    participant OpenText as OpenText

    S3->>Ingest: [1] ObjectCreated event for A* or B* file
    Ingest->>SNS: [2] Notify file received and processing will start shortly
    Ingest->>Core: [3] Parse and validate file and records
    Core->>DB: [3] Persist debtor and transaction records after record-level validation
    Core->>FPS: [4] Notify file processed for orchestration
    FPS->>SNS: [5] Notify files are being processed
    FPS->>DB: [5] Update run control and processed flags
    FPS->>DB: [6] Store report schedule context for submission_id
    FPS->>EB: [6] Schedule processing status report generation
    FPS->>EB: [6] Schedule summary report generation

  par Statement branch
    FPS->>QSO: [7] Enqueue statement IPR chunks with run_id
    QSO->>QSVal: [8] Queue delivery
    QSVal->>SVal: [8] Apply statement generation conditions
    SVal->>DB: [9] Persist statement validation logs
    SVal->>QSR: [10] Enqueue statement request_id
    QSR->>SSubmit: [11] Queue delivery
    SSubmit->>OpenText: [11] Submit statement base64 XML request
    OpenText-->>SSubmit: [12] Statement submission response
    SSubmit->>DB: [12] Persist statement submission status
  and Assignment branch
    FPS->>QAO: [7] Enqueue assignment IPR chunks with run_id
    QAO->>QAVal: [8] Queue delivery
    QAVal->>AVal: [8] Apply assignment generation conditions
    AVal->>DB: [9] Persist assignment validation logs
    AVal->>QAR: [10] Enqueue assignment request_id
    QAR->>ASubmit: [11] Queue delivery
    ASubmit->>OpenText: [11] Submit assignment base64 request
    OpenText-->>ASubmit: [12] Assignment submission response
    ASubmit->>DB: [12] Persist assignment submission status
  and Dunning branch
    FPS->>QDO: [7] Enqueue dunning IPR chunks with run_id
    QDO->>QDVal: [8] Queue delivery
    QDVal->>DVal: [8] Apply dunning generation conditions
    DVal->>DB: [9] Persist dunning validation logs
    DVal->>QDR: [10] Enqueue dunning request_id
    QDR->>DSubmit: [11] Queue delivery
    DSubmit->>OpenText: [11] Submit dunning base64 request
    OpenText-->>DSubmit: [12] Dunning submission response
    DSubmit->>DB: [12] Persist dunning submission status
  end
```

OpenText response update routing:
1. `opentextresponseupdater` reads messages from statements, assignments, and dunnings queues.
2. It inspects `document_type` in each message.
3. It calls `StatementResponseService` for statement updates.
4. It calls `AssignmentLetterResponseService` for assignment updates.
5. It calls `DunningLetterResponseService` for dunning updates.

Simple flow summary:
1. A debtor or transaction file lands in S3, and filedataingestor starts parsing and validation.
2. filedataingestor sends an SNS notification that files were received and will be processed shortly.
3. DebtorService and TransactionService perform record-level validation and persist valid records in PostgreSQL.
4. FileProcessedService is invoked after record validation completes.
5. FileProcessedService sends another SNS notification indicating files are being processed.
6. FileProcessedService schedules processing status and summary report jobs through EventBridge.
7. FileProcessedService fans out into three parallel tracks and queues IPR chunks with run_id to statement, assignment, and dunning orchestrator queues.
8. A validator lambda for each track consumes the queue and applies generation conditions.
9. Validation results are written to PostgreSQL for traceability.
10. Eligible records are placed on the corresponding requests queue.
11. A submitter lambda per track reads requests and submits payloads to OpenText.
12. OpenText returns responses, and each submitter writes submission status back to PostgreSQL.

## 7. Assignment and Dunning Flows
- Assignment flow:
  - assignment-orchestrator queue triggers lambda_assignment_letter_validator
  - AssignmentLetterValidationService validates eligibility and logs outcomes
  - Validated requests are sent to assignment-requests queue
  - lambda_assignment_letter_request_submitter submits to OpenText and persists results
- Dunning flow:
  - dunning-orchestrator queue triggers lambda_dunning_letter_orchestrator
  - DunningLetterValidationService validates eligibility and logs outcomes
  - Validated requests are sent to dunning-requests queue
  - lambda_dunning_letter_request_submitter submits to OpenText and persists results

Both flows reuse common design patterns:
- Chain-of-responsibility for condition checks
- Repository persistence for request/validation state
- Queue-based decoupling between validation and submission stages

## 8. Lambda and Queue Inventory
The following runtime resources are included in this design.

Lambdas:
- cbif-r-euw2-lmd-dss-sftpoperation-01
- cbif-r-euw2-lmd-dss-filedataingestor-01
- cbif-r-euw2-lmd-dss-statementvalidator-01
- cbif-r-euw2-lmd-dss-statementrequestsubmitter-01
- cbif-r-euw2-lmd-dss-assignmentlettervalidator-01
- cbif-r-euw2-lmd-dss-assignmentletterrequestsubmitter-01
- cbif-r-euw2-lmd-dss-dunninglettervalidator-01
- cbif-r-euw2-lmd-dss-dunningletterrequestsubmitter-01
- cbif-r-euw2-lmd-dss-opentextresponseupdater-01
- cbif-r-euw2-lmd-dss-filesprocessedreportgenerator-01
- cbif-r-euw2-lmd-dss-filessummaryreportgenerator-01
- cbif-r-euw2-lmd-dss-dssdboperation-01

Queues:
- cbif-r-euw2-sqs-dss-orchestrator-01
- cbif-r-euw2-sqs-dss-orchestrator-01-dead-letter
- cbif-r-euw2-sqs-dss-requests-01
- cbif-r-euw2-sqs-dss-requests-01-dead-letter
- cbif-r-euw2-sqs-dss-statements-01
- cbif-r-euw2-sqs-dss-statements-01-dead-letter
- cbif-r-euw2-sqs-dss-assignment-orchestrator-01
- cbif-r-euw2-sqs-dss-assignment-orchestrator-01-dead-letter
- cbif-r-euw2-sqs-dss-assignment-requests-01
- cbif-r-euw2-sqs-dss-assignment-requests-01-dead-letter
- cbif-r-euw2-sqs-dss-assignments-01
- cbif-r-euw2-sqs-dss-assignments-01-dead-letter
- cbif-r-euw2-sqs-dss-dunning-orchestrator-01
- cbif-r-euw2-sqs-dss-dunning-orchestrator-01-dead-letter
- cbif-r-euw2-sqs-dss-dunning-requests-01
- cbif-r-euw2-sqs-dss-dunning-requests-01-dead-letter
- cbif-r-euw2-sqs-dss-dunnings-01
- cbif-r-euw2-sqs-dss-dunnings-01-dead-letter

## 9. Data and State Management
- Primary datastore: PostgreSQL
- State entities include:
  - RunControl and RunBatch for processing lifecycle
  - Debtor and Transaction for canonical ingested records
  - Statement, AssignmentLetter, DunningLetter and their request entities
  - Validation entities for auditability and traceability
- Processing model:
  - File-level checks gate processing
  - Record-level checks isolate invalid items
  - Per-IPR outcomes are logged and persisted

## 10. Deployment View
- Packaging and deployment configuration is defined in deployment/deployment.config.json
- Codebase is organized so common modules can be packaged as layers:
  - repositories
  - data_access_layer
  - services
  - utilities
- Runtime target: Python 3.11 Lambda functions and layers
- Local execution and integration testing rely on LocalStack and local Postgres setup

## 11. Security and Compliance Design
- Secret material and endpoint details are resolved via configuration and secrets abstraction
- Sensitive integration credentials are externalized (not hardcoded in service flow)
- Service-to-service communication uses AWS managed channels (SQS/EventBridge)
- Validation and processing logs provide business traceability for audit support

## 12. Reliability and Scalability Design
- Asynchronous queue boundaries allow horizontal scaling of processing stages
- Idempotent-style upsert patterns reduce duplicate processing impact
- Segmented lambdas isolate failures to a processing stage
- Scheduled reporting gives operational visibility into lag/backlog states

## 13. Observability Design
- Current observability includes log outputs and persistence of validation/report states
- Recommended operational baselines:
  - Queue depth alarms per queue
  - Lambda error and duration alarms
  - DB connection and failed transaction monitoring
  - End-to-end SLA metrics from file arrival to final update

## 14. Known Design Risks
- Full table replacement patterns in some ingestion paths can increase data-loss risk during partial failures
- Broad exception handling in selected modules can hide root causes
- Unit test coverage is currently narrow compared to system breadth

## 15. HLD Decision Summary
- Event-driven asynchronous architecture is retained as the core system pattern
- Layered service and repository model is retained for maintainability
- Validation chain handlers are retained for business-rule extensibility
- Next iteration should prioritize resilience hardening and broader automated test coverage

## 16. References
- src/diagrams/architecture.md
- src/deployment/deployment.config.json
- src/services
- src/repositories
- src/data_access_layer
