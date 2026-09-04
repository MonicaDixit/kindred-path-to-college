import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Typography, Row, Col, Card, Input, Select, Checkbox, Tag, Spin, Alert,
  Drawer, Descriptions, Button, Statistic, Divider, Empty,
} from 'antd'
import { MessageOutlined, EnvironmentOutlined, CalendarOutlined } from '@ant-design/icons'
import PageHeader from '../components/PageHeader.jsx'
import { api } from '../lib/api.js'
import { pct, money, dateLabel, daysUntil, selectivityLabel, MAJORS } from '../lib/format.js'

const { Title, Paragraph, Text } = Typography

function SelBadge({ rate }) {
  const label = selectivityLabel(rate)
  const color = rate == null ? 'default'
    : rate < 0.1 ? 'red' : rate < 0.2 ? 'volcano' : rate < 0.4 ? 'orange' : 'green'
  return <Tag color={color}>{label}</Tag>
}

export default function CollegeExplorer() {
  const [list, setList] = useState(null)
  const [err, setErr] = useState(null)
  const [q, setQ] = useState('')
  const [major, setMajor] = useState()
  const [fullNeed, setFullNeed] = useState(false)
  const [sel, setSel] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.colleges().then(setList).catch((e) => setErr(e.message))
  }, [])

  const filtered = useMemo(() => {
    if (!list) return []
    return list.filter((c) => {
      if (q && !`${c.name} ${c.location}`.toLowerCase().includes(q.toLowerCase())) return false
      if (major && !c.majors.includes(major)) return false
      if (fullNeed && !c.meets_full_need) return false
      return true
    })
  }, [list, q, major, fullNeed])

  const askAdvisor = (c) => {
    navigate('/advisor', {
      state: {
        suggestions: [
          `Tell me about ${c.name}. What are my chances and what's the deadline?`,
          `What financial aid does ${c.name} offer?`,
          `Is ${c.name} a reach, target, or safety for me?`,
        ],
      },
    })
  }

  if (err) return <div className="kp-container kp-section"><Alert type="error" message={err} /></div>

  return (
    <>
      <PageHeader
        eyebrow="College Explorer"
        title="Find a college that fits — and that you can afford"
        tagline="Every school here is scored on cost, aid, and first-generation support, not just prestige."
      />
      <section className="kp-section">
        <div className="kp-container">
          <Row gutter={[12, 12]} style={{ marginBottom: 24 }}>
            <Col xs={24} md={10}>
              <Input.Search
                placeholder="Search by name or location"
                allowClear
                value={q}
                onChange={(e) => setQ(e.target.value)}
                size="large"
              />
            </Col>
            <Col xs={14} md={8}>
              <Select
                placeholder="Filter by major"
                allowClear
                size="large"
                style={{ width: '100%' }}
                value={major}
                onChange={setMajor}
                options={MAJORS.map((m) => ({ value: m, label: m }))}
              />
            </Col>
            <Col xs={10} md={6} style={{ display: 'flex', alignItems: 'center' }}>
              <Checkbox checked={fullNeed} onChange={(e) => setFullNeed(e.target.checked)}>
                Meets 100% of need
              </Checkbox>
            </Col>
          </Row>

          {!list ? (
            <Spin />
          ) : filtered.length === 0 ? (
            <Empty description="No colleges match those filters" />
          ) : (
            <Row gutter={[20, 20]}>
              {filtered.map((c) => {
                const d = daysUntil(c.application_deadline)
                return (
                  <Col xs={24} md={12} key={c.id}>
                    <Card
                      className="kp-pathcard"
                      hoverable
                      styles={{ body: { padding: 22 } }}
                      style={{ height: '100%' }}
                      onClick={() => setSel(c)}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                        <Title level={4} style={{ margin: 0 }}>{c.name}</Title>
                        <SelBadge rate={c.acceptance_rate} />
                      </div>
                      <Text type="secondary">
                        <EnvironmentOutlined /> {c.location}
                      </Text>
                      <Paragraph style={{ marginTop: 12, marginBottom: 14 }} ellipsis={{ rows: 2 }}>
                        {c.description}
                      </Paragraph>
                      <Row gutter={8}>
                        <Col span={8}><Statistic title="Avg GPA" value={c.avg_gpa ?? '—'} valueStyle={{ fontSize: 18 }} /></Col>
                        <Col span={8}><Statistic title="Avg SAT" value={c.avg_sat ?? '—'} valueStyle={{ fontSize: 18 }} /></Col>
                        <Col span={8}><Statistic title="Accept" value={pct(c.acceptance_rate)} valueStyle={{ fontSize: 18 }} /></Col>
                      </Row>
                      <Divider style={{ margin: '14px 0' }} />
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                        {c.meets_full_need && <Tag color="green">Meets full need</Tag>}
                        <Tag>{money(c.total_cost)} sticker</Tag>
                        <Tag color="purple">{pct(c.first_gen_percent)} first-gen</Tag>
                        {d != null && (
                          <Text type={d < 30 ? 'danger' : 'secondary'} style={{ fontWeight: 600 }}>
                            <CalendarOutlined /> {d} days to deadline
                          </Text>
                        )}
                      </div>
                    </Card>
                  </Col>
                )
              })}
            </Row>
          )}
        </div>
      </section>

      <Drawer
        open={!!sel}
        onClose={() => setSel(null)}
        width={Math.min(560, typeof window !== 'undefined' ? window.innerWidth : 560)}
        title={sel?.name}
      >
        {sel && (
          <>
            <Paragraph>{sel.description}</Paragraph>
            <Button
              type="primary"
              icon={<MessageOutlined />}
              block
              size="large"
              style={{ marginBottom: 20 }}
              onClick={() => askAdvisor(sel)}
            >
              Ask the Discovery Advisor about {sel.name.split(' ')[0]}
            </Button>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="Location">{sel.location}</Descriptions.Item>
              <Descriptions.Item label="Selectivity">
                {selectivityLabel(sel.acceptance_rate)} ({pct(sel.acceptance_rate, 1)} admitted)
              </Descriptions.Item>
              <Descriptions.Item label="Avg GPA / SAT">{sel.avg_gpa} / {sel.avg_sat}</Descriptions.Item>
              <Descriptions.Item label="Undergrads">
                {sel.undergrad_population?.toLocaleString?.() ?? '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Graduation rate">{pct(sel.graduation_rate)}</Descriptions.Item>
              <Descriptions.Item label="Sticker cost">{money(sel.total_cost)}</Descriptions.Item>
              <Descriptions.Item label="Avg aid package">{money(sel.avg_aid)}</Descriptions.Item>
              <Descriptions.Item label="Students receiving aid">{pct(sel.percent_receiving_aid > 1 ? sel.percent_receiving_aid / 100 : sel.percent_receiving_aid)}</Descriptions.Item>
              <Descriptions.Item label="Meets full need">{sel.meets_full_need ? 'Yes' : 'Not guaranteed'}</Descriptions.Item>
              <Descriptions.Item label="First-gen students">{pct(sel.first_gen_percent)}</Descriptions.Item>
              <Descriptions.Item label="Pell recipients">{pct(sel.pell_grant_percent)}</Descriptions.Item>
              <Descriptions.Item label="Supplemental essays">{sel.essays_required ?? 0}</Descriptions.Item>
              <Descriptions.Item label="Application deadline">
                {dateLabel(sel.application_deadline)}
                {daysUntil(sel.application_deadline) != null && ` (${daysUntil(sel.application_deadline)} days)`}
              </Descriptions.Item>
              <Descriptions.Item label="Majors">
                {sel.majors.map((m) => <Tag key={m} style={{ marginBottom: 4 }}>{m}</Tag>)}
              </Descriptions.Item>
            </Descriptions>
          </>
        )}
      </Drawer>
    </>
  )
}
