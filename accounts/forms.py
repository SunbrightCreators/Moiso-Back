from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm, SetUnusablePasswordMixin
from .models import User

class CustomBaseUserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"

class CustomAdminUserCreationForm(SetUnusablePasswordMixin, CustomBaseUserCreationForm):
    usable_password = SetUnusablePasswordMixin.create_usable_password_field()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].required = False
        self.fields["password2"].required = False