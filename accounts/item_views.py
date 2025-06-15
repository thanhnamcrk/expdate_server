from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import serializers
from .models import Item  # Import the Item model
from django.contrib.auth.models import User  # Import the User model
from django.utils.timezone import now
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from datetime import timedelta

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
            def format_expdate(dt):
                if not dt:
                    return ''
                return dt.strftime('%d/%m/%Y')
            if existing_item:
                # Update the quantity of the existing item
                existing_item.quantity += data['quantity']
                existing_item.save()
                serializer_data = serializer.data.copy()
                serializer_data['quantity'] = existing_item.quantity
                serializer_data['expdate'] = format_expdate(existing_item.expdate)
                item_obj = existing_item
            else:
                # Save the new item to the database
                item = Item.objects.create(
                    barcode=data['barcode'],
                    itemname=data['itemname'],
                    quantity=data['quantity'],
                    expdate=data['expdate'],
                    user=user  # Associate the item with the provided user
                )
                serializer_data = serializer.data.copy()
                serializer_data['expdate'] = format_expdate(item.expdate)
                item_obj = item
            # Tính lại số lượng realtime
            from datetime import timedelta
            today = now().date()
            soon_threshold = today + timedelta(days=15)
            user_items = Item.objects.filter(user=user)
            expired_count = user_items.filter(expdate__lt=today).count()
            soon_expire_count = user_items.filter(expdate__gte=today, expdate__lte=soon_threshold).count()
            valid_count = user_items.filter(expdate__gt=soon_threshold).count()
            return Response({
                "message": "Item created successfully" if not existing_item else "Item quantity updated successfully",
                "data": serializer_data,
                "iid": item_obj.id,
                "user_id": user.id,  # Thêm user_id vào response
                "expired_count": expired_count,
                "soon_expire_count": soon_expire_count,
                "valid_count": valid_count
            }, status=status.HTTP_201_CREATED if not existing_item else status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ItemListByGroupView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user = request.user
        # Xóa các item hết hạn > 30 ngày
        today = now().date()
        threshold = today - timedelta(days=30)
        Item.objects.filter(expdate__lt=threshold).delete()
        try:
            group = user.profile.group
        except AttributeError:
            return Response({'error': 'User or group not found'}, status=status.HTTP_404_NOT_FOUND)
        users_in_group = User.objects.filter(profile__group=group)
        is_manage = user.is_staff or user.is_superuser
        soon_threshold = today + timedelta(days=15)
        users_data = []
        for u in users_in_group:
            items = Item.objects.filter(user=u)
            expired_count = items.filter(expdate__lt=today).count()
            soon_expire_count = items.filter(expdate__gte=today, expdate__lte=soon_threshold).count()
            valid_count = items.filter(expdate__gt=soon_threshold).count()
            users_data.append({
                'id': u.id,
                # 'username': u.username,
                'full_name': u.profile.fullname if hasattr(u, 'profile') else '',
                'expired_count': expired_count,
                'soon_expire_count': soon_expire_count,
                'valid_count': valid_count
            })
        return Response({'group': group, 'users': users_data, 'is_manage': is_manage}, status=status.HTTP_200_OK)

class UserItemListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, user_id):
        current_user = request.user
        is_manage = current_user.is_staff or current_user.is_superuser
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        items = Item.objects.filter(user=user)
        items_data = [
            {
                'id': item.id,
                'barcode': item.barcode,
                'itemname': item.itemname,
                'quantity': item.quantity,
                'expdate': item.expdate,
                'can_edit': is_manage or (item.user == current_user),
                'can_delete': is_manage or (item.user == current_user),
            }
            for item in items
        ]
        return Response({'user_id': user.id, 'username': user.username, 'items': items_data}, status=status.HTTP_200_OK)

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
            item_user = item.user
            item.delete()
            # Tính lại số lượng các loại sản phẩm của user sau khi xóa
            from datetime import timedelta
            today = now().date()
            soon_threshold = today + timedelta(days=15)
            user_items = Item.objects.filter(user=item_user)
            expired_count = user_items.filter(expdate__lt=today).count()
            soon_expire_count = user_items.filter(expdate__gte=today, expdate__lte=soon_threshold).count()
            valid_count = user_items.filter(expdate__gt=soon_threshold).count()
            return Response({
                'message': 'Item deleted successfully',
                'expired_count': expired_count,
                'soon_expire_count': soon_expire_count,
                'valid_count': valid_count
            }, status=status.HTTP_200_OK)

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
            data = serializer.validated_data
            # Kiểm tra nếu có barcode, itemname, expdate trùng với item khác thì chỉ update quantity
            barcode = data.get('barcode', item.barcode)
            itemname = data.get('itemname', item.itemname)
            expdate = data.get('expdate', item.expdate)
            # Đảm bảo expdate là date
            if isinstance(expdate, str):
                from datetime import datetime
                try:
                    expdate = datetime.strptime(expdate, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        expdate = datetime.strptime(expdate, '%d/%m/%Y').date()
                    except Exception:
                        pass
            duplicate = Item.objects.filter(barcode=barcode, itemname=itemname, expdate=expdate, user=user).exclude(id=item.id).first()
            if duplicate:
                # Nếu trùng, cộng quantity vào item trùng, xóa item hiện tại
                duplicate.quantity += data.get('quantity', item.quantity)
                duplicate.save()
                item.delete()
                item = duplicate
            else:
                for attr, value in data.items():
                    setattr(item, attr, value)
                item.save()
            # Tính lại số lượng các loại sản phẩm của user
            from datetime import timedelta
            today = now().date()
            soon_threshold = today + timedelta(days=15)
            user_items = Item.objects.filter(user=user)
            expired_count = user_items.filter(expdate__lt=today).count()
            soon_expire_count = user_items.filter(expdate__gte=today, expdate__lte=soon_threshold).count()
            valid_count = user_items.filter(expdate__gt=soon_threshold).count()
            return Response({
                'message': 'Item updated successfully',
                'item': ItemSerializer(item).data,
                'id': item.id,
                'expired_count': expired_count,
                'soon_expire_count': soon_expire_count,
                'valid_count': valid_count
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
