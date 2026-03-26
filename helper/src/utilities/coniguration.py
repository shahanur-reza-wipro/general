from utilities.utility import Utility
from utilities.singleton import singleton
from string import Template
import os


@singleton
class Configuration:
    CONFIGURATION_JSON_FILE = "config.json"
    __config = None

    # isLocal, dbEndpointSecretName, regionName, userName, password, db_host, db_port, db_name
    def __init__(
        self,
        isLocal=False,
        useRDSProxy=False,
        env="",
        dbEndpointSecretName="",
        region="",
        userName="",
        password="",
        dbHost="",
        dbPort="",
        dbName="",
        dataFileType="",
        dataFileNamePattern="",
        statementGenerationConditions=[],
        assignmentLetterGenerationConditions=[],
        dunningLetterGenerationConditions=[],
        fileValidationConditions=[],
        recordValidationConditions=[],
        openTextAuthURL="",
        openTextUserName="",
        openTextPassword="",
        openTextStatementURL="",
        snsArnSecretName="",
        openTextSecretName="",
        opentextAuthUrl="",
        opentextUserName="",
        opentextPassword="",
        opentextStatementUrl="",
        opentextRequestUrl="",
        opentextAssignmentCreateUrl="",
        opentextAssignmentReportUrl="",
        opentextDunningCreateUrl="",
        opentextDunningReportUrl="",
        orchestrationQueueName="",
        requestsQueueName="",
        statementsQueueName="",
        assignmentLetterOrchestratorQueueName="",
        assignmentLetterRequestsQueueName="",
        dunningLetterRequestsQueueName="",
        integrationConfigSecretName="",
        notificationTopicName="",
        fileProcessedReportGeneratorLambdaDetailsSecretName="",
        fileSummaryReportGeneratorLambdaDetailsSecretName="",
        processingReportGenerationAttemptInterval=5,
        summaryReportGenerationAttemptInterval=60,
        fileProcessingReportRecipients=[],
        fileProcessingReportSender="",
        fileSummaryReportRecipients=[],
        fileSummaryReportSender="",
        enableAssignmentLetters=True,
        enableDunningLetters=True,
    ):
        self.isLocal = isLocal
        self.useRDSProxy = useRDSProxy
        self.dbEndpointSecretName = dbEndpointSecretName
        self.region = region
        self.userName = userName
        self.password = password
        self.dbHost = dbHost
        self.dbPort = dbPort
        self.dbName = dbName
        self.dataFileType = dataFileType
        self.dataFileNamePattern = dataFileNamePattern
        self.statementGenerationConditions = statementGenerationConditions
        self.assignmentLetterGenerationConditions = assignmentLetterGenerationConditions
        self.dunningLetterGenerationConditions = dunningLetterGenerationConditions
        self.fileValidationConditions = fileValidationConditions
        self.recordValidationConditions = recordValidationConditions
        self.openTextAuthURL = openTextAuthURL
        self.openTextUserName = openTextUserName
        self.openTextPassword = openTextPassword
        self.openTextStatementURL = openTextStatementURL
        self.snsArnSecretName = snsArnSecretName
        self.openTextSecretName = openTextSecretName
        self.opentextAuthUrl = opentextAuthUrl
        self.opentextUserName = opentextUserName
        self.opentextPassword = opentextPassword
        self.opentextStatementUrl = opentextStatementUrl
        self.opentextRequestUrl = opentextRequestUrl
        self.opentextAssignmentCreateUrl = opentextAssignmentCreateUrl
        self.opentextAssignmentReportUrl = opentextAssignmentReportUrl
        self.opentextDunningCreateUrl = opentextDunningCreateUrl
        self.opentextDunningReportUrl = opentextDunningReportUrl
        self.orchestrationQueueName = orchestrationQueueName
        self.requestsQueueName = requestsQueueName
        self.statementsQueueName = statementsQueueName
        self.assignmentLetterOrchestratorQueueName = assignmentLetterOrchestratorQueueName
        self.assignmentLetterRequestsQueueName = assignmentLetterRequestsQueueName
        self.dunningLetterRequestsQueueName = dunningLetterRequestsQueueName
        self.integrationConfigSecretName = integrationConfigSecretName
        self.notificationTopicName = notificationTopicName
        self.processingReportGenerationAttemptInterval = processingReportGenerationAttemptInterval
        self.summaryReportGenerationAttemptInterval = summaryReportGenerationAttemptInterval
        self.fileProcessingReportRecipients = fileProcessingReportRecipients
        self.fileProcessingReportSender = fileProcessingReportSender
        self.fileSummaryReportRecipients = fileSummaryReportRecipients
        self.fileSummaryReportSender = fileSummaryReportSender
        self.enableAssignmentLetters = enableAssignmentLetters
        self.enableDunningLetters = enableDunningLetters
        self.fileProcessedReportGeneratorLambdaDetailsSecretName = (
            fileProcessedReportGeneratorLambdaDetailsSecretName
        )
        self.fileSummaryReportGeneratorLambdaDetailsSecretName = (
            fileSummaryReportGeneratorLambdaDetailsSecretName
        )
        self.env = env

        config_data = Utility.load_from_json_as_dictionary(self.CONFIGURATION_JSON_FILE)
        self.__dict__.update(config_data)

    def get_config(self):
        env_id = os.getenv("ENV_ID", "")
        environment_name_map = self.__dict__.get("environmentNameMap", {})
        self.env = next(
            (
                name
                for name, ids in environment_name_map.items()
                if env_id in [i.lower() for i in ids]
            ),
            "Unknown",
        )
        for k, v in self.__dict__.items():
            if isinstance(v, str) and "${" in v:
                self.__dict__[k] = Template(v).safe_substitute(os.environ)

        return self