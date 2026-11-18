from django.test import TestCase
from .models import Author, Article


class DemoTest(TestCase):
    def test_create_author_and_article(self):
        author = Author.objects.create(name="Alice", email="alice@example.com")
        article = Article.objects.create(
            title="Hello MongoDB",
            slug="hello-mongodb",
            author=author,
            content="Testing MongoDB backend.",
        )
        self.assertEqual(article.author.name, "Alice")
