"""Create two local development users and one future event for manual two-user testing."""
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import SessionLocal, User, Event, EventParticipant, make_token
from sqlalchemy import select

with SessionLocal() as session:
    def get_or_create(pid, name):
        u = session.scalar(select(User).where(User.provider == 'dev', User.provider_user_id == pid))
        if not u:
            u = User(name=name, provider='dev', provider_user_id=pid, city='Симферополь')
            session.add(u); session.flush()
        return u
    alice = get_or_create('demo-organizer', 'Организатор')
    bob = get_or_create('demo-participant', 'Участник')
    event = session.scalar(select(Event).where(Event.title == 'Тестовое событие — два пользователя'))
    if not event:
        event = Event(title='Тестовое событие — два пользователя', city='Симферополь', location='Центр Симферополя',
                      starts_at=datetime.now(timezone.utc)+timedelta(days=1), capacity=10,
                      description='Служебное событие для проверки сценария организатор → участник → чат.',
                      lat=44.9521, lon=34.1024, organizer_id=alice.id)
        session.add(event); session.flush()
        session.add(EventParticipant(event_id=event.id, user_id=alice.id))
    session.commit()
    print('ORGANIZER_TOKEN=', make_token(alice))
    print('PARTICIPANT_TOKEN=', make_token(bob))
    print('EVENT_ID=', event.id)
