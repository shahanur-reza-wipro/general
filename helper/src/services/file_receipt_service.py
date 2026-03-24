from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from data_access_layer import RunControl, RunBatch
from data_access_layer import Database
from utilities.coniguration import Configuration
from utilities.utility import Utility
from .notification_service import NotificationService
from repositories import RunControlRepository, RunBatchRepository
import logging

log = logging.getLogger()


class FileReceiptService:

    def __init__(self):
        self.notification_service = NotificationService()
        self.run_control_repository = RunControlRepository()
        self.run_batch_repository = RunBatchRepository()
        self.file_type = None
        self.configuration = Configuration()
        self.hasFileProcessedPreviously = False

    def notify(self, file_name):
        self.file_type = Utility.get_file_content_type(file_name)
        current_date = datetime.today().date()
        run_control = self.get_run_control(current_date, file_name)
        if run_control:
            notification_result = self.send_notification(run_control)
            return notification_result
        return None

    def send_notification(self, run_control):
        template_args = {}
        try:
            now = datetime.now(ZoneInfo("Europe/London"))
        except ZoneInfoNotFoundError:
            # Fallback to UTC+0/+1 offset when tzdata is unavailable (e.g. Windows without tzdata)
            now = datetime.now(timezone.utc)
        notification_result = None
        template_args["date"] = now.strftime("%d/%m/%Y")
        template_args["time"] = now.strftime("%H:%M")
        template_args["env"] = self.configuration.env

        if self.hasFileProcessedPreviously:
            run_batch = self.run_batch_repository.get_all()[0]
            if (
                run_batch.DebtorFileName is None
                or run_batch.TransactionFileName is None
            ):
                return

        # Always persist the run_control to DB so partial state (single file received)
        # is saved and can be found when the second file arrives.
        run_control = self.run_control_repository.upsert(run_control)

        # Only send the receipt notification email once both files are present.
        if (
            run_control.DebtorFileName
            and run_control.TransactionFileName
            and (
                run_control.HasFileReceiptNotified is None
                or run_control.HasFileReceiptNotified is False
            )
        ) or self.hasFileProcessedPreviously:

            template_args["debtor_file_name"] = run_control.DebtorFileName
            template_args["transaction_file_name"] = run_control.TransactionFileName
            notification_result = (
                self.notification_service.send_email(template_args, "FILE_RECEIVED")
                if not self.configuration.isLocal
                else None
            )

            run_control.HasFileReceiptNotified = True
            log.info(f"notification_result: {notification_result}")
            run_control = self.run_control_repository.upsert(run_control)

        return notification_result

    def get_run_control(self, current_date, file_name):
        column_file_name, column_file_processed = (
            self.run_control_repository.COLUMN_MAPPER.get(self.file_type)
        )

        # run_control = (
        #     self.run_control_repository.get_run_control_by_filename_already_processed(
        #         file_name, column_file_name, column_file_processed
        #     )
        # )

        run_controls = (
            self.run_control_repository.get_run_control_by_received_date_and_file_name(
                current_date, file_name
            )
        )

        if run_controls:
            run_control = run_controls[0]
            file_processed_value = getattr(run_control, column_file_processed)
            file_processed = (
                bool(file_processed_value)
                if file_processed_value is not None
                else False
            )

            if file_processed:
                return
        else:
            processed_run_control = self.run_control_repository.get_run_control_by_filename_already_processed(
                file_name, column_file_name, column_file_processed
            )

            if not processed_run_control:
                run_controls = self.run_control_repository.get_run_control_by_received_date(
                    current_date
                )

                if run_controls:
                    run_control = run_controls[0]
                else:
                    run_control = RunControl()
            else:
                self.hasFileProcessedPreviously = True
                run_control = processed_run_control
                run_batches = self.run_batch_repository.get_all()
                run_batch = None
                if run_batches:
                    run_batch = run_batches[0]
                else:
                    run_batch = RunBatch()

                setattr(run_batch, column_file_name, file_name)
                self.run_batch_repository.upsert(run_batch)

        run_control.ReceivedDate = (
            run_control.ReceivedDate if run_control.ReceivedDate else current_date
        )

        self.set_file_name(file_name, run_control)
        return run_control

    def set_file_name(self, file_name, run_control):
        run_control.DebtorFileName = (
            file_name if file_name.startswith("A") else run_control.DebtorFileName
        )

        run_control.TransactionFileName = (
            file_name if file_name.startswith("B") else run_control.TransactionFileName
        )