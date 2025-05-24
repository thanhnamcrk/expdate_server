from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from .models import Profile

class ProfileInlineForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Lấy danh sách group duy nhất từ các profile đã có
        group_choices = [(g, g) for g in Profile.objects.values_list('group', flat=True).distinct() if g]
        group_choices.insert(0, ('', 'None'))  # Thêm lựa chọn None
        self.fields['group'].widget = forms.Select(choices=group_choices)

    class Meta:
        model = Profile
        fields = ('fullname', 'group')

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('fullname', 'group')
    form = ProfileInlineForm

class CustomUserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'is_active', 'is_staff', 'is_superuser')
        labels = {
            'is_active': _('User'),
            'is_staff': _('Manage'),
            'is_superuser': _('Super'),
        }

class CustomUserAdmin(admin.ModelAdmin):
    form = CustomUserChangeForm
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'user', 'manage', 'super', 'get_group')
    search_fields = ('username', 'email', 'profile__group')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('email',)}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
            'description': ''
        }),
    )
    formfield_overrides = {
        User._meta.get_field('is_active'): {'label': _('User')},
        User._meta.get_field('is_staff'): {'label': _('Manage')},
    }

    def user(self, obj):
        return obj.is_active and not obj.is_staff and not obj.is_superuser
    user.boolean = True
    user.short_description = 'User'

    def manage(self, obj):
        return obj.is_staff and not obj.is_superuser
    manage.boolean = True
    manage.short_description = 'Manage'

    def super(self, obj):
        return obj.is_superuser
    super.boolean = True
    super.short_description = 'Super'

    def get_group(self, obj):
        return obj.profile.group if hasattr(obj, 'profile') else None
    get_group.short_description = 'Group'

    def save_model(self, request, obj, form, change):
        # Cập nhật quyền dựa trên các trường is_active, is_staff, is_superuser
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        # Đảm bảo mỗi user chỉ có 1 group
        instances = formset.save(commit=False)
        for instance in instances:
            if hasattr(instance, 'group'):
                Profile.objects.filter(user=instance.user).exclude(pk=instance.pk).delete()
            instance.save()
        formset.save_m2m()

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
