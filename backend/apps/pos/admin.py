from django.contrib import admin

from .models import POSPayment, POSReturn, POSReturnLine, POSSale, POSSaleLine, POSShift, Store, Till


class POSSaleLineInline(admin.TabularInline):
    model = POSSaleLine
    extra = 0


class POSPaymentInline(admin.TabularInline):
    model = POSPayment
    extra = 0


class POSReturnLineInline(admin.TabularInline):
    model = POSReturnLine
    extra = 0


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "entity", "warehouse", "is_active")


@admin.register(Till)
class TillAdmin(admin.ModelAdmin):
    list_display = ("store", "code", "name", "is_active")


@admin.register(POSShift)
class POSShiftAdmin(admin.ModelAdmin):
    list_display = ("id", "till", "opened_by", "status", "opened_at", "closed_at")
    list_filter = ("status",)


@admin.register(POSSale)
class POSSaleAdmin(admin.ModelAdmin):
    list_display = ("id", "shift", "status", "created_by", "created_at")
    list_filter = ("status",)
    inlines = [POSSaleLineInline, POSPaymentInline]


@admin.register(POSReturn)
class POSReturnAdmin(admin.ModelAdmin):
    list_display = ("id", "sale", "refund_method", "created_by", "created_at")
    inlines = [POSReturnLineInline]
