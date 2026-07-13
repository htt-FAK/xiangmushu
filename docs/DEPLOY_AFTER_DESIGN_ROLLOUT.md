# 部署 + 部署后验证：分步执行清单

> ⚠️ **重要架构提示**：本项目服务器运行在**宝塔面板 (BT Panel)** 之上。
> nginx 实际服务的静态文件根目录是 **`/www/wwwroot/xiangmushu/`**，
> **不是** git 仓库中的 `frontend/dist/`。
> 
> 因此 `git pull && npm run build` **不足以**让新 build 生效；
> 必须把 dist/* 复制到 `/www/wwwroot/xiangmushu/`。

---

## 阶段 A：服务器拉取 + 重建 + 复制到 nginx 根

### 选项 A1：一行脚本（推荐）

```bash
cd /root/h/xiangmushu && bash scripts/deploy.sh
```

脚本会自动执行 git pull → npm run build → 替换 /www/wwwroot/xiangmushu/ 内容 → 验证 hash 一致。

### 选项 A2：手动分步

```bash
# ① 拉新代码
cd /root/h/xiangmushu
git pull origin master
git log --oneline -3
# 期望最后一行：c331a8c docs(DESIGN.md): update Appendix A status (18/19 fixed)

# ② 重建前端
cd frontend
npm run build
ls dist/assets/index-*.js
# 期望 hash 包含 EkQ7gk5U（不是旧的 CWR_6Ju2）

# ③ 复制到 nginx 实际服务的目录（关键！）
[ -d /www/wwwroot/xiangmushu ] || sudo mkdir -p /www/wwwroot/xiangmushu
sudo rsync -a --delete frontend/dist/ /www/wwwroot/xiangmushu/

# ④ 验证复制成功
grep "<title>" /www/wwwroot/xiangmushu/index.html
# 期望：<title>项目书工作台</title>
ls /www/wwwroot/xiangmushu/assets/index-*.js
# 期望：包含 EkQ7gk5U
```

### ⑤ 确保 nginx 在跑

```bash
# 宝塔的 nginx 启动方式
/www/server/nginx/sbin/nginx -t     # 测试配置
ss -tlnp | grep ':80'               # 看 80 端口有没有在监听

# 如果 80 端口空闲，手动启动
sudo /www/server/nginx/sbin/nginx

# 如果已经在跑但响应旧内容，reload
sudo /www/server/nginx/sbin/nginx -s reload
```

⚠️ 仅前端改动。后端 **通常无需** `systemctl restart xiangmushu`。

---

## 阶段 B：部署后验证

在**本地**（Windows）开 PowerShell：

```powershell
cd D:\Users\taotao.huang\Desktop\test1\xiangmushu
npx playwright install chromium   # 仅首次
node scripts\verify-after-deploy.cjs
```

脚本会连接 `http://118.126.102.143`，执行 7 大类检查：

| 编号 | 检查项 | 预期 |
|------|--------|------|
| [1] | Build hash | ≠ 旧 hash（CWR_6Ju2 / DgpNz0RN / DKYs-LEY 等） |
| [2] | Document title | `项目书工作台`（非旧 `项目书智能生成舱`） |
| [3] | 命名迁移 | 不再有 `生成舱`，可见 `生成工作台` |
| [4] | 红色违规清零 | 无 `backdrop-blur-2xl` / `rounded-lg` / `bg-night-950/*` / `bg-white/[0.035]` |
| [5] | 无障碍 | skip-link + ≥100 aria-hidden + ≥3 tabular-nums + ≥2 focus-visible rule |
| [6] | i18n 切换 | 英文环境下 `<html lang>` 应变 `en-US`（需登录，脚本会跳过并提示手动检查） |
| [7] | 页面可达 | `/` `/auth` `/auth/login` 返回 < 400 |

---

## 阶段 C：失败时的快速回滚（如出现严重问题）

```bash
cd /root/h/xiangmushu
git reset --hard e05e98a                    # 回到黄色优先级完成后
cd frontend && npm run build
sudo rsync -a --delete dist/ /www/wwwroot/xiangmushu/
```

---

## 常见问题

### Q1：为什么我 `npm run build` 成功了但浏览器还是旧页面？

检查：
```bash
# 看 nginx 实际服务的目录
grep "index-" /www/wwwroot/xiangmushu/index.html
```
如果还是旧的 hash，说明复制步骤没做/没权限/路径写错。

### Q2：nginx 重启了但还是旧内容？

```bash
# 宝塔 nginx 可能有 proxy_cache 或 sendfile 缓存配置
grep -E "(proxy_cache|sendfile|expires)" /www/server/nginx/conf/nginx.conf
# 如果看到缓存配置，需要改配置或加 ?v=hash 强制刷新
```

### Q3：`rsync: command not found`

```bash
# 用 cp 代替（先清空再复制）
sudo rm -rf /www/wwwroot/xiangmushu/*
sudo cp -r frontend/dist/* /www/wwwroot/xiangmushu/
```

---

## 验收清单

验证脚本输出形如：

```
[1] Build fingerprint
  ✓  build hash is new (EkQ7gk5U)
[2] Document title & meta
  ✓  title renamed (项目书工作台)
  ✓  <html lang> (zh) (zh-CN)
...
════════════════════════════════════════
  TOTAL  14 passed / 0 failed
════════════════════════════════════════

✔  All design-system checks passed on production.
```

→ 看到 "0 failed" 即表示本次会话 22 项设计违规的修复已全部生效到生产。
