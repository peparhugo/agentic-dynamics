def paginate_query(query, page, per_page=20):
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max(1, -(-total // per_page))
    return {
        "data": [item.to_dict() for item in items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }
