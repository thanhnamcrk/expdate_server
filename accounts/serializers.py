from rest_framework import serializers
from django.contrib.auth.models import User, Group
from .models import Profile

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    full_name = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    group = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'full_name', 'email', 'group']

    def create(self, validated_data):
        full_name = validated_data.pop('full_name')
        group_name = validated_data.pop('group')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        username = validated_data.pop('username')

        user = User.objects.create_user(username=username, password=password, email=email)

        name_parts = full_name.strip().split(' ', 1)
        user.first_name = name_parts[0]
        user.last_name = name_parts[1] if len(name_parts) > 1 else ''
        user.save()

        # Tạo profile (nếu dùng signals thì có thể đã tự tạo rồi)
        profile = Profile.objects.get(user=user)
        profile.fullname = full_name
        profile.group = group_name
        profile.save()

        group_obj, created = Group.objects.get_or_create(name=group_name)
        user.groups.add(group_obj)

        return user
