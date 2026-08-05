param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$BaseUrl,
    [int]$TimeoutSec = 120,
    [switch]$OverwriteState
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$missing = @("PlayniteApi", "Game", "__logger") | Where-Object { -not (Test-Path "variable:$_") }
if ($missing) { throw "Missing Playnite variables: $($missing -join ', '). Run this script from a Playnite game event." }

$uri = "$($BaseUrl.TrimEnd('/'))/api/http_restore_trigger"
if ($OverwriteState) { $uri += "?overwrite_state=true" }
$__logger.Info("[Bloomin8] Restore endpoint: $uri")

# Runs in its own runspace so Playnite is not blocked while the frame restores.
$worker = {
    param($Uri, $Timeout, $Logger)

    $ProgressPreference = "SilentlyContinue"
    try {
        $response = Invoke-WebRequest -Uri $Uri -Method Post -TimeoutSec $Timeout -UseBasicParsing
        $Logger.Info("[Bloomin8] Restore response: $([int]$response.StatusCode) $($response.Content)")
    }
    catch {
        $status = 0
        if (($_.Exception -is [System.Net.WebException]) -and $_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        $message = if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
        $Logger.Error("[Bloomin8] Restore response: $status $message")
    }
}

$runner = [powershell]::Create()
[void]$runner.AddScript($worker).AddArgument($uri).AddArgument($TimeoutSec).AddArgument($__logger)
[void]$runner.BeginInvoke()
