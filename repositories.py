from abc import ABC, abstractmethod


class BaseRepository(ABC):
    def __init__(self, model, db):
        self.model = model
        self.db = db

    def get_by_id(self, id):
        return self.model.query.get(id)

    def create(self, **kwargs):
        instance = self.model(**kwargs)
        self.db.session.add(instance)
        self.db.session.commit()
        return instance

    def update(self, id, **kwargs):
        instance = self.get_by_id(id)
        if not instance:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(instance, key, value)
        self.db.session.commit()
        return instance

    def delete(self, id):
        instance = self.get_by_id(id)
        if instance:
            self.db.session.delete(instance)
            self.db.session.commit()
            return True
        return False

    def get_all(self):
        return self.model.query.all()


class UserRepository(BaseRepository):
    def __init__(self, user_model, db):
        super().__init__(user_model, db)

    def get_by_username(self, username):
        return self.model.query.filter_by(username=username).first()

    def create_user(self, username, password_hash, email=None):
        user = self.model(username=username, password_hash=password_hash)
        if email:
            user.email = email
        self.db.session.add(user)
        self.db.session.commit()
        return user


class TaskRepository(BaseRepository):
    def __init__(self, task_model, db):
        super().__init__(task_model, db)

    def get_tasks_by_owner(self, owner_id):
        return self.model.query.filter_by(owner_id=owner_id).order_by(self.model.created_at.desc()).all()

    def get_tasks_paginated(self, owner_id, cursor=None, limit=20):
        query = self.model.query.filter_by(owner_id=owner_id).order_by(self.model.id.desc())

        total = query.count()

        if cursor is not None:
            query = query.filter(self.model.id < cursor)

        tasks = query.limit(limit + 1).all()

        next_cursor = None
        if len(tasks) > limit:
            tasks = tasks[:limit]
            next_cursor = tasks[-1].id

        return tasks, next_cursor, total

    def create_task(self, title, owner_id):
        task = self.model(title=title, owner_id=owner_id)
        self.db.session.add(task)
        self.db.session.commit()
        return task

    def update_task(self, task_id, title=None, status=None):
        task = self.get_by_id(task_id)
        if not task:
            return None
        if title is not None:
            task.title = title
        if status is not None:
            task.status = status
        self.db.session.commit()
        return task
