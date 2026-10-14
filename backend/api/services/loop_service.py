from api.services.focused_learning import outline_evidence
from api.services.material_service import ready_documents
from db.models import DocumentIngestion
from utils.observability import failure, get_logger
import time
from fastapi import HTTPException
from db.models import JourneyState, Topic, Attempt, AttemptMeta, Activity, SourceReview, Document
from retrieval.service import retrieve
from utils.citations import validate_citations


def validate_plan_references(result, passages):
    try:
        validate_citations(result, passages)
    except ValueError as exc:
        raise HTTPException(502, 'Invalid learning-plan source references') from exc


def state_for(db, journey_id) -> JourneyState:
    state = db.get(JourneyState, journey_id)
    if state is None:
        state = JourneyState(journey_id=journey_id, revision=db.query(Document).filter_by(journey_id=journey_id).count(), plan_revision=0, plan_status='needs_rebuild')
        db.add(state)
        db.flush()
    return state


def generate(provider, task, passages):
    started = time.perf_counter()
    get_logger('generation').info('generation_started', extra={'fields': {'evidence_count': len(passages)}})
    try:
        result = provider.generate(task, passages)
        if not isinstance(result, dict):
            raise ValueError('Invalid result')
        validate_citations(result, passages)
        get_logger('generation').info('generation_completed', extra={'fields': {'duration_ms': round((time.perf_counter() - started) * 1000, 2)}})
        return result
    except Exception as exc:
        raise failure('generation', exc) from exc


def source_context(db, journey_id, query, limit=12, all_sources=False, preferred_citations=None):
    documents = ready_documents(db, journey_id)
    started = time.perf_counter()
    get_logger('retrieval').info('retrieval_started', extra={'fields': {'journey_id': journey_id, 'document_count': len(documents)}})
    # Fetch before filtering so excluded passages don't consume the evidence budget.
    try:
        passages = retrieve(documents, query, limit=sum(len(d.passages) for d in documents), db=db, all_sources=all_sources)
    except Exception as exc:
        raise failure('retrieval', exc, journey_id=journey_id) from exc
    if preferred_citations:
        current = {f'{d.id}:{i}': {'id': f'{d.id}:{i}', 'document': d.name, **p}
                   for d in documents for i, p in enumerate(d.passages)}
        preferred = [current[c] for c in dict.fromkeys(preferred_citations) if c in current]
        chosen = {p['id'] for p in preferred}
        passages = preferred + [p for p in passages if p['id'] not in chosen]
    get_logger('retrieval').info('retrieval_completed', extra={'fields': {'journey_id': journey_id, 'passages': len(passages), 'duration_ms': round((time.perf_counter() - started) * 1000, 2)}})
    reviews = db.query(SourceReview).filter_by(journey_id=journey_id).order_by(SourceReview.id).all()
    decisions = {}
    for review in reviews:
        for citation in review.data.get('citations', []):
            decisions[citation] = review
    accepted = []
    for passage in passages:
        review = decisions.get(passage['id'])
        if review and review.decision == 'exclude':
            continue
        if review:
            passage = {**passage, 'source_review': {'decision': review.decision, 'source_claim': review.data.get('source_claim'), 'alternative': review.data.get('alternative'), 'reason': review.data.get('reason'), 'user_note': review.note, 'verification': 'unverified comparison; learner preference is not factual verification'}}
        accepted.append(passage)
    if not accepted:
        pending = db.query(DocumentIngestion).join(Document, Document.id == DocumentIngestion.document_id).filter(Document.journey_id == journey_id, DocumentIngestion.status.in_(['queued', 'processing'])).first()
        if pending is not None:
            raise HTTPException(409, 'Your materials are still processing. Please try again when they are ready.')
        raise HTTPException(400, 'Upload usable materials, or review excluded sources first')
    return accepted[:limit]


def rebuild_plan(db, journey, provider):
    state = state_for(db, journey.id)
    revision = state.revision
    documents = ready_documents(db, journey.id)
    passages = source_context(db, journey.id, journey.subject,
                              limit=sum(len(d.passages) for d in documents), all_sources=True)
    selected = outline_evidence(db, documents, passages)
    result = generate(provider, f'Build a learning plan for {journey.goal}: {journey.subject}. Return topics (1-30 objects with title, prerequisites as title strings, citations as passage IDs), concerns (up to 10 objects with source_claim as an exact quote from a cited passage, alternative, reason, citations), and citations. Flag only specific contradictions or possible errors; do not label material verified. Alternative explanations from model knowledge must be explicitly unverified, with no invented authority or external citations. Use source_review decisions when supplied. Infer a focused path from the complete supplied source outline and learner goal. Understand the central subjects before selecting topics. Combine overlapping concepts across documents, keep necessary foundations, and defer peripheral detail to chat. Do not turn every branch into a lesson. Order topics from foundations to application. A separate syllabus is not required; use objectives in the materials when present. For each topic also return focus (essential or foundation), rationale, learning_outcomes (strings), and deferred_details (strings). Outline summaries are not verbatim source text; omit concerns unless an exact source quote is available. Never guarantee exam coverage or success.', selected)
    topics = result.get('topics')
    concerns = result.get('concerns', [])
    if not isinstance(topics, list) or not 1 <= len(topics) <= 30 or not isinstance(concerns, list) or len(concerns) > 10:
        raise HTTPException(502, 'Invalid learning plan')
    for topic in topics:
        if not isinstance(topic, dict) or not isinstance(topic.get('title'), str) or not 1 <= len(topic['title'].strip()) <= 300 or not isinstance(topic.get('prerequisites', []), list) or any(not isinstance(p, str) for p in topic.get('prerequisites', [])):
            raise HTTPException(502, 'Invalid plan topic')
        validate_plan_references(topic, selected)
    # Optional reviews must be grounded, but a bad review should not discard valid topics.
    valid_concerns = []
    for index, concern in enumerate(concerns):
        reason = None
        if not isinstance(concern, dict) or not all(isinstance(concern.get(k), str) and concern[k] for k in ('source_claim', 'alternative', 'reason')):
            reason = 'invalid_fields'
        else:
            try:
                validate_plan_references(concern, selected)
            except HTTPException:
                reason = 'invalid_citations'
            if reason is None:
                import unicodedata
                normalize = lambda value: ' '.join(unicodedata.normalize('NFKC', value).split()).casefold()
                quoted_sources = [p['text'] for p in passages if p['id'] in concern['citations']]
                if not any(normalize(concern['source_claim']) in normalize(text) for text in quoted_sources):
                    reason = 'quote_not_in_cited_source'
        if reason:
            get_logger('planning').warning('plan_concern_rejected', extra={'fields': {
                'journey_id': journey.id, 'concern_index': index, 'reason': reason}})
        else:
            valid_concerns.append(concern)
    concerns = valid_concerns
    db.refresh(state)
    if state.revision != revision:
        raise HTTPException(409, 'Materials changed during planning. Rebuild the plan.')
    existing = db.query(Topic).filter_by(journey_id=journey.id).all()
    by_title = {t.title.casefold(): t for t in existing}
    for old in existing:
        old.active = False
    seen = set()
    for data in topics:
        title = data['title'].strip()
        if title.casefold() in seen:
            continue
        seen.add(title.casefold())
        topic = by_title.get(title.casefold())
        if topic is None:
            topic = Topic(journey_id=journey.id, title=title, active=True, data={})
            db.add(topic)
        topic.active = True
        topic.data = {**data, 'revision': revision}
    for concern in concerns:
        # Keep decisions/history when an unchanged concern is raised again.
        found = db.query(SourceReview).filter_by(journey_id=journey.id).all()
        if not any(r.data.get('source_claim') == concern['source_claim'] and r.data.get('citations') == concern['citations'] for r in found):
            db.add(SourceReview(journey_id=journey.id, revision=revision, data=concern, decision='pending', note=''))
    state.plan_revision = revision
    state.plan_status = 'ready'
    db.commit()


def topic_progress(db, journey_id):
    now = time.time()
    topics = db.query(Topic).filter_by(journey_id=journey_id).order_by(Topic.id).all()
    attempts = db.query(Attempt, Activity, AttemptMeta).join(Activity, Attempt.activity_id == Activity.id).outerjoin(AttemptMeta, AttemptMeta.attempt_id == Attempt.id).filter(Activity.journey_id == journey_id).order_by(Attempt.id).all()
    state = state_for(db, journey_id)
    summaries = []
    for topic in topics:
        rows = [(a, activity, meta) for a, activity, meta in attempts if activity.topic.casefold() == topic.title.casefold()]
        current = [(a, activity, meta) for a, activity, meta in rows if activity.data.get('revision', 0) == state.revision]
        independent = [(a, m) for a, _, m in current if m and not m.supported and a.feedback.get('verdict') == 'correct']
        status, due = 'unpractised', None
        if rows and not current:
            status = 'recheck_after_update'
        elif current:
            latest = current[-1][0].feedback.get('verdict')
            if latest == 'needs_revision':
                status = 'needs_revision'
            elif latest == 'clarification_needed':
                status = 'clarification_needed'
            elif independent:
                first_time = independent[0][1].created_at
                retained = any(m.created_at >= first_time + 86400 for _, m in independent[1:])
                status = 'retained_in_practice' if retained else 'revisit_later'
                due = independent[-1][1].created_at + (7 * 86400 if retained else 86400)
            else:
                status = 'needs_independent_check'
        summaries.append({'id': topic.id, 'title': topic.title, 'active': topic.active, 'citations': topic.data.get('citations', []), 'prerequisites': topic.data.get('prerequisites', []), 'focus': topic.data.get('focus', 'essential'), 'rationale': topic.data.get('rationale', ''), 'learning_outcomes': topic.data.get('learning_outcomes', []), 'deferred_details': topic.data.get('deferred_details', []), 'attempts': len(rows), 'status': status, 'due_at': due, 'due': due is not None and due <= now})
    return summaries


def recommendation(db, journey_id):
    topics = [t for t in topic_progress(db, journey_id) if t['active']]
    if not topics:
        return {'topic': None, 'action': 'rebuild_plan', 'reason': 'Create a learning map from your materials first.'}
    weak = [t for t in topics if t['status'] in ('needs_revision', 'clarification_needed', 'needs_independent_check', 'recheck_after_update')]
    due = [t for t in topics if t['due']]
    new = [t for t in topics if t['status'] == 'unpractised']
    chosen = (weak or due or new or topics)[0]
    title_lookup = {t['title'].casefold(): t for t in topics}
    for prerequisite in chosen['prerequisites']:
        candidate = title_lookup.get(prerequisite.casefold())
        if candidate and candidate['status'] in ('unpractised', 'needs_revision'):
            return {'topic': candidate['title'], 'action': 'study', 'reason': f'This prerequisite will help you work on {chosen["title"]}.'}
    if chosen in weak:
        return {'topic': chosen['title'], 'action': 'revise_then_practise', 'reason': 'Your recent answers or updated materials call for a targeted revision and a fresh scenario.'}
    if chosen in due:
        return {'topic': chosen['title'], 'action': 'reassess', 'reason': 'Check retention using a new scenario after a delay.'}
    return {'topic': chosen['title'], 'action': 'practise', 'reason': 'Cover this topic with a fresh scenario. Correct answers remain practice evidence, not guaranteed mastery.'}
