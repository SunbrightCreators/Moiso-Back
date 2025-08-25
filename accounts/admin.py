from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, PushSubscription, Proposer, ProposerLevel, LocationHistory, Founder
from .forms import CustomUserChangeForm, CustomAdminUserCreationForm

class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {
            "fields": ("name", "birth", "sex", "profile_image", "is_marketing_allowed")
        }),
        ("Permissions", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": (
                "wide",
            ),
            "fields": (
                "email",
                # 비밀번호 생성 관련 (usable_password는 네 커스텀 폼 기준으로 유지)
                "usable_password", "password1", "password2",

                # 👇 추가화면에서도 필수 커스텀 필드 입력받도록
                "name", "birth", "sex", "profile_image", "is_marketing_allowed",

                # 권한(선택)
                "is_active", "is_staff", "is_superuser", "groups", "user_permissions",
            ),
        }),
    )
    form = CustomUserChangeForm
    add_form = CustomAdminUserCreationForm
    list_display = ("email","is_staff",)
    search_fields = ("email",)
    ordering = ("email",)

admin.site.register(User, CustomUserAdmin)
admin.site.register(PushSubscription)
admin.site.register(Proposer)
admin.site.register(ProposerLevel)
admin.site.register(LocationHistory)
admin.site.register(Founder)
