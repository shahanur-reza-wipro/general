# import pkgutil
# import importlib
# import inspect


# def load_classes():
#     for loader, module_name, is_pkg in pkgutil.walk_packages(__path__):
#         importlib.import_module(f"{__name__}.{module_name}")
#         module = importlib.import_module(f"{__name__}.{module_name}")
#         for name, obj in inspect.getmembers(module):
#             if inspect.isclass(obj):
#                 globals()[name] = obj


# load_classes()

from .models import Debtor
from .models import Transaction
from .models import ModelBase
try:
    from .database import Database
except Exception:
    Database = None
from .models import RunControl
from .models import StatementValidation
from .models import Statement
from .models import DebtorFileValidation
from .models import TransactionFileValidation
from .models import DebtorRecordValidation
from .models import TransactionRecordValidation
from .models import StatementValidation
from .models import RunBatch

# Add other imports here

__all__ = [
    ModelBase,
    Debtor,
    Transaction,
    Database,
    RunControl,
    RunBatch,
    StatementValidation,
    Statement,
    DebtorFileValidation,
    TransactionFileValidation,
    DebtorRecordValidation,
    TransactionRecordValidation,
    StatementValidation
]