from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    fullname = models.CharField(max_length=150)
    group = models.CharField(max_length=100)

    def __str__(self):
        return self.fullname

class Item(models.Model):
    barcode = models.CharField(max_length=100)
    itemname = models.CharField(max_length=255)
    quantity = models.IntegerField()
    expdate = models.DateField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='items')

    def __str__(self):
        return f"{self.itemname} ({self.barcode})"
    
class ProductData(models.Model):
    id = models.AutoField(primary_key=True)
    item_barcode = models.CharField(max_length=50)
    item_code = models.CharField(max_length=50)
    item_name = models.CharField(max_length=255)
    department = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    sub_category = models.CharField(max_length=100)
    vendor_code = models.CharField(max_length=50)
    vendor_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'product_data'  # Khớp đúng với bảng trong MySQL

    def __str__(self):
        return self.item_name