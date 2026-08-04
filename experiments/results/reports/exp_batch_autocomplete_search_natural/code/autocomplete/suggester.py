import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Suggestion:
    id: str
    title: str
    description: str
    category: str
    url: str = ""


DEFAULT_DATASET: List[Suggestion] = [
    Suggestion("p1", "iPhone 15 Pro Max", "Latest Apple smartphone with A17 Pro chip", "Products", "/products/iphone-15-pro-max"),
    Suggestion("p2", "MacBook Air M3", "Thin and light laptop with Apple Silicon", "Products", "/products/macbook-air-m3"),
    Suggestion("p3", "iPad Pro 2024", "Powerful tablet with M4 chip and OLED display", "Products", "/products/ipad-pro-2024"),
    Suggestion("p4", "AirPods Pro 2nd Gen", "Noise cancelling wireless earbuds", "Products", "/products/airpods-pro-2"),
    Suggestion("p5", "Apple Watch Ultra 2", "Rugged smartwatch for extreme sports", "Products", "/products/apple-watch-ultra-2"),
    Suggestion("p6", "Samsung Galaxy S24 Ultra", "Flagship Android with built-in AI features", "Products", "/products/galaxy-s24-ultra"),
    Suggestion("p7", "Google Pixel 8 Pro", "Google's AI-powered flagship phone", "Products", "/products/pixel-8-pro"),
    Suggestion("p8", "Sony WH-1000XM5", "Industry-leading noise cancelling headphones", "Products", "/products/sony-wh1000xm5"),
    Suggestion("p9", "Dell XPS 16", "Premium Windows laptop with Intel Core Ultra", "Products", "/products/dell-xps-16"),
    Suggestion("p10", "Nintendo Switch OLED", "Gaming console with vibrant OLED screen", "Products", "/products/nintendo-switch-oled"),

    Suggestion("g1", "How to Build a REST API with Flask", "Step-by-step guide to building APIs in Python", "Guides", "/guides/build-rest-api-flask"),
    Suggestion("g2", "Getting Started with React 19", "New features and migration guide to React 19", "Guides", "/guides/react-19-getting-started"),
    Suggestion("g3", "Docker for Beginners", "Learn containerization from scratch", "Guides", "/guides/docker-beginners"),
    Suggestion("g4", "Python Async Programming", "Understanding async/await in Python", "Guides", "/guides/python-async"),
    Suggestion("g5", "Machine Learning with PyTorch", "Building neural networks with PyTorch", "Guides", "/guides/pytorch-ml"),
    Suggestion("g6", "Kubernetes Deployment Guide", "Deploying apps to production with K8s", "Guides", "/guides/kubernetes-deployment"),
    Suggestion("g7", "TypeScript Best Practices 2025", "Modern TypeScript patterns and techniques", "Guides", "/guides/typescript-best-practices"),
    Suggestion("g8", "CSS Grid Complete Guide", "Mastering CSS Grid layout system", "Guides", "/guides/css-grid-complete"),

    Suggestion("pp1", "Guido van Rossum", "Creator of the Python programming language", "People", "/people/guido-van-rossum"),
    Suggestion("pp2", "Linus Torvalds", "Creator of Linux and Git", "People", "/people/linus-torvalds"),
    Suggestion("pp3", "Ada Lovelace", "First computer programmer in history", "People", "/people/ada-lovelace"),
    Suggestion("pp4", "Alan Turing", "Father of theoretical computer science and AI", "People", "/people/alan-turing"),
    Suggestion("pp5", "Grace Hopper", "Pioneer of computer programming, created COBOL", "People", "/people/grace-hopper"),
    Suggestion("pp6", "Tim Berners-Lee", "Inventor of the World Wide Web", "People", "/people/tim-berners-lee"),
    Suggestion("pp7", "Margaret Hamilton", "Lead software engineer for Apollo missions", "People", "/people/margaret-hamilton"),

    Suggestion("l1", "San Francisco, California", "Tech hub of the United States", "Locations", "/locations/san-francisco"),
    Suggestion("l2", "Tokyo, Japan", "Vibrant metropolis blending tradition and technology", "Locations", "/locations/tokyo"),
    Suggestion("l3", "London, United Kingdom", "Historic capital and global financial center", "Locations", "/locations/london"),
    Suggestion("l4", "Singapore", "Island city-state and tech innovation hub", "Locations", "/locations/singapore"),
    Suggestion("l5", "Berlin, Germany", "European startup capital with rich history", "Locations", "/locations/berlin"),
    Suggestion("l6", "Bangalore, India", "Silicon Valley of India", "Locations", "/locations/bangalore"),
    Suggestion("l7", "Tel Aviv, Israel", "Startup nation's technology center", "Locations", "/locations/tel-aviv"),
    Suggestion("l8", "Seattle, Washington", "Home of Amazon and Microsoft headquarters", "Locations", "/locations/seattle"),

    Suggestion("f1", "What is our return policy?", "Returns accepted within 30 days of purchase", "FAQ", "/faq/return-policy"),
    Suggestion("f2", "How do I reset my password?", "Guide to password recovery and account security", "FAQ", "/faq/reset-password"),
    Suggestion("f3", "What payment methods are accepted?", "Credit cards, PayPal, Apple Pay, and Google Pay", "FAQ", "/faq/payment-methods"),
    Suggestion("f4", "How long does shipping take?", "Standard 5-7 business days, express 1-2 business days", "FAQ", "/faq/shipping-times"),
    Suggestion("f5", "Can I cancel my order?", "Cancel within 1 hour of placing the order", "FAQ", "/faq/cancel-order"),
    Suggestion("f6", "Is my data secure?", "We use enterprise-grade encryption and security", "FAQ", "/faq/data-security"),
    Suggestion("f7", "Do you offer student discounts?", "15% discount for verified students", "FAQ", "/faq/student-discount"),
    Suggestion("f8", "How to contact support?", "24/7 chat, email, and phone support available", "FAQ", "/faq/contact-support"),
]


class Suggester:
    def __init__(self, dataset: Optional[List[Suggestion]] = None):
        self._dataset = dataset or list(DEFAULT_DATASET)

    def search(self, query: str, max_results: int = 8) -> dict:
        if not query or len(query.strip()) < 1:
            return {"query": query, "groups": [], "total": 0}

        q = query.strip().lower()
        results = []
        for item in self._dataset:
            score = self._compute_score(item, q)
            if score > 0:
                results.append((score, item))

        results.sort(key=lambda x: (-x[0], x[1].title.lower()))

        grouped = {}
        for score, item in results:
            group = item.category
            if group not in grouped:
                grouped[group] = []
            if len(grouped[group]) < max_results:
                grouped[group].append({
                    "id": item.id,
                    "title": item.title,
                    "description": item.description,
                    "category": item.category,
                    "url": item.url,
                    "score": score,
                })

        groups = [
            {"category": cat, "results": items}
            for cat, items in grouped.items()
        ]

        total = sum(len(g["results"]) for g in groups)
        return {"query": query, "groups": groups, "total": total}

    @staticmethod
    def _compute_score(item: Suggestion, query: str) -> float:
        title_lower = item.title.lower()
        desc_lower = item.description.lower()

        if title_lower == query:
            return 100.0
        if title_lower.startswith(query):
            return 80.0 + (len(query) / len(title_lower)) * 10
        if query in title_lower:
            return 60.0

        words = query.split()
        if all(w in title_lower for w in words):
            return 50.0

        if desc_lower.startswith(query):
            return 40.0
        if query in desc_lower:
            return 30.0

        if any(w in title_lower for w in words):
            return 20.0 + sum(w in title_lower for w in words)

        if any(w in desc_lower for w in words):
            return 10.0 + sum(w in desc_lower for w in words) * 0.5

        return 0.0

    def get_trending(self, limit: int = 5) -> list:
        trending_ids = ["p1", "g1", "l1", "f1", "pp1"]
        items = []
        for s in self._dataset:
            if s.id in trending_ids:
                items.append({
                    "id": s.id,
                    "title": s.title,
                    "category": s.category,
                    "url": s.url,
                })
        return items[:limit]
