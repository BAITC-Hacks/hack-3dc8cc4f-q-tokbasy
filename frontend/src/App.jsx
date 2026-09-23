import { useCallback, useEffect, useMemo, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const initials = (name) => name.split(' ').map((part) => part[0]).slice(0, 2).join('')
const displayDate = (date) => new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${date}T00:00:00`))
const pretty = (value) => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

function App() {
  const [mode, setMode] = useState('employee')
  const [employees, setEmployees] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [profile, setProfile] = useState(null)
  const [careerGap, setCareerGap] = useState(null)
  const [recommendations, setRecommendations] = useState([])
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [completion, setCompletion] = useState(null)
  const [hrDashboard, setHrDashboard] = useState(null)
  const [hrError, setHrError] = useState('')

  const loadProfile = useCallback(async (employeeId, signal) => {
    const responses = await Promise.all([
      fetch(`${API_URL}/api/employees/${employeeId}`, { signal }),
      fetch(`${API_URL}/api/employees/${employeeId}/career-gap`, { signal }),
      fetch(`${API_URL}/api/employees/${employeeId}/ai-recommendations`, { signal }),
    ])
    if (!responses.every((response) => response.ok)) throw new Error('Profile request failed')
    const [loadedProfile, loadedGap, loadedRecommendations] = await Promise.all(responses.map((response) => response.json()))
    setProfile(loadedProfile)
    setCareerGap(loadedGap)
    setRecommendations(loadedRecommendations.recommendations)
    setError('')
  }, [])

  useEffect(() => {
    fetch(`${API_URL}/api/employees`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((items) => { setEmployees(items); setSelectedId(items[0]?.employee_id) })
      .catch(() => setError('Unable to connect to the Career Quest API.'))
  }, [])

  useEffect(() => {
    if (!selectedId) return
    const controller = new AbortController()
    setProfile(null)
    setCareerGap(null)
    setRecommendations([])
    setCompletion(null)
    setError('')
    loadProfile(selectedId, controller.signal)
      .catch((requestError) => { if (requestError.name !== 'AbortError') setError('Unable to load this employee profile.') })
    return () => controller.abort()
  }, [selectedId, loadProfile])

  useEffect(() => {
    if (mode !== 'hr') return
    const controller = new AbortController()
    setHrDashboard(null)
    setHrError('')
    fetch(`${API_URL}/api/hr/dashboard`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error()))
      .then(setHrDashboard)
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') setHrError('Unable to load the HR dashboard.')
      })
    return () => controller.abort()
  }, [mode])

  const completeQuest = async (eventId) => {
    const response = await fetch(`${API_URL}/api/employees/${selectedId}/complete-quest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_id: eventId }),
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body.detail || 'Unable to complete this quest.')
    }
    const result = await response.json()
    setCompletion(result)
    await loadProfile(selectedId)
  }

  const filteredEmployees = useMemo(() => {
    const value = query.toLowerCase()
    return employees.filter((employee) =>
      `${employee.full_name} ${employee.role} ${employee.department}`.toLowerCase().includes(value)
    )
  }, [employees, query])

  return (
    <div className="app-shell">
      <header>
        <div className="brand-mark">CQ</div>
        <div><h1>Career Quest</h1><p>Career Development Platform</p></div>
        <nav className="mode-switch" aria-label="Dashboard mode">
          <button className={mode === 'employee' ? 'active' : ''} onClick={() => setMode('employee')}>EMPLOYEE</button>
          <button className={mode === 'hr' ? 'active' : ''} onClick={() => setMode('hr')}>HR</button>
        </nav>
        <span className="iteration">MVP · Iteration 4</span>
      </header>

      {mode === 'employee' ? <div className="layout">
        <aside>
          <div className="team-heading"><div><span>TEAM DIRECTORY</span><strong>{employees.length} employees</strong></div></div>
          <label className="search"><span>⌕</span><input aria-label="Search employees" placeholder="Search people or roles" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
          <div className="employee-list">
            {filteredEmployees.map((employee) => (
              <button className={selectedId === employee.employee_id ? 'employee active' : 'employee'} key={employee.employee_id} onClick={() => setSelectedId(employee.employee_id)}>
                <span className="avatar small">{initials(employee.full_name)}</span>
                <span className="employee-copy"><strong>{employee.full_name}</strong><small>{employee.role} · {employee.grade}</small></span>
                <span className="chevron">›</span>
              </button>
            ))}
            {!filteredEmployees.length && employees.length > 0 && <p className="empty">No employees match your search.</p>}
          </div>
        </aside>

        <main>
          {error && <div className="error">{error} Start the backend, then refresh this page.</div>}
          {!error && !profile && <div className="loading">Loading profile…</div>}
          {profile && <Profile profile={profile} careerGap={careerGap} recommendations={recommendations} completion={completion} onComplete={completeQuest} />}
        </main>
      </div> : <main className="hr-main">
        {hrError && <div className="error">{hrError} Start the backend, then refresh this page.</div>}
        {!hrError && !hrDashboard && <div className="loading">Loading HR dashboard…</div>}
        {hrDashboard && <HRDashboard dashboard={hrDashboard} />}
      </main>}
    </div>
  )
}

const statusOrder = ['completed', 'in_progress', 'no_show', 'declined', 'dropped', 'overdue']

function HRDashboard({ dashboard }) {
  const participation = dashboard.participation_summary
  const maximumGap = Math.max(...dashboard.top_skill_gaps.map((gap) => gap.employee_count), 1)
  return <div className="hr-dashboard">
    <div className="hr-heading"><span className="eyebrow">ORGANIZATION OVERVIEW</span><h2>HR DASHBOARD</h2><p>Live career development and participation insights</p></div>
    <section className="summary-grid">
      <SummaryCard label="Total Employees" value={dashboard.total_employees} />
      <SummaryCard label="Completion Rate" value={`${participation.completion_rate_percentage}%`} />
      <SummaryCard label="Employees Without Recommendations" value={dashboard.employees_without_recommendations} />
      <SummaryCard label="Total Activity Records" value={participation.total_activity_records} />
    </section>
    <div className="hr-grid">
      <section className="panel hr-panel">
        <div className="panel-title"><div><span className="section-icon">✦</span><h3>TOP SKILL GAPS</h3></div><small>Employees below target</small></div>
        <div className="gap-list">{dashboard.top_skill_gaps.map((gap) => <article key={gap.skill_id}>
          <div><strong>{gap.skill_name}</strong><span>{gap.employee_count} employees</span></div>
          <div className="gap-bar"><i style={{ width: `${100 * gap.employee_count / maximumGap}%` }} /></div>
        </article>)}</div>
      </section>
      <section className="panel hr-panel">
        <div className="panel-title"><div><span className="section-icon">◴</span><h3>ACTIVITY PARTICIPATION</h3></div><small>{participation.completed_records} completed</small></div>
        <div className="status-grid">{statusOrder.map((status) => <article key={status}>
          <span className={`status-dot ${status}`} />
          <div><small>{pretty(status)}</small><strong>{dashboard.activity_status_counts[status]}</strong></div>
        </article>)}</div>
      </section>
    </div>
  </div>
}

function SummaryCard({ label, value }) {
  return <article className="panel summary-card"><small>{label}</small><strong>{value}</strong></article>
}

function Profile({ profile, careerGap, recommendations, completion, onComplete }) {
  return <>
    {completion && <div className="success-banner" role="status"><strong>QUEST COMPLETED ✓</strong><span>{completion.event_title}</span><span>{completion.skill_changes.map((change) => `${change.skill_name} ${change.before} → ${change.after}`).join(' · ')}</span><span>Career readiness {completion.career_readiness_before}% → {completion.career_readiness_after}%</span></div>}
    <section className="profile-card">
      <div className="profile-top">
        <span className="avatar large">{initials(profile.full_name)}</span>
        <div className="identity"><span className="eyebrow">EMPLOYEE PROFILE</span><h2>{profile.full_name}</h2><p>{profile.role} <i>·</i> <b>{profile.grade}</b></p></div>
        <span className="language">{profile.preferred_language.toUpperCase()}</span>
      </div>
      <div className="facts">
        <Fact icon="⌂" label="Department" value={profile.department} />
        <Fact icon="◷" label="Tenure" value={`${profile.tenure_months} months`} />
        <Fact icon="◇" label="Work format" value={pretty(profile.work_format)} />
      </div>
      {profile.career_goal && <div className="goal"><span className="goal-icon">↗</span><div><small>CAREER GOAL</small><p>{profile.grade} <span>→</span> {profile.career_goal.target_grade}</p><em>{profile.career_goal.target_role}</em></div></div>}
    </section>

    {careerGap && <>
      <section className="panel readiness-panel">
        <div className="readiness-copy"><span className="eyebrow">CAREER READINESS</span><h3>{careerGap.current_grade} <span>→</span> {careerGap.target_grade}</h3><small>{careerGap.target_role}</small></div>
        <strong className="readiness-score">{careerGap.career_readiness}%</strong>
        <div className="readiness-bar"><i style={{ width: `${careerGap.career_readiness}%` }} /></div>
        <div className="critical-gaps"><span className="eyebrow">CRITICAL SKILL GAPS</span><div>{careerGap.critical_gaps.map((gap) => <article key={gap.skill_id}><strong>{gap.skill_name}</strong><small>Current {gap.current_level} / Target {gap.target_level}</small></article>)}{!careerGap.critical_gaps.length && <p className="empty compact">All critical requirements are met.</p>}</div></div>
      </section>

      <section className="recommendations-section">
        <div className="recommendations-heading"><div><span className="eyebrow coach-label">✨ AI CAREER COACH</span><h3>Recommended quests</h3></div><small>Verified deterministic career matches</small></div>
        <div className="quest-grid">{recommendations.map((recommendation) => <QuestCard key={recommendation.event_id} recommendation={recommendation} onComplete={onComplete} />)}{!recommendations.length && <div className="panel empty">No genuinely useful eligible activities are available.</div>}</div>
      </section>
    </>}

    <div className="content-grid">
      <section className="panel skills-panel">
        <div className="panel-title"><div><span className="section-icon">✦</span><h3>Skills</h3></div><small>0–5 proficiency scale</small></div>
        <div className="skills-list">{profile.skills.map((skill) => <Skill key={skill.skill_id} skill={skill} />)}</div>
      </section>
      <section className="panel activity-panel">
        <div className="panel-title"><div><span className="section-icon">◴</span><h3>Recent activity</h3></div><small>Latest {profile.recent_activity.length}</small></div>
        <div className="activity-list">
          {profile.recent_activity.map((activity) => <article className="activity" key={activity.record_id}><div className="event-icon">{activity.status === 'completed' ? '✓' : '↗'}</div><div className="activity-copy"><strong>{activity.event_title}</strong><time>{displayDate(activity.date)}</time></div><span className={`badge ${activity.status}`}>{pretty(activity.status)}</span></article>)}
          {!profile.recent_activity.length && <p className="empty">No recent activity.</p>}
        </div>
      </section>
    </div>
  </>
}

function QuestCard({ recommendation, onComplete }) {
  const explanation = recommendation.explanation
  const [completing, setCompleting] = useState(false)
  const [completionError, setCompletionError] = useState('')
  const submit = async () => {
    if (completing) return
    setCompleting(true)
    setCompletionError('')
    try { await onComplete(recommendation.event_id) }
    catch (error) { setCompletionError(error.message) }
    finally { setCompleting(false) }
  }
  return <article className="panel quest-card">
    <div className="quest-top"><span>{pretty(recommendation.event_type)}</span><span className={`coach-badge ${explanation?.source === 'openai' ? 'ai' : ''}`}>{explanation?.source === 'openai' ? 'AI explained' : 'Smart explanation'}</span><strong>{recommendation.score}%</strong></div>
    <h4>{recommendation.title}</h4><small className="match-label">CAREER MATCH</small>
    <div className="impact-list">{recommendation.skill_impacts.map((impact) => <div key={impact.skill_id}><strong>{impact.skill_name}</strong><small>Current: {impact.current_level} <span>After quest: {impact.possible_new_level}</span> Target: {impact.target_level}</small></div>)}</div>
    <div className="why"><b>WHY THIS QUEST?</b>{(explanation?.why_this_quest || recommendation.reasons.map((reason) => reason.text)).map((reason, index) => <p key={index}><span>✓</span>{reason}</p>)}</div>
    {explanation && <div className="coach-copy"><b>CAREER CONNECTION</b><p>{explanation.career_connection}</p><small><strong>Expected impact:</strong> {explanation.expected_impact}</small><small>{explanation.history_insight}</small></div>}
    {completionError && <p className="quest-error" role="alert">{completionError}</p>}
    <button className="complete-button" type="button" disabled={completing} onClick={submit}>{completing ? 'Completing...' : 'COMPLETE QUEST'}</button>
  </article>
}

function Fact({ icon, label, value }) { return <div className="fact"><span>{icon}</span><div><small>{label}</small><strong>{value}</strong></div></div> }
function Skill({ skill }) { return <div className="skill"><div className="skill-info"><strong>{skill.name}</strong><span>{skill.level} / 5</span></div><div className="bar"><i style={{ width: `${skill.level * 20}%` }} /></div></div> }

export default App
