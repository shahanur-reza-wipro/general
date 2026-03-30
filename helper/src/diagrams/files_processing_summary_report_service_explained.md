# Files Processing Summary Report Service – Flow

This document explains how `FilesProcessingSummaryReportService` works end-to-end.

## Purpose

`FilesProcessingSummaryReportService` generates and emails the daily consolidated CSV summary for:
- statements
- assignment letters
- dunning letters

It also:
- waits for request queues to drain
- checks OpenText processing completion
- fetches per-request status from OpenText
- queues statement updates back to SQS
- triggers OpenText cleanup

---

## High-level flow

1. `send_report(submission_id)` starts.
2. It resolves submission IDs by type (`statement`, `assignment`, `dunning`).
3. It checks pending SQS request messages for all three types.
   - If any are pending, it returns early.
4. It calculates total documents in AWS (by type).
   - Uses date+submission matching first.
   - Falls back to submission-only counting when date filter returns zero.
5. If total documents are zero, it deletes the summary scheduler and exits.
6. For each type with AWS records, it checks OpenText `totalProcessed`.
   - If OpenText hasn’t caught up, it returns early.
7. When all complete, it builds consolidated status data:
   - Finds request IDs for each type
   - Calls OpenText `requestStatus`
   - Normalizes status + failure reason
   - Merges into one row per IPR
8. Generates CSV and sends email.
9. Deletes summary scheduler rule.
10. Queues statement update messages (statement status only) to statements SQS.
11. Calls OpenText cleanup request.
12. Returns success message.

---

## Mermaid flowchart

```mermaid
graph TD;
   A["send_report(submission_id)"] --> B["_resolve_submission_ids(report_run_id, today)<br/>_normalize_submission_id_rows(...)"];
   B --> C["get_total_pending_request_messages()<br/>SQSHelper.get_sqs_message_count() x3"];

   C -->|"Any pending > 0"| C1["Return: still processing requests"];
   C -->|"No pending"| D["get_total_documents_in_aws(today)<br/>statement/assignment/dunning repository count methods"];

   D -->|"All totals == 0"| D1["file_processing_status_report_scheduler_service.delete_schedule_rule(...)<br/>Return: no summary report"];
   D -->|"Any total > 0"| E["get_total_processed_for_document_type(type)<br/>get_total_requests_submitted(type, sid)<br/>get_total_processed_from_opentext(...)"];

   E -->|"Any type not complete"| E1["Return: OpenText still processing"];
   E -->|"All complete"| F["get_report() -> get_processing_statuses()"];

   F --> F1["get_document_status_map(type)<br/>get_document_request_ids(type)"];
   F1 --> F2["get_request_status_from_opentext(request_id, type)<br/>get_opentext_response(...)"];
   F2 --> F3["parse_request_status_response()<br/>extract_processing_status()<br/>extract_failure_reason()<br/>merge_status(...)"];
   F3 --> G["Utility.generate_csv(...) in get_report()"];

   G --> H["notification_service.send_email_with_attachment(...)"];
   H --> I["file_processing_status_report_scheduler_service.delete_schedule_rule(...)"];
   I --> J["queue_for_statement_update_from_open_text_response()<br/>send_to_sqs(...)"];
   J --> K["cleanup_opentext()<br/>get_opentext_response(...)"];
   K --> L["Return success"];

   classDef start fill:#0f172a,stroke:#334155,stroke-width:1px,color:#f8fafc;
   classDef process fill:#e0f2fe,stroke:#0284c7,stroke-width:1px,color:#0c4a6e;
   classDef decision fill:#fef3c7,stroke:#f59e0b,stroke-width:1px,color:#78350f;
   classDef wait fill:#ffedd5,stroke:#f97316,stroke-width:1px,color:#7c2d12;
   classDef error fill:#fee2e2,stroke:#ef4444,stroke-width:1px,color:#7f1d1d;
   classDef success fill:#dcfce7,stroke:#22c55e,stroke-width:1px,color:#14532d;

   class A start;
   class B,D,F,F1,F2,F3,G,H,I,J,K process;
   class C,E decision;
   class C1,E1,D1 wait;
   class L success;
```

---

## Key decision points

- Queue guard: summary only starts when all request queues are empty.
- AWS totals guard: if no records exist, summary is skipped.
- OpenText completion guard: summary waits until OpenText processed totals match.
- Type-specific handling:
  - statement rows are also queued for post-processing update.
  - assignment/dunning are included in CSV but not sent to statement update queue.

---

## Key methods involved

- `send_report()`
- `_resolve_submission_ids()`
- `get_total_pending_request_messages()`
- `get_total_documents_in_aws()`
- `get_total_processed_for_document_type()`
- `get_total_processed_from_opentext()`
- `get_processing_statuses()`
- `get_document_request_ids()`
- `get_request_status_from_opentext()`
- `parse_request_status_response()`
- `queue_for_statement_update_from_open_text_response()`
- `cleanup_opentext()`
