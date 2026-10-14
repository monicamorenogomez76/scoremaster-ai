"""In-memory library for API tests that do not exercise PostgreSQL."""
from dataclasses import replace
from uuid import uuid4

from backend.application.library import Work


class InMemoryLibrary:
    def __init__(self):
        self.works, self.files, self.bands, self.grades = {}, {}, {}, {}

    def store_work(self, user_id, upload):
        existing = next((work_id for work_id, (owner, sha) in self.files.items()
                         if owner == user_id and sha == upload.source_sha256), None)
        work = Work(existing or uuid4(), upload.title, upload.composer, upload.file_name, len(upload.source))
        self.works[work.id], self.files[work.id] = (user_id, work, upload.source), (user_id, upload.source_sha256)
        return work

    def list_works(self, user_id):
        return [work for owner, work, _ in self.works.values() if owner == user_id]

    def get_work(self, user_id, work_id):
        owner, work, _ = self.works.get(work_id, (None, None, None))
        return work if owner == user_id else None

    def work_file(self, user_id, work_id):
        owner, work, source = self.works.get(work_id, (None, None, None))
        return (source, work.file_name) if owner == user_id else None

    def latest_analysis(self, user_id, work_id):
        return None

    def delete_work(self, user_id, work_id):
        if self.get_work(user_id, work_id) is None:
            return False
        del self.works[work_id], self.files[work_id]
        return True

    def update_preparation(self, user_id, work_id, status):
        if self.get_work(user_id, work_id) is None:
            return None
        owner, work, source = self.works[work_id]
        self.works[work_id] = (owner, replace(work, preparation_status=status), source)
        return self.works[work_id][1]

    def preparation_priorities(self, user_id):
        return []

    def band_profile(self, user_id):
        return dict(self.bands.get(user_id, {}))

    def update_band_profile(self, user_id, changes):
        self.bands[user_id] = {**self.bands.get(user_id, {}), **changes}
        return dict(self.bands[user_id])

    def external_grades(self, user_id, work_id):
        return list(self.grades.get(work_id, [])) if self.get_work(user_id, work_id) else None

    def add_external_grade(self, user_id, work_id, grade):
        if self.get_work(user_id, work_id) is None:
            return None
        self.grades.setdefault(work_id, []).append(grade)
        return grade

    def delete_external_grade(self, user_id, work_id, grade_id):
        if self.get_work(user_id, work_id) is None:
            return False
        before = len(self.grades.get(work_id, []))
        self.grades[work_id] = [grade for grade in self.grades.get(work_id, []) if grade.id != grade_id]
        return len(self.grades[work_id]) < before
