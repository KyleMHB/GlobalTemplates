[CmdletBinding()]
param(
    [string]$RootPath = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$validationErrors = [System.Collections.Generic.List[string]]::new()
$allowedFormats = @('gfm', 'bbcode', 'json', 'xml')
$koFiUrl = 'https://ko-fi.com/I7L525WMJ6'
$koFiBadgeUrl = 'https://img.shields.io/badge/Support_me_on_Ko--fi-72a4f2?style=for-the-badge&logo=kofi&logoColor=white'
$gitHubBadgeUrl = 'https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github&logoColor=white'
$repositoryUrlPlaceholder = '{repository-url}'
$bannedPatterns = [ordered]@{
    'System Instructions' = 'stale system-prompt heading'
    'CRITICAL' = 'stale urgency marker'
    'respond\s+ONLY' = 'stale chat-only delivery instruction'
    '(?-i:\bMUST\b)' = 'stale repeated imperative marker'
    'Use this exact date heading format' = 'fixed changelog heading rule'
    '<script\b' = 'embedded scripts are not allowed'
    "Support KyleMHB's" = 'third-person support wording is not allowed'
}

function Add-ValidationError {
    param(
        [string]$Location,
        [string]$Message
    )

    $validationErrors.Add("${Location}: $Message")
}

function Get-DocumentedTemplatePaths {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Add-ValidationError -Location $Path -Message 'mapping document is missing'
        return @()
    }

    $content = Get-Content -Raw -LiteralPath $Path
    $matches = [regex]::Matches(
        $content,
        '(?i)(?:Git|Steam)/[A-Za-z0-9._/-]+-template\.md'
    )

    return @(
        $matches |
            ForEach-Object { $_.Value.Replace('\', '/') } |
            Sort-Object -Unique
    )
}

function Compare-TemplateSets {
    param(
        [string]$DocumentName,
        [string[]]$Expected,
        [string[]]$Actual
    )

    $differences = Compare-Object -ReferenceObject $Expected -DifferenceObject $Actual
    foreach ($difference in $differences) {
        if ($difference.SideIndicator -eq '<=') {
            Add-ValidationError -Location $DocumentName -Message "missing template mapping '$($difference.InputObject)'"
        } else {
            Add-ValidationError -Location $DocumentName -Message "contains unmapped template '$($difference.InputObject)'"
        }
    }
}

function Test-RepositoryMarkdownLinks {
    param([string]$Path)

    $content = Get-Content -Raw -LiteralPath $Path
    $matches = [regex]::Matches($content, '\[[^\]]+\]\((?<target>[^)]+)\)')

    foreach ($match in $matches) {
        $target = $match.Groups['target'].Value.Trim().Trim('<', '>')
        if (
            [string]::IsNullOrWhiteSpace($target) -or
            $target.StartsWith('#') -or
            $target -match '^(?i:https?|mailto):' -or
            $target -match '[\[\]]'
        ) {
            continue
        }

        $targetWithoutAnchor = ($target -split '#', 2)[0]
        if ([string]::IsNullOrWhiteSpace($targetWithoutAnchor)) {
            continue
        }

        $candidate = Join-Path (Split-Path -Parent $Path) $targetWithoutAnchor
        if (-not (Test-Path -LiteralPath $candidate)) {
            Add-ValidationError -Location $Path -Message "broken local Markdown link '$target'"
        }
    }
}

function Test-FencedExamples {
    param(
        [string]$Path,
        [string]$Content
    )

    $pattern = '(?ms)^(?<fence>`{3}|~{3})(?<language>json|xml)\s*\r?\n(?<body>.*?)^\k<fence>\s*$'
    $matches = [regex]::Matches($Content, $pattern)

    foreach ($match in $matches) {
        $language = $match.Groups['language'].Value.ToLowerInvariant()
        $body = $match.Groups['body'].Value.Trim()

        try {
            if ($language -eq 'json') {
                $null = $body | ConvertFrom-Json
            } else {
                $null = [xml]$body
            }
        } catch {
            Add-ValidationError -Location $Path -Message "invalid fenced $language example: $($_.Exception.Message)"
        }
    }
}

function Test-RequiredBadges {
    param(
        [string]$Location,
        [string]$Content,
        [ValidateSet('gfm', 'bbcode')]
        [string]$Format,
        [string]$RepositoryUrl
    )

    if ($Format -eq 'gfm') {
        $koFiMarkup = "[![Support me on Ko-fi]($koFiBadgeUrl)]($koFiUrl)"
        $gitHubMarkup = "[![GitHub Repository]($gitHubBadgeUrl)]($RepositoryUrl)"
    } else {
        $koFiMarkup = "[url=$koFiUrl][img]$koFiBadgeUrl[/img][/url]"
        $gitHubMarkup = "[url=$RepositoryUrl][img]$gitHubBadgeUrl[/img][/url]"
    }

    if (-not $Content.Contains($koFiMarkup)) {
        Add-ValidationError -Location $Location -Message 'missing or malformed linked Ko-fi badge'
    }

    if (-not $Content.Contains($gitHubMarkup)) {
        Add-ValidationError -Location $Location -Message 'missing or malformed linked GitHub repository badge'
    }
}

function Test-SteamSectionOrder {
    param(
        [string]$Location,
        [string]$Content
    )

    $sectionMatch = [regex]::Match(
        $Content,
        '(?ms)^## Default section order\s*\r?\n(?<body>.*?)(?=^## |\z)'
    )

    if (-not $sectionMatch.Success) {
        Add-ValidationError -Location $Location -Message 'missing default Steam section order'
        return
    }

    $expectedSections = @(
        'Description',
        'Features',
        'How to Use',
        'Settings and Configuration',
        'Requirements and Dependencies',
        'Compatibility, Load Order, Multiplayer, and Save Safety',
        'Fork History',
        'Credits',
        'License and Forking Policy',
        'Links'
    )

    $actualSections = @(
        foreach ($match in [regex]::Matches($sectionMatch.Groups['body'].Value, '(?m)^\d+\.\s+(?<name>.+?)\s*$')) {
            $match.Groups['name'].Value.Trim() -replace ', (?:when applicable|required for forks|always last)$', ''
        }
    )

    $orderIsValid = $actualSections.Count -eq $expectedSections.Count
    if ($orderIsValid) {
        for ($index = 0; $index -lt $expectedSections.Count; $index++) {
            if ($actualSections[$index] -ne $expectedSections[$index]) {
                $orderIsValid = $false
                break
            }
        }
    }

    if (-not $orderIsValid) {
        Add-ValidationError -Location $Location -Message 'reader-first Steam section order is invalid'
    }

    if (-not $Content.Contains('Dependencies must appear after How to Use.')) {
        Add-ValidationError -Location $Location -Message 'missing dependencies-after-usage rule'
    }

    if (
        $sectionMatch.Groups['body'].Value -notmatch '(?m)^10\. Links, always last\s*$' -or
        -not $Content.Contains('Links must be the final section.')
    ) {
        Add-ValidationError -Location $Location -Message 'missing Links-last rule'
    }
}

try {
    $resolvedRoot = (Resolve-Path -LiteralPath $RootPath).Path
} catch {
    Write-Error "Root path '$RootPath' does not exist."
    exit 1
}

$manifestPath = Join-Path $resolvedRoot 'templates.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    Write-Error "Template manifest is missing: $manifestPath"
    exit 1
}

try {
    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
} catch {
    Write-Error "Invalid templates.json: $($_.Exception.Message)"
    exit 1
}

$schemaVersionProperty = $manifest.PSObject.Properties['schemaVersion']
if ($null -eq $schemaVersionProperty -or $schemaVersionProperty.Value -ne 1) {
    Add-ValidationError -Location 'templates.json' -Message 'schemaVersion must be 1'
}

$templatesProperty = $manifest.PSObject.Properties['templates']
$templateEntries = if ($null -eq $templatesProperty) { @() } else { @($templatesProperty.Value) }
if ($templateEntries.Count -eq 0) {
    Add-ValidationError -Location 'templates.json' -Message 'templates must contain at least one entry'
}

$seenIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$seenSources = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$manifestSources = [System.Collections.Generic.List[string]]::new()

foreach ($entry in $templateEntries) {
    $idProperty = $entry.PSObject.Properties['id']
    $entryId = if ($null -ne $idProperty -and -not [string]::IsNullOrWhiteSpace([string]$idProperty.Value)) {
        [string]$idProperty.Value
    } else {
        '<missing-id>'
    }
    $missingRequiredProperty = $false

    foreach ($propertyName in @('id', 'template', 'target', 'format', 'appliesWhen')) {
        $property = $entry.PSObject.Properties[$propertyName]
        if ($null -eq $property -or [string]::IsNullOrWhiteSpace([string]$property.Value)) {
            Add-ValidationError -Location "templates.json [$entryId]" -Message "missing '$propertyName'"
            $missingRequiredProperty = $true
        }
    }

    if ($missingRequiredProperty) {
        continue
    }

    if ($entryId -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') {
        Add-ValidationError -Location "templates.json [$entryId]" -Message 'id must be kebab-case'
    }

    if (-not $seenIds.Add($entryId)) {
        Add-ValidationError -Location "templates.json [$entryId]" -Message 'duplicate id'
    }

    $source = ([string]$entry.template).Replace('\', '/')
    if (-not $seenSources.Add($source)) {
        Add-ValidationError -Location "templates.json [$entryId]" -Message "duplicate template source '$source'"
    }
    $manifestSources.Add($source)

    if ([IO.Path]::IsPathRooted($source) -or $source.Split('/') -contains '..') {
        Add-ValidationError -Location "templates.json [$entryId]" -Message 'template path must remain inside the repository'
        continue
    }

    $sourceName = [IO.Path]::GetFileName($source)
    if ($sourceName -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*-template\.md$') {
        Add-ValidationError -Location "templates.json [$entryId]" -Message "template filename '$sourceName' is not kebab-case"
    }

    $format = ([string]$entry.format).ToLowerInvariant()
    if ($format -notin $allowedFormats) {
        Add-ValidationError -Location "templates.json [$entryId]" -Message "unsupported format '$format'"
    }

    $sourcePath = Join-Path $resolvedRoot $source
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        Add-ValidationError -Location "templates.json [$entryId]" -Message "template source is missing: $source"
        continue
    }

    $templateContent = Get-Content -Raw -LiteralPath $sourcePath
    $target = [string]$entry.target
    if ($templateContent -notmatch [regex]::Escape($target)) {
        Add-ValidationError -Location $source -Message "does not name declared target '$target'"
    }

    foreach ($pattern in $bannedPatterns.Keys) {
        if ($templateContent -match $pattern) {
            Add-ValidationError -Location $source -Message $bannedPatterns[$pattern]
        }
    }

    if ($source -eq 'Git/readme-template.md') {
        Test-RequiredBadges -Location $source -Content $templateContent -Format 'gfm' -RepositoryUrl $repositoryUrlPlaceholder
    } elseif ($source -eq 'Steam/steam-description-template.md') {
        Test-RequiredBadges -Location $source -Content $templateContent -Format 'bbcode' -RepositoryUrl $repositoryUrlPlaceholder
        Test-SteamSectionOrder -Location $source -Content $templateContent

        if (-not $templateContent.Contains('### How to Use')) {
            Add-ValidationError -Location $source -Message 'missing required How to Use guidance'
        }

        if (
            -not $templateContent.Contains('### Fork History') -or
            -not $templateContent.Contains('explain why the fork exists') -or
            -not $templateContent.Contains('differences from the upstream mod')
        ) {
            Add-ValidationError -Location $source -Message 'missing required fork purpose and difference guidance'
        }
    }

    Test-FencedExamples -Path $source -Content $templateContent
}

$expectedSources = @($manifestSources | Sort-Object -Unique)
$agentsPath = Join-Path $resolvedRoot 'AGENTS.md'
$readmePath = Join-Path $resolvedRoot 'README.md'

Compare-TemplateSets -DocumentName 'AGENTS.md' -Expected $expectedSources -Actual (Get-DocumentedTemplatePaths -Path $agentsPath)
Compare-TemplateSets -DocumentName 'README.md' -Expected $expectedSources -Actual (Get-DocumentedTemplatePaths -Path $readmePath)

Test-RepositoryMarkdownLinks -Path $readmePath
Test-RepositoryMarkdownLinks -Path $agentsPath

if (Test-Path -LiteralPath $readmePath -PathType Leaf) {
    $readmeContent = Get-Content -Raw -LiteralPath $readmePath
    Test-RequiredBadges `
        -Location 'README.md' `
        -Content $readmeContent `
        -Format 'gfm' `
        -RepositoryUrl 'https://github.com/KyleMHB/GlobalTemplates'

    if ($readmeContent -match '<script\b') {
        Add-ValidationError -Location 'README.md' -Message 'embedded scripts are not allowed'
    }
}

if ($validationErrors.Count -gt 0) {
    foreach ($validationError in $validationErrors) {
        Write-Host "ERROR: $validationError" -ForegroundColor Red
    }

    Write-Host "Template validation failed with $($validationErrors.Count) error(s)." -ForegroundColor Red
    exit 1
}

Write-Host "Validated $($templateEntries.Count) templates successfully." -ForegroundColor Green
