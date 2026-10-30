"""In-memory account repository for fast tests of the authentication service."""
from dataclasses import replace

from backend.application.accounts import DuplicateEmail


class InMemoryAccounts:
    def __init__(self):
        self.users, self.sessions, self.events, self.resets, self.verifications = {}, {}, [], {}, {}

    def add_user(self, user):
        if any(existing.email == user.email for existing in self.users.values()):
            raise DuplicateEmail(user.email)
        self.users[user.id] = user

    def user_by_email(self, email):
        return next((user for user in self.users.values() if user.email == email), None)

    def user_by_id(self, user_id):
        return self.users.get(user_id)

    def user_by_google_sub(self, sub):
        return next((user for user in self.users.values() if user.google_sub == sub), None)

    def link_google(self, user_id, sub):
        self.users[user_id] = replace(self.users[user_id], google_sub=sub)

    def rename_user(self, user_id, display_name):
        self.users[user_id] = replace(self.users[user_id], display_name=display_name)

    def set_password_hash(self, user_id, password_hash):
        self.users[user_id] = replace(self.users[user_id], password_hash=password_hash)

    def delete_user_sessions(self, user_id):
        self.sessions = {key: item for key, item in self.sessions.items() if item.user_id != user_id}

    def add_session(self, session):
        self.sessions[session.token_hash] = session

    def session_by_token_hash(self, token_hash):
        return self.sessions.get(token_hash)

    def delete_session(self, token_hash):
        self.sessions.pop(token_hash, None)

    def add_password_reset(self, reset):
        self.delete_password_resets(reset.user_id)
        self.resets[reset.token_hash] = reset

    def password_reset_by_hash(self, token_hash):
        return self.resets.get(token_hash)

    def delete_password_resets(self, user_id):
        self.resets = {key: item for key, item in self.resets.items() if item.user_id != user_id}

    def mark_email_verified(self, user_id):
        self.users[user_id] = replace(self.users[user_id], email_verified=True)

    def add_email_verification(self, verification):
        self.delete_email_verifications(verification.user_id)
        self.verifications[verification.token_hash] = verification

    def email_verification_by_hash(self, token_hash):
        return self.verifications.get(token_hash)

    def delete_email_verifications(self, user_id):
        self.verifications = {key: item for key, item in self.verifications.items() if item.user_id != user_id}

    def record_event(self, user_id, event, ip):
        self.events.append((user_id, event, ip))
