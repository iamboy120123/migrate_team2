<#
.SYNOPSIS
Prepare an offline migration-team workspace from this source bundle.
.DESCRIPTION
Checks Python 3.11+, initializes settings, restores/freezes the kit, prepares or
verifies a synthetic target snapshot, checks integrity and writes the dashboard.
Installs the repo-local blendata-odi-team skill and a managed AGENTS.md reference.
The default is a numbered Thai question/answer wizard with help and a summary.
Use -NonInteractive for unattended execution. An empty destination can be bootstrapped with -WorkspaceDir. Existing settings,
jobs and the selected target snapshot are preserved. Git initialization is opt-in
and local only. No demo jobs or real ODI import are created.
Oracle access (wizard questions 7-8, or -Db* parameters) is optional and handled by
tools/dbcore: the team policy goes to shared/team.json "db", the connection (no
password) to shared/db.local.json. The default is human-run SQL with no connection.
python-oracledb is installed and a read-only connection test (SELECT USER FROM dual)
is run only when explicitly chosen; passwords come from ORA_RO_PASSWORD /
ORA_RW_PASSWORD or a hidden prompt and are never written to any file.
.EXAMPLE
.\setup_workspace.ps1
.EXAMPLE
.\setup_workspace.ps1 -WorkspaceDir E:\AI_Blendata_to_ODI\Migrate_Team\training_workspace
.EXAMPLE
.\setup_workspace.ps1 -WhatIf
.EXAMPLE
.\setup_workspace.ps1 -WorkspaceDir E:\Migration\Team -NonInteractive
.EXAMPLE
.\setup_workspace.ps1 -NonInteractive -DbAccess ai -DbEnv DEV -DbHost devdb.local -DbService DEVPDB -DbUserRo APP_RO -DbUserRw APP_RW -InstallOracleDriver -TestDbConnection
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Low')]
param(
    [string]$WorkspaceDir,
    [string]$PythonExecutable,
    [string]$TargetSource,
    [string]$WorkspaceName,
    [string[]]$SimulationReviewers,
    [switch]$InitializeGit,
    [switch]$NonInteractive,
    [ValidateSet('human', 'ai')][string]$DbAccess,
    [ValidateSet('ask', 'auto')][string]$DbSelectMode,
    [ValidateSet('split', 'single')][string]$DbUsers,
    [string]$DbEnv,
    [string]$DbHost,
    [ValidateRange(1, 65535)][int]$DbPort = 1521,
    [string]$DbService,
    [string]$DbUserRo,
    [string]$DbUserRw,
    [switch]$InstallOracleDriver,
    [switch]$TestDbConnection
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# PowerShell 7 may otherwise turn native stderr/nonzero exits into terminating errors.
$PSNativeCommandUseErrorActionPreference = $false

$sourceRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$stage = 'preflight'
$logPath = $null
$resultPath = $null
$pushed = $false
$steps = New-Object System.Collections.Generic.List[object]
$oldUtf8 = [Environment]::GetEnvironmentVariable('PYTHONUTF8', 'Process')
$oldIoEncoding = [Environment]::GetEnvironmentVariable('PYTHONIOENCODING', 'Process')
$oldConsoleEncoding = [Console]::OutputEncoding
$oldInputEncoding = [Console]::InputEncoding
$utf8 = New-Object System.Text.UTF8Encoding($false)
$script:setupPython = $null
$script:setupLauncher = $null
$script:wizardAnswers = $null
$script:configureSettings = $PSBoundParameters.ContainsKey('WorkspaceName') -or $PSBoundParameters.ContainsKey('SimulationReviewers')
$script:setupGit = $null
$script:wizardPythonChoice = $null
$script:wizardTargetChoice = $null
$script:configureDbPolicy = $PSBoundParameters.ContainsKey('DbAccess') -or $PSBoundParameters.ContainsKey('DbSelectMode') -or
                            $PSBoundParameters.ContainsKey('DbUsers')
$script:configureDbConnection = $PSBoundParameters.ContainsKey('DbHost')
$script:dbPortBound = $PSBoundParameters.ContainsKey('DbPort')
$script:wizardDbChoice = $null
$script:wizardDbAfter = $null
$script:dbWarnings = New-Object System.Collections.Generic.List[string]

function Read-SetupJson([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        try { return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { return $null }
    }
    return $null
}

function Get-SetupProperty($Object, [string]$Name, $Default) {
    if ($null -ne $Object -and $Object.PSObject.Properties.Name -contains $Name -and $null -ne $Object.$Name -and [string]$Object.$Name -ne '') {
        return $Object.$Name
    }
    return $Default
}

function Get-SetupDbState([string]$Root) {
    # Existing team policy and this machine's connection (no password is ever stored there).
    $team = Read-SetupJson (Join-Path $Root 'shared/team.json')
    $db = Get-SetupProperty $team 'db' $null
    $local = Read-SetupJson (Join-Path $Root 'shared/db.local.json')
    $dbEnv = ([string](Get-SetupProperty $local 'default' (Get-SetupProperty $db 'default_env' 'DEV'))).ToUpperInvariant()
    $cons = Get-SetupProperty $local 'connections' $null
    $conn = Get-SetupProperty $cons $dbEnv $null
    return [PSCustomObject]@{
        Access = [string](Get-SetupProperty $db 'ai_access' 'human')
        SelectMode = [string](Get-SetupProperty $db 'select_mode' 'ask')
        Users = [string](Get-SetupProperty $db 'users' 'split')
        Env = $dbEnv
        Connection = $conn
    }
}

function Test-SetupDbValue([string]$Kind, [string]$Value, [bool]$Required = $true) {
    if (-not $Value) { if ($Required) { return 'ต้องระบุค่า' } else { return $null } }
    switch ($Kind) {
        'env' { if ($Value -cnotmatch '^[A-Z][A-Z0-9_]{0,29}$') { return 'ใช้ A-Z 0-9 _ ตัวพิมพ์ใหญ่ ขึ้นต้นด้วยตัวอักษร เช่น DEV' } }
        'host' { if ($Value -notmatch '^[A-Za-z0-9][A-Za-z0-9.\-]{0,252}$') { return 'ใช้ชื่อเครื่องหรือ IP ไม่มีช่องว่าง' } }
        'port' { if ($Value -notmatch '^\d{1,5}$' -or [int]$Value -lt 1 -or [int]$Value -gt 65535) { return 'ใส่ตัวเลข 1-65535' } }
        'service' { if ($Value -notmatch '^[A-Za-z][A-Za-z0-9_.$#\-]{0,127}$') { return 'รูปแบบ service name ไม่ถูกต้อง' } }
        'user' {
            if ($Value -notmatch '^[A-Za-z][A-Za-z0-9_$#]{0,127}$') { return 'รูปแบบ username ไม่ถูกต้อง' }
            if (@('SYS', 'SYSTEM') -contains $Value.ToUpperInvariant()) { return 'ห้ามใช้ SYS / SYSTEM — ขอ user เฉพาะ schema ของงานจาก DBA' }
        }
    }
    return $null
}

function Resolve-SetupPath([string]$Value) {
    return [System.IO.Path]::GetFullPath(
        $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Value))
}

function Get-SetupLayout([string]$Value) {
    $root = Resolve-SetupPath $Value
    $same = $root.TrimEnd([char[]]'\/').Equals(
        $sourceRoot.TrimEnd([char[]]'\/'), [System.StringComparison]::OrdinalIgnoreCase)
    if (-not $same -and (Test-Within $root $sourceRoot)) {
        throw 'Choose a sibling destination outside the source workspace, rather than a folder inside its source tree.'
    }
    if (Test-Path -LiteralPath $root -PathType Leaf) { throw 'WorkspaceDir points to a file, not a directory.' }
    $entry = Join-Path $root 'tools/workspace.py'
    $known = (Test-Path -LiteralPath $entry -PathType Leaf) -and
             ((Test-Path -LiteralPath (Join-Path $root 'workspace.json') -PathType Leaf) -or $same)
    if (-not $known -and (Test-Path -LiteralPath $root) -and @(Get-ChildItem -LiteralPath $root -Force).Count -gt 0) {
        throw 'Destination is nonempty and is not a recognized workspace. Choose an empty/new directory; no files were overwritten.'
    }
    return [PSCustomObject]@{ Root = $root; Same = $same; Bootstrap = -not $known; Launcher = $entry }
}

function Get-SetupReviewers([string]$Root) {
    $path = Join-Path $Root 'shared/approvers.json'
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $value = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($value.PSObject.Properties.Name -contains 'simulation_reviewers') {
            return @($value.simulation_reviewers)
        }
    }
    return @('DEMO_SA')
}

function Read-SetupAnswer([string]$Prompt) {
    if ([Console]::IsInputRedirected) {
        Write-Host $Prompt -NoNewline
        $value = [Console]::ReadLine()
        if ($null -eq $value) { throw [System.OperationCanceledException]::new('Input ended before confirmation. Use -NonInteractive for unattended setup.') }
        return $value.Trim()
    }
    return ([string](Read-Host $Prompt)).Trim()
}

function Read-SetupText([string]$Title, [string]$What, [string]$Use, [string]$Default,
                        [string]$More, [scriptblock]$Validate) {
    Write-Host "`n$Title" -ForegroundColor Cyan
    Write-Host "   คืออะไร:   $What"
    Write-Host "   ใช้ทำอะไร: $Use"
    Write-Host "   ค่าแนะนำ:  $Default"
    Write-Host '   Enter = ใช้ค่าแนะนำ | ? = รายละเอียด | q = ยกเลิกโดยไม่สร้างไฟล์'
    while ($true) {
        $value = Read-SetupAnswer '   คำตอบ: '
        if ($value -eq '?') { Write-Host "   $More" -ForegroundColor Yellow; continue }
        if ($value -eq 'q') { throw [System.OperationCanceledException]::new('Cancelled by user before setup.') }
        if (-not $value) { $value = $Default }
        $value = $value.Trim().Trim('"')
        $problem = if ($Validate) { & $Validate $value } else { $null }
        if ($problem) { Write-Host "   ตอบไม่ถูกต้อง: $problem" -ForegroundColor Yellow; continue }
        return $value
    }
}

function Read-SetupChoice([string]$Title, [string]$What, [string]$Use, [object[]]$Choices,
                          [int]$Default, [string]$Why, [string]$More) {
    Write-Host "`n$Title" -ForegroundColor Cyan
    Write-Host "   คืออะไร:   $What"
    Write-Host "   ใช้ทำอะไร: $Use"
    for ($i = 0; $i -lt $Choices.Count; $i++) {
        $tag = if ($i + 1 -eq $Default) { ' [แนะนำ]' } else { '' }
        Write-Host ('   {0}. {1}{2}' -f ($i + 1), $Choices[$i].label, $tag)
    }
    Write-Host "   เหตุผล: $Why"
    Write-Host "   Enter = ข้อ $Default | ? = รายละเอียด | q = ยกเลิกโดยไม่สร้างไฟล์"
    while ($true) {
        $value = Read-SetupAnswer '   เลือก: '
        if ($value -eq '?') { Write-Host "   $More" -ForegroundColor Yellow; continue }
        if ($value -eq 'q') { return 'q' }
        if (-not $value) { return $Choices[$Default - 1].value }
        for ($i = 0; $i -lt $Choices.Count; $i++) {
            if ($value -eq [string]($i + 1) -or $value -eq $Choices[$i].value) { return $Choices[$i].value }
        }
        Write-Host '   กรุณาเลือกเลขที่แสดง หรือพิมพ์ ? เพื่อดูรายละเอียด' -ForegroundColor Yellow
    }
}

function Invoke-SetupWizard {
    Write-Host ('=' * 64) -ForegroundColor Cyan
    Write-Host 'Setup Workspace — ถามตอบทีละข้อ (SIMULATION ONLY)' -ForegroundColor Cyan
    Write-Host 'รูปแบบอ้างอิง: Migrate_ODI_Team2\kit\setup_migrate.ps1 รุ่น 2.15.0'
    Write-Host 'GitHub = คนทำเอง | ฐานข้อมูล Oracle = ตามคำตอบข้อ 7-8 (ค่าเริ่มต้น: คนรันเอง ไม่ต่อฐาน)'
    Write-Host 'simulate ยังออฟไลน์เสมอ | ไม่มีการถามหรือเก็บรหัสผ่านในขั้นตอนนี้'
    Write-Host 'คำตอบยังไม่ถูกเขียนลง workspace จนกว่าจะดูสรุปและยืนยัน'
    while ($true) {
        $defaultRoot = if ($script:WorkspaceDir) { $script:WorkspaceDir } else { $sourceRoot }
        $script:WorkspaceDir = Read-SetupText '[1/8] ตั้ง workspace ที่ไหน' 'โฟลเดอร์รวมเครื่องมือและงานของทีม' `
            'เลือก workspace เดิม หรือโฟลเดอร์ว่างใหม่ข้างโฟลเดอร์ต้นทาง' $defaultRoot `
            'ใช้ path เต็มได้ เช่น E:\Migration\training_workspace; workspace เดิมจะคงงานและค่าที่มีอยู่ โฟลเดอร์ที่มีข้อมูลอื่นจะไม่ถูกเขียนทับ' {
                param($v); try { $null = Get-SetupLayout $v } catch { return $_.Exception.Message }
            }
        $layout = Get-SetupLayout $script:WorkspaceDir
        $script:WorkspaceDir = $layout.Root
        $defaultName = if ($script:WorkspaceName) { $script:WorkspaceName } else { Split-Path -Leaf $layout.Root }
        $metadataPath = Join-Path $layout.Root 'workspace.json'
        if (-not $script:WorkspaceName -and (Test-Path -LiteralPath $metadataPath -PathType Leaf)) {
            $metadata = Get-Content -LiteralPath $metadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($metadata.PSObject.Properties.Name -contains 'workspace_name') { $defaultName = [string]$metadata.workspace_name }
        }
        $script:WorkspaceName = Read-SetupText '[2/8] ชื่อ workspace / ทีม' 'ชื่อแสดงสำหรับพื้นที่ทำงานนี้' `
            'บันทึกใน workspace.json โดยไม่เปลี่ยนชื่อโฟลเดอร์หรือชื่อ Job' $defaultName `
            'ตั้งเป็นชื่อที่ทีมจำได้ เช่น Migration Training Team; รองรับภาษาไทยและช่องว่าง ยาวไม่เกิน 80 ตัว' {
                param($v); if (-not $v -or $v.Length -gt 80 -or $v -match '[\x00-\x1f]') { return 'ใส่ชื่อ 1–80 ตัวอักษร ไม่ใช้ตัวควบคุม' }
            }
        $pythonChoice = Read-SetupChoice '[3/8] เลือก Python ที่ใช้' 'ตัวรันเครื่องมือ ต้องเป็น Python 3.11 ขึ้นไป' `
            'ตรวจ interpreter ก่อนเขียนไฟล์ ไม่ติดตั้งโปรแกรมเพิ่ม' @(
                @{ value = 'auto'; label = 'ค้นหา Python ในเครื่องอัตโนมัติ' },
                @{ value = 'custom'; label = 'ระบุ path ของ Python เอง' }
            ) $(if ($script:wizardPythonChoice) { if ($script:wizardPythonChoice -eq 'custom') { 2 } else { 1 } } elseif ($script:PythonExecutable) { 2 } else { 1 }) 'ใช้ Python ที่มีอยู่ได้ทันที หากมีหลายรุ่นจึงเลือก path เอง' `
            'รองรับ python, py launcher และ python3; ไม่ใช้ Windows Store alias และไม่ขอรหัสผ่าน'
        if ($pythonChoice -eq 'q') { throw [System.OperationCanceledException]::new('Cancelled by user before setup.') }
        $script:wizardPythonChoice = $pythonChoice
        if ($pythonChoice -eq 'custom') {
            $script:PythonExecutable = Read-SetupText '   Path ของ Python executable' 'ไฟล์ python.exe ที่จะใช้' `
                'เลือก interpreter โดยตรง ไม่ใส่ argument ต่อท้าย' ([string]$script:PythonExecutable) `
                'ตัวอย่าง C:\Python313\python.exe; ใส่ path ที่ติดตั้งจริงในเครื่องนี้' {
                    param($v); if (-not $v) { return 'ต้องระบุ path ของ Python' }; try { $null = Find-SetupPython $v } catch { return $_.Exception.Message }
                }
        }
        else { $script:PythonExecutable = '' }
        $selectedPython = Find-SetupPython $script:PythonExecutable
        $script:PythonExecutable = $selectedPython.Executable
        Write-Host "   ตรวจแล้ว: Python $($selectedPython.Version) — $($selectedPython.Executable)" -ForegroundColor Green

        $hasTarget = Test-Path -LiteralPath (Join-Path $layout.Root 'shared/target/current.json') -PathType Leaf
        $targets = @()
        if ($hasTarget) { $targets += @{ value = 'preserve'; label = 'ตรวจและใช้ target snapshot ที่ workspace เลือกไว้อยู่แล้ว' } }
        $targets += @{ value = 'sample'; label = 'ใช้ schema และข้อมูลทดสอบสังเคราะห์ที่มากับชุดนี้' }
        $targets += @{ value = 'custom'; label = 'ระบุโฟลเดอร์ synthetic target ชุดอื่น' }
        $targetDefault = if ($script:TargetSource) { $targets.Count } else { 1 }
        if ($script:wizardTargetChoice) {
            for ($i = 0; $i -lt $targets.Count; $i++) {
                if ($targets[$i].value -eq $script:wizardTargetChoice) { $targetDefault = $i + 1 }
            }
        }
        $targetChoice = Read-SetupChoice '[4/8] ข้อมูลอ้างอิงปลายทางที่ใช้ร่วมกัน' 'ชุด schema, source rows และ expected results สำหรับการจำลอง' `
            'สร้าง snapshot ที่หลาย Job อ้างร่วมกันได้; งานเดิมยังใช้ snapshot ที่ล็อกไว้' $targets $targetDefault `
            'workspace เดิมควรใช้ target เดิม; เริ่มฝึกใหม่ใช้ชุดตัวอย่างได้ทันที' `
            'นี่ไม่ใช่ Smart Export จริง โฟลเดอร์ custom ต้องมี columns/all_tab_columns.csv และ fixtures/rows.json และต้องสอดคล้องกับ workflow ที่จะทดสอบ'
        if ($targetChoice -eq 'q') { throw [System.OperationCanceledException]::new('Cancelled by user before setup.') }
        $script:wizardTargetChoice = $targetChoice
        if ($targetChoice -eq 'custom') {
            $script:TargetSource = Read-SetupText '   โฟลเดอร์ synthetic target' 'โฟลเดอร์ที่มี columns/ และ fixtures/' `
                'นำไฟล์เข้า snapshot ใหม่โดยไม่เขียนทับ snapshot เดิม' ([string]$script:TargetSource) `
                'ใช้รูปแบบเดียวกับ samples/target; ไม่ใส่ connection string หรือรหัสผ่าน' {
                    param($v); try {
                        if (-not $v) { return 'ต้องระบุ path' }
                        $p = Resolve-SetupPath $v
                        foreach ($f in @('columns/all_tab_columns.csv', 'fixtures/rows.json')) {
                            if (-not (Test-Path -LiteralPath (Join-Path $p $f) -PathType Leaf)) { return "ไม่พบ $f" }
                        }
                    } catch { return $_.Exception.Message }
                }
            $script:TargetSource = Resolve-SetupPath $script:TargetSource
        }
        elseif ($targetChoice -eq 'sample') {
            $bundle = if ($layout.Bootstrap) { $sourceRoot } else { $layout.Root }
            $script:TargetSource = Join-Path $bundle 'samples/target'
        }
        else { $script:TargetSource = '' }

        $existingReviewers = @(Get-SetupReviewers $layout.Root)
        $reviewerDefault = if ($script:SimulationReviewers) { $script:SimulationReviewers -join ',' } else { $existingReviewers -join ',' }
        $reviewerText = Read-SetupText '[5/8] รายชื่อผู้รีวิวจำลอง' 'ชื่อ persona ที่ใช้ approve --simulation' `
            'เพิ่มชื่อที่ทดลองอนุมัติได้ โดยเก็บรายชื่อเดิมไว้ ไม่สร้างผู้อนุมัติ production' $reviewerDefault `
            'คั่นหลายชื่อด้วย comma เช่น DEMO_SA,QA_REVIEWER; ใช้อักษรอังกฤษนำหน้า ตามด้วยตัวอักษร ตัวเลข หรือ _ ยาวไม่เกิน 50 ตัวต่อชื่อ' {
                param($v)
                $names = @($v -split ',' | ForEach-Object { $_.Trim() })
                if (-not $v -or @($names | Where-Object { $_ -notmatch '^[A-Za-z][A-Za-z0-9_]{0,49}$' }).Count) { return 'รูปแบบชื่อไม่ถูกต้อง หรือมีชื่อว่าง' }
            }
        $script:SimulationReviewers = @(@($existingReviewers) + @($reviewerText -split ',' | ForEach-Object { $_.Trim() }) | Select-Object -Unique)
        $gitChoice = Read-SetupChoice '[6/8] เตรียม Git repository ในเครื่องหรือไม่' 'เก็บประวัติ source และงานใน Git ของเครื่องนี้' `
            'เลือกสร้าง repo เปล่าได้ ยังไม่ commit, push, สร้าง remote หรือเปลี่ยน GitHub settings' @(
                @{ value = 'no'; label = 'ยังไม่สร้าง / ใช้ repository เดิม' },
                @{ value = 'yes'; label = 'สร้าง Git repository ใน workspace หากยังไม่มี' }
            ) $(if ($script:InitializeGit) { 2 } else { 1 }) 'เริ่มจำลองได้ก่อนโดยไม่ต้องตั้ง Git; ถ้ามี repo เดิมระบบจะรักษาไว้' `
            'หากเลือกสร้าง ต้องมี git ในเครื่อง จะใช้ branch main และไม่มี initial commit; หากอยู่ใน repo/worktree เดิมจะใช้ของเดิม'
        if ($gitChoice -eq 'q') { throw [System.OperationCanceledException]::new('Cancelled by user before setup.') }
        $script:InitializeGit = ($gitChoice -eq 'yes')
        if ($script:InitializeGit -and -not (Get-Command git -CommandType Application -ErrorAction SilentlyContinue)) {
            Write-Host '   ไม่พบ Git ในเครื่อง กรุณากลับไปเลือกยังไม่สร้าง หรือติดตั้ง Git ก่อน' -ForegroundColor Yellow
            continue
        }

        # [7/8] กติกาการเข้าฐาน Oracle (shared/team.json → db) — ใช้กับ tools/dbcore เท่านั้น ไม่เปลี่ยน simulator
        $dbState = Get-SetupDbState $layout.Root
        $accessNow = if ($script:DbAccess) { $script:DbAccess } else { $dbState.Access }
        $dbAccessChoice = Read-SetupChoice '[7/8] ใครเป็นผู้รัน SQL บนฐาน Oracle จริง' 'กติกาทีมสำหรับ Run Pack / DDL / ตรวจสอบบนฐานจริง (ไม่เกี่ยวกับ simulate ที่ออฟไลน์เสมอ)' `
            'กำหนดว่าระบบ/AI ต่อฐานได้หรือไม่ ทุกแผนยังต้องได้รับอนุญาตจากคน และทุกครั้งถูกบันทึก' @(
                @{ value = 'human'; label = 'คนรันเองทั้งหมด — ระบบเตรียมแผนและบอกขั้นตอนทีละไฟล์ (ไม่ต่อฐาน)' },
                @{ value = 'ai'; label = 'ระบบ/AI รันได้ หลังคนอนุญาตแต่ละแผน (python-oracledb)' }
            ) $(if ($accessNow -eq 'ai') { 2 } else { 1 }) 'เริ่มแบบคนรันก่อนปลอดภัยที่สุด เปลี่ยนภายหลังได้ด้วย workspace.py db-policy' `
            'คนรัน = ไม่มีการต่อฐานจากเครื่องมือ · ระบบรัน = ต้องมี host/service/user และรหัสผ่านจากตัวแปร ORA_RO_PASSWORD / ORA_RW_PASSWORD หรือพิมพ์ตอนรัน (ไม่เก็บ) · คำสั่งเขียนถามเสมอ · DROP/TRUNCATE/DELETE ไม่มี WHERE ต้องพิมพ์ชื่อตารางยืนยัน · ไฟล์ที่แก้หลังสร้างแผนรันไม่ได้'
        if ($dbAccessChoice -eq 'q') { throw [System.OperationCanceledException]::new('Cancelled by user before setup.') }
        $script:DbAccess = $dbAccessChoice
        # Keeping the default human policy writes nothing; choosing ai (or changing an ai policy) is saved.
        $script:configureDbPolicy = ($dbAccessChoice -eq 'ai' -or $dbState.Access -ne 'human')
        if ($dbAccessChoice -eq 'ai') {
            $modeNow = if ($script:DbSelectMode) { $script:DbSelectMode } else { $dbState.SelectMode }
            $script:DbSelectMode = Read-SetupChoice '   [7.1] คำสั่ง SELECT (อ่านอย่างเดียว) ต้องถามก่อนทุกครั้งไหม' 'ระดับการขออนุญาตของคำสั่งอ่าน' `
                'คำสั่งที่เขียน / แก้โครงสร้างถามเสมอไม่ว่าเลือกข้อใด' @(
                    @{ value = 'ask'; label = 'ถามก่อนทุกครั้ง รวม SELECT' },
                    @{ value = 'auto'; label = 'SELECT ใน Run Pack รันต่อเนื่อง (L3 รายแถว / นอก Run Pack / PROD ยังถาม)' }
                ) $(if ($modeNow -eq 'auto') { 2 } else { 1 }) 'เริ่มจากถามทุกครั้งจนทีมคุ้นกับแผนที่ระบบแสดง' `
                'auto ใช้กับ --run-read; ถ้าไม่แน่ใจเลือก ask'
            if ($script:DbSelectMode -eq 'q') { throw [System.OperationCanceledException]::new('Cancelled by user before setup.') }
            $usersNow = if ($script:DbUsers) { $script:DbUsers } else { $dbState.Users }
            $script:DbUsers = Read-SetupChoice '   [7.2] ใช้ user ฐานข้อมูลแบบไหน' 'การแยกสิทธิ์อ่าน / เขียน' `
                'split: SELECT ใช้ user อ่านอย่างเดียวพร้อม session READ ONLY · คำสั่งเขียนใช้ user ที่เขียนได้' @(
                    @{ value = 'split'; label = 'แยก 2 user: อ่านอย่างเดียว + เขียนได้' },
                    @{ value = 'single'; label = 'user เดียวทุกคำสั่ง' }
                ) $(if ($usersNow -eq 'single') { 2 } else { 1 }) 'แยก user ป้องกัน SELECT ไปแก้ข้อมูลโดยไม่ตั้งใจ' `
                'ขอ user จาก DBA ที่มีสิทธิ์เฉพาะ schema ของงาน ห้ามใช้ SYS / SYSTEM; ยังไม่มี user ที่เขียนได้ก็เลือก split แล้วเว้นว่างได้'
            if ($script:DbUsers -eq 'q') { throw [System.OperationCanceledException]::new('Cancelled by user before setup.') }

            # [8/8] ค่าการเชื่อมต่อของเครื่องนี้ (shared/db.local.json — ไม่มีรหัสผ่าน ไม่ขึ้น Git)
            $hasConn = $null -ne $dbState.Connection
            $connDefault = if ($script:wizardDbChoice) { if ($script:wizardDbChoice -eq 'now') { 1 } else { 2 } } elseif ($hasConn) { 2 } else { 1 }
            $connChoice = Read-SetupChoice '[8/8] ค่าการเชื่อมต่อ Oracle ของเครื่องนี้' 'host / port / service / username ของฐาน (ไม่มีรหัสผ่าน)' `
                'บันทึกใน shared/db.local.json เฉพาะเครื่องนี้ ไม่ขึ้น Git' @(
                    @{ value = 'now'; label = $(if ($hasConn) { "แก้ค่าการเชื่อมต่อ $($dbState.Env) ตอนนี้" } else { 'ตั้งค่าการเชื่อมต่อตอนนี้' }) },
                    @{ value = 'later'; label = $(if ($hasConn) { "ใช้ค่าเดิม ($($dbState.Env))" } else { 'ตั้งภายหลังด้วย workspace.py db-connect' }) }
                ) $connDefault 'ดูค่าได้จาก DBeaver: Edit Connection (Host / Port / Database-Service name)' `
                'รหัสผ่านไม่ถูกถามที่นี่: ตั้งตัวแปร ORA_RO_PASSWORD / ORA_RW_PASSWORD (ฐานที่ไม่ใช่ค่าเริ่มต้นเติม _<ENV>) ด้วย setx หรือพิมพ์ตอนระบบถามขณะรัน'
            if ($connChoice -eq 'q') { throw [System.OperationCanceledException]::new('Cancelled by user before setup.') }
            $script:wizardDbChoice = $connChoice
            $old = $dbState.Connection
            if ($connChoice -eq 'now') {
                $script:DbEnv = (Read-SetupText '   ชื่อฐาน (environment)' 'ชื่อที่แสดงทุกครั้งที่ขออนุญาตรัน' 'แยก DEV / SIT / PROD ให้เห็นชัดก่อนอนุญาต' `
                    $(if ($script:DbEnv) { $script:DbEnv } else { $dbState.Env }) 'DEV = ฐานพัฒนา · SIT = ทดสอบรวม · PROD = ฐานจริง (คำสั่งเขียนแก้ข้อมูลจริง ระบบถามก่อนเสมอ)' {
                        param($v); Test-SetupDbValue 'env' $v.ToUpperInvariant()
                    }).ToUpperInvariant()
                $script:DbHost = Read-SetupText '   host' 'ที่อยู่เครื่องฐานข้อมูล' 'ใช้ต่อด้วย python-oracledb แบบ thin' `
                    $(if ($script:DbHost) { $script:DbHost } else { [string](Get-SetupProperty $old 'host' '') }) 'DBeaver: Edit Connection → Host เช่น 10.0.0.12 หรือ devdb.company.local' {
                        param($v); Test-SetupDbValue 'host' $v
                    }
                $portText = Read-SetupText '   port' 'port ของ listener' 'Oracle ส่วนใหญ่ใช้ 1521' `
                    $(if ($script:dbPortBound) { [string]$script:DbPort } else { [string](Get-SetupProperty $old 'port' 1521) }) 'DBeaver: Edit Connection → Port' {
                        param($v); Test-SetupDbValue 'port' $v
                    }
                $script:DbPort = [int]$portText
                $script:dbPortBound = $true
                $script:DbService = Read-SetupText '   service name' 'ชื่อ service ของฐาน (ไม่ใช่ชื่อ schema)' 'ประกอบเป็น host:port/service' `
                    $(if ($script:DbService) { $script:DbService } else { [string](Get-SetupProperty $old 'service' '') }) 'DBeaver: Edit Connection → Database (Service Name) เช่น DEVPDB, ORCLPDB1' {
                        param($v); Test-SetupDbValue 'service' $v
                    }
                if ($script:DbUsers -eq 'single') {
                    $script:DbUserRw = Read-SetupText '   username (ทุกคำสั่ง)' 'user เดียวที่ใช้อ่านและเขียน' 'รหัสผ่านจากตัวแปร ORA_RW_PASSWORD หรือพิมพ์ตอนรัน' `
                        $(if ($script:DbUserRw) { $script:DbUserRw } else { [string](Get-SetupProperty $old 'user_rw' '') }) 'ขอ user จาก DBA ที่มีสิทธิ์เฉพาะ schema ของงาน ห้ามใช้ SYS / SYSTEM' {
                            param($v); Test-SetupDbValue 'user' $v
                        }
                    $script:DbUserRo = ''
                }
                else {
                    $script:DbUserRo = Read-SetupText '   username อ่านอย่างเดียว' 'user สำหรับ SELECT (session READ ONLY)' 'รหัสผ่านจากตัวแปร ORA_RO_PASSWORD หรือพิมพ์ตอนรัน' `
                        $(if ($script:DbUserRo) { $script:DbUserRo } else { [string](Get-SetupProperty $old 'user_ro' '') }) 'ขอ user read-only จาก DBA ห้ามใช้ SYS / SYSTEM' {
                            param($v); Test-SetupDbValue 'user' $v
                        }
                    $script:DbUserRw = Read-SetupText '   username ที่เขียนได้ (Enter เปล่า = ยังไม่มี)' 'user สำหรับ INSERT / MERGE / DDL' 'ยังไม่มีได้ — คำสั่งเขียนจะให้คนรันเองไปก่อน' `
                        $(if ($script:DbUserRw) { $script:DbUserRw } else { [string](Get-SetupProperty $old 'user_rw' '') }) 'รหัสผ่านจากตัวแปร ORA_RW_PASSWORD · ควรเขียนได้เฉพาะ schema ของงาน ห้ามใช้ SYS / SYSTEM' {
                            param($v); Test-SetupDbValue 'user' $v $false
                        }
                }
                $script:configureDbConnection = $true
            }
            else {
                # keep nothing from an earlier "now" answer (e = edit) — stale values must not reach setup
                $script:configureDbConnection = $false
                $script:DbEnv = ''; $script:DbHost = ''; $script:DbService = ''; $script:DbUserRo = ''; $script:DbUserRw = ''
                $script:dbPortBound = $false
            }
            if ($connChoice -eq 'now' -or $hasConn) {
                $afterDefault = switch ($script:wizardDbAfter) { 'install' { 2 } 'skip' { 3 } default { 1 } }
                $after = Read-SetupChoice '   [8.1] หลัง Setup เสร็จ' 'ติดตั้งตัวต่อ Oracle และทดสอบการเชื่อมต่อ' `
                    'ทดสอบ = SELECT USER, SYSDATE FROM dual ด้วย user อ่านอย่างเดียว บันทึกใน registry/db_queries.log' @(
                        @{ value = 'test'; label = 'ติดตั้ง python-oracledb (ถ้ายังไม่มี) แล้วทดสอบการเชื่อมต่อ' },
                        @{ value = 'install'; label = 'ติดตั้ง python-oracledb อย่างเดียว' },
                        @{ value = 'skip'; label = 'ยังไม่ติดตั้ง / ไม่ทดสอบ' }
                    ) $afterDefault 'รู้ทันทีว่า host / service / user / รหัสผ่านถูก ก่อนต้องใช้จริง' `
                    'ติดตั้ง = pip install --user oracledb (ต้องต่ออินเทอร์เน็ต ไม่ต้องลง Oracle Client) · ทดสอบจะถามรหัสผ่านแบบไม่แสดงบนจอถ้ายังไม่ตั้งตัวแปร · ล้มเหลวจะเตือนแต่ไม่ยกเลิก Setup'
                if ($after -eq 'q') { throw [System.OperationCanceledException]::new('Cancelled by user before setup.') }
                $script:wizardDbAfter = $after
                $script:InstallOracleDriver = ($after -ne 'skip')
                $script:TestDbConnection = ($after -eq 'test')
            }
            else { $script:InstallOracleDriver = $false; $script:TestDbConnection = $false }
        }
        else {
            Write-Host "`n[8/8] ข้าม — ทีมเลือกให้คนรัน SQL เอง จึงไม่ตั้งค่าการเชื่อมต่อ (เปลี่ยนภายหลัง: workspace.py db-policy --access ai)" -ForegroundColor DarkGray
            $script:DbSelectMode = $(if ($script:DbSelectMode) { $script:DbSelectMode } else { $dbState.SelectMode })
            $script:DbUsers = $(if ($script:DbUsers) { $script:DbUsers } else { $dbState.Users })
            $script:configureDbConnection = $false; $script:InstallOracleDriver = $false; $script:TestDbConnection = $false
            $script:DbEnv = ''; $script:DbHost = ''; $script:DbService = ''; $script:DbUserRo = ''; $script:DbUserRw = ''
            $script:dbPortBound = $false
        }

        Write-Host "`nสรุปก่อน Setup — ยังไม่เขียนไฟล์" -ForegroundColor Cyan
        Write-Host "   โฟลเดอร์:       $($layout.Root)"
        Write-Host "   ลักษณะงาน:     $(if ($layout.Bootstrap) { 'สร้าง workspace ใหม่จาก scaffold' } else { 'ตรวจและตั้งค่า workspace เดิม โดยคง Jobs ไว้' })"
        Write-Host "   ชื่อ workspace: $script:WorkspaceName"
        Write-Host "   Python:        $($selectedPython.Version) — $script:PythonExecutable"
        Write-Host "   Target:        $(if ($script:TargetSource) { $script:TargetSource } else { 'ตรวจและคง target ที่เลือกอยู่เดิม' })"
        Write-Host "   ผู้รีวิวจำลอง:   $($script:SimulationReviewers -join ', ')"
        Write-Host "   Git ในเครื่อง:  $(if ($script:InitializeGit) { 'เตรียม repo หากยังไม่มี' } else { 'คงเดิม ไม่สร้างเพิ่ม' })"
        Write-Host "   ฐานข้อมูล:      $(if ($script:DbAccess -eq 'ai') { "ระบบ/AI รันหลังคนอนุญาต · SELECT=$($script:DbSelectMode) · users=$($script:DbUsers)" } else { 'คนรัน SQL เองทั้งหมด (ระบบไม่ต่อฐาน)' })"
        if ($script:DbAccess -eq 'ai') {
            Write-Host "   การเชื่อมต่อ:    $(if ($script:configureDbConnection) { "$($script:DbEnv) $($script:DbHost):$($script:DbPort)/$($script:DbService) · ro=$(if ($script:DbUserRo) { $script:DbUserRo } else { '-' }) · rw=$(if ($script:DbUserRw) { $script:DbUserRw } else { '-' })" } elseif ($dbState.Connection) { "คงค่าเดิม ($($dbState.Env))" } else { 'ยังไม่ตั้ง (workspace.py db-connect)' })"
            Write-Host "   หลัง Setup:     $(if ($script:TestDbConnection) { 'ติดตั้งตัวต่อถ้ายังไม่มี + ทดสอบ SELECT USER FROM dual' } elseif ($script:InstallOracleDriver) { 'ติดตั้ง python-oracledb' } else { 'ไม่ติดตั้ง / ไม่ทดสอบ' })"
        }
        Write-Host '   Skill:         blendata-odi-team — ติดตั้งเฉพาะ workspace พร้อม AGENTS.md'
        Write-Host '   ขอบเขต:        simulate ออฟไลน์; ไม่สร้าง Project/Job · ไม่ต่อ GitHub · ไม่เก็บรหัสผ่าน · G4–G7 ยัง NOT_EXECUTED'
        $confirm = Read-SetupChoice 'ยืนยันคำตอบด้านบน' 'ตัดสินใจว่าจะเริ่มเขียนไฟล์หรือกลับไปแก้คำตอบ' `
            'เมื่อเลือกเริ่ม จะรัน preflight และขั้นตอน Setup ตามสรุปนี้' @(
                @{ value = 'y'; label = 'เริ่ม Setup ตามคำตอบ' },
                @{ value = 'e'; label = 'กลับไปแก้คำตอบ โดยใช้คำตอบล่าสุดเป็นค่าเริ่มต้น' },
                @{ value = 'q'; label = 'ยกเลิก ยังไม่สร้างหรือแก้ไฟล์' }
            ) 1 'เลือกเริ่มเมื่อข้อมูลถูกต้องครบ; หากยังไม่แน่ใจเลือกแก้คำตอบได้' `
            'ตอบ 1/y เพื่อเริ่ม, 2/e เพื่อแก้, 3/q เพื่อออก; q หรือ input สิ้นสุดก่อนยืนยันจะไม่สร้าง workspace'
        if ($confirm -eq 'q') { throw [System.OperationCanceledException]::new('Cancelled by user before setup.') }
        if ($confirm -eq 'e') { continue }
        $script:configureSettings = $true
        $script:wizardAnswers = [ordered]@{
            mode = 'simulation'; workspace = $layout.Root; workspace_name = $script:WorkspaceName
            python = $script:PythonExecutable; target_choice = $targetChoice; target_source = $script:TargetSource
            simulation_reviewers = @($script:SimulationReviewers); initialize_git = [bool]$script:InitializeGit
            db_access = $script:DbAccess; db_select_mode = $script:DbSelectMode; db_users = $script:DbUsers
            db_connection = $(if ($script:configureDbConnection) { [ordered]@{ env = $script:DbEnv; host = $script:DbHost; port = $script:DbPort
                service = $script:DbService; user_ro = $script:DbUserRo; user_rw = $script:DbUserRw } } else { $null })
            install_oracle_driver = [bool]$script:InstallOracleDriver; test_db_connection = [bool]$script:TestDbConnection
        }
        return
    }
}

function Write-SetupMessage([string]$Message) {
    Write-Host $Message
    if ($script:logPath) {
        Add-Content -LiteralPath $script:logPath -Value $Message -Encoding UTF8
    }
}

function Test-Within([string]$Child, [string]$Parent) {
    $prefix = $Parent.TrimEnd([char[]]'\/') + [System.IO.Path]::DirectorySeparatorChar
    return $Child.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Find-SetupPython([string]$Requested) {
    $names = if ($Requested) { @($Requested) } else { @('python', 'py', 'python3') }
    foreach ($name in $names) {
        $command = Get-Command -Name $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) { continue }
        $exe = $command.Source
        if (-not $Requested -and $exe -match '[\\/]Microsoft[\\/]WindowsApps[\\/]') { continue }
        $prefix = @()
        if ([System.IO.Path]::GetFileNameWithoutExtension($exe) -eq 'py') { $prefix = @('-3') }
        # Use Python single-quoted strings: Windows PowerShell 5.1 strips nested
        # double quotes when constructing a native process command line.
        $probe = 'import json,sys; print(json.dumps({''version'':list(sys.version_info[:3]),''executable'':sys.executable}))'
        $savedPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $output = @(& $exe @prefix -B -c $probe 2>$null)
            $code = $LASTEXITCODE
            if ($code -ne 0) { continue }
            $info = ($output -join "`n") | ConvertFrom-Json -ErrorAction Stop
            if ([int]$info.version[0] -eq 3 -and [int]$info.version[1] -ge 11) {
                return [PSCustomObject]@{
                    Executable = [string]$info.executable
                    Version = ($info.version -join '.')
                }
            }
        }
        catch { }
        finally { $ErrorActionPreference = $savedPreference }
    }
    throw 'Python 3.11 or newer was not found. Install Python, or pass -PythonExecutable with its executable path.'
}

function Invoke-SetupPython([string]$Label, [string[]]$Arguments) {
    Write-SetupMessage "`n$Label"
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $script:setupPython -B -X utf8 @Arguments 2>&1 | ForEach-Object {
            Write-SetupMessage ([string]$_)
        }
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $savedPreference }
    if ($code -ne 0) { throw "$Label failed (exit $code). See the message above; setup will not bypass this failure." }
}

function Invoke-WorkspaceStep([string]$Name, [string]$Label, [string[]]$Arguments) {
    $script:stage = $Name
    Invoke-SetupPython $Label (@($script:setupLauncher) + $Arguments)
    $script:steps.Add([PSCustomObject]@{ step = $Name; result = 'PASS' })
}

function Save-SetupSettings([string]$Root, [string]$SettingsPath) {
    $script:stage = 'configure-settings'
    $settings = [ordered]@{ workspace_name = $WorkspaceName; simulation_reviewers = $null }
    if ($SimulationReviewers) { $settings.simulation_reviewers = @($SimulationReviewers) }
    $settings | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SettingsPath -Encoding UTF8
    $code = 'import sys; from pathlib import Path; r=Path(sys.argv[1]); sys.path.insert(0,str(r/''kit/src'')); from migrate_kit.storage import read,write; a=read(Path(sys.argv[2])); w=read(r/''workspace.json''); w.update({''workspace_name'':a[''workspace_name'']} if a.get(''workspace_name'') else {}); write(r/''workspace.json'',w); p=r/''shared/approvers.json''; old=read(p); incoming=a.get(''simulation_reviewers''); old.update({''simulation_reviewers'':list(dict.fromkeys(old.get(''simulation_reviewers'',[])+incoming))} if incoming is not None else {}); write(p,old); print(''Confirmed workspace settings saved; existing reviewer names and unrelated settings preserved.'')'
    Invoke-SetupPython 'Apply confirmed workspace name and simulation reviewers' @('-c', $code, $Root, $SettingsPath)
    $script:steps.Add([PSCustomObject]@{ step = 'configure-settings'; result = 'PASS' })
}

function Initialize-SetupGit([string]$Root) {
    $script:stage = 'initialize-git'
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $existingRoot = @(& $script:setupGit -C $Root rev-parse --show-toplevel 2>$null)
        $existingCode = $LASTEXITCODE
        if ($existingCode -eq 0) {
            Write-SetupMessage "Existing Git repository preserved: $($existingRoot -join '')"
            $script:steps.Add([PSCustomObject]@{ step = 'initialize-git'; result = 'PRESERVED' })
            return
        }
        if (Test-Path -LiteralPath (Join-Path $Root '.git')) { throw 'Existing Git metadata could not be read; refusing to reinitialize it.' }
        & $script:setupGit -C $Root init -b main 2>&1 | ForEach-Object { Write-SetupMessage ([string]$_) }
        $code = $LASTEXITCODE
        if ($code -ne 0) { throw "git init failed (exit $code)" }
        Write-SetupMessage 'Local Git repository initialized on main. No commit, remote or push was performed.'
        $script:steps.Add([PSCustomObject]@{ step = 'initialize-git'; result = 'PASS' })
    }
    finally { $ErrorActionPreference = $savedPreference }
}

function Invoke-SetupDbOptional([string]$Name, [string]$Label, [string[]]$Arguments) {
    # Optional Oracle steps run attached to the console so a hidden password prompt works.
    # A failure is recorded as WARN; the offline workspace itself is already complete.
    $script:stage = $Name
    Write-SetupMessage "`n$Label"
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $script:setupPython -B -X utf8 $script:setupLauncher @Arguments
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $savedPreference }
    if ($code -eq 0) {
        Write-SetupMessage "${Name}: PASS"
        $script:steps.Add([PSCustomObject]@{ step = $Name; result = 'PASS' })
    }
    else {
        $message = "$Name ไม่สำเร็จ (exit $code) — workspace พร้อมใช้แบบออฟไลน์ แก้แล้วรัน: python tools/workspace.py $($Arguments[0]) ..."
        Write-SetupMessage "WARN: $message"
        $script:dbWarnings.Add($message)
        $script:steps.Add([PSCustomObject]@{ step = $Name; result = 'WARN' })
    }
}

try {
    [Console]::OutputEncoding = $utf8
    if ([Console]::IsInputRedirected) { [Console]::InputEncoding = $utf8 }
    $OutputEncoding = $utf8
    if (-not $NonInteractive -and -not $WhatIfPreference) { Invoke-SetupWizard }
    if (-not $WorkspaceDir) { $WorkspaceDir = $sourceRoot }
    $layout = Get-SetupLayout $WorkspaceDir
    $workspaceRoot = $layout.Root
    $launcher = $layout.Launcher
    $bootstrap = $layout.Bootstrap
    if ($WorkspaceName -and ($WorkspaceName.Trim().Length -lt 1 -or $WorkspaceName.Trim().Length -gt 80 -or $WorkspaceName -match '[\x00-\x1f]')) { throw 'WorkspaceName must contain 1-80 printable characters.' }
    if ($WorkspaceName) { $WorkspaceName = $WorkspaceName.Trim() }
    if ($SimulationReviewers) {
        $SimulationReviewers = @($SimulationReviewers | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Select-Object -Unique)
    }
    foreach ($reviewer in $SimulationReviewers) {
        if ($reviewer -notmatch '^[A-Za-z][A-Za-z0-9_]{0,49}$') { throw "Invalid simulation reviewer name: $reviewer" }
    }
    if ($InitializeGit) {
        $gitCommand = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $gitCommand) { throw 'Git was requested but is not installed or not on PATH.' }
        $script:setupGit = $gitCommand.Source
    }
    if ($TargetSource) {
        $targetInput = [System.IO.Path]::GetFullPath(
            $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($TargetSource))
        foreach ($relative in @('columns/all_tab_columns.csv', 'fixtures/rows.json')) {
            if (-not (Test-Path -LiteralPath (Join-Path $targetInput $relative) -PathType Leaf)) {
                throw "TargetSource is missing: $relative"
            }
        }
    }
    else { $targetInput = $null }

    # Oracle adapter settings (tools/dbcore). Existing policy/connection are kept unless requested.
    $dbBefore = Get-SetupDbState $workspaceRoot
    if ($configureDbPolicy -and -not $DbAccess) { $DbAccess = $dbBefore.Access }
    $effectiveAccess = if ($configureDbPolicy) { $DbAccess } else { $dbBefore.Access }
    $effectiveUsers = if ($DbUsers) { $DbUsers } else { $dbBefore.Users }
    if ($configureDbConnection) {
        if ($effectiveAccess -ne 'ai') { throw 'Oracle connection settings require -DbAccess ai (team policy currently lets only people run SQL).' }
        $DbEnv = $(if ($DbEnv) { $DbEnv } else { $dbBefore.Env }).ToUpperInvariant()
        $DbUserRo = [string]$DbUserRo; $DbUserRw = [string]$DbUserRw
        if ($effectiveUsers -eq 'single' -and -not $DbUserRw) { $DbUserRw = $DbUserRo; $DbUserRo = '' }
        $dbProblems = @(
            (Test-SetupDbValue 'env' $DbEnv), (Test-SetupDbValue 'host' $DbHost), (Test-SetupDbValue 'port' ([string]$DbPort)),
            (Test-SetupDbValue 'service' $DbService),
            (Test-SetupDbValue 'user' $DbUserRo ($effectiveUsers -eq 'split')), (Test-SetupDbValue 'user' $DbUserRw ($effectiveUsers -eq 'single'))
        ) | Where-Object { $_ }
        if ($dbProblems) { throw "Invalid Oracle connection setting: $($dbProblems -join '; ')" }
    }
    elseif ($DbEnv -or $DbService -or $DbUserRo -or $DbUserRw -or $dbPortBound) {
        throw 'Oracle connection parameters need -DbHost (and -DbService / user) to be saved.'
    }
    if ($TestDbConnection -and $effectiveAccess -ne 'ai') { throw '-TestDbConnection requires -DbAccess ai (or an existing ai policy).' }
    $dbRequested = $configureDbPolicy -or $configureDbConnection -or $InstallOracleDriver -or $TestDbConnection

    Write-Host 'Migration Team 2 - Workspace setup (SIMULATION ONLY)' -ForegroundColor Cyan
    Write-Host "Source:      $sourceRoot"
    Write-Host "Workspace:   $workspaceRoot"
    Write-Host "Provision:   $bootstrap"
    Write-Host "Mode:        $(if ($NonInteractive) { 'NonInteractive' } elseif ($WhatIfPreference) { 'WhatIf (no prompts)' } else { 'Interactive wizard confirmed' })"
    if (-not $PSCmdlet.ShouldProcess($workspaceRoot, 'Prepare workspace: init, local skill, kit, target, integrity check, report')) {
        Write-Host 'Plan only. No workspace files, jobs or reports were changed.'
        exit 0
    }

    $bundleRoot = if ($bootstrap) { $sourceRoot } else { $workspaceRoot }
    foreach ($relative in @('tools/workspace.py', 'kit/src/migrate_kit/cli.py',
                            'kit/src/migrate_kit/workspace.py', 'kit/pyproject.toml',
                            'samples/target/columns/all_tab_columns.csv', 'samples/target/fixtures/rows.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $bundleRoot $relative) -PathType Leaf)) {
            throw "Source bundle is incomplete: $relative"
        }
    }
    if ($dbRequested) {
        foreach ($relative in @('tools/dbcore/dbx.py', 'tools/dbcore/cli.py')) {
            if (-not (Test-Path -LiteralPath (Join-Path $bundleRoot $relative) -PathType Leaf)) {
                throw "This workspace has no Oracle adapter ($relative). Copy tools/dbcore and tools/workspace.py from the source bundle, then rerun setup."
            }
        }
    }
    foreach ($relative in @('tools/install_workspace_skill.py', '.agents/skills/blendata-odi-team/SKILL.md')) {
        if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot $relative) -PathType Leaf)) {
            throw "Workspace skill source is incomplete: $relative"
        }
    }
    $python = Find-SetupPython $PythonExecutable
    $script:setupPython = $python.Executable
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    [Console]::OutputEncoding = $utf8
    $OutputEncoding = $utf8

    if ($bootstrap) {
        $stage = 'bootstrap'
        New-Item -ItemType Directory -Path $workspaceRoot -Force | Out-Null
        # Explicit scaffold allowlist: jobs, cache, registry, team settings and .git are never copied.
        $scaffold = @('tools', 'kit/src', 'kit/ai', 'kit/knowledge', 'kit/templates', 'kit/delivery', 'kit/releases',
                      'kit/pyproject.toml', 'kit/CHANGELOG.md', 'samples', 'shared/policies',
                      'shared/knowledge', 'tests', 'docs', '.github', 'README.md', '.gitignore',
                      '.gitattributes', 'setup_workspace.ps1')
        foreach ($relative in $scaffold) {
            $from = Join-Path $sourceRoot $relative
            if (-not (Test-Path -LiteralPath $from)) { continue }
            $to = Join-Path $workspaceRoot $relative
            if (Test-Path -LiteralPath $from -PathType Container) {
                New-Item -ItemType Directory -Path $to -Force | Out-Null
                foreach ($file in Get-ChildItem -LiteralPath $from -File -Recurse -Force) {
                    if ($file.FullName -match '[\\/](__pycache__|\.git)[\\/]' -or $file.Extension -eq '.pyc') { continue }
                    $suffix = $file.FullName.Substring($from.Length).TrimStart([char[]]'\/')
                    $destination = Join-Path $to $suffix
                    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
                    Copy-Item -LiteralPath $file.FullName -Destination $destination
                }
            }
            else {
                New-Item -ItemType Directory -Path (Split-Path -Parent $to) -Force | Out-Null
                Copy-Item -LiteralPath $from -Destination $to
            }
        }
        $steps.Add([PSCustomObject]@{ step = 'bootstrap'; result = 'PASS' })
    }

    $logDir = Join-Path $workspaceRoot '.cache/setup'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $logPath = Join-Path $logDir (('setup-{0}-{1}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'), $PID))
    $resultPath = Join-Path $logDir 'last-result.json'
    Set-Content -LiteralPath $logPath -Value 'Workspace setup log - simulation only' -Encoding UTF8
    if ($wizardAnswers) {
        $wizardAnswers | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $logDir 'confirmed-answers.json') -Encoding UTF8
    }
    $script:setupLauncher = $launcher
    Push-Location -LiteralPath $workspaceRoot
    $pushed = $true
    Write-SetupMessage "Python: $($python.Version) ($($python.Executable))"

    Invoke-WorkspaceStep 'init' '[1/5] Initialize workspace defaults' @('init')
    $stage = 'install-skill'
    Invoke-SetupPython 'Install/verify workspace skill and AGENTS.md' @(
        (Join-Path $sourceRoot 'tools/install_workspace_skill.py'), '--source', $sourceRoot, '--workspace', $workspaceRoot)
    $steps.Add([PSCustomObject]@{ step = 'install-skill'; result = 'PASS' })
    if ($configureSettings) { Save-SetupSettings $workspaceRoot (Join-Path $logDir 'confirmed-settings.json') }
    if ($configureDbPolicy) {
        $policyArgs = @('db-policy', '--access', $DbAccess)
        if ($DbSelectMode) { $policyArgs += @('--select-mode', $DbSelectMode) }
        if ($DbUsers) { $policyArgs += @('--users', $DbUsers) }
        Invoke-WorkspaceStep 'db-policy' 'Save Oracle access policy (shared/team.json → db)' $policyArgs
    }
    if ($configureDbConnection) {
        $connectArgs = @('db-connect', '--non-interactive', '--default', '--env', $DbEnv, '--host', $DbHost,
                         '--port', [string]$DbPort, '--service', $DbService)
        if ($DbUserRo) { $connectArgs += @('--user-ro', $DbUserRo) }
        if ($DbUserRw) { $connectArgs += @('--user-rw', $DbUserRw) }
        Invoke-WorkspaceStep 'db-connect' 'Save Oracle connection for this machine (shared/db.local.json, no password)' $connectArgs
    }
    Invoke-WorkspaceStep 'freeze-kit' '[2/5] Verify or create the immutable kit release' @('freeze-kit')

    $currentTarget = Join-Path $workspaceRoot 'shared/target/current.json'
    if ($targetInput) {
        Invoke-WorkspaceStep 'snapshot' '[3/5] Select the explicitly requested synthetic target' @('snapshot', '--source', $targetInput)
    }
    elseif (Test-Path -LiteralPath $currentTarget -PathType Leaf) {
        $stage = 'verify-target'
        $probe = 'import sys; from pathlib import Path; root=Path(sys.argv[1]); sys.path.insert(0,str(root/''kit/src'')); from migrate_kit.storage import read; from migrate_kit.workspace import verify_snapshot; sid=read(root/''shared/target/current.json'')[''snapshot'']; verify_snapshot(root,sid); print(''Preserved verified target: ''+sid)'
        Invoke-SetupPython '[3/5] Verify and preserve the existing target snapshot' @('-c', $probe, $workspaceRoot)
        $steps.Add([PSCustomObject]@{ step = 'verify-target'; result = 'PASS' })
    }
    else {
        Invoke-WorkspaceStep 'snapshot' '[3/5] Create the default synthetic target snapshot' @('snapshot')
    }

    Invoke-WorkspaceStep 'check' '[4/5] Check workspace and existing job integrity' @('check')
    Invoke-WorkspaceStep 'report' '[5/5] Generate status and dashboard' @('report')
    if ($InitializeGit) { Initialize-SetupGit $workspaceRoot }
    if ($InstallOracleDriver) {
        Invoke-SetupDbOptional 'db-driver' 'Check / install python-oracledb (thin mode, no Oracle Client)' @('db-driver', '--install')
    }
    elseif ($TestDbConnection) {
        Invoke-SetupDbOptional 'db-driver' 'Check python-oracledb (not installing: -InstallOracleDriver not given)' @('db-driver')
    }
    if ($TestDbConnection) {
        $who = if ($env:USERNAME) { $env:USERNAME } elseif ($env:USER) { $env:USER } else { 'setup user' }
        $approval = "setup_workspace.ps1 $(if ($NonInteractive) { '-TestDbConnection' } else { 'wizard 8.1' }) ($who $(Get-Date -Format 'yyyy-MM-dd'))"
        if ($script:steps | Where-Object { $_.step -eq 'db-driver' -and $_.result -ne 'PASS' }) {
            $script:dbWarnings.Add('db-test ข้าม — ยังไม่มี python-oracledb')
            $script:steps.Add([PSCustomObject]@{ step = 'db-test'; result = 'SKIPPED' })
        }
        else {
            Invoke-SetupDbOptional 'db-test' 'Test Oracle connection (SELECT USER, SYSDATE FROM dual · read-only)' @('db-test', '--approved', $approval)
        }
    }
    $dbAfter = Get-SetupDbState $workspaceRoot
    $stage = 'complete'
    [PSCustomObject]@{
        success = $true; mode = 'simulation'; stage = $stage; workspace = $workspaceRoot
        python = $python.Executable; python_version = $python.Version
        at = [DateTimeOffset]::Now.ToString('o'); steps = @($steps.ToArray()); log = $logPath
        interactive = (-not $NonInteractive -and -not $WhatIfPreference)
        skill = '.agents/skills/blendata-odi-team/SKILL.md'
        db = [ordered]@{ access = $dbAfter.Access; select_mode = $dbAfter.SelectMode; users = $dbAfter.Users
                         default_env = $dbAfter.Env; connection_configured = ($null -ne $dbAfter.Connection)
                         warnings = @($script:dbWarnings.ToArray()) }
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resultPath -Encoding UTF8

    Write-SetupMessage "`nSETUP COMPLETE - workspace simulation checks passed$(if ($script:dbWarnings.Count) { ' (with Oracle warnings)' })."
    Write-SetupMessage "Dashboard: $(Join-Path $workspaceRoot 'STATUS.html')"
    Write-SetupMessage "Log:       $logPath"
    Write-SetupMessage "Result:    $resultPath"
    Write-SetupMessage "Skill:     $(Join-Path $workspaceRoot '.agents/skills/blendata-odi-team/SKILL.md')"
    Write-SetupMessage "Oracle:    $(if ($dbAfter.Access -eq 'ai') { "ระบบรันได้หลังคนอนุญาต · SELECT=$($dbAfter.SelectMode) · users=$($dbAfter.Users) · ฐาน $($dbAfter.Env) $(if ($dbAfter.Connection) { 'ตั้งค่าแล้ว' } else { 'ยังไม่ตั้งค่า (db-connect)' })" } else { 'คนรัน SQL เอง (ระบบไม่ต่อฐาน)' })"
    foreach ($warning in $script:dbWarnings) { Write-SetupMessage "WARN:      $warning" }
    if ($dbAfter.Access -eq 'ai') {
        Write-SetupMessage 'Oracle:    รหัสผ่านไม่ถูกเก็บ — ตั้ง ORA_RO_PASSWORD / ORA_RW_PASSWORD ด้วย setx หรือพิมพ์ตอนรัน · ดู python tools/workspace.py db-status'
    }
    Write-SetupMessage 'No jobs were created or approved. simulate stays offline; G4-G7 remain NOT_EXECUTED.'
    Write-SetupMessage "`nNext: Set-Location '$($workspaceRoot.Replace("'", "''"))'"
    Write-SetupMessage 'python tools/workspace.py new-job --project TRAINING --job customer_trial --issue 201 --workflow samples/workflows/customer_daily.json --owner DEV_A'
    Write-SetupMessage 'Use a different issue/job name if these are already reserved.'
    exit 0
}
catch [System.OperationCanceledException] {
    Write-Host "`nSETUP CANCELLED: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host 'No workspace files were created or changed.'
    exit 2
}
catch {
    $message = $_.Exception.Message
    Write-Host "`nSETUP FAILED [$stage]: $message" -ForegroundColor Red
    if ($logPath) { Add-Content -LiteralPath $logPath -Value "SETUP FAILED [$stage]: $message" -Encoding UTF8 }
    if ($resultPath) {
        [PSCustomObject]@{
            success = $false; mode = 'simulation'; stage = $stage; error = $message
            workspace = $workspaceRoot; at = [DateTimeOffset]::Now.ToString('o')
            steps = @($steps.ToArray()); log = $logPath
        } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resultPath -Encoding UTF8
    }
    exit 1
}
finally {
    if ($pushed) { Pop-Location }
    [Environment]::SetEnvironmentVariable('PYTHONUTF8', $oldUtf8, 'Process')
    [Environment]::SetEnvironmentVariable('PYTHONIOENCODING', $oldIoEncoding, 'Process')
    [Console]::OutputEncoding = $oldConsoleEncoding
    [Console]::InputEncoding = $oldInputEncoding
}
