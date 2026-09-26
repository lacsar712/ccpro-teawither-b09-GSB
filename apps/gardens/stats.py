"""海拔带 / 茶园维度的同源统计函数。

首页三张对照卡（该带茶园数、该带槽总数、该带批次总数）、茶园列表
筛选后的行数、以及槽列表按茶园过滤，全部走本模块的查询，保证：

* 海拔带是 **精确匹配**（``altitudeBand == band``），不做 contains/icontains；
* 槽数 / 批次按「这些园」聚合，而不是按槽表/批次表全库计数；
* 槽列表按园过滤与首页槽总数是同一个查询集（``troughs_for_gardens``），
  首页一套 SQL、列表另一套的情况不允许出现。
"""

from django.db.models import Count

from .models import Garden, Trough, WitherBatch


def altitude_bands():
    """返回库内现有海拔带（去重、按名排序）。"""
    return list(
        Garden.objects.order_by("altitudeBand")
        .values_list("altitudeBand", flat=True)
        .distinct()
    )


def gardens_in_band(band):
    """精确匹配海拔带的茶园查询集。

    ``band`` 为空/None 时返回全部茶园（即「全部带」口径）。
    """
    qs = Garden.objects.all()
    if band:
        qs = qs.filter(altitudeBand=band)
    return qs


def troughs_for_gardens(gardens):
    """给定茶园查询集，返回这些园下的 **全部** 萎凋槽查询集。

    首页带内槽总数与槽列表按园过滤共用本函数，保证同源。
    必须按子查询过滤到这些园，而非全库 ``Trough.objects.count()``。
    """
    return Trough.objects.filter(garden__in=gardens)


def batches_for_gardens(gardens):
    """给定茶园查询集，返回这些园下的 **全部** 萎凋批次查询集。

    批次挂在槽上（batch -> trough -> garden），必须沿外键链过滤到
    「这些园」，不能直接 ``WitherBatch.objects.count()`` 算全库。
    """
    return WitherBatch.objects.filter(trough__garden__in=gardens)


def band_rows(band):
    """选定海拔带下按园汇总的行（每园一行，带槽数/批次数）。

    ``band`` 为空时汇总全部园。三卡的总数由这些行直接求和得到，
    因此卡片数字与汇总表行数之间误差恒为 0。
    """
    gardens = gardens_in_band(band or None)
    annotated = gardens.annotate(
        trough_count=Count("troughs", distinct=True),
        batch_count=Count("troughs__batches", distinct=True),
    ).order_by("name")
    return list(annotated)


def band_summary(band):
    """选定海拔带下的三卡数据以及按园汇总行。

    返回 dict::

        {
          "selected_band": "600-800m",  # 精确匹配值，未筛选为 ""
          "has_filter": True,
          "garden_count": N,           # == 筛选后茶园列表行数 == len(rows)
          "trough_count": N,           # == sum(row.trough_count)
          "batch_count": N,            # == sum(row.batch_count)
          "rows": [带注解的 Garden, ...],
        }

    槽数 / 批次数同时用 :func:`troughs_for_gardens` /
    :func:`batches_for_gardens` 独立复核一次；两者与行求和同源，
    任何偏差都说明实现被改坏。
    """
    selected_band = band or ""
    has_filter = bool(selected_band)
    gardens = gardens_in_band(selected_band or None)
    rows = band_rows(selected_band)

    garden_count = gardens.count()
    # 子查询口径：槽/批次只统计这些园下的，绝不碰全库。
    trough_count = troughs_for_gardens(gardens).count()
    batch_count = batches_for_gardens(gardens).count()

    rows_trough_sum = sum(r.trough_count for r in rows)
    rows_batch_sum = sum(r.batch_count for r in rows)
    assert trough_count == rows_trough_sum, (
        f"槽总数口径不一致: 子查询 {trough_count} != 按园汇总 {rows_trough_sum}"
    )
    assert batch_count == rows_batch_sum, (
        f"批次总数口径不一致: 子查询 {batch_count} != 按园汇总 {rows_batch_sum}"
    )
    assert garden_count == len(rows), (
        f"茶园数口径不一致: {garden_count} != 汇总行数 {len(rows)}"
    )

    return {
        "selected_band": selected_band,
        "has_filter": has_filter,
        "garden_count": garden_count,
        "trough_count": trough_count,
        "batch_count": batch_count,
        "rows": rows,
    }
