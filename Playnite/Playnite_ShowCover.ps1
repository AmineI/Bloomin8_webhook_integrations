param(
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

if ([string]::IsNullOrWhiteSpace($Game.CoverImage)) {
    $__logger.Debug("[Bloomin8] Game has no cover image, skipping.")
    return
}

$coverPath = $PlayniteApi.Database.GetFullFilePath($Game.CoverImage)
if ([string]::IsNullOrWhiteSpace($coverPath) -or -not (Test-Path -LiteralPath $coverPath)) {
    $__logger.Debug("[Bloomin8] Cover file not found for '$($Game.Name)', skipping.")
    return
}

$coverName = Split-Path -Path $coverPath -Leaf
$query = @("name=$([uri]::EscapeDataString($coverName))")
if ($Gallery) { $query += "gallery=$([uri]::EscapeDataString($Gallery))" }
if ($DisplayMode) { $query += "display_mode=$([uri]::EscapeDataString($DisplayMode))" }
if ($OverwriteState) { $query += "overwrite_state=true" }

$uri = "$($BaseUrl.TrimEnd('/'))/api/http_show_image_trigger?$($query -join '&')"
$__logger.Info("[Bloomin8] Show cover endpoint: $uri")

# Runs in its own runspace so the frame update does not delay the game launch.
$worker = {
    param($Uri, $CoverPath, $Timeout, $Logger)

    $ProgressPreference = "SilentlyContinue"
    try {
        $body = [System.IO.File]::ReadAllBytes($CoverPath)
        $response = Invoke-WebRequest -Uri $Uri -Method Post -Body $body -ContentType "application/octet-stream" -TimeoutSec $Timeout -UseBasicParsing
        $Logger.Info("[Bloomin8] Show cover response: $([int]$response.StatusCode) $($response.Content)")
    }
    catch {
        $status = 0
        if (($_.Exception -is [System.Net.WebException]) -and $_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        $message = if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
        $Logger.Error("[Bloomin8] Show cover response: $status $message")
    }
}

$runner = [powershell]::Create()
[void]$runner.AddScript($worker).AddArgument($uri).AddArgument($coverPath).AddArgument($TimeoutSec).AddArgument($__logger)
[void]$runner.BeginInvoke()
