from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from .forms import CustomUserChangeForm, CustomAdminUserCreationForm

class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("email","password",)}),
        ("Permissions", {"fields": ("is_active","is_staff","is_superuser","groups","user_permissions",)}),
        ("Important dates", {"fields": ("last_login","date_joined",)}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email","usable_password","password1","password2"),
        }),
    )
    form = CustomUserChangeForm
    add_form = CustomAdminUserCreationForm
    list_display = ("email","is_staff",)
    search_fields = ("email",)
    ordering = ("email",)

admin.site.register(CustomUser, CustomUserAdmin)
