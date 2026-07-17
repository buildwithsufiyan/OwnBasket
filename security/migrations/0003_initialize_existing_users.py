from django.conf import settings
from django.db import migrations


def initialize_existing_users(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    AccountSecurityState = apps.get_model('security', 'AccountSecurityState')
    PasswordHistory = apps.get_model('security', 'PasswordHistory')
    TwoFactorProfile = apps.get_model('security', 'TwoFactorProfile')
    for user in User.objects.all().iterator(chunk_size=500):
        AccountSecurityState.objects.get_or_create(user_id=user.pk)
        TwoFactorProfile.objects.get_or_create(user_id=user.pk)
        if user.password:
            PasswordHistory.objects.get_or_create(user_id=user.pk, encoded_password=user.password)


class Migration(migrations.Migration):
    dependencies = [('security', '0002_accountsecuritystate')]
    operations = [migrations.RunPython(initialize_existing_users, migrations.RunPython.noop)]
