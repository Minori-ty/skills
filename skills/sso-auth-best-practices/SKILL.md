---
name: sso-auth-best-practices
description: SSO 认证服务开发与部署。使用此技能处理基于 JWT 的单点登录系统、用户认证、令牌管理、RSA 加密传输、Redis 存储、Docker 部署等 SSO 相关任务。当用户需要开发完整的 SSO 认证服务、实现 JWT 令牌系统、配置 Docker 部署、解决 SSO 开发中的架构和实现问题，或涉及用户认证、令牌刷新、密钥管理等核心功能时，务必使用此技能。
---

# SSO 认证服务技能

此技能提供完整的 SSO 认证服务解决方案，包括架构设计、开发实现、部署配置和常见问题解决。

## 核心功能

- **认证服务开发**：基于 Gin + JWT 的 SSO 认证服务
- **安全设计**：RSA 加密传输、bcrypt 密码存储、JWT 令牌管理
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

## 常见问题解决方案

### 1. Hydration 不匹配 (React #418)
服务端和客户端日期格式不一致导致 hydration 失败：
```tsx
function formatDate(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}
```

### 2. Redis 错误处理
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

---

## 踩坑记录

### 1. 登出后仍显示在线

**现象**: 用户点击退出后，Admin 用户列表仍显示"Online"。

**根因**: 登录时往 Redis 集合 `sso:user_tokens:<userId>` 中同时存储了 **access JTI 和 refresh JTI 两个值**，但登出只删除了 access JTI，refresh JTI 残留导致 `IsUserOnline` 判断集合非空。

```go
// ❌ 登录加了 2 个
h.store.AddUserToken(ctx, userID, accessJTI, ...)    // +1
h.store.AddUserToken(ctx, userID, refreshJTI, ...)   // +1

// ❌ 登出只删了 1 个
h.store.RemoveUserToken(ctx, userID, accessJTI)      // -1，集合还有 refresh
// → IsUserOnline 仍返回 true
```

**解决**: 登出时直接清空该用户的所有 token 集合，不逐个删除。

```go
// ✅ 登出: 清除所有 JTI
if claims, ok := c.Get("user_claims"); ok {
    if uc, ok := claims.(*model.UserClaims); ok {
        h.store.RevokeAllUserTokens(c.Request.Context(), uc.UserID)
    }
}
```

底层实现（redis.go）：

```go
func (s *RedisStore) RevokeAllUserTokens(ctx context.Context, userID string) error {
    jtiKey := UserTokensPrefix + userID
    jtis, _ := s.client.SMembers(ctx, jtiKey).Result()
    pipe := s.client.Pipeline()
    for _, jti := range jtis {
        pipe.Set(ctx, TokenBlacklist+":"+jti, "1", 24*time.Hour)
    }
    pipe.Del(ctx, jtiKey)     // 删除整个集合
    _, err := pipe.Exec(ctx)
    return err
}

func (s *RedisStore) IsUserOnline(ctx context.Context, userID string) (bool, error) {
    jtiKey := UserTokensPrefix + userID
    jtis, _ := s.client.SMembers(ctx, jtiKey).Result()
    return len(jtis) > 0, nil  // 集合为空 = 离线
}
```

### 2. Docker 镜像尽量用 `:alpine`，不锁版本号

**原则**: 所有基础镜像统一使用 `:alpine` 标签，不指定具体版本号。

```dockerfile
# ✅ 用 :alpine 自动跟随最新
FROM golang:alpine
FROM node:alpine
```

```yaml
# docker-compose.yml
image: redis:alpine
image: postgres:alpine
image: nginx:alpine
```

**理由**:

| 原因 | 说明 |
|:---|---|
| 安全补丁 | `:alpine` 指向最新的 Alpine 版本，自动包含安全更新 |
| 体积 | Alpine 基础镜像约 5MB，Debian 约 50MB+ |
| 常见服务 | Redis、PostgreSQL、Nginx、Node、Go 都提供 `:alpine` 标签 |

**注意 PostgreSQL 18**: 升级到 `postgres:alpine` 后数据目录结构变了，需设置 `PGDATA` 兼容旧数据：

```yaml
environment:
  PGDATA: /var/lib/postgresql/data   # 保持旧目录格式
```

否则会报 `in 18+, these Docker images are configured to store database data in a format which is compatible with "pg_ctlcluster"`。

---

此技能专注于 SSO 认证服务的完整解决方案，提供从开发到部署的全流程支持。