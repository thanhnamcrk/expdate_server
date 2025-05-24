from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import serializers
from .models import Item  # Import the Item model
from django.contrib.auth.models import User  # Import the User model
from django.utils.timezone import now
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

class ItemSerializer(serializers.Serializer):
    barcode = serializers.CharField(max_length=100)
    itemname = serializers.CharField(max_length=255)
    quantity = serializers.IntegerField()
    expdate = serializers.DateField(input_formats=['%d/%m/%Y'])

class ItemCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = ItemSerializer(data=request.data)
        if serializer.is_valid():
            # Process the valid data here
            data = serializer.validated_data
            user = request.user

            # Log the IP address of the client
            client_ip = request.META.get('REMOTE_ADDR', '')
            print(f"Request received from IP: {client_ip} at {now()}")

            # Check if an item with the same barcode and expdate exists
            # Đảm bảo expdate là kiểu date, so sánh đúng
            expdate = data['expdate']
            if isinstance(expdate, str):
                from datetime import datetime
                try:
                    expdate = datetime.strptime(expdate, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        expdate = datetime.strptime(expdate, '%d/%m/%Y').date()
                    except Exception:
                        pass
            existing_item = Item.objects.filter(barcode=data['barcode'], expdate=expdate, user=user).first()
            if existing_item:
                # Update the quantity of the existing item
                existing_item.quantity += data['quantity']
                existing_item.save()
                serializer_data = serializer.data.copy()
                serializer_data['quantity'] = existing_item.quantity
                return Response({
                    "message": "Item quantity updated successfully",
                    "data": serializer_data,
                    "iid": existing_item.id
                }, status=status.HTTP_200_OK)
            else:
                # Save the new item to the database
                item = Item.objects.create(
                    barcode=data['barcode'],
                    itemname=data['itemname'],
                    quantity=data['quantity'],
                    expdate=data['expdate'],
                    user=user  # Associate the item with the provided user
                )
                return Response({
                    "message": "Item created successfully",
                    "data": serializer.data,
                    "iid": item.id
                }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ItemListByGroupView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user = request.user
        try:
            group = user.profile.group
        except AttributeError:
            return Response({'error': 'User or group not found'}, status=status.HTTP_404_NOT_FOUND)
        # Lấy tất cả user trong cùng group
        users_in_group = User.objects.filter(profile__group=group)
        users_data = []
        is_manage = user.is_staff or user.is_superuser
        for u in users_in_group:
            items = Item.objects.filter(user=u)
            items_data = [
                {
                    'id': item.id,
                    'barcode': item.barcode,
                    'itemname': item.itemname,
                    'quantity': item.quantity,
                    'expdate': item.expdate,
                    'can_edit': is_manage or (item.user == user),
                    'can_delete': is_manage or (item.user == user),
                }
                for item in items
            ]
            users_data.append({
                'username': u.username,
                'full_name': u.profile.fullname if hasattr(u, 'profile') else '',
                'items': items_data
            })
        return Response({'group': group, 'users': users_data}, status=status.HTTP_200_OK)

class ItemDeleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        user = request.user
        try:
            item = Item.objects.get(id=item_id)
        except Item.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)

        if item.user == user or user.is_staff or user.is_superuser:
            item.delete()
            return Response({'message': 'Item deleted successfully'}, status=status.HTTP_200_OK)

        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

class ItemUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def put(self, request, item_id):
        user = request.user
        try:
            item = Item.objects.get(id=item_id)
        except Item.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)
        # Chỉ cho phép sửa nếu là chủ sở hữu hoặc manage
        if not (item.user == user or user.is_staff or user.is_superuser):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ItemSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            for attr, value in serializer.validated_data.items():
                setattr(item, attr, value)
            item.save()
            return Response({
                'message': 'Item updated successfully',
                'iid': item.id
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
