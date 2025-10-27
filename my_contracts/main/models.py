from django.db import models

# Create your models here.

class User(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    wallet_address = models.CharField(max_length=42, unique=True)


    def __str__(self):
        return self.username