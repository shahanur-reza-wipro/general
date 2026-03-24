import os
import sys
import zipfile
import hashlib
import json
import re
import shutil


# =============================
# Utility Functions
# =============================

def compute_hash(source):
    """Generates a SHA256 hash of all files in the directory or a single file."""
    hasher = hashlib.sha256()

    if os.path.isdir(source):
        for root, _, files in sorted(os.walk(source)):  # Sort for consistency
            for file in sorted(files):
                file_path = os.path.join(root, file)
                with open(file_path, "rb") as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)

    elif os.path.isfile(source):
        with open(source, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)

    else:
        error_output = {"error": f"Invalid source path '{source}'"}
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)

    raw_hash = hasher.hexdigest()[:10]  # Shortened hash
    safe_hash = re.sub(r"[^a-zA-Z0-9]", "", raw_hash)  # Remove special characters
    return safe_hash


def prepare_layer_structure(source, function_name, runtime):
    """
    Creates the AWS Lambda layer directory structure inside the artifacts folder.
    """

    python_version_match = re.search(r"python(\d+\.\d+)", runtime)

    if not python_version_match:
        error_output = {"error": f"Invalid Python runtime '{runtime}'"}
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)

    python_version = python_version_match.group(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    is_direct_copy = source.endswith("/")

    source = os.path.abspath(os.path.join(script_dir, source.rstrip("/")))

    artifacts_root = os.path.join(os.getcwd(), "artifacts", function_name)
    site_packages_path = os.path.join(
        artifacts_root,
        "python",
        "lib",
        f"python{python_version}",
        "site-packages"
    )

    # Remove existing python directory if it exists
    if os.path.exists(os.path.join(artifacts_root, "python")):
        shutil.rmtree(os.path.join(artifacts_root, "python"))

    if is_direct_copy:
        os.makedirs(site_packages_path, exist_ok=True)
    else:
        os.makedirs(os.path.join(site_packages_path, function_name), exist_ok=True)

    for item in os.listdir(source):
        item_path = os.path.join(source, item)

        if is_direct_copy:
            target_path = os.path.join(site_packages_path, item)
        else:
            target_path = os.path.join(site_packages_path, function_name, item)

        if os.path.isdir(item_path):
            shutil.copytree(item_path, target_path, dirs_exist_ok=True)
        else:
            shutil.copy2(item_path, target_path)

    return artifacts_root


def zip_layer(function_name):
    """
    Zips the entire 'python/' folder inside artifacts/{function_name}
    ensuring proper AWS Lambda Layer structure.
    """

    artifacts_root = os.path.join(os.getcwd(), "artifacts", function_name)
    python_folder = os.path.join(artifacts_root, "python")

    if not os.path.exists(python_folder):
        error_output = {"error": f"Expected 'python' folder not found in {artifacts_root}"}
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)

    content_hash = compute_hash(python_folder)
    zip_name = os.path.join(artifacts_root, f"{content_hash}.zip")

    try:
        with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(python_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, artifacts_root)
                    zipf.write(file_path, arcname)

    except Exception as e:
        error_output = {"error": str(e)}
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)

    output = {
        "zip_file": zip_name,
        "content_hash": content_hash
    }

    print(json.dumps(output))
    return zip_name


def zip_function(source, function_name):
    """Handles zipping a Lambda function (NOT a layer)."""

    script_dir = os.path.dirname(os.path.abspath(__file__))
    source = os.path.abspath(os.path.join(script_dir, source))

    if not os.path.exists(source):
        error_output = {"error": f"Source path '{source}' does not exist."}
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)

    content_hash = compute_hash(source)

    artifacts_root = os.path.join(os.getcwd(), "artifacts", function_name)
    zip_name = os.path.join(artifacts_root, f"{content_hash}.zip")

    os.makedirs(artifacts_root, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(source):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source)
                    zipf.write(file_path, arcname)

    except Exception as e:
        error_output = {"error": str(e)}
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)

    output = {
        "zip_file": zip_name,
        "content_hash": content_hash
    }

    print(json.dumps(output))
    return zip_name


def zip_path(source, function_name, runtime=None):
    """Handles both Lambda function and Lambda layer packaging."""

    is_layer = bool(runtime)

    if is_layer:
        prepare_layer_structure(source, function_name, runtime)
        return zip_layer(function_name)
    else:
        return zip_function(source, function_name)


# =============================
# JSON Configuration Reader
# =============================

def read_config(file_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, file_name)

    """Read deployment configuration from a JSON file."""

    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(file_path, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}", file=sys.stderr)
            sys.exit(1)


# =============================
# Main Execution
# =============================

def main():
    config = read_config("deployment.config.json")

    # Process Lambda Functions
    lambda_functions = config.get("lambda_functions", [])
    for function in lambda_functions:
        source_path = function["source_path"]
        function_name = function["function_name"]

        print(f"Packaging Lambda function: {function_name} from {source_path}")
        zip_path(source_path, function_name)

    # Process Lambda Layers
    lambda_layers = config.get("lambda_layers", [])
    for layer in lambda_layers:
        source_path = layer["source_path"]
        layer_name = layer["layer_name"]
        runtime = layer.get("runtime", "python3.11")

        print(f"Packaging Lambda layer: {layer_name} from {source_path}")
        zip_path(source_path, layer_name, runtime)


if __name__ == "__main__":
    main()