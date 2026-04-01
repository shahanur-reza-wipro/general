import datetime
import logging

from repositories import DunningLetterRepository

log = logging.getLogger()


class DunningLetterResponseService:

    def __init__(self):
        self.dunning_letter_repository = DunningLetterRepository()

    def update_dunnings_for_open_text_response(self, ipr_status_list, submission_id):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        dunning_letters = []

        for ipr_status in ipr_status_list:
            ipr = ipr_status["IPR"]
            processing_status = ipr_status["Dunning Processing Status"]
            reason_for_failure = ipr_status["Reason For Failure"]

            dunning_letter = self.dunning_letter_repository.get_dunning_by_opentext_ipr_and_date(
                ipr,
                today,
                submission_id,
            )

            if dunning_letter is not None:
                if processing_status is not None:
                    dunning_letter.ProcessingStatus = processing_status

                if reason_for_failure is not None:
                    dunning_letter.ReasonForFailure = reason_for_failure

                dunning_letters.append(dunning_letter)
            else:
                log.info(f"dunning letter was not found for {submission_id}")

        unique_dunning_letters = list({item.ID: item for item in dunning_letters}.values())

        result = self.dunning_letter_repository.upsert(unique_dunning_letters)

        log_message = f"{len(result)} dunning letters have been updated successfully"
        log.info(log_message)

        return log_message