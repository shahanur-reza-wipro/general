import datetime
import logging

from repositories import AssignmentLetterRepository

log = logging.getLogger()


class AssignmentLetterResponseService:

    def __init__(self):
        self.assignment_letter_repository = AssignmentLetterRepository()

    def update_assignments_for_open_text_response(self, ipr_status_list, submission_id):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        assignment_letters = []

        for ipr_status in ipr_status_list:
            ipr = ipr_status["IPR"]
            processing_status = ipr_status["Assignment Processing Status"]
            reason_for_failure = ipr_status["Reason For Failure"]

            assignment_letter = self.assignment_letter_repository.get_assignment_by_opentext_ipr_and_date(
                ipr,
                today,
                submission_id,
            )

            if assignment_letter is not None:
                if processing_status is not None:
                    assignment_letter.ProcessingStatus = processing_status

                if reason_for_failure is not None:
                    assignment_letter.ReasonForFailure = reason_for_failure

                assignment_letters.append(assignment_letter)
            else:
                log.info(f"assignment letter was not found for {submission_id}")

        unique_assignment_letters = list({item.ID: item for item in assignment_letters}.values())

        result = self.assignment_letter_repository.upsert(unique_assignment_letters)

        log_message = f"{len(result)} assignment letters have been updated successfully"
        log.info(log_message)

        return log_message