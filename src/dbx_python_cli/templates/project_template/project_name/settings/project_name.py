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
    # For Queryable Encryption demo:
    # "medical_records",
]

# Queryable Encryption (QE) Configuration
# Uncomment the import below to enable Queryable Encryption settings.
# from .qe import *  # noqa

# Wagtail CMS Configuration
# Uncomment the import below to enable Wagtail settings.
# from .wagtail import *  # noqa
