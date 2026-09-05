[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$validatorPath = Join-Path $PSScriptRoot 'validate-templates.ps1'
$fixtureSourcePaths = @(
    'AGENTS.md'
    'LICENSE'
    'README.md'
    'templates.json'
    'Git'
    'Steam'
)
$failedTests = [System.Collections.Generic.List[string]]::new()

function Set-FixtureContent {
    param(
        [string]$FixtureRoot,
        [string]$RelativePath,
        [scriptblock]$Transform
    )

    $path = Join-Path $FixtureRoot $RelativePath
    $content = Get-Content -Raw -LiteralPath $path
    $updatedContent = & $Transform $content
    Set-Content -LiteralPath $path -Value $updatedContent -NoNewline
}

function Test-InvalidFixture {
    param(
        [string]$Name,
        [scriptblock]$Mutation,
        [string]$ExpectedError
    )

    $fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ("globaltemplates-validator-{0}" -f [guid]::NewGuid())
    $null = New-Item -ItemType Directory -Path $fixtureRoot

    try {
        foreach ($relativePath in $fixtureSourcePaths) {
            Copy-Item -LiteralPath (Join-Path $repositoryRoot $relativePath) -Destination $fixtureRoot -Recurse
        }

        & $Mutation $fixtureRoot
        $output = (& $validatorPath -RootPath $fixtureRoot *>&1 | Out-String)
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq 0) {
            $failedTests.Add("${Name}: validator unexpectedly succeeded")
        } elseif ($output -notmatch [regex]::Escape($ExpectedError)) {
            $failedTests.Add("${Name}: expected '$ExpectedError' but received: $output")
        } else {
            Write-Host "Passed: $Name" -ForegroundColor Green
        }
    } finally {
        Remove-Item -LiteralPath $fixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Test-ValidFixture {
    $fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ("globaltemplates-validator-{0}" -f [guid]::NewGuid())
    $null = New-Item -ItemType Directory -Path $fixtureRoot

    try {
        foreach ($relativePath in $fixtureSourcePaths) {
            Copy-Item -LiteralPath (Join-Path $repositoryRoot $relativePath) -Destination $fixtureRoot -Recurse
        }

        $output = (& $validatorPath -RootPath $fixtureRoot *>&1 | Out-String)
        $exitCodeVariable = Get-Variable -Name LASTEXITCODE -ErrorAction SilentlyContinue
        $exitCode = if ($null -eq $exitCodeVariable) { 0 } else { $exitCodeVariable.Value }

        if ($exitCode -ne 0) {
            $failedTests.Add("pristine fixture: validator failed: $output")
        } else {
            Write-Host 'Passed: pristine fixture' -ForegroundColor Green
        }
    } finally {
        Remove-Item -LiteralPath $fixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$koFiMarkdown = '[![Support me on Ko-fi](https://img.shields.io/badge/Support_me_on_Ko--fi-72a4f2?style=for-the-badge&logo=kofi&logoColor=white)](https://ko-fi.com/I7L525WMJ6)'

Test-ValidFixture

Test-InvalidFixture -Name 'missing publicFacing property' -ExpectedError "missing 'publicFacing'" -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'templates.json' -Transform {
        param($content)
        [regex]::Replace($content, '(?m)^\s+"publicFacing": true,\r?\n', '', 1)
    }
}

Test-InvalidFixture -Name 'invalid publicFacing type' -ExpectedError "'publicFacing' must be a Boolean" -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'templates.json' -Transform {
        param($content)
        [regex]::Replace($content, '"publicFacing": true', '"publicFacing": "yes"', 1)
    }
}

Test-InvalidFixture -Name 'missing Public copy heading' -ExpectedError "must contain exactly one '## Public copy' heading; found 0" -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Git/readme-template.md' -Transform {
        param($content)
        $content.Replace('## Public copy', '## Public prose')
    }
}

Test-InvalidFixture -Name 'missing Unslop workflow' -ExpectedError 'missing required Unslop workflow' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Git/readme-template.md' -Transform {
        param($content)
        $content.Replace(
            'Run the installed `unslop` skill with its default crisp-human preset',
            'Review the public prose manually'
        )
    }
}

Test-InvalidFixture -Name 'missing Unslop fallback' -ExpectedError 'missing Unslop fallback disclosure' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Git/readme-template.md' -Transform {
        param($content)
        $content.Replace(
            'If `unslop` or its validation scripts are unavailable',
            'When automated review is unavailable'
        )
    }
}

Test-InvalidFixture -Name 'AGENTS public-copy mapping drift' -ExpectedError "AGENTS.md public copy: missing template mapping 'Git/readme-template.md'" -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'AGENTS.md' -Transform {
        param($content)
        $content.Replace(
            '| `README.md` | `Git/readme-template.md` | Explicit template-backed request | Yes |',
            '| `README.md` | `Git/readme-template.md` | Explicit template-backed request | No |'
        )
    }
}

Test-InvalidFixture -Name 'README public-copy mapping drift' -ExpectedError "README.md public copy: missing template mapping 'Git/readme-template.md'" -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'README.md' -Transform {
        param($content)
        $content.Replace(
            '| `README.md` | `Git/readme-template.md` | GFM | Yes |',
            '| `README.md` | `Git/readme-template.md` | GFM | No |'
        )
    }
}

foreach ($requiredHeading in @('Use when', 'Evidence', 'Update rules', 'Validation', 'Delivery')) {
    $missingHeadingMutation = {
        param($fixtureRoot)
        Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Git/readme-template.md' -Transform {
            param($content)
            $content.Replace("## $requiredHeading", "## Removed $requiredHeading")
        }
    }.GetNewClosure()

    Test-InvalidFixture `
        -Name "missing $requiredHeading heading" `
        -ExpectedError "must contain exactly one '## $requiredHeading' heading; found 0" `
        -Mutation $missingHeadingMutation

    $duplicateHeadingMutation = {
        param($fixtureRoot)
        Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Git/readme-template.md' -Transform {
            param($content)
            "$content`n`n## $requiredHeading`n"
        }
    }.GetNewClosure()

    Test-InvalidFixture `
        -Name "duplicate $requiredHeading heading" `
        -ExpectedError "must contain exactly one '## $requiredHeading' heading; found 2" `
        -Mutation $duplicateHeadingMutation
}

Test-InvalidFixture -Name 'orphan template file' -ExpectedError "contains unmapped template 'Git/orphan-template.md'" -Mutation {
    param($fixtureRoot)
    Set-Content -LiteralPath (Join-Path $fixtureRoot 'Git/orphan-template.md') -Value '# Orphan Template'
}

Test-InvalidFixture -Name 'missing manifest source' -ExpectedError 'template source is missing: Git/missing-template.md' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'templates.json' -Transform {
        param($content)
        $content.Replace('Git/readme-template.md', 'Git/missing-template.md')
    }
}

Test-InvalidFixture -Name 'missing Ko-fi badge' -ExpectedError 'missing or malformed linked Ko-fi badge' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Git/readme-template.md' -Transform {
        param($content)
        $content.Replace($koFiMarkdown, '')
    }
}

Test-InvalidFixture -Name 'incorrect Ko-fi ID' -ExpectedError 'missing or malformed linked Ko-fi badge' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Git/readme-template.md' -Transform {
        param($content)
        $content.Replace('I7L525WMJ6', 'INVALID')
    }
}

Test-InvalidFixture -Name 'broken root badge link' -ExpectedError 'missing or malformed linked Ko-fi badge' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'README.md' -Transform {
        param($content)
        $content.Replace('https://ko-fi.com/I7L525WMJ6', 'https://ko-fi.com/INVALID')
    }
}

Test-InvalidFixture -Name 'missing repository placeholder' -ExpectedError 'missing or malformed linked GitHub repository badge' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Git/readme-template.md' -Transform {
        param($content)
        $content.Replace('{repository-url}', 'https://github.com/KyleMHB/HardcodedProject')
    }
}

Test-InvalidFixture -Name 'malformed Steam BBCode' -ExpectedError 'missing or malformed linked Ko-fi badge' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Steam/steam-description-template.md' -Transform {
        param($content)
        $content.Replace('logoColor=white[/img][/url]', 'logoColor=white[/img]')
    }
}

Test-InvalidFixture -Name 'unbalanced general Steam BBCode' -ExpectedError 'unbalanced BBCode' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Steam/steam-description-template.md' -Transform {
        param($content)
        $content.Replace('- Bold: `[b]text[/b]`', '- Bold: `[b]text`')
    }
}

Test-InvalidFixture -Name 'contradictory Steam Links rule' -ExpectedError 'missing conditional Links rule' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Steam/steam-description-template.md' -Transform {
        param($content)
        $content.Replace(
            'Links is conditional. Include it only when at least one confirmed and permitted link remains',
            'Links is required even when no confirmed and permitted link remains'
        )
    }
}

Test-InvalidFixture -Name 'prohibited script' -ExpectedError 'embedded scripts are not allowed' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Git/readme-template.md' -Transform {
        param($content)
        "$content`n<script src='https://example.com/widget.js'></script>"
    }
}

Test-InvalidFixture -Name 'missing required How to Use guidance' -ExpectedError 'missing required How to Use guidance' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Steam/steam-description-template.md' -Transform {
        param($content)
        $content.Replace('### How to Use', '### Usage Notes')
    }
}

Test-InvalidFixture -Name 'missing fork difference guidance' -ExpectedError 'missing required fork purpose and difference guidance' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Steam/steam-description-template.md' -Transform {
        param($content)
        $content.Replace('differences from the upstream mod', 'relationship to the upstream mod')
    }
}

Test-InvalidFixture -Name 'fork history before How to Use' -ExpectedError 'reader-first Steam section order is invalid' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Steam/steam-description-template.md' -Transform {
        param($content)
        $content.Replace('3. How to Use', '3. Fork History, required for forks').Replace('7. Fork History, required for forks', '7. How to Use')
    }
}

Test-InvalidFixture -Name 'dependencies before How to Use' -ExpectedError 'reader-first Steam section order is invalid' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Steam/steam-description-template.md' -Transform {
        param($content)
        $content.Replace('3. How to Use', '3. Requirements and Dependencies, when applicable').Replace('5. Requirements and Dependencies, when applicable', '5. How to Use')
    }
}

Test-InvalidFixture -Name 'missing Links-last guidance' -ExpectedError 'missing Links-last rule' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Steam/steam-description-template.md' -Transform {
        param($content)
        $content.Replace('10. Links, always last', '10. Links').Replace('Links must be the final section.', 'Links belong near the end.')
    }
}

Test-InvalidFixture -Name 'Links before license' -ExpectedError 'reader-first Steam section order is invalid' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Steam/steam-description-template.md' -Transform {
        param($content)
        $content.Replace('9. License and Forking Policy', '9. TEMP SECTION').Replace('10. Links, always last', '10. License and Forking Policy').Replace('9. TEMP SECTION', '9. Links, always last')
    }
}

Test-InvalidFixture -Name 'missing player-facing order' -ExpectedError 'reader-first Steam section order is invalid' -Mutation {
    param($fixtureRoot)
    Set-FixtureContent -FixtureRoot $fixtureRoot -RelativePath 'Steam/steam-description-template.md' -Transform {
        param($content)
        $content.Replace('2. Features', '2. Overview')
    }
}

if ($failedTests.Count -gt 0) {
    foreach ($failure in $failedTests) {
        Write-Host "FAILED: $failure" -ForegroundColor Red
    }

    exit 1
}

Write-Host 'All validator tests passed.' -ForegroundColor Green
