param([string]$ConnectionConfig,[switch]$Refresh,[string]$Python='python')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONIOENCODING='utf-8'
$env:LABEL_OUTPUT_DIR=Join-Path $PSScriptRoot '../outputs'
if($ConnectionConfig){
    $stored=Import-Clixml -LiteralPath $ConnectionConfig
    if($stored.Python){$Python=$stored.Python}
    $env:JQ_DEPENDENCIES=$stored.Dependencies
}
if($Refresh -or !(Test-Path -LiteralPath 'raw/manifest.json')){
    if(!$ConnectionConfig){throw '首次采集或刷新需要指定本机DPAPI连接配置 -ConnectionConfig；凭据不会写入输出'}
    $cfg=@{host=$stored.Host;port=3306;user=$stored.User;database='spider';password=([PSCredential]::new($stored.User,$stored.Password)).GetNetworkCredential().Password}
    try{$cfg | ConvertTo-Json -Compress | & $Python extract.py;if($LASTEXITCODE -ne 0){throw '采集失败，停止汇总'}}finally{$cfg=$null}
}else{Write-Output '复用本地已成功快照，不代表源库已刷新。'}
& $Python test_rules.py
if($LASTEXITCODE -ne 0){throw '规则测试失败'}
& $Python analyze.py
if($LASTEXITCODE -ne 0){throw '汇总校验失败'}
Write-Output '候选数据已生成，未推送或发布。'
