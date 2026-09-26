"""海拔带筛选与按园汇总的唯一统计来源。

首页三张对照卡、茶园列表的海拔带筛选、槽列表按茶园过滤，
全部经由本模块取数：禁止首页一套 SQL、列表另一套。

口径（精确匹配）：
- 海拔带用 ``Garden.altitudeBand`` 整串等值匹配，不做模糊/区间包含。
- 选定带后，槽与批次只统计「该带茶园」名下：先取该带全部茶园，
  再用外键 ``garden__in`` 聚合，因此某园零槽或零批次不会漏园、
  也不会把别带茶园的槽/批次算进来。
"""

from django.db.models import Count

from .models import Garden, Trough, WitherBatch

ALL_BANDS = ""  # “全部海拔带”下拉哨兵值


def altitude_band_choices():
    """返回去重后的海拔带选项（精确串），含“全部”哨兵。"""
    values = (
        Garden.objects.exclude(altitudeBand="")
        .values_list("altitudeBand", flat=True)
        .distinct()
        .order_by("altitudeBand")
    )
    return [(ALL_BANDS, "全部海拔带")] + [(v, v) for v in values]


def is_specific_band(band):
    """是否选定了某个具体海拔带（而非“全部”）。"""
    return bool(band) and band != ALL_BANDS


def gardens_in_band(band):
    """精确匹配某海拔带的茶园 queryset；“全部”时返回全部茶园。"""
    qs = Garden.objects.all()
    if is_specific_band(band):
        qs = qs.filter(altitudeBand=band)
    return qs


def troughs_for_gardens(gardens):
    """给定茶园集合（queryset 或可迭代），返回其名下全部槽位。

    首页带内槽总数与槽列表按园过滤共用此函数，保证同源。
    """
    if hasattr(gardens, "values_list"):
        garden_ids = list(gardens.values_list("pk", flat=True))
    else:
        garden_ids = [g.pk for g in gardens]
    return Trough.objects.select_related("garden").filter(garden_id__in=garden_ids)


def batches_for_gardens(gardens):
    """给定茶园集合，返回其名下全部槽位的全部批次。"""
    if hasattr(gardens, "values_list"):
        garden_ids = list(gardens.values_list("pk", flat=True))
    else:
        garden_ids = [g.pk for g in gardens]
    return WitherBatch.objects.select_related("trough", "trough__garden").filter(
        trough__garden_id__in=garden_ids
    )


def per_garden_trough_rows(gardens):
    """按园汇总槽：每个有槽的园一行（园名, 槽数）。

    行数即“按园汇总后的槽行数”，须与首页槽总数同源
    （都来自 :func:`troughs_for_gardens` 的同一过滤口径）。
    """
    rows = (
        troughs_for_gardens(gardens)
        .values("garden_id", "garden__name")
        .annotate(num=Count("id"))
        .order_by("garden__name")
    )
    return [(row["garden__name"], row["num"]) for row in rows]


def per_garden_batch_rows(gardens):
    """按园汇总批次：每个有批次的园一行（园名, 批次数）。"""
    rows = (
        batches_for_gardens(gardens)
        .values("trough__garden_id", "trough__garden__name")
        .annotate(num=Count("id"))
        .order_by("trough__garden__name")
    )
    return [(row["trough__garden__name"], row["num"]) for row in rows]


def band_summary(band):
    """选定海拔带（或“全部”）下的三张对照卡数据。

    返回 dict：garden_count / trough_count / batch_count，
    以及按园汇总行，供首页整页与 HTMX 局部刷新共用同一上下文。
    无匹配带时三个计数均为 0、列表为空，不报错。
    """
    gardens = gardens_in_band(band)
    trough_rows = per_garden_trough_rows(gardens)
    batch_rows = per_garden_batch_rows(gardens)
    # 强制求值，使后续 list(gardens) 与计数共享同一次取数结果。
    garden_list = list(gardens)
    return {
        "selected_band": band if is_specific_band(band) else ALL_BANDS,
        "band_choices": altitude_band_choices(),
        "band_gardens": garden_list,
        "garden_count": len(garden_list),
        "trough_count": sum(n for _, n in trough_rows),
        "batch_count": sum(n for _, n in batch_rows),
        "trough_rows": trough_rows,
        "batch_rows": batch_rows,
    }
