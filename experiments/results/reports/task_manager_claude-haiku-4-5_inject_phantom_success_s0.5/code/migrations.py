from app import create_app, db, Category, Priority, User

def init_db():
    app = create_app()

    with app.app_context():
        db.create_all()

        existing_priorities = Priority.query.count()
        if existing_priorities == 0:
            priorities = [
                Priority(level='low', rank=1),
                Priority(level='medium', rank=2),
                Priority(level='high', rank=3),
                Priority(level='urgent', rank=4),
            ]
            db.session.add_all(priorities)
            db.session.commit()

        existing_categories = Category.query.count()
        if existing_categories == 0:
            categories = [
                Category(name='Work', description='Work-related tasks'),
                Category(name='Personal', description='Personal tasks'),
                Category(name='Shopping', description='Shopping list'),
                Category(name='Health', description='Health and fitness'),
                Category(name='Learning', description='Educational tasks'),
            ]
            db.session.add_all(categories)
            db.session.commit()

        print('Database initialized successfully!')
        print('Created default priorities: Low, Medium, High, Urgent')
        print('Created default categories: Work, Personal, Shopping, Health, Learning')

if __name__ == '__main__':
    init_db()
