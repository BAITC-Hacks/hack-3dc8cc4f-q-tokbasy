import { useEffect, useMemo, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const initials = (name) => name.split(' ').map((part) => part[0]).slice(0, 2).join('')
const displayDate = (date) => new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${date}T00:00:00`))
const pretty = (value) => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

function App() {
  const [employees, setEmployees] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [profile, setProfile] = useState(null)
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(`${API_URL}/api/employees`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((items) => { setEmployees(items); setSelectedId(items[0]?.employee_id) })
      .catch(() => setError('Unable to connect to the Career Quest API.'))
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setProfile(null)
    fetch(`${API_URL}/api/employees/${selectedId}`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then(setProfile)
      .catch(() => setError('Unable to load this employee profile.'))
  }, [selectedId])

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
        <div><h1>Career Quest</h1><p>AI Career Development Platform</p></div>
        <span className="iteration">MVP · Iteration 1</span>
      </header>

      <div className="layout">
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
          {profile && <Profile profile={profile} />}
        </main>
      </div>
    </div>
  )
}

function Profile({ profile }) {
  return <>
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

function Fact({ icon, label, value }) { return <div className="fact"><span>{icon}</span><div><small>{label}</small><strong>{value}</strong></div></div> }
function Skill({ skill }) { return <div className="skill"><div className="skill-info"><strong>{skill.name}</strong><span>{skill.level} / 5</span></div><div className="bar"><i style={{ width: `${skill.level * 20}%` }} /></div></div> }

export default App
