from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Garden, Trough, WitherBatch


def ensure_seed_data():
    """Idempotent seed: users + 3 个海拔带，每带均有园/槽/批次。

    海拔带（altitudeBand 整串精确匹配）：
    - 600-800m：2 园 / 3 槽 / 2 批次（其中一园有槽无批次，制造对照差异）
    - 800-1000m：2 园 / 2 槽 / 2 批次
    - 1000-1200m：1 园 / 1 槽 / 1 批次
    """
    User = get_user_model()

    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@teawither.local", "123456")

    if not User.objects.filter(username="witherer").exists():
        User.objects.create_user("witherer", "witherer@teawither.local", "123456")

    if Garden.objects.exists():
        return

    now = timezone.now()

    # ---- 600-800m ----
    g_low1 = Garden.objects.create(
        name="竹影台二号园",
        altitudeBand="600-800m",
        notes="背风缓坡",
    )
    g_low2 = Garden.objects.create(
        name="溪畔小园",
        altitudeBand="600-800m",
        notes="临溪，湿度偏高",
    )

    t_b1 = Trough.objects.create(
        garden=g_low1,
        troughCode="B-01",
        cultivar="黄金芽",
        loadKg=Decimal("88.25"),
        status=Trough.STATUS_WITHERING,
    )
    WitherBatch.objects.create(
        trough=t_b1,
        startedAt=now - timezone.timedelta(hours=30),
        targetMoisture=Decimal("36.00"),
        actualMoisture=Decimal("42.00"),
        rollGrade="二级",
    )
    # 可下槽槽位：先建批次（实测含水率合格）再置 ready。
    t_b2 = Trough.objects.create(
        garden=g_low1,
        troughCode="B-02",
        cultivar="龙井43",
        loadKg=Decimal("110.00"),
        status=Trough.STATUS_WITHERING,
    )
    WitherBatch.objects.create(
        trough=t_b2,
        startedAt=now - timezone.timedelta(hours=24),
        targetMoisture=Decimal("35.00"),
        actualMoisture=Decimal("34.80"),
        rollGrade="特级",
    )
    t_b2.status = Trough.STATUS_READY
    t_b2.save()

    # 有槽但尚无批次的园：该带槽总数与批次总数因此不同。
    Trough.objects.create(
        garden=g_low2,
        troughCode="C-01",
        cultivar="毛蟹",
        loadKg=Decimal("60.00"),
        status=Trough.STATUS_LOADING,
    )

    # ---- 800-1000m ----
    g_mid1 = Garden.objects.create(
        name="云雾岭一号园",
        altitudeBand="800-1000m",
        notes="向阳坡，晨雾较重",
    )
    g_mid2 = Garden.objects.create(
        name="松风岭园",
        altitudeBand="800-1000m",
        notes="松林旁侧，散射光足",
    )

    t_a1 = Trough.objects.create(
        garden=g_mid1,
        troughCode="A-01",
        cultivar="福鼎大白",
        loadKg=Decimal("120.50"),
        status=Trough.STATUS_WITHERING,
    )
    WitherBatch.objects.create(
        trough=t_a1,
        startedAt=now - timezone.timedelta(hours=18),
        targetMoisture=Decimal("38.00"),
        actualMoisture=Decimal("37.50"),
        rollGrade="一级",
    )
    t_a2 = Trough.objects.create(
        garden=g_mid1,
        troughCode="A-02",
        cultivar="铁观音",
        loadKg=Decimal("95.00"),
        status=Trough.STATUS_LOADING,
    )
    WitherBatch.objects.create(
        trough=t_a2,
        startedAt=now - timezone.timedelta(hours=2),
        targetMoisture=Decimal("40.00"),
        actualMoisture=None,
        rollGrade="待评",
    )

    t_d1 = Trough.objects.create(
        garden=g_mid2,
        troughCode="D-01",
        cultivar="梅占",
        loadKg=Decimal("100.00"),
        status=Trough.STATUS_WITHERING,
    )
    WitherBatch.objects.create(
        trough=t_d1,
        startedAt=now - timezone.timedelta(hours=20),
        targetMoisture=Decimal("37.00"),
        actualMoisture=Decimal("36.20"),
        rollGrade="一级",
    )
    t_d1.status = Trough.STATUS_READY
    t_d1.save()

    # ---- 1000-1200m ----
    g_high = Garden.objects.create(
        name="高山云顶园",
        altitudeBand="1000-1200m",
        notes="高海拔，芽叶偏嫩",
    )
    t_e1 = Trough.objects.create(
        garden=g_high,
        troughCode="E-01",
        cultivar="白毫早",
        loadKg=Decimal("72.50"),
        status=Trough.STATUS_WITHERING,
    )
    WitherBatch.objects.create(
        trough=t_e1,
        startedAt=now - timezone.timedelta(hours=12),
        targetMoisture=Decimal("36.50"),
        actualMoisture=Decimal("36.10"),
        rollGrade="特级",
    )
