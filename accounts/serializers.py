from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    initials = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name',
                  'initials', 'role', 'status', 'is_approved', 'date_joined', 'phone']
        read_only_fields = ['id', 'email', 'role', 'status', 'is_approved', 'date_joined']
