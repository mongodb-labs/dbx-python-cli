# {{ project_name }} settings module.
# Import database-specific settings and add project-specific configurations here.

# Database Configuration
# ----------------------
# To use MongoDB (default):
from .mongodb import *  # noqa

# To use PostgreSQL (uncomment the line below and comment out the MongoDB import above):
# from .postgresql import *  # noqa

# Add project-specific settings below
# Example:
# DEBUG = False
# ALLOWED_HOSTS = ['example.com']

# Add project-specific apps to INSTALLED_APPS
INSTALLED_APPS += [  # noqa: F405
    # Add your project-specific apps here
    # Example:
    # "myapp",
]

# Queryable Encryption (QE) Configuration
# Uncomment the two lines below to enable Queryable Encryption settings.
# from .qe import *  # noqa
# INSTALLED_APPS += QE_INSTALLED_APPS  # noqa: F405

# Wagtail CMS Configuration
# Uncomment the four lines below to enable Wagtail settings.
# from .wagtail import *  # noqa
# INSTALLED_APPS += WAGTAIL_INSTALLED_APPS  # noqa: F405
# MIDDLEWARE += WAGTAIL_MIDDLEWARE  # noqa: F405
# MIGRATION_MODULES.update(WAGTAIL_MIGRATION_MODULES)  # noqa: F405
