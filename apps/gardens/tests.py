import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.gardens import stats
from apps.gardens.models import Garden, Trough, WitherBatch
from apps.gardens.seed import ensure_seed_data


def _norm(html):
    """压缩全部空白，便于比较整页片段与 HTMX 片段是否同口径。"""
    return re.sub(r"\s+", "", html)


class BandStatsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_seed_data()
        cls.user = get_user_model().objects.create_user("tester", password="x")

    def setUp(self):
        self.client.force_login(self.user)

    def test_seed_has_multiple_bands_each_with_garden_trough_batch(self):
        bands = list(
            Garden.objects.values_list("altitudeBand", flat=True).distinct()
        )
        self.assertGreaterEqual(len(bands), 2)
        for band in bands:
            gardens = stats.gardens_in_band(band)
            self.assertGreater(gardens.count(), 0, f"{band} 无园")
            self.assertGreater(
                stats.troughs_for_gardens(gardens).count(), 0, f"{band} 无槽"
            )
            self.assertGreater(
                stats.batches_for_gardens(gardens).count(), 0, f"{band} 无批次"
            )

    def test_three_cards_match_list_rows_and_per_garden_rows(self):
        """三张对照卡 == 筛选后茶园行数 / Σ按园槽行 / Σ按园批次行，误差 0。"""
        bands = dict(stats.altitude_band_choices()).keys()
        for band in bands:
            if not band:
                continue
            summary = stats.band_summary(band)

            # 卡1 == 茶园列表精确筛选后的行数
            garden_rows = list(stats.gardens_in_band(band))
            self.assertEqual(summary["garden_count"], len(garden_rows))

            # 卡2 == Σ按园槽行 == 按这些园过滤后的槽列表行数
            trough_list_rows = stats.troughs_for_gardens(garden_rows).count()
            self.assertEqual(
                summary["trough_count"], sum(n for _, n in summary["trough_rows"])
            )
            self.assertEqual(summary["trough_count"], trough_list_rows)

            # 卡3 == Σ按园批次行 == 按这些园过滤后的批次行数
            batch_list_rows = stats.batches_for_gardens(garden_rows).count()
            self.assertEqual(
                summary["batch_count"], sum(n for _, n in summary["batch_rows"])
            )
            self.assertEqual(summary["batch_count"], batch_list_rows)

    def test_band_match_is_exact_not_prefix_or_range(self):
        """精确匹配：800-1000m 不命中 1000-1200m，前缀串也不命中。"""
        self.assertTrue(stats.gardens_in_band("800-1000m").exists())
        self.assertTrue(stats.gardens_in_band("1000-1200m").exists())
        self.assertFalse(stats.gardens_in_band("800").exists())
        self.assertFalse(stats.gardens_in_band("800-1200m").exists())

    def test_no_match_band_is_all_zero_and_empty(self):
        """无匹配带：三卡为 0、列表为空、首页不报错。"""
        summary = stats.band_summary("不存在的带 9999m")
        self.assertEqual(summary["garden_count"], 0)
        self.assertEqual(summary["trough_count"], 0)
        self.assertEqual(summary["batch_count"], 0)
        self.assertEqual(list(summary["band_gardens"]), [])
        self.assertEqual(summary["trough_rows"], [])
        self.assertEqual(summary["batch_rows"], [])

        resp = self.client.get(reverse("home"), {"band": "不存在的带 9999m"})
        self.assertEqual(resp.status_code, 200)
        for ctx_key in ("garden_count", "trough_count", "batch_count"):
            self.assertEqual(resp.context[ctx_key], 0)

        resp = self.client.get(reverse("garden_list"), {"band": "不存在的带 9999m"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["gardens"]), 0)

    def test_home_full_page_and_htmx_share_same_panel(self):
        """切换带后整页与 HTMX 局部刷新口径一致（同一 panel 片段）。"""
        band = "600-800m"
        full = self.client.get(reverse("home"), {"band": band})
        hx = self.client.get(
            reverse("home"), {"band": band}, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(full.status_code, 200)
        self.assertEqual(hx.status_code, 200)
        self.assertIn(_norm(hx.content.decode()), _norm(full.content.decode()))

        summary = stats.band_summary(band)
        body = hx.content.decode()
        for name, num in summary["trough_rows"]:
            self.assertIn(name, body)
        # 该带有一个“有槽无批次”之外：槽总数与批次总数在 600-800m 不同
        self.assertNotEqual(summary["trough_count"], summary["batch_count"])

    def test_garden_list_full_and_htmx_consistent(self):
        band = "800-1000m"
        full = self.client.get(reverse("garden_list"), {"band": band})
        hx = self.client.get(
            reverse("garden_list"), {"band": band}, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(full.status_code, 200)
        self.assertEqual(hx.status_code, 200)
        self.assertIn(_norm(hx.content.decode()), _norm(full.content.decode()))
        expected = stats.gardens_in_band(band).count()
        self.assertEqual(len(full.context["gardens"]), expected)

    def test_trough_list_full_and_htmx_consistent(self):
        garden = Garden.objects.filter(altitudeBand="800-1000m").first()
        full = self.client.get(reverse("trough_list"), {"garden": garden.pk})
        hx = self.client.get(
            reverse("trough_list"), {"garden": garden.pk}, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(full.status_code, 200)
        self.assertEqual(hx.status_code, 200)
        self.assertIn(_norm(hx.content.decode()), _norm(full.content.decode()))

    def test_trough_garden_filter_uses_same_source_as_home_card(self):
        """槽侧按园过滤与首页槽总数同源 stats.troughs_for_gardens。"""
        for band, _ in stats.altitude_band_choices():
            if not band:
                continue
            gardens = list(stats.gardens_in_band(band))
            card_total = stats.band_summary(band)["trough_count"]

            via_list_filter = 0
            for g in gardens:
                resp = self.client.get(reverse("trough_list"), {"garden": g.pk})
                via_list_filter += len(resp.context["troughs"])
                # 视图结果必须与同源函数逐条一致
                direct = list(stats.troughs_for_gardens([g]))
                self.assertEqual(list(resp.context["troughs"]), direct)

            self.assertEqual(via_list_filter, card_total)

    def test_trough_filter_invalid_garden_id_is_empty_not_error(self):
        resp = self.client.get(reverse("trough_list"), {"garden": "999999"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["troughs"]), 0)

    def test_home_without_band_shows_global_totals(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["garden_count"], Garden.objects.count())
        self.assertEqual(resp.context["trough_count"], Trough.objects.count())
        self.assertEqual(resp.context["batch_count"], WitherBatch.objects.count())
