param([string]$ProjectRoot = (Join-Path $PSScriptRoot '..'))
$ErrorActionPreference = 'Stop'
$projectPath = [IO.Path]::GetFullPath($ProjectRoot)
$cardsPath = Join-Path $projectPath 'releases\v1.1\cards.json'
$outputPath = Join-Path $projectPath 'Data\Presentation\Cards'
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
$cards = (Get-Content -Raw -LiteralPath $cardsPath | ConvertFrom-Json).cards
$prices = @{ common = 1; rare = 2; epic = 3; legendary = 4; specialization = 0 }
$profileIndex = [ordered]@{}
foreach ($entry in ($cards.PSObject.Properties | Sort-Object Name)) {
    $card = $entry.Value
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $hash = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($card.name))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    $id = 'card-' + $hash.Substring(0, 16)
    $filePath = Join-Path $outputPath ($id + '.json')
    $art = [ordered]@{ IllustrationTexture = ''; FrameTexture = ''; ElementIconTexture = ''; EffectScene = ''; Sound = '' }
    if (Test-Path -LiteralPath $filePath) {
        $previous = Get-Content -Raw -LiteralPath $filePath | ConvertFrom-Json
        if ($previous.Art) { $art = $previous.Art }
    }
    $notes = @()
    $displayRules = $card.text
    if ($card.name -eq '大地之握') {
        $notes += '转伤范围：上一发主弹发射后至本发主弹发射前的实际叠盾衰减；包含本行动值发射前的土附魔叠盾。按300%计入本发，发射后清零，不累计整场。'
    }
    if ($card.name -in @('焰心屏障', '临时壁垒', '岩潮壁垒')) {
        $displayRules = switch ($card.name) {
            '焰心屏障' { '下一发主弹造成伤害前，获得本次有效攻击力50%的临时护盾。剩余临时护盾在获得后的下一个抽牌阶段前消失。' }
            '临时壁垒' { '获得150临时护盾，本次不触发旧盾衰减。剩余临时护盾在获得后的下一个抽牌阶段前消失。' }
            '岩潮壁垒' { '获得220临时护盾，本次不触发旧盾衰减。剩余临时护盾在获得后的下一个抽牌阶段前消失。' }
        }
    }
    $profile = [ordered]@{
        SchemaVersion = 1; CardId = $card.name; ProfileId = $id; Name = $card.name
        Element = $card.element; Rarity = $card.rarity; CombatCost = $card.cost
        BaseStudyCost = $prices[$card.rarity]; Attack = $card.attack; Defense = $card.defense
        FirstEnchantmentLayers = $card.layers; RulesText = $card.text; DisplayRulesText = $displayRules; RuleNotes = @($notes); Art = $art
    }
    $profile | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $filePath -Encoding UTF8
    $profileIndex[$card.name] = [ordered]@{ ProfileId = $id; Path = "res://Data/Presentation/Cards/$id.json" }
}
$profileIndex | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $projectPath 'Data\Presentation\card-profiles-index.json') -Encoding UTF8
Write-Output "Generated $($cards.PSObject.Properties.Count | Measure-Object -Sum | Select-Object -ExpandProperty Sum) card profiles in $outputPath"

