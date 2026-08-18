[CmdletBinding(DefaultParameterSetName = "ShowCover")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "ShowCover")]
    [switch]$ShowCover,
    [Parameter(Mandatory = $true, ParameterSetName = "Restore")]
    [switch]$Restore,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$BaseUrl, #Webhook base URL, e.g. http://localhost:7072
    [Parameter(ParameterSetName = "ShowCover")]
    [string]$Gallery = "games", 
    [Parameter(ParameterSetName = "ShowCover")]
    [string]$DisplayMode, #See BLOOMIN8_DISPLAY_MODE
    [switch]$OverwriteState, #See BLOOMIN8_OVERWRITE_STATE
    [int]$HTTPTimeoutSec = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Skips null/empty params so optional webhook flags aren't sent as blank query values.
function Build-RequestUri {
    param(
        [string]$BaseUrl,
        [string]$Path,
        [hashtable]$Params = @{}
    )

    $trimmedUri = "$($BaseUrl.TrimEnd('/'))/$($Path.TrimStart('/'))"
    $uriBuilder = [System.UriBuilder]::new($trimmedUri)
    $pairs = foreach ($entry in $Params.GetEnumerator()) {
        if ($null -ne $entry.Value -and $entry.Value -ne "") {
            "$([System.Net.WebUtility]::UrlEncode($entry.Key))=$([System.Net.WebUtility]::UrlEncode([string]$entry.Value))"
        }
    }
    $uriBuilder.Query = $pairs -join "&"

    return $uriBuilder.Uri.AbsoluteUri
}

$missing = @("PlayniteApi", "Game", "__logger") | Where-Object { -not (Test-Path "variable:$_") }
if ($missing) { throw "Missing Playnite variables: $($missing -join ', '). Run this script from a Playnite game event." }

$Action = $PSCmdlet.ParameterSetName
$overwriteStateValue = if ($OverwriteState) { "true" } else { $null }

$request = @{
    Method          = "Post"
    HTTPTimeoutSec  = $HTTPTimeoutSec
    UseBasicParsing = $true
}

if ($Action -eq "ShowCover") {
    $coverPath = if ($Game.CoverImage) { $PlayniteApi.Database.GetFullFilePath($Game.CoverImage) }
    if (-not $coverPath -or -not (Test-Path -LiteralPath $coverPath)) {
        $__logger.Info("[Bloomin8] No usable cover image for '$($Game.Name)', skipping.")
        return
    }

    $queryParams = @{
        name            = Split-Path -Path $coverPath -Leaf
        gallery         = $Gallery
        display_mode    = $DisplayMode
        overwrite_state = $overwriteStateValue
    }
    $request.Uri = Build-RequestUri -BaseUrl $BaseUrl -Path "/api/http_show_image_trigger" -Params $queryParams
    $request.Body = [System.IO.File]::ReadAllBytes($coverPath)
    $request.ContentType = "application/octet-stream"
}
else {
    $queryParams = @{
        overwrite_state = $overwriteStateValue
    }
    $request.Uri = Build-RequestUri -BaseUrl $BaseUrl -Path "/api/http_restore_trigger" -Params $queryParams
}

$__logger.Debug("[Bloomin8] $Action endpoint: $($request.Uri)")

# Runs in its own runspace so neither the game launch nor Playnite waits for the frame.
$backgroundJob = {
    param($Request, $Logger, $ActionName)

    $ProgressPreference = "SilentlyContinue"
    try {
        $response = Invoke-WebRequest @Request
        $Logger.Debug("[Bloomin8] $ActionName response: $([int]$response.StatusCode) $($response.Content)")
    }
    catch {
        $status = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
        $message = if ($_.ErrorDetails) { $_.ErrorDetails.Message } else { $_.Exception.Message }
        $Logger.Error("[Bloomin8] $ActionName response: $status $message")
    }
}

$runner = [powershell]::Create()
[void]$runner.AddScript($backgroundJob).AddArgument($request).AddArgument($__logger).AddArgument($Action)
[void]$runner.BeginInvoke()
