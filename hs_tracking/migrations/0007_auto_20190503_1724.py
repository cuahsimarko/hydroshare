# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-05-03 17:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hs_tracking', '0006_auto_20190407_1436'),
    ]

    operations = [
        migrations.AddField(
            model_name='variable',
            name='rest',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='variable',
            name='landing',
            field=models.BooleanField(default=False),
        ),
    ]
