## Database Migration
### Init alembic
```powershell
 alembic init dss_db_migration
```
### Auto Generate from the available models
```powershell
 alembic revision --autogenerate -m "your message like a commit message"
```
### Upgrade Database
```powershell
 alembic upgrade head #[It will upgrade to the latest changes]
```
### Downgrade Database
```powershell
 alembic downgrade -1 #[To get to the previous version]
 alembic downgrade base #[To get to the starting point, this would !! DROP ALL THE TABLES !! if it is written in the downgrade function of the revision py file]
```
## High Level Solution Design

```mermaid
graph TD
  S3 --> |Triggers| LambdaFunctions
  LambdaFunctions --> |Calls| ServiceLayer
  ServiceLayer --> |Calls| Repositories
  Repositories --> |Calls| DataAccessLayer
  DataAccessLayer --> |Contains| Models

  classDef lambdaFunctions fill:#ff9,stroke:#333,stroke-width:2px;
  classDef serviceLayer fill:#f96,stroke:#333,stroke-width:2px;
  classDef repositories fill:#6cf,stroke:#333,stroke-width:2px;
  classDef dataAccessLayer fill:#fc6,stroke:#333,stroke-width:2px;
  classDef models fill:#9f6,stroke:#333,stroke-width:2px;

  class LambdaFunctions lambdaFunctions;
  class ServiceLayer serviceLayer;
  class Repositories repositories;
  class DataAccessLayer dataAccessLayer;
  class Models models;
```

# Design Patterns

- [SOA - Service Oriented Architecture](https://en.wikipedia.org/wiki/Service-oriented_architecture)
- [Repository](https://martinfowler.com/eaaCatalog/repository.html)

# Resources

- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Alembic](https://alembic.sqlalchemy.org/en/latest/)
