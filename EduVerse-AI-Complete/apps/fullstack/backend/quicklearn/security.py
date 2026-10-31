"""Request identity and mandatory tenant filtering for the shared SQLite store.

Background workers have no request identity and operate on explicit queued source IDs.
HTTP and WebSocket requests must establish identity before entering application routes.
"""
from __future__ import annotations
import asyncio
import json
import os
from contextvars import ContextVar
from sqlalchemy import event, select
from sqlalchemy.orm import Session, with_loader_criteria
from starlette.responses import JSONResponse
from .db import models as m

principal: ContextVar[int | None] = ContextVar('principal', default=None)

OWNED = (m.Source, m.Note, m.Folder, m.Tag, m.Chat, m.QuizSession,
         m.Podcast, m.RevisionSession, m.ActivityLog)
SOURCE_LINKED = (m.Transcript, m.Segment, m.Concept, m.Card, m.QuizItem,
                 m.Job, m.LlmCall, m.UploadSession)

def criteria(uid):
    sources = select(m.Source.id).where(m.Source.user_id == uid)
    notes = select(m.Note.id).where(m.Note.source_id.in_(sources))
    cards = select(m.Card.id).where(m.Card.source_id.in_(sources))
    items = select(m.QuizItem.id).where(m.QuizItem.source_id.in_(sources))
    chats = select(m.Chat.id).where(m.Chat.user_id == uid)
    # Generated notes inherit source ownership, including notes created by workers.
    rules = [(model, model.user_id == uid) for model in OWNED if model is not m.Note]
    rules += [(m.Note, m.Note.source_id.in_(sources))]
    rules += [(model, model.source_id.in_(sources)) for model in SOURCE_LINKED]
    rules += [(m.NoteBlock, m.NoteBlock.note_id.in_(notes)),
              (m.Review, m.Review.card_id.in_(cards)),
              (m.QuizAttempt, m.QuizAttempt.quiz_item_id.in_(items)),
              (m.GradingFailure, m.GradingFailure.quiz_item_id.in_(items)),
              (m.Message, m.Message.chat_id.in_(chats))]
    return rules

@event.listens_for(Session, 'do_orm_execute')
def tenant_queries(state):
    uid = principal.get()
    if uid is None or not state.is_orm_statement:
        return
    for model, predicate in criteria(uid):
        state.statement = state.statement.options(with_loader_criteria(model, predicate, include_aliases=True))

@event.listens_for(Session, 'before_flush')
def tenant_writes(session, context, instances):
    uid = principal.get()
    if uid is None:
        return
    from .errors import ForbiddenError
    references = {'source_id': m.Source, 'folder_id': m.Folder, 'note_id': m.Note,
                  'card_id': m.Card, 'concept_id': m.Concept, 'quiz_item_id': m.QuizItem,
                  'session_id': m.QuizSession, 'chat_id': m.Chat}
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        if isinstance(obj, OWNED):
            if obj in session.new and obj.user_id is None:
                obj.user_id = uid
            if obj.user_id != uid:
                raise ForbiddenError('This resource belongs to another account.')
        for field, model in references.items():
            value = getattr(obj, field, None)
            if value is not None and session.get(model, value) is None:
                raise ForbiddenError('The referenced resource is not available to this account.')
        for source_id in getattr(obj, 'source_ids', []) or []:
            if session.get(m.Source, source_id) is None:
                raise ForbiddenError('The referenced source is not available to this account.')
        if isinstance(obj, m.Chat) and obj.scope_id is not None:
            model = m.Source if str(obj.scope_type) == 'source' else m.Folder
            if session.get(model, obj.scope_id) is None:
                raise ForbiddenError('The conversation scope is not available to this account.')

class SecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if scope['type'] not in ('http', 'websocket') or not path.startswith('/api/v1'):
            return await self.app(scope, receive, send)
        if path in ('/api/v1/health', '/api/v1/auth/login', '/api/v1/auth/register'):
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        header = headers.get(b'authorization', b'').decode()
        token = header[7:] if header.startswith('Bearer ') else None
        if scope['type'] == 'websocket':
            token = next((p[7:] for p in scope.get('subprotocols', []) if p.startswith('bearer.')), None)
        from .auth import get_current_user
        try:
            user = await asyncio.to_thread(get_current_user, token)
        except Exception:
            if scope['type'] == 'websocket':
                return await send({'type': 'websocket.close', 'code': 4401})
            return await JSONResponse({'message': 'Authentication required.'}, status_code=401)(scope, receive, send)
        admins = {v.strip().lower() for v in os.getenv('EDUVERSE_ADMIN_EMAILS', '').split(',') if v.strip()}
        admin_operation = (path.startswith('/api/v1/settings') and
                           (scope.get('method') != 'GET' or path.endswith('/models'))) or path.endswith('/optimize-fsrs')
        if admin_operation and user.email.lower() not in admins:
            return await JSONResponse({'message': 'Installation administrator permission required.'}, status_code=403)(scope, receive, send)
        marker = principal.set(user.id)
        try:
            if scope['type'] == 'websocket' and path.endswith('/ws/jobs'):
                async def filtered_send(message):
                    if message['type'] == 'websocket.send' and message.get('text'):
                        payload = json.loads(message['text'])
                        if payload.get('type') != 'ping':
                            from .db.session import session_scope
                            with session_scope() as session:
                                if not payload.get('source_id') or session.get(m.Source, payload['source_id']) is None:
                                    return
                    await send(message)
                return await self.app(scope, receive, filtered_send)
            return await self.app(scope, receive, send)
        finally:
            principal.reset(marker)
