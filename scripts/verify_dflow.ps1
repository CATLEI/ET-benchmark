# dflow验证脚本
# 用于验证dflow环境配置是否正确

Write-Host "=== dflow环境验证 ===" -ForegroundColor Cyan

# 1. 验证Kubernetes集群
Write-Host "`n1. 验证Kubernetes集群..." -ForegroundColor Yellow
kubectl version --client
kubectl cluster-info
kubectl get nodes

# 2. 检查Argo Workflows
Write-Host "`n2. 检查Argo Workflows..." -ForegroundColor Yellow
$argoPods = kubectl get pods -n argo 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Argo Workflows命名空间存在" -ForegroundColor Green
    kubectl get pods -n argo
    kubectl get svc -n argo
} else {
    Write-Host "Argo Workflows未安装，需要先安装" -ForegroundColor Red
}

# 3. 检查端口转发
Write-Host "`n3. 检查端口2746是否被占用..." -ForegroundColor Yellow
$portCheck = netstat -ano | findstr ":2746"
if ($portCheck) {
    Write-Host "端口2746已被占用（可能是端口转发正在运行）" -ForegroundColor Green
} else {
    Write-Host "端口2746未被占用，需要启动端口转发" -ForegroundColor Yellow
    Write-Host "  运行: kubectl port-forward svc/argo-server -n argo 2746:2746" -ForegroundColor Cyan
}

# 4. 检查环境变量
Write-Host "`n4. 检查dflow环境变量..." -ForegroundColor Yellow
if ($env:DFLOW_HOST) {
    Write-Host "DFLOW_HOST: $env:DFLOW_HOST" -ForegroundColor Green
} else {
    Write-Host "DFLOW_HOST未设置" -ForegroundColor Yellow
    Write-Host "  设置: `$env:DFLOW_HOST = 'http://localhost:2746'" -ForegroundColor Cyan
}

if ($env:DFLOW_NAMESPACE) {
    Write-Host "DFLOW_NAMESPACE: $env:DFLOW_NAMESPACE" -ForegroundColor Green
} else {
    Write-Host "DFLOW_NAMESPACE未设置" -ForegroundColor Yellow
    Write-Host "  设置: `$env:DFLOW_NAMESPACE = 'argo'" -ForegroundColor Cyan
}

# 5. 测试dflow连接
Write-Host "`n5. 测试dflow Python连接..." -ForegroundColor Yellow
python -c "from dflow import config; config['host']='http://localhost:2746'; config['namespace']='argo'; print('dflow配置成功')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "dflow Python连接测试通过" -ForegroundColor Green
} else {
    Write-Host "dflow Python连接测试失败" -ForegroundColor Red
}

# 6. 检查Docker镜像
Write-Host "`n6. 检查WBP Docker镜像..." -ForegroundColor Yellow
docker images | Select-String "wbp"
if ($LASTEXITCODE -eq 0) {
    Write-Host "WBP镜像存在" -ForegroundColor Green
} else {
    Write-Host "WBP镜像不存在" -ForegroundColor Red
}

Write-Host "`n=== 验证完成 ===" -ForegroundColor Cyan

