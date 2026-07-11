---
name: sso-auth-best-practices
description: SSO 认证服务开发与部署。使用此技能处理基于 JWT 的单点登录系统、用户认证、令牌管理、RSA 加密传输、Redis 存储、Docker 部署等 SSO 相关任务。当用户需要开发完整的 SSO 认证服务、实现 JWT 令牌系统、配置 Docker 部署、解决 SSO 开发中的架构和实现问题，或涉及用户认证、令牌刷新、密钥管理等核心功能时，务必使用此技能。
---

# SSO 认证服务技能

此技能提供完整的 SSO 认证服务解决方案，包括架构设计、开发实现、部署配置和常见问题解决。

## 核心功能

- **认证服务开发**：基于 Gin + JWT 的 SSO 认证服务
- **安全设计**：RSA 加密传输、bcrypt 密码存储、JWT 令牌管理
- **用户管理**：用户注册、登录、禁言、封禁、踢下线
- **令牌管理**：access token、refresh token、令牌刷新、退出登录
- **部署支持**：Docker 部署、多环境配置、密钥管理
- **问题解决**：常见 SSO 开发踩坑和解决方案

## 使用场景

当用户需要：
- 开发或配置 SSO 认证服务
- 处理 JWT 令牌生成和验证
- 实现 RSA 加密的密码传输
- 使用 Redis 存储 SSO 数据
- Docker 部署认证服务
- 解决 SSO 开发中的常见问题

## 快速开始

### 1. 项目初始化
```bash
# Go 项目初始化
go mod init sso
go get github.com/gin-gonic/gin
go get github.com/redis/go-redis/v9
go get github.com/golang-jwt/jwt/v5
```

### 2. 核心配置
```bash
# 生成 RSA 密钥对
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

### 3. 启动服务
```bash
# Docker 启动
docker compose up -d sso
```

## API 端点

### 公开端点
- `POST /api/auth/login` - 登录（RSA加密密码）
- `POST /api/auth/register` - 注册
- `GET /api/auth/public-key` - 获取公钥

### 认证端点
- `POST /api/auth/refresh` - 刷新令牌
- `POST /api/auth/logout` - 退出登录
- `GET /api/auth/validate` - 验证令牌

### 管理端点
- `GET /api/admin/users` - 用户列表
- `POST /api/admin/kick` - 踢下线
- `POST /api/admin/blacklist` - 拉黑用户
- `POST /api/admin/mute` - 设置禁言

## 常见问题解决方案

### 1. Hydration 不匹配 (React #418)
服务端和客户端日期格式不一致导致 hydration 失败：
```tsx
function formatDate(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}
```

### 2. CSS 样式丢失
确保 `App.tsx` 包含 CSS 导入：
```tsx
import './index.css'
```

### 3. 销毁按钮文字不可见
修复 CSS 变量颜色：
```css
--destructive-foreground: oklch(0.985 0 0); /* 白色 */
```

### 4. Redis 错误处理
使用 go-redis 的原生错误：
```go
if err == redis.Nil {  // 正确的错误检查
```

## 部署配置

### 本地开发
```bash
docker compose up -d
```

### 生产部署
```bash
docker compose -f SSO/docker-compose.yml up -d
```

## 状态模型

- 正常：可登录、可发帖
- 禁言：可登录、不可发帖  
- 封禁：不可登录（黑名单）

---

此技能专注于 SSO 认证服务的完整解决方案，提供从开发到部署的全流程支持。