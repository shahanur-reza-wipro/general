# abstract_repository.py
from abc import ABC, abstractmethod


class AbstractRepository(ABC):

    @abstractmethod
    def upsert(self, entity) -> str:
        """Add a new entity to the database."""
        raise NotImplementedError

    @abstractmethod
    def update(self, entity) -> str:
        """Update an existing entity in the database."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, entity_id):
        """Retrieve an entity by its ID."""
        raise NotImplementedError

    @abstractmethod
    def get_all(self):
        """Retrieve all entities from the database."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, entity_id):
        """Delete an entity by its ID."""
        raise NotImplementedError

    @abstractmethod
    def upsert(self, entities) -> list[str]:
        """Upsert (update or insert) list of entities."""
        raise NotImplementedError