from contextlib import contextmanager
from typing import List, Type, Optional, Tuple, Callable, Generator
import uuid

from sqlalchemy import create_engine, delete, inspect, asc, desc, text
from sqlalchemy.orm import sessionmaker, scoped_session, subqueryload
from sqlalchemy.orm.query import Query
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.dialects.postgresql import Insert
from sqlalchemy.orm.session import object_session
from sqlalchemy.schema import CreateColumn

from .models import ModelBase
from utilities import SecretManager, Configuration, Utility


class Database:
    def __init__(self):
        """Initialize database connection and session factory."""
        self.configuration = Configuration().get_config()
        self.engine = self.get_db_engine()
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = self.session_factory()
        self.inspector = inspect(self.engine)

    def __del__(self):
        """Ensure the session is closed on destruction."""
        if self.Session:
            self.Session.close()

    def get_db_engine(self):
        """Configure and return the database engine."""
        if not self.configuration.isLocal:
            db_endpoint = SecretManager().get_endpoint()
            host = (
                db_endpoint.proxy_endpoint
                if self.configuration.useRDSProxy
                else db_endpoint.db_endpoint
            )
            db_url = (
                f"postgresql+psycopg2://{db_endpoint.username}:"
                f"{db_endpoint.password}@{host}/{db_endpoint.db_name}"
            )
        else:
            db_url = (
                f"postgresql+psycopg2://{self.configuration.userName}:"
                f"{self.configuration.password}@"
                f"{self.configuration.dbHost}:{self.configuration.dbPort}/"
                f"{self.configuration.dbName}"
            )

        return create_engine(db_url, pool_size=5, max_overflow=10)

    @contextmanager
    def get_session(self) -> Generator[scoped_session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.Session
        try:
            yield session
            session.commit()
        except Exception as ex:
            session.rollback()
            raise ex
        finally:
            session.close()

    def reset_database(self):
        """Drop all tables and schemas, then recreate the public schema."""
        with self.engine.connect() as conn:
            try:
                conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text(
                        """
                        DO $$
                        DECLARE
                            drop_tables_query text;
                            drop_schemas_query text;
                        BEGIN
                            SELECT string_agg(
                                'DROP TABLE IF EXISTS "' || schemaname || '"."' || tablename || '" CASCADE;',
                                ' '
                            )
                            INTO drop_tables_query
                            FROM pg_tables
                            WHERE schemaname IN ('public');

                            IF drop_tables_query IS NOT NULL THEN
                                EXECUTE drop_tables_query;
                            END IF;

                            SELECT string_agg(
                                'DROP SCHEMA IF EXISTS "' || nspname || '" CASCADE;',
                                ' '
                            )
                            INTO drop_schemas_query
                            FROM pg_namespace
                            WHERE nspname IN ('public');

                            IF drop_schemas_query IS NOT NULL THEN
                                EXECUTE drop_schemas_query;
                            END IF;

                            EXECUTE 'CREATE SCHEMA IF NOT EXISTS public';
                        END $$;
                        """
                    )
                )
            finally:
                conn.close()

    def create_tables(self):
        """Create all database tables based on models."""
        ModelBase.metadata.create_all(self.engine)

    def alter_table_add_missing_columns(
        self,
        table_name: str,
        model: Type[DeclarativeMeta],
        schema: Optional[str] = None,
    ) -> List[str]:
        """
        Alter an existing table by adding columns that exist in the model but not in the table.

        :param table_name: Name of the existing table to alter.
        :param model: SQLAlchemy model class used as the source of truth for columns.
        :param schema: Optional schema name. Uses model schema or 'public' by default.
        :return: List of column names that were added.
        """
        model_table = model.__table__
        target_schema = schema or model_table.schema or "public"

        inspector = inspect(self.engine)
        if table_name not in inspector.get_table_names(schema=target_schema):
            raise ValueError(
                f"Table '{target_schema}.{table_name}' does not exist. "
                "Create the table before altering it."
            )

        existing_columns = {
            column["name"]
            for column in inspector.get_columns(table_name, schema=target_schema)
        }
        added_columns = []

        with self.engine.begin() as conn:
            for column in model_table.columns:
                if column.name in existing_columns or column.primary_key:
                    continue

                column_definition = str(
                    CreateColumn(column).compile(dialect=self.engine.dialect)
                )
                conn.execute(
                    text(
                        f'ALTER TABLE "{target_schema}"."{table_name}" '
                        f"ADD COLUMN {column_definition}"
                    )
                )
                added_columns.append(column.name)

        return added_columns

    def drop_tables(self):
        """Drop all tables based on models."""
        ModelBase.metadata.drop_all(self.engine)

    def drop_table(
        self,
        table_name: str,
        schema: Optional[str] = None,
        cascade: bool = False,
    ) -> bool:
        """Drop a single table by name and return whether it existed."""
        target_schema = schema or "public"
        inspector = inspect(self.engine)

        if not inspector.has_table(table_name, schema=target_schema):
            return False

        safe_schema = target_schema.replace('"', '""')
        safe_table_name = table_name.replace('"', '""')
        cascade_sql = " CASCADE" if cascade else ""

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f'DROP TABLE "{safe_schema}"."{safe_table_name}"{cascade_sql}'
                )
            )

        return True

    def drop_tables_recreate(self):
        """Drop all tables and recreate the schema."""
        with self.engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))

    def execute_raw_sql_statement(self, sql):
        """Execute a raw SQL statement."""
        with self.engine.connect() as conn:
            return conn.execute(text(sql))

    def insert(self, obj):
        """Insert a single object into the database."""
        with self.get_session() as session:
            session.add(obj)
            return obj

    def update(self, obj):
        """Update an existing object in the database."""
        with self.get_session() as session:
            updated_object = session.merge(obj)
            session.commit()
            session.expunge(updated_object)
            return updated_object

    def upsert(self, objects, excluded_columns=[], exclude_id=True, batch_size=100):
        """
        Perform an upsert (INSERT ... ON CONFLICT DO UPDATE) for one or multiple objects.

        :param objects: A single ORM object or a list of ORM objects.
        :param excluded_columns: Columns to exclude from the update.
        :param exclude_id: Whether to exclude the primary key from the update.
        :return: List of inserted/updated primary keys.
        """
        if not isinstance(objects, list):
            return self.upsert_single(objects)  # Convert single object to list
        if not objects:
            return []  # Return empty list if no objects provided

        return self.upsert_multiple(objects, excluded_columns, exclude_id, batch_size)

    def upsert_single(self, object: object):
        print(f"calling upsert_single of type {type(object)}")
        result_dict = None
        model = object.__class__
        saved_object = None

        with self.get_session() as session:
            table = object.__table__

            primary_key = inspect(object.__class__).primary_key[0].name

            insert_columns_and_data = {
                col.name: getattr(object, col.name, None) for col in table.columns
            }

            if insert_columns_and_data[primary_key] is None:
                del insert_columns_and_data[primary_key]

            stmt = Insert(table).values(insert_columns_and_data)

            update_columns = {
                col.name: stmt.excluded[col.name]
                for col in table.columns
                if col.name != primary_key
            }

            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=[primary_key],
                set_=update_columns
            ).returning(table.columns)

            # print(upsert_stmt.compile())

            result = session.execute(upsert_stmt).fetchone()
            session.commit()
            if result:
                result_dict = dict(zip(model.__table__.columns.keys(), result))
            if result_dict:
                saved_object = model(**result_dict)

        return saved_object

    def upsert_multiple(
        self,
        objects: list,
        excluded_columns: list = [],
        exclude_id=True,
        batch_size=100
    ):
        """
        Performs bulk upsert in batches to avoid SQL size limitations.

        :param objects: List of ORM objects to upsert.
        :param excluded_columns: List of columns to exclude from the update.
        :param exclude_id: Whether to exclude the primary key from the update step.
        :param batch_size: The number of records per batch.
        :return: list of inserted/updated primary keys.
        """
        if not objects:
            return []  # Return empty list if there are no objects to process

        first_object = objects[0]
        table = first_object.__table__
        primary_key = inspect(first_object.__class__).primary_key[0].name
        primary_key_column = table.primary_key.columns.values()[0]

        ids = []

        with self.get_session() as session:
            # Process objects in batches
            for i in range(0, len(objects), batch_size):
                batch = objects[i:i + batch_size]  # Get batch of objects

                columns_list = []
                for obj in batch:
                    insert_columns_and_data = {
                        col.name: (
                            str(getattr(obj, col.name, None))
                            if isinstance(getattr(obj, col.name, None), uuid.UUID)
                            else getattr(obj, col.name, None)
                        )
                        for col in table.columns
                        if col.name not in excluded_columns
                    }

                    if exclude_id and insert_columns_and_data.get(primary_key) is None:
                        del insert_columns_and_data[primary_key]

                    columns_list.append(insert_columns_and_data)

                # Create the insert statement with conflict handling
                stmt = Insert(table).values(columns_list)

                update_stmt = stmt.on_conflict_do_update(
                    index_elements=[primary_key],
                    set_={
                        col.name: stmt.excluded[col.name]
                        for col in table.columns
                        if col.name != primary_key
                    }
                ).returning(primary_key_column)

                # Execute batch
                rows = session.execute(update_stmt)
                ids.extend(row[0] for row in rows)
                print(
                    f"A batch of {len(batch)} has been upserted for the type "
                    f"{type(first_object)}"
                )

            session.commit()
            print(f"All data type of {type(first_object)} has been committed to database")
            return ids

    def get_by_id(self, id, object_type):
        """Fetch a single record by ID."""
        if not isinstance(id, uuid.UUID):
            try:
                id = uuid.UUID(str(id))
            except (ValueError, AttributeError):
                pass
        with self.get_session() as session:
            object = session.query(object_type).get(id)
            if object is not None:
                session.expunge(object)
            return object

    def get_all(self, object_type):
        """Fetch all records from a given table."""
        with self.get_session() as session:
            results = session.query(object_type).all()
            for result in results:
                session.expunge(result)
            return results

    def delete(self, obj):
        """Delete a single record from the database."""
        with self.get_session() as session:
            session.delete(obj)

    def delete_all(self, model):
        """Delete all records from a given table."""
        with self.get_session() as session:
            session.execute(delete(model))

    def get_record_count(self, model):
        """Get the count of records in a table."""
        with self.get_session() as session:
            return session.query(model).count()

    def get_records(self, model, filter_condition):
        """Get records based on a filter condition."""
        records = []
        with self.get_session() as session:
            records = session.query(model).filter(filter_condition).all()
            for record in records:
                session.expunge(record)
        return records

    def get_records_with_children(self, model, filter_condition, child_properties: list = []):
        """Get records based on a filter condition."""
        records = []

        with self.get_session() as session:
            query = session.query(model)
            for child_property in child_properties:
                query = query.options(subqueryload(child_property))

            records = query.filter(filter_condition).all()

            for record in records:
                for child_prop in child_properties:
                    children = getattr(record, child_prop.key, [])
                    if children:
                        if isinstance(children, list):
                            if children:
                                for child in children:
                                    session.expunge(child)
                        else:
                            if object_session(children) is not None:
                                session.expunge(children)

                session.expunge(record)

        return records

    def get_with_condition(
        self,
        model: Type[DeclarativeMeta],
        conditions: List[Callable[[Query], Query]] = [],
        orderby: Optional[Tuple] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ):
        """Fetch records with custom filtering, sorting, and limiting."""
        results = []
        with self.get_session() as session:
            query: Query = session.query(model)
            try:
                for condition in conditions:
                    query = condition(query)

                if orderby:
                    column, direction = orderby
                    query = query.order_by(
                        asc(column) if direction == "asc" else desc(column)
                    )

                if offset:
                    query = query.offset(offset)

                if limit:
                    query = query.limit(limit)

                results = query.all()
                for result in results:
                    session.expunge(result)
            except Exception as e:
                raise e

        return results

    def dispose_engine(self):
        """Dispose of the database engine (useful for Lambda cold starts)."""
        self.engine.dispose()