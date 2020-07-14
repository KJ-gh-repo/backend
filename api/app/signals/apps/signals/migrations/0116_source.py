# Generated by Django 2.2.13 on 2020-07-27 08:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0115_auto_20200709_0910'),
    ]

    operations = [
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('description', models.TextField(max_length=3000)),
                ('order', models.PositiveIntegerField(null=True)),
            ],
            options={
                'ordering': ('order', 'name'),
            },
        ),
    ]
