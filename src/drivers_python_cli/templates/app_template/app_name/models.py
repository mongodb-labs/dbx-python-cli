from django.db import models


class Author(models.Model):
    """
    Author document with a unique email index.
    """

    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)  # Unique index in MongoDB

    bio = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),  # Index to speed up name lookups
        ]

    def __str__(self):
        return self.name


class Article(models.Model):
    """
    Article document with MongoDB-specific indexing features.
    """

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    author = models.ForeignKey(
        Author, on_delete=models.CASCADE, related_name="articles"
    )

    tags = models.JSONField(default=list)  # Great for arrays in MongoDB
    content = models.TextField()

    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # Compound index for search: title + published_at DESC
            models.Index(fields=["title", "-published_at"], name="title_date_idx"),
            # Text index for content search (MongoDB backend will map to $text index)
            models.Index(fields=["content"], name="content_text_idx"),
        ]
        unique_together = ("slug", "author")

    def __str__(self):
        return self.title


class Comment(models.Model):
    """
    Comments related to an article.
    """

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="comments"
    )
    user_name = models.CharField(max_length=200)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["article", "-created_at"], name="article_recent_comments_idx"
            ),
        ]

    def __str__(self):
        return f"Comment by {self.user_name} on {self.article}"
