param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("ShowCover", "Restore")]
    [string]$Action,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$BaseUrl,
    [string]$Gallery = "games",
    [string]$DisplayMode = "",
    [int]$TimeoutSec = 120,
    [switch]$OverwriteState
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$missing = @("PlayniteApi", "Game", "__logger") | Where-Object { -not (Test-Path "variable:$_") }
if ($missing) { throw "Missing Playnite variables: $($missing -join ', '). Run this script from a Playnite game event." }

$request = @{
    Method          = "Post"
    TimeoutSec      = $TimeoutSec
    UseBasicParsing = $true
}

if ($Action -eq "ShowCover") {
    $coverPath = if ($Game.CoverImage) { $PlayniteApi.Database.GetFullFilePath($Game.CoverImage) }
    if ([string]::IsNullOrWhiteSpace($coverPath) -or -not (Test-Path -LiteralPath $coverPath)) {
        $__logger.Info("[Bloomin8] No usable cover image for '$($Game.Name)', skipping.")
        return
    }

    $query = @("name=$([uri]::EscapeDataString((Split-Path -Path $coverPath -Leaf)))")
    if ($Gallery) { $query += "gallery=$([uri]::EscapeDataString($Gallery))" }
    if ($DisplayMode) { $query += "display_mode=$([uri]::EscapeDataString($DisplayMode))" }
    if ($OverwriteState) { $query += "overwrite_state=true" }

    $request.Uri = "$($BaseUrl.TrimEnd('/'))/api/http_show_image_trigger?$($query -join '&')"
    $request.Body = [System.IO.File]::ReadAllBytes($coverPath)
    $request.ContentType = "application/octet-stream"
}
else {
    $request.Uri = "$($BaseUrl.TrimEnd('/'))/api/http_restore_trigger"
    if ($OverwriteState) { $request.Uri += "?overwrite_state=true" }
}

$__logger.Debug("[Bloomin8] $Action endpoint: $($request.Uri)")

# Runs in its own runspace so neither the game launch nor Playnite waits for the frame.
$worker = {
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
[void]$runner.AddScript($worker).AddArgument($request).AddArgument($__logger).AddArgument($Action)
[void]$runner.BeginInvoke()
