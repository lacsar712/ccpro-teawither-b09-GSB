from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Garden, Trough, WitherBatch


def ensure_seed_data():
    """Idempotent seed: users + sample gardens/troughs/batches.

    覆盖三个海拔带，**每个带都有园、有槽、有批次**，便于验证首页
    海拔带精确筛选与三张对照卡：

    * 800-1000m：云雾岭一号园、雪顶东坡园
    * 600-800m ：竹影台二号园、梅家坞西坡园
    * 400-600m ：清溪畔三号园、黄泥土坎园
    """
    User = get_user_model()

    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@teawither.local", "123456")

    if not User.objects.filter(username="witherer").exists():
        User.objects.create_user("witherer", "witherer@teawither.local", "123456")

    if Garden.objects.exists():
        return

    # (园名, 海拔带, 备注, [(槽号, 品种, 装叶量, 状态, 目标含水, 实测含水, 揉捻等级), ...])
    seed = [
        (
            "云雾岭一号园", "800-1000m", "向阳坡，晨雾较重",
            [
                ("A-01", "福鼎大白", "120.50", Trough.STATUS_WITHERING, "38.00", "37.50", "一级"),
                ("A-02", "铁观音", "95.00", Trough.STATUS_LOADING, "40.00", None, "待评"),
            ],
        ),
        (
            "雪顶东坡园", "800-1000m", "高海拔，昼夜温差大",
            [
                ("X-01", "白毫早", "102.00", Trough.STATUS_WITHERING, "36.50", "39.20", "二级"),
            ],
        ),
        (
            "竹影台二号园", "600-800m", "背风缓坡",
            [
                ("B-01", "黄金芽", "88.25", Trough.STATUS_WITHERING, "36.00", "42.00", "二级"),
                # 最新批次实测 34.80 ≤ 40，可设为「可下槽」
                ("B-02", "龙井43", "110.00", Trough.STATUS_READY, "35.00", "34.80", "特级"),
            ],
        ),
        (
            "梅家坞西坡园", "600-800m", "老丛群体种",
            [
                ("M-01", "群体种", "76.40", Trough.STATUS_LOADING, "39.00", None, "待评"),
            ],
        ),
        (
            "清溪畔三号园", "400-600m", "溪谷边，湿度偏高",
            [
                ("C-01", "安吉白茶", "130.00", Trough.STATUS_WITHERING, "37.00", "36.60", "一级"),
            ],
        ),
        (
            "黄泥土坎园", "400-600m", "黄土台地，排水好",
            [
                ("H-01", "毛蟹", "64.75", Trough.STATUS_WITHERING, "38.50", "38.10", "三级"),
            ],
        ),
    ]

    now = timezone.now()
    for gi, (gname, band, notes, troughs) in enumerate(seed):
        garden = Garden.objects.create(name=gname, altitudeBand=band, notes=notes)
        for ti, (code, cultivar, load, status, target, actual, grade) in enumerate(
            troughs
        ):
            # READY 槽先以 withering 建槽+批次，再按业务规则置 READY，
            # 走 Trough.clean() 校验。
            initial_status = (
                Trough.STATUS_WITHERING if status == Trough.STATUS_READY else status
            )
            trough = Trough.objects.create(
                garden=garden,
                troughCode=code,
                cultivar=cultivar,
                loadKg=Decimal(load),
                status=initial_status,
            )
            WitherBatch.objects.create(
                trough=trough,
                startedAt=now
                - timezone.timedelta(hours=2 + gi * 3 + ti * 2),
                targetMoisture=Decimal(target),
                actualMoisture=Decimal(actual) if actual is not None else None,
                rollGrade=grade,
            )
            if status == Trough.STATUS_READY:
                trough.status = Trough.STATUS_READY
                trough.save()
