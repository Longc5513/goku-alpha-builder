param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

$scriptPath = Join-Path $PSScriptRoot "ship.py"
python $scriptPath @Args

