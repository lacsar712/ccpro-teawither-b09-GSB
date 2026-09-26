from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)

from . import stats
from .forms import GardenForm, TroughForm, WitherBatchForm
from .models import Garden, Trough, WitherBatch


def _wants_htmx(request):
    return request.headers.get("HX-Request") == "true"


@login_required
def home(request):
    band = request.GET.get("band", stats.ALL_BANDS) or stats.ALL_BANDS
    context = stats.band_summary(band)
    # 未选带时保留全库槽位状态概览；选带后只看三张对照卡。
    if not stats.is_specific_band(band):
        context.update(
            {
                "ready_count": Trough.objects.filter(
                    status=Trough.STATUS_READY
                ).count(),
                "withering_count": Trough.objects.filter(
                    status=Trough.STATUS_WITHERING
                ).count(),
                "loading_count": Trough.objects.filter(
                    status=Trough.STATUS_LOADING
                ).count(),
            }
        )
    if _wants_htmx(request):
        return HttpResponse(
            render_to_string("home/_band_panel.html", context, request=request)
        )
    return render(request, "home.html", context)


# ---- Garden ----


class GardenListView(LoginRequiredMixin, ListView):
    model = Garden
    template_name = "gardens/list.html"
    context_object_name = "gardens"

    def get_queryset(self):
        # 海拔带“精确匹配”：与首页三张对照卡走同一函数。
        self.selected_band = self.request.GET.get("band", stats.ALL_BANDS)
        return stats.gardens_in_band(self.selected_band)

    def _table_context(self):
        return {
            "gardens": self.object_list,
            "band_choices": stats.altitude_band_choices(),
            "selected_band": self.selected_band,
        }

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "gardens/_table.html", self._table_context(), request=request
            )
            return HttpResponse(html)
        # 整页渲染也使用同一 context builder，口径与 HTMX 完全一致。
        return self.render_to_response(self._table_context())


class GardenCreateView(LoginRequiredMixin, CreateView):
    model = Garden
    form_class = GardenForm
    template_name = "gardens/form.html"
    success_url = reverse_lazy("garden_list")

    def form_valid(self, form):
        messages.success(self.request, "茶园已创建")
        response = super().form_valid(form)
        if _wants_htmx(self.request):
            return redirect("garden_list")
        return response


class GardenUpdateView(LoginRequiredMixin, UpdateView):
    model = Garden
    form_class = GardenForm
    template_name = "gardens/form.html"
    success_url = reverse_lazy("garden_list")

    def form_valid(self, form):
        messages.success(self.request, "茶园已更新")
        return super().form_valid(form)


class GardenDeleteView(LoginRequiredMixin, DeleteView):
    model = Garden
    template_name = "gardens/confirm_delete.html"
    success_url = reverse_lazy("garden_list")

    def form_valid(self, form):
        messages.success(self.request, "茶园已删除")
        return super().form_valid(form)


# ---- Trough ----


class TroughListView(LoginRequiredMixin, ListView):
    model = Trough
    template_name = "troughs/list.html"
    context_object_name = "troughs"

    def get_queryset(self):
        # 槽侧按园过滤：首页“带内槽总数”与本列表共用
        # stats.troughs_for_gardens，禁止两套 SQL。
        self.selected_garden = self.request.GET.get("garden", "")
        if self.selected_garden.isdigit():
            garden = Garden.objects.filter(pk=int(self.selected_garden)).first()
            self.selected_garden = str(garden.pk) if garden else ""
            return stats.troughs_for_gardens([garden] if garden else [])
        return stats.troughs_for_gardens(Garden.objects.all())

    def _table_context(self):
        return {
            "troughs": self.object_list,
            "gardens": Garden.objects.all(),
            "selected_garden": self.selected_garden,
        }

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "troughs/_table.html", self._table_context(), request=request
            )
            return HttpResponse(html)
        return self.render_to_response(self._table_context())


class TroughCreateView(LoginRequiredMixin, CreateView):
    model = Trough
    form_class = TroughForm
    template_name = "troughs/form.html"
    success_url = reverse_lazy("trough_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋槽已创建")
        return super().form_valid(form)


class TroughUpdateView(LoginRequiredMixin, UpdateView):
    model = Trough
    form_class = TroughForm
    template_name = "troughs/form.html"
    success_url = reverse_lazy("trough_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋槽已更新")
        return super().form_valid(form)


class TroughDeleteView(LoginRequiredMixin, DeleteView):
    model = Trough
    template_name = "troughs/confirm_delete.html"
    success_url = reverse_lazy("trough_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋槽已删除")
        return super().form_valid(form)


# ---- WitherBatch ----


class BatchListView(LoginRequiredMixin, ListView):
    model = WitherBatch
    template_name = "batches/list.html"
    context_object_name = "batches"

    def get_queryset(self):
        return WitherBatch.objects.select_related("trough", "trough__garden").all()

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if _wants_htmx(request):
            html = render_to_string(
                "batches/_table.html",
                {"batches": self.object_list},
                request=request,
            )
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class BatchCreateView(LoginRequiredMixin, CreateView):
    model = WitherBatch
    form_class = WitherBatchForm
    template_name = "batches/form.html"
    success_url = reverse_lazy("batch_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋批次已创建")
        return super().form_valid(form)


class BatchUpdateView(LoginRequiredMixin, UpdateView):
    model = WitherBatch
    form_class = WitherBatchForm
    template_name = "batches/form.html"
    success_url = reverse_lazy("batch_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋批次已更新")
        return super().form_valid(form)


class BatchDeleteView(LoginRequiredMixin, DeleteView):
    model = WitherBatch
    template_name = "batches/confirm_delete.html"
    success_url = reverse_lazy("batch_list")

    def form_valid(self, form):
        messages.success(self.request, "萎凋批次已删除")
        return super().form_valid(form)
