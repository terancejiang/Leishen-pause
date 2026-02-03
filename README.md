# 雷神加速器自动暂停（Python版）

本项目用于自动暂停雷神加速器，支持定时运行、Telegram 通知、Telegram 更新 Token、浏览器自动获取 Token 等功能。

**主要功能**
1. 自动暂停加速器（调用官方接口）
2. 定时运行（默认每天 04:00，本地时间）
3. Telegram 通知（成功、已暂停、失败/异常、Token 过期）
4. Telegram 更新 Token（发送 `/token <new_token>`）
5. 浏览器自动获取 Token（`--fetch-token`，需 Playwright）
6. 单实例运行（lock + pid）

**环境要求**
1. Python 3.10+（推荐 3.12）
2. 安装依赖：`pip install -r requirements.txt`

**快速开始**
1. 复制配置模板：`.env.example` → `.env`
2. 填写 `TOKEN`
3. 运行：`python main.py --once`

**配置说明（.env）**
1. `TOKEN`：必填，账号 Token  
2. `RUN_TIME`：每天执行时间（本地时间，`HH:MM`），默认 `04:00`
3. `TIMEOUT_SECONDS`：请求超时秒数
4. `BASE_URL`：API 地址（默认官方）
5. `LOG_DIR` / `LOG_RETENTION_DAYS`：日志目录与保留天数
6. Telegram 相关  
   - `TELEGRAM_ENABLED`：是否启用（true/false）  
   - `TELEGRAM_BOT_TOKEN`：Bot Token  
   - `TELEGRAM_CHAT_ID`：聊天 ID  
   - `TELEGRAM_POLL_TIME`：每天轮询时间（本地时间，`HH:MM`，默认 `00:00`）  
   - `TELEGRAM_POLL_SECONDS`：旧版秒级轮询（如设置会覆盖 `TELEGRAM_POLL_TIME`）  
7. Token 获取  
   - `TOKEN_FETCH_URL`：默认 `https://vip.leigod.com/user.html`  
   - `TOKEN_FETCH_TIMEOUT_SECONDS`：等待超时秒数

**运行方式**
1. 只运行一次：`python main.py --once`
2. 按固定间隔循环：`python main.py --interval-minutes 60`
3. 启动后常驻（按 `RUN_TIME` 定时）：`python main.py`
4. 自动打开浏览器获取 Token：`python main.py --fetch-token`

**Telegram 更新 Token**
1. 开启 `TELEGRAM_ENABLED=true`
2. 配置 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`
3. 发送指令：`/token <new_token>`  
脚本会在每天凌晨获取同时指令中的token，写入 `.env` 并回复更新结果。

**如何获取 Token**
请参考 6yy66yy 的 wiki，步骤详细清晰（直接链接如下）：  
```
https://github.com/6yy66yy/legod-auto-pause/wiki/%E5%A6%82%E4%BD%95%E4%BD%BF%E7%94%A8%E7%BD%91%E9%A1%B5%E7%99%BB%E5%BD%95%E8%8E%B7%E5%8F%96%E8%87%AA%E5%B7%B1%E7%9A%84token
```

**GitHub Actions（更详细步骤）**
1. Fork本repo
2. 进入 GitHub 仓库 → `Settings` → `Secrets and variables` → `Actions`
3. 点击 `New repository secret` 添加以下 Secrets  
   - `TOKEN`（必填）  
   - 可选：`TELEGRAM_ENABLED`、`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`  
   - 可选：`TELEGRAM_POLL_TIME`、`TIMEOUT_SECONDS`、`BASE_URL`
4. 进入 `Actions` 页面，启用 workflows
5. 手动运行测试  
   - Actions → 选择 `Auto Pause Leishen (Python)`  
   - 点击 `Run workflow`
6. 定时运行  
   - 默认 cron 为 `0 0 * * *`（UTC 时间）  
   - 若需修改，请编辑 `.github/workflows/python-auto-pause.yml`

**常见问题**
1. Token 过期：更新 `.env` 中 `TOKEN` 或使用浏览器自动获取
2. Telegram 未生效：确认 `TELEGRAM_ENABLED=true` 且 Bot/ChatId 正确
