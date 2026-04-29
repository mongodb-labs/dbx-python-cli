import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    # wagtailcore uses syncdb (MIGRATION_MODULES points to an empty directory),
    # so there is no wagtailcore migration to depend on.  Django's migrate
    # command runs syncdb apps before applying migrations, so wagtailcore_page
    # will exist by the time this migration runs.
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="HomePage",
            fields=[
                (
                    "page_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="wagtailcore.page",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("wagtailcore.page",),
        ),
    ]
