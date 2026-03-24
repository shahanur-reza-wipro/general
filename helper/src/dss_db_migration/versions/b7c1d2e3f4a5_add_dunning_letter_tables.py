"""add dunning letter tables

Revision ID: b7c1d2e3f4a5
Revises: 92cb59edfa00
Create Date: 2026-03-23 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c1d2e3f4a5'
down_revision: Union[str, None] = '92cb59edfa00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dunning_letter',
        sa.Column('ID', sa.UUID(), nullable=False),
        sa.Column('DunningLetterRequestId', sa.UUID(), nullable=True),
        sa.Column('IPR', sa.String(length=26), nullable=False),
        sa.Column('OpenTextIPR', sa.String(length=255), nullable=False),
        sa.Column('RunId', sa.UUID(), nullable=False),
        sa.Column('FileName', sa.String(length=255), nullable=False),
        sa.Column('RequestDateTime', sa.DateTime(), nullable=False),
        sa.Column('DunningReminderLevel', sa.Integer(), nullable=False),
        sa.Column('DunningCycleCode', sa.String(length=10), nullable=True),
        sa.Column('OpenTextTrackerId', sa.Text(), nullable=True),
        sa.Column('RequestSubmissionStatus', sa.String(length=26), nullable=True),
        sa.Column('PdfGenerationStatus', sa.String(length=26), nullable=True),
        sa.Column('RequestBody', sa.Text(), nullable=True),
        sa.Column('PdfContent', sa.Text(), nullable=True),
        sa.Column('ProcessingStatus', sa.Text(), nullable=True),
        sa.Column('ReasonForFailure', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ID')
    )
    op.create_table(
        'dunning_letter_request',
        sa.Column('DunningLetterRequestID', sa.UUID(), nullable=False),
        sa.Column('RequestDate', sa.Date(), nullable=False),
        sa.Column('ExpectedLetterCount', sa.Numeric(precision=10), nullable=False),
        sa.Column('SubmissionStatus', sa.String(length=26), nullable=True),
        sa.Column('SubmissionResult', sa.Text(), nullable=True),
        sa.Column('RequestBase64Body', sa.Text(), nullable=True),
        sa.Column('SubmissionId', sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint('DunningLetterRequestID')
    )
    op.create_table(
        'dunning_letter_validation',
        sa.Column('ID', sa.UUID(), nullable=False),
        sa.Column('IPR', sa.String(length=26), nullable=False),
        sa.Column('ConditionName', sa.String(length=255), nullable=False),
        sa.Column('Log', sa.String(length=255), nullable=False),
        sa.Column('Description', sa.Text(), nullable=True),
        sa.Column('RunId', sa.UUID(), nullable=False),
        sa.Column('FileName', sa.String(length=255), nullable=False),
        sa.Column('ValidationDate', sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint('ID')
    )


def downgrade() -> None:
    op.drop_table('dunning_letter_validation')
    op.drop_table('dunning_letter_request')
    op.drop_table('dunning_letter')