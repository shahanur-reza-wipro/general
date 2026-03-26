import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from services.files_processing_summary_report_service import FilesProcessingSummaryReportService


class TestFilesProcessingSummaryReportServiceSendReport(unittest.TestCase):

    def setUp(self):
        self.config = SimpleNamespace(
            isLocal=True,
            requestsQueueName="statement-requests-queue",
            assignmentLetterRequestsQueueName="assignment-requests-queue",
            dunningLetterRequestsQueueName="dunning-requests-queue",
            integrationConfigSecretName="integration-secret",
            statementsQueueName="statements-queue",
            env="dev",
            fileSummaryReportRecipients=["test@example.com"],
            opentextRequestUrl="https://example.com/statement/report",
            opentextAssignmentReportUrl="https://example.com/assignment/report",
            opentextDunningReportUrl="https://example.com/dunning/report",
            opentextUserName="user",
            opentextPassword="pass",
            opentextAuthUrl="https://example.com/auth",
        )

        self.statement_sqs_helper = Mock()
        self.assignment_sqs_helper = Mock()
        self.dunning_sqs_helper = Mock()
        self.statement_update_sqs_helper = Mock()

        self.sqs_helper_patcher = patch(
            "services.files_processing_summary_report_service.SQSHelper",
            side_effect=[
                self.statement_sqs_helper,
                self.assignment_sqs_helper,
                self.dunning_sqs_helper,
                self.statement_update_sqs_helper,
            ],
        )
        self.configuration_patcher = patch("services.files_processing_summary_report_service.Configuration")
        self.secret_manager_patcher = patch("services.files_processing_summary_report_service.SecretManager")
        self.statement_repository_patcher = patch("services.files_processing_summary_report_service.StatementRepository")
        self.statement_request_repository_patcher = patch("services.files_processing_summary_report_service.StatementRequestRepository")
        self.assignment_letter_repository_patcher = patch("services.files_processing_summary_report_service.AssignmentLetterRepository")
        self.assignment_letter_request_repository_patcher = patch("services.files_processing_summary_report_service.AssignmentLetterRequestRepository")
        self.dunning_letter_repository_patcher = patch("services.files_processing_summary_report_service.DunningLetterRepository")
        self.dunning_letter_request_repository_patcher = patch("services.files_processing_summary_report_service.DunningLetterRequestRepository")
        self.notification_service_patcher = patch("services.files_processing_summary_report_service.NotificationService")
        self.scheduler_service_patcher = patch(
            "services.files_processing_summary_report_service.FilesProcessingStatusReportSchedulerService"
        )

        self.mock_sqs_helper_cls = self.sqs_helper_patcher.start()
        self.mock_configuration_cls = self.configuration_patcher.start()
        self.mock_secret_manager_cls = self.secret_manager_patcher.start()
        self.mock_statement_repository_cls = self.statement_repository_patcher.start()
        self.mock_statement_request_repository_cls = self.statement_request_repository_patcher.start()
        self.mock_assignment_letter_repository_cls = self.assignment_letter_repository_patcher.start()
        self.mock_assignment_letter_request_repository_cls = self.assignment_letter_request_repository_patcher.start()
        self.mock_dunning_letter_repository_cls = self.dunning_letter_repository_patcher.start()
        self.mock_dunning_letter_request_repository_cls = self.dunning_letter_request_repository_patcher.start()
        self.mock_notification_service_cls = self.notification_service_patcher.start()
        self.mock_scheduler_service_cls = self.scheduler_service_patcher.start()

        self.addCleanup(self.sqs_helper_patcher.stop)
        self.addCleanup(self.configuration_patcher.stop)
        self.addCleanup(self.secret_manager_patcher.stop)
        self.addCleanup(self.statement_repository_patcher.stop)
        self.addCleanup(self.statement_request_repository_patcher.stop)
        self.addCleanup(self.assignment_letter_repository_patcher.stop)
        self.addCleanup(self.assignment_letter_request_repository_patcher.stop)
        self.addCleanup(self.dunning_letter_repository_patcher.stop)
        self.addCleanup(self.dunning_letter_request_repository_patcher.stop)
        self.addCleanup(self.notification_service_patcher.stop)
        self.addCleanup(self.scheduler_service_patcher.stop)

        self.mock_configuration_cls.return_value.get_config.return_value = self.config
        self.mock_secret_manager_cls.return_value.get_opentext_endpoint.return_value = None

        self.statement_repository = self.mock_statement_repository_cls.return_value
        self.statement_request_repository = self.mock_statement_request_repository_cls.return_value
        self.assignment_letter_repository = self.mock_assignment_letter_repository_cls.return_value
        self.assignment_letter_request_repository = self.mock_assignment_letter_request_repository_cls.return_value
        self.dunning_letter_repository = self.mock_dunning_letter_repository_cls.return_value
        self.dunning_letter_request_repository = self.mock_dunning_letter_request_repository_cls.return_value
        self.notification_service = self.mock_notification_service_cls.return_value
        self.scheduler_service = self.mock_scheduler_service_cls.return_value

        self.statement_sqs_helper.get_sqs_message_count.return_value = 0
        self.assignment_sqs_helper.get_sqs_message_count.return_value = 0
        self.dunning_sqs_helper.get_sqs_message_count.return_value = 0

    def test_send_report_returns_when_any_queue_has_pending_messages(self):
        self.assignment_sqs_helper.get_sqs_message_count.return_value = 3

        service = FilesProcessingSummaryReportService()
        result = service.send_report("run-1")

        self.assertEqual(result, "System is still processing requests for: assignment.")
        self.scheduler_service.delete_schedule_rule.assert_not_called()
        self.notification_service.send_email_with_attachment.assert_not_called()

    def test_send_report_returns_no_summary_when_no_documents_exist(self):
        service = FilesProcessingSummaryReportService()
        service._resolve_submission_ids = Mock(
            return_value={"statement": ["run-1"], "assignment": [], "dunning": []}
        )
        service.get_total_documents_in_aws = Mock(
            return_value={"statement": 0, "assignment": 0, "dunning": 0}
        )

        result = service.send_report("run-1")

        self.assertIn("No summary report to be generated", result)
        self.scheduler_service.delete_schedule_rule.assert_called_once_with(
            self.config.integrationConfigSecretName,
            False,
        )
        self.notification_service.send_email_with_attachment.assert_not_called()

    def test_send_report_sends_summary_email_when_all_types_processed(self):
        service = FilesProcessingSummaryReportService()
        service._resolve_submission_ids = Mock(
            return_value={
                "statement": ["run-1"],
                "assignment": ["run-1"],
                "dunning": ["run-1"],
            }
        )
        service.get_total_documents_in_aws = Mock(
            return_value={"statement": 2, "assignment": 1, "dunning": 1}
        )
        service.get_total_processed_for_document_type = Mock(side_effect=[2, 1, 1])
        service.get_report = Mock(return_value="IPR,Date\n123,2026-03-25")
        service.queue_for_statement_update_from_open_text_response = Mock()
        service.cleanup_opentext = Mock()

        result = service.send_report("run-1")

        self.assertIn("A report has been sent successfully", result)
        self.notification_service.send_email_with_attachment.assert_called_once()
        self.scheduler_service.delete_schedule_rule.assert_called_once_with(
            self.config.integrationConfigSecretName,
            False,
        )
        service.queue_for_statement_update_from_open_text_response.assert_called_once()
        service.cleanup_opentext.assert_called_once()


if __name__ == "__main__":
    unittest.main()
