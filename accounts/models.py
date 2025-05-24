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
