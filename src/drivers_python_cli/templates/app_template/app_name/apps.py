from django.apps import AppConfig


class DemoConfig(AppConfig):
    # default_auto_field is inherited from project settings (mongodb.py or postgresql.py)
    name = "{{ app_name }}"
