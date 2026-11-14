$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$workspaceBinary = Join-Path $projectRoot '.tools/ollama/ollama.exe'
if (Test-Path -LiteralPath $workspaceBinary) {
    $ollamaBinary = $workspaceBinary
    $env:OLLAMA_MODELS = Join-Path $projectRoot '.tools/ollama-models'
} else {
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollamaCommand) {
        throw 'Install Ollama first: winget install --exact --id Ollama.Ollama --scope user'
    }
    $ollamaBinary = $ollamaCommand.Source
}
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_VULKAN = '0'
& $ollamaBinary serve
