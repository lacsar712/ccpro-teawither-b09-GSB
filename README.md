# TeaWither-01 · 茶萎凋台账

Django 5 + PostgreSQL 服务端渲染应用：Templates + HTMX + 自定义 CSS，无 Vue/React SPA。

## 技术栈

- Django 5、PostgreSQL
- Session 登录
- HTMX（CDN）局部刷新列表
- Docker Compose：`web` + `db`

## 端口与数据库

| 服务 | 端口 |
|------|------|
| Web  | **4100** |
| Postgres | **5440**（容器内 5432） |

数据库账号：`teawither` / `teawither` / 库名 `teawither`

## 快速启动

```bash
cd TeaWither/TeaWither-01
docker compose up --build -d
```

浏览器打开：http://localhost:4100

演示账号：

- `admin` / `123456`（超级用户）
- `witherer` / `123456`（普通用户）

容器启动时会自动：`migrate` → `seed_data` → `collectstatic` → `gunicorn`

## 本地开发（可选）

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 确保本机 Postgres 监听 5440，或先 docker compose up -d db
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5440
python manage.py migrate
python manage.py seed_data
python manage.py runserver 0.0.0.0:4100
```

## 业务模型

1. **Garden（茶园）**：`name`、`altitudeBand`、`notes`
2. **Trough（萎凋槽）**：归属茶园、`troughCode`、`cultivar`、`loadKg`、状态 `loading|withering|ready`；同一茶园内槽位编号唯一
3. **WitherBatch（萎凋批次）**：归属槽位、`startedAt`、`targetMoisture`、`actualMoisture`（可空）、`rollGrade`

**业务规则**：将槽位状态设为 `ready`（可下槽）时，若最新批次的 `actualMoisture` 为空或大于 40，抛出中文 `ValidationError`。

## 海拔带筛选与首页三张对照卡

- **茶园列表**（`/gardens/`）支持按海拔带筛选，筛选为 **精确匹配**（`altitudeBand == band`，不是 `contains`）。例如带值为 `600-800m` 时，传 `band=600-800` 或 `band=m` 均无结果。
- **槽列表**（`/troughs/`）支持按茶园筛选（`?garden=<id>`）。
- **首页**（`/?band=<海拔带>`）选定海拔带后展示三张对照卡：该带茶园数、这些园下槽总数、这些园下批次总数；下方附「按园汇总」表（每园一行：槽数、批次数，末行合计）。

### 三卡复算（核对误差必须为 0）

| 对照卡 | 复算口径 | 必须等于 |
|---|---|---|
| 该带茶园数 | `gardens_in_band(band).count()` | 筛选后茶园列表 **行数** |
| 槽总数 | `troughs_for_gardens(该带茶园).count()` | 按园汇总表 **槽数行合计** |
| 批次总数 | `batches_for_gardens(该带茶园).count()`（沿 `batch→trough→garden` 过滤，非全库） | 按园汇总表 **批次数行合计** |

复算步骤：

1. 首页选定海拔带（或直接访问 `/?band=600-800m`），记下三卡数字与按园汇总表各行数值；
2. 打开 `/gardens/?band=600-800m`，表格行数须等于「该带茶园数」；
3. 把按园汇总表中每个园的槽数、批次数分别相加，须等于槽卡、批次卡（`apps/gardens/stats.py` 的 `band_summary()` 内有断言在运行时强制这三个等式）；
4. 槽侧可逐园在 `/troughs/?garden=<id>` 过滤，各园行数相加须等于首页槽总数——两边调用同一个 `stats.troughs_for_gardens()`，同源统计，不存在首页一套 SQL、列表另一套；
5. 传一个不存在的带（如 `?band=nope`）：三卡均为 0、汇总表与茶园列表为空，页面不报错。

整页访问与 HTMX 局部刷新共用同一模板片段（`templates/home/_band_panel.html`）与同一份 `band_summary` 数据，切换海拔带后两种刷新方式口径一致（无 JS 时表单自动回退为普通 GET 提交）。

## 种子数据

```bash
python manage.py seed_data
```

幂等：已有茶园则只保证账号存在。亦可在环境变量 `TEAWITHER_AUTO_SEED=1` 时于 `post_migrate` 自动播种。

种子覆盖三个海拔带（`800-1000m`、`600-800m`、`400-600m`），**每个带都有园、有槽、有批次**，共 6 个茶园、9 个槽位、9 个批次。

## 目录结构

```
TeaWither-01/
  manage.py
  requirements.txt
  Dockerfile
  entrypoint.sh
  docker-compose.yml
  config/           # 项目配置
  apps/gardens/     # 模型、视图、种子命令
  templates/        # Django 模板
  static/css/       # 自定义样式（茶绿色顶栏）
```
