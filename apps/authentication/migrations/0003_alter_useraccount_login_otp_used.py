# Generated by Django 5.1.6 on 2025-03-26 22:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_useraccount_login_otp_useraccount_login_otp_used_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='useraccount',
            name='login_otp_used',
            field=models.BooleanField(default=False),
        ),
    ]
