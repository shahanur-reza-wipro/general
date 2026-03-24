param(
    [Parameter(Mandatory = $true)]
    [string]$PythonRuntime,
    [Parameter(Mandatory = $false)]
    [switch]$RemoveDestination
)

function Copy-FolderToLambdaLayer {
    param (
        [string]$SourceFolder,
        [string]$PythonRuntime,
        [switch]$RemoveDestination
    )

    # Define destination path
    $destinationFolder = "${SourceFolder}_lambda_layer"
    $destinationPath = "$destinationFolder/python/lib/$PythonRuntime/site-packages/"

    
    if ($RemoveDestination) {
        # Remove the original folder
        Remove-Item -Path $destinationFolder -Recurse -Force
        Write-Output "removed $destinationPath"
    }
    else {
        # Create the destination directory structure
        New-Item -ItemType Directory -Force -Path $destinationPath

        # Copy the folder recursively
        Copy-Item -Path $SourceFolder -Destination $destinationPath -Recurse

        Write-Output "Copied $SourceFolder to $destinationPath"
    }
}

# Example usage:
# Remove
Copy-FolderToLambdaLayer -SourceFolder .\data_access_layer -PythonRuntime $PythonRuntime -RemoveDestination
Copy-FolderToLambdaLayer -SourceFolder .\repositories -PythonRuntime $PythonRuntime -RemoveDestination
Copy-FolderToLambdaLayer -SourceFolder .\services -PythonRuntime $PythonRuntime -RemoveDestination
Copy-FolderToLambdaLayer -SourceFolder .\utilities -PythonRuntime $PythonRuntime -RemoveDestination

# Create Folder and Copy
Copy-FolderToLambdaLayer -SourceFolder .\data_access_layer -PythonRuntime $PythonRuntime
Copy-FolderToLambdaLayer -SourceFolder .\repositories -PythonRuntime $PythonRuntime
Copy-FolderToLambdaLayer -SourceFolder .\services -PythonRuntime $PythonRuntime
Copy-FolderToLambdaLayer -SourceFolder .\utilities -PythonRuntime $PythonRuntime
