import { Card, Tag, Typography, Empty, Divider, Timeline } from 'antd'
import {
  UserOutlined, BankOutlined, EditOutlined, CalendarOutlined,
} from '@ant-design/icons'
import { dateLabel } from '../lib/format.js'

const { Text, Title } = Typography

const PROFILE_LABELS = {
  name: 'Name', gpa: 'GPA', sat_score: 'SAT', major: 'Major',
  is_first_gen: 'First-gen', needs_financial_aid: 'Needs aid',
  sport: 'Sport', athlete_division: 'Athletics',
}

const STATUS_COLOR = { complete: 'green', in_progress: 'gold', not_started: 'default' }

export default function SessionSidebar({ state }) {
  const profile = state?.profile || {}
  const colleges = state?.selected_colleges || []
  const essays = state?.essays || {}
  const timeline = state?.timeline || {}
  const hasProfile = Object.keys(profile).length > 0
  const nameFor = (id) =>
    colleges.find((c) => c.id === id)?.name ||
    (state?.discussed_colleges || []).find((c) => c.id === id)?.name || id

  return (
    <Card
      title={<span><UserOutlined /> What Kindred knows</span>}
      styles={{ body: { padding: 16 } }}
      style={{ position: 'sticky', top: 84 }}
    >
      <Text type="secondary" style={{ fontSize: 12 }}>YOUR PROFILE</Text>
      <div style={{ marginTop: 8 }}>
        {hasProfile ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {Object.entries(profile).map(([k, v]) => (
              <Tag key={k} color="purple">
                {PROFILE_LABELS[k] || k}: {v === true ? 'yes' : String(v)}
              </Tag>
            ))}
          </div>
        ) : (
          <Text type="secondary" style={{ fontSize: 13 }}>
            Tell the advisor your GPA, test score, intended major, and background.
          </Text>
        )}
      </div>

      <Divider style={{ margin: '14px 0' }} />
      <Text type="secondary" style={{ fontSize: 12 }}>
        <BankOutlined /> COLLEGES ON YOUR LIST
      </Text>
      <div style={{ marginTop: 8 }}>
        {colleges.length ? (
          colleges.map((c) => (
            <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
              <Text style={{ fontSize: 13 }}>{c.name}</Text>
              <Text type="secondary" style={{ fontSize: 12 }}>{dateLabel(c.deadline)}</Text>
            </div>
          ))
        ) : (
          <Text type="secondary" style={{ fontSize: 13 }}>None yet — ask for college recommendations.</Text>
        )}
      </div>

      {Object.keys(essays).length > 0 && (
        <>
          <Divider style={{ margin: '14px 0' }} />
          <Text type="secondary" style={{ fontSize: 12 }}>
            <EditOutlined /> ESSAYS
          </Text>
          <div style={{ marginTop: 8 }}>
            {Object.entries(essays).map(([id, e]) => (
              <div key={id} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                <Text style={{ fontSize: 13 }}>{nameFor(id)}</Text>
                <Tag color={STATUS_COLOR[e.status] || 'default'} style={{ marginRight: 0 }}>
                  {e.status.replace('_', ' ')} · {e.drafts} draft{e.drafts === 1 ? '' : 's'}
                </Tag>
              </div>
            ))}
          </div>
        </>
      )}

      {timeline?.deadline_order?.length > 0 && (
        <>
          <Divider style={{ margin: '14px 0' }} />
          <Text type="secondary" style={{ fontSize: 12 }}>
            <CalendarOutlined /> DEADLINE ORDER
          </Text>
          <Timeline
            style={{ marginTop: 12 }}
            items={timeline.deadline_order.slice(0, 6).map((r) => ({
              color: r.days_left < 21 ? 'red' : '#6d28d9',
              children: (
                <Text style={{ fontSize: 12 }}>
                  <b>{r.college}</b> — {r.deadline} ({r.days_left}d)
                </Text>
              ),
            }))}
          />
        </>
      )}

      {(state?.sensitive_categories || []).length > 0 && (
        <>
          <Divider style={{ margin: '14px 0' }} />
          <Text type="secondary" style={{ fontSize: 12 }}>PRIVACY</Text>
          <Text style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
            Some things you shared are kept to this conversation only — they aren&apos;t
            saved to your profile and don&apos;t change your college recommendations.
          </Text>
        </>
      )}
    </Card>
  )
}
