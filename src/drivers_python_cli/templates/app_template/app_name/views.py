from django.shortcuts import render, get_object_or_404
from .models import Article


def article_list(request):
    articles = Article.objects.all().order_by("-published_at")
    return render(request, "demo/article_list.html", {"articles": articles})


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug)
    comments = article.comments.all().order_by("-created_at")
    return render(
        request, "demo/article_detail.html", {"article": article, "comments": comments}
    )
