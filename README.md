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

## 海拔带筛选与首页三张对照

### 精确匹配口径

- 海拔带按 `Garden.altitudeBand` **整串等值匹配**（`altitudeBand = "800-1000m"`），
  不是区间比较、也不是 `contains` 模糊匹配。因此 `800-1000m` 与 `800-1200m`
  互不命中，下拉选项来自现有茶园去重后的海拔带值。
- 选定某带后，槽与批次**只统计该带茶园名下**：先取该带全部茶园，
  再以外键 `garden_id__in` 过滤槽位、`trough__garden_id__in` 过滤批次。
- **唯一统计来源**：`apps/gardens/stats.py`。
  - 首页三张对照卡、茶园列表带筛选 → `gardens_in_band()`
  - 首页“带内槽总数”与槽列表按园过滤 → **同一个** `troughs_for_gardens()`
  - 首页“带内批次总数” → `batches_for_gardens()`

  禁止首页一套 SQL、列表另一套；槽侧按园过滤与首页槽总数必然同源。

### 三张对照卡（首页选定海拔带时）

首页下拉切换海拔带后展示：

1. **该带茶园数** = `gardens_in_band(band)` 行数
2. **这些园下的槽总数** = Σ“按园汇总槽”各行 = `troughs_for_gardens(该带茶园)` 行数
3. **这些园下的批次总数** = Σ“按园汇总批次”各行 = `batches_for_gardens(该带茶园)` 行数

**三卡复算步骤（误差必须为 0）：**

```text
设选定带为 B。
G  = SELECT * FROM gardens_garden WHERE altitudeBand = B          # 精确匹配
卡1 = |G|
T  = SELECT * FROM gardens_trough WHERE garden_id IN (G 的 id)     # troughs_for_gardens
卡2 = |T| = Σ_g |T_g|        （按园汇总槽表各园槽数之和）
W  = SELECT * FROM gardens_witherbatch
     WHERE trough_id IN (SELECT id FROM gardens_trough WHERE garden_id IN G)
卡3 = |W| = Σ_g |W_g|        （按园汇总批次表各园批次数之和）
```

手工核对：

1. 打开「茶园」列表，用同一海拔带精确筛选，列表行数必须 == 卡 1。
2. 首页「按园汇总 · 萎凋槽」各园槽数相加必须 == 卡 2；
   打开「萎凋槽」列表，逐园筛选这些茶园后的行数之和同样 == 卡 2（同源函数）。
3. 首页「按园汇总 · 萎凋批次」各园批次数相加必须 == 卡 3。

三个差值均为 0 才算通过。**无匹配带**（数据库中不存在该带）时三张卡均为 0、
茶园列表为空、按园汇总表为空，页面不报错。整页渲染与 HTMX 局部刷新
（下拉 `change` 触发）渲染的是同一个 `home/_band_panel.html` 片段与同一份
`band_summary()` 上下文，因此切换带后两种口径完全一致。

### 槽列表按茶园筛选

「萎凋槽」页新增「按茶园筛选」下拉（支持整页与 HTMX 局部刷新）。
该过滤走 `stats.troughs_for_gardens()`，与首页槽总数统计函数相同；
选不存在的茶园 id 时回退为空结果，不报错。

## 种子数据

```bash
python manage.py seed_data
```

幂等：已有茶园则只保证账号存在。亦可在环境变量 `TEAWITHER_AUTO_SEED=1` 时于 `post_migrate` 自动播种。

种子含 **3 个海拔带**（`600-800m`、`800-1000m`、`1000-1200m`），每带均有茶园、
槽位与批次；`600-800m` 带另有一个「有槽无批次」的园，便于核对槽总数与批次总数的差异。

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
