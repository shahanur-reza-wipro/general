import json
import os
from typing import List, Optional, Dict


class Field:

    def __init__(
        self,
        field: str,
        start: int,
        length: int,
        modelProperty: str,
        validationPattern: str = "",
        isMandatory: bool = False,
    ):
        self.field = field
        self.start = start
        self.length = length
        self.modelProperty = modelProperty
        self.validationPattern = validationPattern
        self.isMandatory = isMandatory

    def __repr__(self):
        return (
            f"Field(field={self.field}, start={self.start}, "
            f"length={self.length}, modelProperty={self.modelProperty}, "
            f"validationPattern={self.validationPattern}, isMandatory={self.isMandatory})"
        )


class Schema:

    def __init__(self, modelName: str, fields: List[Field]):
        self.modelName = modelName
        self.fields = fields

    def __repr__(self):
        return f"Schema(modelName={self.modelName}, fields={self.fields})"

    @classmethod
    def from_json(cls, json_data):
        fields = [Field(**field) for field in json_data["fields"]]
        return cls(modelName=json_data["modelName"], fields=fields)

    def get_field_lengths(self) -> List[int]:
        # Sort fields by 'start' position
        sorted_fields = sorted(self.fields, key=lambda field: field.start)
        # Extract and return the 'length' attribute of each sorted field
        return [field.length for field in sorted_fields]

    def get_field_starts(self) -> List[int]:
        # Sort fields by 'start' position
        sorted_fields = sorted(self.fields, key=lambda field: field.start)
        # Extract and return the 'start' attribute of each sorted field
        return [field.start for field in sorted_fields]

    def get_model_properties(self) -> List[str]:
        # Sort fields by 'start' position
        sorted_fields = sorted(self.fields, key=lambda field: field.start)
        # Extract and return the 'modelProperty' attribute of each sorted field
        return [field.modelProperty for field in sorted_fields]

    def get_validation_patterns(self) -> List[str]:
        # Sort fields by 'start' position
        sorted_fields = sorted(self.fields, key=lambda field: field.start)
        # Extract and return the 'modelProperty' attribute of each sorted field
        return [field.validationPattern for field in sorted_fields]

    def get_is_mandatory(self) -> List[bool]:
        # Sort fields by 'start' position
        sorted_fields = sorted(self.fields, key=lambda field: field.start)
        # Extract and return the 'modelProperty' attribute of each sorted field
        return [field.isMandatory for field in sorted_fields]


class SchemaManager:

    def __init__(self):
        # Load schemas once when the SchemaManager is instantiated
        self.schemas = self.get_schemas()

    # Load the JSON file into Schema objects
    def load_schemas_from_json(self, file_path: str) -> List[Schema]:
        with open(file_path, "r") as file:
            data = json.load(file)
            return [Schema.from_json(schema_data) for schema_data in data]

    def get_schemas(self) -> List[Schema]:
        file_path = os.path.join(os.path.dirname(__file__), "schema.json")
        result = self.load_schemas_from_json(file_path)
        return result

    def get_schema_by_model_name(self, model_name: str) -> Optional[Schema]:
        for schema in self.schemas:
            if schema.modelName == model_name:
                return schema
        return None  # Return None if not found


# # Example usage
# if __name__ == "__main__":
#     # Assuming 'data.json' contains the JSON structure provided
#     schemas = load_schemas_from_json('data.json')
#     for schema in schemas:
#         print(schema)