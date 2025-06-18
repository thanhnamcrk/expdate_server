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
import threading
import time
from django.core.mail import send_mail as django_send_mail
from django.conf import settings
from django.utils import timezone
import datetime

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

# Gửi mail sử dụng SMTP thủ công (từ mail_api.py)
def send_expiry_email(to_email, subject, body_html):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    
    # Template HTML cơ bản cho email
    def get_email_template(content, email_type="info"):
        """
        Tạo template email đồng bộ
        email_type: 'warning' (sắp hết hạn), 'danger' (đã hết hạn), 'info' (thông tin chung)
        """
        # Màu sắc theo loại email
        colors = {
            'warning': {
                'primary': '#f39c12',
                'secondary': '#e67e22',
                'text': '#8b4513'
            },
            'danger': {
                'primary': '#e74c3c',
                'secondary': '#c0392b',
                'text': '#722f37'
            },
            'info': {
                'primary': '#3498db',
                'secondary': '#2980b9',
                'text': '#2c3e50'
            }
        }
        
        color_scheme = colors.get(email_type, colors['info'])
        
        signature = f"""
        <div style="margin-top: 40px; padding-top: 20px; border-top: 2px solid {color_scheme['primary']};">
            <div style="font-size: 14px; color: #555555; line-height: 1.6;">
                Trân trọng,<br>
                <strong style="color: {color_scheme['primary']}; font-size: 16px;">Thành Nam</strong><br>
                <span style="color: #888;">Founder @ nguyenthanhnam.io.vn</span><br>
                <a href="https://nguyenthanhnam.io.vn/wp" style="color: {color_scheme['primary']}; text-decoration: none;">
                    https://nguyenthanhnam.io.vn/wp
                </a>
            </div>
        </div>
        """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Thông Báo Hạn Sử Dụng</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                
                <!-- Header -->
                <div style="background: linear-gradient(135deg, {color_scheme['primary']} 0%, {color_scheme['secondary']} 100%); padding: 30px 40px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px;">
                        📦 Quản Lý Hạn Sử Dụng
                    </h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">
                        Hệ thống thông báo tự động
                    </p>
                </div>
                
                <!-- Content -->
                <div style="padding: 40px;">
                    {content}
                </div>
                
                <!-- Signature -->
                {signature}
                
                <!-- Footer -->
                <div style="background-color: #f8f9fa; padding: 20px 40px; text-align: center; border-top: 1px solid #e9ecef;">
                    <p style="color: #6c757d; font-size: 12px; margin: 0;">
                        © 2025 nguyenthanhnam.io.vn - Hệ thống quản lý tự động
                    </p>
                </div>
                
            </div>
        </body>
        </html>
        """
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = "thanhnamsuken@gmail.com"
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html"))
    
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login("thanhnamsuken@gmail.com", "hnvjgqonbzpsxnvk")
            server.sendmail(msg["From"], msg["To"], msg.as_string())
    except Exception as e:
        print(f"Send mail error: {e}")

def create_item_card(item, now_date, card_type="warning"):
    """
    Tạo card sản phẩm với thiết kế đồng bộ
    card_type: 'warning' (sắp hết hạn), 'danger' (đã hết hạn)
    """
    if card_type == "warning":
        days_left = (item.expdate - now_date).days
        status_text = 'hôm nay' if days_left == 0 else f'{days_left} ngày'
        status_color = '#f39c12' if days_left > 3 else '#e74c3c'
        border_color = '#f39c12'
        icon = '⚠️'
    else:  # danger
        days_expired = (now_date - item.expdate).days
        status_text = f'{days_expired} ngày'
        status_color = '#e74c3c'
        border_color = '#e74c3c'
        icon = '❌'
    
    return f"""
    <div style="
        border: 2px solid {border_color}; 
        border-radius: 12px; 
        padding: 20px; 
        margin-bottom: 16px; 
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        position: relative;
    ">
        <div style="position: absolute; top: -1px; right: 15px; font-size: 20px;">{icon}</div>
        
        <div style="display: grid; gap: 8px;">
            <div style="display: flex; align-items: center;">
                <span style="font-weight: 600; color: #2c3e50; font-size: 16px; margin-right: 8px;">📦</span>
                <span style="font-weight: 600; color: #2c3e50; font-size: 16px;">{item.itemname}</span>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 8px;">
                <div>
                    <span style="color: #888; font-size: 13px; font-weight: 500;">BARCODE</span><br>
                    <span style="color: #495057; font-weight: 500;">{item.barcode}</span>
                </div>
                <div>
                    <span style="color: #888; font-size: 13px; font-weight: 500;">SỐ LƯỢNG</span><br>
                    <span style="color: #e67e22; font-weight: 600;">{item.quantity}</span>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 8px;">
                <div>
                    <span style="color: #888; font-size: 13px; font-weight: 500;">HẠN SỬ DỤNG</span><br>
                    <span style="color: #c0392b; font-weight: 600;">{item.expdate.strftime('%d/%m/%Y')}</span>
                </div>
                <div>
                    <span style="color: #888; font-size: 13px; font-weight: 500;">
                        {'CÒN LẠI' if card_type == 'warning' else 'ĐÃ HẾT HẠN'}
                    </span><br>
                    <span style="color: {status_color}; font-weight: 700; font-size: 15px;">{status_text}</span>
                </div>
            </div>
        </div>
    </div>
    """

def seconds_until_next_midnight():
    import datetime
    now = datetime.datetime.now()
    tomorrow = now + datetime.timedelta(days=1)
    midnight = datetime.datetime.combine(tomorrow.date(), datetime.time(0, 0, 0))
    return (midnight - now).total_seconds()

# Hàm kiểm tra và gửi mail định kỳ - CẢI TIẾN
def check_and_notify_expiring_items():
    while True:
        now_date = timezone.now().date()
        soon_threshold = now_date + timedelta(days=15)
        users = User.objects.all()
        
        for user in users:
            email = user.email
            if not email:
                continue
                
            expiring_items = Item.objects.filter(
                user=user, 
                expdate__gte=now_date, 
                expdate__lte=soon_threshold
            )
            
            if expiring_items.exists():
                # Tạo danh sách sản phẩm với design mới
                item_cards = "".join([
                    create_item_card(item, now_date, "warning")
                    for item in expiring_items
                ])
                
                import datetime
                now_str = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                subject = f"⚠️ Thông báo sản phẩm sắp hết hạn [{now_str}]"
                
                # Nội dung email với thiết kế mới
                content = f"""
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); 
                                padding: 20px; border-radius: 12px; border-left: 4px solid #f39c12;">
                        <h2 style="color: #8b4513; margin: 0 0 8px 0; font-size: 20px;">
                            🔔 Cảnh Báo Hạn Sử Dụng
                        </h2>
                        <p style="color: #8b4513; margin: 0; font-size: 15px;">
                            Bạn có <strong>{expiring_items.count()} sản phẩm</strong> sắp hết hạn trong 15 ngày tới
                        </p>
                    </div>
                </div>
                
                <div style="margin-bottom: 30px;">
                    {item_cards}
                </div>
                
                <div style="background-color: #e8f4fd; padding: 20px; border-radius: 12px; text-align: center;">
                    <p style="color: #2980b9; margin: 0; font-size: 14px; font-weight: 500;">
                        💡 <strong>Gợi ý:</strong> Vui lòng kiểm tra và đưa sản phẩm lên UPSELLING để tối ưu doanh thu!
                    </p>
                </div>
                """
                
                # Sử dụng template mới
                def get_email_template(content, email_type="warning"):
                    colors = {
                        'warning': {'primary': '#f39c12', 'secondary': '#e67e22'},
                        'danger': {'primary': '#e74c3c', 'secondary': '#c0392b'},
                    }
                    color_scheme = colors.get(email_type, colors['warning'])
                    
                    signature = f"""
                    <div style="margin-top: 40px; padding-top: 20px; border-top: 2px solid {color_scheme['primary']};">
                        <div style="font-size: 14px; color: #555555; line-height: 1.6;">
                            Trân trọng,<br>
                            <strong style="color: {color_scheme['primary']}; font-size: 16px;">Thành Nam</strong><br>
                            <span style="color: #888;">Founder @ nguyenthanhnam.io.vn</span><br>
                            <a href="https://nguyenthanhnam.io.vn/wp" style="color: {color_scheme['primary']}; text-decoration: none;">
                                https://nguyenthanhnam.io.vn/wp
                            </a>
                        </div>
                    </div>
                    """
                    
                    return f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    </head>
                    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa;">
                        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                            <div style="background: linear-gradient(135deg, {color_scheme['primary']} 0%, {color_scheme['secondary']} 100%); padding: 30px 40px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600;">
                                    📦 Quản Lý Hạn Sử Dụng
                                </h1>
                                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">
                                    Hệ thống thông báo tự động
                                </p>
                            </div>
                            <div style="padding: 40px;">
                                {content}
                            </div>
                            {signature}
                            <div style="background-color: #f8f9fa; padding: 20px 40px; text-align: center; border-top: 1px solid #e9ecef;">
                                <p style="color: #6c757d; font-size: 12px; margin: 0;">
                                    © 2025 nguyenthanhnam.io.vn - Hệ thống quản lý tự động
                                </p>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                
                body_html = get_email_template(content, "warning")
                send_expiry_email(email, subject, body_html)
                
        # Chỉ gửi mail đúng vào 12 giờ đêm mỗi ngày
        time.sleep(seconds_until_next_midnight())

# Hàm kiểm tra sản phẩm đã hết hạn - CẢI TIẾN
def check_and_notify_expired_items():
    while True:
        now_date = timezone.now().date()
        users = User.objects.all()
        
        for user in users:
            email = user.email
            if not email:
                continue
                
            expired_items = Item.objects.filter(user=user, expdate__lt=now_date)
            
            if expired_items.exists():
                # Tạo danh sách sản phẩm đã hết hạn
                item_cards = "".join([
                    create_item_card(item, now_date, "danger")
                    for item in expired_items
                ])
                
                import datetime
                now_str = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                subject = f"🚨 Thông báo sản phẩm đã hết hạn [{now_str}]"
                
                content = f"""
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%); 
                                padding: 20px; border-radius: 12px; border-left: 4px solid #e74c3c;">
                        <h2 style="color: #722f37; margin: 0 0 8px 0; font-size: 20px;">
                            🚨 Cảnh Báo Khẩn Cấp
                        </h2>
                        <p style="color: #722f37; margin: 0; font-size: 15px;">
                            Bạn có <strong>{expired_items.count()} sản phẩm</strong> đã hết hạn sử dụng
                        </p>
                    </div>
                </div>
                
                <div style="margin-bottom: 30px;">
                    {item_cards}
                </div>
                
                <div style="background-color: #fee; padding: 20px; border-radius: 12px; text-align: center; border: 1px solid #fcc;">
                    <p style="color: #c0392b; margin: 0; font-size: 14px; font-weight: 600;">
                        ⚠️ <strong>Hành động ngay:</strong> Vui lòng kiểm tra và lấy sản phẩm ra khỏi kệ để đảm bảo an toàn!
                    </p>
                </div>
                """
                
                def get_email_template_danger(content):
                    signature = """
                    <div style="margin-top: 40px; padding-top: 20px; border-top: 2px solid #e74c3c;">
                        <div style="font-size: 14px; color: #555555; line-height: 1.6;">
                            Trân trọng,<br>
                            <strong style="color: #e74c3c; font-size: 16px;">Thành Nam</strong><br>
                            <span style="color: #888;">Founder @ nguyenthanhnam.io.vn</span><br>
                            <a href="https://nguyenthanhnam.io.vn/wp" style="color: #e74c3c; text-decoration: none;">
                                https://nguyenthanhnam.io.vn/wp
                            </a>
                        </div>
                    </div>
                    """
                    
                    return f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    </head>
                    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa;">
                        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                            <div style="background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); padding: 30px 40px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600;">
                                    🚨 Cảnh Báo Hết Hạn
                                </h1>
                                <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">
                                    Yêu cầu xử lý ngay lập tức
                                </p>
                            </div>
                            <div style="padding: 40px;">
                                {content}
                            </div>
                            {signature}
                            <div style="background-color: #f8f9fa; padding: 20px 40px; text-align: center; border-top: 1px solid #e9ecef;">
                                <p style="color: #6c757d; font-size: 12px; margin: 0;">
                                    © 2025 nguyenthanhnam.io.vn - Hệ thống quản lý tự động
                                </p>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                
                body_html = get_email_template_danger(content)
                send_expiry_email(email, subject, body_html)
                
        # Chỉ gửi mail đúng vào 12 giờ đêm mỗi ngày
        time.sleep(seconds_until_next_midnight())

# Khởi động thread kiểm tra khi server chạy
def start_expiry_check_thread():
    import threading
    t1 = threading.Thread(target=check_and_notify_expiring_items, daemon=True)
    t2 = threading.Thread(target=check_and_notify_expired_items, daemon=True)
    t1.start()
    t2.start()

start_expiry_check_thread()

