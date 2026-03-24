from datetime import datetime
import asyncio
import http.client
import json
import ssl
import uuid

from repositories import StatementRepository, RunControlRepository
from data_access_layer.models import Debtor, Statement
from utilities import Utility, Configuration, SecretManager
from ..popos import (
    DebtorDetails,
    Transaction,
    TransactionDetails,
    InPaymentInfo,
    Invoice,
    InvoiceFinanceDocumentRoot,
    MetaData,
)
from .statement_generation_handler import (
    StatementRequestedTodayHandler,
    InpaymentDetailsHandler,
    STMFlagHandler,
    StatementRunDayHandler,
    AccountBalanceMinHandler,
    AccountBalanceMatchHandler,
    CreditControllerDetailsHandler,
    DebtorEmailHandler,
    RequestStatementGenerationHandler,
)

class StatementGenerator:
    HANDLER_MAP = {
        "StatementRequestedToday": StatementRequestedTodayHandler,
        "InpaymentDetails": InpaymentDetailsHandler,
        "STMFlag": STMFlagHandler,
        "StatementRunDay": StatementRunDayHandler,
        "AccountBalanceMin": AccountBalanceMinHandler,
        "AccountBalanceMatch": AccountBalanceMatchHandler,
        "CreditControllerDetails": CreditControllerDetailsHandler,
        "DebtorEmail": DebtorEmailHandler,
        "RequestStatementGeneration": RequestStatementGenerationHandler,
    }

    def __init__(self, statement_generation_conditions):
        self.handler_chain = self.build_chain(statement_generation_conditions)
        self.configuration = Configuration().get_config()
        self.debtor_queue = asyncio.Queue()
        self.statement_repository = StatementRepository()
        self.run_control_repository = RunControlRepository()
        self.opentext_endpoint = SecretManager().get_opentext_endpoint() if not self.configuration.islocal else None

    def build_chain(self, statement_generation_conditions):
        chain = None
        for condition in reversed(statement_generation_conditions):
            handle_class = self.HANDLER_MAP.get(condition)
            if handle_class:
                chain = handle_class(chain)
        return chain

    def generate(self, debtors):
        results = asyncio.run(self.pub_sub_orchestrator(debtors))
        return results

    async def pub_sub_orchestrator(self, debtors, num_consumers=5):
        queue_tasks = [
            asyncio.create_task(self.queue_debtor_to_process(debtor))
            for debtor in debtors
        ]
        statement_generator_tasks = [
            asyncio.create_task(self._process_debtor_for_statement())
            for _ in range(num_consumers)
        ]
        queue_results = await asyncio.gather(*queue_tasks)
        for _ in range(num_consumers):
            await self.debtor_queue.put(None)
        await self.debtor_queue.join()
        statement_generation_results = await asyncio.gather(*statement_generator_tasks)
        return statement_generation_results

    async def queue_debtor_to_process(self, debtor):
        has_met_all_conditions = self.handler_chain.handle(debtor)
        if has_met_all_conditions:
            print("start statement generation")
            await self.debtor_queue.put(debtor)
        else:
            print(f"can not generate statement for Debtor: {debtor.IPR}")

    async def _process_debtor_for_statement(self):
        authentication_ticket = await self.get_authentication_token()
        results = []
        while True:
            debtor = await self.debtor_queue.get()
            if debtor is None:
                self.debtor_queue.task_done()
                break
            try:                
                xml_data, statement_request_id = self.get_statement_xml(debtor)
                xml_base64_statement = Utility.encode_to_base64(xml_data)
                print(f"submitting statement generation for: {debtor.IPR}")
                result = await self.send_for_statement_generation(
                    authentication_ticket, xml_base64_statement
                )
                data = result["data"]
                status = result["status"]
                statement_id = self.statement_operation(debtor, status == "success", statement_request_id, xml_data, result)
                self.statement_operation(debtor, True, statement_request_id, xml_data, result)
                print(f"Debtor {debtor.IPR} statement generation was: {status}")
                results.append((data))
            except Exception as e:
                has_request_submitted = "N"
                print(f"Failed to process and send for statement generation; Debtor: {debtor.IPR}; Error: {e}")
                raise e
            finally:
                statement_id = self.statement_operation(debtor, has_request_submitted, xml_data, result)
                self.debtor_queue.task_done()
        return results

    async def send_for_statement_generation(self, authentication_ticket, xml_base64_statement):
        # Disable SSL warnings by creating an unverified SSL context
        ssl_context = ssl._create_unverified_context()
        # Prepare the payload
        payload = json.dumps({
            "content": {
                "contentType": "application/xml",
                "data": xml_base64_statement,
            }
        })
        # Prepare headers
        headers = {
            "OTCSTICKET": f"{{authentication_ticket}}",
            "Content-Type": "application/json",
        }
        # Parse the host and path from your endpoint
        endpoint_url = self.configuration.opentextStatementUrl if self.configuration.islocal else self.secret_manager.opentextStatementUrl
        host, path = Utility.extract_host_and_path(endpoint_url)
        # Make the HTTP connection
        conn = http.client.HTTPSConnection(host, context=ssl_context)
        try:
            # Send the POST request
            conn.request("POST", path, payload, headers)
            response = conn.getresponse()
            # Raise an exception if the status code indicates an error
            if response.status >= 400:
                raise Exception(f"Request failed with status {{response.status}}: {{response.reason}}")
            # Parse and return the ticket from the JSON response
            response_data = response.read().decode()
            response_json = json.loads(response_data)
            return response_json
        finally:
            conn.close()

    async def get_authentication_token(self):
        # Disable SSL warnings by creating an unverified SSL context
        ssl_context = ssl._create_unverified_context()
        if not self.configuration.islocal:
            username = self.opentext_endpoint.username
            password = self.opentext_endpoint.password
            endpoint_url = self.opentext_endpoint.auth_url
        else:
            username = self.configuration.opentextUsername
            password = self.configuration.opentextPassword
            endpoint_url = self.configuration.opentextAuthUrl
            
        # Prepare the payload
        payload = json.dumps({
            "user": username,
            "password": password,
        })
        headers = {"Content-Type": "application/json"}

        # Parse the host and path from your endpoint
        host, path = Utility.extract_host_and_path(endpoint_url)

        # Make the HTTP connection
        conn = http.client.HTTPSConnection(host, context=ssl_context)
        try:
            # Send the POST request
            conn.request("POST", path, payload, headers)
            response = conn.getresponse()
            # Raise an exception if the status code indicates an error
            if response.status >= 400:
                raise Exception(f"Request failed with status {{response.status}}: {{response.reason}}")
            # Parse and return the ticket from the JSON response
            response_data = response.read().decode()
            response_json = json.loads(response_data)
            return response_json["ticket"]
        finally:
            conn.close()

    def get_statement_xml(self, debtor: Debtor):
        statement_request_id = uuid.uuid4()
        od_map = {
            (False, False): "",
            (True, False): "O",
            (False, True): "D",
            (True, True): "D/O"
        }
        
        meta_data = MetaData(
            statementRequestId=statement_request_id,
            generationDate=datetime.today().strftime("%Y-%m-%d"),
            printDestination="EML1" if debtor.DebtorStmEmail else "ARCH1",
            letterType="DebtorStatement",
        )
        debtor_details = DebtorDetails(
            name=debtor.DebtorName,
            addressLine1=debtor.DebtorAddr1,
            addressLine2=debtor.DebtorAddr2,
            addressLine3=debtor.DebtorAddr3,
            city=debtor.DebtorCity,
            postCode=debtor.DebtorPostCode,
            countryCode=debtor.DebtorCountry,
            email=debtor.DebtorStmEmail,
        )
        transaction_list = []
        total_balance_amount = 0
        sorted_transactions = sorted(
            debtor.Transactions, key=lambda tran: (tran.ItemNumber, tran.SeqId)
        )
        account_balance = 0
        overdue_balance = 0
        for tran in sorted_transactions:
            account_balance = account_balance + tran.ItemBalance

            transaction = Transaction(
                docDate=(
                    tran.DocumentDate.strftime("%Y-%m-%d")                    
                    if not Utility.is_none_or_empty(tran.DocumentDate)
                    else ""
                ),
                transType=tran.TransactionType,
                docRef=tran.DocumentReference,
                itemBalance=tran.ItemBalance,
                dueDate=(
                    tran.DueDate.strftime("%Y-%m-%d")                    
                    if not Utility.is_none_or_empty(tran.DueDate)
                    else ""
                ),
                accountBalanceAmt=account_balance,
                od=od_map[(tran.Overdue, tran.Disputed)],
            )
            total_balance_amount = total_balance_amount + tran.ItemBalance
            overdue_balance = (overdue_balance + tran.Overdue if tran.Overdue else overdue_balance)
            transaction_list.append(transaction)
            
        transactionDetails = TransactionDetails(
            transaction=[transaction_list],
            accountCurrency=debtor.AccountCurrency,
            totalBalanceAmount=total_balance_amount,
            overdueAmt=overdue_balance,
        )
        in_payment_info = InPaymentInfo(
            bankCode=debtor.InpaymentBankCode,
            bankAccount=debtor.InpaymentBankAccount,            
            iban=debtor.InpaymentIbanNumber,
        )
        invoice = Invoice(
            ipr=debtor.IPR,
            creditController=debtor.CreditController,
            clientName=debtor.ClientName,
            extractDate=(
                debtor.ExtractDate.strftime("%Y-%m-%d")                
                if not Utility.is_none_or_empty(tran.ExtractDate)
                else ""
            ),
            debtorDetails=debtor_details,
            transactionDetails=transactionDetails,
            inPaymentDetails=in_payment_info,
        )
        invoice_finance_document_root = InvoiceFinanceDocumentRoot(
            metaData=meta_data, invoice=invoice
        )
        xml_string = Utility.serialize_to_xml(invoice_finance_document_root)
        return xml_string, statement_request_id

    def statement_operation(
            self, 
            debtor: Debtor, 
            has_generated: bool, 
            statement_request_id=None, 
            statement_xml=None, 
            opent_text_response=None
    ):
        run_control_data = self.run_control_repository.get_by_id(
            debtor.RunId
        )
        
        statement = Statement(
            StatementRequestId=statement_request_id,
            IPR=debtor.IPR,
            RunId=debtor.RunId,
            FileName=run_control_data.DebtorFileName,
            StatementRequestDateTime=datetime.now(),
            StatementRequestBody=str(statement_xml),
            HasGenerated=has_generated,
            OpenTextResponse=str(opent_text_response),
        )
        statement_id = self.statement_repository.add(statement)
        return statement_id